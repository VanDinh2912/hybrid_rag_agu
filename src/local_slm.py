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
"""

import os
import re
from typing import Optional

import ollama


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

    Few-shot cố định 3 mẫu (tiếng lóng / viết tắt không dấu / sai chính tả) vì
    Qwen2.5-1.5B dễ bịa khi nhận câu hỏi nằm ngoài phân bố ví dụ đã cho.
    """
    return (
        "Bạn là bộ chuẩn hóa câu hỏi cho hệ thống tra cứu quy chế đào tạo đại học.\n"
        "Nhiệm vụ: viết lại câu hỏi đời thường của sinh viên thành MỘT câu hỏi trang trọng,\n"
        "rõ nghĩa pháp lý, dùng đúng thuật ngữ học vụ, giữ nguyên mọi con số/mốc thời gian,\n"
        "để hệ thống tìm kiếm vector truy xuất đúng điều khoản quy chế.\n"
        "Ràng buộc: chỉ xuất ra DUY NHẤT một dòng là câu hỏi đã viết lại. "
        "Không giải thích, không trả lời câu hỏi, không thêm chữ nào khác.\n\n"
        "Ví dụ 1:\n"
        'Câu hỏi thô: "Ê ad, tui bị ĐTBHK dưới 1.0 thì có bị đuổi học luôn không hay sao?"\n'
        'Câu hỏi chuẩn hóa: "Sinh viên có điểm trung bình học kỳ dưới 1.0 có bị buộc thôi học không?"\n\n'
        "Ví dụ 2:\n"
        'Câu hỏi thô: "cho e hỏi mún xin hoãn học phí thì lm đơn j nộp ở đâu z ạ"\n'
        'Câu hỏi chuẩn hóa: "Sinh viên cần làm đơn gì và nộp ở đâu để được gia hạn học phí?"\n\n'
        "Ví dụ 3:\n"
        'Câu hỏi thô: "rớt môn tiên quyết r thì có đc đkí môn đó lại hk ad"\n'
        'Câu hỏi chuẩn hóa: "Sinh viên chưa đạt môn học tiên quyết có được đăng ký học lại môn đó không?"\n\n'
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


def _env_float(name: str, default: float) -> float:
    """Đọc số thực từ biến môi trường, trả về default nếu thiếu hoặc sai định dạng."""
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


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
    ):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL") or DEFAULT_MODEL
        self.host = host or os.getenv("OLLAMA_HOST") or DEFAULT_HOST
        self.timeout = timeout if timeout is not None else _env_float("OLLAMA_TIMEOUT", DEFAULT_TIMEOUT)
        self.probe_timeout = probe_timeout
        self.num_predict = num_predict
        self.max_retries = max(0, max_retries)
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
                if attempt:
                    print(f"[LocalSLM] Chuẩn hóa thành công ở lần thử {attempt + 1}.")
                return normalized

            print(f"[LocalSLM] Lần thử {attempt + 1} bị loại — {reason}.")
            if attempt < self.max_retries:
                prompt = base_prompt + CORRECTION_SUFFIX

        print(f"[LocalSLM] Suy giảm mềm: dùng nguyên câu hỏi gốc để truy xuất ({reason}).")
        return question
