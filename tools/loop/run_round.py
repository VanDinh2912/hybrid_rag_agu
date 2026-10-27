"""Chạy một ROUND của vòng lặp: pipeline thật + trọng tài deterministic + bản đồ lỗi.

Mặc định chạy offline (generator Qwen qua Ollama) để không ăn quota Gemini —
vòng lặp hàng nghìn câu mà dựa vào API ~14 request/ngày thì không bao giờ kín.

Bản đồ lỗi (mỗi verdict trỏ đúng tầng cần sửa, tránh "thấy lỗi là nhét vào SFT"):
- FAIL_RETRIEVAL      -> tầng truy xuất (BM25/vector/fusion/router source_filter)
- FAIL_FABRICATED     -> tầng sinh + guardrail câu trả lời
- FAIL_OVERREFUSAL    -> splitting theo bằng chứng (xem triage.lever_for): căn cứ ĐÃ
                          vào cửa sổ generator = tầng sinh (model không trích xuất, dạy
                          lại bằng SFT row); chưa chứng minh được căn cứ = ngưỡng guardrail
- FAIL_HALLUCINATED_ON_UNANSWERABLE -> lớp từ chối (thiếu dữ liệu refusal)
- FAIL_CONFIRMED_FALSE_PREMISE      -> không tin ngữ cảnh, tin tiền đề của người hỏi
- FAIL_INCOMPLETE     -> bao phủ nội dung (prompt/định dạng theo question_type)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.answer_guard import check_grounding  # noqa: E402
from src.pipeline import HybridRAGPipeline  # noqa: E402
from src.vector_db import VectorStoreManager  # noqa: E402
from src.local_slm import LocalSLM  # noqa: E402
from src.generator import QwenGenerator  # noqa: E402
from tools.loop.verify import (  # noqa: E402
    aggregate,
    load_jsonl,
    referee_fingerprint,
    score_item,
)

LEVER_OF_VERDICT = {
    "FAIL_RETRIEVAL": "retrieval",
    "FAIL_FABRICATED": "generation",
    "FAIL_HALLUCINATED_ON_UNANSWERABLE": "refusal",
    "FAIL_CONFIRMED_FALSE_PREMISE": "refusal",
    "FAIL_OVERREFUSAL": "guardrail",
    "FAIL_INCOMPLETE": "generation",
    "PASS_CORRECT": "none",
    "PASS_REFUSAL": "none",
    "PASS_CORRECTED_TRAP": "none",
}


def lever_of(verdict: dict) -> str:
    """Một quy tắc quy lỗi duy nhất cho cả summary của round lẫn triage.

    Dụng ý: `triage.lever_for` phân biệt hai loại FAIL_OVERREFUSAL bằng bằng chứng
    `gold_in_top_k` (căn cứ đã ở trước mặt model hay chưa). Nếu ở đây vẫn giữ bảng
    cứng thì round tự báo lỗi ở tầng guardrail trong khi triage dạy lại ở tầng sinh.
    """
    from tools.loop.triage import lever_for

    return lever_for(verdict, verdict.get("item") or {})[0]


def _percentile(values: list, q: float) -> Optional[float]:
    """Phân vị đơn giản (phần tử thứ ceil(q*n) của danh sách đã sắp xếp) — không nội suy."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(-(-q * len(ordered) // 1)) - 1))
    return round(ordered[index], 2)


def _dec_thresholds() -> dict:
    """Chụp lại bộ ngưỡng từ chối của tầng ngoài đang có hiệu lực (manifest T3).

    Import trễ + fail-open: round không bật lever T3 vẫn ghi được summary kể cả khi
    module chưa tồn tại ở checkout cũ.
    """
    try:
        from src.refusal_policy import thresholds

        return thresholds()
    except Exception as exc:  # noqa: BLE001
        return {"unavailable": f"{type(exc).__name__}: {exc}"}


def _evidence_status() -> dict:
    """Reranker THỰC TẾ đã dùng (cross-encoder hay bi-encoder lùi về) — bắt buộc ghi rõ.

    Đã đăng ký ở `data/loop/README.md` mục T3: nếu môi trường không tải được
    cross-encoder thì số của r9 phải đọc là "chọn câu theo bi-encoder", nên manifest
    phải nói được điều đó sau khi round chạy xong.
    """
    try:
        from src.evidence_selection import reranker_status

        return reranker_status()
    except Exception as exc:  # noqa: BLE001
        return {"unavailable": f"{type(exc).__name__}: {exc}"}


def _retrieval_reranker_status(pipeline=None) -> dict:
    """Trạng thái reranker TRUY XUẤT (lever T5a, `ENABLE_RERANKER`) cho manifest.

    Khác với `_evidence_status()`: cái đó là chuyện chọn CÂU của tầng sinh (T3), còn
    đây là chuyện xếp hạng CHUNK của tầng truy xuất. `gate.compatibility()` không so
    lever, nên round phải tự ký: model nào, thiết bị nào, pool bao nhiêu, và lượt
    rerank thật gần nhất chấm mấy ứng viên.
    """
    try:
        from src.reranker import reranker_status

        status = dict(reranker_status())
    except Exception as exc:  # noqa: BLE001
        return {"unavailable": f"{type(exc).__name__}: {exc}"}
    if pipeline is not None:
        status["last_rerank_call"] = getattr(pipeline, "last_rerank_call", None)
        status["hybrid_path_available"] = bool(
            getattr(pipeline, "use_hybrid", False) and getattr(pipeline, "ensemble_retriever", None) is not None
        )
    return status


def generator_model_override() -> Optional[str]:
    """T4a: slug Ollama RIÊNG cho tầng sinh (`GENERATOR_OLLAMA_MODEL`, mặc định rỗng = TẮT).

    Vì sao không dùng thẳng `OLLAMA_MODEL`: biến đó dẫn NĂM nơi — `src/generator.py:1050`,
    `src/local_slm.py:232`, `src/query_normalizer.py:419`, `src/classifier.py:553` (khi
    `CLASSIFIER_MODEL` để trống) và `src/retrieval.py:299`. Đặt `OLLAMA_MODEL` cho một round
    là đổi đồng thời sinh + chuẩn hóa câu hỏi + phân loại + tách câu, tức bốn biến số một lượt,
    trái quy tắc một biến đã đăng ký ở `data/loop/README.md` mục T4.

    Rỗng (hoặc chỉ khoảng trắng) ⇒ trả `None` ⇒ `QwenGenerator(ollama_model=None)` đi đúng chuỗi
    fallback cũ `os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL`, từng ký tự.
    """
    return os.getenv("GENERATOR_OLLAMA_MODEL", "").strip() or None


def _generator_status(pipeline: Optional[HybridRAGPipeline] = None) -> dict:
    """Model sinh THỰC TẾ đã dùng, để round tự ký dụng cụ đo của nó.

    `gate.compatibility()` chỉ so khóa `generator` (giá trị `"offline_qwen"` — không đổi khi
    đổi slug model), nên cổng mù hoàn toàn với biến số của T4a. Manifest phải nói được slug,
    `num_ctx`, `temperature`, `PROMPT_VERSION` và trần ký tự của cửa ngữ cảnh.
    Import trễ + fail-open: thiếu module thì manifest ghi lý do, round không chết vì ghi sổ.
    """
    status: dict[str, Any] = {"generator_model_env": os.getenv("GENERATOR_OLLAMA_MODEL", "").strip()}
    try:
        from src import generator as generator_module

        gen = getattr(pipeline, "generator", None) if pipeline is not None else None
        status.update(
            {
                "class": type(gen).__name__ if gen is not None else "không chạy (todo rỗng)",
                "model_name": getattr(gen, "model_name", None),
                "ollama_model": getattr(gen, "ollama_model", None)
                or os.getenv("OLLAMA_MODEL")
                or generator_module.DEFAULT_OLLAMA_MODEL,
                "temperature": getattr(gen, "temperature", None),
                "num_ctx": generator_module.QWEN_FALLBACK_NUM_CTX,
                "prompt_version": generator_module.effective_prompt_version(),
                "context_char_caps": {
                    "block": generator_module.QWEN_MAX_BLOCK_CHARS,
                    "total": generator_module.QWEN_MAX_TOTAL_CHARS,
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        status["unavailable"] = f"{type(exc).__name__}: {exc}"
    return status


def build_pipeline(generator_kind: str) -> HybridRAGPipeline:
    vector_db = VectorStoreManager().load_vector_store()
    local_slm = LocalSLM()
    ok, message = local_slm.check_connection()
    print(f"[loop] Local SLM: {'OK' if ok else 'CẢNH BÁO'} — {message}")
    if generator_kind == "gemini":
        from src.generator import GeminiGenerator

        generator: Any = GeminiGenerator()
    else:
        # T4a: chỉ tầng sinh mới được nhận model override; LocalSLM ở trên VÔ TƯ với cờ này.
        generator = QwenGenerator(ollama_model=generator_model_override())
    print(f"[loop] Generator: {getattr(generator, 'model_name', generator_kind)}")
    return HybridRAGPipeline(local_slm=local_slm, vector_db=vector_db, generator=generator)


def run_retrieval_phase(pipeline: HybridRAGPipeline, item: dict, top_k: int, normalize: bool = False) -> dict:
    """Pha rẻ: chỉ đo truy xuất + phân loại, không gọi sinh văn bản.

    `FAIL_RETRIEVAL` đã kết luận được trước khi sinh (chunk vàng không vào cửa sổ
    thì mọi câu trả lời đều vô căn cứ), nên toàn bộ test bank chạy được pha này
    trong vài phút thay vì vài giờ.

    Mặc định câu hỏi KHÔNG qua chuẩn hóa Qwen — đây là cận dưới của recall
    production. `--normalize-query` bật chuẩn hóa để đo riêng đóng góp của tầng đó
    (một đòn bẩy trên mỗi lượt chạy, để cổng duyệt quy đúng nguyên nhân).
    """
    query = item["raw_query"]
    normalized_query = query
    if normalize:
        try:
            candidate = pipeline.local_slm.normalize_query(query)
            if candidate:
                normalized_query = candidate
        except Exception as exc:
            print(f"[loop] chuẩn hóa lỗi ({type(exc).__name__}) — dùng nguyên văn câu hỏi")
    labels = None
    config = None
    if pipeline.enable_classifier:
        try:
            from src.classifier import classify_query
            from src.router import base_config_from_env, get_retrieval_config

            labels = classify_query(normalized_query)
            base = base_config_from_env()
            base.top_k = top_k
            config = get_retrieval_config(labels, base)
        except Exception as exc:
            print(f"[loop] classifier lỗi: {exc}")
    retrieve_k = top_k * pipeline.oversample_factor
    docs = pipeline.retrieve(normalized_query, k=retrieve_k, fallback_query=query, config=config)
    return {
        "answer": None,
        "normalized_query": normalized_query,
        "contexts": [d.page_content for d in docs[:top_k]],
        "sources": [
            {
                "rank": i + 1,
                "chunk_id": d.metadata.get("chunk_id", i),
                "source": d.metadata.get("source", ""),
                "tier": d.metadata.get("tier", ""),
                "chars": len(d.page_content or ""),
            }
            for i, d in enumerate(docs)
        ],
        "labels": labels,
        "retrieval_config": vars(config) if config is not None else None,
        "error": None,
    }



def gold_in_context_flags(retrieval_path: Path, top_k: int) -> dict[str, bool]:
    """Đọc pha truy xuất (nếu đã chạy) để biết item nào có chunk vàng trong cửa sổ.

    Dùng cho bước chọn subset sinh văn bản: sinh một câu mà ngữ cảnh không chứa
    đáp án chỉ đo được khả năng 'nói dối có duyên', không đo được tầng sinh.
    """
    if not retrieval_path.exists():
        return {}
    flags: dict[str, bool] = {}
    for row in load_jsonl(retrieval_path):
        item = row.get("item")
        if not item:
            continue
        verdict = score_item(item, row, top_k=top_k)
        # Item không có chunk vàng (REFUSE_*): không cần truy xuất trúng để đo tầng
        # sinh — câu trả lời ĐÚNG ở đây là từ chối, nên giữ nó trong subset.
        flags[item["id"]] = (
            True if item.get("gold_chunk_id") is None else bool(verdict.get("gold_in_top_k"))
        )
    return flags


def select_for_generation(
    items: list[dict],
    retrieved: dict[str, bool],
    strategy: str,
    limit: int,
    only_retrieved: bool = False,
) -> list[dict]:
    """Chọn tập item chạy PHA SINH (đắt) một cách có chủ đích.

    - `stratified`: chia ô theo (family, split), lấy luân phiên từng ô cho đến khi
      đủ `limit` — bảo đảm mọi family (kể cả REFUSE_*, TRAP) đều có mặt, thay vì
      để CLOZE_OCR (206 item) nuốt trọn ngân sách. Trong mỗi ô, ưu tiên item có
      chunk vàng đã truy xuất được (đo được tầng sinh) rồi mới đến item khó.
    - `only_retrieved`: bỏ hẳn item mà truy xuất đã trượt (dành cho lượt đo sinh).
    """
    pool = [i for i in items if not only_retrieved or retrieved.get(i["id"], True)]
    if strategy == "all" or not limit:
        return pool[: limit or None]
    cells: dict[tuple[str, str], list[dict]] = {}
    for item in pool:
        cells.setdefault((item.get("family") or "?", item.get("split") or "?"), []).append(item)
    for bucket in cells.values():
        bucket.sort(key=lambda i: (not retrieved.get(i["id"], False), i["id"]))
    order = sorted(cells)
    picked: list[dict] = []
    cursors = {k: 0 for k in order}
    while len(picked) < limit:
        progressed = False
        for key in order:
            bucket = cells[key]
            idx = cursors[key]
            if idx >= len(bucket):
                continue
            picked.append(bucket[idx])
            cursors[key] = idx + 1
            progressed = True
            if len(picked) >= limit:
                break
        if not progressed:
            break
    return picked


def plan_subset(
    items: list[dict],
    retrieved: dict[str, bool],
    *,
    phase: str,
    strategy: str,
    limit: int,
    only_retrieved: bool = False,
    pinned: Optional[set[str]] = None,
) -> list[dict]:
    """Tập đo của một round, tính từ TOÀN BỘ item đã lọc — KHÔNG phụ thuộc `done`.

    Đây là bất biến chạy lại-idempotent: chạy lại một round đã xong phải cho đúng
    cùng một tập item (để chấm lại bằng trọng tài mới), không được nhân thêm `limit`
    item mới như bản cũ. Khi `pinned` được đưa ra thì tập đo là định nghĩa từ round
    gốc, không lọc lại theo cờ recall của round này — nếu không subset sẽ co giãn
    theo đúng cái lever đang đo.
    """
    if pinned is not None:
        items = [i for i in items if i["id"] in pinned]
    if phase == "full":
        return select_for_generation(
            items, retrieved, strategy, limit, only_retrieved=only_retrieved and pinned is None
        )
    return items[: limit or None]


def compact_rows(rows: list[dict], subset_ids: set[str]) -> tuple[list[dict], int, int]:
    """Một dòng một id, chỉ giữ dòng thuộc tập đo; trả (rows, ngoài_tập_đo, trùng_id).

    Giữ lại dòng CUỐI của mỗi id: nếu một item được chạy hai lần thì lần sau là
    trạng thái hiện tại của pipeline.
    """
    by_id: dict[str, dict] = {}
    order: list[str] = []
    outside = 0
    for row in rows:
        rid = row.get("id")
        if subset_ids and rid not in subset_ids:
            outside += 1
            continue
        if rid not in by_id:
            order.append(rid)
        by_id[rid] = row
    kept = [by_id[rid] for rid in order]
    return kept, outside, (len(rows) - outside) - len(kept)


def pin_subset(rounds_root: Path, round_name: str, phase: str) -> set[str]:
    """Danh sách item id đã chạy ở round khác — để các round SO SÁNH ĐƯỢC nhau.

    Không pin thì subset mỗi round lại đổi theo cờ `gold_in_top_k` của chính round
    đó, gate chỉ còn phần giao rất nhỏ và mất ý nghĩa 'cùng thang đo'.
    """
    path = rounds_root / round_name / f"{phase}.jsonl"
    if not path.exists():
        raise SystemExit(
            f"Không có {path} — không pin được subset từ round '{round_name}'. "
            "Bỏ --pin-subset-from để tự chọn subset mới."
        )
    return {row["id"] for row in load_jsonl(path) if row.get("id")}


def load_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            done.add(json.loads(line)["id"])
        except json.JSONDecodeError:
            continue
    return done


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--testset", default=str(ROOT / "data" / "loop" / "testset_v1.jsonl"))
    parser.add_argument("--split", default="test", choices=["test", "trainpool", "all"])
    parser.add_argument("--families", default="", help="Lọc theo family, phẩy ngăn cách; rỗng = tất cả")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--generator", default="offline_qwen", choices=["offline_qwen", "gemini"])
    parser.add_argument("--round", default="r0")
    parser.add_argument(
        "--phase",
        default="full",
        choices=["retrieval", "full"],
        help="retrieval = không sinh text (nhanh, chạy trọn test bank); full = pipeline thật",
    )
    parser.add_argument("--out-root", default=str(ROOT / "data" / "loop" / "rounds"))
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument(
        "--strategy",
        default="stratified",
        choices=["stratified", "all"],
        help="Cách chọn subset khi --limit ở pha full: stratified = chia đều theo (family, split)",
    )
    parser.add_argument(
        "--only-retrieved",
        action="store_true",
        help="Pha full: bỏ item mà pha truy xuất không kéo được chunk vàng vào cửa sổ",
    )
    parser.add_argument(
        "--pin-subset-from",
        default="",
        metavar="ROUND",
        help="Chạy đúng tập item đã dùng ở ROUND khác (cùng pha) để cổng duyệt so sánh "
        "trên cùng thang đo. Ví dụ round r1 pin từ r0.",
    )
    parser.add_argument(
        "--normalize-query",
        action="store_true",
        help="Pha retrieval: cho câu hỏi đi qua LocalSLM.normalize_query trước khi truy xuất "
        "(mặc định TẮT = cận dưới của recall production)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_root) / args.round
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"{args.phase}.jsonl"

    items = load_jsonl(Path(args.testset))
    if args.split != "all":
        items = [i for i in items if i["split"] == args.split]
    if args.families:
        wanted = {f.strip() for f in args.families.split(",")}
        items = [i for i in items if i["family"] in wanted]
    done = load_done(results_path)
    pinned: Optional[set[str]] = None
    if args.pin_subset_from:
        pinned = pin_subset(Path(args.out_root), args.pin_subset_from, args.phase)
    # ---- TẬP ĐO: chọn từ toàn bộ pool, không chọn từ phần chưa chạy ----
    if args.phase == "full" and pinned is None:
        retrieved = gold_in_context_flags(out_dir / "retrieval.jsonl", args.top_k)
    else:
        retrieved = {}
    items = plan_subset(
        items,
        retrieved,
        phase=args.phase,
        strategy=args.strategy,
        limit=args.limit,
        only_retrieved=args.only_retrieved,
        pinned=pinned,
    )
    subset_ids = {i["id"] for i in items}
    todo = [i for i in items if i["id"] not in done]
    print(
        f"[loop] round={args.round} tập đo={len(subset_ids)} item, đã chạy="
        f"{len(subset_ids & done)} lần này={len(todo)} "
        f"top_k={args.top_k} classifier={os.getenv('ENABLE_CLASSIFIER', '0')}"
        + (f" (pin từ {args.pin_subset_from})" if pinned is not None else "")
    )
    if not todo:
        print("[loop] Không có item mới — vào thẳng bước chấm điểm.")

    oversample: Optional[int] = None
    pipeline: Optional[HybridRAGPipeline] = None
    if todo:
        pipeline = build_pipeline(args.generator)
        oversample = pipeline.oversample_factor
        with results_path.open("a", encoding="utf-8") as fh:
            for n, item in enumerate(todo, 1):
                t0 = time.perf_counter()
                entry: dict[str, Any] = {"id": item["id"], "item": item}
                try:
                    if args.phase == "retrieval":
                        result = run_retrieval_phase(pipeline, item, args.top_k, normalize=args.normalize_query)
                    else:
                        result = pipeline.run(item["raw_query"], top_k=args.top_k)
                    entry.update(
                        {
                            "answer": result.get("answer"),
                            "normalized_query": result.get("normalized_query"),
                            "contexts": result.get("contexts") or [],
                            "sources": result.get("sources") or [],
                            "labels": result.get("labels"),
                            "retrieval_config": result.get("retrieval_config"),
                            "error": None,
                        }
                    )
                except Exception as exc:
                    entry.update({"answer": "", "contexts": [], "sources": [], "error": f"{type(exc).__name__}: {exc}"})
                entry["latency_seconds"] = round(time.perf_counter() - t0, 2)
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                fh.flush()
                if n % 10 == 0 or n == len(todo):
                    print(f"[loop]  {n}/{len(todo)} ({entry['latency_seconds']}s) id={item['id']} err={entry.get('error')}")
                if args.sleep_seconds:
                    time.sleep(args.sleep_seconds)

    # ---- chấm điểm toàn bộ round (kể cả kết quả cũ, để resume đúng nghĩa) ----
    # Nhưng CHỈ chấm dòng thuộc tập đo, và ghi ngược file đúng tập đó: một round
    # phải có một định nghĩa tập đo duy nhất, nếu không `--pin-subset-from` của round
    # sau nuốt luôn xác của những lần chạy trước (r0/full từng phình 100 -> 178 dòng
    # chỉ vì chạy lại để chấm điểm).
    rows_all = load_jsonl(results_path)
    rows_raw, outside, duplicated = compact_rows(rows_all, subset_ids)
    if len(rows_raw) != len(rows_all):
        with results_path.open("w", encoding="utf-8") as fh:
            for row in rows_raw:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            f"[loop] nén {results_path.name}: giữ {len(rows_raw)}/{len(rows_all)} dòng "
            f"(loại {outside} ngoài tập đo, {duplicated} trùng id)"
        )
    item_by_id = {i["id"]: i for i in items}
    verdicts = []
    for row in rows_raw:
        item = item_by_id.get(row["id"])
        if item is None:
            continue
        if row.get("error"):
            verdicts.append(
                {"id": row["id"], "family": item["family"], "split": item["split"],
                 "verdict": "FAIL_SYSTEM_ERROR", "severity": 3, "raw_query": item["raw_query"],
                 "answer_preview": "", "unsupported": [], "detail": {"error": row["error"]}}
            )
            continue
        verdicts.append(score_item(item, row, top_k=args.top_k))

    verdicts_path = out_dir / f"verdicts_{args.phase}.jsonl"
    with verdicts_path.open("w", encoding="utf-8") as fh:
        for v in verdicts:
            fh.write(json.dumps(v, ensure_ascii=False) + "\n")

    overall = Counter(v["verdict"] for v in verdicts)
    by_family = aggregate(verdicts, "family")
    by_split = aggregate(verdicts, "split")
    lever_counts: Counter = Counter(lever_of(v) for v in verdicts)
    answered = [v for v in verdicts if not v.get("is_refusal") and v.get("answer_chars", 0) > 0]
    fabrication_rate = round(
        sum(1 for v in answered if v["unsupported"]) / len(answered), 4
    ) if answered else None

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "round": args.round,
        "settings": {
            "split": args.split,
            "families": args.families or "all",
            "top_k": args.top_k,
            "generator": args.generator,
            "strategy": args.strategy,
            "limit": args.limit or None,
            "only_retrieved": args.only_retrieved,
            "normalize_query": args.normalize_query,
            "pin_subset_from": args.pin_subset_from or None,
            "testset": args.testset,
            "enable_classifier": os.getenv("ENABLE_CLASSIFIER", "0"),
            "enable_answer_guard": os.getenv("ENABLE_ANSWER_GUARD", "0"),
            # Lever P5.2: router cắt cứng nguồn (0) hay chỉ cộng ưu tiên hạng (1).
            # Không nằm trong danh sách so khớp của gate vì đây chính là biến số
            # đang được thử — gate so ĐẠNG chạy, không so lever.
            "router_soft_filter": os.getenv("ROUTER_SOFT_FILTER", "0"),
            "router_filter_rank_bonus": os.getenv("ROUTER_FILTER_RANK_BONUS", "3"),
            # Lever P5.14: hạn ngạch suất tối đa cho một nguồn trong danh sách ứng viên.
            # Cũng là biến số đang thử nên không nằm trong danh sách so khớp của gate.
            "router_source_quota": os.getenv("ROUTER_SOURCE_QUOTA", "0"),
            # Lever P5.13: cứu câu từ chối oan bằng lượt yêu cầu trích xuất (mặc định TẮT).
            # Cũng là lever nên KHÔNG đưa vào danh sách so khớp của gate.
            "answer_rescue": os.getenv("ENABLE_ANSWER_RESCUE", "0"),
            "rescue_min_score": os.getenv("RESCUE_MIN_SCORE", "0.8"),
            # Lever P5.16: bản kiểm chứng đầu ra bộ chuẩn hóa câu hỏi (mặc định TẮT).
            # Cũng là lever nên KHÔNG đưa vào danh sách so khớp của gate.
            "normalize_sanity_guard": os.getenv("NORMALIZE_SANITY_GUARD", "0"),
            "normalize_min_containment": os.getenv("NORMALIZE_MIN_CONTAINMENT", "0.3"),
            # Lever T3 (P5.18): quyền từ chối rời khỏi tầng sinh + chọn câu bằng chứng.
            # Là lever đang thử nên KHÔNG vào danh sách so khớp của gate. Ngưỡng ghi hết
            # vào manifest để round sau đọc lại được ĐÚNG bộ số đã đăng ký ở README.
            "decoupled_refusal": os.getenv("ENABLE_DECOUPLED_REFUSAL", "0"),
            "dec_thresholds": _dec_thresholds(),
            "evidence_selection": os.getenv("ENABLE_EVIDENCE_SELECTION", "0"),
            "evidence_reranker": _evidence_status(),
            # Lever T5a (P5.21): reranker cross-encoder cho tầng TRUY XUẤT. Là lever đang
            # thử nên KHÔNG vào danh sách so khớp của gate — manifest phải tự ký.
            "retrieval_reranker": _retrieval_reranker_status(pipeline),
            # Lever T4a (P5.20): slug model sinh THỰC TẾ + num_ctx/temperature/prompt version.
            # `gate.compatibility()` chỉ nhìn khóa `generator` ("offline_qwen") nên nó KHÔNG
            # bao giờ thấy biến số này — manifest phải tự ký, nếu không round đổi model sẽ
            # trông như "cùng cấu hình" và số latency/PASS_CORRECT bị gán sai nguyên nhân.
            "generator_status": _generator_status(pipeline),
            # Cache sinh văn bản: vòng lặp phải trỏ vào thư mục LẠNH dùng chung cho
            # mọi round. Nếu để ./.generation_cache (đã ấm từ thời prompt cũ), đa số
            # câu là cache-hit và AnswerGuard không hề được chạy -> đo sai lever sinh.
            "generation_cache_dir": os.getenv("GENERATION_CACHE_DIR", "./.generation_cache"),
            # Chữ ký của dụng cụ đo. Hai round chỉ so được nhau khi cùng chữ ký.
            "referee": referee_fingerprint(),
            "oversample_factor": oversample,
        },
        "n_scored": len(verdicts),
        "verdict_counts": dict(overall),
        "by_family": by_family,
        "by_split": by_split,
        "failures_by_lever": dict(lever_counts),
        "fabrication_rate_on_answered": fabrication_rate,
        "refusal_rate": round(sum(1 for v in verdicts if v.get("is_refusal")) / len(verdicts), 4) if verdicts else None,
        "median_latency": (
            sorted([v["latency_seconds"] for v in verdicts if v.get("latency_seconds")])[
                len([v for v in verdicts if v.get("latency_seconds")]) // 2
            ]
            if any(v.get("latency_seconds") for v in verdicts)
            else None
        ),
        # T3 đăng ký đo p95: đòn bẩy mới thêm việc ở tầng ngoài (đo hạng hai nhánh,
        # chấm grounding), phải thấy được giá latency ở đuôi phân phối chứ không chỉ
        # giữa. Phần tử thứ ceil(0.95*n) của danh sách đã sắp xếp.
        "p95_latency": _percentile(
            [v["latency_seconds"] for v in verdicts if v.get("latency_seconds")], 0.95
        ),
    }
    (out_dir / f"round_summary_{args.phase}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in ("n_scored", "verdict_counts", "failures_by_lever", "fabrication_rate_on_answered", "refusal_rate")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
