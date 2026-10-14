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
    python src/evaluation.py                  # đủ 8 câu, top_k=6, có giám khảo
    python src/evaluation.py -k 4             # truy xuất Top-4 (Hit@3/Hit@5 vẫn đo được)
    python src/evaluation.py --limit 2        # chạy thử nhanh 2 câu đầu
    python src/evaluation.py --no-judge       # bỏ tầng giám khảo, tiết kiệm quota
    python src/evaluation.py --judge-model gemini-3.5-flash-lite
        # giám khảo dùng model khác: free tier Gemini giới hạn quota THEO TỪNG MODEL,
        # tách model giám khảo để Generator không bị đụng ngân sách
"""


import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):  # cho phép chạy trực tiếp: python src/evaluation.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

from src.generator import (
    REFUSAL_MARKER,
    RETRYABLE_MARKERS,
    GeneratorError,
    GeminiGenerator,
    QwenGenerator,
    _env_flag,
)
from src.local_slm import LocalSLM
from src.pipeline import HybridRAGPipeline
from src.text_utils import fold
from src.vector_db import VectorStoreManager

BENCHMARK_PATH = Path("data/evaluation/benchmark_50_questions.json")
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


def extract_citations(text: str) -> set[str]:
    """Rút tập trích dẫn từ văn bản (đã bỏ dấu).
    
    Chiến lược đơn giản hóa: chỉ trích xuất tên file từ trích dẫn dạng (Tên_file.pdf)
    hoặc số quyết định/văn bản. Được cả ngoặc đơn (Tên_file.pdf) và ngoặc kép.
    """
    folded = fold(text)
    
    citations: set[str] = set()
    
    # Tìm pattern trích dẫn dạng (Tên_file.pdf) với ngoặc đơn hoặc kép
    file_pattern = re.compile(r"[\'\"\(]([^)\'\"]*\.pdf)[\'\"\)]", re.IGNORECASE)
    for match in file_pattern.finditer(folded):
        filename = match.group(1).strip()
        if filename:
            citations.add(filename)
    
    # Nếu không tìm thấy file, tìm số quyết định (vd: 1504, 1059)
    if not citations:
        decision_pattern = re.compile(r"\b(\d{4})\b")
        for match in decision_pattern.finditer(folded):
            citations.add(match.group(1))
    
    return citations


def _article_of(citation: str) -> str:
    return citation.split(" khoan ", 1)[0]


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
    
    intersection = expected_normalized & predicted_normalized
    true_positive = len(intersection)
    
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
        if REFUSAL_MARKER in fold(answer):
            return 1.0, [], "refusal"  # từ chối = không khẳng định gì, không có gì để phản bội

        context_block = "\n\n".join(f"[Ngữ cảnh {i}] {content}" for i, content in enumerate(contexts, start=1))
        prompt = JUDGE_PROMPT.format(context_block=context_block, answer=answer)

        # Lần 1 dùng JSON mode để máy đọc được; lần 2 (nếu model trả văn thừa) parse mềm.
        for use_json_mode in (True, False):
            config: dict = {"temperature": 0.0, "max_output_tokens": JUDGE_MAX_TOKENS}
            if use_json_mode:
                config["response_mime_type"] = "application/json"
            raw = None
            for attempt in range(JUDGE_MAX_RETRIES + 1):
                try:
                    raw = judge_model.generate_content(prompt, generation_config=config).text
                    break
                except Exception as exc:
                    message = str(exc).lower()
                    if "perday" in message or "resource_exhausted" in message or "429" in message or "quota" in message:
                        return None, [], f"Gemini Judge Quota Exceeded ({type(exc).__name__}) - Bỏ qua chấm điểm Faithfulness"
                    if "404" in message or "not found" in message:
                        return None, [], f"Gemini Judge Model Not Found ({type(exc).__name__}) - Bỏ qua chấm điểm Faithfulness"
                    transient = any(marker in message for marker in RETRYABLE_MARKERS)
                    if not transient or attempt == JUDGE_MAX_RETRIES:
                        return None, [], f"lỗi gọi LLM giám khảo ({type(exc).__name__}: {exc})"
                    wait = 15 * (attempt + 1)
                    print(f"[Judge] Lỗi tạm thời ({type(exc).__name__}), thử lại sau {wait}s — lần {attempt + 1}/{JUDGE_MAX_RETRIES}.")
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
        msg = str(exc).lower()
        if any(marker in msg for marker in ("429", "resource_exhausted", "resourceexhausted", "quota", "perday")):
            return None, [], f"Gemini Judge Quota Exceeded ({type(exc).__name__}) - Bỏ qua chấm điểm Faithfulness"
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
    is_refusal = REFUSAL_MARKER in fold(answer)

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
        "error": None,
    }

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
        "mrr": _mean([e["retrieval"]["reciprocal_rank"] for e in scored]),
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



def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


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
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    top_k = max(1, int(args.top_k))
    retrieve_k = max(top_k, MIN_TOP_K)

    questions = load_benchmark(args.benchmark)
    if args.limit is not None:
        questions = questions[: max(1, args.limit)]
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

    entries: list[dict] = []
    interrupted = False
    generator_desc = "Local Qwen" if args.use_qwen_generator else "Gemini"
    print(f"\nChạy {len(questions)} câu (mỗi câu: chuẩn hóa → truy xuất → {generator_desc} → LLM giám khảo)...\n")
    try:
        for position, question in enumerate(questions, start=1):
            label = question.get("id", f"q{position}")
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
            except Exception as exc:  # hết quota Generator, mất mạng, lỗi model... — bỏ qua câu này, chạy tiếp
                entries.append({
                    "id": label, "category": question.get("category", ""), "raw_query": question["raw_query"],
                    "normalized_query_expected": question.get("normalized_query"), "normalized_query_system": None,
                    "normalization_preservation": None, "retrieval": {}, "answer": None, "is_refusal_answer": None,
                    "citations": None, "predicted_citations": [], "refusal_expected": question.get("in_corpus") is False,
                    "refusal_correct": None, "hallucinated_on_unanswerable": False,
                    "faithfulness": {"score": None, "unsupported_claims": [], "method": None, "error": None},
                    "number_support": None, "latency_seconds": None,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                print(f"[{label}/{len(questions)}] LỖI — bỏ qua: {type(exc).__name__}: {exc}")
                if "perday" in str(exc).lower() and not args.use_qwen_generator:
                    print(f"\n[Quota] Hết quota NGÀY của Generator — {len(questions) - position} câu còn lại sẽ dính lỗi tương tự, dừng sớm để giữ kết quả đã chạy.")
                    break
    except KeyboardInterrupt:
        interrupted = True
        print("\n[Ngắt bởi người dùng] — vẫn ghi kết quả phần đã chạy.")

    aggregates = aggregate(entries, top_k)
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
        "interrupted": interrupted,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"meta": meta, "aggregates": aggregates, "per_question": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = format_summary_md(aggregates, entries, top_k, meta)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")
    print(f"\nĐã lưu chi tiết: {args.output}")
    print(f"Đã lưu tóm tắt : {SUMMARY_PATH}\n")
    print(summary)
    if aggregates["errors"]:
        print("Câu bị lỗi (không tính vào chỉ số):")
        for message in aggregates["errors"]:
            print(f"  - {message}")


if __name__ == "__main__":
    main()
