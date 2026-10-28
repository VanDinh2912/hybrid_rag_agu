"""Module chuẩn hóa câu hỏi của sinh viên sang từ khóa pháp lý chuẩn quy chế ĐHAG.

Module này cung cấp hàm `normalize_user_query` sử dụng Local Qwen (Ollama)
với System Prompt chuyên biệt cùng các quy tắc ánh xạ bắt buộc:
|- "đuổi học", "đuổi", "thôi học" -> "buộc thôi học"
|- "loại yếu", "hạnh kiểm yếu", "điểm yếu" -> "xếp loại rèn luyện Yếu"
|- "rớt môn", "trượt môn", "không qua" -> "điểm học phần lần thứ nhất dưới 5.5"
|- "nợ học phí", "tiền học" -> "hỗ trợ học phí", "miễn giảm học phí"
|- "mấy tín", "mã mấy", "môn nào trước" -> "bao nhiêu tín chỉ", "mã môn học", "môn học trước"

QUAN TRỌNG: System Prompt được thiết kế để CHỐNG HALLUCINATION - ép Qwen tuyệt đối
không được tự ý bổ sung tên ngành, tên khoa, tên môn học tiên quyết hoặc bất kỳ
thông tin nào không có trong câu hỏi gốc. Chỉ thay thế từ đồng nghĩa/viết tắt.

Vai trò trong kiến trúc Hybrid RAG:
- Layer 1 của pipeline: Chuẩn hóa câu hỏi trước khi đưa vào retrieval
- Mục tiêu: Tăng độ tương đồng vector giữa câu hỏi sinh viên và corpus quy chế
- Model: Qwen2.5:1.5b-instruct (1.5B parameters) chạy local qua Ollama
- Temperature: 0.0 (deterministic) để đảm bảo tính nhất quán

ACTIVE LEARNING: Module hỗ trợ học từ phản hồi người dùng
- Tự động tải cặp (câu_gốc -> câu_chuẩn_hóa) từ normalization_pairs.json
- Nhét vào FEW_SHOT_PROMPT làm ví dụ thực tế để Qwen học
- Mỗi lần người dùng lưu phản hồi trên GUI, Qwen sẽ học cách dịch mới

Bảo đảm chịu lỗi (fault-tolerant): khối try-except fallback trả về nguyên bản
câu hỏi gốc nếu LLM gặp bất kỳ sự cố nào.

Xem chi tiết kiến trúc: docs/architecture/SYSTEM_ARCHITECTURE.md - Section 4.1
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import ollama

from src.text_utils import fold

DEFAULT_MODEL = "qwen2.5:1.5b-instruct"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT = 90.0

# Đường dẫn file Active Learning cho normalization
NORMALIZATION_PAIRS_PATH = Path("data/normalization_pairs.json")
GHI_CHU_HOC_THEM_PATH = Path("data/corpus/ghi_chu_hoc_them.txt")
BENCHMARK_QUESTIONS_PATH = Path("data/evaluation/benchmark_questions.json")

NORMALIZER_SYSTEM_PROMPT = """Bạn là một bộ chuẩn hóa câu hỏi học vụ cho Trường Đại học An Giang.
Nhiệm vụ: Chuyển đổi từ ngữ thông tục/viết tắt trong câu hỏi thành thuật ngữ chuẩn quy chế.

QUY TẮC BẮT BUỘC:
1. KHÔNG ĐƯỢC TỰ Ý BỔ SUNG tên ngành, tên khoa, tên môn học tiên quyết hoặc bất kỳ thông tin nào KHÔNG CÓ trong câu hỏi gốc.
2. Chỉ thay thế từ đồng nghĩa/viết tắt:
   - "mấy tín", "mấy tín chỉ" -> "bao nhiêu tín chỉ"
   - "môn nào trước", "qua môn nào" -> "môn học trước"
   - "mã mấy", "mã gì" -> "mã môn học"
   - "đuổi học" -> "buộc thôi học"
   - "loại yếu" -> "xếp loại rèn luyện Yếu"

RÀNG BUỘC KẾT QUẢ ĐẦU RA:
- Giữ nguyên vẹn ý định hỏi ban đầu của sinh viên.
- Bảo toàn tuyệt đối mọi con số, điểm số, mốc thời gian, mã học phần, tên môn học (ví dụ: 1.0, 5.5, CON915, K21, Thiết kế và cài đặt mạng...).
- Chỉ xuất ra DUY NHẤT một câu hỏi đã chuẩn hóa, kết thúc bằng dấu chấm hỏi '?'.
- TUYỆT ĐỐI KHÔNG giải thích, không tự trả lời câu hỏi, không thêm bất kỳ tiền tố như 'Câu hỏi chuẩn hóa:', 'Trả lời:'.
"""

FEW_SHOT_PROMPT = """Ví dụ 1:
Sinh viên: Bị điểm rèn luyện loại yếu thì có bị đuổi học không ad?
Chuẩn hóa: Sinh viên có kết quả xếp loại rèn luyện Yếu có bị buộc thôi học không?

Ví dụ 2:
Sinh viên: Nếu em rớt môn thì có được xét học bổng với khen thưởng không ạ?
Chuẩn hóa: Sinh viên có điểm học phần lần thứ nhất dưới 5.5 có được xét khen thưởng và học bổng không?

Ví dụ 3:
Sinh viên: Em đang nợ học phí chưa đóng tiền học kịp thì làm đơn gì để được đi thi?
Chuẩn hóa: Sinh viên cần làm thủ tục gì về hỗ trợ học phí, miễn giảm học phí và gia hạn nộp học phí để được dự thi?

Ví dụ 4:
Sinh viên: môn Thiết kế và cài đặt mạng mã mấy vậy, học mấy tín với phải qua môn nào trước
Chuẩn hóa: Môn Thiết kế và cài đặt mạng có mã môn học là gì, bao nhiêu tín chỉ và có môn học trước là môn nào?

Ví dụ 5:
Sinh viên: {user_query}
Chuẩn hóa:"""

LABEL_PREFIX_RE = re.compile(
    r"^(?:câu hỏi chuẩn hóa|chuẩn hóa|câu hỏi|kết quả|output|normalized query)\s*[:\-\u2013]?\s*",
    re.IGNORECASE,
)
QUOTES = "\"'`""''"


def load_normalization_pairs() -> dict:
    """Tải cặp (câu_gốc -> câu_chuẩn_hóa) từ 3 nguồn theo thứ tự ưu tiên:
    
    1. normalization_pairs.json (người dùng thêm qua GUI)
    2. ghi_chu_hoc_them.txt (bài học cũ, format có cấu trúc)
    3. benchmark_questions.json (bộ câu hỏi benchmark chuẩn)
    
    Trả về dict format: {"raw_query": "normalized_query"}
    Nếu không có dữ liệu từ bất kỳ nguồn nào, trả về dict rỗng.
    """
    all_pairs = {}
    
    # 1. Tải từ normalization_pairs.json (ưu tiên cao nhất)
    try:
        if NORMALIZATION_PAIRS_PATH.exists():
            with open(NORMALIZATION_PAIRS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for p in data.get("pairs", []):
                all_pairs[p["raw_query"]] = p["normalized_query"]
            print(f"[Normalization] Đã tải {len(data.get('pairs', []))} cặp từ normalization_pairs.json")
    except Exception as exc:
        print(f"[Normalization] Lỗi khi tải normalization_pairs.json: {exc}")
    
    # 2. Tải từ ghi_chu_hoc_them.txt (format có cấu trúc)
    try:
        if GHI_CHU_HOC_THEM_PATH.exists():
            with open(GHI_CHU_HOC_THEM_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Parse format: "Câu hỏi: ...\nChuẩn hóa: ...\n-"
            import re
            pattern = r"Câu hỏi:\s*(.+?)\n(?:.*?\n)*?Chuẩn hóa:\s*(.+?)(?:\n|$)"
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            
            for raw, norm in matches:
                raw = raw.strip()
                norm = norm.strip()
                if raw and norm:
                    all_pairs[raw] = norm
            
            print(f"[Normalization] Đã tải {len(matches)} cặp từ ghi_chu_hoc_them.txt")
    except Exception as exc:
        print(f"[Normalization] Lỗi khi tải ghi_chu_hoc_them.txt: {exc}")
    
    # 3. Tải từ benchmark_questions.json (bộ câu hỏi chuẩn)
    try:
        if BENCHMARK_QUESTIONS_PATH.exists():
            with open(BENCHMARK_QUESTIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for q in data.get("questions", []):
                raw = q.get("raw_query", "")
                norm = q.get("normalized_query", "")
                if raw and norm:
                    all_pairs[raw] = norm
            
            print(f"[Normalization] Đã tải {len(data.get('questions', []))} cặp từ benchmark_questions.json")
    except Exception as exc:
        print(f"[Normalization] Lỗi khi tải benchmark_questions.json: {exc}")
    
    print(f"[Normalization] Tổng cộng đã tải {len(all_pairs)} cặp chuẩn hóa từ 3 nguồn")
    return all_pairs


# 4 ví dụ base cố định. Đưa lên cấp module để `prompt_example_lines()` (bản kiểm
# chứng đầu ra, P5.16) dùng lại ĐÚNG danh sách này — một bản sao thứ hai sẽ lệch âm
# thầm khi ai đó sửa few-shot, và gate sẽ bảo vệ nhầm cái prompt cũ.
BASE_EXAMPLES = [
    {
        "raw": "Bị điểm rèn luyện loại yếu thì có bị đuổi học không ad?",
        "normalized": "Sinh viên có kết quả xếp loại rèn luyện Yếu có bị buộc thôi học không?"
    },
    {
        "raw": "Nếu em rớt môn thì có được xét học bổng với khen thưởng không ạ?",
        "normalized": "Sinh viên có điểm học phần lần thứ nhất dưới 5.5 có được xét khen thưởng và học bổng không?"
    },
    {
        "raw": "Em đang nợ học phí chưa đóng tiền học kịp thì làm đơn gì để được đi thi?",
        "normalized": "Sinh viên cần làm thủ tục gì về hỗ trợ học phí, miễn giảm học phí và gia hạn nộp học phí để được dự thi?"
    },
    {
        "raw": "môn Thiết kế và cài đặt mạng mã mấy vậy, học mấy tín với phải qua môn nào trước",
        "normalized": "Môn Thiết kế và cài đặt mạng có mã môn học là gì, bao nhiêu tín chỉ và có môn học trước là môn nào?"
    },
]

LEARNING_EXAMPLE_LIMIT = 4


def build_few_shot_with_learning(user_query: str, learning_pairs: dict) -> str:
    """Xây dựng Few-Shot Prompt với các ví dụ học từ người dùng.
    
    Thuật toán:
    1. Sử dụng 4 ví dụ cố định (hard-coded) làm base
    2. Thêm tối đa 4 ví dụ từ learning_pairs (người dùng thêm)
    3. Tổng số ví dụ: 4 (base) + min(4, len(learning_pairs)) (learning)
    4. Mục tiêu: Giữ prompt không quá dài để Qwen 1.5B vẫn xử lý tốt
    
    Tham số:
        user_query: Câu hỏi người dùng hiện tại
        learning_pairs: Dict {raw_query: normalized_query} từ phản hồi người dùng
    
    Trả về:
        Chuỗi prompt Few-Shot đã xây dựng
    """
    base_examples = BASE_EXAMPLES
    
    # Chọn tối đa 4 ví dụ từ learning_pairs
    learning_examples = []
    if learning_pairs:
        for raw, norm in list(learning_pairs.items())[:LEARNING_EXAMPLE_LIMIT]:
            learning_examples.append({"raw": raw, "normalized": norm})
    
    # Xây dựng prompt
    prompt_parts = []
    
    # Thêm ví dụ base
    for i, ex in enumerate(base_examples, 1):
        prompt_parts.append(f"Ví dụ {i}:")
        prompt_parts.append(f"Sinh viên: {ex['raw']}")
        prompt_parts.append(f"Chuẩn hóa: {ex['normalized']}")
        prompt_parts.append("")
    
    # Thêm ví dụ học (nếu có)
    for i, ex in enumerate(learning_examples, len(base_examples) + 1):
        prompt_parts.append(f"Ví dụ {i} (Người dùng thêm):")
        prompt_parts.append(f"Sinh viên: {ex['raw']}")
        prompt_parts.append(f"Chuẩn hóa: {ex['normalized']}")
        prompt_parts.append("")
    
    # Thêm câu hỏi hiện tại
    prompt_parts.append(f"Ví dụ {len(base_examples) + len(learning_examples) + 1}:")
    prompt_parts.append(f"Sinh viên: {user_query}")
    prompt_parts.append("Chuẩn hóa:")
    
    return "\n".join(prompt_parts)


def clean_normalized_text(text: str) -> str:
    """Làm sạch output từ mô hình, loại bỏ nhãn và dấu ngoặc kép thừa.

    Qwen đôi khi thêm các nhãn không mong muốn như "Câu hỏi chuẩn hóa:",
    "Chuẩn hóa:", "Trả lời:" ở đầu output. Hàm này loại bỏ các nhãn đó
    và dấu ngoặc kép để chỉ giữ lại nội dung câu hỏi đã chuẩn hóa.

    Thuật toán:
    1. Tách output thành các dòng (splitlines)
    2. Với mỗi dòng:
       - Loại bỏ LABEL_PREFIX (regex) nếu có
       - Loại bỏ dấu ngoặc kép (QUOTES) ở đầu/cuôi
       - Lặp đến khi không còn thay đổi (fixed-point iteration)
    3. Chuẩn hóa khoảng trắng (multiple spaces → single space)
    4. Trả về dòng đầu tiên không rỗng

    Tham số:
        text: Output thô từ Qwen

    Trả về:
        Chuỗi câu hỏi đã làm sạch, hoặc chuỗi rỗng nếu input rỗng
    """
    if not text:
        return ""
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


# ---------------------------------------------------------------------------
# P5.16 — bản kiểm chứng đầu ra của bộ chuẩn hóa (mặc định TẮT)
# ---------------------------------------------------------------------------
# Vì sao cần: vòng lặp P5 đo trên 300 lượt sinh (r0/r1/r3, 100 item x 3 round) cho thấy
# `normalize_user_query` thỉnh thoảng trả về văn bản KHÔNG PHẢI câu hỏi đã chuẩn hóa:
#   (a) ECHO NGUYÊN VĂN một dòng few-shot — "Sinh viên: Bị điểm rèn luyện loại yếu thì có
#       bị đuổi học không ad?" xuất hiện làm output của 3 item KHÁC nhau;
#   (b) TRẢ LỜI thay vì chuẩn hóa — item hỏi mức phụ cấp nội quy nhận được
#       "Mức độ hoàn thành: 9/10".
# Không phải hàm tất định dù temperature=0.0: so 100 item trùng khớp giữa các round thì
# r0 và r3 cho `normalized_query` giống nhau 100/100, còn r1 lệch 18/100 (cùng code, cùng
# model). Coi tỉ lệ hỏng là đặc tính TẦN SUẤT (5-6/100 mỗi lượt), đừng dựa vào một bản
# chuẩn hóa của MỘT lượt chạy.
# Hậu quả không dừng ở câu trả lời lệch: `src/pipeline.py:386` đưa `normalized_query` vào
# CẢ truy xuất lẫn sinh, nên item bị hỏng từ gốc — 5/23 `FAIL_RETRIEVAL` của r1 ở pha đắt
# thuộc nhóm này, tức một phần "lỗi truy xuất" thực chất là lỗi tầng input.
#
# Ngưỡng 0.3 KHÔNG phải số vẽ ra: phân bố containment (số token gốc còn sót trong output)
# trên 300 lượt có median 1,00 và p10 0,46; cả hai mode hỏng ở trên nằm dưới 0,15. Một
# chuẩn hóa tốt được phép ĐỔI chữ (từ lóng → thuật ngữ) nên chỉ số này không cần cao; rơi
# xuống dưới 0,3 nghĩa là phần lớn nội dung câu hỏi đã biến mất.
NORMALIZE_SANITY_GUARD_ENV = "NORMALIZE_SANITY_GUARD"
NORMALIZE_MIN_CONTAINMENT_ENV = "NORMALIZE_MIN_CONTAINMENT"
DEFAULT_NORMALIZE_MIN_CONTAINMENT = 0.3

_CONTENT_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_sanity_guard_enabled() -> bool:
    """Mặc định TẮT — bật bằng `NORMALIZE_SANITY_GUARD=1` (đường production cũ không đổi)."""
    return (os.getenv(NORMALIZE_SANITY_GUARD_ENV) or "0").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    )


def normalize_min_containment() -> float:
    """Ngưỡng tối thiểu tỉ lệ token gốc còn sót trong output (0..1, giá trị hỏng -> mặc định)."""
    raw = (os.getenv(NORMALIZE_MIN_CONTAINMENT_ENV) or "").strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_NORMALIZE_MIN_CONTAINMENT
    return min(1.0, max(0.0, value))


def content_tokens(text: str) -> set:
    """Token "nội dung" (bỏ ký tự đơn và dấu câu), so không dấu qua `fold()`."""
    return {tok for tok in _CONTENT_TOKEN_RE.findall(fold(text or "")) if len(tok) > 2}


def token_containment(raw_query: str, normalized: str) -> float:
    """Bao nhiêu token của câu GỐC còn xuất hiện trong câu chuẩn hóa (1.0 = giữ hết)."""
    base = content_tokens(raw_query)
    if not base:
        return 1.0
    return len(base & content_tokens(normalized)) / len(base)


def prompt_example_lines(learning_pairs: Optional[dict] = None) -> set:
    """Mọi dòng ví dụ model có thể chép lại, đã `fold()` (cả vế 'Sinh viên:' lẫn vế 'Chuẩn hóa:').

    Danh sách lấy thẳng từ `BASE_EXAMPLES` + learning pairs đang dùng để dựng prompt, nên
    sửa few-shot thì gate tự cập nhật — không có bản sao thứ hai để lệch âm.
    """
    lines = set()
    pairs = [(ex["raw"], ex["normalized"]) for ex in BASE_EXAMPLES]
    if learning_pairs:
        pairs += [(raw, norm) for raw, norm in list(learning_pairs.items())[:LEARNING_EXAMPLE_LIMIT]]
    for raw, norm in pairs:
        for text in (raw, norm, f"Sinh viên: {raw}"):
            lines.add(fold(str(text)).strip())
    return lines


def normalized_output_rejection(
    raw_query: str, normalized: str, learning_pairs: Optional[dict] = None
) -> str:
    """Lý do BÁC bản chuẩn hóa, hoặc chuỗi rỗng nếu chấp nhận. Deterministic, không gọi model."""
    if not (normalized or "").strip():
        return "output rỗng"
    if fold(normalized).strip() in prompt_example_lines(learning_pairs):
        return "chép nguyên văn một dòng few-shot"
    ratio = token_containment(raw_query, normalized)
    floor = normalize_min_containment()
    if ratio < floor:
        return (
            f"mất nội dung câu gốc (containment={ratio:.2f} < ngưỡng {floor:.2f})"
        )
    return ""


def normalize_user_query(llm_client: Any, user_query: str) -> str:
    """Chuyển đổi câu hỏi thông tục của sinh viên sang từ khóa pháp lý chuẩn ĐHAG.

    Hàm này là giao diện chính của Layer Normalization trong kiến trúc Hybrid RAG.
    Nó sử dụng Local Qwen (Ollama) để:
    1. Ánh xạ từ lóng/tiếng lóng → thuật ngữ quy chế chuẩn
    2. Sửa lỗi chính tả và chuẩn hóa văn phong
    3. Bảo toàn tên môn học, con số, mốc thời gian gốc
    4. CHỐNG HALLUCINATION - không bổ sung thông tin không có trong câu hỏi

    ACTIVE LEARNING: Tự động tải và sử dụng cặp chuẩn hóa từ người dùng
    - Tải normalization_pairs.json chứa (câu_gốc -> câu_chuẩn_hóa) từ phản hồi GUI
    - Nhét vào Few-Shot Prompt làm ví dụ thực tế
    - Mỗi lần người dùng lưu phản hồi trên GUI → Qwen học cách dịch mới

    Ví dụ ánh xạ:
    - "đuổi học" → "buộc thôi học"
    - "loại yếu" → "xếp loại rèn luyện Yếu"
    - "rớt môn" → "điểm học phần lần thứ nhất dưới 5.5"
    - "mấy tín" → "bao nhiêu tín chỉ"
    - "mã mấy" → "mã môn học"

    Hỗ trợ nhiều loại llm_client:
    - ollama.Client: Client chính thức của Ollama
    - LocalSLM: Wrapper tùy chỉnh (có hàm generate)
    - ChatOllama: Client hỗ trợ chat (có hàm chat)
    - Callable: Bất kỳ callable chấp nhận prompt
    - None: Tự khởi tạo ollama.Client từ biến môi trường

    Tham số:
        llm_client: Client giao tiếp với mô hình (ví dụ: ollama.Client, instance LocalSLM,
                    hoặc None để tự khởi tạo từ cấu hình môi trường).
        user_query: Chuỗi câu hỏi gốc của sinh viên (có thể viết tắt, tiếng lóng).

    Trả về:
        Câu hỏi sau khi chuẩn hóa (chuẩn quy chế ĐHAG), hoặc nguyên bản user_query
        nếu LLM gặp lỗi (fault-tolerant fallback).

    Xem chi tiết:
        - System Prompt: NORMALIZER_SYSTEM_PROMPT (chống hallucination)
        - Learning: load_normalization_pairs(), build_few_shot_with_learning()
        - Kiến trúc: docs/architecture/SYSTEM_ARCHITECTURE.md - Section 4.1
    """
    if not isinstance(user_query, str):
        return str(user_query) if user_query is not None else ""

    raw_text = user_query.strip()
    if not raw_text:
        return raw_text

    try:
        model_name = os.getenv("OLLAMA_MODEL") or DEFAULT_MODEL
        host = os.getenv("OLLAMA_HOST") or DEFAULT_HOST
        timeout = float(os.getenv("OLLAMA_TIMEOUT", str(DEFAULT_TIMEOUT)))

        # Load learning pairs từ phản hồi người dùng
        learning_pairs = load_normalization_pairs()

        # Xây dựng Few-Shot Prompt với ví dụ học
        prompt = build_few_shot_with_learning(raw_text, learning_pairs)

        # 1. Trường hợp llm_client hỗ trợ generate trực tiếp (như LocalSLM)
        if hasattr(llm_client, "generate") and callable(getattr(llm_client, "generate")):
            try:
                # Nếu là client Ollama chính thức: client.generate(model=..., prompt=..., system=...)
                if isinstance(llm_client, ollama.Client):
                    response = llm_client.generate(
                        model=model_name,
                        prompt=prompt,
                        system=NORMALIZER_SYSTEM_PROMPT,
                        options={"temperature": 0.0, "num_predict": 128},
                        stream=False,
                    )
                    text = response.get("response") if isinstance(response, dict) else getattr(response, "response", "")
                else:
                    # Đối tượng SLM wrapper có hàm generate(prompt=...)
                    full_prompt = f"{NORMALIZER_SYSTEM_PROMPT}\n\n{prompt}"
                    text = llm_client.generate(full_prompt, temperature=0.0)
            except TypeError:
                full_prompt = f"{NORMALIZER_SYSTEM_PROMPT}\n\n{prompt}"
                text = llm_client.generate(full_prompt)

        # 2. Trường hợp llm_client hỗ trợ chat (như ChatOllama hoặc ollama.chat)
        elif hasattr(llm_client, "chat") and callable(getattr(llm_client, "chat")):
            messages = [
                {"role": "system", "content": NORMALIZER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            response = llm_client.chat(model=model_name, messages=messages, options={"temperature": 0.0})
            if isinstance(response, dict):
                text = response.get("message", {}).get("content", "")
            else:
                msg = getattr(response, "message", None)
                text = getattr(msg, "content", "") if msg else ""

        # 3. Trường hợp llm_client là callable hoặc None
        elif callable(llm_client):
            full_prompt = f"{NORMALIZER_SYSTEM_PROMPT}\n\n{prompt}"
            text = str(llm_client(full_prompt))
        else:
            # Tự khởi tạo ollama.Client nếu llm_client không truyền hoặc không xác định
            client = ollama.Client(host=host, timeout=timeout)
            response = client.generate(
                model=model_name,
                prompt=prompt,
                system=NORMALIZER_SYSTEM_PROMPT,
                options={"temperature": 0.0, "num_predict": 128},
                stream=False,
            )
            text = response.get("response") if isinstance(response, dict) else getattr(response, "response", "")

        cleaned = clean_normalized_text(text)
        if not cleaned:
            return raw_text
        if normalize_sanity_guard_enabled():
            # P5.16: output phải còn LÀ câu hỏi này. Không đạt -> dùng câu gốc, tức đúng
            # hành vi của hệ thống trước khi có bộ chuẩn hóa (không bao giờ lệch chủ đề).
            reason = normalized_output_rejection(raw_text, cleaned, learning_pairs)
            if reason:
                print(
                    f"[QueryNormalizer] Bác bản chuẩn hóa: {reason} — dùng câu gốc "
                    f"(gốc={raw_text[:60]!r} -> model={cleaned[:60]!r})"
                )
                return raw_text
        return cleaned
    except Exception as exc:
        print(f"[QueryNormalizer] Lỗi khi gọi Local Qwen ({type(exc).__name__}: {exc}) - Fallback về câu gốc.")
        return raw_text
