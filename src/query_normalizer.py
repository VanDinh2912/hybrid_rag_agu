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

Bảo đảm chịu lỗi (fault-tolerant): khối try-except fallback trả về nguyên bản
câu hỏi gốc nếu LLM gặp bất kỳ sự cố nào.
"""

import os
import re
from typing import Any, Optional

import ollama

DEFAULT_MODEL = "qwen2.5:1.5b-instruct"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT = 90.0

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


def clean_normalized_text(text: str) -> str:
    """Làm sạch output từ mô hình, loại bỏ nhãn và dấu ngoặc kép thừa."""
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


def normalize_user_query(llm_client: Any, user_query: str) -> str:
    """Chuyển đổi câu hỏi thông tục của sinh viên sang từ khóa pháp lý chuẩn ĐHAG.

    Tham số:
        llm_client: Client giao tiếp với mô hình (ví dụ: ollama.Client, instance LocalSLM,
                    hoặc None để tự khởi tạo từ cấu hình môi trường).
        user_query: Chuỗi câu hỏi gốc của sinh viên.

    Trả về:
        Câu hỏi sau khi chuẩn hóa, hoặc nguyên bản user_query nếu LLM gặp lỗi.
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

        prompt = FEW_SHOT_PROMPT.format(user_query=raw_text)

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
        if cleaned:
            return cleaned
        return raw_text

    except Exception as exc:
        print(f"[QueryNormalizer] Lỗi khi gọi Local Qwen ({type(exc).__name__}: {exc}) - Fallback về câu gốc.")
        return raw_text
