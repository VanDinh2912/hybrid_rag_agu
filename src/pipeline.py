"""Module gộp luồng Hybrid RAG (Local SLM phối hợp Gemini API).

Luồng xử lý (True Hybrid Search):
1. Nhận câu hỏi thô của sinh viên.
2. Local SLM (Qwen/Ollama) chuẩn hóa câu hỏi thành văn phong học vụ.
3. Bỏ dấu thanh câu chuẩn hóa (fold) rồi truy vấn kết hợp (True Hybrid Search):
   - BM25 Retriever: tìm kiếm từ khóa chính xác (Điều, Khoản, thuật ngữ viết tắt).
   - ChromaDB Retriever (bge-m3): tìm kiếm ngữ nghĩa theo vector tương đồng.
   - EnsembleRetriever (RRF - Reciprocal Rank Fusion): gộp và xếp hạng lại tài liệu.
4. Gemini API sinh câu trả lời cuối cùng dựa trên ngữ cảnh đã truy xuất.

Chiến lược oversampling (retrieve_k ≥ top_k):
- Bộ truy xuất trả về `retrieve_k` ứng viên để tính Hit@K chính xác trong evaluation
  (recall window rộng hơn cửa sổ ngữ cảnh generator).
- Chỉ `top_k` chunk đứng đầu (theo RRF ranking) được đưa vào generator —
  giữ nguyên chất lượng câu trả lời, không mở rộng context window không cần thiết.
- `sources` trả về TOÀN BỘ retrieve_k chunk để evaluation đo Hit@retrieve_k,
  `gen_docs` chỉ là top_k đầu để generator dùng.

Tương thích ngược:
- Nếu use_hybrid=False hoặc ChromaDB không hỗ trợ BM25, pipeline tự động lùi về
  `vector_db.similarity_search` thuần vector ban đầu.
"""

import os
from typing import Any, Optional

from langchain_core.documents import Document

from src.query_normalizer import normalize_user_query
from src.retrieval import SYNONYM_DICTIONARY, expand_query_with_synonyms
from src.text_utils import fold
from src.vector_db import (
    DEFAULT_BM25_WEIGHT,
    DEFAULT_VECTOR_WEIGHT,
    DEFAULT_RRF_C,
    extract_documents_from_chroma,
    bm25_tokenize,
)

try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:
    try:
        from langchain_classic.retrievers.ensemble import EnsembleRetriever
    except ImportError:
        from langchain_community.retrievers import EnsembleRetriever

from langchain_community.retrievers import BM25Retriever

DEFAULT_OVERSAMPLE_FACTOR = 2


def _preview(text: str, limit: int = 160) -> str:
    """Một dòng xem trước của chunk, dùng khi liệt kê nguồn trích dẫn."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def describe_document(doc: Any, index: int) -> dict:
    """Trích metadata của một chunk LangChain Document thành dict hiển thị được."""
    metadata = getattr(doc, "metadata", None) or {}
    content = getattr(doc, "page_content", "") or ""
    return {
        "rank": index + 1,
        "source": str(metadata.get("source") or "không rõ nguồn"),
        "tier": str(metadata.get("tier") or "Khác"),
        "chunk_id": metadata.get("chunk_id", index),
        "preview": _preview(content),
        "chars": len(content),
    }


class HybridRAGPipeline:
    """Điều phối toàn bộ luồng True Hybrid RAG."""

    def __init__(
        self,
        vector_db: Any,
        local_slm: Any,
        generator: Any,
        oversample_factor: int = DEFAULT_OVERSAMPLE_FACTOR,
        use_hybrid: bool = True,
        bm25_weight: float = DEFAULT_BM25_WEIGHT,
        vector_weight: float = DEFAULT_VECTOR_WEIGHT,
        retriever: Optional[Any] = None,
        expand_query: bool = True,
    ):
        self.vector_db = vector_db
        self.local_slm = local_slm
        self.generator = generator
        self.oversample_factor = max(1, int(oversample_factor))
        self.use_hybrid = use_hybrid and os.getenv("ENABLE_HYBRID_SEARCH", "1").lower() not in {"0", "false", "no"}
        self.bm25_weight = float(os.getenv("BM25_WEIGHT", str(bm25_weight)))
        self.vector_weight = float(os.getenv("CHROMA_WEIGHT", str(vector_weight)))
        self.expand_query = expand_query and os.getenv("ENABLE_QUERY_EXPANSION", "1").lower() not in {"0", "false", "no"}

        # Nếu người dùng truyền thẳng retriever tùy chỉnh vào
        self.custom_retriever = retriever

        # Khởi tạo EnsembleRetriever (BM25 + Chroma) nếu được bật
        self.ensemble_retriever: Optional[Any] = None
        if self.custom_retriever is not None:
            self.ensemble_retriever = self.custom_retriever
        elif self.use_hybrid:
            self._init_hybrid_retriever()

    def _init_hybrid_retriever(self) -> None:
        """Tự động thiết lập BM25 và kết hợp với ChromaDB qua EnsembleRetriever (RRF)."""
        try:
            # Nếu vector_db vốn đã là một retriever có phương thức invoke
            if hasattr(self.vector_db, "invoke") and not hasattr(self.vector_db, "get"):
                self.ensemble_retriever = self.vector_db
                return

            if not hasattr(self.vector_db, "get"):
                return

            docs = extract_documents_from_chroma(self.vector_db)
            if not docs:
                return

            bm25 = BM25Retriever.from_documents(docs, preprocess_func=bm25_tokenize)
            bm25.k = 12  # Oversampling: truy xuất 12 ứng viên để tăng Recall/Hit@K

            chroma_ret = self.vector_db.as_retriever(search_kwargs={"k": 12})  # Đồng bộ với BM25

            weights = [self.bm25_weight, self.vector_weight]
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[bm25, chroma_ret],
                weights=weights,
                c=DEFAULT_RRF_C,
                id_key="chunk_id",
            )
            print(
                f"[HybridSearch] Đã kích hoạt True Hybrid Search (BM25={weights[0]:.2f} + Chroma={weights[1]:.2f}, c={DEFAULT_RRF_C})."
            )
        except Exception as exc:
            print(f"[HybridSearch] Cảnh báo: không thể khởi tạo BM25 ({exc}) — tự động lùi về Chroma vector search.")
            self.ensemble_retriever = None

    def retrieve(self, query: str, k: int = 6, fallback_query: Optional[str] = None) -> list[Document]:
        """Truy xuất tài liệu: True Hybrid Search (BM25 + Vector RRF) hoặc Vector Search thuần túy.

        Với oversampling, trả về đúng k chunks tốt nhất (Best-First Search / Beam Filter).
        Đảm bảo trả về danh sách Document giữ nguyên vẹn metadata (chunk_id, source, tier).
        
        Args:
            query: Câu hỏi truy xuất chính (thường là normalized_query)
            k: Số chunk cần trả về
            fallback_query: Câu hỏi dự phòng (thường là original_user_query) để chạy song song
        """
        k = max(1, int(k))

        # 1. Trường hợp sử dụng True Hybrid Search (EnsembleRetriever)
        if self.use_hybrid and self.ensemble_retriever is not None:
            try:
                # Đồng bộ tham số k cho các sub-retrievers bên trong
                sub_retrievers = getattr(self.ensemble_retriever, "retrievers", [])
                for r in sub_retrievers:
                    if hasattr(r, "k"):
                        r.k = k
                    elif hasattr(r, "search_kwargs") and isinstance(r.search_kwargs, dict):
                        r.search_kwargs["k"] = k

                docs = self.ensemble_retriever.invoke(query)
                
                # Fallback Query: chạy song song với câu hỏi gốc nếu được cung cấp
                if fallback_query and fallback_query != query:
                    try:
                        fallback_docs = self.ensemble_retriever.invoke(fallback_query)
                        # Gộp và khử trùng lặp theo chunk_id
                        seen_chunk_ids = set()
                        merged_docs = []
                        
                        # Thêm docs từ query chính
                        for doc in docs:
                            chunk_id = doc.metadata.get("chunk_id")
                            if chunk_id not in seen_chunk_ids:
                                seen_chunk_ids.add(chunk_id)
                                merged_docs.append(doc)
                        
                        # Thêm docs từ fallback query nếu chưa có
                        for doc in fallback_docs:
                            chunk_id = doc.metadata.get("chunk_id")
                            if chunk_id not in seen_chunk_ids:
                                seen_chunk_ids.add(chunk_id)
                                merged_docs.append(doc)
                        
                        docs = merged_docs
                        print(f"[FallbackQuery] Đã gộp {len(docs)} chunk từ 2 query (normalized + original)")
                    except Exception as exc:
                        print(f"[FallbackQuery] Lỗi khi chạy fallback query ({exc}), chỉ dùng kết quả chính.")
                
                # Lọc lấy Top-k chunks tốt nhất (Best-First Search / Beam Filter)
                return docs[:k]
            except Exception as exc:
                print(f"[HybridSearch] Lỗi truy xuất qua EnsembleRetriever ({exc}), lùi về similarity_search.")

        # 2. Fallback tương thích ngược: ChromaDB similarity_search (sử dụng query đã fold để khớp tài liệu OCR mất dấu)
        vector_query = fold(query)
        return self.vector_db.similarity_search(vector_query, k=k)

    def run(self, question: str, top_k: int = 4) -> dict:
        """Xử lý một câu hỏi với True Hybrid Search và oversampling.

        Tham số:
            question: câu hỏi thô của sinh viên.
            top_k: số chunk đưa vào generator (và đo Hit@top_k nếu evaluation
                   không tự đặt retrieve_k riêng).

        Trả về dict gồm:
            raw_query, normalized_query, retrieval_query,
            contexts: nội dung top_k chunk đầu (cho generator),
            sources:  metadata TẤT CẢ retrieve_k chunk (cho Hit@K evaluation),
            gen_docs: top_k LangChain Document đầu (dùng nội bộ, không in ra),
            answer:   câu trả lời Gemini.
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Câu hỏi phải là chuỗi không rỗng.")
        raw_query = question.strip()
        top_k = max(1, int(top_k))

        # --- Oversampling: lấy nhiều ứng viên hơn, chỉ cho generator top_k đầu ---
        # Với oversample_factor=2 và top_k=6, retrieve_k=12 để tăng Recall/Hit@K
        retrieve_k = top_k * self.oversample_factor

        # Bước 1: Chuẩn hóa câu hỏi bằng Qwen (normalize_user_query)
        normalized_query = normalize_user_query(self.local_slm, raw_query)

        # Bước 2: Mở rộng từ khóa (Query Expansion) bằng từ điển đồng nghĩa pháp lý
        expanded_query = (
            expand_query_with_synonyms(normalized_query)
            if self.expand_query
            else normalized_query
        )

        # BM25 hoạt động tốt nhất với câu GỐC CÓ DẤU (bm25_tokenize tự xử lý fold nội bộ).
        # Chỉ fold cho ChromaDB vector search (retrieval_query dùng để log/debug).
        retrieval_query = fold(expanded_query)

        # Truy xuất True Hybrid — truyền câu CÓ DẤU (đã mở rộng từ đồng nghĩa) vào retrieve() để BM25 & ChromaDB khớp tốt nhất.
        # Đồng thời truyền câu hỏi gốc (raw_query) làm fallback_query để đảm bảo không mất chunk nếu chuẩn hóa làm mất từ khóa.
        all_docs = self.retrieve(expanded_query, k=retrieve_k, fallback_query=raw_query)

        # Generator chỉ nhận top_k đầu — recall window rộng hơn mà context không phình.
        gen_docs = all_docs[:top_k]
        contexts = [doc.page_content for doc in gen_docs]

        # sources chứa TOÀN BỘ retrieve_k để evaluation đo Hit@retrieve_k.
        sources = [describe_document(doc, i) for i, doc in enumerate(all_docs)]

        answer = self.generator.generate_answer(query=normalized_query, retrieved_docs=gen_docs)

        return {
            "raw_query": raw_query,
            "normalized_query": normalized_query,
            "expanded_query": expanded_query,
            "retrieval_query": retrieval_query,
            "contexts": contexts,
            "sources": sources,
            "answer": answer,
        }


