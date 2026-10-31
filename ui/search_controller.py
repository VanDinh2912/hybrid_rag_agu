"""Chạy truy vấn/search ngoài luồng giao diện (REVIEW §7)."""

from __future__ import annotations

import time
from typing import Any, Tuple


def execute_search(pipeline: Any, query: str, top_k: int) -> Tuple[dict, float]:
    """Chạy `pipeline.run` và trả `(result, giây)`. Lỗi nổi lên caller để báo đúng."""
    started = time.perf_counter()
    result = pipeline.run(query, top_k=top_k)
    return result, time.perf_counter() - started
