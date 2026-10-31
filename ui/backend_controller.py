"""Khởi tạo backend cho GUI (REVIEW §7) — chạy được mà không cần Tkinter.

Controller chỉ trả dữ liệu/raises; mọi cập nhật widget do `ui/app.py` bọc qua `after()`.
Việc chọn generator (Qwen offline hay Gemini) do GUI truyền vào để giữ nguyên điểm test
`ui.app.build_generator` / `ui.app.use_qwen_generator`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.core.pipeline import HybridRAGPipeline
from src.generation.local_slm import LocalSLM
from src.generator import GeminiGenerator, QwenGenerator
from src.retrieval.vector_db import VectorStoreManager


@dataclass
class BackendBundle:
    db_manager: VectorStoreManager
    vector_db: Any
    local_slm: LocalSLM
    generator: Any
    pipeline: HybridRAGPipeline
    slm_ok: bool
    chunk_count: int


def build_backend(
    status: Optional[Callable[[str], None]] = None,
    *,
    use_qwen: bool = False,
    generator_factory: Optional[Callable[[bool], Any]] = None,
) -> BackendBundle:
    """Dựng toàn bộ backend. Ném lỗi thật lên caller — không trả "backend rỗng"."""
    report = status or (lambda _msg: None)
    factory = generator_factory or (QwenGenerator if use_qwen else GeminiGenerator)

    report("Đang kết nối ChromaDB...")
    db_manager = VectorStoreManager()
    vector_db = db_manager.load_vector_store()

    report("Kiểm tra Local SLM (Ollama)...")
    local_slm = LocalSLM()
    slm_ok, _msg = local_slm.check_connection()

    report("Kết nối Local Qwen (chế độ OFFLINE)..." if use_qwen else "Kết nối Gemini API...")
    generator = factory(use_qwen)

    pipeline = HybridRAGPipeline(vector_db=vector_db, local_slm=local_slm, generator=generator)
    return BackendBundle(
        db_manager=db_manager,
        vector_db=vector_db,
        local_slm=local_slm,
        generator=generator,
        pipeline=pipeline,
        slm_ok=slm_ok,
        chunk_count=vector_db._collection.count(),
    )
