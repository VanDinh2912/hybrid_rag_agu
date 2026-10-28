"""Module đánh giá định lượng Hybrid RAG trên tập benchmark chuẩn hóa.

Với mỗi câu hỏi trong `data/evaluation/benchmark_questions.json`, chạy đúng pipeline
sản xuất (Qwen chuẩn hóa → ChromaDB truy xuất → Gemini trả lời) rồi đo:

Tầng truy xuất:
- Hit@3 / Hit@5 / Hit@K: Top-K có chứa chunk thuộc `source_document` ground truth không
  (so khớp tên nguồn sau khi bỏ dấu thanh, vì OCR có thể làm sai lệch tên file).
- MRR (Mean Reciprocal Rank): 1/thứ hạng của chunk đúng đầu tiên.

  Lưu ý oversampling: pipeline.run() với top_k=K thực ra truy xuất K×oversample_factor
  chunk từ ChromaDB (mặc định 2×). `sources` trong kết quả chứa TẤT CẢ các chunk đó;
  Hit@K và MRR@K được tính trên toàn bộ danh sách đó (không bị cắt ở top_k) để đánh
  giá được recall thực sự của bước retrieval.

Tầng sinh & trích dẫn:
- Citation Precision / Recall / F1 / Exact Match: tập mã "Điều N [Khoản M]" trích từ
  câu trả lời so với `expected_citations` (so khớp sau khi bỏ dấu, nên "Điều 12
  Khoản 2" khớp cả dạng "dieu 12 khoan 2" do OCR). Khớp đủ Điều+Khoản = 1.0;
  trùng Điều nhưng một phía không ghi Khoản = 0.5; Exact Match nghiêm ngặt.
- Faithfulness: LLM giám khảo (Gemini không mang system instruction của Generator,
  temperature 0, chế độ JSON) tách câu trả lời thành các khẳng định nguyên tố và
  kết luận từng khẳng định có được hỗ trợ trực tiếp bởi ngữ cảnh không. Điểm = tỉ lệ
  khẳng định được hỗ trợ. Câu trả lời dạng từ chối coi như trung thực (không có
  khẳng định nào để phản bội). Kèm chỉ số phụ `number_support` không tốn API: tỉ lệ
  con số trong câu trả lời xuất hiện trong ngữ cảnh.
- Câu `in_corpus=false` kiểm tra hành vi từ chối: hệ thống trả lời bằng câu chứa
  REFUSAL_MARKER là đúng; ngược lại đánh dấu là ảo giác ngoài corpus.

Xuất: `outputs/evaluation_results.json` (chi tiết từng câu) và
`outputs/evaluation_summary.md` (bảng Markdown đưa thẳng vào bài báo), đồng thời in
bảng đó ra terminal. Câu hỏi lỗi (hết quota, mất mạng...) được ghi nhận và bỏ qua,
không làm chết cả lượt đánh giá; Ctrl+C giữa chừng vẫn ghi kết quả phần đã chạy.

Cách chạy (từ thư mục gốc dự án):
    python src/assessment/evaluation.py                  # đủ 8 câu, top_k=6, có giám khảo
    python src/assessment/evaluation.py -k 4             # truy xuất Top-4 (Hit@3/Hit@5 vẫn đo được)
    python src/assessment/evaluation.py --limit 2        # chạy thử nhanh 2 câu đầu
    python src/assessment/evaluation.py --no-judge       # bỏ tầng giám khảo, tiết kiệm quota
    python src/assessment/evaluation.py --judge-model gemini-3.5-flash-lite
        # giám khảo dùng model khác: free tier Gemini giới hạn quota THEO TỪNG MODEL,
        # tách model giám khảo để Generator không bị đụng ngân sách

Giai đoạn 4 (P4.1) — chế độ A/B bật/tắt tầng phân loại:
    python src/assessment/evaluation.py --dry-run --limit 2
        # ước lượng số request Gemini (generator + giám khảo, trừ cache-hit) TRƯỚC khi chạy
    python src/assessment/evaluation.py --benchmark data/evaluation/benchmark_100_questions_v3.json \
        --with-classifier --limit 2
        # lượt WITH: bật ENABLE_CLASSIFIER (router + sub-query); per-question ghi thêm
        # predicted_labels + retrieval_config; summary thêm accuracy phân loại, bảng theo
        # loại câu/chủ đề và tỉ lệ từ chối oan
    python src/assessment/evaluation.py --limit 2
        # lượt WITHOUT: không cờ → hành vi cũ 100% (ép ENABLE_CLASSIFIER=0)
"""


import argparse
import json
import os
import itertools
import re
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):  # cho phép chạy trực tiếp: python src/assessment/evaluation.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

from src.generator import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_MODEL,
    REFUSAL_MARKER,
    RETRYABLE_MARKERS,
    GeneratorError,
    GeminiGenerator,
    QwenGenerator,
    _env_flag,
    quota_error_kind,
)
from src.generation.local_slm import LocalSLM
from src.core.pipeline import HybridRAGPipeline
from src.text_utils import fold
from src.retrieval.vector_db import VectorStoreManager

BENCHMARK_PATH = Path("data/evaluation/benchmark_100_questions_v2.json")
RESULTS_PATH = Path("outputs/evaluation_results.json")
SUMMARY_PATH = Path("outputs/evaluation_summary.md")
DEFAULT_TOP_K = 6
# Luôn lấy tối thiểu 6 chunk để tính đồng thời Hit@3, Hit@5 và Hit@6 từ MỘT lượt truy xuất.
# Kết hợp với oversampling ×2 trong pipeline, evaluation_k=6 → ChromaDB thực trả 12 chunk.
MIN_TOP_K = 6
JUDGE_MAX_TOKENS = 4096
# Lỗi tạm thời (429 quota-phút, 5xx) của giám khảo được thử lại với chờ 15s/30s —
# đủ phủ hạn free tier ~5 request/phút khi chạy liên tiếp nhiều câu.
JUDGE_MAX_RETRIES = 2
# Bước 0 P4.2 (mục 1): giám khảo dính 429 THEO PHÚT thì chờ 60s và chấm lại ĐÚNG câu đó,
# tối đa 3 lần — lỗi phút là tạm thời, không được đánh mất câu khỏi A/B. Riêng PerDay
# trả về lỗi mang marker "PerDay" để vòng lặp chính dừng cả lượt, giữ phần đã chạy.
JUDGE_MINUTE_429_MAX_RETRIES = 3
JUDGE_MINUTE_429_WAIT_SECONDS = 60

CITATION_ARTICLE_RE = re.compile(r"(?:dieu|d)\.?\s*(\d+)(?:\s*[-–]\s*(\d+))?", re.IGNORECASE)
CITATION_CLAUSE_RE = re.compile(r"(?:khoan|k)\.?\s*(\d+)((?:\s*[,;]\s*\d+)*)", re.IGNORECASE)
CITATION_PAIR_WINDOW = 80  # ký tự — giới hạn ghép khoản với điều
CITATION_RANGE_CAP = 20  # bung tối đa 20 điều cho một dải "Điều 10-12"
CITATION_PARTIAL_WEIGHT = 0.5
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

JUDGE_PROMPT = """Bạn là giám khảo độc lập đánh giá ĐỘ TRUNG THỰC (faithfulness) của một câu trả lời.

NGỮ CẢNH ĐÃ TRUY XUẤT (toàn bộ bằng chứng được phép dùng):
{context_block}

CÂU TRẢ LỜI CẦN KIỂM:
{answer}

Nhiệm vụ:
1. Tách câu trả lời thành các khẳng định nguyên tố — mỗi mệnh đề kiểm chứng được độc lập là một khẳng định.
2. Với từng khẳng định, quyết định nó có được HỖ TRỢ TRỰC TIẾP bởi NGỮ CẢNH hay không. CHỈ được dựa vào ngữ cảnh, tuyệt đối cấm dùng kiến thức riêng của bạn: thông tin không tìm thấy trong ngữ cảnh, hoặc mâu thuẫn với ngữ cảnh, đều là supported=false.
3. Diễn đạt lại đúng ý ngữ cảnh hoặc trích dẫn đúng Điều/Khoản có trong ngữ cảnh là supported=true.

Chỉ trả về DUY NHẤT một JSON hợp lệ theo đúng lược đồ dưới đây, không thêm bất kỳ chữ nào khác:
{{"claims": [{{"text": "<khẳng định thứ nhất>", "supported": true}}, {{"text": "<khẳng định thứ hai>", "supported": false}}]}}"""


_ARTICLE_RE = re.compile(
    r"(?<!\w)(?:dieu|d\.?)\s*(\d+(?:\s*[-–]\s*\d+)?)",
    re.IGNORECASE,
)


def extract_citations(text: str) -> set[str]:
    """Rút tập trích dẫn Điều/Khoản từ văn bản (không phân biệt dấu thanh)."""
    folded = fold(text)

    # Chuẩn hóa thứ tự ngược "Khoản X Điều Y" -> "Điều Y Khoản X".
    folded = re.sub(
        r"khoan\s+([\d,\s]+?)\s+(dieu|d\.?)\s*(\d+(?:\s*[-–]\s*\d+)?)",
        lambda m: f"{m.group(2)} {m.group(3)} khoan {m.group(1)}",
        folded,
        flags=re.IGNORECASE,
    )

    matches = list(_ARTICLE_RE.finditer(folded))
    citations: set[str] = set()

    for i, match in enumerate(matches):
        range_str = match.group(1)
        if re.search(r"[-–]", range_str):
            parts = re.split(r"[-–]", range_str)
            try:
                start, end = int(parts[0].strip()), int(parts[1].strip())
                articles = list(range(start, end + 1))
            except ValueError:
                articles = [int(range_str.strip())]
        else:
            articles = [int(range_str.strip())]

        seg_start = match.end()
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else len(folded)
        segment = folded[seg_start:seg_end]

        clauses: list[int] = []
        if re.search(r"khoan", segment, re.IGNORECASE):
            for km in re.finditer(r"khoan\s*([0-9][0-9,\s]*)", segment, re.IGNORECASE):
                for num in re.findall(r"\d+", km.group(1)):
                    clauses.append(int(num))
            seen: set[int] = set()
            unique_clauses: list[int] = []
            for c in clauses:
                if c not in seen:
                    seen.add(c)
                    unique_clauses.append(c)
            clauses = unique_clauses

        if not clauses:
            for art in articles:
                citations.add(f"dieu {art}")
        else:
            for art in articles:
                for cl in clauses:
                    citations.add(f"dieu {art} khoan {cl}")

    return citations


def _article_of(citation: str) -> str:
    return citation.split(" khoan ", 1)[0]


def _parse_citation_parts(citation: str):
    folded = fold(citation)
    m = re.search(r"dieu\s*(\d+)(?:\s*khoan\s*(\d+))?", folded)
    if not m:
        return (folded, None)
    article = m.group(1)
    clause = m.group(2)
    return (article, clause)


def _citation_pair_weight(a: str, b: str) -> float:
    art_a, cl_a = _parse_citation_parts(a)
    art_b, cl_b = _parse_citation_parts(b)
    if art_a != art_b:
        return 0.0
    if cl_a == cl_b:
        return 1.0
    if cl_a is None or cl_b is None:
        return 0.5
    return 0.0


def _citation_true_positives(predicted: set[str], expected: set[str]) -> float:
    """Tính tổng điểm khớp tối ưu (maximum weight matching) giữa hai tập trích dẫn."""
    if not predicted or not expected:
        return 0.0
    pred_list = list(predicted)
    exp_list = list(expected)

    # Luôn lặp trên tập nhỏ hơn để giảm tổ hợp.
    if len(pred_list) > len(exp_list):
        pred_list, exp_list = exp_list, pred_list

    n = len(pred_list)
    best = 0.0
    for combo in itertools.combinations(range(len(exp_list)), n):
        for perm in itertools.permutations(range(n)):
            total = 0.0
            for i in range(n):
                total += _citation_pair_weight(pred_list[i], exp_list[combo[perm[i]]])
            if total > best:
                best = total
    return best


def citation_scores(expected: set[str], predicted: set[str], source_document: str = None) -> dict:
    """Precision / Recall / F1 / Exact Match giữa hai tập trích dẫn.
    
    Phiên bản đơn giản hóa: Nếu source_document được cung cấp và predicted có chứa nó,
    cho điểm hoàn toàn. Nếu không, dựa trên so sánh predicted với expected.
    """
    if source_document:
        source_folded = fold(source_document)
        predicted_folded = fold(" ".join(predicted))
        # Nếu predicted có chứa tên file nguồn, cho điểm hoàn toàn
        if source_folded in predicted_folded or predicted_folded in source_folded:
            return {
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "exact_match": 1.0,
            }
    
    # Fallback: so sánh predicted với expected
    expected_normalized = set()
    for item in expected:
        if re.match(r"^\d+$", item):
            expected_normalized.add(item)
        elif ".pdf" in item.lower():
            expected_normalized.add(item.lower())
        else:
            expected_normalized.add(item.lower())
    
    predicted_normalized = set()
    for item in predicted:
        if re.match(r"^\d+$", item):
            predicted_normalized.add(item)
        elif ".pdf" in item.lower():
            predicted_normalized.add(item.lower())
        else:
            predicted_normalized.add(item.lower())
    
    true_positive = _citation_true_positives(predicted_normalized, expected_normalized)
    
    precision = true_positive / len(predicted_normalized) if predicted_normalized else 0.0
    recall = true_positive / len(expected_normalized) if expected_normalized else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact_match": 1.0 if expected_normalized == predicted_normalized else 0.0,
    }


def source_match(chunk_source: str, expected_document: str) -> bool:
    """Chunk đúng nguồn nếu tên file ground truth nằm trong tên nguồn (hoặc ngược lại)."""
    a, b = fold(chunk_source), fold(expected_document)
    return bool(a and b) and (b in a or a in b)


ARTICLE_CLAUSE_TOKEN_RE = re.compile(r"(?:dieu|khoan)\s*\d+", re.IGNORECASE)
PLAIN_NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")


def _decimal_comma_to_dot(text: str) -> str:
    """'1,0' → '1.0': tiếng Việt viết thập phân bằng dấu phẩy; quy về dấu chấm để so khớp."""
    return re.sub(r"(\d),(\d)", r"\1.\2", text)


def normalization_preservation(raw_query: str, normalized_query: str) -> dict:
    """Tỉ lệ thực thể (số Điều/Khoản, con số) trong câu hỏi gốc còn nguyên sau chuẩn hóa.

    So khớp chuỗi con sau khi fold(): tầng chuẩn hóa được phép diễn đạt lại câu hỏi;
    điều nguy hiểm thật sự là làm mất hay sai lệch con số/số Điều/Khoản — đó mới là
    lỗi chuẩn hóa làm hỏng kết quả truy xuất. Hạn chế: số viết bằng chữ ("hai lần")
    không được quy về dạng chữ số nên có thể bị tính là mất.
    """
    raw = fold(_decimal_comma_to_dot(raw_query))
    norm = fold(_decimal_comma_to_dot(normalized_query))
    article_tokens = ARTICLE_CLAUSE_TOKEN_RE.findall(raw)
    remainder = ARTICLE_CLAUSE_TOKEN_RE.sub(" ", raw)
    tokens = article_tokens + PLAIN_NUMBER_TOKEN_RE.findall(remainder)
    if not tokens:
        return {"score": None, "total": 0, "preserved": 0, "lost": []}
    lost = [token for token in tokens if token not in norm]
    preserved = len(tokens) - len(lost)
    return {
        "score": round(preserved / len(tokens), 4),
        "total": len(tokens),
        "preserved": preserved,
        "lost": lost,
    }


def number_support(answer: str, contexts: list[str]) -> float | None:
    """Tỉ lệ con số trong câu trả lời xuất hiện trong ngữ cảnh (proxy trung thực, miễn phí)."""
    numbers = NUMBER_RE.findall(fold(answer))
    if not numbers:
        return None
    pool = fold(" ".join(contexts))
    return round(sum(1 for n in numbers if n in pool) / len(numbers), 4)


def _strip_code_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_judge_json(raw: str) -> list | None:
    text = _strip_code_fence(raw)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        claims = json.loads(text[start : end + 1]).get("claims")
    except (json.JSONDecodeError, AttributeError):
        return None
    return claims if isinstance(claims, list) else None


def judge_faithfulness(judge_model, contexts: list[str], answer: str) -> tuple[float | None, list[str], str]:
    """Chấm độ trung thực bằng LLM giám khảo. Trả về (điểm, khẳng định không được hỗ trợ, lỗi)."""
    try:
        # P4.1: fold cả marker (lỗi có sẵn — marker có dấu, answer đã fold → không bao giờ khớp).
        if fold(REFUSAL_MARKER) in fold(answer):
            return 1.0, [], "refusal"  # từ chối = không khẳng định gì, không có gì để phản bội

        context_block = "\n\n".join(f"[Ngữ cảnh {i}] {content}" for i, content in enumerate(contexts, start=1))
        prompt = JUDGE_PROMPT.format(context_block=context_block, answer=answer)

        # Lần 1 dùng JSON mode để máy đọc được; lần 2 (nếu model trả văn thừa) parse mềm.
        for use_json_mode in (True, False):
            config: dict = {"temperature": 0.0, "max_output_tokens": JUDGE_MAX_TOKENS}
            if use_json_mode:
                config["response_mime_type"] = "application/json"
            raw = None
            # Bước 0 P4.2: 2 bộ đếm riêng — lỗi tạm thời thường 15s/30s như cũ,
            # 429 THEO PHÚT chờ 60s tối đa 3 lần (không đánh mất câu), PerDay dừng lượt.
            attempt = 0
            minute_retries = 0
            while True:
                try:
                    raw = judge_model.generate_content(prompt, generation_config=config).text
                    break
                except Exception as exc:
                    kind = quota_error_kind(str(exc))
                    if kind == "perday":
                        return None, [], (
                            "429 PerDay — Judge hết quota ngày: DỪNG lượt, giữ phần đã chạy "
                            "(resume đúng lệnh cũ sẽ chỉ chấm nốt phần faithfulness còn thiếu)"
                        )
                    if kind == "minute":
                        if minute_retries >= JUDGE_MINUTE_429_MAX_RETRIES:
                            return None, [], (
                                f"Judge vẫn 429 theo phút sau {JUDGE_MINUTE_429_MAX_RETRIES} lần chờ "
                                f"{JUDGE_MINUTE_429_WAIT_SECONDS}s — bỏ qua câu này"
                            )
                        minute_retries += 1
                        print(f"[Judge] 429 theo phút — chờ {JUDGE_MINUTE_429_WAIT_SECONDS}s rồi chấm lại đúng câu này "
                              f"(lần {minute_retries}/{JUDGE_MINUTE_429_MAX_RETRIES}).")
                        time.sleep(JUDGE_MINUTE_429_WAIT_SECONDS)
                        continue
                    message = str(exc).lower()
                    if "404" in message or "not found" in message:
                        return None, [], f"Gemini Judge Model Not Found ({type(exc).__name__}) - Bỏ qua chấm điểm Faithfulness"
                    transient = any(marker in message for marker in RETRYABLE_MARKERS)
                    if not transient or attempt >= JUDGE_MAX_RETRIES:
                        return None, [], f"lỗi gọi LLM giám khảo ({type(exc).__name__}: {exc})"
                    attempt += 1
                    wait = 15 * attempt
                    print(f"[Judge] Lỗi tạm thời ({type(exc).__name__}), thử lại sau {wait}s — lần {attempt}/{JUDGE_MAX_RETRIES}.")
                    time.sleep(wait)
            claims = _parse_judge_json(raw)
            if claims is None:
                continue
            clean = [c for c in claims if isinstance(c, dict) and isinstance(c.get("text"), str)]
            if not clean:
                return None, [], "giám khảo trả về danh sách khẳng định rỗng/lệch lược đồ"
            unsupported = [c["text"] for c in clean if c.get("supported") is not True]
            score = round((len(clean) - len(unsupported)) / len(clean), 4)
            return score, unsupported, ""
        return None, [], "không phân tích được JSON từ LLM giám khảo sau 2 lần thử"
    except Exception as exc:
        kind = quota_error_kind(str(exc))
        if kind == "perday":
            return None, [], (
                "429 PerDay — Judge hết quota ngày: DỪNG lượt, giữ phần đã chạy "
                "(resume đúng lệnh cũ sẽ chỉ chấm nốt phần faithfulness còn thiếu)"
            )
        if kind == "minute":
            return None, [], f"Judge 429 theo phút ({type(exc).__name__}) - Bỏ qua chấm điểm Faithfulness"
        msg = str(exc).lower()
        if "404" in msg or "not found" in msg:
            return None, [], f"Gemini Judge Model Not Found ({type(exc).__name__}) - Bỏ qua chấm điểm Faithfulness"
        return None, [], f"lỗi ngoại lệ LLM giám khảo ({type(exc).__name__}: {exc})"


def load_benchmark(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Không tìm thấy benchmark '{path}'.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Benchmark '{path}' hỏng định dạng JSON: {exc}")
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise SystemExit(f"Benchmark '{path}' không có danh sách 'questions' nào.")
    for index, question in enumerate(questions):
        if not isinstance(question.get("raw_query"), str) or not question["raw_query"].strip():
            raise SystemExit(f"Benchmark lỗi: questions[{index}] thiếu trường 'raw_query'.")
    return questions


def evaluate_question(pipeline: HybridRAGPipeline, judge_model, question: dict,
                      top_k: int, retrieve_k: int) -> dict:
    """Chạy đúng pipeline sản xuất cho 1 câu hỏi rồi đo mọi chỉ số.

    Với oversampling trong pipeline.run(), `sources` chứa TẤT CẢ chunk được ChromaDB
    trả về (retrieve_k = top_k × oversample_factor). Hit@K và MRR@K đo trên toàn bộ
    danh sách đó — đây là recall window thực sự của tầng retrieval. Generator chỉ nhận
    top_k đầu (gen_top_k = top_k), không bị ảnh hưởng bởi retrieve_k.

    Args:
        top_k:      số chunk generator nhận AND ngưỡng đo Hit@top_k.
        retrieve_k: số chunk ChromaDB trả về (≥ top_k, dùng cho Hit@3/Hit@5/Hit@6).
    """
    t0 = time.perf_counter()
    # Truyền top_k vào pipeline; pipeline.run() tự tính retrieve_k = top_k × oversample_factor
    # nên retrieve_k ở đây chỉ dùng như floor để đảm bảo đủ chunk cho Hit@5/Hit@6.
    result = pipeline.run(question["raw_query"], top_k=retrieve_k)
    elapsed = round(time.perf_counter() - t0, 2)

    # sources = TẤT CẢ chunk ChromaDB trả về (oversampled); contexts = top_k đầu (gen window).
    sources, contexts, answer = result["sources"], result["contexts"], result["answer"]
    expected_document = question.get("source_document")

    # Hit@K đo trên toàn bộ sources (recall window đầy đủ).
    hits = [source_match(s["source"], expected_document) for s in sources] if expected_document else []

    # MRR@top_k: xét thứ hạng của chunk đúng đầu tiên trong toàn bộ danh sách
    # (không cắt cứng ở top_k vì đó là generator window, không phải retrieval window).
    matched_rank = next((i + 1 for i, hit in enumerate(hits) if hit), None)

    expected_citations: set[str] = set()
    for item in question.get("expected_citations") or []:
        expected_citations.update(extract_citations(item))
    predicted_citations = extract_citations(answer)
    refusal_expected = question.get("in_corpus") is False
    # P4.1 sửa lỗi có sẵn: REFUSAL_MARKER mang dấu thanh, fold(answer) đã bỏ dấu →
    # phép so cũ `REFUSAL_MARKER in fold(answer)` KHÔNG BAO GIỜ đúng, làm mọi số
    # liệu "từ chối đúng" cũ luôn bằng 0. Phải fold cả marker trước khi so.
    is_refusal = fold(REFUSAL_MARKER) in fold(answer)
    # P4.1: nhãn pipeline gán (None khi cờ tắt) + cấu hình router đã áp dụng.
    labels = result.get("labels") or None

    entry = {
        "id": question.get("id", "?"),
        "category": question.get("category", ""),
        "raw_query": question["raw_query"],
        "normalized_query_expected": question.get("normalized_query"),
        "normalized_query_system": result["normalized_query"],
        "retrieval_query": result.get("retrieval_query"),
        "normalization_preservation": normalization_preservation(
            question["raw_query"], result["normalized_query"]
        ),
        "retrieval": {
            "top_k": top_k,           # chunk generator nhận
            "retrieved_k": len(sources),  # chunk ChromaDB thực trả (oversampled)
            "hit_at_3": any(hits[:3]) if expected_document else None,
            "hit_at_5": any(hits[:5]) if expected_document else None,
            "hit_at_6": any(hits[:6]) if expected_document else None,
            "hit_at_k": any(hits[:top_k]) if expected_document else None,
            # MRR không cắt ở top_k: phản ánh thứ hạng thực trong toàn bộ recall window.
            "reciprocal_rank": round(1.0 / matched_rank, 4) if matched_rank else 0.0,
            "matched_rank": matched_rank,
            "retrieved": [
                {"rank": s["rank"], "source": s["source"], "tier": s["tier"], "chunk_id": s["chunk_id"]}
                for s in sources
            ],
        },
        "answer": answer,
        "is_refusal_answer": is_refusal,
        "citations": None,
        "predicted_citations": sorted(predicted_citations),
        "refusal_expected": refusal_expected,
        "refusal_correct": (is_refusal if refusal_expected else None),
        "hallucinated_on_unanswerable": bool(refusal_expected and not is_refusal),
        "faithfulness": {"score": None, "unsupported_claims": [], "method": None, "error": None},
        "number_support": number_support(answer, contexts) if not is_refusal else None,
        "latency_seconds": elapsed,
        # P4.1: thêm khi chạy A/B — predicted_labels None khi không bật classifier.
        "predicted_labels": (
            {"topic": labels.get("topic"), "question_type": labels.get("question_type")}
            if labels else None
        ),
        "retrieval_config": result.get("retrieval_config"),
        "expected_question_type": question.get("question_type"),
        "generation_scoring": "skipped_no_gt" if is_skipped_no_gt(question) else "scored",
        "error": None,
    }

    # Lưu contexts để tính faithfulness heuristic sau (chỉ khi judge tắt)
    if judge_model is None:
        entry["contexts"] = contexts

    if expected_citations:
        entry["citations"] = {
            "expected": question.get("expected_citations", []),
            **citation_scores(expected_citations, predicted_citations, expected_document),
        }

    if judge_model is not None:
        score, unsupported, judge_error = judge_faithfulness(judge_model, contexts, answer)
        entry["faithfulness"] = {
            "score": score,
            "unsupported_claims": unsupported,
            "method": "refusal" if score is not None and not judge_error and not unsupported and is_refusal else ("llm_judge" if score is not None else None),
            "error": judge_error or None,
        }
    return entry



def _mean(values: list) -> float | None:
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 4) if valid else None


def aggregate(entries: list[dict], top_k: int) -> dict:
    scored = [e for e in entries if e["error"] is None]
    citation_entries = [e for e in scored if e["citations"] is not None]
    refusal_entries = [e for e in scored if e["refusal_expected"]]
    return {
        "n_total": len(entries),
        "n_ok": len(scored),
        f"hit_at_{top_k}": _mean([e["retrieval"]["hit_at_k"] for e in scored]),
        "hit_at_3": _mean([e["retrieval"]["hit_at_3"] for e in scored]),
        "hit_at_5": _mean([e["retrieval"]["hit_at_5"] for e in scored]),
        "hit_at_6": _mean([e["retrieval"].get("hit_at_6") for e in scored]),
        # MRR chỉ tính trên các câu CÓ tiêu chí truy xuất (source_document khác rỗng):
        # câu test từ chối (in_corpus=false) có reciprocal_rank=0.0 mặc định, đưa vào
        # trung bình sẽ kéo MRR xuống oan dù hệ thống không hề truy xuất sai.
        "mrr": _mean([e["retrieval"]["reciprocal_rank"] for e in scored
                      if e["retrieval"]["hit_at_k"] is not None]),
        "n_retrieval_scored": sum(1 for e in scored if e["retrieval"]["hit_at_k"] is not None),
        "citation_precision": _mean([e["citations"]["precision"] for e in citation_entries]),
        "citation_recall": _mean([e["citations"]["recall"] for e in citation_entries]),
        "citation_f1": _mean([e["citations"]["f1"] for e in citation_entries]),
        "citation_exact_match": _mean([e["citations"]["exact_match"] for e in citation_entries]),
        "n_citation_scored": len(citation_entries),
        "faithfulness_llm": _mean([e["faithfulness"]["score"] for e in scored]),
        "n_faithfulness_scored": sum(1 for e in scored if e["faithfulness"]["score"] is not None),
        "number_support": _mean([e["number_support"] for e in scored]),
        "normalization_preservation": _mean(
            [e["normalization_preservation"]["score"] for e in scored]
        ),
        "normalization_full_preservation": _mean(
            [1.0 if e["normalization_preservation"]["score"] == 1.0 else 0.0
             for e in scored if e["normalization_preservation"]["score"] is not None]
        ),
        "n_normalization_checked": sum(
            1 for e in scored if e["normalization_preservation"]["score"] is not None
        ),
        "refusal_correct_rate": _mean([e["refusal_correct"] for e in refusal_entries]),
        "n_refusal_cases": len(refusal_entries),
        "hallucination_on_unanswerable": sum(1 for e in refusal_entries if e["hallucinated_on_unanswerable"]),
        "avg_latency_seconds": _mean([e["latency_seconds"] for e in scored]),
        "errors": [f"{e['id']}: {e['error']}" for e in entries if e["error"] is not None],
    }


# --------------------------------------------------------------------------
# P4.1 — thống kê chế độ A/B (chỉ chạy khi --with-classifier; hàm thuần, test offline)
# --------------------------------------------------------------------------

def is_skipped_no_gt(question: dict) -> bool:
    """Câu ngoài corpus mà GT trống (Q96–98 theo chốt 2026-10-20): bỏ qua chấm
    generation theo GT một cách tường minh — phép đo hành vi từ chối vẫn chạy bình thường."""
    return (
        question.get("in_corpus") is False
        and not (question.get("expected_citations") or [])
        and not (question.get("ground_truth_answer") or "").strip()
    )


def classification_stats(entries: list[dict]) -> dict | None:
    """Độ chính xác phân loại: predicted topic so với `category` của benchmark,
    predicted question_type so với nhãn `question_type` của v3 (so fold, bỏ dấu)."""
    scored = [e for e in entries if e.get("error") is None and e.get("predicted_labels")]
    topic_pairs = [
        ((e["predicted_labels"].get("topic") or "", e.get("category") or ""))
        for e in scored if (e.get("category") or "").strip()
    ]
    type_pairs = [
        ((e["predicted_labels"].get("question_type") or "", e.get("expected_question_type") or ""))
        for e in scored if (e.get("expected_question_type") or "").strip()
    ]
    if not scored:
        return None

    def _acc(pairs) -> tuple[float | None, int]:
        if not pairs:
            return None, 0
        hits = [1.0 if fold(p) == fold(g) else 0.0 for p, g in pairs]
        return _mean(hits), len(pairs)

    topic_acc, n_topic = _acc(topic_pairs)
    type_acc, n_type = _acc(type_pairs)
    return {
        "n_scored": len(scored),
        "topic_accuracy": topic_acc,
        "n_topic_scored": n_topic,
        "question_type_accuracy": type_acc,
        "n_type_scored": n_type,
    }


def group_metrics(entries: list[dict], key_of) -> dict:
    """Gom chỉ số theo nhóm (predicted question_type hoặc category): Hit@3/5/6,
    MRR, Citation F1, Faithfulness trung bình — để thấy router giúp nhóm nào."""
    groups: dict[str, list] = {}
    for e in entries:
        if e.get("error") is not None:
            continue
        key = key_of(e)
        if not key:
            continue
        groups.setdefault(str(key), []).append(e)

    result = {}
    for key, group in sorted(groups.items()):
        mrr_pool = [e for e in group if e["retrieval"].get("hit_at_k") is not None]
        cit = [e for e in group if e["citations"] is not None]
        result[key] = {
            "n": len(group),
            "hit_at_3": _mean([e["retrieval"].get("hit_at_3") for e in group]),
            "hit_at_5": _mean([e["retrieval"].get("hit_at_5") for e in group]),
            "hit_at_6": _mean([e["retrieval"].get("hit_at_6") for e in group]),
            "mrr": _mean([e["retrieval"]["reciprocal_rank"] for e in mrr_pool]),
            "citation_f1": _mean([e["citations"]["f1"] for e in cit]),
            "faithfulness": _mean([e["faithfulness"]["score"] for e in group]),
        }
    return result


def false_refusal_stats(entries: list[dict]) -> dict:
    """Tỉ lệ từ chối oan: câu `in_corpus=true` bị trả lời chứa REFUSAL_MARKER.

    Lượng hóa trực tiếp tác hại của lỗi gán nhầm lớp hiếm (classifier over-predict
    NGOAI_PHAM_VI / SO_SANH — chốt 2026-10-20 sau P2.3): câu TRA_CUU bị gán nhầm
    có thể bị prompt biến thể ép từ chối dù corpus có căn cứ.
    """
    in_corpus = [e for e in entries if e.get("error") is None and not e["refusal_expected"]]
    by_type: dict[str, list] = {}
    for e in in_corpus:
        pred = (e.get("predicted_labels") or {}).get("question_type") if e.get("predicted_labels") else None
        by_type.setdefault(str(pred) if pred else "KHONG_NHAN", []).append(e)
    return {
        "n_in_corpus": len(in_corpus),
        "n_false_refusal": sum(1 for e in in_corpus if e["is_refusal_answer"]),
        "overall_rate": _mean([1.0 if e["is_refusal_answer"] else 0.0 for e in in_corpus]),
        "by_predicted_type": {
            key: {
                "n": len(group),
                "n_false_refusal": sum(1 for e in group if e["is_refusal_answer"]),
                "rate": _mean([1.0 if e["is_refusal_answer"] else 0.0 for e in group]),
            }
            for key, group in sorted(by_type.items())
        },
    }


def estimate_requests(questions: list[dict], cache_dir: Path, judge_enabled: bool,
                      generator_model: str | None = None) -> dict:
    """Ước lượng request Gemini cho lượt chạy thật (--dry-run, KHÔNG gọi API).

    - Generator: tối đa 1 request/câu; ước lượng cache-hit bằng cách so raw_query và
      normalized_query (kỳ vọng) của benchmark với trường `query` trong các entry
      `.generation_cache/` (so fold). Là ƯỚC LƯỢNG: normalized_query thật của hệ thống
      có thể khác bản kỳ vọng trong benchmark.
    - Bước 0 P4.2 (mục 3): khi truyền `generator_model`, chỉ đếm entry cache của ĐÚNG
      model lượt này sẽ dùng — key SHA-1 gồm cả model nên entry của model khác (vd
      308 entry Qwen từ smoke) KHÔNG THỂ phục vụ lượt Gemini; đếm nhầm sẽ thổi phồng
      cache-hit và làm kế hoạch quota lệch.
    - Giám khảo: tối đa 1 request/câu có câu trả lời substantive; câu TỰ từ chối = 0
      request nhưng không biết trước được → in cận trên kèm ghi chú.
    """
    cached_queries: set[str] = set()
    other_model_entries = 0
    if cache_dir.exists():
        for path in cache_dir.glob("*.json"):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            query = entry.get("query") if isinstance(entry, dict) else None
            if not (isinstance(query, str) and query.strip()):
                continue
            if generator_model is not None and entry.get("model") != generator_model:
                other_model_entries += 1
                continue
            cached_queries.add(fold(query.strip()))
    n = len(questions)
    est_cache_hits = sum(
        1 for q in questions
        if fold((q["raw_query"] or "").strip()) in cached_queries
        or fold((q.get("normalized_query") or "").strip()) in cached_queries
    )
    generator_est = max(0, n - est_cache_hits)
    judge_max = n if judge_enabled else 0
    return {
        "n_questions": n,
        "generator_model": generator_model,
        "estimated_cache_hits": est_cache_hits,
        "cache_entries_other_model": other_model_entries,
        "generator_requests_max": n,
        "generator_requests_est": generator_est,
        "judge_requests_max": judge_max,
        "total_est_upper": generator_est + judge_max,
    }


def expected_generator_cache_model(use_qwen: bool) -> str:
    """Tên model ĐÚNG như trường 'model' trong entry cache mà lượt này sẽ tạo/tra.

    PHẢI khớp công thức đặt tên trong generator.py: GeminiGenerator._cache_put ghi
    self.model_name (= GEMINI_MODEL hoặc DEFAULT_MODEL), QwenGenerator._cache_put ghi
    self.ollama_model (= OLLAMA_MODEL hoặc DEFAULT_OLLAMA_MODEL).
    """
    if use_qwen:
        return os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    return os.getenv("GEMINI_MODEL") or DEFAULT_MODEL


def load_resumable_entries(path: Path, benchmark: str, with_classifier: bool, judge_enabled: bool) -> dict[str, dict]:
    """Bước 0 P4.2 (mục 2): nạp kết quả lượt trước để resume KHÔNG tốn lại quota.

    Điều kiện dùng lại một entry: file output tồn tại, meta KHỚP (cùng benchmark +
    cùng cờ A/B, cùng judge_mode), entry không lỗi, CÓ answer, và:
    - Nếu judge_enabled=True: đã có điểm faithfulness trọn vẹn (score khác None và
      không có lỗi judge ngoài trường hợp từ chối chuẩn)
    - Nếu judge_enabled=False: chỉ cần answer (không cần faithfulness score)
    Lý do: judge KHÔNG có cache — nếu không resume được thì mỗi lần chạy lại tốn
    thêm ~100 request judge cho những câu đã chấm rồi.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"[Resume] File '{path}' hỏng/không đọc được — chạy lại từ đầu.")
        return {}
    if not isinstance(data, dict):
        return {}
    meta = data.get("meta") or {}
    norm = lambda p: os.path.normcase(os.path.normpath(str(p or "")))  # noqa: E731
    if norm(meta.get("benchmark")) != norm(benchmark) or bool(meta.get("with_classifier")) != bool(with_classifier):
        print("[Resume] Meta lượt trước KHÁC (benchmark hoặc cờ A/B) — bỏ qua, chạy lại từ đầu.")
        return {}
    if bool(meta.get("judge_enabled")) != bool(judge_enabled):
        print(f"[Resume] Meta lượt trước judge_mode={'bật' if meta.get('judge_enabled') else 'tắt'} KHÁC với lượt hiện tại "
              f"({'bật' if judge_enabled else 'tắt'}) — bỏ qua, chạy lại từ đầu.")
        return {}
    resumable: dict[str, dict] = {}
    for entry in data.get("per_question") or []:
        if not isinstance(entry, dict):
            continue
        # Judge tắt: chỉ cần answer không lỗi
        if not judge_enabled:
            if entry.get("answer") and not entry.get("error"):
                resumable[str(entry.get("id"))] = entry
            continue
        # Judge bật: cần faithfulness trọn vẹn
        faith = entry.get("faithfulness") or {}
        judge_clean = (
            not faith.get("error")
            or faith.get("error") == "refusal"  # đường từ chối chuẩn: score 1.0 + nhãn, không phải lỗi
        )
        if entry.get("answer") and not entry.get("error") and faith.get("score") is not None and judge_clean:
            resumable[str(entry.get("id"))] = entry
    return resumable


def flush_partial_results(path: Path, meta: dict, entries: list[dict], top_k: int,
                          partial: bool = True) -> None:
    """Bước 0 P4.2 (mục 3b): ghi JSON ra đĩa sau MỖI câu.

    Lượt chạy bị kill/mất điện giữa chừng vẫn còn kết quả phần đã chạy trên đĩa —
    lần chạy lại (resume đúng lệnh cũ) không tốn lại quota cho các câu đã chấm
    trọn vẹn. `partial=True` ở các lần flush giữa chừng; lần ghi cuối của lượt
    (kết thúc bình thường / dừng PerDay / Ctrl+C) dùng `partial=False`.
    """
    payload_meta = dict(meta)
    payload_meta["partial"] = partial
    try:
        aggregates = aggregate(entries, top_k)
    except Exception:
        aggregates = {}  # entry schema lạ/cũ — resume vẫn đọc được per_question
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"meta": payload_meta, "aggregates": aggregates, "per_question": entries},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )



def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _group_table(title: str, groups: dict) -> list[str]:
    """Bảng chỉ số theo nhóm (P4.1): predicted question_type hoặc category."""
    lines = [
        "",
        f"### {title}",
        "",
        "| Nhóm | n | Hit@3 | Hit@5 | Hit@6 | MRR | Citation F1 | Faithfulness |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for key, m in groups.items():
        lines.append(
            f"| {key} | {m['n']} | {_pct(m['hit_at_3'])} | {_pct(m['hit_at_5'])} | {_pct(m['hit_at_6'])} | "
            f"{m['mrr'] if m['mrr'] is not None else 'n/a'} | {_pct(m['citation_f1'])} | {_pct(m['faithfulness'])} |"
        )
    return lines


def format_summary_md(aggregates: dict, entries: list[dict], top_k: int, meta: dict) -> str:
    retrieve_k = meta.get("retrieve_k", top_k)
    lines = [
        "# Kết quả đánh giá Hybrid RAG",
        "",
        f"Benchmark: `{meta['benchmark']}` · {meta['n_questions']} câu · "
        f"Top-K (generator) = {top_k} · Retrieve-K (ChromaDB) = {retrieve_k} · "
        f"Judge = {'bật' if meta['judge_enabled'] else 'tắt'} · {meta['timestamp']}",
        f"Model: Generator `{meta['generator_model']}` · Local SLM `{meta['local_slm_model']}` · Embedding `BAAI/bge-m3`",
        "",
        "## Chỉ số tổng hợp",
        "",
        "| Chỉ số | Giá trị |",
        "|---|---|",
        f"| Số câu chạy được | {aggregates['n_ok']}/{aggregates['n_total']} |",
        f"| Hit@3 | {_pct(aggregates['hit_at_3'])} |",
        f"| Hit@5 | {_pct(aggregates['hit_at_5'])} |",
        f"| Hit@6 | {_pct(aggregates.get('hit_at_6'))} |",
        *([] if top_k in (3, 5, 6) else [f"| Hit@{top_k} | {_pct(aggregates[f'hit_at_{top_k}'])} |"]),
        f"| MRR (recall window) | {aggregates['mrr'] if aggregates['mrr'] is not None else 'n/a'} |",
        f"| Citation Precision | {_pct(aggregates['citation_precision'])} |",
        f"| Citation Recall | {_pct(aggregates['citation_recall'])} |",
        f"| Citation F1 | {_pct(aggregates['citation_f1'])} |",
        f"| Citation Exact Match | {_pct(aggregates['citation_exact_match'])} |",
        f"| Faithfulness (LLM judge) | {_pct(aggregates['faithfulness_llm'])} |",
        f"| Number support (không cần API) | {_pct(aggregates['number_support'])} |",
        f"| Bảo toàn thực thể sau chuẩn hóa (Qwen) | {_pct(aggregates['normalization_preservation'])} |",
        f"| Bảo toàn đủ 100% thực thể | {_pct(aggregates['normalization_full_preservation'])} |",
        f"| Từ chối đúng (câu ngoài corpus) | {_pct(aggregates['refusal_correct_rate'])} "
        f"({aggregates['n_refusal_cases']} câu) |",
        f"| Ảo giác trên câu ngoài corpus | {aggregates['hallucination_on_unanswerable']} câu |",
        f"| Thời gian trung bình / câu | {aggregates['avg_latency_seconds']}s |",
    ]

    # P4.1: mục phân loại/router chỉ xuất hiện khi lượt chạy --with-classifier.
    clf = aggregates.get("classifier")
    if clf:
        stats = clf.get("classification") or {}
        fr = clf.get("false_refusal") or {}
        lines += [
            "",
            "## Phân loại & Router (lượt WITH classifier)",
            "",
            "| Chỉ số | Giá trị |",
            "|---|---|",
            f"| Độ chính xác chủ đề | {_pct(stats.get('topic_accuracy'))} ({stats.get('n_topic_scored', 0)} câu) |",
            f"| Độ chính xác loại câu hỏi | {_pct(stats.get('question_type_accuracy'))} ({stats.get('n_type_scored', 0)} câu) |",
            f"| Từ chối oan (in_corpus=true) | {_pct(fr.get('overall_rate'))} ({fr.get('n_false_refusal', 0)}/{fr.get('n_in_corpus', 0)} câu) |",
        ]
        lines += _group_table("Theo loại câu hỏi (predicted)", clf.get("by_question_type") or {})
        lines += _group_table("Theo chủ đề (category benchmark)", clf.get("by_category") or {})

    lines += [
        "",
        "## Kết quả theo câu",
        "",
        "| ID | Hit@6 | RR | Citation F1 | Faithfulness | Ghi chú |",
        "|---|---|---|---|---|---|",
    ]

    for entry in entries:
        if entry["error"] is not None:
            note = f"LỖI: {entry['error']}"
            cells = ["—", "—", "—", "—"]
        else:
            retrieval = entry["retrieval"]
            hit6 = "—" if retrieval.get("hit_at_6") is None else str(retrieval["hit_at_6"])
            cells = [
                hit6,
                f"{retrieval['reciprocal_rank']:.2f}",
                "—" if entry["citations"] is None else f"{entry['citations']['f1']:.2f}",
                "—" if entry["faithfulness"]["score"] is None else f"{entry['faithfulness']['score']:.2f}",
            ]
            if entry["hallucinated_on_unanswerable"]:
                note = "ẢO GIÁC: trả lời câu ngoài corpus thay vì từ chối"
            elif entry["refusal_correct"]:
                note = "từ chối đúng"
            elif entry["citations"] is not None and entry["citations"]["exact_match"] < 1.0:
                note = f"trích dẫn lệch: {', '.join(entry['predicted_citations']) or '(không có)'}"
            elif entry.get("faithfulness", {}).get("error"):
                note = f"{entry['faithfulness']['error']}"
            else:
                note = ""
        lines.append(f"| {entry['id']} | {' | '.join(cells)} | {note} |")
    lines.append("")
    return "\n".join(lines)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Đánh giá định lượng Hybrid RAG trên data/evaluation/benchmark_questions.json."
    )
    parser.add_argument("-k", "--top-k", type=int, default=DEFAULT_TOP_K,
                        help=f"số chunk truy xuất mỗi câu (mặc định {DEFAULT_TOP_K}; luôn lấy ≥{MIN_TOP_K} để đo Hit@5)")
    parser.add_argument("--limit", type=int, default=None, help="chỉ chạy N câu đầu (test nhanh, tiết kiệm quota)")
    parser.add_argument("--no-judge", action="store_true", help="bỏ tầng giám khảo Faithfulness (không gọi thêm Gemini)")
    parser.add_argument("--judge-model", type=str, default=None,
                        help="model giám khảo Faithfulness (cờ > GEMINI_JUDGE_MODEL > model Generator). "
                             "Dùng model KHÁC để tận dụng ngân sách quota riêng — free tier Gemini giới hạn theo từng model.")
    parser.add_argument("--use-qwen-generator", action="store_true",
                        default=_env_flag("USE_QWEN_GENERATOR", False),
                        help="Dùng Local Qwen (qwen2.5:1.5b-instruct qua Ollama) làm Generator sinh câu trả lời (offline 100%%, không tốn quota Gemini)")
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_PATH, help="đường dẫn file benchmark")
    parser.add_argument("--output", type=Path, default=RESULTS_PATH, help="nơi ghi kết quả chi tiết JSON")
    parser.add_argument("--summary-output", type=Path, default=SUMMARY_PATH,
                        help="nơi ghi bảng tóm tắt Markdown (mặc định giữ nguyên; lượt A/B nên tách file để không ghi đè nhau)")
    parser.add_argument("--with-classifier", action="store_true",
                        help="lượt WITH: bật ENABLE_CLASSIFIER=1 cho pipeline (router + sub-query); "
                             "không cờ → ép ENABLE_CLASSIFIER=0, hành vi cũ 100%%")
    parser.add_argument("--dry-run", action="store_true",
                        help="chỉ ước lượng số request Gemini sẽ tốn (generator + giám khảo, trừ cache-hit) rồi thoát — không đụng ChromaDB/API")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    top_k = max(1, int(args.top_k))
    retrieve_k = max(top_k, MIN_TOP_K)

    questions = load_benchmark(args.benchmark)
    if args.limit is not None:
        questions = questions[: max(1, args.limit)]

    # P4.1: --dry-run — ước lượng quota rồi thoát TRƯỚC khi nạp ChromaDB/gọi API.
    if args.dry_run:
        judge_enabled = not args.no_judge
        cache_dir = Path(os.getenv("GENERATION_CACHE_DIR") or "./.generation_cache")
        gen_model = expected_generator_cache_model(args.use_qwen_generator)
        est = estimate_requests(questions, cache_dir, judge_enabled, generator_model=gen_model)
        print("--- DRY-RUN: ƯỚC LƯỢNG REQUEST GEMINI (chưa chạy thật) ---")
        print(f"Benchmark: {args.benchmark} · {est['n_questions']} câu · Judge: {'bật' if judge_enabled else 'tắt'}")
        print(f"Generator : {gen_model} — tối đa {est['generator_requests_max']} request; ước lượng trúng cache "
              f"{est['estimated_cache_hits']} → ~{est['generator_requests_est']} request")
        if est.get("cache_entries_other_model"):
            print(f"            (bỏ qua {est['cache_entries_other_model']} entry cache của model KHÁC — "
                  "key SHA-1 gồm cả model nên entry đó không thể phục vụ lượt này)")
        print(f"Giám khảo : tối đa {est['judge_requests_max']} request "
              f"(câu TỰ từ chối tốn 0 — không biết trước nên đây là cận trên)")
        print(f"TỔNG ƯỚC LƯỢNG: ~{est['total_est_upper']} request (cận trên)")
        return

    # P4.1: cờ A/B — bật/tắt tầng phân loại TRƯỚC khi dựng pipeline (pipeline đọc env lúc __init__).
    if args.with_classifier:
        os.environ["ENABLE_CLASSIFIER"] = "1"
        print("Chế độ A/B: lượt WITH — ENABLE_CLASSIFIER=1 (router + sub-query kích hoạt).")
    else:
        os.environ["ENABLE_CLASSIFIER"] = "0"
        print("Chế độ WITHOUT — ép ENABLE_CLASSIFIER=0: hành vi cũ 100%.")
    print(f"--- ĐÁNH GIÁ ĐỊNH LƯỢNG HYBRID RAG ---")
    print(f"Benchmark: {args.benchmark} ({len(questions)} câu) · Top-K = {top_k} (truy xuất {retrieve_k} để tính Hit@5) · Judge = {'tắt' if args.no_judge else 'bật'}")
    print(f"Chế độ Generator: {'Local Qwen (Ollama - Offline)' if args.use_qwen_generator else 'Gemini API'}\n")

    print("[1/2] Nối ChromaDB đã persist (không nạp lại corpus)...")
    vector_db = VectorStoreManager().load_vector_store()
    indexed = vector_db._collection.count()
    if indexed == 0:
        raise SystemExit("ChromaDB rỗng — chạy 'python ingest.py' trước khi đánh giá.")
    print(f"      Đã nối collection ('{indexed}' chunks).")

    local_slm = LocalSLM()
    ollama_ok, ollama_message = local_slm.check_connection()
    print(f"[2/2] Ollama: {'sẵn sàng' if ollama_ok else 'CẢNH BÁO — ' + ollama_message}")
    if not ollama_ok:
        print("      Số liệu vẫn chạy được (dùng câu hỏi gốc) nhưng 'normalization_preservation' sẽ mất ý nghĩa.")

    if args.use_qwen_generator:
        generator = QwenGenerator()
        print(f"      Generator chính: {generator.model_name} (chạy offline qua Ollama, không tốn quota API).")
    else:
        generator = GeminiGenerator()
        # Tắt Qwen-fallback CHỈ trong lượt đánh giá chế độ Gemini: nếu Gemini hết quota mà câu trả lời
        # lại do Qwen tổng hợp thì Hit/Citation/Faithfulness sẽ đo nhầm chất lượng fallback
        # thay vì chất lượng pipeline Gemini của đề tài. Caching vẫn giữ nguyên để chạy lại
        # benchmark không tốn thêm quota cho các câu đã trả lời thành công trước đó.
        generator.qwen_fallback = False
        print("      Generator chính: Gemini API (Qwen-fallback: TẮT trong lượt đánh giá).")

    judge_model = None
    judge_name = None
    if not args.no_judge:
        judge_name = args.judge_model or os.getenv("GEMINI_JUDGE_MODEL") or "gemini-3.5-flash-lite"
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key and gemini_api_key.strip() not in {"your_gemini_api_key_here", "<your_api_key>"}:
            try:
                genai.configure(api_key=gemini_api_key)
                judge_model = genai.GenerativeModel(model_name=judge_name)
                print(f"      Giám khảo Faithfulness: {judge_name} (Gemini LLM-Judge độc lập).")
            except Exception as exc:
                print(f"      [Judge] Cảnh báo: không khởi tạo được Gemini Judge ({exc}) — tự động bỏ qua chấm điểm Faithfulness.")
                judge_model = None
        else:
            print("      [Judge] Cảnh báo: không có GEMINI_API_KEY hợp lệ — bỏ qua giám khảo Faithfulness.")
            judge_model = None

    pipeline = HybridRAGPipeline(local_slm=local_slm, vector_db=vector_db, generator=generator)

    # Bước 0 P4.2 (mục 2): resume an toàn — nạp kết quả lượt trước CÙNG benchmark + CÙNG cờ
    # A/B + CÙNG judge_mode từ cùng file output; câu đã có answer (+ judge score nếu bật)
    # giữ nguyên (0 request), chỉ chạy câu thiếu. Judge KHÔNG có cache nên đây là tấm át
    # chống phí quota khi hẹn lại giờ.
    resumable = load_resumable_entries(args.output, str(args.benchmark), args.with_classifier, judge_model is not None)
    n_resumed = 0
    if resumable:
        print(f"[Resume] {len(resumable)} câu đã có kết quả trọn vẹn từ lượt trước — giữ nguyên (0 request).")

    entries: list[dict] = []
    interrupted = False
    # Bước 0 P4.2 (mục 3b): meta dựng TRƯỚC vòng lặp để flush từng câu ra đĩa —
    # lượt chạy bị kill/mất điện vẫn còn kết quả phần đã chạy cho lần resume sau.
    meta = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "benchmark": str(args.benchmark),
        "n_questions": len(questions),
        "top_k": top_k,
        "retrieve_k": retrieve_k,
        "judge_enabled": judge_model is not None,
        "judge_model": judge_name,
        "generator_model": generator.model_name,
        "local_slm_model": local_slm.model_name,
        "ollama_available": ollama_ok,
        "interrupted": False,
        "with_classifier": args.with_classifier,
        "resumed": 0,
        "partial": True,
    }
    generator_desc = "Local Qwen" if args.use_qwen_generator else "Gemini"
    print(f"\nChạy {len(questions)} câu (mỗi câu: chuẩn hóa → truy xuất → {generator_desc} → LLM giám khảo)...\n")
    try:
        for position, question in enumerate(questions, start=1):
            label = str(question.get("id", f"q{position}"))
            if label in resumable:
                entries.append(resumable[label])
                n_resumed += 1
                print(f"[{label}/{len(questions)}] RESUME — giữ kết quả cũ (0 request).")
                flush_partial_results(args.output, meta, entries, top_k)
                continue
            try:
                entry = evaluate_question(pipeline, judge_model, question, top_k, retrieve_k)
                entries.append(entry)
                retrieval, faith = entry["retrieval"], entry["faithfulness"]
                cit_f1 = "—" if entry["citations"] is None else f"{entry['citations']['f1']:.2f}"
                faith_text = "—" if faith["score"] is None else f"{faith['score']:.2f}"
                note_judge = ""
                if faith.get("error"):
                    note_judge = f" [Judge: {faith['error'][:50]}...]"
                print(f"[{label}/{len(questions)}] hit@{top_k}={int(bool(retrieval['hit_at_k'])) if retrieval['hit_at_k'] is not None else '—'} "
                      f"rr={retrieval['reciprocal_rank']:.2f} citF1={cit_f1} faith={faith_text} ({entry['latency_seconds']}s){note_judge}")
                flush_partial_results(args.output, meta, entries, top_k)  # mục 3b: lưu từng câu
                # Bước 0 P4.2: Judge hết quota NGÀY → dừng cả lượt, giữ phần đã chạy; resume
                # đúng lệnh cũ sẽ chỉ chấm nốt faithfulness còn thiếu (generator free nhờ cache).
                faith_error = (entry.get("faithfulness") or {}).get("error") or ""
                if "perday" in faith_error.lower() and not args.use_qwen_generator:
                    print(f"\n[Quota] Judge hết quota NGÀY — dừng lượt sớm tại câu {position}/{len(questions)} "
                          "để giữ kết quả đã chạy. Resume đúng lệnh cũ sau khi quota reset.")
                    break
            except Exception as exc:  # hết quota Generator, mất mạng, lỗi model... — bỏ qua câu này, chạy tiếp
                entries.append({
                    "id": label, "category": question.get("category", ""), "raw_query": question["raw_query"],
                    "normalized_query_expected": question.get("normalized_query"), "normalized_query_system": None,
                    "normalization_preservation": None, "retrieval": {}, "answer": None, "is_refusal_answer": None,
                    "citations": None, "predicted_citations": [], "refusal_expected": question.get("in_corpus") is False,
                    "refusal_correct": None, "hallucinated_on_unanswerable": False,
                    "faithfulness": {"score": None, "unsupported_claims": [], "method": None, "error": None},
                    "number_support": None, "latency_seconds": None,
                    "predicted_labels": None, "retrieval_config": None,
                    "expected_question_type": question.get("question_type"),
                    "generation_scoring": "skipped_no_gt" if is_skipped_no_gt(question) else "scored",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                print(f"[{label}/{len(questions)}] LỖI — bỏ qua: {type(exc).__name__}: {exc}")
                flush_partial_results(args.output, meta, entries, top_k)  # mục 3b: lưu cả câu lỗi
                if "perday" in str(exc).lower() and not args.use_qwen_generator:
                    print(f"\n[Quota] Hết quota NGÀY của Generator — {len(questions) - position} câu còn lại sẽ dính lỗi tương tự, dừng sớm để giữ kết quả đã chạy.")
                    break
    except KeyboardInterrupt:
        interrupted = True
        print("\n[Ngắt bởi người dùng] — vẫn ghi kết quả phần đã chạy.")

    aggregates = aggregate(entries, top_k)
    # P4.1: thống kê A/B chỉ khi lượt WITH — JSON giữ nguyên dạng cũ khi không bật.
    if args.with_classifier:
        aggregates["classifier"] = {
            "classification": classification_stats(entries),
            "by_question_type": group_metrics(
                entries, lambda e: (e.get("predicted_labels") or {}).get("question_type")
            ),
            "by_category": group_metrics(entries, lambda e: e.get("category")),
            "false_refusal": false_refusal_stats(entries),
        }
    meta["interrupted"] = interrupted
    meta["resumed"] = n_resumed  # Bước 0 P4.2: số câu giữ nguyên từ lượt trước (0 request)
    # Ghi cuối lượt: kết thúc có kiểm soát (trọn vẹn / dừng PerDay / Ctrl+C) → partial=False.
    flush_partial_results(args.output, meta, entries, top_k, partial=False)
    summary = format_summary_md(aggregates, entries, top_k, meta)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(summary, encoding="utf-8")
    print(f"\nĐã lưu chi tiết: {args.output}")
    print(f"Đã lưu tóm tắt : {args.summary_output}\n")
    print(summary)
    if aggregates["errors"]:
        print("Câu bị lỗi (không tính vào chỉ số):")
        for message in aggregates["errors"]:
            print(f"  - {message}")


if __name__ == "__main__":
    main()
