"""Ghi JSON nguyên tử + khoá file, dùng cho feedback/benchmark của GUI (REVIEW §13).

Vì sao cần
----------
Ghi trực tiếp `open(path, "w")` rồi `json.dump` có hai lỗi: chương trình dừng giữa chừng
để lại file cụt, và hai thao tác đồng thời đọc–sửa–ghi sẽ ghi đè nhau. Module này gói
đúng ba bước: khoá file → đọc bản hiện tại → ghi file tạm cùng thư mục → `os.replace`.

Không phải cơ sở dữ liệu: chỉ dùng cho file JSON nhỏ do GUI/CLI ghi tuần tự. Runner đo
và artifact công bố KHÔNG đi qua đây — chúng có quy trình đóng băng riêng.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from filelock import FileLock


class JsonStoreError(RuntimeError):
    """Đọc/ghi JSON thất bại — caller phải báo lỗi, không được coi là thành công."""


@contextmanager
def _locked(path: Path, timeout: float = 10.0):
    """Khoá cạnh file đích (`<tên>.lock`), tự tạo thư mục cha."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise JsonStoreError(f"không tạo được thư mục cho {path}: {exc}") from exc
    lock = FileLock(str(path) + ".lock", timeout=timeout)
    with lock:
        yield


def read_json(path: Path, default: Any) -> Any:
    """Đọc JSON; file chưa có ⇒ `default`. File hỏng ⇒ `JsonStoreError` (không nuốt)."""
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise JsonStoreError(f"không đọc được {path}: {exc}") from exc


def write_atomic(path: Path, data: Any, *, validate: Optional[Callable[[Any], None]] = None) -> None:
    """Ghi `data` ra `path` nguyên tử: file tạm cùng thư mục → fsync → `os.replace`."""
    if validate is not None:
        validate(data)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise JsonStoreError(f"không tạo được thư mục cho {path}: {exc}") from exc
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp",
            delete=False, newline="\n",
        ) as fh:
            tmp_name = fh.name
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except OSError as exc:
        raise JsonStoreError(f"không ghi được {path}: {exc}") from exc
    finally:
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def update_json(
    path: Path,
    default: Any,
    mutator: Callable[[Any], Any],
    *,
    validate: Optional[Callable[[Any], None]] = None,
) -> Any:
    """Đọc–sửa–ghi dưới một khoá file; trả dữ liệu mới.

    `mutator` nhận bản đọc được và trả bản sẽ ghi. Ném `JsonStoreError` khi đọc/ghi hỏng
    để caller phân biệt với "đã lưu thành công".
    """
    with _locked(path):
        current = read_json(path, default)
        updated = mutator(current)
        write_atomic(path, updated, validate=validate)
        return updated


def now_iso() -> str:
    """Dấu thời gian thống nhất cho mọi bản ghi (giây, giờ máy)."""
    return datetime.now().isoformat(timespec="seconds")


def validate_feedback_list(data: Any) -> None:
    """Schema tối thiểu của `logs/feedback/user_feedback.json`.

    Bản ghi cũ (trước REVIEW §13) không có `schema_version` vẫn đọc/ghi được; bản ghi
    MỚI do GUI sinh luôn đủ 5 trường chuẩn. Chỉ từ chối cấu trúc hỏng thật sự.
    """
    if not isinstance(data, list):
        raise JsonStoreError("feedback phải là danh sách bản ghi")
    for index, record in enumerate(data):
        if not isinstance(record, dict):
            raise JsonStoreError(f"bản ghi feedback #{index} không phải object")
        if "raw_query" not in record:
            raise JsonStoreError(f"bản ghi feedback #{index} thiếu `raw_query`")
        if "feedback_type" not in record and "feedback" not in record:
            raise JsonStoreError(f"bản ghi feedback #{index} thiếu loại đánh giá")


def validate_benchmark_doc(data: Any) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise JsonStoreError("benchmark phải là object có mảng `questions`")
    ids = [q.get("id") for q in data["questions"] if isinstance(q, dict)]
    if len(ids) != len(data["questions"]):
        raise JsonStoreError("mọi câu benchmark phải là object")
    if len(set(ids)) != len(ids):
        raise JsonStoreError(f"id benchmark trùng: {len(ids) - len(set(ids))} bản ghi")


def validate_pairs_doc(data: Any) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("pairs"), list):
        raise JsonStoreError("normalization_pairs phải là object có mảng `pairs`")


def iter_records(path: Path, key: str = "pairs") -> Iterable[dict]:
    """Đọc danh sách bản ghi từ file cấu trúc `{key: [...]}` (dùng cho thống kê đọc-only)."""
    data = read_json(path, {})
    records = data.get(key, []) if isinstance(data, dict) else []
    return [r for r in records if isinstance(r, dict)]
