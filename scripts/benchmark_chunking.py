"""BENCHMARK & LOGGING PIPELINE — so sánh 3 chiến lược chunking trên cùng một testbed.

Script chạy thực nghiệm trọn vòng: với MỖI chiến lược chunking (fixed-size 512 token,
recursive, structure-aware + khóa bảng Markdown) nó sẽ

  1. nạp corpus `data/corpus` (PDF/DOCX/TXT, có OCR cache) và cắt chunk theo chiến lược đó;
  2. dựng một ChromaDB ĐỘC LẬP tại `logs/benchmark/chroma_<strategy>/` và đo dung lượng
     chỉ mục (Index Size, MB);
  3. dựng đúng pipeline sản xuất (Qwen chuẩn hóa → BM25 + bge-m3 gộp RRF → Gemini) với
     Retriever Top-K=3 cho generator và Generator temperature=0;
  4. duyệt lần lượt từng câu trong testbed (mặc định 50 câu) và tự động tính
     Hit@K, MRR, Citation Precision / Recall / F1, Latency (ms);
  5. xuất log chi tiết riêng cho từng chiến lược và một báo cáo so sánh dạng ma trận.

Mọi hàm chấm điểm (Hit@K, MRR, Citation) được TÁI SỬ DỤNG từ `src/assessment/evaluation.py` để số
liệu của script này so sánh trực tiếp được với `outputs/evaluation_summary.md`.

ĐẦU RA (thư mục `./logs/benchmark/` tự tạo):
    log_fixed_size.txt            log chi tiết chiến lược fixed
    log_recursive.txt             log chi tiết chiến lược recursive
    log_structure_aware.txt       log chi tiết chiến lược structure
    summary_comparison_report.csv ma trận so sánh (mở được bằng Excel, có BOM UTF-8)
    summary_comparison_report.md  ma trận so sánh dạng Markdown (dán thẳng vào bài báo)
    results_all.json              toàn bộ số liệu thô để vẽ biểu đồ / chấm lại sau
    chroma_<strategy>/            vector store độc lập của từng chiến lược (xóa được)

CÁCH CHẠY (từ thư mục gốc dự án):
    python scripts/benchmark_chunking.py                        # đủ 3 chiến lược × 50 câu, Gemini
    python scripts/benchmark_chunking.py --limit 2              # smoke test nhanh 2 câu
    python scripts/benchmark_chunking.py --strategies structure # chỉ một chiến lược
    python scripts/benchmark_chunking.py --generator qwen       # 100% offline, không tốn quota
    python scripts/benchmark_chunking.py --no-cache             # tắt cache để đo Latency trung thực
    python scripts/benchmark_chunking.py --device cuda          # Colab GPU T4

LƯU Ý QUOTA: 50 câu × 3 chiến lược = 150 lần gọi Gemini. Free tier giới hạn theo NGÀY
cho từng model, nên hãy chạy thử `--limit 2` trước, hoặc dùng `--generator qwen`, hoặc
chạy rải từng chiến lược một. Script tự dừng sớm (vẫn ghi báo cáo phần đã chạy) khi
phát hiện lỗi quota ngày.

Python 3.10+. Chạy được trên Google Colab (`%cd` vào thư mục dự án rồi chạy như trên);
`pandas` là tùy chọn — nếu chưa cài (`pip install pandas`) script tự lùi về `csv`/bảng
Markdown dựng tay và vẫn xuất đủ báo cáo.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

if __package__ in (None, ""):  # cho phép chạy trực tiếp từ mọi thư mục làm việc
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.indexing.chunking import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    WhitespaceTokenCounter,
    chunk_with_strategy,
    get_token_counter,
)
from src.assessment.evaluation import (
    citation_scores,
    extract_citations,
    load_benchmark,
    source_match,
)
from src.generator import (
    GeminiGenerator,
    QwenGenerator,
    REFUSAL_MARKER,
    is_quota_error,
)
from src.indexing.loader import DocumentLoader
from src.generation.local_slm import LocalSLM
from src.core.pipeline import HybridRAGPipeline
from src.text_utils import fold
from src.retrieval.vector_db import DEFAULT_RRF_C, VectorStoreManager

try:  # pandas chỉ dùng để dựng bảng; thiếu thì script vẫn chạy bằng nhánh dự phòng
    import pandas as pd
except ImportError:  # pragma: no cover - phụ thuộc môi trường
    pd = None

# --------------------------------------------------------------------------- Cấu hình

CORPUS_DIR = "./data/corpus"
DEFAULT_BENCHMARK = Path("data/evaluation/benchmark_50_questions.json")
DEFAULT_LOG_DIR = Path("logs", "benchmark")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
COLLECTION_PREFIX = "bench"

# Tên file log bắt buộc theo từng chiến lược (đặt hàng cho bài báo NCKH).
STRATEGY_LOG_NAMES: dict[str, str] = {
    "fixed": "log_fixed_size.txt",
    "recursive": "log_recursive.txt",
    "structure": "log_structure_aware.txt",
}
STRATEGY_LABELS: dict[str, str] = {
    "fixed": "Fixed-size (cắt cứng theo token)",
    "recursive": "Recursive (phân tách theo cấp bậc)",
    "structure": "Structure-aware (Điều/Khoản/Điểm + metadata phân cấp)",
}

# Số chunk truy xuất mở rộng (oversampling) để đo được cả Hit@5/Hit@6 từ một lượt chạy.
OVERSAMPLE_FACTOR = 2

# Độ dài trích dẫn hiển thị trong log.
CHUNK_PREVIEW_CHARS = 100
ANSWER_LOG_CHARS = 1200
GROUND_TRUTH_LOG_CHARS = 300

LINE = "=" * 78
SUBLINE = "-" * 78

logger = logging.getLogger("benchmark_chunking")


# --------------------------------------------------------------------------- logging


def setup_logger() -> None:
    """Logger chuẩn của Python: một kênh console cố định, kênh file gắn theo chiến lược."""
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


@contextmanager
def strategy_log_file(log_path: Path) -> Iterator[logging.Handler]:
    """Gắn tạm một FileHandler UTF-8 cho file log của chiến lược đang chạy.

    Phải mở với `encoding="utf-8"`: console Windows mặc định cp1258 sẽ nổ
    UnicodeEncodeError khi ghi tiếng Việt có dấu.
    """
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        handler.close()


# --------------------------------------------------------------------------- tiện ích


def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
    """Trung bình bỏ qua None (câu không chấm được chỉ số đó)."""
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 4) if valid else None


def _num(value: Optional[float], digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _one_line(text: Any, limit: int) -> str:
    """Làm phẳng văn bản nhiều dòng thành một dòng, cắt ở `limit` ký tự."""
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _wrap(text: Any, limit: int, indent: str = "  ") -> str:
    """Cắt văn bản dài thành nhiều dòng có thụt lề để log dễ đọc."""
    flat = _one_line(text, limit)
    if not flat:
        return f"{indent}(trống)"
    width = max(40, 100 - len(indent))
    lines = [flat[i : i + width] for i in range(0, len(flat), width)]
    return "\n".join(indent + line for line in lines)


def dir_size_mb(path: Path) -> float:
    """Dung lượng toàn bộ file trong thư mục ChromaDB, tính bằng MB (hệ 10^6)."""
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / 1_000_000, 2)


def rrf_rank_score(rank: int, c: int = DEFAULT_RRF_C) -> float:
    """Điểm Reciprocal Rank Fusion suy ra từ thứ hạng cuối cùng: 1/(c + rank).

    EnsembleRetriever của LangChain không trả kèm điểm số, nên điểm RRF được dựng lại
    từ chính thứ hạng đã fusion — nhất quán cho cả 3 chiến lược và không tốn thêm lượt
    truy xuất nào (khác với việc gọi lại ChromaDB để lấy cosine).
    """
    return round(1.0 / (c + max(1, int(rank))), 6)


def apply_device(manager: VectorStoreManager, device: str) -> str:
    """Trả về nhãn thiết bị nhúng thực tế; chỉ dựng lại embeddings khi yêu cầu CUDA.

    `VectorStoreManager` mặc định nạp bge-m3 trên CPU. Trên Colab T4 việc nhúng ~600
    chunk × 3 chiến lược nhanh hơn rõ rệt nếu chuyển sang GPU, nên khi `--device cuda`
    ta thay hẳn đối tượng embeddings trước khi tạo vector store.
    """
    if device != "cuda":
        return "cpu"
    try:
        import torch
        from langchain_huggingface import HuggingFaceEmbeddings

        if not torch.cuda.is_available():
            return "cpu (torch.cuda không khả dụng)"
        manager.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cuda"},
            encode_kwargs={"normalize_embeddings": True},
        )
        return f"cuda ({torch.cuda.get_device_name(0)})"
    except Exception as exc:  # pragma: no cover - phụ thuộc phần cứng
        return f"cpu (không bật được GPU: {type(exc).__name__}: {exc})"


# --------------------------------------------------------------------------- corpus & index


def load_corpus() -> list[dict]:
    """Nạp corpus MỘT lần dùng chung cho cả 3 chiến lược (OCR đã có cache trên đĩa)."""
    loader = DocumentLoader(data_dir=CORPUS_DIR)
    documents = loader.load_documents()
    if not documents:
        raise SystemExit(
            f"Thư mục '{CORPUS_DIR}' không có tài liệu nào đọc được (.txt/.pdf/.docx). "
            f"Đã bỏ qua {len(loader.skipped)} file."
        )
    if loader.skipped:
        logger.info(f"[Corpus] Cảnh báo: không đọc được {len(loader.skipped)} file:")
        for path, reason in loader.skipped:
            logger.info(f"[Corpus]   - {os.path.basename(path)}: {reason}")
    return documents


def chunk_corpus(
    documents: list[dict],
    strategy: str,
    counter: Any,
    max_tokens: int,
    overlap_tokens: int,
) -> tuple[list[dict], dict]:
    """Cắt toàn bộ corpus theo một chiến lược; trả về (chunks, thống_kê).

    `chunks` giữ đúng khuôn {"text","tier","source"} mà `VectorStoreManager` mong đợi,
    trong đó `source` là tên file — khóa để đối chiếu Hit@K với `source_document`
    của testbed.
    """
    chunks: list[dict] = []
    per_doc: list[tuple[str, str, int]] = []
    token_counts: list[int] = []
    oversized = 0

    for doc in documents:
        texts = chunk_with_strategy(
            strategy,
            doc["content"],
            doc_title=doc["title"],
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            token_counter=counter,
        )
        per_doc.append((doc["title"], doc["tier"], len(texts)))
        for text in texts:
            chunks.append({"text": text, "tier": doc["tier"], "source": doc["title"]})
            try:
                n_tokens = counter.count(text)
            except Exception:
                n_tokens = len(text.split())
            token_counts.append(n_tokens)
            if n_tokens > max_tokens:
                oversized += 1

    stats = {
        "n_documents": len(documents),
        "n_chunks": len(chunks),
        "mean_tokens": _mean(token_counts),
        "max_tokens": max(token_counts) if token_counts else 0,
        "n_oversized": oversized,
        "per_doc": per_doc,
    }
    return chunks, stats


def build_index(
    manager: VectorStoreManager,
    chunks: list[dict],
    strategy: str,
    log_dir: Path,
) -> tuple[Any, Path, float]:
    """Dựng ChromaDB ĐỘC LẬP cho một chiến lược rồi đo dung lượng chỉ mục.

    `VectorStoreManager` được tái sử dụng (bge-m3 chỉ nạp một lần cho cả 3 chiến lược)
    bằng cách trỏ `persist_directory` sang thư mục riêng trước khi tạo store — mỗi chiến
    lược vẫn có một chỉ mục vật lý tách biệt, đúng yêu cầu so sánh công bằng.
    """
    index_dir = log_dir / f"chroma_{strategy}"
    if index_dir.exists():
        try:
            shutil.rmtree(index_dir)
        except OSError as exc:
            raise SystemExit(
                f"Không xóa được chỉ mục cũ '{index_dir}' ({exc}). "
                "Hãy đóng tiến trình khác đang giữ ChromaDB rồi chạy lại."
            ) from exc

    manager.persist_directory = str(index_dir)
    collection = f"{COLLECTION_PREFIX}_{strategy}"
    vector_db = manager.create_vector_store(chunks, collection_name=collection)

    stored = 0
    try:
        stored = int(vector_db._collection.count())
    except Exception:
        stored = -1
    if 0 <= stored != len(chunks):
        raise SystemExit(
            f"Chỉ mục '{collection}' chứa {stored} chunk, kỳ vọng {len(chunks)} — "
            "không thể benchmark trên một chỉ mục sai lệch."
        )

    return vector_db, index_dir, dir_size_mb(index_dir)


# --------------------------------------------------------------------------- chấm điểm


def expected_citations_of(question: dict) -> set[str]:
    """Tập trích dẫn chuẩn của một câu, rút từ cả 2 trường ground truth của testbed.

    `expected_citations` có thể chứa chuỗi không phải trích dẫn ("1504", "1 lần/học kỳ");
    `extract_citations` tự bỏ qua chúng vì không khớp mẫu "Điều N [Khoản M]".
    """
    expected: set[str] = set()
    for item in question.get("expected_citations") or []:
        expected.update(extract_citations(str(item)))
    ground_truth = question.get("ground_truth_citation")
    if ground_truth:
        expected.update(extract_citations(str(ground_truth)))
    return expected


def evaluate_one(pipeline: HybridRAGPipeline, question: dict, top_k: int) -> dict:
    """Chạy MỘT câu qua pipeline sản xuất và tính toàn bộ chỉ số của câu đó.

    `pipeline.run(top_k)` tự nhân oversample_factor, nên cửa sổ generator là đúng top_k
    (mặc định 3) còn `sources` chứa top_k × 2 chunk — nhờ vậy đo được đồng thời
    Hit@3 (đúng cửa sổ generator), Hit@5 và Hit@6 (recall window) từ một lượt truy xuất.
    """
    expected_document = question.get("source_document")
    expected = expected_citations_of(question)

    t0 = time.perf_counter()
    result = pipeline.run(question["raw_query"], top_k=top_k)
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    sources: list[dict] = result["sources"]
    answer: str = result["answer"]

    hits = [source_match(s["source"], expected_document) for s in sources] if expected_document else []
    matched_rank = next((i + 1 for i, hit in enumerate(hits) if hit), None)

    predicted = extract_citations(answer)
    # KHÔNG truyền source_document vào citation_scores: nhánh rút gọn đó chấm 1.0 tuyệt đối
    # kể cả khi câu trả lời không trích dẫn gì, làm inflated Citation F1.
    scores = citation_scores(expected, predicted)

    retrieved = [
        {
            "rank": s["rank"],
            "score": rrf_rank_score(s["rank"]),
            "source": s["source"],
            "tier": s["tier"],
            "chunk_id": s["chunk_id"],
            "preview": _one_line(s.get("preview"), CHUNK_PREVIEW_CHARS),
            "fed_to_generator": s["rank"] <= top_k,
            "ground_truth_source": bool(hits[i]) if i < len(hits) else False,
        }
        for i, s in enumerate(sources)
    ]

    return {
        "id": question.get("id", "?"),
        "category": question.get("category", ""),
        "tier": question.get("tier", ""),
        "in_corpus": question.get("in_corpus", True),
        "raw_query": question["raw_query"],
        "normalized_query": result.get("normalized_query"),
        "source_document": expected_document,
        "ground_truth_answer": question.get("ground_truth_answer") or question.get("expected_answer"),
        "ground_truth_citation": question.get("ground_truth_citation"),
        "expected_citations": sorted(expected),
        "predicted_citations": sorted(predicted),
        "retrieved": retrieved,
        "answer": answer,
        "is_refusal": REFUSAL_MARKER in fold(answer),
        "hit_at_3": any(hits[:3]) if expected_document else None,
        "hit_at_5": any(hits[:5]) if expected_document else None,
        "hit_at_6": any(hits[:6]) if expected_document else None,
        "hit_at_k": any(hits[:top_k]) if expected_document else None,
        "matched_rank": matched_rank,
        "mrr": round(1.0 / matched_rank, 4) if matched_rank else 0.0,
        "citation_precision": scores["precision"],
        "citation_recall": scores["recall"],
        "citation_f1": scores["f1"],
        "citation_exact_match": scores["exact_match"],
        "latency_ms": latency_ms,
        "error": None,
    }


def error_entry(question: dict, exc: Exception, elapsed_ms: float) -> dict:
    """Bản ghi cho câu bị lỗi: giữ nguyên khung chỉ số để bảng tổng hợp không lệch dòng."""
    return {
        "id": question.get("id", "?"),
        "category": question.get("category", ""),
        "tier": question.get("tier", ""),
        "in_corpus": question.get("in_corpus", True),
        "raw_query": question.get("raw_query", ""),
        "normalized_query": None,
        "source_document": question.get("source_document"),
        "ground_truth_answer": question.get("ground_truth_answer") or question.get("expected_answer"),
        "ground_truth_citation": question.get("ground_truth_citation"),
        "expected_citations": sorted(expected_citations_of(question)),
        "predicted_citations": [],
        "retrieved": [],
        "answer": None,
        "is_refusal": False,
        "hit_at_3": None,
        "hit_at_5": None,
        "hit_at_6": None,
        "hit_at_k": None,
        "matched_rank": None,
        "mrr": None,
        "citation_precision": None,
        "citation_recall": None,
        "citation_f1": None,
        "citation_exact_match": None,
        "latency_ms": round(elapsed_ms, 1),
        "error": f"{type(exc).__name__}: {exc}",
    }


def aggregate(strategy: str, entries: list[dict], chunk_stats: dict,
              index_size_mb: float, total_time_s: float) -> dict:
    """Gộp chỉ số của toàn bộ câu hỏi thành một dòng báo cáo cho chiến lược đó."""
    scored = [e for e in entries if e["error"] is None]
    cited = [e for e in scored if e["citation_f1"] is not None]
    return {
        "strategy": strategy,
        "label": STRATEGY_LABELS.get(strategy, strategy),
        "n_total": len(entries),
        "n_ok": len(scored),
        "n_error": len(entries) - len(scored),
        "mean_hit_at_3": _mean([e["hit_at_3"] for e in scored]),
        "mean_hit_at_5": _mean([e["hit_at_5"] for e in scored]),
        "mean_hit_at_6": _mean([e["hit_at_6"] for e in scored]),
        "mean_mrr": _mean([e["mrr"] for e in scored]),
        "citation_precision": _mean([e["citation_precision"] for e in cited]),
        "citation_recall": _mean([e["citation_recall"] for e in cited]),
        "citation_f1": _mean([e["citation_f1"] for e in cited]),
        "citation_exact_match": _mean([e["citation_exact_match"] for e in cited]),
        "avg_latency_ms": _mean([e["latency_ms"] for e in scored]),
        "refusal_rate": _mean([1.0 if e["is_refusal"] else 0.0 for e in scored]),
        "total_chunks": chunk_stats["n_chunks"],
        "mean_chunk_tokens": chunk_stats["mean_tokens"],
        "max_chunk_tokens": chunk_stats["max_tokens"],
        "n_oversized_chunks": chunk_stats["n_oversized"],
        "index_size_mb": index_size_mb,
        "total_time_s": round(total_time_s, 1),
        "errors": [f"{e['id']}: {e['error']}" for e in entries if e["error"] is not None],
    }


# --------------------------------------------------------------------------- ghi log


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def log_header(strategy: str, params: dict, chunk_stats: dict, index_size_mb: float,
               collection: str, index_dir: Path, device_label: str) -> None:
    """Khối [HEADER]: ngày giờ chạy + toàn bộ tham số cố định của lượt thực nghiệm."""
    bm25_w = float(os.getenv("BM25_WEIGHT", "0.5"))
    vector_w = float(os.getenv("CHROMA_WEIGHT", "0.5"))
    logger.info(LINE)
    logger.info(f"[HEADER] BENCHMARK CHIẾN LƯỢC CHUNKING: {STRATEGY_LABELS.get(strategy, strategy).upper()}")
    logger.info(LINE)
    logger.info(f"  Ngày giờ chạy        : {params['timestamp']}")
    logger.info(f"  Chiến lược chunking  : {strategy}  (max_tokens={params['max_tokens']}, "
                f"overlap_tokens={params['overlap_tokens'] if strategy != 'structure' else 'không dùng'})")
    logger.info(f"  Tokenizer            : {params['tokenizer_name']}")
    logger.info(f"  Embedding model      : {EMBEDDING_MODEL} (normalize_embeddings=True, device={device_label})")
    logger.info(f"  Vector store         : ChromaDB · collection='{collection}' · {index_dir}")
    logger.info(f"  Corpus               : {chunk_stats['n_documents']} tài liệu từ {CORPUS_DIR}")
    logger.info(f"  Số chunk             : {chunk_stats['n_chunks']} "
                f"(mean {_num(chunk_stats['mean_tokens'], 1)} token, max {chunk_stats['max_tokens']}, "
                f"vượt ngưỡng {chunk_stats['n_oversized']})")
    logger.info(f"  Index Size           : {index_size_mb:.2f} MB")
    logger.info(f"  Retriever            : True Hybrid Search — BM25 w={bm25_w:.2f} + Chroma w={vector_w:.2f}, "
                f"RRF c={DEFAULT_RRF_C}")
    logger.info(f"  Top-K (generator)    : {params['top_k']}   ·   Retrieve-K (đo Hit@K) : "
                f"{params['top_k'] * OVERSAMPLE_FACTOR}   ·   Oversample factor : {OVERSAMPLE_FACTOR}")
    logger.info(f"  Generator            : {params['generator_model']} · temperature={params['temperature']:.2f} "
                f"· cache={'bật' if params['cache'] else 'TẮT'}")
    logger.info(f"  Local SLM            : {params['local_slm_model']} (chuẩn hóa câu hỏi) · {params['slm_status']}")
    logger.info(f"  Benchmark            : {params['benchmark']} · {params['n_questions']} câu")
    logger.info(f"  Quy ước Score        : điểm RRF dựng lại từ thứ hạng = 1/(c + rank), c={DEFAULT_RRF_C}")
    logger.info(f"  Quy ước Hit@K/MRR    : chunk đúng nguồn nếu tên file ground truth khớp 'source' (so khớp sau khi bỏ dấu)")
    logger.info(f"  Quy ước Citation     : Precision/Recall/F1 trên tập 'Điều N [Khoản M]', khớp Điều+Khoản=1.0, "
                f"trùng Điều một phía thiếu Khoản=0.5")
    logger.info("  Total Processing Time: xem [FOOTER SUMMARY] cuối file")
    logger.info(LINE)
    logger.info("")
    logger.info("[PHÂN BỐ CHUNK THEO TÀI LIỆU]")
    for title, tier, n in chunk_stats["per_doc"]:
        logger.info(f"  - [{tier}] {title}: {n} chunks")
    logger.info("")
    logger.info(SUBLINE)
    logger.info(f"[LOG CHI TIẾT CÂU HỎI] — {params['n_questions']} câu, "
                f"mỗi câu ghi Query & Ground Truth / Retrieved Chunks / Generated Answer / Chỉ số")
    logger.info(SUBLINE)


def log_question(index: int, total: int, entry: dict) -> None:
    """Khối log của MỘT câu hỏi: query, ground truth, chunk truy xuất, câu trả lời, chỉ số."""
    logger.info("")
    logger.info(SUBLINE)
    logger.info(f"[CÂU {index}/{total}] id={entry['id']} · category={entry['category']} · "
                f"tier={entry['tier']} · in_corpus={entry['in_corpus']}")
    logger.info(SUBLINE)
    logger.info(f"QUERY              : {_one_line(entry['raw_query'], 400)}")
    if entry.get("normalized_query") and entry["normalized_query"] != entry["raw_query"]:
        logger.info(f"QUERY (đã chuẩn hóa): {_one_line(entry['normalized_query'], 400)}")

    logger.info("GROUND TRUTH CONTEXT:")
    logger.info(f"  Nguồn kỳ vọng      : {entry['source_document'] or '(không khai báo)'}")
    logger.info("  Đáp án chuẩn       :")
    logger.info(_wrap(entry["ground_truth_answer"], GROUND_TRUTH_LOG_CHARS, indent="    "))
    logger.info("GROUND TRUTH CITATION:")
    logger.info(f"  Nguyên văn         : {_one_line(entry['ground_truth_citation'], 200)}")
    logger.info(f"  Tập dùng để chấm   : {entry['expected_citations'] or '(rỗng — không chấm Citation)'}")

    if entry["error"]:
        logger.info(f"ERROR              : {entry['error']}")
        logger.info(f"METRICS            : Hit@3=ERROR | MRR=ERROR | Citation_F1=ERROR | "
                    f"Latency={entry['latency_ms']} ms")
        return

    logger.info(f"RETRIEVED CHUNKS (Top-{len(entry['retrieved'])}; "
                f"{sum(1 for r in entry['retrieved'] if r['fed_to_generator'])} chunk đầu đưa vào generator):")
    for chunk in entry["retrieved"]:
        flag = "GEN" if chunk["fed_to_generator"] else "   "
        mark = "✓đúng nguồn" if chunk["ground_truth_source"] else " "
        logger.info(f"  #{chunk['rank']} [{flag}] score={chunk['score']:.6f} {mark} "
                    f"src={chunk['source']} · tier={chunk['tier']} · chunk_id={chunk['chunk_id']}")
        logger.info(f"        \"{chunk['preview']}\"")

    logger.info("GENERATED ANSWER:")
    logger.info(_wrap(entry["answer"], ANSWER_LOG_CHARS))
    if entry["is_refusal"]:
        logger.info("  (câu trả lời dạng TỪ CHỐI — ngữ cảnh không đủ căn cứ)")
    logger.info(f"  Trích dẫn hệ thống sinh ra : {entry['predicted_citations'] or '(không có)'}")

    logger.info(
        f"METRICS            : Hit@3={entry['hit_at_3']} | Hit@5={entry['hit_at_5']} | "
        f"MRR={_num(entry['mrr'])} (rank {entry['matched_rank'] or '—'}) | "
        f"Citation_P={_num(entry['citation_precision'])} | Citation_R={_num(entry['citation_recall'])} | "
        f"Citation_F1={_num(entry['citation_f1'])} | Latency={entry['latency_ms']} ms"
    )


def log_footer(agg: dict, params: dict, device_label: str) -> None:
    """Khối [FOOTER SUMMARY]: điểm trung bình toàn testbed của chiến lược này."""
    logger.info("")
    logger.info(LINE)
    logger.info(f"[FOOTER SUMMARY] — {agg['label']} (strategy='{agg['strategy']}')")
    logger.info(LINE)
    logger.info(f"  Số câu chấm được     : {agg['n_ok']}/{agg['n_total']}  (lỗi: {agg['n_error']})")
    logger.info(f"  Mean Hit@3           : {_pct(agg['mean_hit_at_3'])}")
    logger.info(f"  Mean Hit@5           : {_pct(agg['mean_hit_at_5'])}")
    logger.info(f"  Mean Hit@6           : {_pct(agg['mean_hit_at_6'])}")
    logger.info(f"  Mean MRR             : {_num(agg['mean_mrr'])}")
    logger.info(f"  Citation Precision   : {_num(agg['citation_precision'])}")
    logger.info(f"  Citation Recall      : {_num(agg['citation_recall'])}")
    logger.info(f"  Mean Citation_F1     : {_num(agg['citation_f1'])}")
    logger.info(f"  Citation Exact Match : {_num(agg['citation_exact_match'])}")
    logger.info(f"  Tỉ lệ từ chối        : {_pct(agg['refusal_rate'])}")
    logger.info(f"  Avg Latency          : {_num(agg['avg_latency_ms'], 1)} ms"
                f"{'  (cache BẬT — chưa phản ánh độ trễ thật)' if params['cache'] else ''}")
    logger.info("")
    logger.info("  [THAM SỐ HẠ TẦNG]")
    logger.info(f"  Tổng số chunk        : {agg['total_chunks']}")
    logger.info(f"  Mean chunk tokens    : {_num(agg['mean_chunk_tokens'], 1)}  ·  max {agg['max_chunk_tokens']}")
    logger.info(f"  Index Size           : {agg['index_size_mb']:.2f} MB")
    logger.info(f"  Embedding device     : {device_label}")
    logger.info(f"  Total Processing Time: {agg['total_time_s']} s "
                f"({agg['total_time_s'] / 60:.1f} phút) cho {agg['n_total']} câu")
    if agg["errors"]:
        logger.info("")
        logger.info("  [CÂU BỊ LỖI]")
        for line in agg["errors"]:
            logger.info(f"    - {line}")
    logger.info(LINE)


# --------------------------------------------------------------------------- báo cáo so sánh


def comparison_rows(aggregates: list[dict]) -> list[dict]:
    """Ma trận 3 dòng × 7 cột chỉ số chính, theo đúng thứ tự cột yêu cầu."""
    rows = []
    for agg in aggregates:
        rows.append({
            "Chiến lược": agg["strategy"],
            "Mean Hit@3": _num(agg["mean_hit_at_3"]),
            "Mean Hit@5": _num(agg["mean_hit_at_5"]),
            "Mean MRR": _num(agg["mean_mrr"]),
            "Citation Precision": _num(agg["citation_precision"]),
            "Citation Recall": _num(agg["citation_recall"]),
            "Citation F1": _num(agg["citation_f1"]),
            "Avg Latency (ms)": _num(agg["avg_latency_ms"], 1),
        })
    return rows


def infrastructure_rows(aggregates: list[dict]) -> list[dict]:
    """Bảng phụ: chỉ số hạ tầng phục vụ phần phân tích chi phí của bài báo."""
    rows = []
    for agg in aggregates:
        rows.append({
            "Chiến lược": agg["strategy"],
            "Total Chunks": agg["total_chunks"],
            "Mean Chunk Tokens": _num(agg["mean_chunk_tokens"], 1),
            "Max Chunk Tokens": agg["max_chunk_tokens"],
            "Index Size (MB)": f"{agg['index_size_mb']:.2f}",
            "Hit@6": _num(agg["mean_hit_at_6"]),
            "Citation Exact Match": _num(agg["citation_exact_match"]),
            "Số câu OK": f"{agg['n_ok']}/{agg['n_total']}",
            "Số câu lỗi": agg["n_error"],
            "Total Time (s)": f"{agg['total_time_s']:.1f}",
        })
    return rows


def _manual_markdown(rows: list[dict]) -> str:
    """Dựng bảng Markdown bằng stdlib khi thiếu pandas/tabulate."""
    if not rows:
        return "_(không có dữ liệu)_"
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def _write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    # utf-8-sig: Excel trên Windows nhận đúng tiếng Việt khi mở file CSV.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def write_comparison_report(aggregates: list[dict], log_dir: Path, meta: dict) -> tuple[Path, Path]:
    """Xuất `summary_comparison_report.csv` và `.md` — ma trận 3 chiến lược đặt cạnh nhau."""
    csv_path = log_dir / "summary_comparison_report.csv"
    md_path = log_dir / "summary_comparison_report.md"

    main_rows = comparison_rows(aggregates)
    infra_rows = infrastructure_rows(aggregates)

    if pd is not None:
        main_df = pd.DataFrame(main_rows)
        infra_df = pd.DataFrame(infra_rows)
        main_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        try:
            main_table = main_df.to_markdown(index=False)
            infra_table = infra_df.to_markdown(index=False)
        except Exception:  # thiếu 'tabulate'
            main_table = _manual_markdown(main_rows)
            infra_table = _manual_markdown(infra_rows)
        logger.info("")
        logger.info("[BẢNG SO SÁNH] Ma trận 3 chiến lược × 7 chỉ số:")
        logger.info("\n" + main_df.to_string(index=False))
    else:
        _write_csv(main_rows, csv_path)
        main_table = _manual_markdown(main_rows)
        infra_table = _manual_markdown(infra_rows)
        logger.info("")
        logger.info("[BẢNG SO SÁNH] (pandas chưa cài — bảng dựng bằng stdlib; "
                    "`pip install pandas tabulate` để có bảng căn cột đẹp hơn)")
        logger.info("\n" + main_table)

    md = "\n".join([
        "# So sánh 3 chiến lược chunking — Hybrid RAG quy chế ĐHAG",
        "",
        f"Benchmark: `{meta['benchmark']}` · {meta['n_questions']} câu · "
        f"Top-K (generator) = {meta['top_k']} · Retrieve-K = {meta['top_k'] * OVERSAMPLE_FACTOR} · "
        f"max_tokens = {meta['max_tokens']} · overlap = {meta['overlap_tokens']}",
        "",
        f"Embedding: `{EMBEDDING_MODEL}` · Generator: `{meta['generator_model']}` "
        f"(temperature = {meta['temperature']:.2f}) · Local SLM: `{meta['local_slm_model']}` · "
        f"Retriever: BM25 + Chroma gộp RRF (c = {DEFAULT_RRF_C})",
        "",
        f"Chạy lúc: {meta['timestamp']} · Thiết bị nhúng: {meta['device']} · "
        f"Cache sinh chữ: {'bật' if meta['cache'] else 'tắt'} · pandas: "
        f"{'có' if pd is not None else 'không (fallback stdlib)'}",
        "",
        "## Ma trận chỉ số chính (3 chiến lược × 7 chỉ số)",
        "",
        main_table,
        "",
        "## Chỉ số hạ tầng",
        "",
        infra_table,
        "",
        "## Quy ước chấm điểm",
        "",
        "- **Hit@K**: Top-K chunk truy xuất có chứa ít nhất một chunk thuộc `source_document` "
        "ground truth hay không (so khớp tên file sau khi bỏ dấu thanh, vì OCR làm sai lệch tên).",
        "- **MRR**: nghịch đảo thứ hạng của chunk đúng nguồn đầu tiên trong toàn bộ recall "
        f"window ({meta['top_k'] * OVERSAMPLE_FACTOR} chunk), không cắt ở Top-K generator.",
        "- **Citation P/R/F1**: so tập mã \"Điều N [Khoản M]\" hệ thống trích ra với tập rút từ "
        "`ground_truth_citation` + `expected_citations`; khớp đủ Điều+Khoản = 1.0, trùng Điều mà "
        "một phía không ghi Khoản = 0.5; ghép cặp theo maximum-weight matching.",
        "- **Latency**: thời gian end-to-end của một câu (chuẩn hóa Qwen + truy xuất hybrid + sinh chữ).",
        "",
    ])
    md_path.write_text(md, encoding="utf-8")
    return csv_path, md_path


# --------------------------------------------------------------------------- vòng lặp chính


def build_generator(args: argparse.Namespace) -> tuple[Any, str, str]:
    """Dựng generator theo `--generator`; luôn khóa temperature=0 như yêu cầu thực nghiệm."""
    if args.generator == "qwen":
        generator = QwenGenerator(temperature=args.temperature)
        generator.use_cache = not args.no_cache
        return generator, generator.model_name, "Qwen local (Ollama) — chạy offline"
    generator = GeminiGenerator(temperature=args.temperature)
    generator.use_cache = not args.no_cache
    # Tắt fallback Qwen: nếu để bật, các câu hết quota sẽ âm thầm trả lời bằng model khác,
    # khiến 3 chiến lược bị chấm trên những generator không đồng nhất.
    generator.qwen_fallback = False
    return generator, generator.model_name, f"Gemini API ({generator.model_name})"


def build_token_counter(args: argparse.Namespace) -> tuple[Any, str]:
    if args.tokenizer == "whitespace":
        return WhitespaceTokenCounter(), "Whitespace (đếm từ)"
    counter = get_token_counter(EMBEDDING_MODEL)
    return counter, f"{type(counter).__name__} '{getattr(counter, 'name', EMBEDDING_MODEL)}'"


def load_previous_results(log_dir: Path, compat: dict) -> dict[str, dict]:
    """Đọc `results_all.json` của lượt chạy trước để gộp vào báo cáo khi chạy tách lệnh.

    Trả về dict rỗng nếu file chưa tồn tại, hỏng JSON, hoặc tham số thí nghiệm khác
    lượt trước (benchmark, top-k, max-tokens, generator, device…) — khi đó báo cáo
    mới chỉ chứa các chiến lược của lượt hiện tại, tránh trộn số liệu không đồng nhất.
    """
    path = log_dir / "results_all.json"
    if not path.exists():
        return {}
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        old_meta = previous.get("meta") or {}
        mismatched = [k for k, v in compat.items() if old_meta.get(k) != v]
        if mismatched:
            logger.info("[Merge] Bỏ qua kết quả cũ trong results_all.json vì tham số khác: "
                        + ", ".join(mismatched))
            return {}
        strategies = previous.get("strategies") or {}
        return strategies if isinstance(strategies, dict) else {}
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        logger.info(f"[Merge] Không đọc được results_all.json cũ ({type(exc).__name__}) — bỏ qua.")
        return {}


def run_strategy(strategy: str, args: argparse.Namespace, documents: list[dict],
                 counter: Any, tokenizer_name: str, manager: VectorStoreManager,
                 local_slm: LocalSLM, generator: Any, generator_model: str,
                 questions: list[dict], log_dir: Path, device_label: str) -> dict:
    """Chạy trọn một chiến lược: chunking → index → 50 câu → log → aggregate."""
    log_path = log_dir / STRATEGY_LOG_NAMES[strategy]
    collection = f"{COLLECTION_PREFIX}_{strategy}"
    strategy_t0 = time.perf_counter()

    logger.info("")
    logger.info(LINE)
    logger.info(f"[{strategy.upper()}] Bắt đầu: chunking {len(documents)} tài liệu "
                f"(max_tokens={args.max_tokens}, overlap={args.overlap_tokens})…")
    logger.info(LINE)

    chunks, chunk_stats = chunk_corpus(documents, strategy, counter, args.max_tokens, args.overlap_tokens)
    logger.info(f"[{strategy.upper()}] Đã cắt {chunk_stats['n_chunks']} chunk "
                f"(mean {_num(chunk_stats['mean_tokens'], 1)} token, max {chunk_stats['max_tokens']}, "
                f"vượt ngưỡng {chunk_stats['n_oversized']}). Đang nhúng {EMBEDDING_MODEL}…")

    vector_db, index_dir, index_size_mb = build_index(manager, chunks, strategy, log_dir)
    logger.info(f"[{strategy.upper()}] Index sẵn sàng: {index_dir} · {index_size_mb:.2f} MB · "
                f"collection='{collection}'")

    pipeline = HybridRAGPipeline(
        vector_db=vector_db,
        local_slm=local_slm,
        generator=generator,
        oversample_factor=OVERSAMPLE_FACTOR,
        use_hybrid=True,
    )

    params = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "max_tokens": args.max_tokens,
        "overlap_tokens": args.overlap_tokens,
        "tokenizer_name": tokenizer_name,
        "top_k": args.top_k,
        "generator_model": generator_model,
        "temperature": args.temperature,
        "cache": not args.no_cache,
        "local_slm_model": local_slm.model_name,
        "slm_status": args._slm_status,
        "benchmark": str(args.benchmark),
        "n_questions": len(questions),
    }

    entries: list[dict] = []
    aborted = False
    with strategy_log_file(log_path):
        log_header(strategy, params, chunk_stats, index_size_mb, collection, index_dir, device_label)

        for index, question in enumerate(questions, start=1):
            logger.info("")
            logger.info(f"[{strategy.upper()}] ({index}/{len(questions)}) {question.get('id', '?')}: "
                        f"{_one_line(question['raw_query'], 90)}")
            t0 = time.perf_counter()
            try:
                entry = evaluate_one(pipeline, question, args.top_k)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                entry = error_entry(question, exc, (time.perf_counter() - t0) * 1000)
                logger.info(f"[{strategy.upper()}] ERROR câu {question.get('id', '?')}: {entry['error']}")
                if is_quota_error(exc) or "perday" in str(exc).lower():
                    logger.info(f"[{strategy.upper()}] Gemini hết quota NGÀY — dừng sớm, "
                                f"ghi báo cáo {len(entries)} câu đã chạy.")
                    entries.append(entry)
                    aborted = True
                    break
            entries.append(entry)
            log_question(index, len(questions), entry)

        total_time = time.perf_counter() - strategy_t0
        agg = aggregate(strategy, entries, chunk_stats, index_size_mb, total_time)
        log_footer(agg, params, device_label)

    logger.info(f"[{strategy.upper()}] Đã ghi log chi tiết: {log_path}")
    agg["aborted_by_quota"] = aborted
    return {"aggregate": agg, "questions": entries, "params": params}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark 3 chiến lược chunking trên testbed quy chế AGU, xuất log + báo cáo so sánh.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK,
                        help="File JSON testbed (danh sách 'questions' có trường 'raw_query').")
    parser.add_argument("--limit", type=int, default=None,
                        help="Chỉ chạy N câu đầu (smoke test). Mặc định chạy hết.")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Số chunk đưa vào generator (Top-K của Retriever).")
    parser.add_argument("--strategies", nargs="+", default=list(STRATEGY_LOG_NAMES),
                        choices=list(STRATEGY_LOG_NAMES),
                        help="Chiến lược cần benchmark, chạy theo thứ tự khai báo.")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
                        help="Ngưỡng token của mỗi chunk.")
    parser.add_argument("--overlap-tokens", type=int, default=DEFAULT_OVERLAP_TOKENS,
                        help="Số token chồng lấp (chỉ áp dụng cho fixed/recursive).")
    parser.add_argument("--tokenizer", choices=("auto", "hf", "whitespace"), default="auto",
                        help="Tokenizer đếm token; 'auto'/'hf' dùng HuggingFace, lỗi thì lùi về whitespace.")
    parser.add_argument("--generator", choices=("gemini", "qwen"), default="gemini",
                        help="LLM sinh câu trả lời. 'qwen' chạy hoàn toàn offline, không tốn quota Gemini.")
    parser.add_argument("--temperature", type=float, default=0.0,
                        help="Temperature của generator (thực nghiệm yêu cầu 0).")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu",
                        help="Thiết bị nhúng bge-m3; 'cuda' cho Colab GPU T4.")
    parser.add_argument("--logs-dir", type=Path, default=DEFAULT_LOG_DIR,
                        help="Thư mục xuất log và chỉ mục ChromaDB tạm.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Tắt cache sinh chữ để đo Latency trung thực (tốn quota hơn).")
    args = parser.parse_args()
    args.top_k = max(1, args.top_k)
    if args.overlap_tokens >= args.max_tokens:
        parser.error(f"--overlap-tokens ({args.overlap_tokens}) phải nhỏ hơn --max-tokens ({args.max_tokens}).")
    return args


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    setup_logger()
    args = parse_args()

    run_started = datetime.now()
    log_dir: Path = args.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    questions = load_benchmark(args.benchmark)
    if args.limit:
        questions = questions[: max(1, args.limit)]
    n_questions = len(questions)

    logger.info(LINE)
    logger.info("BENCHMARK & LOGGING PIPELINE — SO SÁNH CHIẾN LƯỢC CHUNKING")
    logger.info(LINE)
    logger.info(f"  Benchmark      : {args.benchmark} · {n_questions} câu")
    logger.info(f"  Chiến lược     : {', '.join(args.strategies)}")
    logger.info(f"  Top-K          : {args.top_k} (generator) · {args.top_k * OVERSAMPLE_FACTOR} (recall window)")
    logger.info(f"  Chunk          : max_tokens={args.max_tokens}, overlap_tokens={args.overlap_tokens}")
    logger.info(f"  Generator      : {args.generator} · temperature={args.temperature:.2f} · "
                f"cache={'TẮT' if args.no_cache else 'bật'}")
    logger.info(f"  Thư mục log    : {log_dir.resolve()}")
    logger.info(f"  pandas         : {'có' if pd is not None else 'KHÔNG (fallback stdlib)'}")
    if args.generator == "gemini" and not args.no_cache:
        logger.info(f"  Ước tính       : tối đa {n_questions * len(args.strategies)} lần gọi Gemini "
                    f"({n_questions} câu × {len(args.strategies)} chiến lược) — kiểm tra quota trước khi chạy.")
    logger.info("")

    counter, tokenizer_name = build_token_counter(args)
    logger.info(f"[Setup] Tokenizer: {tokenizer_name}")

    documents = load_corpus()
    logger.info(f"[Setup] Đã nạp {len(documents)} tài liệu từ {CORPUS_DIR} "
                f"({sum(len(d['content']) for d in documents):,} ký tự).")

    local_slm = LocalSLM()
    ok, message = local_slm.check_connection()
    args._slm_status = message
    logger.info(f"[Setup] Local SLM: {message}" if ok else f"[Setup] CẢNH BÁO Local SLM: {message}")

    generator, generator_model, generator_label = build_generator(args)
    logger.info(f"[Setup] Generator: {generator_label} · temperature={args.temperature:.2f}")

    manager = VectorStoreManager()
    device_label = apply_device(manager, args.device)
    logger.info(f"[Setup] Embedding: {EMBEDDING_MODEL} trên {device_label}")
    logger.info("")

    results: dict[str, dict] = {}
    try:
        for strategy in args.strategies:
            payload = run_strategy(
                strategy, args, documents, counter, tokenizer_name, manager,
                local_slm, generator, generator_model, questions, log_dir, device_label,
            )
            results[strategy] = payload
            if payload["aggregate"].get("aborted_by_quota"):
                logger.info("[Benchmark] Dừng các chiến lược còn lại vì hết quota Gemini. "
                            "Chạy lại với --generator qwen hoặc chờ quota reset (~14:00 giờ VN = 07:00 UTC).")
                break
    except KeyboardInterrupt:
        logger.info("")
        logger.info("[Benchmark] Nhận Ctrl+C — ghi báo cáo cho các chiến lược đã chạy xong.")

    # Gộp kết quả các chiến lược đã chạy ở LƯỢT TRƯỚC (cùng tham số) vào báo cáo, để chạy
    # tách từng chiến lược bằng nhiều lệnh riêng vẫn ra đủ ma trận 3 dòng × 7 chỉ số.
    compat = {
        "benchmark": str(args.benchmark),
        "n_questions": n_questions,
        "top_k": args.top_k,
        "max_tokens": args.max_tokens,
        "overlap_tokens": args.overlap_tokens,
        "tokenizer": tokenizer_name,
        "generator_model": generator_model,
        "device": device_label,
        "cache": not args.no_cache,
    }
    previous = load_previous_results(log_dir, compat)
    merged_from_previous = [s for s in previous if s not in results]
    for strategy in merged_from_previous:
        results[strategy] = previous[strategy]
    aggregates = [results[s]["aggregate"] for s in STRATEGY_LOG_NAMES if s in results]

    meta = {
        "timestamp": run_started.strftime("%Y-%m-%d %H:%M:%S"),
        "benchmark": str(args.benchmark),
        "n_questions": n_questions,
        "top_k": args.top_k,
        "max_tokens": args.max_tokens,
        "overlap_tokens": args.overlap_tokens,
        "tokenizer": tokenizer_name,
        "generator_model": generator_model,
        "temperature": args.temperature,
        "local_slm_model": local_slm.model_name,
        "device": device_label,
        "cache": not args.no_cache,
        "strategies_completed": [a["strategy"] for a in aggregates],
        "strategies_requested": list(args.strategies),
        "merged_from_previous": merged_from_previous,
        "total_time_s": round((datetime.now() - run_started).total_seconds(), 1),
    }

    if aggregates:
        csv_path, md_path = write_comparison_report(aggregates, log_dir, meta)
        results_path = log_dir / "results_all.json"
        results_path.write_text(
            json.dumps({"meta": meta, "strategies": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("")
        logger.info(LINE)
        logger.info("[HOÀN TẤT] Đã xuất:")
        for strategy in meta["strategies_completed"]:
            logger.info(f"  - {log_dir / STRATEGY_LOG_NAMES[strategy]}")
        logger.info(f"  - {csv_path}")
        logger.info(f"  - {md_path}")
        logger.info(f"  - {results_path}")
        logger.info(f"  Tổng thời gian thực nghiệm: {meta['total_time_s']} s")
        logger.info(LINE)
    else:
        logger.info("[Benchmark] Không có chiến lược nào chạy xong — không xuất báo cáo so sánh.")


if __name__ == "__main__":
    main()
