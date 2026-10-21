"""Module sinh câu trả lời bằng Gemini API (backend trên mây của Hybrid RAG).

Trách nhiệm:
- Khởi tạo Google Generative AI client từ API key trong biến môi trường.
- `generate_answer(query, retrieved_docs, question_type=None)`: nhận câu hỏi đã
  chuẩn hóa cùng danh sách chunk truy xuất được từ ChromaDB (nội dung + tên văn
  bản + tier), dựng prompt nghiêm ngặt và trả về câu trả lời có trích dẫn
  Điều/Khoản. `question_type` (P3.4) chọn biến thể định dạng: SO_SANH → bảng so
  sánh, THU_TUC → bước đánh số, NGOAI_PHAM_VI → thêm dòng từ chối chuẩn; None →
  prompt gốc không đổi một ký tự (cache cũ vẫn trúng).

Chống ảo giác (anti-hallucination): prompt cấm dùng kiến thức ngoài ngữ cảnh,
bắt buộc nêu căn cứ pháp lý cho từng ý, và khi không đủ căn cứ thì phải từ chối
lịch sự bằng đúng câu `REFUSAL_TEXT`. Nếu ngữ cảnh rỗng, module trả về
`REFUSAL_TEXT` ngay mà không gọi API (không có gì để bám thì không được đoán).

Tiết kiệm quota & chống sập khi demo:
- Response caching: key là SHA-1 của {model, temperature, prompt}; trúng cache
  trong `./.generation_cache/` thì trả lời ngay không gọi API. Chỉ cache câu
  trả lời nguồn Gemini — câu fallback Qwen KHÔNG cache để lượt chạy sau còn
  được thử lại Gemini thật, tránh "đóng băng" câu trả lời tạm vĩnh viễn.
- Fallback Local Qwen: Gemini hết quota (429/ResourceExhausted) hoặc gặp sự cố
  → tổng hợp câu trả lời thay thế bằng Qwen trên Ollama kèm nhãn cảnh báo rõ
  ràng. Nếu Ollama cũng chết, ném GeneratorError (main.py/evaluation.py đã bắt
  ngoại lệ này — chương trình không bao giờ chết vì hết quota).
"""

import hashlib
import json
import os
import re
import time
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import google.generativeai as genai
import ollama

from src.text_utils import fold

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TEMPERATURE = 0.0
# gemini-2.5-flash là model "thinking": số token suy luận nội bộ bị trừ VÀO CÙNG
# ngân sách max_output_tokens (đo thực tế: 763 token thinking + 73 token trả lời
# đã chạm trần 1024 và làm câu trả lời bị cắt giữa chừng). Để đủ chỗ cho cả hai.
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_MAX_RETRIES = 2

REFUSAL_TEXT = "Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."
REFUSAL_MARKER = "không đủ thông tin"

# Phiên bản prompt: đưa vào cache key để mọi thay đổi SYSTEM_INSTRUCTION/PROMPT_RULES
# (nằm NGOÀI chuỗi prompt truyền vào) đều tự làm cache cũ vô hiệu — bump khi sửa prompt.
PROMPT_VERSION = "v1.3"  # P3.4b: cache vẫn lưu text CHƯA inject; inject thành hậu xử lý dùng chung HIT/MISS — entry cũ vẫn hợp lệ, KHÔNG bump.

# --- Response caching: lưu câu trả lời đã sinh vào ./.generation_cache/ ---
# Key là SHA-1 của {model, temperature, prompt_version, prompt} nên corpus re-ingest,
# sửa prompt hay sửa system instruction đều tự làm cache cũ vô hiệu (self-invalidating),
# không cần dọn tay.
GENERATION_CACHE_DIR = "./.generation_cache"

# --- Fallback Local Qwen: tầng dự phòng khi Gemini lỗi quota / sự cố ---
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:1.5b-instruct"
DEFAULT_OLLAMA_TIMEOUT = 90.0

# Dấu hiệu lỗi hết quota (429 / ResourceExhausted) — dùng để chọn nhãn cảnh báo.
QUOTA_MARKERS = ("429", "resource_exhausted", "resource exhausted", "too many requests", "quota")

# Bước 0 P4.2 (mục 1): 429 theo PHÚT là lỗi tạm thời — chờ 60s rồi thử lại ĐÚNG câu đó,
# tối đa 3 lần, KHÔNG đánh dấu câu là error (đánh mất câu khỏi A/B). Riêng 429 PerDay
# (hết quota ngày) thì không chờ — tầng evaluation nhận marker để dừng cả lượt, giữ phần đã chạy.
MINUTE_429_WAIT_SECONDS = 60
MINUTE_429_MAX_RETRIES = 3


def quota_error_kind(message: str) -> Optional[str]:
    """Phân loại lỗi quota từ thông báo API: 'perday' | 'minute' | None.

    Ưu tiên nhận diện PerDay TRƯỚC (thông điệp Gemini chứa 'PerDay'/'per day' trong
    chi tiết vi hạn mức), còn lại mọi 429/quota/perminute coi như giới hạn theo phút.
    """
    m = str(message).lower()
    if "perday" in m or "per day" in m:
        return "perday"
    if "perminute" in m or "per minute" in m or any(marker in m for marker in QUOTA_MARKERS):
        return "minute"
    return None

FALLBACK_NOTICE_PREFIX = "[Cảnh báo:"
QWEN_FALLBACK_NOTICE = (
    "[Cảnh báo: {reason} — câu trả lời này được tổng hợp tạm thời bằng Local Qwen ({model}) "
    "để phục vụ demo. Hãy đối chiếu với văn bản gốc trước khi sử dụng.]"
)

# Pattern phát hiện trích dẫn chuẩn đã có trong câu trả lời
# Khớp nhiều dạng: (Điều X), (dieu X), (Điều X, Khoản Y), (tên file.pdf)
CITATION_PATTERN = re.compile(r"\(?(Điều|dieu|Khoản|khoan|pdf|\.pdf)", re.IGNORECASE)

# Ollama mặc định num_ctx=2048 — ngữ cảnh 4-5 chunk sẽ bị CẮT IM LẶNG nếu không
# nâng lên. Qwen2.5-1.5B cũng dễ "quên" chỉ dẫn khi prompt quá dài nên phải cắt
# cứng khối ngữ cảnh đưa vào fallback prompt.
QWEN_FALLBACK_NUM_CTX = 8192
QWEN_FALLBACK_NUM_PREDICT = 512
QWEN_FALLBACK_TEMPERATURE = 0.1
QWEN_MAX_BLOCK_CHARS = 1600
QWEN_MAX_TOTAL_CHARS = 10000

SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý học vụ của Trường Đại học An Giang (AGU), trả lời câu hỏi của sinh viên "
    "về quy chế, quy định đào tạo. Bạn chỉ được phép suy luận từ các đoạn ngữ cảnh do hệ "
    "thống truy xuất cung cấp, tuyệt đối không dùng kiến thức nền bên ngoài và không bịa "
    "số hiệu điều khoản, mốc thời gian hay tên văn bản.\n\n"
    # --- NEGATIVE CONSTRAINTS (ràng buộc tiêu cực — KHÔNG ĐƯỢC VI PHẠM) ---
    "RÀNG BUỘC TIÊU CỰC — VI PHẠM BẤT KỲ ĐIỀU NÀO SAU ĐÂY LÀ SAI HOÀN TOÀN:\n"
    "• TUYỆT ĐỐI KHÔNG tự suy diễn, ước đoán hay nội suy thông tin ngoài ngữ cảnh được cung cấp, "
    "dù bạn có thể biết đáp án từ dữ liệu huấn luyện.\n"
    "• TUYỆT ĐỐI KHÔNG bịa đặt hoặc 'hoàn chỉnh' số Điều, số Khoản, tên văn bản, con số hay "
    "mốc thời gian khi chúng không xuất hiện rõ ràng trong ngữ cảnh.\n"
    "• TUYỆT ĐỐI KHÔNG trả lời câu hỏi khi ngữ cảnh được cung cấp hoàn toàn không chứa thông tin "
    "liên quan. Trong trường hợp đó, bạn BẮT BUỘC phải từ chối bằng đúng câu được quy định — "
    "không được thêm, bớt hay paraphrase câu từ chối đó.\n"
    "• TUYỆT ĐỐI KHÔNG dùng cụm từ mơ hồ như 'thông thường', 'thường thì', 'có thể là', "
    "'theo quy định chung', 'theo thông lệ' khi không có căn cứ trong ngữ cảnh.\n"
    "• TUYỆT ĐỐI KHÔNG giả định ngữ cảnh thiếu thông tin là do truy xuất sai — "
    "hãy từ chối lịch sự thay vì cố 'giúp đỡ' bằng kiến thức ngoài corpus."
)

PROMPT_RULES = """QUY TẮC BẮT BUỘC:
1. Chỉ dùng thông tin có trong NGỮ CẢNH ở trên. Không suy diễn, không bổ sung kiến thức ngoài ngữ cảnh.
2. Mỗi ý trả lời PHẢI kèm căn cứ pháp lý ngay trong câu, theo mẫu BẮT BUỘC: (Điều [X], Khoản [Y] — [Tên_file_nguồn.pdf]).
   - Nếu ngữ cảnh có đánh số Điều/Khoản: ghi đầy đủ (Điều 14, Khoản 5 — 1059-qd-dhag-2020-09-29.pdf)
   - Nếu ngữ cảnh không đánh số Điều/Khoản: bắt buộc ghi tên file nguồn (1059-qd-dhag-2020-09-29.pdf)
   - Luôn dùng TÊN FILE NGUỒN THẬT được ghi ở dòng "Nguồn:"; không viết "(Ngữ cảnh 1)", "(1)", "theo tài liệu".
   - Định dạng trích dẫn phải xuất hiện ở CUỐI câu trả lời hoặc ngay sau ý tương ứng.
3. Nếu NGỮ CẢNH không đủ căn cứ để trả lời (kể cả khi bạn biết đáp án ngoài đời), trả lời đúng một câu:
   "{refusal}" — sau đó nêu ngắn gọn thông tin còn thiếu. KHÔNG được đoán.
4. Ưu tiên ngữ cảnh có tier cao hơn (Tầng 1 là văn bản quy chế gốc) khi các nguồn mâu thuẫn,
   và nói rõ sự mâu thuẫn đó nếu có.
5. Trả lời bằng tiếng Việt, ngắn gọn (tối đa ~200 từ), dùng gạch đầu dòng khi có nhiều ý,
   có thể trích nguyên văn cụm từ quan trọng trong ngoặc kép.
6. Không lặp lại các quy tắc này, không kể chuyện hệ thống hoạt động ra sao.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VÍ DỤ MẪU (FEW-SHOT) — TUÂN THEO ĐÚNG CÁC MẪU NÀY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[VÍ DỤ 1 — Ngữ cảnh rỗng / không truy xuất được chunk nào]
Ngữ cảnh: (không có đoạn nào được cung cấp)
Câu hỏi: Sinh viên cần đạt GPA bao nhiêu để tốt nghiệp?
✅ TRẢ LỜI ĐÚNG:
"{refusal}" Ngữ cảnh được cung cấp không chứa thông tin về điều kiện GPA tốt nghiệp.

❌ TRẢ LỜI SAI (tuyệt đối không làm như này):
"Theo quy định chung, sinh viên cần đạt GPA tối thiểu 2.0/4.0 để tốt nghiệp." (← suy diễn ngoài ngữ cảnh)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[VÍ DỤ 2 — Câu hỏi ngoài phạm vi corpus, ngữ cảnh không liên quan]
Ngữ cảnh: [Ngữ cảnh 1] Nguồn: Quy chế đào tạo AGU | Tầng: 1
  "Sinh viên vắng quá 30% số tiết học của một học phần sẽ bị cấm thi."
Câu hỏi: Học phí học kỳ II năm học 2024-2025 của ngành Kỹ thuật phần mềm là bao nhiêu?
✅ TRẢ LỜI ĐÚNG:
"{refusal}" Ngữ cảnh được cung cấp chỉ đề cập đến quy định vắng mặt, không chứa thông tin về mức học phí ngành Kỹ thuật phần mềm.

❌ TRẢ LỜI SAI (tuyệt đối không làm như này):
"Học phí ngành Kỹ thuật phần mềm thường dao động khoảng 15-20 triệu/học kỳ." (← bịa đặt hoàn toàn)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[VÍ DỤ 3 — Ngữ cảnh có liên quan, trả lời đúng với trích dẫn đầy đủ]
Ngữ cảnh: [Ngữ cảnh 1] Nguồn: Quy chế đào tạo AGU 2023 | Tầng: 1
  "Điều 15, Khoản 2: Sinh viên được phép đăng ký học lại tối đa 2 lần cho mỗi học phần không đạt."
Câu hỏi: Sinh viên được học lại bao nhiêu lần nếu rớt môn?
✅ TRẢ LỜI ĐÚNG:
Sinh viên được phép đăng ký học lại tối đa **2 lần** cho mỗi học phần không đạt. (Điều 15, Khoản 2 — Quy chế đào tạo AGU 2023)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[VÍ DỤ 4 — Ngữ cảnh không đánh số Điều/Khoản, chỉ trích dẫn tên file]
Ngữ cảnh: [Ngữ cảnh 1] Nguồn: 1059-qd-dhag-2020-09-29.pdf | Tầng: 1
  "Sinh viên phải hoàn thành học phí trước ngày 15 của tháng đầu tiên mỗi học kỳ."
Câu hỏi: Sinh viên cần đóng học phí trước khi nào?
✅ TRẢ LỜI ĐÚNG:
Sinh viên phải hoàn thành học phí trước ngày 15 của tháng đầu tiên mỗi học kỳ. (1059-qd-dhag-2020-09-29.pdf)

❌ TRẢ LỜI SAI (tuyệt đối không làm như này):
"Sinh viên phải đóng học phí trước ngày 15 tháng đầu." (← thiếu tên file nguồn)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

# --- Biến thể prompt theo question_type (P3.4) --------------------------------
# Thiết kế cache-an toàn: biến thể chỉ NỐI THÊM vào đuôi PROMPT_RULES gốc, còn
# đường question_type=None dùng nguyên PROMPT_RULES → prompt xuất ra GIỐNG HỆT
# TỪNG KÝ TỰ hành vi cũ, nên key cache cũ vẫn hợp lệ (không cần bump PROMPT_VERSION
# và không cần xóa .generation_cache/). Biến thể đổi NỘI DUNG prompt → SHA-1 tự
# khác → cache tự tách nhánh cho từng loại câu.
#
# NGOAI_PHAM_VI — KHÔNG skip truy xuất (skip-early là thí nghiệm tùy chọn ở P4,
# chỉ cân nhắc bật khi nhãn đủ tin cậy): nhãn sai mà skip là từ chối oan câu
# đúng. Ở đây chỉ chèn thêm 1 dòng nhắc từ chối chuẩn; Soft Refusal hiện có
# (từ chối khi ngữ cảnh rỗng/không liên quan) lo phần còn lại.

_SO_SANH_APPENDIX = """ĐỊNH DẠNG RIÊNG CHO CÂU SO SÁNH — câu hỏi này yêu cầu so sánh/tổng hợp nhiều điểm:
• Trình bày kết quả dưới dạng BẢNG so sánh: mỗi hàng là một TIÊU CHÍ, các cột là các vế cần so sánh.
• Mỗi Ô của bảng PHẢI có trích dẫn riêng theo mẫu (Điều [X], Khoản [Y] — [Tên_file_nguồn.pdf]),
  hoặc (Tên_file_nguồn.pdf) nếu ngữ cảnh không đánh số Điều/Khoản.
• Ghi rõ NGUỒN của từng vế: nếu các vế đến từ hai văn bản khác nhau thì phải nêu tên file của
  từng vế, tuyệt đối không trộn lẫn số liệu giữa các vế.
• Nếu ngữ cảnh chỉ đủ căn cứ cho một vế: trả lời vế đó và nêu rõ vế còn lại không có căn cứ,
  KHÔNG bịa thay."""

_THU_TUC_APPENDIX = """ĐỊNH DẠNG RIÊNG CHO CÂU THỦ TỤC — câu hỏi này yêu cầu quy trình/hồ sơ:
• Trình bày các BƯỚC ĐÁNH SỐ theo thứ tự thời gian (Bước 1, Bước 2, ...).
• Mỗi bước PHẢI kèm căn cứ ngay trong bước theo mẫu (Điều [X], Khoản [Y] — [Tên_file_nguồn.pdf]),
  hoặc (Tên_file_nguồn.pdf) nếu ngữ cảnh không đánh số Điều/Khoản.
• Nếu thủ tục có hồ sơ/giấy tờ kèm theo, liệt kê ngay sau các bước, mỗi loại một dòng có căn cứ.
• Bước nào ngữ cảnh không đủ căn cứ thì KHÔNG bịa — nêu rõ thiếu căn cứ cho bước đó."""

NGOAI_PHAM_VI_EXTRA_LINE = (
    "Nếu ngữ cảnh không chứa thông tin liên quan đến câu hỏi, trả lời đúng một câu từ chối chuẩn."
)

PROMPT_RULES_SO_SANH = PROMPT_RULES + "\n\n" + _SO_SANH_APPENDIX
PROMPT_RULES_THU_TUC = PROMPT_RULES + "\n\n" + _THU_TUC_APPENDIX
PROMPT_RULES_NGOAI_PHAM_VI = PROMPT_RULES + "\n\n" + NGOAI_PHAM_VI_EXTRA_LINE


def canonicalize_refusal(answer: str, question_type: Optional[str]) -> str:
    """P3.4 — câu NGOAI_PHAM_VI có cơ chế từ chối "chắc hơn" nhưng KHÔNG từ chối oan.

    Nếu model TỰ chọn từ chối (câu trả lời chứa dấu hiệu REFUSAL_MARKER, ví dụ
    kèm rác phía sau hay thêm câu giải thích) thì chuẩn hóa về ĐÚNG chuỗi
    REFUSAL_TEXT để tầng evaluation đối sánh chắc chắn theo hằng số. Model trả
    lời có căn cứ (không chứa marker) → giữ nguyên từng ký tự — nhãn sai thì
    câu trả lời đúng vẫn không bị mất. Áp cho cả Gemini lẫn Qwen; cache lưu
    dạng đã chuẩn hóa nên lượt sau trả lại đúng chuỗi.
    """
    if answer and question_type and fold(str(question_type)).strip().lower() == "ngoai_pham_vi":
        if REFUSAL_MARKER in answer:
            return REFUSAL_TEXT
    return answer


def is_canonical_refusal_answer(text: str, question_type: Optional[str]) -> bool:
    """P3.4b — text có phải câu từ chối chuẩn của NGOAI_PHAM_VI hay không.

    Dùng chung cho nhánh MISS (sau canonicalize_refusal) và nhánh HIT (text đọc
    từ cache) để quyết định có inject trích dẫn hay không: câu từ chối chuẩn
    giữ nguyên vẹn, không bị gắn trích dẫn vào cuối.
    """
    return (
        text == REFUSAL_TEXT
        and bool(question_type)
        and fold(str(question_type)).strip().lower() == "ngoai_pham_vi"
    )


def select_prompt_rules(question_type: Optional[str]) -> str:
    """Chọn khối quy tắc prompt theo question_type (P3.4).

    - None / TRA_CUU / nhãn lạ → PROMPT_RULES gốc (giữ nguyên hành vi cũ, cache cũ
      vẫn trúng vì prompt không đổi một ký tự).
    - SO_SANH → PROMPT_RULES_SO_SANH (bảng so sánh theo tiêu chí, mỗi ô có trích dẫn).
    - THU_TUC → PROMPT_RULES_THU_TUC (các bước đánh số, mỗi bước kèm căn cứ).
    - NGOAI_PHAM_VI → PROMPT_RULES + 1 dòng từ chối chuẩn (KHÔNG skip truy xuất —
      xem ghi chú thiết kế ở khối comment phía trên).
    So khớp nhãn sau khi fold (bỏ dấu) nên "so_sanh"/"SO_SANH"/"So_Sanh" như nhau.
    """
    if question_type:
        key = fold(str(question_type)).strip().lower()
        if key == "so_sanh":
            return PROMPT_RULES_SO_SANH
        if key == "thu_tuc":
            return PROMPT_RULES_THU_TUC
        if key == "ngoai_pham_vi":
            return PROMPT_RULES_NGOAI_PHAM_VI
    return PROMPT_RULES

# Lỗi nên thử lại: giới hạn tần suất (429) và lỗi phía server Google.
RETRYABLE_MARKERS = (
    "429",
    "resource_exhausted",
    "resource exhausted",
    "too many requests",
    "500",
    "503",
    "unavailable",
    "internal error",
    "deadline",
    "timeout",
    "timed out",
    "connection",
)


class GeneratorError(RuntimeError):
    """Lỗi khi gọi Gemini API (thiếu key, hết quota, bị chặn nội dung, phản hồi hỏng)."""


def is_quota_error(exc: Exception) -> bool:
    """Nhận diện lỗi hết quota (429/ResourceExhausted) để chọn nhãn cảnh báo phù hợp."""
    message = str(exc).lower()
    return any(marker in message for marker in QUOTA_MARKERS)


def is_fallback_answer(answer: Any) -> bool:
    """Nhận diện phản hồi do tầng fallback Local Qwen tổng hợp — để CLI gắn nhãn đúng nguồn sinh."""
    return isinstance(answer, str) and answer.lstrip().startswith(FALLBACK_NOTICE_PREFIX)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_flag(name: str, default: bool) -> bool:
    """Đọc cờ bật/tắt từ biến môi trường ("1"/"true"/"yes"/"on"); thiếu hoặc sai → default."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _pick(mapping: dict, keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


def normalize_docs(retrieved_docs: Any) -> list[dict]:
    """Quy đổi mọi dạng chunk về [{"content", "source", "tier", "chunk_id"}].

    Chấp nhận: LangChain `Document` (page_content + metadata), dict, hoặc chuỗi
    trần (khi người gọi chỉ có nội dung chunk).
    """
    if retrieved_docs is None:
        return []
    if isinstance(retrieved_docs, (str, bytes)):
        raise TypeError("retrieved_docs phải là danh sách chunk, không phải một chuỗi đơn lẻ.")
    if not isinstance(retrieved_docs, Iterable):
        raise TypeError(
            f"retrieved_docs phải là danh sách chunk, nhận được '{type(retrieved_docs).__name__}'."
        )
    if not isinstance(retrieved_docs, (list, tuple)):
        retrieved_docs = list(retrieved_docs)

    normalized: list[dict] = []
    for index, doc in enumerate(retrieved_docs):
        if isinstance(doc, str):
            content, source, tier, chunk_id = doc, "", "", index
        elif isinstance(doc, dict):
            content = _pick(doc, ("page_content", "content", "text", "chunk"))
            metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else doc
            source = _pick(metadata, ("source", "title", "file", "van_ban"), "")
            tier = _pick(metadata, ("tier", "tang", "category"), "")
            chunk_id = _pick(metadata, ("chunk_id", "id"), index)
        else:
            content = getattr(doc, "page_content", None)
            if content is None:
                raise TypeError(
                    f"Chunk thứ {index + 1} có kiểu '{type(doc).__name__}' không hỗ trợ — "
                    "chấp nhận Document, dict hoặc str."
                )
            metadata = getattr(doc, "metadata", None) or {}
            source = _pick(metadata, ("source", "title", "file", "van_ban"), "")
            tier = _pick(metadata, ("tier", "tang", "category"), "")
            chunk_id = _pick(metadata, ("chunk_id", "id"), index)

        content = str(content).strip()
        if not content:
            continue
        normalized.append(
            {
                "content": content,
                "source": str(source) or "không rõ nguồn",
                "tier": str(tier) or "Khác",
                "chunk_id": chunk_id,
            }
        )
    return normalized


def extract_citation_from_metadata(doc: dict) -> str:
    """Trích xuất thông tin trích dẫn từ metadata của một chunk.
    
    Tìm trong page_content và metadata để lấy thông tin Điều/Khoản nếu có.
    Nếu không tìm thấy, chỉ trả về tên file nguồn với ngoặc đơn.
    """
    import re
    
    content = doc.get("content", "")
    source = doc.get("source", "không rõ nguồn")
    
    # Nếu không có nội dung chunk, chỉ trả về tên file
    if not content or content.strip() == "":
        return f"({source})"
    
    # Tìm Điều trong nội dung chunk
    article_match = re.search(r"Điều\s+(\d+)", content)
    clause_match = re.search(r"Khoản\s+(\d+)", content)
    
    if article_match:
        article_num = article_match.group(1)
        if clause_match:
            clause_num = clause_match.group(1)
            return f"(Điều {article_num}, Khoản {clause_num} — {source})"
        else:
            return f"(Điều {article_num} — {source})"
    else:
        # Không tìm thấy Điều, chỉ trả về tên file với ngoặc đơn
        return f"({source})"


def inject_citations_from_metadata(answer: str, retrieved_chunks: list) -> str:
    """Tự động đính kèm trích dẫn từ metadata cho tất cả câu trả lời.
    
    Luôn trích xuất thông tin từ chunk có RRF score cao nhất (Top-1) và ghép
    chuỗi trích dẫn vào cuối câu trả lời để đảm bảo Citation F1 cao.
    
    Args:
        answer: Câu trả lời do Generator sinh ra
        retrieved_chunks: Danh sách chunk đã truy xuất (có metadata)
    
    Returns:
        Câu trả lời đã được đính kèm trích dẫn
    """
    if not retrieved_chunks:
        return answer  # Không có chunk nào để trích dẫn
    
    # Lấy chunk đầu tiên (có RRF score cao nhất)
    top_chunk = retrieved_chunks[0]
    
    # Chuẩn hóa chunk thành dict nếu cần
    if hasattr(top_chunk, "metadata"):
        doc = {
            "content": getattr(top_chunk, "page_content", ""),
            "source": top_chunk.metadata.get("source", "không rõ nguồn")
        }
    elif isinstance(top_chunk, dict):
        doc = {
            "content": top_chunk.get("page_content") or top_chunk.get("content", ""),
            "source": top_chunk.get("source", "không rõ nguồn")
        }
    else:
        return answer  # Không thể trích xuất thông tin
    
    # Trích xuất chuỗi trích dẫn
    citation = extract_citation_from_metadata(doc)
    
    # Ghép vào cuối câu trả lời
    if citation:
        # Xóa khoảng trắng thừa ở cuối câu trả lời
        answer = answer.rstrip()
        # Nếu câu trả lời không kết thúc bằng dấu câu, thêm dấu chấm
        if not answer.endswith(('.', '!', '?', ')', '"', "'")):
            answer += '.'
        return f"{answer} {citation}"
    
    return answer


def build_prompt(query: str, docs: list[dict], question_type: Optional[str] = None) -> str:
    """Dựng prompt grounded: mỗi chunk kèm số thứ tự, tên văn bản và tier.

    question_type (P3.4): None → khối quy tắc PROMPT_RULES gốc, prompt GIỐNG HỆT
    từng ký tự hành vi cũ (cache cũ còn dùng được); SO_SANH/THU_TUC/NGOAI_PHAM_VI
    → biến thể tương ứng (nội dung khác → cache tự tách key).
    """
    blocks = []
    for i, doc in enumerate(docs, start=1):
        blocks.append(
            f"[Ngữ cảnh {i}] Nguồn: {doc['source']} | Tầng: {doc['tier']} | chunk_id: {doc['chunk_id']}\n"
            f"{doc['content']}"
        )
    context_block = "\n\n".join(blocks)
    rules = select_prompt_rules(question_type)
    return (
        f"NGỮ CẢNH TRUY XUẤT TỪ VECTOR DB ({len(docs)} đoạn):\n{context_block}\n\n"
        f"CÂU HỎI CỦA SINH VIÊN: {query}\n\n"
        f"{rules.format(refusal=REFUSAL_TEXT)}\n\n"
        "TRẢ LỜI:"
    )


class GeminiGenerator:
    """Lớp sinh chữ sử dụng Gemini API."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        self.model_name = model_name or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise GeneratorError(
                "Thiếu GEMINI_API_KEY: hãy khai báo trong file .env "
                "(xem .env.example) hoặc truyền api_key trực tiếp."
            )
        if self.api_key.strip() in {"your_gemini_api_key_here", "<your_api_key>"}:
            raise GeneratorError("GEMINI_API_KEY vẫn là giá trị mẫu trong .env.example — hãy thay bằng key thật.")

        self.temperature = (
            temperature if temperature is not None else _env_float("GEMINI_TEMPERATURE", DEFAULT_TEMPERATURE)
        )
        self.max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else _env_int("GEMINI_MAX_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS)
        )
        self.max_retries = max(0, max_retries)

        # Cấu hình caching + fallback: dùng chung biến OLLAMA_* với src/local_slm.py
        # để không phải khai báo hai lần trong .env.
        self.use_cache = _env_flag("GENERATION_CACHE", True)
        self.qwen_fallback = _env_flag("QWEN_FALLBACK", True)
        self.cache_dir = Path(os.getenv("GENERATION_CACHE_DIR") or GENERATION_CACHE_DIR)
        self.ollama_host = os.getenv("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST
        self.ollama_model = os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        self.ollama_timeout = _env_float("OLLAMA_TIMEOUT", DEFAULT_OLLAMA_TIMEOUT)

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_INSTRUCTION,
            )
        except GeneratorError:
            raise
        except Exception as exc:
            raise GeneratorError(f"Không khởi tạo được Gemini model '{self.model_name}': {exc}") from exc

    def _warn_if_truncated(self, response: Any) -> None:
        """Cảnh báo khi câu trả lời bị cắt vì hết ngân sách token (kể cả token thinking)."""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return
        finish_reason = getattr(candidates[0], "finish_reason", None)
        name = str(getattr(finish_reason, "name", finish_reason))
        if "MAX_TOKENS" in name.upper():
            usage = getattr(response, "usage_metadata", None)
            total = getattr(usage, "total_token_count", None) if usage is not None else None
            print(
                f"[Gemini] Cảnh báo: câu trả lời bị CẮT vì chạm trần {self.max_output_tokens} token"
                f"{f' (đã dùng {total})' if total else ''}. "
                "Tăng GEMINI_MAX_TOKENS trong .env nếu thường xuyên gặp."
            )

    def _call_api(self, prompt: str, temperature: float) -> str:
        """Gọi Gemini kèm retry: lỗi tạm thời 2s/4s, 429 THEO PHÚT chờ 60s (tối đa 3 lần,
        không tính vào hạn retry thường vì là lỗi tạm thời riêng), 429 PerDay dừng ngay."""
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        last_error: Optional[Exception] = None
        attempt = 0        # đếm retry lỗi tạm thời thường (5xx, timeout...)
        minute_retries = 0  # đếm retry riêng cho 429 theo phút (Bước 0 P4.2)
        while attempt <= self.max_retries:
            try:
                response = self.model.generate_content(prompt, generation_config=generation_config)
            except Exception as exc:
                last_error = exc
                kind = quota_error_kind(str(exc))
                # Hết quota NGÀY thì chờ 60s hay 2s/4s đều vô ích — break ngay,
                # tầng đánh giá nhận marker "PerDay" để dừng sớm cả lượt, giữ phần đã chạy.
                if kind == "perday":
                    break
                if kind == "minute":
                    # Bước 0 P4.2: lỗi PHÚT là tạm thời — chờ 60s rồi thử lại ĐÚNG câu này,
                    # tối đa 3 lần, không đốt hạn retry thường và không đánh mất câu.
                    if minute_retries < MINUTE_429_MAX_RETRIES:
                        minute_retries += 1
                        print(f"[Gemini] 429 theo phút — chờ {MINUTE_429_WAIT_SECONDS}s rồi thử lại đúng câu này "
                              f"(lần {minute_retries}/{MINUTE_429_MAX_RETRIES}).")
                        time.sleep(MINUTE_429_WAIT_SECONDS)
                        continue
                    break
                message = str(exc).lower()
                retryable = any(marker in message for marker in RETRYABLE_MARKERS)
                if not retryable or attempt == self.max_retries:
                    break
                attempt += 1
                wait = 2 ** attempt
                print(f"[Gemini] Lỗi tạm thời ({type(exc).__name__}), thử lại sau {wait}s — lần {attempt}/{self.max_retries}.")
                time.sleep(wait)
                continue

            try:
                text = response.text
            except Exception as exc:
                feedback = getattr(response, "prompt_feedback", None)
                block_reason = getattr(feedback, "block_reason", None) if feedback is not None else None
                if block_reason:
                    raise GeneratorError(
                        f"Gemini chặn prompt vì lý do an toàn nội dung (block_reason={block_reason}). "
                        "Thử diễn đạt lại câu hỏi."
                    ) from exc
                raise GeneratorError(f"Gemini trả về phản hồi không đọc được ({type(exc).__name__}: {exc}).") from exc

            if not text or not text.strip():
                raise GeneratorError("Gemini trả về nội dung rỗng (có thể bị chặn bởi bộ lọc an toàn).")
            self._warn_if_truncated(response)
            return text.strip()

        reason = str(last_error) if last_error else "không rõ nguyên nhân"
        hint = ""
        if "api key not valid" in reason.lower() or "api_key" in reason.lower():
            hint = " Kiểm tra lại GEMINI_API_KEY trong .env."
        elif "404" in reason:
            hint = f" Model '{self.model_name}' có thể đã bị khai tử — đổi GEMINI_MODEL trong .env."
        elif any(marker in reason.lower() for marker in ("429", "resource_exhausted", "quota")):
            hint = " Đã hết quota Gemini — chờ reset hoặc dùng key khác."
        # Bước 0 P4.2: marker "PerDay" tường minh để tầng evaluation dừng cả lượt
        # (vẫn giữ chuỗi "perday" thường để kiểm tra cũ "perday in message" hoạt động).
        if quota_error_kind(reason) == "perday":
            raise GeneratorError(
                f"429 PerDay — hết quota NGÀY của Gemini: {reason}. Chờ reset (~14:00 VN = 07:00 UTC, "
                "midnight Pacific) rồi chạy lại ĐÚNG lệnh cũ; cache giữ phần đã trả lời, resume chỉ chạy câu thiếu."
            )
        raise GeneratorError(f"Gọi Gemini API thất bại: {reason}.{hint}")

    # ------------------------------------------------- Response caching (Giải pháp 2) ---

    def _cache_key(self, prompt: str, temperature: float) -> str:
        """SHA-1 của {model, temperature, prompt} — đổi model/prompt/corpus là tự miss cache."""
        payload = json.dumps(
            {
                "model": self.model_name,
                "temperature": temperature,
                "prompt_version": PROMPT_VERSION,
                "prompt": prompt,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[str]:
        """Đọc câu trả lời từ cache; file thiếu/hỏng/sai cấu trúc đều coi như cache miss."""
        path = self.cache_dir / f"{key}.json"
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            answer = entry["answer"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if not isinstance(answer, str) or not answer.strip():
            return None
        return answer

    def _cache_put(self, key: str, prompt: str, temperature: float, question: str, answer: str) -> None:
        """Ghi kết quả nguồn Gemini vào cache; lỗi đĩa/thư mục chỉ cảnh báo, không làm rơi câu trả lời."""
        entry = {
            "prompt_sha1": key,
            "model": self.model_name,
            "temperature": temperature,
            "query": question,
            "answer": answer,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path = self.cache_dir / f"{key}.json"
            tmp_path = self.cache_dir / f"{key}.json.tmp"
            tmp_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(path)  # ghi nguyên tử: Ctrl+C giữa chừng không để lại file dởm
        except OSError as exc:
            print(f"[Cache] Cảnh báo: không ghi được cache ({exc}) — câu trả lời vẫn được dùng bình thường.")

    # --------------------------------------- Fallback Local Qwen (Giải pháp 4) ---

    def _build_qwen_prompt(self, question: str, docs: list[dict]) -> str:
        """Prompt gọn cho Qwen2.5-1.5B: ngữ cảnh bị cắt cứng vì cửa sổ nhỏ, chỉ dẫn ngắn."""
        parts: list[str] = []
        total = 0
        for i, doc in enumerate(docs, start=1):
            block = (
                f"[{i}] {doc['source']} (Tầng {doc['tier']}):\n"
                f"{doc['content'][:QWEN_MAX_BLOCK_CHARS]}"
            )
            if parts and total + len(block) > QWEN_MAX_TOTAL_CHARS:
                break
            parts.append(block)
            total += len(block)
        context = "\n\n".join(parts)
        return (
            "Bạn là trợ lý học vụ Trường Đại học An Giang (AGU). Chỉ được dùng thông tin trong "
            "NGỮ CẢNH dưới đây, tuyệt đối không dùng kiến thức bên ngoài, không bịa số Điều/Khoản.\n"
            "Trả lời bằng tiếng Việt, ngắn gọn (dưới 200 từ), mỗi ý PHẢI kèm căn cứ pháp lý:\n"
            "- Nếu ngữ cảnh có đánh số: (Điều N, Khoản M — Tên_file.pdf)\n"
            "- Nếu không đánh số: (Tên_file.pdf)\n"
            "Ví dụ: (Điều 14, Khoản 5 — 1059-qd-dhag-2020-09-29.pdf)\n"
            f'Nếu NGỮ CẢNH không đủ căn cứ, trả lời đúng một câu: "{REFUSAL_TEXT}"\n\n'
            f"NGỮ CẢNH:\n{context}\n\n"
            f"CÂU HỎI: {question}\n"
            "TRẢ LỜI:"
        )

    def _qwen_answer(self, question: str, docs: list[dict], gemini_error: Exception) -> str:
        """Tổng hợp câu trả lời thay thế bằng Local Qwen; kèm nhãn cảnh báo nguồn tạm thời.

        Ném GeneratorError khi cả Ollama cũng thất bại — caller (main.py, evaluation.py)
        đã bắt GeneratorError nên CLI/pipeline không bao giờ chết vì hết quota.
        """
        reason = (
            "Gemini đã hết quota"
            if is_quota_error(gemini_error)
            else f"Gemini gặp sự cố ({type(gemini_error).__name__})"
        )
        print(f"[Qwen-Fallback] {reason}: {str(gemini_error)[:200]}")
        print(f"[Qwen-Fallback] Chuyển sang Local Qwen ({self.ollama_model} @ {self.ollama_host})...")

        prompt = self._build_qwen_prompt(question, docs)
        try:
            client = ollama.Client(host=self.ollama_host, timeout=self.ollama_timeout)
            response = client.generate(
                model=self.ollama_model,
                prompt=prompt,
                options={
                    "temperature": QWEN_FALLBACK_TEMPERATURE,
                    "num_predict": QWEN_FALLBACK_NUM_PREDICT,
                    "num_ctx": QWEN_FALLBACK_NUM_CTX,
                },
                stream=False,
            )
        except Exception as exc:
            raise GeneratorError(
                f"Cả hai tầng sinh đều thất bại — Gemini: {gemini_error}; "
                f"Local Qwen tại {self.ollama_host} ({type(exc).__name__}: {exc}). "
                "Hãy kiểm tra 'ollama serve' đang chạy hoặc chờ quota Gemini reset."
            ) from exc

        text = response.get("response") if isinstance(response, dict) else getattr(response, "response", "")
        text = (text or "").strip()
        if not text:
            raise GeneratorError(
                f"Local Qwen trả về nội dung rỗng sau khi Gemini lỗi: {gemini_error}"
            )
        notice = QWEN_FALLBACK_NOTICE.format(reason=reason, model=self.ollama_model)
        return f"{notice}\n\n{text}"

    def generate_answer(
        self,
        query: str,
        retrieved_docs: list,
        temperature: Optional[float] = None,
        question_type: Optional[str] = None,
    ) -> str:
        """Sinh câu trả lời: cache → Gemini → (hết quota/sự cố) fallback Local Qwen.

        question_type (P3.4): nhãn loại câu hỏi từ tầng classifier; None → prompt
        gốc giống hệt từng ký tự (đường ENABLE_CLASSIFIER=0, cache cũ còn trúng).

        Hàm này là giao diện chính của Layer Generator trong kiến trúc Hybrid RAG.
        Nó thực hiện quy trình sau:
        1. Normalize retrieved_docs → format chuẩn cho prompt
        2. Soft Refusal: Nếu không có ngữ cảnh → trả về REFUSAL_TEXT ngay
        3. Check cache: Nếu trúng cache → hậu xử lý inject dùng chung (P3.4b) rồi trả lời ngay (tiết kiệm quota)
        4. Gọi Gemini API với System Instruction chống ảo giác
        5. Fallback: Nếu Gemini lỗi → chuyển sang Local Qwen với nhãn cảnh báo
        6. Save cache: Ghi câu trả lời Gemini (không cache câu fallback)

        Soft Refusal Mechanism:
        - IF (ngữ cảnh trống OR ngữ cảnh không liên quan) THEN
            RETURN REFUSAL_TEXT ("Xin lỗi, tài liệu hiện có không đủ thông tin...")
        - System Prompt ép Gemini từ chối khi không đủ căn cứ
        - Không đoán, không bịa đặt, không dùng kiến thức ngoài corpus

        Citation Rules (System Instruction):
        - Mỗi ý trả lời PHẢI kèm: (Điều N, Khoản M — Tên văn bản)
        - Nếu ngữ cảnh không đánh số → ghi: (<Tên văn bản>)
        - Dùng TÊN VĂN BẢN THẬT, không viết "(Ngữ cảnh 1)", "(1)"
        - Ưu tiên tier cao hơn (Tầng 1 = quy chế gốc)

        Response Caching:
        - Cache key = SHA-1({model, temperature, prompt_version, prompt})
        - PROMPT_VERSION bump khi sửa SYSTEM_INSTRUCTION/PROMPT_RULES
        - Chỉ cache câu trả lời từ Gemini (không cache fallback Qwen)
        - Cache tự invalidating khi đổi model/temperature/prompt

        Fallback Mechanism:
        - Trigger: Gemini lỗi quota (429) hoặc gặp sự cố
        - Action: Chuyển sang Local Qwen với nhãn cảnh báo
        - Label: "[Cảnh báo: Gemini hết quota — câu trả lời do Local Qwen tổng hợp]"
        - Error handling: Nếu cả Gemini và Qwen đều chết → ném GeneratorError

        Tham số:
            query: Câu hỏi đã chuẩn hóa từ Layer Normalization
            retrieved_docs: Danh sách chunk truy xuất từ Layer Retrieval
            temperature: Nhiệt độ sinh (mặc định 0.0 cho deterministic)

        Trả về:
            Câu trả lời có trích dẫn, hoặc REFUSAL_TEXT nếu không đủ căn cứ

        Xem chi tiết:
            - System Prompt: SYSTEM_INSTRUCTION (anti-hallucination)
            - Prompt Rules: PROMPT_RULES (citation + soft refusal)
            - Cache: _cache_get(), _cache_put() (line 420-449)
            - Fallback: _qwen_answer() (line 478-519)
            - Kiến trúc: SYSTEM_ARCHITECTURE.md - Section 2.5 (Logic Mệnh đề)
        """
        if not isinstance(query, str):
            raise TypeError(f"query phải là str, nhận được {type(query).__name__}.")
        question = query.strip()
        if not question:
            raise ValueError("Câu hỏi rỗng — không có gì để trả lời.")

        try:
            docs = normalize_docs(retrieved_docs)
        except TypeError as exc:
            raise GeneratorError(str(exc)) from exc

        if not docs:
            print("[Gemini] Cảnh báo: không truy xuất được ngữ cảnh nào — từ chối trả lời thay vì đoán.")
            return REFUSAL_TEXT

        resolved_temperature = self.temperature if temperature is None else temperature
        prompt = build_prompt(question, docs, question_type=question_type)

        if self.use_cache:
            key = self._cache_key(prompt, resolved_temperature)
            cached = self._cache_get(key)
            if cached is not None:
                print(f"[Cache] Trúng ./.generation_cache/{key[:12]}... — không gọi API, tiết kiệm quota.")
                # P3.4b: inject là hậu xử lý dùng chung HIT/MISS — cùng câu hỏi
                # trả cùng chuỗi bất kể lượt gọi có trúng cache hay không.
                if is_canonical_refusal_answer(cached, question_type):
                    return cached
                return inject_citations_from_metadata(cached, retrieved_docs)

        try:
            answer = self._call_api(prompt, resolved_temperature)
        except GeneratorError as exc:
            if not self.qwen_fallback:
                raise
            answer = self._qwen_answer(question, docs, exc)
            # Không cache câu fallback: lượt chạy sau vẫn được thử lại Gemini thật.
            print("[Qwen-Fallback] Câu trả lời fallback KHÔNG lưu cache — lượt sau sẽ thử lại Gemini.")
            return answer

        # P3.4: chuẩn hóa từ chối cho NGOAI_PHAM_VI TRƯỚC khi lưu cache để
        # lượt sau (trúng cache) cũng trả đúng chuỗi chuẩn.
        answer = canonicalize_refusal(answer, question_type)

        if self.use_cache:
            self._cache_put(key, prompt, resolved_temperature, question, answer)

        # P3.4: NGOAI_PHAM_VI mà model tự từ chối → trả ĐÚNG chuỗi REFUSAL_TEXT,
        # không đính kèm trích dẫn (giữ nguyên vẹn chuỗi chuẩn cho evaluation).
        if is_canonical_refusal_answer(answer, question_type):
            return answer
        # P3.4b: tự động đính kèm trích dẫn từ metadata nếu chưa có — bước hậu
        # xử lý dùng chung cả nhánh HIT lẫn MISS.
        answer = inject_citations_from_metadata(answer, retrieved_docs)

        return answer


class QwenGenerator:
    """Lớp sinh câu trả lời bằng Local SLM (Qwen chạy trên Ollama).
    
    Chạy 100% offline, không tốn token Gemini và không bị giới hạn quota API.
    Có hỗ trợ response caching để tăng tốc đánh giá lặp lại.
    """

    def __init__(
        self,
        ollama_host: Optional[str] = None,
        ollama_model: Optional[str] = None,
        timeout: Optional[float] = None,
        temperature: float = QWEN_FALLBACK_TEMPERATURE,
        use_cache: Optional[bool] = None,
    ):
        self.ollama_host = ollama_host or os.getenv("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else _env_float("OLLAMA_TIMEOUT", DEFAULT_OLLAMA_TIMEOUT)
        self.temperature = temperature
        self.model_name = f"local-qwen ({self.ollama_model})"
        self.use_cache = _env_flag("GENERATION_CACHE", True) if use_cache is None else use_cache
        self.cache_dir = Path(os.getenv("GENERATION_CACHE_DIR") or GENERATION_CACHE_DIR)

    # Chỉ dẫn định dạng ngắn theo question_type (P3.4) — Qwen 1.5B cửa sổ nhỏ nên
    # chỉ nhét MỘT dòng thay vì toàn bộ appendix của Gemini. None → không thêm gì,
    # prompt giữ nguyên từng ký tự (cache Qwen cũ vẫn trúng).
    QWEN_FORMAT_LINES = {
        "so_sanh": "Câu hỏi so sánh: trả lời dạng bảng (mỗi hàng một tiêu chí), mỗi ô kèm trích dẫn nguồn riêng.",
        "thu_tuc": "Câu hỏi thủ tục: trả lời các bước đánh số (Bước 1, Bước 2, ...), mỗi bước kèm căn cứ.",
        "ngoai_pham_vi": NGOAI_PHAM_VI_EXTRA_LINE,
    }

    def _build_prompt(self, question: str, docs: list[dict], question_type: Optional[str] = None) -> str:
        parts: list[str] = []
        total = 0
        for i, doc in enumerate(docs, start=1):
            block = (
                f"[{i}] {doc['source']} (Tầng {doc['tier']}):\n"
                f"{doc['content'][:QWEN_MAX_BLOCK_CHARS]}"
            )
            if parts and total + len(block) > QWEN_MAX_TOTAL_CHARS:
                break
            parts.append(block)
            total += len(block)
        context = "\n\n".join(parts)
        format_line = ""
        if question_type:
            key = fold(str(question_type)).strip().lower()
            format_line = self.QWEN_FORMAT_LINES.get(key, "")
        head = (
            "Bạn là trợ lý học vụ Trường Đại học An Giang (AGU). Chỉ được dùng thông tin trong "
            "NGỮ CẢNH dưới đây, tuyệt đối không dùng kiến thức bên ngoài, không bịa số Điều/Khoản.\n"
            "Trả lời bằng tiếng Việt, ngắn gọn (dưới 200 từ), mỗi ý PHẢI kèm căn cứ pháp lý:\n"
            "- Nếu ngữ cảnh có đánh số: (Điều N, Khoản M — Tên_file.pdf)\n"
            "- Nếu không đánh số: (Tên_file.pdf)\n"
            "Ví dụ: (Điều 14, Khoản 5 — 1059-qd-dhag-2020-09-29.pdf)\n"
            f'Nếu NGỮ CẢNH không đủ căn cứ, trả lời đúng một câu: "{REFUSAL_TEXT}"\n'
        )
        if format_line:
            head += f"{format_line}\n"
        return f"{head}\nNGỮ CẢNH:\n{context}\n\nCÂU HỎI: {question}\nTRẢ LỜI:"

    def _cache_key(self, prompt: str, temperature: float) -> str:
        payload = json.dumps(
            {
                "model": self.ollama_model,
                "temperature": temperature,
                "prompt_version": PROMPT_VERSION,
                "prompt": prompt,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[str]:
        path = self.cache_dir / f"{key}.json"
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            answer = entry["answer"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if not isinstance(answer, str) or not answer.strip():
            return None
        return answer

    def _cache_put(self, key: str, prompt: str, temperature: float, question: str, answer: str) -> None:
        entry = {
            "prompt_sha1": key,
            "model": self.ollama_model,
            "temperature": temperature,
            "query": question,
            "answer": answer,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path = self.cache_dir / f"{key}.json"
            tmp_path = self.cache_dir / f"{key}.json.tmp"
            tmp_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(path)
        except OSError as exc:
            print(f"[Cache] Cảnh báo: không ghi được cache ({exc}).")

    def generate_answer(
        self,
        query: str,
        retrieved_docs: list,
        temperature: Optional[float] = None,
        question_type: Optional[str] = None,
    ) -> str:
        """Sinh câu trả lời trực tiếp qua Ollama Qwen.

        question_type (P3.4): None → prompt giữ nguyên từng ký tự; nhãn SO_SANH/
        THU_TUC/NGOAI_PHAM_VI → chèn 1 dòng định dạng ngắn (cache tự tách key).
        """
        if not isinstance(query, str):
            raise TypeError(f"query phải là str, nhận được {type(query).__name__}.")
        question = query.strip()
        if not question:
            raise ValueError("Câu hỏi rỗng — không có gì để trả lời.")

        try:
            docs = normalize_docs(retrieved_docs)
        except TypeError as exc:
            raise GeneratorError(str(exc)) from exc

        if not docs:
            print("[QwenGenerator] Cảnh báo: không truy xuất được ngữ cảnh nào — từ chối trả lời.")
            return REFUSAL_TEXT

        resolved_temp = self.temperature if temperature is None else temperature
        prompt = self._build_prompt(question, docs, question_type=question_type)

        if self.use_cache:
            key = self._cache_key(prompt, resolved_temp)
            cached = self._cache_get(key)
            if cached is not None:
                print(f"[Cache] Trúng cache Qwen ./.generation_cache/{key[:12]}...")
                # P3.4b: inject là hậu xử lý dùng chung HIT/MISS — cùng câu hỏi
                # trả cùng chuỗi bất kể lượt gọi có trúng cache hay không.
                if is_canonical_refusal_answer(cached, question_type):
                    return cached
                return inject_citations_from_metadata(cached, retrieved_docs)

        try:
            client = ollama.Client(host=self.ollama_host, timeout=self.timeout)
            response = client.generate(
                model=self.ollama_model,
                prompt=prompt,
                options={
                    "temperature": resolved_temp,
                    "num_predict": QWEN_FALLBACK_NUM_PREDICT,
                    "num_ctx": QWEN_FALLBACK_NUM_CTX,
                },
                stream=False,
            )
        except Exception as exc:
            raise GeneratorError(
                f"Local Qwen ({self.ollama_model} @ {self.ollama_host}) thất bại: {exc}"
            ) from exc

        text = response.get("response") if isinstance(response, dict) else getattr(response, "response", "")
        text = (text or "").strip()
        if not text:
            raise GeneratorError(f"Local Qwen trả về nội dung rỗng cho câu hỏi: {question}")

        # P3.4: chuẩn hóa từ chối cho NGOAI_PHAM_VI TRƯỚC khi lưu cache để
        # lượt sau (trúng cache) cũng trả đúng chuỗi chuẩn.
        text = canonicalize_refusal(text, question_type)

        if self.use_cache:
            self._cache_put(key, prompt, resolved_temp, question, text)

        # P3.4: NGOAI_PHAM_VI mà model tự từ chối → trả ĐÚNG chuỗi REFUSAL_TEXT,
        # không đính kèm trích dẫn (giữ nguyên vẹn chuỗi chuẩn cho evaluation).
        if is_canonical_refusal_answer(text, question_type):
            return text
        # P3.4b: tự động đính kèm trích dẫn từ metadata nếu chưa có — bước hậu
        # xử lý dùng chung cả nhánh HIT lẫn MISS.
        text = inject_citations_from_metadata(text, retrieved_docs)

        return text
