"""T1 — ablation tầng sinh: tách "năng lực model" khỏi "chất lượng ngữ cảnh/corpus".

Chạy trên ĐÚNG 100 item pha sinh của r5 (cùng id, lấy thứ tự từ
`data/loop/rounds/r5/full.jsonl`) và chấm bằng ĐÚNG trọng tài hiện tại
(`tools/loop/verify.py::score_item`, chữ ký `9f1179ccab74`). Không sửa code sản
xuất; script chỉ ĐỌC round cũ + gọi generator.

Ba cấu hình (mỗi cái một thư mục `data/loop/diag/<name>/`):

  a_oracle_qwen     Qwen + CHỈ chunk vàng làm ngữ cảnh (oracle truy xuất)
                    -> TRẦN của generator: căn cứ hoàn hảo, thiếu gì thì tại model.
                    Item không có chunk vàng duy nhất (HUMAN/REFUSE_*) bị LOẠI và
                    ghi danh sách — oracle không tồn tại cho chúng.

  b_gemini_top6     Gemini + top-6 hiện tại của r5 (cùng câu hỏi/nhãn)
                    -> HIỆU ỨNG NĂNG LỰC MODEL: đổi mỗi model, giữ nguyên ngữ cảnh.
                    QWEN_FALLBACK=0 được ép trong script: lỗi Gemini PHẢI thành
                    dòng ERROR, không được lén tráo thành Qwen (nhiễm phép đo).

  c_gold_window_qwen Qwen + gold_sentence kèm 2 câu lân cận (cửa sổ ngắn)
                    -> HIỆU ỨNG ĐỘ DÀI NGỮ CẢNH: cùng model, căn cứ vẫn nguyên
                    nhưng corpus cắt nhỏ.

Ghép một biến với baseline: cả ba chạy `ENABLE_ANSWER_RESCUE` TẮT (lever đã bị bác
ở r5b — chênh so với r5 đúng ≤1 câu cứu, ghi ở summary), guard = env của người chạy
(khuyến nghị `ENABLE_ANSWER_GUARD=1` như r5). Câu hỏi và nhãn lấy nguyên từ r5 đã lưu
(`normalized_query`, `labels.question_type`) để KHÔNG đổi gì ngoài ngữ cảnh/model.

Lệnh tái lập (xem docstring cuối file):
    ENABLE_ANSWER_GUARD=1 ./venv/Scripts/python.exe tools/diag/ablation_generation.py \
        --config a_oracle_qwen [--limit 5] [--dry-run]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:  # nạp GEMINI_API_KEY v.v. từ .env — cùng cách các entrypoint của repo
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

from src.generator import (  # noqa: E402
    GeminiGenerator,
    GeneratorError,
    QwenGenerator,
)
from src.text_utils import fold  # noqa: E402
from tools.loop import verify  # noqa: E402  (trọng tài hiện tại — KHÔNG sửa)

BASE_ROUND = "r5"
ROUNDS_DIR = ROOT / "data" / "loop" / "rounds"
DIAG_DIR = ROOT / "data" / "loop" / "diag"
TESTSET = ROOT / "data" / "loop" / "testset_v1.jsonl"

CONFIG_NAMES = ("a_oracle_qwen", "b_gemini_top6", "c_gold_window_qwen")

ENV_SNAPSHOT_KEYS = (
    "ENABLE_ANSWER_GUARD",
    "ANSWER_GUARD_MIN_SCORE",
    "ANSWER_GUARD_MAX_UNSUPPORTED",
    "ENABLE_ANSWER_RESCUE",
    "RESCUE_MIN_SCORE",
    "QWEN_FALLBACK",
    "GEMINI_MODEL",
    "USE_QWEN_GENERATOR",
)


# --------------------------------------------------------------------------- dữ liệu

def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_base_rows() -> list[dict]:
    """100 dòng r5/full.jsonl theo đúng thứ tự pin của round."""
    return load_jsonl(ROUNDS_DIR / BASE_ROUND / "full.jsonl")


def load_items() -> dict[str, dict]:
    return {row["id"]: row for row in load_jsonl(TESTSET)}


def load_chunks() -> dict[int, dict]:
    """chunk_id -> chunk (nguyên văn qua build_training_data.load_chunks, cùng nguồn
    mà testset.py đã dùng để neo bằng chứng)."""
    spec = importlib.util.spec_from_file_location(
        "btd_diag", str(ROOT / "tools" / "build_training_data.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["btd_diag"] = module  # dataclass trong module cần tra cứu sys.modules
    spec.loader.exec_module(module)
    return {c["chunk_id"]: c for c in module.load_chunks()}


def sentence_split(text: str) -> list[str]:
    """Cùng luật tách câu với testset.py (nơi gold_sentence được chọn)."""
    parts = re.split(r"(?<=[\.;:])\s+", text)
    return [p.strip() for p in parts if p and len(p.strip()) >= 25]


# --------------------------------------------------------------------------- docs theo config

def docs_for(config: str, row: dict, item: dict, chunks: dict[int, dict]) -> tuple[Optional[list[dict]], Optional[str]]:
    """Trả (docs, skip_reason). docs theo đúng schema normalize_docs: content/source/tier/chunk_id."""
    question_contexts = row.get("contexts") or []
    sources = row.get("sources") or []

    if config == "b_gemini_top6":
        top = sources[: len(question_contexts)] or sources[:6]
        docs = []
        for i, content in enumerate(question_contexts):
            meta = top[i] if i < len(top) else {}
            docs.append({
                "content": content,
                "source": meta.get("source", ""),
                "tier": meta.get("tier", "Khác"),
                "chunk_id": meta.get("chunk_id", i),
            })
        return docs, None

    gold_id = item.get("gold_chunk_id")
    if gold_id is None:
        return None, "no_gold_chunk"
    chunk = chunks.get(gold_id)
    if chunk is None:
        return None, "gold_chunk_missing_in_index"

    if config == "a_oracle_qwen":
        return [{
            "content": chunk["text"],
            "source": chunk["source"],
            "tier": chunk["tier"],
            "chunk_id": chunk["chunk_id"],
        }], None

    # c_gold_window_qwen — gold_sentence + đúng 2 câu lân cận (1 trước, 1 sau)
    body = chunk.get("body") or chunk["text"]
    sentences = sentence_split(body)
    fgs = fold(item.get("gold_sentence") or "")
    idx = next((i for i, s in enumerate(sentences) if fgs and fgs in fold(s)), None)
    if idx is None:
        return None, "gold_sentence_not_in_sentences"
    window = sentences[max(0, idx - 1): idx + 2]
    return [{
        "content": "\n".join(window),
        "source": chunk["source"],
        "tier": chunk["tier"],
        "chunk_id": chunk["chunk_id"],
    }], None


# --------------------------------------------------------------------------- chạy

def make_generator(config: str, cache_dir: Path):
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["GENERATION_CACHE_DIR"] = str(cache_dir)
    if config == "b_gemini_top6":
        # Ép không fallback: một dòng ANSWER từ Qwen lọt vào bảng Gemini là nhiễm đo.
        os.environ["QWEN_FALLBACK"] = "0"
        return GeminiGenerator()
    return QwenGenerator()


def build_result(row: dict, docs: list[dict], answer: str, latency: float) -> dict:
    """Shape tối thiểu mà verify.score_item cần (theo src/pipeline.py::run)."""
    return {
        "answer": answer,
        "contexts": [d["content"] for d in docs],
        "sources": [
            {"rank": i + 1, "source": d["source"], "tier": d["tier"], "chunk_id": d["chunk_id"]}
            for i, d in enumerate(docs)
        ],
        "labels": row.get("labels"),
        "latency_seconds": latency,
    }


def run_config(config: str, limit: Optional[int], dry_run: bool,
               ids_file: Optional[Path] = None, force: bool = False) -> Path:
    out_dir = DIAG_DIR / config
    rows_path = out_dir / "rows.jsonl"
    # An toàn thư mục (ca #5): thư mục diag ĐÃ có kết quả thì không tự ý ghi tiếp/đè —
    # phải nói rõ bằng --force. (Resume có chủ đích = cho phép, nhưng là lựa chọn tường minh.)
    if rows_path.exists() and not force:
        raise SystemExit(
            f"[out] {out_dir} đã có rows.jsonl; thêm --force để chạy tiếp (resume) vào cùng thư mục."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows = load_jsonl(rows_path) if rows_path.exists() else []
    # Chỉ dòng CÓ KẾT QUẢ được tính là xong; dòng error phải được thử lại khi resume
    # (quota Gemini theo ngày — PerDay là chuyện thường, không phải hết item).
    done = {r["id"] for r in all_rows if not r.get("error")}

    base_rows = load_base_rows()
    # Cùng tập item (ca #2): full.jsonl là nguồn thứ tự chạy, verdicts_full.jsonl là tập
    # đã chấm của r5. Thêm/bớt một id ở full.jsonl => lệch tập đo giữa (a)/(b)/(c) và r5
    # => từ chối kèm tên id, không chạy tiếp trên một tập khác.
    verdicts_path = ROUNDS_DIR / BASE_ROUND / "verdicts_full.jsonl"
    if verdicts_path.exists():
        verdict_ids = {r["id"] for r in load_jsonl(verdicts_path)}
        base_ids = {r["id"] for r in base_rows}
        extra = sorted(base_ids - verdict_ids)
        missing = sorted(verdict_ids - base_ids)
        if extra or missing:
            raise SystemExit(
                f"[ids] tập item KHÔNG khớp {BASE_ROUND}/verdicts_full.jsonl: "
                f"thừa={extra[:5]} thiếu={missing[:5]}"
            )
    if ids_file is not None:
        # (b) theo điều đăng ký trước: chỉ chạy đúng danh sách id đã chốt TRƯỚC khi gọi.
        allow = set(json.loads(ids_file.read_text(encoding="utf-8"))["ids"])
        unknown = sorted(allow - {r["id"] for r in base_rows})
        if unknown:
            raise SystemExit(f"[ids] id KHÔNG thuộc 100 item r5: {unknown[:5]}")
        base_rows = [r for r in base_rows if r["id"] in allow]
        print(f"[ids] {len(base_rows)}/{len(allow)} id từ {ids_file}")
    items = load_items()
    chunks = load_chunks()
    todo = []
    skipped: list[dict[str, str]] = []
    for row in base_rows:
        item = items[row["id"]]
        docs, reason = docs_for(config, row, item, chunks)
        if reason:
            skipped.append({"id": row["id"], "family": item.get("family"), "reason": reason})
            continue
        if row["id"] not in done:
            todo.append((row, item, docs))
    if limit is not None:
        todo = todo[:limit]

    settings = {
        "config": config,
        "base_round": BASE_ROUND,
        "referee": verify.referee_fingerprint(),
        "env": {k: os.environ.get(k) for k in ENV_SNAPSHOT_KEYS},
        "n_base_items": len(base_rows),
        "n_skipped": len(skipped),
        "skipped_items": skipped,
        "ids_file": str(ids_file) if ids_file else None,
        "question_and_labels_source": "normalized_query + labels.question_type của r5 (đã lưu)",
        "rescue_note": "ENABLE_ANSWER_RESCUE để TẮT (lever đã bác ở r5b; r5 chạy BẬT, chênh ≤1 câu cứu)",
    }
    (out_dir / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if dry_run:
        for row, item, docs in todo[:3]:
            print(f"[dry] {row['id']} ({item.get('family')}): {len(docs)} block, "
                  f"{sum(len(d['content']) for d in docs)} ký tự ngữ cảnh")
        print(f"[dry] {config}: todo={len(todo)} skipped={len(skipped)} — không gọi model.")
        return out_dir

    generator = make_generator(config, out_dir / "cache")
    started = len(done)
    with rows_path.open("a", encoding="utf-8") as sink:
        for n, (row, item, docs) in enumerate(todo, start=1):
            t0 = time.time()
            question = row.get("normalized_query") or item.get("raw_query") or ""
            qtype = (row.get("labels") or {}).get("question_type")
            try:
                answer = generator.generate_answer(
                    query=question,
                    retrieved_docs=docs,
                    question_type=qtype,
                    raw_query=item.get("raw_query"),
                )
                error = None
            except GeneratorError as exc:
                answer, error = None, f"{type(exc).__name__}: {exc}"
            except Exception as exc:  # lỗi bất kỳ cũng phải thành dòng, không rơi round
                answer, error = None, f"{type(exc).__name__}: {exc}"
            latency = round(time.time() - t0, 2)
            if error:
                rec = {"id": row["id"], "error": error, "latency_seconds": latency}
            else:
                verdict = verify.score_item(item, build_result(row, docs, answer, latency), top_k=6)
                rec = {**verdict, "answer": answer, "n_docs": len(docs),
                       "context_chars": sum(len(d["content"]) for d in docs)}
            sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
            sink.flush()
            print(f"[{config}] {started + n}/{len(base_rows)} {row['id']}: "
                  f"{rec.get('verdict') or rec.get('error')} ({latency}s)")
    return out_dir


# --------------------------------------------------------------------------- tóm tắt

def summarize(config: str) -> dict:
    out_dir = DIAG_DIR / config
    rows = [r for r in load_jsonl(out_dir / "rows.jsonl") if not r.get("error")] if (out_dir / "rows.jsonl").exists() else []
    errors = [r for r in load_jsonl(out_dir / "rows.jsonl") if r.get("error")] if (out_dir / "rows.jsonl").exists() else []
    settings = json.loads((out_dir / "settings.json").read_text(encoding="utf-8")) if (out_dir / "settings.json").exists() else {}
    skipped = settings.get("skipped_items", [])

    def block(subset: list[dict]) -> dict:
        decided = [r for r in subset if r.get("verdict") != "PENDING_GENERATION"]
        if not decided:
            return {"n": 0}
        answered = [r for r in decided if not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0]
        return {
            "n": len(decided),
            "n_answered": len(answered),
            "refusal_rate": round(sum(1 for r in decided if r.get("is_refusal")) / len(decided), 4),
            "pass_correct": sum(1 for r in decided if r.get("verdict") == "PASS_CORRECT"),
            "pass_correct_rate": round(sum(1 for r in decided if r.get("verdict") == "PASS_CORRECT") / len(decided), 4),
            "pass_any_rate": round(sum(1 for r in decided if r.get("verdict") in verify.PASS_VERDICTS) / len(decided), 4),
            "fabrication_rate_on_answered": (
                round(sum(1 for r in answered if r.get("unsupported")) / len(answered), 4) if answered else None
            ),
            "fabricated_items": sum(1 for r in decided if r.get("verdict") == "FAIL_FABRICATED"),
            "hallucinated_on_unanswerable": sum(1 for r in decided if r.get("verdict") == "FAIL_HALLUCINATED_ON_UNANSWERABLE"),
            "overrefusal": sum(1 for r in decided if r.get("verdict") == "FAIL_OVERREFUSAL"),
            "verdict_counts": dict(__import__("collections").Counter(r.get("verdict") for r in decided)),
            "median_latency": (
                round(sorted(r.get("latency_seconds") or 0 for r in decided)[len(decided) // 2], 2)
                if decided else None
            ),
        }

    families = sorted({r.get("family") for r in rows if r.get("family")})
    summary = {
        "config": config,
        "referee": settings.get("referee"),
        "env": settings.get("env"),
        "n_rows": len(rows),
        "n_errors": len(errors),
        "errors": errors[:20],
        "n_skipped_no_gold": len(skipped),
        "overall": block(rows),
        "overall_answerable80": block([r for r in rows if r.get("has_gold_chunk")]),
        "by_family": {fam: block([r for r in rows if r.get("family") == fam]) for fam in families},
    }

    # CI 95% (bootstrap 10.000 lượt, seed cố định — cùng chuẩn T0) cho 3 chỉ số chính
    # trên tập answerable (cùng mẫu số với a/c).
    from tools.loop.noise_floor import BOOTSTRAP_SEED, rate_ci  # noqa: WPS433

    subset = [r for r in rows if r.get("has_gold_chunk")]
    if subset:
        pc = [1 if r.get("verdict") == "PASS_CORRECT" else 0 for r in subset]
        rf = [1 if r.get("is_refusal") else 0 for r in subset]
        fab = [1 if (not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0 and r.get("unsupported")) else 0 for r in subset]
        fden = [1 if (not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0) else 0 for r in subset]
        summary["ci95_answerable"] = {
            "pass_correct": rate_ci(pc, [1] * len(subset), seed=BOOTSTRAP_SEED),
            "refusal_rate": rate_ci(rf, [1] * len(subset), seed=BOOTSTRAP_SEED),
            "fabrication_rate_on_answered": rate_ci(fab, fden, seed=BOOTSTRAP_SEED),
        }

    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


# ------------------------------------------------------------------- bảng quyết định (đăng ký trước)
# Điều kiện định tính ĐÃ đăng ký ở `data/loop/README.md` mục "Ablation tầng sinh T1":
#   (a) cao            -> bỏ (b); nút thắt là CHỌN/ĐỘ DÀI ngữ cảnh      -> ưu tiên T3
#   (a) thấp + (b) cao -> năng lực model (Qwen không trích xuất được)   -> ưu tiên T4
#   (a) thấp + (b) thấp -> trọng tài hoặc corpus                        -> ưu tiên T2+T6
#   số SÁT ngưỡng       -> "không kết luận được" (KHÔNG bẻ nhánh theo số nhiễu)
# README chỉ chốt hướng, không chốt con số; các ngưỡng số dưới đây là tham số minh
# bạch để hàm diễn giải tái lập được và mutation-check bắt được (không đổi ý nghĩa nhánh).
T1_A_PASS_THRESHOLD = 0.15
T1_B_PASS_THRESHOLD = 0.30
T1_BAND = 0.02  # vùng "sát ngưỡng": |rate - ngưỡng| <= BAND => không kết luận được


def _side_of(value: float, threshold: float, band: float) -> str:
    if value >= threshold + band:
        return "high"
    if value < threshold - band:
        return "low"
    return "near"


def interpret_decision(
    a_pass_rate: Optional[float],
    b_pass_rate: Optional[float] = None,
    *,
    a_threshold: float = T1_A_PASS_THRESHOLD,
    b_threshold: float = T1_B_PASS_THRESHOLD,
    band: float = T1_BAND,
) -> dict[str, Any]:
    """Diễn giải bộ số (a)/(b) theo bảng quyết định T1 -> nhãn ưu tiên + trạng thái từng nhánh.

    Trả dict có `label` một trong: "T3", "T4", "T2+T6", "không kết luận được",
    "chờ (b)". Không bẻ nhánh khi một trong hai tỉ lệ rơi vào vùng sát ngưỡng.
    """
    if a_pass_rate is None:
        return {"label": "không kết luận được", "a_status": None, "b_status": None,
                "note": "thiếu số liệu (a)"}

    a_status = _side_of(a_pass_rate, a_threshold, band)
    if a_status == "near":
        return {"label": "không kết luận được", "a_status": "near", "b_status": None,
                "note": f"(a)={a_pass_rate} sát ngưỡng {a_threshold} (band ±{band})"}
    if a_status == "high":
        return {"label": "T3", "a_status": "high", "b_status": None,
                "note": "(a) cao => bỏ (b): nút thắt là chọn/độ dài ngữ cảnh"}

    # (a) thấp => cần (b) để tách "năng lực model" khỏi "trọng tài/corpus".
    if b_pass_rate is None:
        return {"label": "chờ (b)", "a_status": "low", "b_status": None,
                "note": "(a) thấp, chưa có (b) => chưa phán quyết nhánh"}
    b_status = _side_of(b_pass_rate, b_threshold, band)
    if b_status == "near":
        return {"label": "không kết luận được", "a_status": "low", "b_status": "near",
                "note": f"(b)={b_pass_rate} sát ngưỡng {b_threshold} (band ±{band})"}
    if b_status == "high":
        return {"label": "T4", "a_status": "low", "b_status": "high",
                "note": "(a) thấp + (b) cao => năng lực model (Qwen không trích xuất nổi)"}
    return {"label": "T2+T6", "a_status": "low", "b_status": "low",
            "note": "(a) thấp + (b) thấp => trọng tài hoặc corpus"}


def make_b_sample(n: int = 30, seed: int = 20261023) -> Path:
    """Chốt danh sách (b) TRƯỚC khi gọi Gemini, theo điều đăng ký trước trong
    `data/loop/README.md`: item FAIL_OVERREFUSAL của r5 CÓ chunk vàng trong cửa sổ,
    phân tầng theo family, seed cố định. Nếu pool < n thì lấy toàn bộ."""
    import random

    rows = load_jsonl(ROUNDS_DIR / BASE_ROUND / "verdicts_full.jsonl")
    pool = [r for r in rows
            if r.get("verdict") == "FAIL_OVERREFUSAL" and r.get("has_gold_chunk")]
    by_fam: dict[str, list[str]] = {}
    for r in sorted(pool, key=lambda x: x["id"]):
        by_fam.setdefault(r["family"], []).append(r["id"])
    rng = random.Random(seed)
    ids: list[str] = []
    if len(pool) <= n:
        ids = sorted(r["id"] for r in pool)
    else:
        # phân tầng tỉ lệ (làm tròn xuống), phần dư bù lần lượt theo thứ tự family.
        target = {fam: int(len(v) * n / len(pool)) for fam, v in by_fam.items()}
        for fam in sorted(by_fam):
            take = min(target[fam], len(by_fam[fam]))
            ids += sorted(rng.sample(sorted(by_fam[fam]), take)) if take else []
        remaining = [fam for fam in sorted(by_fam) if len(ids) < n and target[fam] < len(by_fam[fam])]
        for fam in remaining:
            if len(ids) >= n:
                break
            chosen = rng.sample(sorted(set(by_fam[fam]) - set(ids)), 1)
            ids += chosen
    out = DIAG_DIR / "b_gemini_top6"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "sample_ids.json"
    path.write_text(json.dumps({
        "rule": "T1 (b): FAIL_OVERREFUSAL ∩ has_gold_chunk của r5, phân tầng family, "
                "đăng ký trước khi gọi (data/loop/README.md mục 'Ablation tầng sinh T1')",
        "seed": seed,
        "n_requested": n,
        "pool_size": len(pool),
        "ids": sorted(ids),
        "family_counts": {fam: len(v) for fam, v in by_fam.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[b-sample] pool={len(pool)} chọn={len(sorted(ids))} -> {path}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="T1 ablation tầng sinh (không sửa code sản xuất).")
    parser.add_argument("--config", nargs="?", choices=CONFIG_NAMES)
    parser.add_argument("--limit", type=int, default=None, help="cắt n nhỏ cho smoke test")
    parser.add_argument("--ids-file", default=None, help="JSON {ids:[...]} — chỉ chạy đúng danh sách đã chốt")
    parser.add_argument("--dry-run", action="store_true", help="không gọi model")
    parser.add_argument("--force", action="store_true",
                        help="cho phép chạy tiếp/ghi vào thư mục diag ĐÃ có rows.jsonl (mặc định từ chối)")
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--make-b-sample", action="store_true",
                        help="chốt sample_ids.json cho (b) — chạy TRƯỚC khi gọi Gemini")
    args = parser.parse_args()

    if args.make_b_sample:
        make_b_sample()
        return 0
    if not args.config:
        parser.error("cần --config <a_oracle_qwen|b_gemini_top6|c_gold_window_qwen>")

    if args.summarize_only:
        summary = summarize(args.config)
    else:
        run_config(args.config, args.limit, args.dry_run,
                   Path(args.ids_file) if args.ids_file else None, force=args.force)
        if args.dry_run:
            return 0
        summary = summarize(args.config)
    print(json.dumps({k: summary[k] for k in ("config", "n_rows", "n_errors", "n_skipped_no_gold", "overall", "overall_answerable80", "ci95_answerable") if k in summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
