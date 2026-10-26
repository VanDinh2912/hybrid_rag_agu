"""Module chuẩn hóa câu hỏi bằng Local SLM (Qwen chạy trên Ollama).

Trách nhiệm:
- Kết nối Ollama server cục bộ (mặc định http://localhost:11434).
- `normalize_query()`: viết lại câu hỏi đời thường của sinh viên (tiếng lóng,
  viết tắt, lỗi chính tả) thành câu hỏi học vụ trang trọng, rõ nghĩa pháp lý,
  nhằm tăng độ tương đồng vector khi truy xuất trong ChromaDB.

Nguyên tắc chịu lỗi: Local SLM chỉ là bước *tối ưu* truy xuất, không phải bước
bắt buộc. Mọi sự cố (Ollama chưa chạy, model chưa pull, timeout, model sinh nội
dung lạc đề) đều được bắt và suy giảm mềm về chính câu hỏi gốc kèm cảnh báo,
để pipeline luôn trả lời được.

Guardrail chống lệch nghĩa: Qwen 1.5B đôi khi "drift" — viết lại thành một câu
hỏi KHÁC chủ đề (thường là nhại lại câu hỏi trong ví dụ few-shot) — khiến tầng
truy xuất sa vào tài liệu sai. Sau khi Qwen xuất câu chuẩn hóa, module đối chiếu
với câu gốc bằng hai tín hiệu tính trên văn bản đã fold (bỏ dấu thanh):
(1) bảo toàn con số: mọi số của câu gốc phải còn xuất hiện và không được bịa
số mới; (2) tỉ lệ token: phần từ của câu chuẩn hóa phải bắt nguồn từ câu gốc
đạt ngưỡng tối thiểu. Vi phạm → fallback ngay về câu hỏi gốc kèm log
`[LocalSLM-Guardrail]`, vì truy xuất bằng câu gốc sai văn phong vẫn an toàn hơn
truy xuất bằng một câu hỏi bịa chủ đề khác.
"""

import re
from typing import Optional

import ollama

from src.config import settings
from src.text_utils import fold


class LocalSLMError(RuntimeError):
    """Lỗi khi giao tiếp với Ollama (không kết nối được, model lỗi, timeout)."""


DEFAULT_MODEL = "qwen2.5:1.5b-instruct"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT = 90.0
DEFAULT_PROBE_TIMEOUT = 5.0
DEFAULT_NUM_PREDICT = 128
DEFAULT_MAX_RETRIES = 1  # số lần thử lại khi output bị bộ lọc loại (không phải số lần gọi tối đa)

# Giới hạn độ dài câu chuẩn hóa: quá dài nghĩa là model đã "trả lời" thay vì viết lại.
MAX_NORMALIZED_CHARS = 300

# Dấu hiệu model lạc đề / từ chối / trả lời bằng ngôn ngữ khác (Qwen 1.5B hay
# bịa khi câu hỏi nằm ngoài phân bố few-shot) → hủy kết quả, dùng câu gốc.
REJECT_PATTERNS = (
    "xin lỗi",
    "xin loi",
    "tôi không thể",
    "không thể xác định",
    "không rõ",
    "hãy cung cấp",
    "vui lòng cung cấp",
    "as an ai",
    "i cannot",
    "i'm sorry",
    "câu hỏi thô",
    "câu hỏi chuẩn hóa:",
)

# Nhãn model hay lặp lại ở đầu dòng output ("Câu hỏi chuẩn hóa: ...").
LABEL_PREFIX_RE = re.compile(
    r"^(?:câu hỏi chuẩn hóa|cau hoi chuan hoa|chuẩn hóa|chuan hoa|câu hỏi|cau hoi|kết quả|ket qua|trả lời|tra loi|output)\s*[:\-\u2013]?\s*",
    re.IGNORECASE,
)


def build_normalize_prompt(raw_query: str) -> str:
    """Dựng prompt few-shot cho tác vụ chuẩn hóa câu hỏi.

    Few-shot cố định 4 mẫu (tiếng lóng có số liệu / viết tắt không dấu / sai
    chính tả / cụm danh từ không phải câu hỏi) vì Qwen2.5-1.5B dễ bịa khi nhận
    câu hỏi nằm ngoài phân bố ví dụ đã cho.
    """
    return (
        "Bạn là bộ chuẩn hóa câu hỏi cho hệ thống tra cứu quy chế đào tạo đại học.\n"
        "Nhiệm vụ: viết lại câu hỏi đời thường của sinh viên thành MỘT câu hỏi trang trọng,\n"
        "rõ nghĩa pháp lý, dùng đúng thuật ngữ học vụ.\n"
        "QUY TẮC BẢO TOÀN THỰC THỂ (bắt buộc):\n"
        "- Chỉ được sửa lỗi chính tả, bỏ tiếng lóng, làm sạch văn phong.\n"
        "- Giữ nguyên vẹn mọi con số, điểm số, mốc thời gian (1.0, 2.0, 2020, 5 tốt...).\n"
        "- Giữ nguyên vẹn từ khóa pháp lý/học vụ; được phép mở rộng đúng nghĩa:\n"
        "  'ĐTBHK' → 'điểm trung bình học kỳ', 'cảnh báo học vụ', 'buộc thôi học',\n"
        "  'mã học phần', tên danh hiệu, tên quy chế.\n"
        "- Không được đổi chủ đề: câu viết lại phải hỏi đúng điều sinh viên đang hỏi.\n"
        "- Nếu câu gốc là cụm từ (không phải câu hỏi), chỉ chuyển thành câu hỏi về\n"
        "  chính nội dung đó, không thêm chủ đề mới.\n"
        "Ràng buộc: chỉ xuất ra DUY NHẤT một dòng là câu hỏi đã viết lại. "
        "Không giải thích, không trả lời câu hỏi, không thêm chữ nào khác.\n\n"
        "Ví dụ 1:\n"
        'Câu hỏi thô: "Ê ad, tui bị ĐTBHK dưới 1.0 thì có bị đuổi học luôn không?"\n'
        'Câu hỏi chuẩn hóa: "Điểm trung bình học kỳ dưới 1.0 có bị buộc thôi học không?"\n\n'
        "Ví dụ 2:\n"
        'Câu hỏi thô: "cho e hỏi mún xin hoãn học phí thì lm đơn j nộp ở đâu z ạ"\n'
        'Câu hỏi chuẩn hóa: "Sinh viên cần làm đơn gì và nộp ở đâu để được gia hạn học phí?"\n\n'
        "Ví dụ 3:\n"
        'Câu hỏi thô: "rớt môn tiên quyết r thì có đc đkí môn đó lại hk ad"\n'
        'Câu hỏi chuẩn hóa: "Sinh viên chưa đạt môn học tiên quyết có được đăng ký học lại môn đó không?"\n\n'
        "Ví dụ 4:\n"
        'Câu hỏi thô: "quy che danh hieu Sinh vien 5 tot"\n'
        'Câu hỏi chuẩn hóa: "Sinh viên cần đạt tiêu chuẩn gì để được xét danh hiệu Sinh viên 5 tốt?"\n\n'
        f'Câu hỏi thô: "{raw_query}"\n'
        "Câu hỏi chuẩn hóa:"
    )


# Chỉ dẫn bổ sung khi lượt đầu bị từ chối. Qwen2.5-1.5B rất hay "trả lời luôn"
# thay vì viết lại câu hỏi (đã ghi nhận thực nghiệm), nên phải nhắc lại ràng buộc
# dạng câu hỏi một cách tường minh ở lượt thứ hai.
CORRECTION_SUFFIX = (
    "\n\nLưu ý: lần trước bạn đã TRẢ LỜI câu hỏi thay vì viết lại nó, và đưa ra nhận định không có căn cứ. "
    "Lần này chỉ được xuất ra DUY NHẤT MỘT CÂU HỎI kết thúc bằng dấu '?'. "
    "Không khẳng định đúng/sai, không giải thích, không thêm bất kỳ chữ nào khác."
)


QUOTES = "\"'`“”‘’"


def clean_output(text: str) -> str:
    """Làm sạch output của Qwen: bỏ nhãn, dấu nháy, khoảng trắng thừa, chỉ giữ dòng đầu.

    Phải lặp tới điểm bất động vì model có thể xen kẽ nhãn và dấu nháy
    (ví dụ `"Câu hỏi chuẩn hóa: ..."` — dấu nháy nằm ngoài nhãn).
    """
    for line in text.replace("\r", "").splitlines():
        cleaned = line.strip()
        while True:
            before = cleaned
            cleaned = LABEL_PREFIX_RE.sub("", cleaned.strip(QUOTES).strip()).strip()
            if cleaned == before:
                break
        cleaned = re.sub(r"\s+", " ", cleaned)
        if cleaned:
            return cleaned
    return ""


def is_acceptable(normalized: str) -> Optional[str]:
    """Trả về lý do từ chối nếu câu chuẩn hóa không dùng được, ngược lại trả về None."""
    if not normalized:
        return "model trả về chuỗi rỗng"
    if len(normalized) > MAX_NORMALIZED_CHARS:
        return f"câu chuẩn hóa dài {len(normalized)} ký tự (> {MAX_NORMALIZED_CHARS}) — nghi model trả lời thay vì viết lại"
    if "?" not in normalized:
        return "câu chuẩn hóa không ở dạng câu hỏi (thiếu dấu '?') — nghi model tự trả lời/bịa nhận định"
    lowered = normalized.lower()
    for pattern in REJECT_PATTERNS:
        if pattern in lowered:
            return f"câu chuẩn hóa chứa dấu hiệu lạc đề/từ chối ('{pattern}')"
    return None


# --- Guardrail chống lệch nghĩa (drift) -------------------------------------
# Đối chiếu trên văn bản đã fold (bỏ dấu thanh) để không đánh lừa do khác dấu;
# fold() dùng chung từ src/text_utils.py — xem docstring tại đó về bẫy "Đ"/U+0110.

# Tỉ lệ token (đã fold) của câu chuẩn hóa phải bắt nguồn từ câu hỏi gốc.
# Thực nghiệm trên 4 cặp few-shot: hợp lệ ≥ 0.4; ca drift quan sát được = 0.14.
MIN_TOKEN_OVERLAP = 0.3

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _extract_numbers(folded_text: str) -> set[str]:
    """Trích tập con số từ văn bản đã fold; '1,0' và '1.0' là cùng một số."""
    return {token.replace(",", ".") for token in _NUMBER_RE.findall(folded_text)}


def guardrail_violation(
    raw_query: str, normalized_query: str, min_overlap: float = MIN_TOKEN_OVERLAP
) -> Optional[str]:
    """Trả về lý do nếu câu chuẩn hóa bị lệch nghĩa so với câu gốc, None nếu an toàn.

    Hai tín hiệu trên văn bản đã fold:
    1. Bảo toàn con số: mất số của câu gốc hoặc bịa số mới đều là lệch nghĩa
       (Qwen từng biến "5 tốt" thành "dưới 2.0").
    2. Tỉ lệ token: phần từ từ của câu chuẩn hóa phải trùng câu gốc; quá thấp
       nghĩa là model đã đặt lại thành câu hỏi khác chủ đề.
    """
    raw_folded = fold(raw_query)
    norm_folded = fold(normalized_query)

    raw_numbers = _extract_numbers(raw_folded)
    norm_numbers = _extract_numbers(norm_folded)
    if raw_numbers - norm_numbers:
        return f"mất con số {', '.join(sorted(raw_numbers - norm_numbers))} có trong câu hỏi gốc"
    if norm_numbers - raw_numbers:
        return f"bịa thêm con số {', '.join(sorted(norm_numbers - raw_numbers))} không có trong câu hỏi gốc"

    norm_tokens = set(_TOKEN_RE.findall(norm_folded))
    if not norm_tokens:
        return "câu chuẩn hóa không còn token sau khi fold"
    overlap = len(set(_TOKEN_RE.findall(raw_folded)) & norm_tokens) / len(norm_tokens)
    if overlap < min_overlap:
        return (
            f"chỉ {overlap:.0%} token của câu chuẩn hóa có trong câu hỏi gốc "
            f"(ngưỡng {min_overlap:.0%}) — nghi đặt lại chủ đề"
        )
    return None


class LocalSLM:
    """Bao bọc mô hình Qwen chạy cục bộ qua Ollama."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        host: Optional[str] = None,
        timeout: Optional[float] = None,
        probe_timeout: float = DEFAULT_PROBE_TIMEOUT,
        num_predict: int = DEFAULT_NUM_PREDICT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        min_token_overlap: float = MIN_TOKEN_OVERLAP,
    ):
        cfg = settings()
        self.model_name = model_name or cfg.text_or("OLLAMA_MODEL", DEFAULT_MODEL)
        self.host = host or cfg.text_or("OLLAMA_HOST", DEFAULT_HOST)
        self.timeout = timeout if timeout is not None else cfg._env_float("OLLAMA_TIMEOUT", DEFAULT_TIMEOUT)
        self.probe_timeout = probe_timeout
        self.num_predict = num_predict
        self.max_retries = max(0, max_retries)
        self.min_token_overlap = min_token_overlap
        try:
            self.client = ollama.Client(host=self.host, timeout=self.timeout)
        except Exception as exc:  # host sai định dạng, thiếu quyền...
            raise LocalSLMError(f"Không khởi tạo được client Ollama tại '{self.host}': {exc}") from exc

    def check_connection(self) -> tuple[bool, str]:
        """Kiểm tra Ollama đang sống và model đã được pull chưa (không tải model)."""
        try:
            probe = ollama.Client(host=self.host, timeout=self.probe_timeout)
            response = probe.list()
        except Exception as exc:
            return False, (
                f"không kết nối được Ollama tại {self.host} ({type(exc).__name__}: {exc}). "
                "Hãy mở terminal khác và chạy 'ollama serve'."
            )

        models = getattr(response, "models", None) or []
        names = [str(getattr(m, "model", None) or getattr(m, "name", "") or "") for m in models]
        wanted = self.model_name.split(":")[0].lower()
        if not any(name.split(":")[0].lower() == wanted for name in names):
            return False, (
                f"Ollama đang chạy nhưng chưa có model '{self.model_name}' "
                f"(đã có: {', '.join(names) or 'không có model nào'}). "
                f"Hãy chạy 'ollama pull {self.model_name}'."
            )
        return True, f"Ollama sẵn sàng tại {self.host}, model '{self.model_name}'."

    def generate(self, prompt: str, temperature: float = 0.0, num_predict: Optional[int] = None) -> str:
        """Gửi prompt tới Qwen trên Ollama; ném LocalSLMError nếu giao tiếp thất bại."""
        options = {
            "temperature": temperature,
            "num_predict": num_predict if num_predict is not None else self.num_predict,
        }
        try:
            response = self.client.generate(model=self.model_name, prompt=prompt, options=options, stream=False)
        except ollama.ResponseError as exc:
            hint = ""
            if exc.status_code == 404:
                hint = f" Model chưa được tải — chạy 'ollama pull {self.model_name}'."
            raise LocalSLMError(f"Ollama trả về lỗi cho model '{self.model_name}': {exc}.{hint}") from exc
        except Exception as exc:  # ConnectError, ReadTimeout, JSON lỗi...
            raise LocalSLMError(
                f"Không gọi được Ollama tại {self.host} ({type(exc).__name__}: {exc}). "
                "Kiểm tra 'ollama serve' đang chạy và OLLAMA_HOST đúng."
            ) from exc

        text = response.get("response") if isinstance(response, dict) else getattr(response, "response", "")
        if text is None:
            raise LocalSLMError("Ollama phản hồi không có trường 'response'.")
        return text.strip()

    def normalize_query(self, raw_query: str) -> str:
        """Chuẩn hóa câu hỏi đời thường thành câu hỏi học vụ; lỗi thì trả về câu gốc."""
        if not isinstance(raw_query, str):
            raise TypeError(f"raw_query phải là str, nhận được {type(raw_query).__name__}.")
        question = raw_query.strip()
        if not question:
            raise ValueError("Câu hỏi rỗng — không có gì để chuẩn hóa.")

        base_prompt = build_normalize_prompt(question.replace('"', "'"))
        prompt = base_prompt
        reason = "không gọi được model"
        for attempt in range(self.max_retries + 1):
            try:
                output = self.generate(prompt)
            except LocalSLMError as exc:
                print(f"[LocalSLM] Cảnh báo: {exc}")
                print("[LocalSLM] Suy giảm mềm: dùng nguyên câu hỏi gốc để truy xuất.")
                return question

            normalized = clean_output(output)
            reason = is_acceptable(normalized)
            if reason is None:
                violation = guardrail_violation(question, normalized, self.min_token_overlap)
                if violation is None:
                    if attempt:
                        print(f"[LocalSLM] Chuẩn hóa thành công ở lần thử {attempt + 1}.")
                    return normalized
                print(
                    "[LocalSLM-Guardrail] Phát hiện Qwen làm lệch nghĩa — fallback về câu gốc "
                    f"({violation})."
                )
                print("[LocalSLM] Suy giảm mềm: dùng nguyên câu hỏi gốc để truy xuất.")
                return question

            print(f"[LocalSLM] Lần thử {attempt + 1} bị loại — {reason}.")
            if attempt < self.max_retries:
                prompt = base_prompt + CORRECTION_SUFFIX

        print(f"[LocalSLM] Suy giảm mềm: dùng nguyên câu hỏi gốc để truy xuất ({reason}).")
        return question
