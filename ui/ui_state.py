"""Trạng thái giao diện + hàm định dạng thuần, tách khỏi `ui/app.py` (REVIEW §7).

`AppState` giữ đúng những gì cần nhớ giữa các tab; widget Tkinter KHÔNG nằm ở đây để
logic này test được mà không dựng cửa sổ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


def format_labels_display(labels, retrieval_config) -> str:
    """Dòng nhãn hiển thị ở Tab 1 (P3.5) — THUẦN HIỂN THỊ, không đụng logic hỏi đáp.

    - labels None/rỗng (ENABLE_CLASSIFIER=0 hoặc suy giảm mềm) → "—".
    - Có nhãn → gộp 1 dòng: chủ đề · loại câu hỏi · top_k · trọng số · lọc nguồn.
    """
    if not labels:
        return "—"
    cfg = retrieval_config or {}
    parts = [
        f"chủ đề: {labels.get('topic', '—')}",
        f"loại: {labels.get('question_type', '—')}",
        f"top_k={cfg.get('top_k', '—')}",
        f"bm25={cfg.get('bm25_weight', '—')}/chroma={cfg.get('chroma_weight', '—')}",
    ]
    src_filter = cfg.get("source_filter") or []
    if src_filter:
        parts.append("lọc nguồn: " + ", ".join(src_filter))
    return " | ".join(parts)


@dataclass
class AppState:
    """Trạng thái backend + cờ bận. Mọi thay đổi diễn ra trên luồng giao diện."""

    db_manager: Any = None
    local_slm: Any = None
    generator: Any = None
    pipeline: Any = None

    is_searching: bool = False
    is_ingesting: bool = False
    is_testing: bool = False

    current_test_data: Optional[dict] = field(default=None)

    def busy(self) -> bool:
        return self.is_searching or self.is_ingesting or self.is_testing
