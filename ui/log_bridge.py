"""Cầu nối log giữa worker thread và GUI (REVIEW §8).

Worker KHÔNG ghi thẳng vào widget Tkinter và KHÔNG đổi `sys.stdout` toàn cục: nó đẩy bản
ghi vào `queue.Queue`; luồng giao diện đọc queue bằng `after()` rồi mới chèn vào widget.
Cách này giữ log của mọi thread và không nuốt log của thread khác trong lúc ingest.
"""

from __future__ import annotations

import logging
import queue
from typing import List, Tuple


class QueueLogHandler(logging.Handler):
    """Handler đẩy bản ghi đã format vào queue; thread nào đọc queue sẽ tự hiển thị."""

    def __init__(self, sink: "queue.Queue[str]"):
        super().__init__()
        self.sink = sink
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - gọi từ logging
        try:
            self.sink.put_nowait(self.format(record) + "\n")
        except Exception:
            self.handleError(record)


def attach_queue_logger(
    logger_name: str = "rag.gui", level: int = logging.INFO
) -> Tuple["queue.Queue[str]", QueueLogHandler]:
    """Gắn handler vào một logger RIÊNG (không đụng root/console của CLI)."""
    sink: "queue.Queue[str]" = queue.Queue()
    handler = QueueLogHandler(sink)
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return sink, handler


def drain(sink: "queue.Queue[str]", limit: int = 500) -> List[str]:
    """Lấy tối đa `limit` dòng đang chờ; không chặn nếu queue rỗng."""
    lines: List[str] = []
    for _ in range(limit):
        try:
            lines.append(sink.get_nowait())
        except queue.Empty:
            break
    return lines
