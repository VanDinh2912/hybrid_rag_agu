"""Chạy ingest ngoài luồng giao diện (REVIEW §7) — không đụng widget, không đổi stdout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ingest import run_ingestion


@dataclass
class IngestOutcome:
    db_manager: Any
    vector_db: Any
    total: int


class IngestRetrieverError(RuntimeError):
    """Đã nạp xong dữ liệu nhưng chưa làm mới được bộ truy xuất.

    Mang theo `outcome` để GUI vẫn cập nhật `db_manager` và báo đúng "đã nạp N chunks
    nhưng retriever chưa theo corpus mới" thay vì báo thành công (REVIEW §2.1).
    """

    def __init__(self, outcome: IngestOutcome, cause: Exception):
        super().__init__(str(cause))
        self.outcome = outcome
        self.cause = cause


def execute_ingest(
    pipeline: Any,
    db_manager: Any,
    reuse_model: bool,
    log: Callable[[str], None],
) -> IngestOutcome:
    """Nạp corpus rồi làm mới bộ truy xuất.

    `log` nhận từng dòng của `run_ingestion` (mặc định là `print` cho CLI). GUI truyền
    callback đẩy vào queue — không thay `sys.stdout` toàn cục.
    """
    target_manager = db_manager if (reuse_model and db_manager) else None
    reset_mode = not reuse_model  # reset=False khi tái sử dụng để tránh khoá file ChromaDB
    new_manager, new_vector_db, total = run_ingestion(
        db_manager=target_manager, reset=reset_mode, log=log
    )
    outcome = IngestOutcome(db_manager=new_manager, vector_db=new_vector_db, total=total)
    if pipeline is not None:
        try:
            # Phải dựng lại CẢ bộ truy xuất: BM25 giữ danh sách document cũ nếu chỉ gán
            # vector_db (REVIEW §2.1).
            pipeline.replace_vector_db(new_vector_db)
        except Exception as exc:
            raise IngestRetrieverError(outcome, exc) from exc
    return outcome
