"""Module gộp luồng Hybrid RAG (Local SLM phối hợp Gemini API).

Luồng xử lý:
1. Nhận câu hỏi thô của sinh viên.
2. Local SLM (Qwen/Ollama) chuẩn hóa câu hỏi thành văn phong học vụ.
3. Bỏ dấu thanh câu chuẩn hóa (fold) rồi truy vấn VectorDB (bge-m3 + ChromaDB)
   lấy top-k chunk — chunk Tầng 1 bị OCR mất dấu, embed câu đã fold để câu hỏi
   nằm cùng không gian vector với chunk (nếu không truy xuất trượt hẳn 1054/1059).
4. Gemini API sinh câu trả lời cuối cùng dựa trên ngữ cảnh đã truy xuất.

Chiến lược oversampling (retrieve_k ≥ top_k):
- ChromaDB trả về `retrieve_k` ứng viên để tính Hit@K chính xác trong evaluation
  (recall window rộng hơn cửa sổ ngữ cảnh generator).
- Chỉ `top_k` chunk đứng đầu (theo cosine similarity) được đưa vào generator —
  giữ nguyên chất lượng câu trả lời, không mở rộng context window không cần thiết.
- `sources` trả về TOÀN BỘ retrieve_k chunk để evaluation đo Hit@retrieve_k,
  `gen_docs` chỉ là top_k đầu để generator dùng.

`run()` trả về dict gồm cả metadata nguồn (tier, tên văn bản, chunk_id) để tầng
CLI in danh sách trích dẫn và để đánh giá Recall@K theo từng tầng.
"""

from typing import Any

from src.text_utils import fold

# Hệ số oversampling mặc định: ChromaDB lấy nhiều hơn top_k một chút để
# tăng recall window mà không làm generator nhận quá nhiều ngữ cảnh nhiễu.
# Giá trị 2 có nghĩa: top_k=4 → retrieve 8 chunk; top_k=6 → retrieve 12 chunk.
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
    """Điều phối toàn bộ luồng Hybrid RAG."""

    def __init__(self, vector_db: Any, local_slm: Any, generator: Any,
                 oversample_factor: int = DEFAULT_OVERSAMPLE_FACTOR):
        self.vector_db = vector_db
        self.local_slm = local_slm
        self.generator = generator
        # oversample_factor: số lần nhân top_k khi lấy ứng viên từ ChromaDB.
        # Đặt 1 để tắt oversampling (retrieve_k = top_k, hành vi cũ).
        self.oversample_factor = max(1, int(oversample_factor))

    def run(self, question: str, top_k: int = 4) -> dict:
        """Xử lý một câu hỏi với chiến lược oversampling.

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
        retrieve_k = top_k * self.oversample_factor

        normalized_query = self.local_slm.normalize_query(raw_query)
        retrieval_query = fold(normalized_query)

        # ChromaDB trả retrieve_k chunk, xếp theo cosine similarity giảm dần.
        all_docs = self.vector_db.similarity_search(retrieval_query, k=retrieve_k)

        # Generator chỉ nhận top_k đầu — recall window rộng hơn mà context không phình.
        gen_docs = all_docs[:top_k]
        contexts = [doc.page_content for doc in gen_docs]

        # sources chứa TOÀN BỘ retrieve_k để evaluation đo Hit@retrieve_k.
        sources = [describe_document(doc, i) for i, doc in enumerate(all_docs)]

        answer = self.generator.generate_answer(query=normalized_query, retrieved_docs=gen_docs)

        return {
            "raw_query": raw_query,
            "normalized_query": normalized_query,
            "retrieval_query": retrieval_query,
            "contexts": contexts,
            "sources": sources,
            "answer": answer,
        }

