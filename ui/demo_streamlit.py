"""Demo Streamlit — so sánh thực nghiệm 3 chiến lược phân đoạn tài liệu (chunking).

App CHỈ là lớp trình bày: toàn bộ chunking / truy xuất hybrid / sinh chữ / chấm điểm
được TÁI SỬ DỤNG từ `src/` (chunking, loader, vector_db, pipeline, local_slm,
generator, evaluation) — KHÔNG cài lại bất kỳ logic backend nào.

Ba chiến lược so sánh (đúng hiện trạng repo):
    CS1 "fixed"      — Fixed-size: cắt cứng 512 token, overlap 0.
    CS2 "recursive"  — Recursive: cắt đệ quy "\\n\\n" → "\\n" → câu → từ, 512 token.
    CS3 "structure"  — Structure-aware: cắt theo Điều/Khoản/Điểm, tiền tố metadata
                       phân cấp ở đầu chunk, khóa nguyên khối bảng Markdown
                       (chunking mặc định đã lock_markdown_tables=True cho cả 3).

Cài đặt thêm (chưa có trong ./venv):
    pip install streamlit pandas

Chạy (từ thư mục gốc repo — bắt buộc kèm flag watcher để app không chết im khi
file watcher của Streamlit quét thư viện lớn):
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m streamlit run ui/demo_streamlit.py --server.fileWatcherType none

Nguồn dữ liệu index (theo thứ tự ưu tiên cho từng chiến lược):
    1. logs/benchmark/chroma_<strategy>/     — sản phẩm của benchmark_chunking.py (vị trí mới)
    2. benchmark_logs/chroma_<strategy>/     — vị trí cũ (nếu còn từ lượt benchmark trước)
    3. logs/demo_chroma_<strategy>/          — tự dựng mới từ data/corpus (OCR đã cache)
Dữ liệu replay đọc từ logs/benchmark/results_all.json (hoặc benchmark_logs/ cũ).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

if __package__ in (None, ""):  # cho phép chạy trực tiếp `streamlit run ui/demo_streamlit.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()  # nạp .env (GEMINI_API_KEY, OLLAMA_*, ...) TRƯỚC khi backend đọc biến môi trường

import pandas as pd
import streamlit as st

from src.chunking import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    chunk_with_strategy,
    get_token_counter,
)
from src.evaluation import (
    REFUSAL_MARKER,
    citation_scores,
    extract_citations,
    judge_faithfulness,
    load_benchmark,
    number_support,
    source_match,
)
from src.generator import GeminiGenerator, QwenGenerator
from src.loader import DocumentLoader
from src.local_slm import LocalSLM
from src.pipeline import HybridRAGPipeline
from src.text_utils import fold
from src.vector_db import VectorStoreManager

# --------------------------------------------------------------------------- hằng số

BENCHMARK_PATH = Path("data/evaluation/benchmark_50_questions.json")
LOGS_DIR = Path("logs")
LOGS_BENCHMARK_DIR = LOGS_DIR / "benchmark"
LEGACY_BENCHMARK_DIR = Path("benchmark_logs")
COLLECTION_PREFIX = "bench"  # trùng COLLECTION_PREFIX của benchmark_chunking.py

GENERATOR_QWEN = "Qwen local (offline, không tốn quota)"
GENERATOR_GEMINI = "Gemini API"
JUDGE_MODEL_NAME = os.getenv("GEMINI_JUDGE_MODEL", "gemini-3.5-flash-lite")

# Thứ tự dict = thứ tự hiển thị và thứ tự chạy trong app.
STRATEGIES: dict[str, dict[str, str]] = {
    "fixed": {
        "short": "Fixed-size",
        "label": "CS1 · Fixed-size — cắt cứng 512 token, overlap 0",
    },
    "recursive": {
        "short": "Recursive",
        "label": "CS2 · Recursive — cắt đệ quy theo cấp bậc, 512 token",
    },
    "structure": {
        "short": "Structure-aware",
        "label": "CS3 · Structure-aware — Điều/Khoản/Điểm + metadata phân cấp",
    },
}

DEFAULT_WEIGHTS: tuple[float, float, float] = (0.4, 0.3, 0.3)


# --------------------------------------------------------------------------- tài nguyên nặng (@st.cache_resource)


@st.cache_resource(show_spinner="Đang nạp tokenizer HuggingFace (BAAI/bge-m3)...")
def get_tokenizer() -> Any:
    """Tokenizer đếm token dùng chung cho 3 chiến lược (đã cache sẵn trên đĩa)."""
    return get_token_counter("BAAI/bge-m3")


@st.cache_resource(show_spinner="Đang nạp corpus từ data/corpus (OCR đã cache)...")
def get_corpus() -> tuple[dict[str, Any], ...]:
    """Nạp corpus MỘT lần duy nhất: list[{title, content, tier}] từ DocumentLoader."""
    loader = DocumentLoader(data_dir="./data/corpus")
    documents = loader.load_documents()
    return tuple(documents)


@st.cache_resource(show_spinner="Đang kết nối Local SLM (Ollama)...")
def get_local_slm() -> LocalSLM:
    """LocalSLM chuẩn hóa câu hỏi — dùng chung cho mọi chiến lược."""
    return LocalSLM()


@st.cache_resource(show_spinner=False)
def get_generator(generator_label: str) -> tuple[Any, str | None]:
    """Dựng generator theo lựa chọn sidebar; trả về (generator | None, thông báo lỗi).

    Với Gemini bắt buộc tắt qwen_fallback: nếu Gemini hết quota mà câu trả lời âm thầm
    do Qwen tổng hợp thì 3 chiến lược sẽ bị so sánh trên 2 model khác nhau — sai thực nghiệm.
    """
    try:
        if generator_label == GENERATOR_GEMINI:
            generator = GeminiGenerator(temperature=0.0)
            generator.qwen_fallback = False
            return generator, None
        return QwenGenerator(temperature=0.0), None
    except Exception as exc:  # ví dụ GeneratorError khi thiếu GEMINI_API_KEY
        return None, f"{type(exc).__name__}: {exc}"


@st.cache_resource(show_spinner=False)
def get_judge_model() -> tuple[Any, str | None]:
    """Dựng LLM Judge ĐỘC LẬP (không dùng generator chính) cho tầng giám khảo Faithfulness.

    Trả về raw `google.generativeai.GenerativeModel` đúng kiểu `judge_faithfulness`
    trong src/evaluation.py mong đợi (object có .generate_content).
    """
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key or api_key in {"your_gemini_api_key_here", "<your_api_key>"}:
        return None, "Chưa cấu hình GEMINI_API_KEY hợp lệ trong .env — không bật được LLM Judge."
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name=JUDGE_MODEL_NAME), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


class DemoIndexRegistry:
    """Quản lý 3 ChromaDB index — mỗi chiến lược một chỉ mục vật lý độc lập.

    VectorStoreManager nạp bge-m3 ĐÚNG MỘT lần và được tái dùng cho cả 3 chiến lược
    bằng cách trỏ `persist_directory` sang thư mục riêng trước mỗi lệnh tạo/nạp
    (cùng cách benchmark_chunking.py đảm bảo so sánh công bằng).
    """

    def __init__(self) -> None:
        self._manager: VectorStoreManager | None = None
        self._stores: dict[str, tuple[Any, int, str]] = {}

    def _manager_or_load(self) -> VectorStoreManager:
        if self._manager is None:
            self._manager = VectorStoreManager()  # moment nặng duy nhất: nạp bge-m3 lên CPU
        return self._manager

    def get_store(self, strategy: str) -> tuple[Any, int, str]:
        """Trả về (vector_db, số_chunk, nguồn_index) của một chiến lược.

        Thứ tự: index có sẵn của benchmark (vị trí mới rồi cũ) → dựng mới vào
        logs/demo_chroma_<strategy>/ từ corpus. Kết quả giữ trong bộ nhớ phiên.
        """
        if strategy in self._stores:
            return self._stores[strategy]

        collection = f"{COLLECTION_PREFIX}_{strategy}"
        manager = self._manager_or_load()

        # 1) Tải index có sẵn theo thứ tự ưu tiên:
        #    a) logs/benchmark/chroma_<strategy>/   — sản phẩm của benchmark_chunking.py
        #    b) benchmark_logs/chroma_<strategy>/   — vị trí cũ của benchmark
        #    c) logs/demo_chroma_<strategy>/        — index demo app đã dựng ở lượt chạy trước
        candidates = [
            LOGS_BENCHMARK_DIR / f"chroma_{strategy}",
            LEGACY_BENCHMARK_DIR / f"chroma_{strategy}",
            LOGS_DIR / f"demo_chroma_{strategy}",
        ]
        for candidate in candidates:
            if (candidate / "chroma.sqlite3").exists():
                manager.persist_directory = str(candidate)
                vector_db = manager.load_vector_store(collection_name=collection)
                n_chunks = int(vector_db._collection.count())
                if n_chunks == 0:
                    raise RuntimeError(f"Index '{candidate}' tồn tại nhưng collection rỗng.")
                self._stores[strategy] = (vector_db, n_chunks, f"tải sẵn từ {candidate}")
                return self._stores[strategy]

        # 2) Dựng mới từ corpus (OCR đã cache nên chỉ tốn thời gian nhúng embedding)
        documents = get_corpus()
        if not documents:
            raise RuntimeError("Corpus rỗng — không dựng được index demo.")
        counter = get_tokenizer()
        chunks: list[dict[str, str]] = []
        for doc in documents:
            texts = chunk_with_strategy(
                strategy,
                doc["content"],
                doc_title=doc["title"],
                max_tokens=DEFAULT_MAX_TOKENS,
                overlap_tokens=DEFAULT_OVERLAP_TOKENS,
                token_counter=counter,
                # lock_markdown_tables mặc định True: cả 3 chiến lược đều khóa bảng Markdown
            )
            for text in texts:
                if text and text.strip():
                    chunks.append({"text": text, "tier": doc["tier"], "source": doc["title"]})
        if not chunks:
            raise RuntimeError(f"Chiến lược '{strategy}' sinh 0 chunk từ corpus.")

        target = LOGS_DIR / f"demo_chroma_{strategy}"
        manager.persist_directory = str(target)
        vector_db = manager.create_vector_store(chunks, collection_name=collection)
        n_chunks = int(vector_db._collection.count())
        self._stores[strategy] = (vector_db, n_chunks, f"dựng mới {len(chunks)} chunk tại {target}")
        return self._stores[strategy]


@st.cache_resource(show_spinner=False)
def get_index_registry() -> DemoIndexRegistry:
    """Registry 3 index được cache như một resource — giữ bge-m3 + 3 store trong bộ nhớ."""
    return DemoIndexRegistry()


# --------------------------------------------------------------------------- dữ liệu nhẹ (@st.cache_data)


@st.cache_data(show_spinner=False)
def load_benchmark_questions() -> tuple[list[dict[str, Any]], str | None]:
    """Đọc testbed benchmark (JSON, utf-8). Trả về (danh sách câu hỏi, thông báo lỗi)."""
    if not BENCHMARK_PATH.exists():
        return [], f"Không tìm thấy {BENCHMARK_PATH}"
    try:
        return load_benchmark(BENCHMARK_PATH), None
    except Exception as exc:
        return [], f"Không đọc được {BENCHMARK_PATH}: {type(exc).__name__}: {exc}"


@st.cache_data(show_spinner=False)
def load_replay_payload() -> tuple[dict[str, Any] | None, str | None]:
    """Đọc results_all.json của lượt benchmark (vị trí mới rồi cũ) để chế độ replay.

    Schema: {"meta": {...}, "strategies": {"fixed"|"recursive"|"structure":
    {"aggregate": {...}, "questions": [entry, ...]}}}.
    """
    for path in (LOGS_BENCHMARK_DIR / "results_all.json", LEGACY_BENCHMARK_DIR / "results_all.json"):
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(payload, dict) and isinstance(payload.get("strategies"), dict):
                return payload, str(path)
    return None, None


# --------------------------------------------------------------------------- chấm điểm & tổng hợp


def is_refusal_answer(answer: str | None) -> bool:
    """Phát hiện câu trả lời dạng Soft Refusal của hệ thống.

    So khớp marker ở CẢ dạng gốc và dạng fold: phần lớn backend so
    `REFUSAL_MARKER in fold(answer)`, nhưng marker có dấu thanh trong khi fold() bỏ
    dấu — câu trả lời "không đủ thông tin" sẽ không bao giờ khớp nếu chỉ so một dạng.
    """
    if not answer:
        return False
    return REFUSAL_MARKER in answer or fold(REFUSAL_MARKER) in fold(answer)


def expected_citations_of(question: dict[str, Any] | None) -> set[str]:
    """Tập trích dẫn chuẩn rút từ cả 2 trường ground truth của câu benchmark.

    `expected_citations` có thể chứa chuỗi không phải trích dẫn ("1504", "1 lần/học kỳ");
    `extract_citations` của src/evaluation tự bỏ qua chúng vì không khớp mẫu "Điều N [Khoản M]".
    """
    expected: set[str] = set()
    if not question:
        return expected
    for item in question.get("expected_citations") or []:
        expected.update(extract_citations(str(item)))
    ground_truth = question.get("ground_truth_citation")
    if ground_truth:
        expected.update(extract_citations(str(ground_truth)))
    return expected


def compute_composite(
    hit_at_k: float | None,
    faithfulness: float | None,
    citation_f1: float | None,
    weights: tuple[float, float, float],
) -> float | None:
    """Composite = w1×Hit@K + w2×Faithfulness + w3×Citation_F1.

    Chuẩn hóa theo tổng trọng số CÓ THỂ DÙNG: khi đủ 3 thành phần và tổng trọng số = 1
    thì trùng khớp đúng công thức 0.4×Hit + 0.3×Faithfulness + 0.3×Citation_F1 của đề bài;
    khi một thành phần thiếu (replay không đo faithfulness, câu trả lời không chứa con số
    để number_support chấm) thì phần còn lại được chuẩn hóa lại thay vì bịa giá trị 0.
    """
    w_hit, w_faith, w_cit = weights
    terms: list[tuple[float | None, float]] = [
        (hit_at_k, w_hit),
        (faithfulness, w_faith),
        (citation_f1, w_cit),
    ]
    usable = [(value, weight) for value, weight in terms if value is not None and weight > 0]
    total_weight = sum(weight for _value, weight in usable)
    if not usable or total_weight <= 0:
        return None
    return round(sum(value * weight for value, weight in usable) / total_weight, 4)


def pick_winner(results: dict[str, dict[str, Any]], free_mode: bool) -> str | None:
    """Chọn chiến lược tối ưu: composite cao nhất; hết tiêu chí thì lùi theo thứ tự
    Hit@K/MRR/Citation F1 (có ground truth) hoặc Faithfulness/Latency (câu tự do)."""
    candidates = [key for key, result in results.items() if not result.get("error")]
    if not candidates:
        return None

    def _latency_of(key: str) -> float:
        value = results[key]["metrics"].get("latency_ms")
        return float(value) if value is not None else float("inf")

    if not free_mode:
        by_composite = {
            key: results[key]["composite_score"]
            for key in candidates
            if results[key]["composite_score"] is not None
        }
        if by_composite:
            return max(by_composite, key=lambda k: float(by_composite[k]))

        def _gt_rank(key: str) -> tuple[float, float, float]:
            metrics = results[key]["metrics"]
            return (
                float(metrics.get("hit_at_k") or -1.0),
                float(metrics.get("mrr") or -1.0),
                float(metrics.get("citation_f1") or -1.0),
            )

        best_rank = max(_gt_rank(key) for key in candidates)
        if best_rank > (-1.0, -1.0, -1.0):
            return max(candidates, key=_gt_rank)
        return min(candidates, key=_latency_of)

    # Chế độ câu tự do: không có ground truth — tín hiệu chất lượng duy nhất là
    # number_support (proxy Faithfulness miễn phí), sau đó mới đến Latency.
    by_faithfulness = {
        key: results[key]["metrics"].get("faithfulness")
        for key in candidates
        if results[key]["metrics"].get("faithfulness") is not None
    }
    if by_faithfulness:
        return max(by_faithfulness, key=lambda k: float(by_faithfulness[k]))
    return min(candidates, key=_latency_of)


# --------------------------------------------------------------------------- chạy MỘT chiến lược (live, có cache)


def build_demo_pipeline(use_classifier: bool, **pipeline_kwargs: Any) -> HybridRAGPipeline:
    """Dựng pipeline demo với ENABLE_CLASSIFIER đặt đúng giá trị sidebar (P5.1).

    HybridRAGPipeline đọc env NGAY LÚC __init__ nên chỉ cần đặt xung quanh lệnh
    dựng rồi khôi phục giá trị cũ — app không cài lại logic phân loại, chỉ chuyển
    lựa chọn sidebar sang cơ chế ENABLE_CLASSIFIER có sẵn của backend.
    """
    previous = os.environ.get("ENABLE_CLASSIFIER")
    os.environ["ENABLE_CLASSIFIER"] = "1" if use_classifier else "0"
    try:
        return HybridRAGPipeline(**pipeline_kwargs)
    finally:
        if previous is None:
            os.environ.pop("ENABLE_CLASSIFIER", None)
        else:
            os.environ["ENABLE_CLASSIFIER"] = previous


@st.cache_data(show_spinner=False)
def evaluate_strategy_live(
    strategy: str,
    query: str,
    top_k: int,
    generator_label: str,
    use_judge: bool,
    question: dict[str, Any] | None,
    use_classifier: bool = False,
) -> dict[str, Any]:
    """Chạy sống động MỘT chiến lược cho MỘT câu hỏi: index → pipeline → chấm điểm.

    Cache key = (strategy, query, top_k, generator_label, use_judge, question,
    use_classifier): đổi trọng số composite KHÔNG làm mất cache vì composite được
    tính ở lớp ngoài. Lỗi (Ollama chết, hết quota Gemini, thiếu index) được ném
    ra để caller bắt.
    """
    registry = get_index_registry()
    vector_db, n_chunks, index_origin = registry.get_store(strategy)

    generator, generator_error = get_generator(generator_label)
    if generator is None:
        raise RuntimeError(f"Không khởi tạo được generator: {generator_error}")

    pipeline = build_demo_pipeline(
        use_classifier,
        vector_db=vector_db,
        local_slm=get_local_slm(),
        generator=generator,
        oversample_factor=2,
        use_hybrid=True,
    )

    started = time.perf_counter()
    run = pipeline.run(query, top_k=top_k)  # pipeline TỰ fold() query bên trong — app không fold thêm
    latency_ms = round((time.perf_counter() - started) * 1000.0, 1)

    answer: str = run["answer"]
    contexts: list[str] = run["contexts"]
    sources: list[dict[str, Any]] = run["sources"]
    predicted: set[str] = extract_citations(answer)

    expected_document = (question or {}).get("source_document")
    expected = expected_citations_of(question)
    hits = (
        [source_match(s["source"], expected_document) for s in sources]
        if expected_document
        else []
    )
    matched_rank = next((i + 1 for i, hit in enumerate(hits) if hit), None)

    # KHÔNG truyền source_document vào citation_scores: nhánh rút gọn đó chấm 1.0
    # tuyệt đối kể cả khi câu trả lời không trích dẫn gì, làm phồng Citation F1.
    scores = citation_scores(expected, predicted)

    # Faithfulness: LLM Judge (Gemini, tốn quota) nếu bật; không thì number_support (proxy miễn phí).
    faithfulness: float | None = None
    faithfulness_method: str | None = None
    if use_judge:
        judge_model, judge_error = get_judge_model()
        if judge_model is not None:
            score, _unsupported, _judge_error = judge_faithfulness(judge_model, contexts, answer)
            faithfulness = score
            faithfulness_method = "judge" if score is not None else None
        elif judge_error:
            faithfulness_method = "proxy (judge lỗi: " + judge_error[:60] + ")"
    if faithfulness is None:
        proxy = number_support(answer, contexts)
        if proxy is not None:
            faithfulness = proxy
            faithfulness_method = faithfulness_method or "proxy (number_support)"

    metrics: dict[str, Any] = {
        "hit_at_k": (any(hits[:top_k]) if expected_document else None),
        "mrr": (round(1.0 / matched_rank, 4) if matched_rank else (0.0 if expected_document else None)),
        "citation_precision": scores.get("precision"),
        "citation_recall": scores.get("recall"),
        "citation_f1": scores.get("f1"),
        "citation_exact_match": scores.get("exact_match"),
        "faithfulness": faithfulness,
        "faithfulness_method": faithfulness_method,
        "latency_ms": latency_ms,
        "is_refusal": is_refusal_answer(answer),
        "n_chunks": n_chunks,
        "index_origin": index_origin,
    }
    return {
        "strategy": strategy,
        "answer": answer,
        "sources": sources,
        "contexts": contexts,
        "predicted_citations": sorted(predicted),
        "metrics": metrics,
        "normalized_query": run.get("normalized_query"),
        "labels": run.get("labels"),
        "retrieval_config": run.get("retrieval_config"),
        "sub_queries": run.get("sub_queries"),
        "error": None,
        "mode": "live",
        "replay_ts": None,
    }


def replay_entry_to_result(
    entry: dict[str, Any],
    strategy: str,
    timestamp: str,
    total_chunks: int | None,
) -> dict[str, Any]:
    """Chuyển một entry của results_all.json thành đúng khung kết quả của app.

    Replay KHÔNG có contexts đầy đủ và KHÔNG đo faithfulness — hai ô đó hiển thị
    "—" (composite chỉ còn Hit + Citation, được chuẩn hóa trọng số lại trong
    compute_composite), tuyệt đối không bịa số.
    """
    sources: list[dict[str, Any]] = []
    for retrieved in entry.get("retrieved") or []:
        sources.append(
            {
                "rank": retrieved.get("rank"),
                "source": str(retrieved.get("source") or ""),
                "tier": str(retrieved.get("tier") or ""),
                "chunk_id": retrieved.get("chunk_id"),
                "preview": str(retrieved.get("preview") or ""),
                "chars": None,
                "gt_hit": bool(retrieved.get("ground_truth_source")),
                "fed_to_generator": bool(retrieved.get("fed_to_generator")),
            }
        )
    metrics: dict[str, Any] = {
        "hit_at_k": entry.get("hit_at_k"),
        "mrr": entry.get("mrr"),
        "citation_precision": entry.get("citation_precision"),
        "citation_recall": entry.get("citation_recall"),
        "citation_f1": entry.get("citation_f1"),
        "citation_exact_match": entry.get("citation_exact_match"),
        "faithfulness": None,
        "faithfulness_method": None,
        "latency_ms": entry.get("latency_ms"),
        "is_refusal": bool(entry.get("is_refusal")),
        "n_chunks": total_chunks,
        "index_origin": None,
    }
    return {
        "strategy": strategy,
        "answer": entry.get("answer"),
        "sources": sources,
        "contexts": None,
        "predicted_citations": list(entry.get("predicted_citations") or []),
        "metrics": metrics,
        "normalized_query": None,
        "labels": entry.get("labels"),
        "retrieval_config": entry.get("retrieval_config"),
        "sub_queries": entry.get("sub_queries"),
        "error": entry.get("error"),
        "mode": "replay",
        "replay_ts": timestamp,
    }


def find_replay_entry(
    payload: dict[str, Any] | None,
    strategy: str,
    query: str,
    top_k: int,
    generator_label: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Tìm entry replay của câu đang chọn, CHỈ khi khớp tham số (top_k, generator).

    So khớp generator theo từ khóa "qwen"/"gemini" trong meta.generator_model để
    không phụ thuộc định dạng chuỗi model_name của từng lớp generator.
    """
    if payload is None:
        return None, None
    meta = payload.get("meta") or {}
    try:
        if int(meta.get("top_k", -1)) != int(top_k):
            return None, None
    except (TypeError, ValueError):
        return None, None
    meta_is_qwen = "qwen" in str(meta.get("generator_model", "")).lower()
    want_qwen = generator_label != GENERATOR_GEMINI
    if meta_is_qwen != want_qwen:
        return None, None

    questions = (payload.get("strategies") or {}).get(strategy, {}).get("questions") or []
    target = query.strip()
    for entry in questions:
        if str(entry.get("raw_query", "")).strip() == target:
            return entry, str(meta.get("timestamp", ""))
    return None, None


def error_result(strategy: str, exc: Exception) -> dict[str, Any]:
    """Khung kết quả cho chiến lược bị lỗi — 2 chiến lược còn lại vẫn hiển thị bình thường."""
    return {
        "strategy": strategy,
        "answer": None,
        "sources": [],
        "contexts": None,
        "predicted_citations": [],
        "metrics": {},
        "normalized_query": None,
        "labels": None,
        "retrieval_config": None,
        "sub_queries": None,
        "composite_score": None,
        "error": f"{type(exc).__name__}: {exc}",
        "mode": "live",
        "replay_ts": None,
    }


# --------------------------------------------------------------------------- hàm trung tâm


def evaluate_rag_strategies(
    query: str,
    top_k: int,
    benchmark_question: dict[str, Any] | None = None,
    *,
    generator_label: str = GENERATOR_QWEN,
    use_judge: bool = False,
    use_classifier: bool = False,
    allow_replay: bool = True,
    weights: tuple[float, float, float] = DEFAULT_WEIGHTS,
    on_strategy_start: Callable[[int, str], Any] | None = None,
    on_strategy_done: Callable[[int, str, dict[str, Any]], Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Hàm backend trung tâm của app: chạy TUẦN TỰ 3 chiến lược cho một câu hỏi.

    Trả về {strategy_key: {"answer", "sources", "contexts", "predicted_citations",
    "metrics": {...}, "labels": {...}|None, "retrieval_config": {...}|None,
    "composite_score": float | None, "error": str | None, ...}}.
    Mỗi chiến lược độc lập: một chiến lược lỗi không ảnh hưởng 2 chiến lược còn lại.
    Callback on_strategy_start/on_strategy_done để UI render st.status + st.progress
    theo từng chiến lược mà vẫn giữ hàm này làm điểm vào duy nhất.
    """
    payload, _path = load_replay_payload() if allow_replay else (None, None)

    results: dict[str, dict[str, Any]] = {}
    for index, strategy in enumerate(STRATEGIES):
        if on_strategy_start is not None:
            on_strategy_start(index, strategy)
        try:
            if allow_replay and payload is not None:
                entry, timestamp = find_replay_entry(
                    payload, strategy, query, top_k, generator_label
                )
                if entry is not None:
                    total_chunks = (
                        (payload.get("strategies") or {})
                        .get(strategy, {})
                        .get("aggregate", {})
                        .get("total_chunks")
                    )
                    results[strategy] = replay_entry_to_result(
                        entry, strategy, timestamp, int(total_chunks) if total_chunks else None
                    )
                else:
                    results[strategy] = evaluate_strategy_live(
                        strategy, query, top_k, generator_label, use_judge,
                        benchmark_question, use_classifier,
                    )
            else:
                results[strategy] = evaluate_strategy_live(
                    strategy, query, top_k, generator_label, use_judge,
                    benchmark_question, use_classifier,
                )
        except Exception as exc:  # một chiến lược chết không được làm app chết
            results[strategy] = error_result(strategy, exc)
        if on_strategy_done is not None:
            on_strategy_done(index, strategy, results[strategy])

    # Composite tính NGOÀI cache: đổi trọng số ở sidebar chỉ tính lại công thức, không chạy lại backend.
    for result in results.values():
        if result["error"] is None:
            metrics = result["metrics"]
            result["composite_score"] = compute_composite(
                metrics.get("hit_at_k"),
                metrics.get("faithfulness"),
                metrics.get("citation_f1"),
                weights,
            )
    return results


# --------------------------------------------------------------------------- định dạng hiển thị


def fmt_score(value: float | None, digits: int = 3) -> str:
    """Số liệu 0–1 hiển thị dạng thập phân; thiếu dữ liệu thì hiển thị '—'."""
    return "—" if value is None else f"{value:.{digits}f}"


def fmt_percent(value: float | None) -> str:
    """Tỉ lệ 0–1 hiển thị dạng phần trăm; thiếu dữ liệu thì hiển thị '—'."""
    return "—" if value is None else f"{value * 100:.0f}%"


def fmt_latency(value: float | None) -> str:
    """Latency ms hiển thị cách ngăn nghìn; thiếu dữ liệu thì hiển thị '—'."""
    return "—" if value is None else f"{value:,.0f}"


def format_classification_lines(
    labels: dict[str, Any] | None,
    retrieval_config: dict[str, Any] | None,
    sub_queries: list[str] | None,
    mode: str,
) -> list[str]:
    """Các dòng khối '🏷️ Phân loại câu hỏi' (P5.1) — THUẦN HIỂN THỊ, không gọi backend.

    - labels None (tầng phân loại Tắt / suy giảm mềm / entry replay cũ không có
      nhãn) → dòng '—'; entry replay cũ kèm ghi chú chạy lại benchmark với
      `--with-classifier` để có dữ liệu replay mới.
    - Có nhãn → dòng nhãn (chủ đề · loại) + dòng cấu hình router đã chọn
      (top_k · trọng số BM25/Chroma · lọc nguồn) + dòng tách truy vấn con
      (CÓ n nhánh theo result.sub_queries / KHÔNG).
    """
    if not labels:
        lines = ["Nhãn phân loại: —"]
        if mode == "replay":
            lines.append(
                "(Entry replay cũ chưa có nhãn — chạy lại benchmark với `--with-classifier` "
                "để có dữ liệu replay mới.)"
            )
        return lines

    cfg = retrieval_config or {}
    lines: list[str] = []
    # `or '—'`: classifier trả None cho cả key (vd câu ngoài corpus → chủ đề
    # None) — .get(key, '—') chỉ fallback khi THIẾU key, không bắt giá trị None.
    topic = labels.get("topic") or "—"
    question_type = labels.get("question_type") or "—"
    lines.append(f"Nhãn: chủ đề **{topic}** · loại câu hỏi **{question_type}**")
    config_parts = [
        f"top_k={cfg.get('top_k', '—')}",
        f"bm25={cfg.get('bm25_weight', '—')}/chroma={cfg.get('chroma_weight', '—')}",
    ]
    src_filter = cfg.get("source_filter") or []
    if src_filter:
        config_parts.append("lọc nguồn: " + ", ".join(src_filter))
    lines.append("Cấu hình đã chọn: " + " · ".join(config_parts))

    if sub_queries:
        lines.append(f"Tách truy vấn con: CÓ ({len(sub_queries)} nhánh)")
    elif cfg.get("enable_subquery"):
        lines.append("Tách truy vấn con: CÓ (guardrail lùi về đường đơn)")
    else:
        lines.append("Tách truy vấn con: KHÔNG")
    return lines


# --------------------------------------------------------------------------- UI: sidebar & input


def render_sidebar() -> dict[str, Any]:
    """Vẽ sidebar cấu hình và trả về dict tham số cho lượt đánh giá."""
    with st.sidebar:
        st.header("⚙️ Cấu hình thí nghiệm")

        st.text_input("Embedding Model", value="BAAI/bge-m3", disabled=True,
                      help="Fixed của đề tài: bge-m3 (normalize_embeddings=True) trên ChromaDB.")
        generator_label = st.radio(
            "Generator",
            (GENERATOR_QWEN, GENERATOR_GEMINI),
            index=0,
            help="Qwen chạy 100% offline qua Ollama. Gemini cần GEMINI_API_KEY trong .env "
                 "và đã TẮT qwen_fallback để không trộn 2 model trong một lượt so sánh.",
        )
        top_k = st.slider(
            "Top-K (generator)",
            min_value=1,
            max_value=5,
            value=3,
            help="Generator nhận top_k chunk; hệ truy xuất lấy top_k×2 (oversampling) để đo Hit@K.",
        )
        use_classifier = st.selectbox(
            "Tầng phân loại câu hỏi",
            ("Tắt", "Bật"),
            index=1,
            help="Bật: LocalSLM gán nhãn chủ đề/loại câu hỏi và router điều chỉnh cấu hình "
                 "truy xuất theo lớp (top_k, trọng số, lọc nguồn, tách truy vấn con — P3.2). "
                 "Tắt: truy xuất giữ nguyên cấu hình nền, không gọi classifier.",
        )

        st.divider()
        use_judge = st.checkbox(
            "Bật LLM Judge Faithfulness (Gemini, tốn quota)",
            value=False,
            help=f"Tắt: Faithfulness đo bằng number_support (proxy miễn phí). "
                 f"Bật: Gemini '{JUDGE_MODEL_NAME}' chấm độc lập, tách khỏi generator.",
        )
        allow_replay = st.checkbox(
            "Chế độ demo nhanh (replay)",
            value=True,
            help="Dùng số liệu ĐÃ ĐO trong logs/benchmark/results_all.json nếu câu hỏi và "
                 "tham số khớp — demo tức thì, không gọi generator.",
        )

        st.divider()
        st.caption("Trọng số Composite (tổng nên = 1)")
        w_hit = st.number_input("Trọng số Hit@K", min_value=0.0, max_value=1.0, value=DEFAULT_WEIGHTS[0],
                                step=0.05, format="%.2f", key="w_hit")
        w_faith = st.number_input("Trọng số Faithfulness", min_value=0.0, max_value=1.0,
                                  value=DEFAULT_WEIGHTS[1], step=0.05, format="%.2f", key="w_faith")
        w_cit = st.number_input("Trọng số Citation F1", min_value=0.0, max_value=1.0,
                                value=DEFAULT_WEIGHTS[2], step=0.05, format="%.2f", key="w_cit")

        st.divider()
        ok, message = get_local_slm().check_connection()
        if ok:
            st.caption(f"🟢 Ollama: {message}")
        else:
            st.caption(f"🔴 Ollama: {message} — chế độ Qwen live sẽ lỗi, dùng replay hoặc Gemini.")

        return {
            "generator_label": generator_label,
            "top_k": top_k,
            "use_classifier": use_classifier == "Bật",
            "use_judge": use_judge,
            "allow_replay": allow_replay,
            "weights": (float(w_hit), float(w_faith), float(w_cit)),
        }


def render_input(sidebar: dict[str, Any]) -> tuple[str, dict[str, Any] | None, bool]:
    """Khu nhập câu hỏi với 2 chế độ: câu từ benchmark (có ground truth) / câu tự do."""
    questions, benchmark_error = load_benchmark_questions()
    in_corpus = [q for q in questions if q.get("in_corpus")]

    mode_free = False
    question: dict[str, Any] | None = None

    if not questions:
        mode_free = True
        st.caption(f"⚠️ {benchmark_error} — chỉ nhập được câu tự do.")
    else:
        # Câu mặc định: chứa "cảnh báo" (cảnh báo học vụ), Tầng 1, in_corpus=true;
        # không có thì lấy câu đầu tiên in_corpus=true (so khớp có dấu trước, fold làm phương án dự phòng).
        default_index = 0
        for index, candidate in enumerate(in_corpus or questions):
            raw = str(candidate.get("raw_query", ""))
            is_warning_tier1 = (
                "cảnh báo" in raw.lower() or "canh bao" in fold(raw)
            ) and candidate.get("tier") == "Tầng 1"
            if is_warning_tier1:
                default_index = index
                break

        choice = st.radio("Nguồn câu hỏi", ("📚 Câu từ benchmark", "✍️ Câu tự do"), horizontal=True)
        if choice == "📚 Câu từ benchmark":
            pool = in_corpus or questions
            labels = [f"{q.get('id', '?')} · {_one_line(q.get('raw_query', ''), 90)}" for q in pool]
            selected = st.selectbox(
                "Chọn câu hỏi benchmark",
                range(len(pool)),
                index=min(default_index, len(pool) - 1),
                format_func=lambda i: labels[i],
            )
            question = pool[selected]
            st.caption(
                f"Tier: {question.get('tier')} · in_corpus: {question.get('in_corpus')} · "
                f"Nguồn chuẩn: {question.get('source_document') or '—'}"
            )
        else:
            mode_free = True

    if mode_free:
        question = None

    if mode_free:
        query = st.text_input(
            "Nhập câu hỏi của bạn",
            value="",
            placeholder="Ví dụ: Điều kiện tốt nghiệp với bằng điểm loại giỏi là gì?",
            help="Câu tự do KHÔNG có ground truth: chỉ hiển thị Answer + chunk truy xuất + "
                 "Latency; các ô Hit@K / Citation / Composite hiển thị '—'.",
        )
    else:
        assert question is not None  # chắc chắn ở nhánh benchmark có câu được chọn
        query = str(question.get("raw_query", ""))
        st.text_area("Câu hỏi đã chọn", value=query, height=68, disabled=True)

    return query, question, mode_free


def _one_line(text: Any, limit: int) -> str:
    """Làm phẳng văn bản nhiều dòng thành một dòng, cắt ở `limit` ký tự."""
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------- UI: chạy & 3 tab


def run_evaluation(sidebar: dict[str, Any], query: str, question: dict[str, Any] | None,
                   free_mode: bool) -> None:
    """Chạy 3 chiến lược với st.status riêng cho từng chiến lược + st.progress tổng."""
    progress = st.progress(0.0, text="Chuẩn bị chạy đánh giá…")
    statuses: dict[str, Any] = {}

    def on_strategy_start(index: int, strategy: str) -> None:
        statuses[strategy] = st.status(f"⏳ {STRATEGIES[strategy]['label']}", expanded=True)

    def on_strategy_done(index: int, strategy: str, result: dict[str, Any]) -> None:
        label = STRATEGIES[strategy]["label"]
        status = statuses.pop(strategy)
        latency = result["metrics"].get("latency_ms")
        if result["error"]:
            status.update(label=f"❌ {label} — LỖI", state="error", expanded=True)
            st.error(f"{label}: {result['error']}")
        else:
            badge = (
                f"📅 Replay từ lượt benchmark {result['replay_ts']}"
                if result["mode"] == "replay"
                else "⚡ Live"
            )
            latency_text = f" · {latency:,.0f} ms" if latency is not None else ""
            status.update(label=f"✅ {label} — {badge}{latency_text}", state="complete",
                          expanded=False)
        progress.progress(
            (index + 1) / len(STRATEGIES),
            text=f"Hoàn tất {index + 1}/{len(STRATEGIES)} chiến lược",
        )

    results = evaluate_rag_strategies(
        query,
        sidebar["top_k"],
        benchmark_question=question,
        generator_label=sidebar["generator_label"],
        use_judge=sidebar["use_judge"],
        use_classifier=sidebar["use_classifier"],
        allow_replay=sidebar["allow_replay"],
        weights=sidebar["weights"],
        on_strategy_start=on_strategy_start,
        on_strategy_done=on_strategy_done,
    )
    progress.progress(1.0, text="🎉 Đánh giá hoàn tất")

    st.session_state["demo_run"] = {
        "results": results,
        "query": query,
        "question": question,
        "free_mode": free_mode,
        "top_k": sidebar["top_k"],
        "weights": sidebar["weights"],
        "use_judge": sidebar["use_judge"],
        "use_classifier": sidebar["use_classifier"],
    }


def render_tab_winner(run: dict[str, Any], winner: str | None) -> None:
    """Tab 1 — câu trả lời của chiến lược tối ưu + 4 ô chỉ số tổng hợp."""
    results: dict[str, dict[str, Any]] = run["results"]
    free_mode: bool = run["free_mode"]
    weights: tuple[float, float, float] = run["weights"]

    if winner is None:
        st.error("Cả 3 chiến lược đều lỗi — xem chi tiết ở Tab 3 hoặc kiểm tra Ollama/API key.")
        return

    best = results[winner]
    metrics = best["metrics"]

    if free_mode:
        st.caption("Chế độ câu tự do: không có ground truth để chọn theo Composite — "
                   "app chọn chiến lược theo Faithfulness proxy (number_support), sau đó Latency.")
    st.subheader(f"🏆 {STRATEGIES[winner]['short']}")
    st.caption(STRATEGIES[winner]["label"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Composite Score",
        fmt_score(best["composite_score"]),
        help="Composite = "
             f"{weights[0]:.2f}×Hit@K + {weights[1]:.2f}×Faithfulness + {weights[2]:.2f}×Citation_F1 "
             "(chuẩn hóa theo tổng trọng số khả dụng khi một thành phần thiếu).",
    )
    col2.metric(
        "Hit@K",
        fmt_percent(metrics.get("hit_at_k")),
        help="Top-K chunk đưa vào generator có chứa chunk đúng nguồn chuẩn hay không."
             if not free_mode else "Chỉ đo được khi có ground truth (câu benchmark).",
    )
    col3.metric(
        "Faithfulness",
        fmt_score(metrics.get("faithfulness")),
        help=str(metrics.get("faithfulness_method") or
                 "LLM Judge hoặc number_support; chưa đo được ở lượt này."),
    )
    col4.metric(
        "Citation F1",
        fmt_score(metrics.get("citation_f1")),
        help="F1 giữa tập mã 'Điều N [Khoản M]' hệ thống sinh ra và tập ground truth."
             if not free_mode else "Chỉ đo được khi có ground truth (câu benchmark).",
    )

    if best.get("error"):
        st.error(f"Chiến lược thắng bị lỗi: {best['error']}")
        return

    # P5.1: khối "🏷️ Phân loại câu hỏi" — nhãn + cấu hình router của chiến lược thắng.
    st.markdown("##### 🏷️ Phân loại câu hỏi")
    for line in format_classification_lines(
        best.get("labels"), best.get("retrieval_config"), best.get("sub_queries"), best["mode"]
    ):
        st.markdown(line)

    answer = str(best.get("answer") or "")
    if is_refusal_answer(answer):
        st.warning(
            "Hệ thống TỪ CHỐI trả lời — ngữ cảnh truy xuất không đủ căn cứ. "
            "Với câu hỏi ngoài phạm vi corpus, đây là hành vi ĐÚNG (Soft Refusal, không bịa)."
        )
    else:
        st.info(answer)

    lines = ["TRÍCH DẪN HỆ THỐNG SINH RA:"]
    citations = sorted(best.get("predicted_citations") or [])
    lines.append("  " + ("; ".join(citations) if citations else "(không có)"))
    lines.append("")
    lines.append("NGUỒN TOP-K ĐƯA VÀO GENERATOR:")
    for source in (best.get("sources") or [])[: run["top_k"]]:
        lines.append(
            f"  #{source.get('rank')}  {source.get('source')}  "
            f"(tier: {source.get('tier')}, chunk_id={source.get('chunk_id')})"
        )
    if best["mode"] == "replay":
        lines.append("")
        lines.append(f"(Dữ liệu replay từ lượt benchmark {best['replay_ts']} — không gọi generator.)")
    st.code("\n".join(lines), language=None)


def render_tab_comparison(run: dict[str, Any], winner: str | None) -> None:
    """Tab 2 — bảng so sánh 3 chiến lược, tô nổi dòng chiến lược thắng."""
    results: dict[str, dict[str, Any]] = run["results"]
    rows: list[dict[str, str]] = []
    for strategy, meta in STRATEGIES.items():
        result = results[strategy]
        metrics = result["metrics"]
        faith_value = metrics.get("faithfulness")
        method_suffix = ""
        if faith_value is not None and "proxy" in str(metrics.get("faithfulness_method") or ""):
            method_suffix = " (proxy)"
        rows.append(
            {
                "Chiến lược": meta["short"],
                "Composite": fmt_score(result.get("composite_score")),
                "Hit@K": fmt_percent(metrics.get("hit_at_k")),
                "MRR": fmt_score(metrics.get("mrr")),
                "Faithfulness": fmt_score(faith_value) + method_suffix,
                "Citation Precision": fmt_score(metrics.get("citation_precision")),
                "Citation Recall": fmt_score(metrics.get("citation_recall")),
                "Citation F1": fmt_score(metrics.get("citation_f1")),
                "Latency (ms)": fmt_latency(metrics.get("latency_ms")),
                "Số chunk": str(metrics["n_chunks"]) if metrics.get("n_chunks") is not None else "—",
            }
        )

    frame = pd.DataFrame(rows)

    def _highlight_winner(row: pd.Series) -> list[str]:
        if winner is not None and row["Chiến lược"] == STRATEGIES[winner]["short"]:
            return ["background-color: #d4edda; font-weight: 600"] * len(row)
        return [""] * len(row)

    st.dataframe(frame.style.apply(_highlight_winner, axis=1), hide_index=True)

    if not run["free_mode"]:
        any_replay = any(r["mode"] == "replay" for r in results.values())
        if any(r["metrics"].get("faithfulness") is None for r in results.values() if not r["error"]):
            st.caption("Composite ở dòng có Faithfulness = '—' chỉ gồm Hit@K và Citation F1 "
                       "(chuẩn hóa trọng số lại) — replay không lưu contexts nên không đo lại faithfulness.")
        if any_replay:
            st.caption("📅 Dòng mang số liệu replay từ logs/benchmark/results_all.json; "
                       "còn lại là lượt Live. Trộn hai nguồn vẫn cùng tham số top_k và generator.")
    else:
        st.caption("Chế độ câu tự do: không có ground truth → Hit@K / MRR / Citation / Composite "
                   "hiển thị '—'; Faithfulness là proxy number_support (số trong đáp án có trong ngữ cảnh).")

    origins = [
        f"{meta['short']}: {results[key]['metrics'].get('index_origin')}"
        for key, meta in STRATEGIES.items()
        if results[key]["metrics"].get("index_origin")
    ]
    if origins:
        st.caption("Nguồn index — " + " · ".join(origins))


def render_tab_chunks(run: dict[str, Any]) -> None:
    """Tab 3 — chi tiết đoạn truy xuất của từng chiến lược đặt cạnh nhau để soi đứt gãy ngữ cảnh."""
    results: dict[str, dict[str, Any]] = run["results"]
    question = run["question"]
    expected_document = (question or {}).get("source_document")
    top_k: int = run["top_k"]

    columns = st.columns(3)
    for column, (strategy, meta) in zip(columns, STRATEGIES.items()):
        result = results[strategy]
        with column:
            st.markdown(f"#### {meta['short']}")
            if result["error"]:
                st.error(result["error"])
                continue

            sources: list[dict[str, Any]] = result.get("sources") or []
            contexts: list[str] | None = result.get("contexts")
            if result["mode"] == "replay":
                st.caption("📅 Replay: chỉ có preview đã lưu trong results_all.json, "
                           "không có ngữ cảnh đầy đủ.")

            for source in sources:
                gt_mark = ""
                if expected_document:
                    gt_mark = " ✓" if source_match(str(source.get("source")), str(expected_document)) else ""
                elif result["mode"] == "replay" and source.get("gt_hit"):
                    gt_mark = " ✓"
                fed = "🅖" if source.get("fed_to_generator") else " "
                header = (
                    f"{fed} #{source.get('rank')} · "
                    f"{_one_line(source.get('source'), 34)}{gt_mark}"
                )
                with st.expander(header):
                    st.caption(
                        f"source: {source.get('source')} · tier: {source.get('tier')} · "
                        f"chunk_id: {source.get('chunk_id')}"
                        + (f" · {source.get('chars')} ký tự" if source.get("chars") else "")
                        + (" · đưa vào generator" if source.get("fed_to_generator") else
                           " · ngoài cửa sổ generator (recall window)")
                    )
                    if contexts is not None and source.get("rank") is not None:
                        rank_index = int(source["rank"]) - 1
                        if 0 <= rank_index < len(contexts):
                            st.markdown(contexts[rank_index])
                            continue
                    st.markdown(str(source.get("preview") or "")[:160] or "_(trống)_")

            answer = str(result.get("answer") or "")
            if not answer:
                st.warning("Không có câu trả lời ở lượt này.")
            else:
                st.markdown("**Câu trả lời:**")
                st.markdown(answer)
            citations = sorted(result.get("predicted_citations") or [])
            st.caption("Trích dẫn hệ thống sinh ra: " + ("; ".join(citations) if citations else "(không có)"))
            if result.get("normalized_query"):
                st.caption(f"Query sau chuẩn hóa: {result['normalized_query']}")
            if metrics := result["metrics"]:
                st.caption(
                    f"Latency: {fmt_latency(metrics.get('latency_ms'))} ms · "
                    f"Hit@K: {fmt_percent(metrics.get('hit_at_k'))} · "
                    f"MRR: {fmt_score(metrics.get('mrr'))} · "
                    f"Citation F1: {fmt_score(metrics.get('citation_f1'))}"
                )


def main() -> None:
    """Điểm vào app: sidebar → input → chạy đánh giá → 3 tab kết quả."""
    st.set_page_config(
        page_title="Demo Chunking — Hybrid RAG ĐHAG",
        page_icon="🔬",
        layout="wide",
    )
    st.title("🔬 Demo So Sánh 3 Chiến Lược Phân Đoạn Tài Liệu")
    st.caption(
        "Hybrid RAG tra cứu quy chế sinh viên ĐHAG · backend tái sử dụng nguyên vẹn từ `src/` "
        "(chunking → bge-m3 + BM25/RRF → Qwen/Gemini · chấm điểm từ `src/evaluation.py`). "
        "Live mode mất khoảng 30–60 giây/câu/chiến lược với Qwen local; lần đầu chưa có index "
        "sẽ mất thêm vài phút để nhúng corpus."
    )

    sidebar = render_sidebar()
    query, question, free_mode = render_input(sidebar)

    st.divider()
    col_run, col_hint = st.columns([1, 3])
    run_clicked = col_run.button("🚀 Chạy Đánh Giá RAG", type="primary", use_container_width=True)
    with col_hint:
        payload, payload_path = load_replay_payload()
        if payload is None:
            st.caption(
                "💡 Chưa có dữ liệu replay — chạy `python scripts/benchmark_chunking.py --generator qwen` "
                "để tạo logs/benchmark/results_all.json rồi bật 'Chế độ demo nhanh (replay)'."
            )
        elif not sidebar["allow_replay"]:
            st.caption(f"💡 Replay đang TẮT — đang dùng dữ liệu tại {payload_path}, "
                       "tick 'Chế độ demo nhanh (replay)' để demo tức thì.")

    if run_clicked:
        if not query.strip():
            st.warning("Hãy nhập hoặc chọn một câu hỏi trước khi chạy đánh giá.")
        else:
            run_evaluation(sidebar, query.strip(), question, free_mode)

    run = st.session_state.get("demo_run")
    if not run:
        st.info(
            "👈 Cấu hình ở sidebar, chọn hoặc nhập câu hỏi rồi bấm **🚀 Chạy Đánh Giá RAG**.\n\n"
            "Kết quả gồm 3 tab: 🏆 Câu trả lời tối ưu · 📊 Bảng so sánh 3 chiến lược · "
            "🔍 Chi tiết đoạn truy xuất."
        )
        return

    winner = pick_winner(run["results"], run["free_mode"])
    tab_winner, tab_table, tab_chunks = st.tabs(
        ["🏆 Câu Trả Lời Tối Ưu", "📊 Bảng So Sánh 3 Chiến Lược", "🔍 Chi Tiết Đoạn Truy Xuất"]
    )
    with tab_winner:
        render_tab_winner(run, winner)
    with tab_table:
        render_tab_comparison(run, winner)
    with tab_chunks:
        render_tab_chunks(run)


if __name__ == "__main__":
    main()
