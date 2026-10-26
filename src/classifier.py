"""Module phân loại câu hỏi 2 nhãn (chủ đề + loại câu hỏi) bằng Qwen local.

Trách nhiệm:
- `classify_query(query)`: gán cho câu hỏi THÔ của sinh viên hai nhãn:
  `topic` (1 trong 14 chủ đề của TAXONOMY.md hoặc None) và `question_type`
  (1 trong 4 nhãn TRA_CUU / SO_SANH / THU_TUC / NGOAI_PHAM_VI).
- Mô hình: Qwen2.5-1.5B-Instruct chạy qua Ollama (không dùng Gemini, không tốn
  quota). Prompt few-shot được dựng CỐ ĐỊNH từ 16 câu đã chọn trong
  `data/evaluation/benchmark_100_questions_v3.json` — xem `FEW_SHOT_SAMPLES`.

Guardrail 3 lớp (suy giảm mềm, pipeline không bao giờ chết vì classifier):
1. Lớp chính: Qwen trả JSON hợp lệ + nhãn hợp lệ → dùng luôn. `topic` được
   chuẩn hóa không dấu qua `fold()` để chịu được khác biệt dấu/hoa-thường.
2. JSON lỗi hoặc nhãn lạ → bổ sung phần nhãn hỏng bằng bảng từ khóa theo chủ đề
   và loại câu hỏi (dấu hiệu lấy từ TAXONOMY.md, so khớp không dấu).
3. Từ khóa cũng không khớp → `topic=None`, `question_type="TRA_CUU"`. Router
   hiểu `topic=None` là không lọc, dùng cấu hình chung.

Ollama chết / timeout (`CLASSIFIER_TIMEOUT`, mặc định 20 giây) → trả thẳng
kết quả lớp 3 kèm log cảnh báo; không ném ngoại lệ ra pipeline.

Cấu hình (đọc qua dotenv như các module `src/` khác):
- `CLASSIFIER_MODEL`: tên model Qwen; để trống thì dùng `OLLAMA_MODEL`.
- `CLASSIFIER_TIMEOUT`: thời gian chờ tối đa mỗi lần gọi (giây).
- `OLLAMA_HOST`: địa chỉ Ollama (dùng chung với LocalSLM).
"""

import json
import re
from typing import Optional

from dotenv import load_dotenv

from src.config import settings
from src.local_slm import LocalSLM
from src.text_utils import fold

load_dotenv()

DEFAULT_MODEL = "qwen2.5:1.5b-instruct"
DEFAULT_TIMEOUT = 20.0
# Model được yêu cầu in 1 dòng dấu hiệu ngắn + 1 dòng JSON; 160 token đủ rộng.
DEFAULT_NUM_PREDICT = 160

DEFAULT_QUESTION_TYPE = "TRA_CUU"

# 14 chủ đề giữ nguyên chuỗi `category` của benchmark v3 (đúng cả dấu tiếng Việt).
TOPICS = (
    "chương trình đào tạo",
    "học phí",
    "cuộc thi chính luận",
    "đánh giá rèn luyện",
    "khen thưởng sinh viên",
    "thực tập tốt nghiệp",
    "quy chế công tác sinh viên",
    "sinh viên 5 tốt",
    "thực tập chuyên đề",
    "khen thưởng cấp ĐHQG",
    "ký túc xá",
    "tài chính sinh viên",
    "bảo hiểm y tế",
    "hành chính sinh viên",
)

QUESTION_TYPES = ("TRA_CUU", "SO_SANH", "THU_TUC", "NGOAI_PHAM_VI")

_TOPIC_BY_FOLDED = {fold(topic): topic for topic in TOPICS}

# Mô tả ngắn/dấu hiệu từng chủ đề — lấy từ bảng A của TAXONOMY.md. Bản rút gọn
# này hiệu quả hơn với Qwen 1.5B so với mô tả dài: model bám đúng từ khóa neo.
TOPIC_RULES = {
    "chương trình đào tạo": (
        "môn học, mã môn, tín chỉ, học kỳ, tiên quyết/học trước, ELO, chuẩn đầu ra, "
        "khối kiến thức."
    ),
    "học phí": (
        "học phí, miễn giảm, đơn giá tín chỉ, gia hạn nộp, học lại/cải thiện điểm."
    ),
    "cuộc thi chính luận": (
        "chính luận, tác phẩm dự thi, thể loại, dung lượng, hạn nộp bài."
    ),
    "đánh giá rèn luyện": (
        "rèn luyện, khung điểm, tiêu chí cộng/trừ, xếp loại rèn luyện."
    ),
    "khen thưởng sinh viên": (
        "danh hiệu thi đua năm học, Sinh viên Giỏi, Sinh viên Xuất sắc, giấy khen, "
        "mức tiền thưởng cấp Trường."
    ),
    "thực tập tốt nghiệp": (
        "thực tập tốt nghiệp, khóa luận tốt nghiệp, hội đồng chấm, báo cáo TTTN."
    ),
    "quy chế công tác sinh viên": (
        "nghỉ học tạm thời, kỷ luật, nhập học lại, cố vấn học tập, nghĩa vụ sinh viên, "
        "thi cử."
    ),
    # Neo âm: tránh Qwen gán mọi câu có "Sinh viên Xuất sắc"/"điểm rèn luyện" vào nhóm này.
    "sinh viên 5 tốt": (
        'chỉ khi câu hỏi nói rõ "Sinh viên 5 tốt" hoặc "Sao Tháng Giêng".'
    ),
    "thực tập chuyên đề": (
        "thực tập chuyên đề, tài liệu nghiệm thu, cơ sở thực tập."
    ),
    "khen thưởng cấp ĐHQG": (
        "ĐHQG, Đại học Quốc gia, Sinh viên Xuất sắc toàn khóa."
    ),
    "ký túc xá": "ký túc xá, nội trú, giờ giấc ra vào, thiết bị điện.",
    "tài chính sinh viên": "vay vốn, ACB, tín dụng ưu đãi, lãi suất, trả nợ gốc.",
    "bảo hiểm y tế": "bảo hiểm y tế, BHYT, VssID, VNeID.",
    "hành chính sinh viên": "mẫu đơn, hoàn cảnh khó khăn, cơ quan xác nhận.",
}

# Thứ tự dòng 1–4 chính là thứ tự luật phân giải xung đột của TAXONOMY.md.
QUESTION_TYPE_RULES = (
    (
        "NGOAI_PHAM_VI",
        "không thể trả lời từ văn bản quy chế của Trường (du học, visa, trường khác, "
        "kiến thức chung, tư vấn cá nhân).",
    ),
    (
        "SO_SANH",
        'hỏi từ 2 đối tượng/mức/nguồn trở lên cần đối chiếu hoặc tổng hợp; có "so sánh", '
        '"khác nhau", "so với", "các mức".',
    ),
    (
        "THU_TUC",
        "hỏi hồ sơ, giấy tờ, tài liệu cần nộp, thủ tục, các bước, nơi nộp hoặc nơi "
        "xác nhận.",
    ),
    (
        "TRA_CUU",
        "còn lại — hỏi một thông tin cụ thể (bao nhiêu, là gì, điều kiện nào, ra sao).",
    ),
)

# Dòng "Dấu hiệu" trong few-shot giúp Qwen 1.5B bám quy tắc thay vì chỉ nhại đáp án.
SIGNAL_BY_TYPE = {
    "TRA_CUU": "tra một thông tin cụ thể",
    "SO_SANH": "so sánh/đối chiếu từ 2 đối tượng trở lên",
    "THU_TUC": "hồ sơ/giấy tờ/thủ tục",
    "NGOAI_PHAM_VI": "ngoài quy chế AGU",
}

# --- Few-shot cố định -------------------------------------------------------
# Nguồn: data/evaluation/benchmark_100_questions_v3.json (đọc một lần khi soạn
# code, KHÔNG đọc lại lúc chạy). Chọn đúng 16 câu:
#   - 1 câu/chủ đề (14 chủ đề): Q02, Q78, Q39, Q44, Q55, Q88, Q90, Q92, Q93,
#     Q99, Q95, Q72, Q23, Q96.
#   - Thêm Q97, Q98 (NGOAI_PHAM_VI) để mỗi loại hiếm SO_SANH / THU_TUC /
#     NGOAI_PHAM_VI đều có 3 ví dụ; TRA_CUU có 7 ví dụ.
# Muốn tái lập: lọc v3 theo đúng danh sách id dưới đây và đối chiếu nguyên văn
# `raw_query`, `category`, `question_type`.
FEW_SHOT_IDS = (
    "Q02",
    "Q78",
    "Q39",
    "Q44",
    "Q55",
    "Q88",
    "Q90",
    "Q92",
    "Q93",
    "Q99",
    "Q95",
    "Q72",
    "Q23",
    "Q96",
    "Q97",
    "Q98",
)

FEW_SHOT_SAMPLES = (
    (
        "Q02",
        "chương trình đào tạo",
        "SO_SANH",
        "Chuẩn đầu ra ELO 6, ELO 7, ELO 8 và ELO 9 của chương trình đào tạo ngành Công nghệ thông tin quy định như thế nào?",
    ),
    (
        "Q78",
        "cuộc thi chính luận",
        "TRA_CUU",
        "Thời hạn chót nhận bài dự thi Cuộc thi Chính luận năm 2026 cấp Trường là ngày nào?",
    ),
    (
        "Q39",
        "khen thưởng sinh viên",
        "TRA_CUU",
        "Mức tiền thưởng kèm theo Giấy khen của Hiệu trưởng cho danh hiệu 'Sinh viên Xuất sắc' năm học là bao nhiêu?",
    ),
    (
        "Q44",
        "quy chế công tác sinh viên",
        "TRA_CUU",
        "Sinh viên nghỉ học tạm thời vì lý do cá nhân phải hoàn thành tối thiểu bao nhiêu học kỳ tại Trường?",
    ),
    (
        "Q55",
        "sinh viên 5 tốt",
        "THU_TUC",
        "Hồ sơ cá nhân đăng ký danh hiệu 'Sinh viên 5 tốt' bao gồm những tài liệu chứng minh nào?",
    ),
    (
        "Q88",
        "thực tập chuyên đề",
        "THU_TUC",
        "Trường hợp sinh viên tự liên hệ cơ sở thực tập ngoài danh sách liên kết của Trường cần làm thủ tục gì?",
    ),
    (
        "Q90",
        "khen thưởng cấp ĐHQG",
        "TRA_CUU",
        "Mức tiền thưởng cho sinh viên đạt danh hiệu Khen thưởng cấp ĐHQG-HCM do cơ quan nào chi trả?",
    ),
    (
        "Q92",
        "ký túc xá",
        "TRA_CUU",
        "Hành vi sử dụng các thiết bị điện đun nấu trong phòng ở Ký túc xá bị xử lý kỷ luật như thế nào?",
    ),
    (
        "Q93",
        "tài chính sinh viên",
        "THU_TUC",
        "Chương trình tín dụng ưu đãi vay vốn học tập ACB yêu cầu sinh viên cung cấp các tài liệu xác thực nào?",
    ),
    (
        "Q99",
        "bảo hiểm y tế",
        "TRA_CUU",
        "Theo thông báo về Bảo hiểm y tế (BHYT) do Phó Hiệu trưởng Nguyễn Hữu Trí ký, Cố vấn học tập và lớp trưởng các lớp khóa mới (DH27) cần thực hiện công việc gì?",
    ),
    (
        "Q95",
        "hành chính sinh viên",
        "TRA_CUU",
        "Mẫu đơn xác nhận hoàn cảnh gia đình sinh viên khó khăn cần có xác nhận của cơ quan thẩm quyền nào?",
    ),
    (
        "Q72",
        "học phí",
        "SO_SANH",
        "Đơn giá học phí cho 1 tín chỉ thực hành so với tín chỉ lý thuyết được quy định như thế nào?",
    ),
    (
        "Q23",
        "đánh giá rèn luyện",
        "SO_SANH",
        "Tiêu chí xếp loại kết quả rèn luyện học kỳ đối với các mức Xuất sắc, Tốt, Khá, Trung bình, Yếu, Kém được tính theo thang điểm nào?",
    ),
    (
        "Q96",
        "thực tập tốt nghiệp",
        "NGOAI_PHAM_VI",
        "Kế hoạch tổ chức đánh giá Thực tập chuyên đề cấp Khoa do đơn vị nào phê duyệt ban hành?",
    ),
    (
        "Q97",
        "thực tập tốt nghiệp",
        "NGOAI_PHAM_VI",
        "Sinh viên không hoàn thành đủ số giờ thực tập tại doanh nghiệp có được xem xét gia hạn không?",
    ),
    (
        "Q98",
        "thực tập tốt nghiệp",
        "NGOAI_PHAM_VI",
        "Hình thức kỷ luật đối với sinh viên bị phát hiện đạo văn trong báo cáo Khóa luận tốt nghiệp là gì?",
    ),
)

# --- Bảng từ khóa dự phòng (lớp 2) -----------------------------------------
# Thứ tự QUAN TRỌNG: neo đặc thù đứng trước để không bị nuốt bởi từ khóa chung.
# Ví dụ "thực tập chuyên đề" phải xét trước "thực tập"; "đhqg" phải xét trước
# "khen thưởng"; "học phí" phải xét trước "tín chỉ" của CTĐT.
_TOPIC_KEYWORDS_RAW = (
    ("cuộc thi chính luận", ("chính luận",)),
    ("sinh viên 5 tốt", ("sinh viên 5 tốt", "5 tốt", "sao tháng giêng")),
    ("khen thưởng cấp ĐHQG", ("đhqg", "đại học quốc gia")),
    ("bảo hiểm y tế", ("bảo hiểm y tế", "bhyt", "vssid", "vneid")),
    ("ký túc xá", ("ký túc xá", "ktx", "nội trú")),
    (
        "tài chính sinh viên",
        ("vay vốn", "tín dụng ưu đãi", "acb", "lãi suất", "trả nợ gốc"),
    ),
    ("hành chính sinh viên", ("hoàn cảnh khó khăn", "mẫu đơn", "đơn xác nhận")),
    ("thực tập chuyên đề", ("thực tập chuyên đề", "ttcd", "nghiệm thu")),
    (
        "thực tập tốt nghiệp",
        (
            "thực tập tốt nghiệp",
            "tttn",
            "khóa luận tốt nghiệp",
            "kltn",
            "hội đồng chấm",
            "thực tập",
        ),
    ),
    ("đánh giá rèn luyện", ("rèn luyện", "khung điểm")),
    (
        "khen thưởng sinh viên",
        (
            "khen thưởng",
            "danh hiệu thi đua",
            "sinh viên giỏi",
            "sinh viên xuất sắc",
            "lớp sinh viên tiên tiến",
            "giấy khen",
            "mức tiền thưởng",
            "trao tặng",
        ),
    ),
    ("học phí", ("học phí", "miễn giảm", "đơn giá tín chỉ", "gia hạn nộp")),
    (
        "quy chế công tác sinh viên",
        (
            "nghỉ học tạm thời",
            "kỷ luật",
            "nhập học lại",
            "buộc thôi học",
            "cố vấn học tập",
            "nghĩa vụ sinh viên",
            "gian lận thi",
            "thẻ sinh viên",
            "vi phạm quy chế",
        ),
    ),
    (
        "chương trình đào tạo",
        (
            "chương trình đào tạo",
            "ctdt",
            "tín chỉ",
            "môn học",
            "học phần",
            "mã môn",
            "tiên quyết",
            "học trước",
            "elo",
            "chuẩn đầu ra",
            "khối kiến thức",
        ),
    ),
)

TOPIC_KEYWORDS = tuple(
    (topic, tuple(fold(keyword) for keyword in keywords))
    for topic, keywords in _TOPIC_KEYWORDS_RAW
)

# Cùng thứ tự luật phân giải xung đột của TAXONOMY.md: NGOAI_PHAM_VI →
# SO_SANH → THU_TUC → mặc định TRA_CUU.
_QUESTION_TYPE_KEYWORDS_RAW = (
    (
        "NGOAI_PHAM_VI",
        (
            "trường khác",
            "đại học khác",
            "ngoài quy chế",
            "du học",
            "visa",
            "đại sứ quán",
            "tư vấn cá nhân",
            "không có trong quy chế",
        ),
    ),
    (
        "SO_SANH",
        (
            "so sánh",
            "khác nhau",
            "khác gì",
            "đối chiếu",
            "so với",
            "các mức",
            "thang điểm",
            "mức nào",
        ),
    ),
    (
        "THU_TUC",
        (
            "thủ tục",
            "hồ sơ",
            "giấy tờ",
            "tài liệu",
            "cần nộp",
            "nộp ở đâu",
            "các bước",
            "quy trình",
            "làm đơn",
            "cần làm gì",
        ),
    ),
)

QUESTION_TYPE_KEYWORDS = tuple(
    (question_type, tuple(fold(keyword) for keyword in keywords))
    for question_type, keywords in _QUESTION_TYPE_KEYWORDS_RAW
)


def build_few_shot_examples() -> str:
    """Dựng phần few-shot cố định cho prompt phân loại.

    Dữ liệu lấy từ `FEW_SHOT_SAMPLES` (16 câu đã chọn trong benchmark v3, ghi
    cứng trong code kèm id để tái lập). Không đọc file benchmark lúc chạy.

    Mỗi ví dụ có thêm dòng "Dấu hiệu" — thực nghiệm cho thấy Qwen 1.5B bám quy
    tắc phân loại tốt hơn hẳn khi phải nêu dấu hiệu trước khi ra nhãn.
    """
    lines = []
    for _question_id, topic, question_type, raw_query in FEW_SHOT_SAMPLES:
        lines.append(f'Q: "{raw_query}"')
        lines.append(f"Dấu hiệu: {SIGNAL_BY_TYPE[question_type]}")
        lines.append(
            "A: "
            + json.dumps(
                {"topic": topic, "question_type": question_type},
                ensure_ascii=False,
            )
        )
    return "\n".join(lines).strip()


def build_classifier_prompt(query: str) -> str:
    """Dựng prompt đầy đủ (quy tắc + taxonomy + few-shot + câu hỏi cần gán nhãn).

    Quy tắc được nhắc lại NGAY TRƯỚC câu hỏi (recency) vì Qwen 1.5B dễ trôi về
    nhãn TRA_CUU nếu chỉ đọc hướng dẫn ở đầu prompt.
    """
    topic_lines = "\n".join(
        f"- {topic}: {TOPIC_RULES[topic]}" for topic in TOPICS
    )
    type_lines = "\n".join(
        f"{index}. {question_type}: {description}"
        for index, (question_type, description) in enumerate(
            QUESTION_TYPE_RULES, start=1
        )
    )
    safe_query = re.sub(r"\s+", " ", query.replace('"', "'")).strip()
    return (
        "Bạn là bộ phân loại câu hỏi quy chế học vụ Trường Đại học An Giang.\n\n"
        "QUY TẮC CHỌN question_type — xét theo thứ tự, dừng ở điều kiện đầu tiên:\n"
        f"{type_lines}\n"
        "Lưu ý: hỏi nhiều thuộc tính của CÙNG một đối tượng (mã môn + tín chỉ + "
        "học kỳ) là TRA_CUU, không phải SO_SANH.\n\n"
        "QUY TẮC CHỌN topic — chọn đúng 1 trong 14 nhãn:\n"
        f"{topic_lines}\n"
        "Nếu câu hỏi hoàn toàn không thuộc 14 nhóm, topic = null.\n\n"
        "VÍ DỤ:\n"
        f"{build_few_shot_examples()}\n\n"
        'NHẮC LẠI (theo đúng thứ tự ưu tiên): nếu câu hỏi nhắc đến du học, visa, '
        "đại sứ quán, trường khác hoặc không thể trả lời từ quy chế AGU → "
        "NGOAI_PHAM_VI; nếu có \"hồ sơ\", \"giấy tờ\", \"tài liệu\", \"thủ tục\", "
        '"các bước", "nộp" → THU_TUC; nếu hỏi từ 2 đối tượng trở lên hoặc có '
        '"so sánh"/"khác nhau"/"so với" → SO_SANH; còn lại → TRA_CUU.\n\n'
        "Trả lời đúng 2 dòng:\n"
        "Dấu hiệu: <một cụm ngắn nêu dấu hiệu quyết định>\n"
        'A: {"topic": "<chủ đề hoặc null>", "question_type": "<nhãn>"}\n\n'
        f'Câu hỏi: "{safe_query}"\n'
        "Dấu hiệu:"
    )


def extract_json_object(text: str) -> Optional[dict]:
    """Tách đối tượng JSON đầu tiên trong output của model.

    Chịu được markdown fence, lời dẫn thừa và nhiều khối `{...}`. Bộ quét theo
    dõi độ sâu ngoặc và trạng thái chuỗi nên không cắt nhầm dấu `}` nằm trong
    giá trị chuỗi. Trả về None nếu không có khối JSON hợp lệ nào.
    """
    if not text:
        return None

    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : index + 1]
                    try:
                        value = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    return value if isinstance(value, dict) else None
        start = text.find("{", start + 1)
    return None


def _canonical_topic(value: object) -> Optional[str]:
    """Chuẩn hóa topic về đúng 14 chuỗi của TAXONOMY; nhãn lạ trả None."""
    if value is None or not isinstance(value, str):
        return None
    return _TOPIC_BY_FOLDED.get(fold(value).strip())


def _canonical_question_type(value: object) -> Optional[str]:
    """Chuẩn hóa question_type về 4 chuỗi chuẩn; nhãn lạ trả None."""
    if not isinstance(value, str):
        return None
    key = re.sub(r"[\s\-]+", "_", fold(value).strip()).upper()
    return key if key in QUESTION_TYPES else None


def _keyword_topic(folded_query: str) -> Optional[str]:
    """Tìm chủ đề theo bảng từ khóa (đã fold); None nếu không khớp."""
    for topic, keywords in TOPIC_KEYWORDS:
        if any(keyword in folded_query for keyword in keywords):
            return topic
    return None


def _keyword_question_type(folded_query: str) -> str:
    """Tìm loại câu hỏi theo bảng từ khóa; mặc định TRA_CUU (lớp 3)."""
    for question_type, keywords in QUESTION_TYPE_KEYWORDS:
        if any(keyword in folded_query for keyword in keywords):
            return question_type
    return DEFAULT_QUESTION_TYPE


def _classifier_timeout() -> float:
    """Đọc CLASSIFIER_TIMEOUT; giá trị thiếu/sai/không dương đều về mặc định 20s."""
    return settings()._env_float("CLASSIFIER_TIMEOUT", DEFAULT_TIMEOUT, gt=0.0)


def _classifier_model() -> str:
    """CLASSIFIER_MODEL nếu có, ngược lại OLLAMA_MODEL, cuối cùng là Qwen mặc định."""
    cfg = settings()
    return (
        cfg.text("CLASSIFIER_MODEL", "").strip()
        or cfg.text_or("OLLAMA_MODEL", DEFAULT_MODEL)
    )


def classify_query(query: str) -> dict:
    """Gán nhãn chủ đề + loại câu hỏi cho một câu hỏi THÔ.

    Trả về dict đúng 3 khóa:
    - `topic`: 1 trong 14 chuỗi của TAXONOMY.md hoặc None (không xác định).
    - `question_type`: luôn là 1 trong 4 chuỗi chuẩn.
    - `raw_response`: nguyên văn output của Qwen (rỗng nếu không gọi được model).

    Mọi sự cố giao tiếp với Ollama đều suy giảm về lớp 3 (`topic=None`,
    `question_type="TRA_CUU"`) kèm log cảnh báo — không ném lỗi ra pipeline.
    """
    if not isinstance(query, str):
        raise TypeError(f"query phải là str, nhận được {type(query).__name__}.")

    text = query.strip()
    if not text:
        return {
            "topic": None,
            "question_type": DEFAULT_QUESTION_TYPE,
            "raw_response": "",
        }

    try:
        slm = LocalSLM(
            model_name=_classifier_model(),
            timeout=_classifier_timeout(),
            num_predict=DEFAULT_NUM_PREDICT,
            max_retries=0,
        )
        raw_response = slm.generate(build_classifier_prompt(text), temperature=0.0)
    except Exception as exc:
        print(
            "[Classifier] Cảnh báo: không gọi được Qwen "
            f"({type(exc).__name__}: {exc}) — fallback topic=None, question_type=TRA_CUU."
        )
        return {
            "topic": None,
            "question_type": DEFAULT_QUESTION_TYPE,
            "raw_response": "",
        }

    parsed = extract_json_object(raw_response)
    raw_topic = parsed.get("topic") if parsed else None
    raw_question_type = parsed.get("question_type") if parsed else None
    topic = _canonical_topic(raw_topic)
    question_type = _canonical_question_type(raw_question_type)

    if parsed is None:
        print(
            "[Classifier] Cảnh báo: Qwen không trả về JSON hợp lệ — "
            "chuyển sang bảng từ khóa."
        )
    elif (raw_topic is not None and topic is None) or question_type is None:
        # topic=null là hợp lệ (ngoài 14 nhóm); chỉ cảnh báo khi có nhãn sai/thiếu.
        print(
            "[Classifier] Cảnh báo: nhãn Qwen trả về không hợp lệ "
            f"(topic={raw_topic!r}, question_type={raw_question_type!r}) "
            "— bổ sung bằng bảng từ khóa."
        )

    if topic is None or question_type is None:
        folded_query = fold(text)
        if topic is None:
            topic = _keyword_topic(folded_query)
        if question_type is None:
            question_type = _keyword_question_type(folded_query)

    if question_type not in QUESTION_TYPES:
        question_type = DEFAULT_QUESTION_TYPE

    return {
        "topic": topic,
        "question_type": question_type,
        "raw_response": raw_response,
    }
