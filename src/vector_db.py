import os

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

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
