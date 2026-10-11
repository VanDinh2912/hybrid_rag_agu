"""Tiện ích xử lý văn bản dùng chung toàn pipeline (không import module nội bộ khác).

Nhiều tầng của hệ thống cần so khớp không phân biệt dấu thanh: văn bản OCR ở
Tầng 1 mất dấu, còn câu hỏi/câu trả lời của người dùng và tài liệu Tầng 2 vẫn
giữ dấu. fold() là điểm chuẩn hóa duy nhất cho mọi tầng — mỗi tầng tự chịu
trách nhiệm gọi nó trước khi so sánh hoặc embed.
"""

import re
import unicodedata


def fold(text: str) -> str:
    """Bỏ dấu thanh + chữ thường + gom khoảng trắng, để so khớp không phân biệt dấu.

    Cần thiết vì văn bản OCR ở Tầng 1 mất dấu thanh: "Điều 12" và "dieu 12" phải
    được coi là cùng một trích dẫn. Lưu ý: "Đ" (U+0110) là chữ cái độc lập, NFD
    KHÔNG tách thành "d" + dấu — phải tự thay "đ"→"d", nếu không regex "dieu"
    sẽ bỏ sót mọi trích dẫn.
    """
    decomposed = unicodedata.normalize("NFD", str(text).lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.replace("đ", "d")).strip()
