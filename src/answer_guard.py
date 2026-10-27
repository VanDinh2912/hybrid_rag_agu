"""Tầng kiểm chứng căn cứ câu trả lời (answer grounding guard).

Lý do tồn tại: `src/faithfulness_heuristic.py` chỉ đo token-overlap toàn cục
(tỉ lệ từ xuất hiện lại), còn `local_slm.guardrail_violation` chỉ canh tầng
CHUẨN HÓA CÂU HỎI. Câu trả lời đi thẳng tới sinh viên mà không có lớp nào kiểm
tra từng KHẲNG ĐỊNH CỤ THỂ. Một câu trả lời bịa "học phí 500.000đ" nhưng chép
lại 90% chữ của context vẫn qua token-overlap — đúng loại lỗi cần chặn.

Thiết kế (bất biến quan trọng):
- Deterministic, không gọi LLM, chạy được trên CPU, chi phí ~ms.
- Đơn vị kiểm chứng là THỰC THỂ: số (kèm đơn vị tiền/tỷ lệ), mã văn bản
  (1054-QĐ, CON915), số Điều/Khoản, ngày, và cụm tên riêng viết hoa.
- Thực thể được coi là CÓ CĂN CỨ nếu xuất hiện trong tập context đã truy xuất
  (so khớp sau `fold`, chuẩn hóa phân tách nghìn), hoặc do chính người hỏi nêu
  trong câu hỏi (không phải model bịa ra).
- Cùng module này được dùng ở hai nơi: (1) pipeline production — từ chối/retry;
  (2) `tools/loop/verify.py` — chấm điểm vòng lặp. Nhờ đó số liệu đo và hành vi
  thật của hệ thống không thể lệch nhau.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from src.text_utils import fold

# ---------------------------------------------------------------------------
# Nhận diện thực thể
# ---------------------------------------------------------------------------

# Số có thể kèm dấu phân tách nghìn (1.500.000 / 1,500,000), phần thập phân,
# đơn vị đi liền (đ, đồng, %, tín chỉ, ngày, buổi, LDP...).
NUMBER_RE = re.compile(
    r"(?<![\w])(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)"
    r"(?P<unit>\s?(?:đ|dong|dong/dt|VNĐ| đồng|%|tuoi/nam|nam|tháng|ngày|tuần|buổi|ti[ê]n ch[ỉ]|tín chỉ|tc|phút|giờ|lượt|SV|sinh viên|người|hồ sơ|đơn))?",
    re.IGNORECASE,
)
# Mã văn bản/mã môn học: chữ hoa có số xen kẽ (1054-QĐ, QD1133, CON915, CVHS-29).
CODE_RE = re.compile(r"(?<![\w])[A-ZĐ]{1,6}[\-]?\d{2,6}[A-ZĐ\-]*|(?<![\w])\d{2,6}[\-](?:QD|Q\.?D\.?)[\-\d]*", re.UNICODE)
# Điều/Khoản/Điểm/Mục — pháp điển, rất dễ bị bịa số.
LEGAL_REF_RE = re.compile(
    r"(?:[Đđ]iều|[Kk]ho[ảa]n?|[Đđ]i[ểe]m|[Mm]ục)\s*(?:\d+|[A-Z]{1,3})", re.UNICODE
)
DATE_RE = re.compile(r"\d{1,2}[/.]\d{1,2}[/.]\d{2,4}")
# Cụm tên riêng: >=2 từ LIÊN TIẾP đều viết hoa chữ đầu ("Công Nghệ Web", "Đắk Nông").
# Không dùng range [À-Ỹ] vì trong Python nó phủ U+00C0..U+07EF, bao gồm cả chữ
# thường có dấu (đ, ơ, ị…) -> nhận diện sai thành tên riêng. Bẻ nhỏ bằng
# `str[0].isupper()` (đúng Unicode) trên từng token.
TOKEN_RE = re.compile(r"\w+(?:[\-'’]\w+)*", re.UNICODE)

# PA-2 (duyệt 25-10): những từ mở đầu cụm HOA mà câu văn tiếng Việt viết hoa theo
# quy tắc chính tả chứ không phải tên riêng — "Theo Bản mô tả…", "Theo Thông báo…",
# "Tại Khoản 1…". Bằng chứng dương-giả: 3/25 id T1(b) bị cờ FAIL_FABRICATED chỉ vì
# loại này (docs/reports/T1.md mục "Kiểm tay 5 ca FAIL_FABRICATED"). Một token trong
# tập này KHÔNG được mở/tiếp tục cụm tên riêng; các từ khác vẫn đối xử như cũ.
_PROPER_RUN_STOPWORDS = {fold(w) for w in {
    "Theo", "Tại", "Căn", "Các", "Trong", "Nếu", "Khi", "Vì", "Do",
    "Đối", "Phần", "Mục", "Về", "Bằng", "Từ", "Đến", "Với",
}}

# Từ viết hoa hợp lệ luôn xuất hiện mà không phải thực thể (đầu câu, thuật ngữ
# định dạng, nhãn nguồn). Danh sách chủ đích RỘNG để tránh báo động giả.
_ALLOWED_CAPITAL_PHRASES_RAW = {
    "cộng hòa", "xã hội", "chủ nghĩa", "việt nam", "đại học", "an giang",
    "trường đại học", "sinh viên", "học kỳ", "học phí", "tân sinh viên",
    "chương trình", "công tác", "cán bộ", "giảng viên", "danh hiệu",
    "trách nhiệm", "hữu hạn", "bảo hiểm", "y tế", "thể dục", "quốc phòng",
    "khiển trách", "cảnh cáo", "đình chỉ", "tốt nghiệp", "trường", "khoa",
    "phòng", "ban", "viện", "tổ", "nhóm", "số", "ngày", "tháng", "năm",
}
# So khớp luôn diễn ra sau `fold` (đã mất dấu), nên danh sách cho phép cũng phải
# được fold một lượt — nếu không "Sinh Viên"/"Học Phí" (danh sách ghi "sinh viên")
# không bao giờ khớp và mọi thuật ngữ định dạng bị gọi là thực thể không căn cứ.
_ALLOWED_CAPITAL_PHRASES = {fold(p) for p in _ALLOWED_CAPITAL_PHRASES_RAW}
# Tập từ 1 chữ cái-trong-cụm được coi là quen thuộc: cụm cho phép + mọi từ đơn
# trong danh sách gốc (kể cả dưới 5 ký tự như "ban", "tổ", "số").
_ALLOWED_CAPITAL_TOKENS = (
    _ALLOWED_CAPITAL_PHRASES | {w for p in _ALLOWED_CAPITAL_PHRASES_RAW for w in fold(p).split()}
)

# Bỏ qua số nằm trong ngữ cảnh định dạng/liệt kê không mang khẳng định.
_IGNORE_CONTEXT_RE = re.compile(
    r"(bước|b?ước|nguồn|trang|dòng|cột|hàng|vd|ví dụ|thí dụ)", re.IGNORECASE
)


def _norm_number(raw: str) -> Optional[str]:
    """Chuẩn hóa số: bỏ dấu phân tách nghìn, về dạng không dấu chấm/phẩy.

    '1.500.000' -> '1500000'; '2' -> '2'; '02' -> '2'; '70' -> '70'.
    Số thập phân giữ nguyên chữ số sau dấu (nhưng tách cả hai dạng ghi).
    """
    s = raw.strip()
    if not s:
        return None
    # Dạng nhóm 3 chữ số: 1.500.000 / 1,500,000 -> 1500000
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        return s.replace(".", "").replace(",", "")
    m = re.fullmatch(r"(\d+)([.,])(\d+)", s)
    if m:
        # 2,5 và 2.5 là cùng một số; '2,5' kiểu nhóm bị quy về 25 ở trên
        variants = {m.group(1) + m.group(3), m.group(1)}
        return "|".join(sorted(variants))
    if re.fullmatch(r"0*\d+", s):
        return str(int(s))
    return None


def _number_variants(raw: str) -> set[str]:
    """Mọi dạng ghi chấp nhận được của một số (để so khớp hai chiều)."""
    out: set[str] = set()
    s = raw.strip()
    out.add(s)
    n = _norm_number(s)
    if n:
        for part in n.split("|"):
            out.add(part)
    return {o for o in out if o}


@dataclass(frozen=True)
class Entity:
    kind: str  # number | code | legal | date | proper
    text: str
    start: int

    @property
    def end(self) -> int:
        """Biên phải suy từ độ dài — cần cho thao tác che/điền (CLOZE) ở vòng lặp."""
        return self.start + len(self.text)

    def keys(self) -> set[str]:
        """Các khóa so khớp (fold + chuẩn hóa số).

        Với số, trả về TẤT CẢ biến thể chấp nhận ('28,6' -> {'28,6','286','28'});
        bản trước trả nguyên chuỗi nối '286|28' nên không bao giờ khớp và tạo
        báo động giả hàng loạt (phát hiện khi hiệu chỉnh trên dữ liệu A/B cũ).
        """
        if self.kind == "number":
            return _number_variants(self.text)
        return {fold(self.text)}


@dataclass
class GroundingReport:
    """Kết quả kiểm chứng căn cứ của MỘT câu trả lời."""

    supported: list[Entity] = field(default_factory=list)
    unsupported: list[Entity] = field(default_factory=list)
    entities_total: int = 0
    contexts_chars: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def grounding_score(self) -> Optional[float]:
        """Tỉ lệ khẳng định có căn cứ. None khi câu trả lời không có khẳng định
        nào kiểm chứng được (ví dụ câu từ chối) — không được tính là điểm 100."""
        if self.entities_total == 0:
            return None
        return round(len(self.supported) / self.entities_total, 4)

    @property
    def fabricated(self) -> bool:
        return bool(self.unsupported)

    def to_dict(self) -> dict:
        return {
            "grounding_score": self.grounding_score,
            "entities_total": self.entities_total,
            "n_supported": len(self.supported),
            "n_unsupported": len(self.unsupported),
            "unsupported": [
                {"kind": e.kind, "text": e.text} for e in self.unsupported
            ],
            "contexts_chars": self.contexts_chars,
            "notes": self.notes,
        }


def _scan_proper_runs(text: str) -> list[tuple[int, int, str]]:
    """Tìm cụm >=2 từ liền nhau cùng viết hoa chữ đầu (tên riêng/định dạng Title).

    Chỉ tính khi các từ kề nhau bằng khoảng trắng đơn (không cách bởi dấu chấm,
    phẩy, xuống dòng) — ranh giới câu không được biến hai từ đầu câu thành 'tên riêng'.
    """
    runs: list[tuple[int, int, str]] = []
    current: list[tuple[int, int, str]] = []
    prev_end: Optional[int] = None
    for m in TOKEN_RE.finditer(text):
        tok = m.group(0)
        is_cap = (
            bool(tok)
            and tok[0].isupper()
            and len(tok) >= 2
            and not tok.isdigit()
            and fold(tok) not in _PROPER_RUN_STOPWORDS  # PA-2
        )
        adjacent = prev_end is not None and m.start() - prev_end == 1 and text[prev_end:m.start()] == " "
        if is_cap and current and adjacent:
            if fold(tok) == fold(current[-1][2]):
                # "Tầng Tầng", "Nguồn Nguồn": model chép lại đúng từ của khung cảnh do
                # CHÍNH HỆ THỐNG dán vào block truy xuất ("[1] file.pdf (Tầng 1)").
                # Đây là lỗi lặp của bộ sinh, không phải một khẳng định về thế giới, nên
                # không được biến thành thực thể "không căn cứ". Audit trên 38 ca
                # over-refusal của r1: 3/4 bản nháp bị guard chặn có "Tầng Tầng" trong
                # danh sách thực thể bị kết — 2 ca trong đó CHỈ vì nó (score 0,90 và 0,80
                # trên ngưỡng 0,60). Chỉ giữ một bản; hai từ KHÁC nhau vẫn thành cụm.
                prev_end = m.end()
                continue
            current.append((m.start(), m.end(), tok))
        elif is_cap:
            if len(current) >= 2:
                runs.append((current[0][0], current[-1][1], " ".join(t[2] for t in current)))
            current = [(m.start(), m.end(), tok)] if not tok.isupper() else []
        else:
            if len(current) >= 2:
                runs.append((current[0][0], current[-1][1], " ".join(t[2] for t in current)))
            current = []
        prev_end = m.end()
    if len(current) >= 2:
        runs.append((current[0][0], current[-1][1], " ".join(t[2] for t in current)))
    return runs


def extract_entities(
    text: str, *, include_proper: bool = True, include_codes: bool = True
) -> list[Entity]:
    """Rút các khẳng định kiểm chứng được khỏi câu trả lời.

    Thứ tự ưu tiên khi trùng lấp: legal/date/code trước, số sau (để "Điều 5"
    không đồng thời bị tính là số trần 5), tên riêng cuối cùng.
    """
    if not text:
        return []
    consumed: list[tuple[int, int]] = []
    entities: list[Entity] = []

    def claim(span: tuple[int, int]) -> bool:
        s, e = span
        for cs, ce in consumed:
            if s < ce and e > cs:
                return False
        consumed.append((s, e))
        return True

    for m in DATE_RE.finditer(text):
        if claim(m.span()):
            entities.append(Entity("date", m.group(0), m.start()))
    for m in LEGAL_REF_RE.finditer(text):
        if claim(m.span()):
            entities.append(Entity("legal", m.group(0), m.start()))
    if include_codes:
        for m in CODE_RE.finditer(text):
            tok = m.group(0)
            if len(tok) < 3:
                continue
            if claim(m.span()):
                entities.append(Entity("code", tok, m.start()))
    if include_proper:
        for start, end, tok in _scan_proper_runs(text):
            if not claim((start, end)):
                continue
            if len(tok) < 5:
                continue
            # Bỏ qua khi cả cụm — hoặc TỪNG từ của cụm — nằm trong danh sách thuật
            # ngữ định dạng. So hai chiều vì cụm 3 từ ("Trường Đại Học An Giang")
            # không có nguyên dạng trong danh sách nhưng từng từ đều quen thuộc;
            # gọi nó là thực thể bịa chỉ tạo báo động giả.
            folded_words = [fold(w) for w in tok.split()]
            if (
                fold(tok) in _ALLOWED_CAPITAL_PHRASES
                or fold(tok) in _ALLOWED_CAPITAL_TOKENS
                or all(w in _ALLOWED_CAPITAL_TOKENS for w in folded_words)
            ):
                continue
            entities.append(Entity("proper", tok, start))
    for m in NUMBER_RE.finditer(text):
        span = m.span(1)
        if not claim(span):
            continue
        raw = m.group(1)
        # Bỏ SỐ THỨ TỰ ở đầu dòng ("1. …", "12) …") — audit trên 50 câu A/B cũ
        # (tools/loop/audit_guard.py) cho thấy đây là nguồn báo động giả lớn nhất:
        # 42/45 thực thể "không căn cứ" là marker định dạng markdown, không phải
        # khẳng định. Số tiền/tỷ lệ thật vẫn nằm giữa dòng nên không bị ảnh hưởng.
        line_start = text.rfind("\n", 0, m.start()) + 1
        at_line_head = text[line_start : m.start()].strip() == ""
        if at_line_head and text[m.end() : m.end() + 1] in {".", ")"}:
            continue
        # Bỏ số nhỏ đứng một mình trong mệnh đề liệt kê/bước (kém đặc hiệu,
        # dễ trùng => nếu giữ sẽ làm loãng tỉ lệ và sinh báo động giả).
        head = text[max(0, m.start() - 20): m.start()]
        if _IGNORE_CONTEXT_RE.search(head) and not m.group("unit"):
            continue
        entities.append(Entity("number", raw, m.start()))

    return sorted(entities, key=lambda e: e.start)


def _corpus_of(contexts: Iterable[str]) -> str:
    return fold(" \n ".join(contexts or []))


def _haystack_keys(hay: str) -> set[str]:
    """Tập số xuất hiện trong văn bản tham chiếu (đã fold), chuẩn hóa một lượt."""
    keys: set[str] = set()
    for m in NUMBER_RE.finditer(hay):
        for v in _number_variants(m.group(1)):
            keys.add(v)
    return keys


def check_grounding(
    answer: str,
    contexts: list[str],
    question: str = "",
    *,
    min_entity_len: int = 2,
    extra_haystack: Iterable[str] = (),
) -> GroundingReport:
    """Kiểm từng khẳng định của `answer` có căn cứ trong `contexts` hay không.

    Khung so khớp = contexts + câu hỏi (thực thể do người hỏi nêu không tính là
    bịa) + `extra_haystack`. So khớp fold, không phân biệt hoa/thường và dấu câu;
    số được chuẩn hóa phân tách nghìn.

    `extra_haystack` dùng cho TÊN VĂN BẢN đã truy xuất: pipeline tự dán tên file
    vào cuối câu trả lời (`inject_citations_from_metadata`), nên các số trong tên
    file ("1059-qd-dhag-2020-09-29.pdf") mà chỉ so với page_content sẽ bị gọi là
    bịa — 7/11 trường hợp UNSOURCED còn lại trong audit cũ đúng là loại này.
    """
    report = GroundingReport()
    parts = [_corpus_of(contexts), fold(question or "")]
    if extra_haystack:
        parts.append(fold(" \n ".join(x for x in extra_haystack if x)))
    hay_text = " \n ".join(parts)
    report.contexts_chars = sum(len(c or "") for c in (contexts or []))
    hay_numbers = _haystack_keys(hay_text)
    hay_folded = hay_text

    for ent in extract_entities(answer or ""):
        keys = ent.keys()
        keys = {k for k in keys if len(k) >= min_entity_len}
        if not keys:
            continue
        report.entities_total += 1
        if ent.kind == "number":
            hit = bool(keys & hay_numbers) or any(k in hay_folded for k in keys)
        else:
            hit = any(k in hay_folded for k in keys)
        if hit:
            report.supported.append(ent)
        else:
            report.unsupported.append(ent)
    return report


def refusal_thresholds() -> tuple[float, int]:
    """Ngưỡng từ chối cứng (env): min_score và max_unsupported.

    ENABLE_ANSWER_GUARD=1 bật tầng guard. Mặc định min_score=0.6, max_unsupported=1:
    chỉ một khẳng định không căn cứ cũng đủ để không tin câu trả lời.
    """
    try:
        min_score = float(os.getenv("ANSWER_GUARD_MIN_SCORE", "0.6"))
    except ValueError:
        min_score = 0.6
    try:
        max_unsupported = int(os.getenv("ANSWER_GUARD_MAX_UNSUPPORTED", "1"))
    except ValueError:
        max_unsupported = 1
    return min_score, max_unsupported


def is_enough_evidence(contexts: list[str]) -> bool:
    """Không có ngữ cảnh thì không có quyền khẳng định (chống bịa khi retrieve hỏng)."""
    return bool(contexts) and any(len(c or "") >= 40 for c in contexts)


# ---------------------------------------------------------------------------
# Tích hợp Ollama (bám sát pattern lỗi đã biết của tầng normalize)
# ---------------------------------------------------------------------------

# Lỗi có thể tái thử: quá thời gian, hết VRAM, kết nối bị ngắt.
RETRYABLE_MARKERS = (
    "overloaded",
    "timed out",
    "timeout",
    "connection refused",
    "connection reset",
    "EOF occurred",
    "cuda out of memory",
    "500",
    "503",
)


def is_retryable(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in RETRYABLE_MARKERS)


def generate_verified(
    generate_fn,
    question: str,
    contexts: list[str],
    *,
    build_prompt,
    max_attempts: int = 2,
    retry_wait_seconds: float = 0.0,
    on_refusal,
    log=print,
):
    """Sinh câu trả lời và CHỈ chấp nhận khi đi qua `check_grounding`.

    Args:
        generate_fn: callable(prompt, temperature=..., num_predict=...) -> str
        build_prompt: callable(question, contexts, attempt, previous) -> str
            attempt 2 nhận câu trả lời cũ để model tự bỏ khẳng định không căn cứ.
        on_refusal: callable(reason, report) -> str  (chuỗi từ chối chuẩn của app)

    Trả về (answer, report). Mọi nhánh lỗi đều có `report` để evaluation ghi lại
    được vì sao câu trả lời bị chặn.
    """
    report = GroundingReport()
    answer = ""
    last_error: Optional[Exception] = None
    for attempt in range(1, max(1, int(max_attempts)) + 1):
        if not is_enough_evidence(contexts):
            report.notes.append("no_context: từ chối vì không có căn cứ để trả lời")
            return on_refusal("empty_context", report), report
        try:
            answer = generate_fn(build_prompt(attempt, answer))
        except Exception as exc:  # Ollama/process lỗi
            last_error = exc
            if attempt < max_attempts and is_retryable(exc):
                log(
                    f"[AnswerGuard] Thử lại lượt {attempt + 1}/{max_attempts} vì "
                    f"{type(exc).__name__}: {str(exc)[:120]}"
                )
                if retry_wait_seconds > 0:
                    import time

                    time.sleep(retry_wait_seconds)
                continue
            report.notes.append(
                f"generation_error: {type(exc).__name__}: {str(exc)[:160]} — từ chối thay vì trả lời chưa kiểm chứng"
            )
            return on_refusal("generation_error", report), report
        report = check_grounding(answer, contexts, question)
        if not report.fabricated and (report.grounding_score or 0) >= refusal_thresholds()[0]:
            report.notes.append(f"accepted(attempt={attempt})")
            return answer, report
        log(
            "[AnswerGuard] Câu trả lời có "
            f"{len(report.unsupported)} khẳng định không căn cứ "
            f"(score={report.grounding_score}) — "
            + ("tự sửa và thử lại" if attempt < max_attempts else "từ chối")
        )
    if last_error is not None and not answer:
        report.notes.append("generation_error: không sinh được câu trả lời")
        return on_refusal("generation_error", report), report
    report.notes.append("rejected_ungrounded: chặn để bảo toàn tính trung thực")
    return on_refusal("ungrounded_answer", report), report


# ---------------------------------------------------------------------------
# Tầng guard cho đường sinh câu trả lời (Qwen local)
# ---------------------------------------------------------------------------


def answer_guard_enabled() -> bool:
    """Cờ bật guard câu trả lời. Mặc định TẮT để không đổi hành vi đã nghiệm thu."""
    return os.getenv("ENABLE_ANSWER_GUARD", "0").strip().lower() not in {"0", "false", "no"}


_CORRECTION_TEMPLATE = """

CẢNH BÁO KIỂM CHỨNG: những khẳng định sau KHÔNG xuất hiện trong NGỮ CẢNH ở trên
và bị hệ thống coi là bịa: {bad}.
Hãy viết lại câu trả lời: (1) XÓA mọi nội dung chỉ tồn tại vì {bad},
(2) chỉ giữ những ý có câu chữ trong ngữ cảnh, (3) nếu sau khi xóa không còn gì
đủ căn cứ thì trả lời ĐÚNG một câu từ chối chuẩn, không thêm số liệu.
"""


def guard_qwen_answer(
    *,
    text: str,
    question: str,
    docs: list[dict],
    generate_fn,
    prompt: str,
    max_attempts: int = 2,
    log=print,
) -> str:
    """Chặn câu trả lời có khẳng định không căn cứ: tự sửa 1 lượt, vẫn lỗi -> từ chối.

    Trả về chuỗi cuối cùng (có thể là REFUSAL_TEXT). Không ném exception: tầng
    guard không được phép làm chết lượt hỏi của sinh viên.
    """
    from src.generator import REFUSAL_TEXT  # import trễ để tránh vòng lặp module

    contexts = [(d.get("content") or "") for d in (docs or [])]
    # Tên file là hệ thống dán vào (không phải model bịa) -> thuộc khung so khớp.
    names = [str(d.get("source") or "") for d in (docs or [])]
    min_score, _ = refusal_thresholds()
    current = text
    for attempt in range(1, max(1, int(max_attempts)) + 1):
        try:
            report = check_grounding(current, contexts, question, extra_haystack=names)
        except Exception as exc:  # trọng tài lỗi -> không chặn, giữ hành vi cũ
            log(f"[AnswerGuard] Bỏ qua vì lỗi kiểm chứng: {exc}")
            return current
        if not report.fabricated and (report.grounding_score is None or report.grounding_score >= min_score):
            if attempt > 1:
                report.notes.append(f"accepted_after_retry(attempt={attempt})")
            return current
        bad = ", ".join(sorted({e.text for e in report.unsupported})[:6]) or "(không xác định)"
        log(f"[AnswerGuard] Không căn cứ: {bad}")
        if attempt >= max_attempts:
            break
        try:
            candidate = generate_fn(prompt + _CORRECTION_TEMPLATE.format(bad=bad))
        except Exception as exc:
            log(f"[AnswerGuard] Thử lại thất bại ({type(exc).__name__}) — từ chối an toàn")
            break
        if not candidate.strip():
            break
        current = candidate.strip()
    log("[AnswerGuard] Từ chối chuẩn thay vì trả lời chưa được kiểm chứng.")
    return REFUSAL_TEXT
