"""Module sinh câu trả lời bằng Gemini API (backend trên mây của Hybrid RAG).

Trách nhiệm:
- Khởi tạo Google Generative AI client từ API key trong biến môi trường.
- `generate_answer(query, retrieved_docs)`: nhận câu hỏi đã chuẩn hóa cùng danh
  sách chunk truy xuất được từ ChromaDB (nội dung + tên văn bản + tier), dựng
  prompt nghiêm ngặt và trả về câu trả lời có trích dẫn Điều/Khoản.

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
import time
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import google.generativeai as genai
import ollama

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
PROMPT_VERSION = "v1.1"

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

FALLBACK_NOTICE_PREFIX = "[Cảnh báo:"
QWEN_FALLBACK_NOTICE = (
    "[Cảnh báo: {reason} — câu trả lời này được tổng hợp tạm thời bằng Local Qwen ({model}) "
    "để phục vụ demo. Hãy đối chiếu với văn bản gốc trước khi sử dụng.]"
)

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
2. Mỗi ý trả lời PHẢI kèm căn cứ pháp lý ngay trong câu, theo mẫu: (Điều 12, Khoản 3 — <tên văn bản>).
   Nếu ngữ cảnh không đánh số Điều/Khoản thì ghi căn cứ theo nguồn: (<tên văn bản>).
   Luôn dùng TÊN VĂN BẢN THẬT được ghi ở dòng "Nguồn:"; không viết "(Ngữ cảnh 1)", "(1)", "theo tài liệu".
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
[VÍ DỤ 3 — Ngữ cảnh có liên quan, trả lời đúng với trích dẫn]
Ngữ cảnh: [Ngữ cảnh 1] Nguồn: Quy chế đào tạo AGU 2023 | Tầng: 1
  "Điều 15, Khoản 2: Sinh viên được phép đăng ký học lại tối đa 2 lần cho mỗi học phần không đạt."
Câu hỏi: Sinh viên được học lại bao nhiêu lần nếu rớt môn?
✅ TRẢ LỜI ĐÚNG:
Sinh viên được phép đăng ký học lại tối đa **2 lần** cho mỗi học phần không đạt. (Điều 15, Khoản 2 — Quy chế đào tạo AGU 2023)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

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


def build_prompt(query: str, docs: list[dict]) -> str:
    """Dựng prompt grounded: mỗi chunk kèm số thứ tự, tên văn bản và tier."""
    blocks = []
    for i, doc in enumerate(docs, start=1):
        blocks.append(
            f"[Ngữ cảnh {i}] Nguồn: {doc['source']} | Tầng: {doc['tier']} | chunk_id: {doc['chunk_id']}\n"
            f"{doc['content']}"
        )
    context_block = "\n\n".join(blocks)
    return (
        f"NGỮ CẢNH TRUY XUẤT TỪ VECTOR DB ({len(docs)} đoạn):\n{context_block}\n\n"
        f"CÂU HỎI CỦA SINH VIÊN: {query}\n\n"
        f"{PROMPT_RULES.format(refusal=REFUSAL_TEXT)}\n\n"
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
        """Gọi Gemini kèm retry cho lỗi 429/5xx; ném GeneratorError khi thất bại hẳn."""
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.model.generate_content(prompt, generation_config=generation_config)
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                # Hết quota NGÀY ("PerDay") thì retry sau 2s/4s vô ích — break ngay,
                # tầng đánh giá sẽ nhận diện "perday" để dừng sớm cả lượt chạy.
                if "perday" in message:
                    break
                retryable = any(marker in message for marker in RETRYABLE_MARKERS)
                if not retryable or attempt == self.max_retries:
                    break
                wait = 2 ** (attempt + 1)
                print(f"[Gemini] Lỗi tạm thời ({type(exc).__name__}), thử lại sau {wait}s — lần {attempt + 1}/{self.max_retries}.")
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
            "Trả lời bằng tiếng Việt, ngắn gọn (dưới 200 từ), mỗi ý nêu căn cứ dạng "
            "(Điều N, Khoản M — tên văn bản) nếu ngữ cảnh có đánh số.\n"
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

    def generate_answer(self, query: str, retrieved_docs: list, temperature: Optional[float] = None) -> str:
        """Sinh câu trả lời: cache → Gemini → (hết quota/sự cố) fallback Local Qwen."""
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
        prompt = build_prompt(question, docs)

        if self.use_cache:
            key = self._cache_key(prompt, resolved_temperature)
            cached = self._cache_get(key)
            if cached is not None:
                print(f"[Cache] Trúng ./.generation_cache/{key[:12]}... — không gọi API, tiết kiệm quota.")
                return cached

        try:
            answer = self._call_api(prompt, resolved_temperature)
        except GeneratorError as exc:
            if not self.qwen_fallback:
                raise
            answer = self._qwen_answer(question, docs, exc)
            # Không cache câu fallback: lượt chạy sau vẫn được thử lại Gemini thật.
            print("[Qwen-Fallback] Câu trả lời fallback KHÔNG lưu cache — lượt sau sẽ thử lại Gemini.")
            return answer

        if self.use_cache:
            self._cache_put(key, prompt, resolved_temperature, question, answer)
        return answer
