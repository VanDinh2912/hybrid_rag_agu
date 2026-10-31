"""Đường dẫn chuẩn neo theo gốc dự án (REVIEW §4, 31-10).

Trước đây một số module dùng `Path("data/...")`, `Path("outputs/...")`,
`Path("logs/...")` nên kết quả phụ thuộc thư mục làm việc: chạy từ root repo,
từ IDE, hay từ thư mục khác cho ba vị trí khác nhau. Module này là nguồn duy nhất:

1. `PROJECT_ROOT` suy từ vị trí file (`src/core/paths.py` → lên hai cấp), không
   phụ thuộc `Path.cwd()`.
2. Mỗi thư mục có hằng số tuyệt đối. Đường dẫn tương đối trong biến môi trường
   được hiểu **theo gốc dự án** (không theo CWD) để chạy ở đâu cũng như nhau.
3. Override qua `.env` giữ đúng tên cũ ở nơi đã có (`CHROMA_PERSIST_DIR`) và
   thêm tên mới cho các thư mục chưa có (`RAG_*_DIR`). Biến rỗng = dùng mặc định.

Không đọc cờ bật/tắt ở đây; đây chỉ là đường dẫn. `src/core/config.py` vẫn là nơi
đọc cờ của 9 module đã chuyển.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Gốc repository: `…/hybrid_rag_agu/src/core/paths.py` → lên `src/core` → `src` → gốc.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(raw: str, default: Path) -> Path:
    """Chuẩn hóa một giá trị đường dẫn: rỗng → mặc định; tương đối → theo gốc dự án."""
    value = (raw or "").strip()
    if not value:
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path)


def _dir(env_name: str, default: Path) -> Path:
    return _resolve(os.getenv(env_name, ""), default)


DATA_DIR = _dir("RAG_DATA_DIR", PROJECT_ROOT / "data")
CORPUS_DIR = _dir("RAG_CORPUS_DIR", DATA_DIR / "corpus")
EVALUATION_DIR = _dir("RAG_EVALUATION_DIR", DATA_DIR / "evaluation")
LEARNING_DIR = DATA_DIR / "learning"
TRAINING_DIR = DATA_DIR / "training"

LOGS_DIR = _dir("RAG_LOGS_DIR", PROJECT_ROOT / "logs")
OUTPUTS_DIR = _dir("RAG_OUTPUTS_DIR", PROJECT_ROOT / "outputs")
CACHE_DIR = _dir("RAG_CACHE_DIR", PROJECT_ROOT / ".cache")
CHROMA_DIR = _dir("CHROMA_PERSIST_DIR", PROJECT_ROOT / "chroma_db")

#: Thư mục con hay dùng — dẫn xuất để không ai tự nối chuỗi sai gốc.
FEEDBACK_DIR = LOGS_DIR / "feedback"
OCR_CACHE_DIR = CACHE_DIR / "ocr" / "rapidocr"
