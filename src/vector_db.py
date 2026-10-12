import os
import re
from typing import Any, Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from src.text_utils import fold

try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:
    try:
        from langchain_classic.retrievers.ensemble import EnsembleRetriever
    except ImportError:
        from langchain_community.retrievers import EnsembleRetriever


DEFAULT_BM25_WEIGHT = 0.4
DEFAULT_VECTOR_WEIGHT = 0.6
DEFAULT_RRF_C = 60


def bm25_tokenize(text: str) -> list[str]:
    """Tokenizer tối ưu cho BM25 trong môi trường tài liệu hỗn hợp (OCR không dấu & chuẩn có dấu).

    Sinh cả token gốc (có dấu) và token đã fold (bỏ dấu thanh), giúp so khớp hoàn hảo:
    - Tài liệu Tầng 1 bị mất dấu ("Dieu 12", "hoc phi")
    - Tài liệu chuẩn có dấu ("Thiết kế và cài đặt mạng", "chuẩn đầu ra ELO 9")
    """
    clean_raw = re.sub(r"[^\w\s]", " ", text.lower())
    raw_tokens = clean_raw.split()
    clean_folded = re.sub(r"[^\w\s]", " ", fold(text))
    folded_tokens = clean_folded.split()
    return raw_tokens + folded_tokens


def extract_documents_from_chroma(vector_db: Any) -> list[Document]:
    """Trích xuất toàn bộ Document (nội dung + metadata) từ ChromaDB collection đã persist."""
    data = vector_db.get()
    raw_docs = data.get("documents") or []
    raw_metas = data.get("metadatas") or []
    documents: list[Document] = []
    for i, (text, meta) in enumerate(zip(raw_docs, raw_metas)):
        metadata = dict(meta or {})
        if "chunk_id" not in metadata:
            metadata["chunk_id"] = i
        documents.append(Document(page_content=text, metadata=metadata))
    return documents



class VectorStoreManager:
    def __init__(self, persist_directory: str | None = None):
        print("Đang tải mô hình Embedding BAAI/bge-m3 lên phần cứng...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': 'cpu'}, # Đổi thành 'cuda' nếu máy hỗ trợ GPU tốt
            encode_kwargs={'normalize_embeddings': True}
        )
        self.persist_directory = persist_directory or os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

    def create_vector_store(self, chunks: list[dict], collection_name="agu_regulations"):
        """Nạp chunk (kết quả của DocumentChunker.chunk_document) vào ChromaDB.

        Mỗi chunk là {"text", "tier", "source"}; metadata lưu kèm chunk_id đánh số
        tuần tự toàn đợt nạp để truy vết và thống kê Recall@K theo từng tầng.
        """
        # Xóa collection cũ để mỗi lần chạy rebuild index từ data/, tránh nhân đôi chunk khi chạy lại
        try:
            Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_name=collection_name,
            ).delete_collection()
        except Exception:
            pass

        documents = [
            Document(
                page_content=chunk["text"],
                metadata={
                    "tier": chunk["tier"],
                    "source": chunk["source"],
                    "chunk_id": i,
                },
            )
            for i, chunk in enumerate(chunks)
        ]

        vector_db = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            collection_name=collection_name,
            persist_directory=self.persist_directory,
        )
        return vector_db

    def load_vector_store(self, collection_name="agu_regulations"):
        """Kết nối ChromaDB đã persist để truy vấn (không nạp lại corpus)."""
        return Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
            collection_name=collection_name,
        )

    def create_bm25_retriever(self, vector_db: Any, k: int = 6) -> BM25Retriever:
        """Tạo BM25Retriever từ toàn bộ tài liệu đã lưu trong ChromaDB với dual tokenizer."""
        docs = extract_documents_from_chroma(vector_db)
        if not docs:
            raise ValueError("ChromaDB chưa có tài liệu nào để xây dựng chỉ mục BM25.")
        bm25_retriever = BM25Retriever.from_documents(docs, preprocess_func=bm25_tokenize)
        bm25_retriever.k = max(1, int(k))
        return bm25_retriever


    def create_ensemble_retriever(
        self,
        vector_db: Any,
        weights: Optional[list[float]] = None,
        c: int = DEFAULT_RRF_C,
        k: int = 6,
    ) -> EnsembleRetriever:
        """Tạo EnsembleRetriever kết hợp BM25 (từ khóa) và Chroma (ngữ nghĩa) theo RRF.

        weights: [bm25_weight, vector_weight]. Mặc định [0.4, 0.6].
        c: hằng số làm mượt xếp hạng Reciprocal Rank Fusion (mặc định 60).
        id_key: 'chunk_id' để so khớp chính xác từng chunk giữa hai bộ truy xuất.
        """
        bm25_w = float(os.getenv("BM25_WEIGHT", str(DEFAULT_BM25_WEIGHT)))
        vector_w = float(os.getenv("CHROMA_WEIGHT", str(DEFAULT_VECTOR_WEIGHT)))
        resolved_weights = weights or [bm25_w, vector_w]

        bm25_retriever = self.create_bm25_retriever(vector_db, k=k)
        chroma_retriever = vector_db.as_retriever(search_kwargs={"k": k})

        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, chroma_retriever],
            weights=resolved_weights,
            c=c,
            id_key="chunk_id",
        )
        return ensemble_retriever

