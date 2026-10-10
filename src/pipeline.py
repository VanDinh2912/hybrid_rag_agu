"""Module gộp luồng Hybrid RAG (Local SLM phối hợp Gemini API).

Luồng xử lý:
1. Nhận câu hỏi thô của sinh viên.
2. Local SLM (Qwen/Ollama) chuẩn hóa câu hỏi thành văn phong học vụ.
3. Truy vấn VectorDB (bge-m3 + ChromaDB) lấy top-k chunk ngữ cảnh.
4. Gemini API sinh câu trả lời cuối cùng dựa trên ngữ cảnh đã truy xuất.

`run()` trả về dict gồm cả metadata nguồn (tier, tên văn bản, chunk_id) để tầng
CLI in danh sách trích dẫn và để đánh giá Recall@K theo từng tầng.
"""

from typing import Any


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

    def __init__(self, vector_db: Any, local_slm: Any, generator: Any):
        self.vector_db = vector_db
        self.local_slm = local_slm
        self.generator = generator

    def run(self, question: str, top_k: int = 5) -> dict:
        """Xử lý một câu hỏi.

        Trả về: raw_query, normalized_query, contexts (nội dung chunk),
        sources (metadata từng chunk), answer.
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Câu hỏi phải là chuỗi không rỗng.")
        raw_query = question.strip()
        top_k = max(1, int(top_k))

        normalized_query = self.local_slm.normalize_query(raw_query)

        docs = self.vector_db.similarity_search(normalized_query, k=top_k)
        contexts = [doc.page_content for doc in docs]
        sources = [describe_document(doc, i) for i, doc in enumerate(docs)]

        answer = self.generator.generate_answer(query=normalized_query, retrieved_docs=docs)

        return {
            "raw_query": raw_query,
            "normalized_query": normalized_query,
            "contexts": contexts,
            "sources": sources,
            "answer": answer,
        }
