"""B1 — ablation (c′): ngữ cảnh là chunk vàng CÓ DẤU từ `chroma_db_vie`.

Đề bài (duyệt 25-10): chọn các item pha sinh của r5 mà gold ánh xạ được sang index mới
(quy tắc "khớp nguồn + fold gold_sentence", kiểm kê ở `mapping.json` do
`tmp/b1_mapping_check.py` dựng — reproduced trong hàm `build_mapping` dưới đây), chạy
Qwen 1,5B trên chunk vàng mới, SO VỚI (a) trên ĐÚNG các item đó, cùng prompt/temp/num_ctx.

Vì sao chạy lại (a) thành `a_prime` thay vì dùng rows đã công bố: giữa lúc (a) chạy
(23-10) và bây giờ, cây làm việc đã đổi (T3/T4/T5 commit + file `src/` dirty của phiên
khác) — một phép ghép cặp chỉ là "một biến" khi cả hai nhánh chạy trên CÙNG cây.
`a_prime` dùng lại ĐÚNG đường gọi của (a) (chunk cũ, cùng content/source, cùng
`QwenGenerator._build_prompt`, temp 0,1, num_ctx ghim sẵn). So sánh chéo a_prime với
rows (a) đã công bố được in ra để phát hiện drift; kết luận ghép cặp dùng a_prime-vs-c′.

Không sửa file nào thuộc REFEREE_FILES / rounds đã đóng; mọi thứ ghi vào
`data/loop/diag/b1_cprime/`. Chữ ký trọng tài lúc chạy phải là bản TRƯỚC PA-2/PA-20
(`9f1179ccab74`) để ngang bằng với (a) gốc — script từ chối chạy nếu khác.

Lệnh tái lập:
    PYTHONIOENCODING=utf-8 ENABLE_ANSWER_GUARD=1 venv/Scripts/python.exe -u \
        tools/diag/ablation_c_prime.py            # đủ 57 item, rồi tự phân tích
    ... --dry-run | --limit N | --force | --analyze-only
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

import chromadb  # noqa: E402

from src.generator import GeneratorError, QwenGenerator  # noqa: E402
from src.text_utils import fold  # noqa: E402
from tools.loop import noise_floor, verify  # noqa: E402

BASE_ROUND = "r5"
ROUNDS_DIR = ROOT / "data" / "loop" / "rounds"
DIAG_DIR = ROOT / "data" / "loop" / "diag"
OUT_DIR = DIAG_DIR / "b1_cprime"
TESTSET = ROOT / "data" / "loop" / "testset_v1.jsonl"
NEW_INDEX = ROOT / "chroma_db_vie"
EXPECTED_REFEREE = "9f1179ccab74"  # trọng tài v1 — bản đã chấm (a) gốc


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_old_chunks() -> dict[int, dict]:
    spec = importlib.util.spec_from_file_location("btd_b1", str(ROOT / "tools" / "train" / "build_training_data.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["btd_b1"] = module
    spec.loader.exec_module(module)
    return {c["chunk_id"]: c for c in module.load_chunks()}


def load_new_chunks() -> list[dict]:
    client = chromadb.PersistentClient(path=str(NEW_INDEX))
    cols = client.list_collections()
    if len(cols) != 1:
        raise SystemExit(f"[c] chroma_db_vie có {len(cols)} collection — không rõ dùng cái nào")
    got = cols[0].get(include=["documents", "metadatas"])
    return [
        {"cid": cid, "text": doc or "", "source": str((meta or {}).get("source") or ""),
         "chunk_id": (meta or {}).get("chunk_id")}
        for cid, doc, meta in zip(got.get("ids") or [], got.get("documents") or [], got.get("metadatas") or [])
    ]


def build_mapping(a_rows_ids: set[str], items: dict[str, dict]) -> dict:
    """Ánh xạ gold -> chunk mới (khớp nguồn + fold gold_sentence). Nhiều khớp -> chunk dài nhất."""
    rows = load_jsonl(ROUNDS_DIR / BASE_ROUND / "full.jsonl")
    old_chunks = load_old_chunks()
    new_chunks = load_new_chunks()
    by_source: dict[str, list[dict]] = {}
    for c in new_chunks:
        by_source.setdefault(fold(c["source"]), []).append(c)

    mapped: list[dict] = []
    unmapped: list[dict] = []
    for row in rows:
        iid = row["id"]
        if iid not in a_rows_ids:
            continue
        item = items[iid]
        gold_id = item.get("gold_chunk_id")
        gs = fold(item.get("gold_sentence") or "")
        old_chunk = old_chunks.get(gold_id)
        if old_chunk is None or not gs:
            unmapped.append({"id": iid, "reason": "no_old_chunk_or_no_gold_sentence"})
            continue
        want_src = fold(str(old_chunk.get("source") or ""))
        hits = [c for c in by_source.get(want_src, []) if gs in fold(c["text"])]
        if not hits:
            unmapped.append({"id": iid, "reason": "no_new_chunk_same_source_with_gold",
                             "family": item.get("family"), "source": old_chunk.get("source")})
            continue
        best = max(hits, key=lambda c: len(c["text"]))
        mapped.append({"id": iid, "family": item.get("family"), "old_chunk_id": gold_id,
                       "source": best["source"], "new_cid": best["cid"],
                       "n_hits": len(hits), "new_chars": len(best["text"]),
                       "old_chars": len(old_chunk.get("text") or "")})
    return {"n_mapped": len(mapped), "n_unmapped": len(unmapped), "mapped": mapped,
            "unmapped": unmapped, "multi_hit": sum(1 for m in mapped if m["n_hits"] > 1)}


def docs_for(kind: str, m: dict, item: dict, old_chunks: dict[int, dict], new_by_cid: dict[str, dict]) -> list[dict]:
    """Một block ngữ cảnh. CẢ HAI nhánh khai báo chunk_id = gold id cũ (đúng tiền lệ
    config (c) của ablation_generation.py): điều đang đo là NỘI DUNG căn cứ, không phải id."""
    gold_id = item["gold_chunk_id"]
    if kind == "a_prime":
        ch = old_chunks[gold_id]
        return [{"content": ch["text"], "source": ch["source"], "tier": ch["tier"], "chunk_id": gold_id}]
    nc = new_by_cid[m["new_cid"]]
    old = old_chunks[gold_id]
    return [{"content": nc["text"], "source": old["source"], "tier": old["tier"], "chunk_id": gold_id}]


def build_result(docs: list[dict], answer: str, row: dict, latency: float) -> dict:
    return {
        "answer": answer,
        "contexts": [d["content"] for d in docs],
        "sources": [{"rank": i + 1, "source": d["source"], "tier": d["tier"], "chunk_id": d["chunk_id"]}
                    for i, d in enumerate(docs)],
        "labels": row.get("labels"),
        "latency_seconds": latency,
    }


def run_branch(kind: str, todo: list[tuple[dict, dict, list[dict]]], force: bool) -> Path:
    branch_dir = OUT_DIR / kind
    rows_path = branch_dir / "rows.jsonl"
    branch_dir.mkdir(parents=True, exist_ok=True)
    if rows_path.exists() and not force:
        raise SystemExit(f"[out] {rows_path} đã có; dùng --force để resume (thư mục B1 không đụng bản cũ nào khác).")
    done = {r["id"] for r in load_jsonl(rows_path) if not r.get("error")} if rows_path.exists() else set()
    generator = QwenGenerator()  # cùng đường gọi với (a): env OLLAMA_MODEL, temp 0,1, num_ctx ghim
    with rows_path.open("a", encoding="utf-8") as sink:
        for n, (mrow, item, docs) in enumerate(todo, start=1):
            if mrow["id"] in done:
                continue
            row = mrow["row"]
            question = row.get("normalized_query") or item.get("raw_query") or ""
            qtype = (row.get("labels") or {}).get("question_type")
            t0 = time.time()
            try:
                answer = generator.generate_answer(
                    query=question, retrieved_docs=docs, question_type=qtype,
                    raw_query=item.get("raw_query"))
                error = None
            except GeneratorError as exc:
                answer, error = None, f"{type(exc).__name__}: {exc}"
            except Exception as exc:  # noqa: BLE001 — lỗi nào cũng phải thành dòng
                answer, error = None, f"{type(exc).__name__}: {exc}"
            latency = round(time.time() - t0, 2)
            if error:
                rec = {"id": mrow["id"], "error": error, "latency_seconds": latency}
            else:
                v = verify.score_item(item, build_result(docs, answer, row, latency), top_k=6)
                rec = {**v, "answer": answer, "n_docs": len(docs),
                       "context_chars": sum(len(d["content"]) for d in docs)}
            sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
            sink.flush()
            print(f"[b1:{kind}] {n}/{len(todo)} {mrow['id']}: {rec.get('verdict') or rec.get('error')} ({latency}s)",
                  flush=True)
    return branch_dir


# ------------------------------------------------------------------ phân tích ghép cặp

def _block_rows(path: Path) -> dict[str, dict]:
    return {r["id"]: r for r in load_jsonl(path) if not r.get("error")}


def analyze(published_a: dict[str, dict]) -> dict[str, Any]:
    a_rows = _block_rows(OUT_DIR / "a_prime" / "rows.jsonl")
    c_rows = _block_rows(OUT_DIR / "c_prime" / "rows.jsonl")
    ids = sorted(set(a_rows) & set(c_rows))
    n = len(ids)

    def flag(rows: dict[str, dict], iid: str, key: str) -> int:
        r = rows[iid]
        if key == "pass_correct":
            return 1 if r.get("verdict") == "PASS_CORRECT" else 0
        if key == "refusal":
            return 1 if r.get("is_refusal") else 0
        if key == "answered":
            return 1 if (not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0) else 0
        if key == "fabricated":
            return 1 if (r.get("unsupported") and not r.get("is_refusal")) else 0
        raise KeyError(key)

    out: dict[str, Any] = {"n_paired": n, "conclusion_allowed": n >= 30,
                           "rule": "n<30 => KHÔNG kết luận (đề bài B1)"}
    ones = [1] * n
    for key in ("pass_correct", "refusal", "fabricated"):
        av = [flag(a_rows, i, key) for i in ids]
        cv = [flag(c_rows, i, key) for i in ids]
        den = ones if key != "fabricated" else [max(av[i], cv[i]) for i in range(n)]
        b, c = sum(1 for i in range(n) if av[i] == 0 and cv[i] == 1), sum(1 for i in range(n) if av[i] == 1 and cv[i] == 0)
        out[key] = {
            "a_prime": {"num": sum(av), "rate": round(sum(av) / max(sum(den), n) if key != "fabricated" else sum(av) / max(sum(den), 1), 4)},
            "c_prime": {"num": sum(cv), "rate": round(sum(cv) / max(sum(den), n) if key != "fabricated" else sum(cv) / max(sum(den), 1), 4)},
            "den": sum(den),
            "paired_bootstrap": noise_floor.paired_bootstrap(av, cv, den, den),
            "mcnemar_exact": noise_floor.mcnemar_exact(b, c),
        }
    out["verdict_counts"] = {
        "a_prime": dict(Counter(a_rows[i].get("verdict") for i in ids)),
        "c_prime": dict(Counter(c_rows[i].get("verdict") for i in ids)),
    }
    out["per_item"] = [
        {"id": i, "family": a_rows[i].get("family"),
         "a_verdict": a_rows[i].get("verdict"), "c_verdict": c_rows[i].get("verdict"),
         "a_refusal": bool(a_rows[i].get("is_refusal")), "c_refusal": bool(c_rows[i].get("is_refusal"))}
        for i in ids
    ]
    # Drift cây: a_prime (cây hiện tại) vs rows (a) đã công bố (cây 23-10) trên cùng id.
    drift = []
    for i in ids:
        pub = published_a.get(i)
        if pub is None:
            continue
        same_answer = (pub.get("answer") or "") == (a_rows[i].get("answer") or "")
        if not same_answer or pub.get("verdict") != a_rows[i].get("verdict"):
            drift.append({"id": i, "answer_same": same_answer,
                          "a_pub_verdict": pub.get("verdict"), "a_prime_verdict": a_rows[i].get("verdict")})
    out["tree_drift_vs_published_a"] = {"n_checked": sum(1 for i in ids if i in published_a),
                                        "n_drifted": len(drift), "drifted": drift[:20]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="B1 ablation c′ (không sửa rounds/trọng tài).")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="resume vào rows.jsonl của B1 (chỉ thư mục b1_cprime)")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()

    fp = verify.referee_fingerprint()
    if fp != EXPECTED_REFEREE:
        raise SystemExit(f"[referee] chữ ký hiện tại {fp} != {EXPECTED_REFEREE} — B1 phải chạy TRƯỚC khi áp PA-2/PA-20.")

    base_rows = {r["id"]: r for r in load_jsonl(ROUNDS_DIR / BASE_ROUND / "full.jsonl")}
    published_a_path = DIAG_DIR / "a_oracle_qwen" / "rows.jsonl"
    published_a = _block_rows(published_a_path)
    items = {r["id"]: r for r in load_jsonl(TESTSET)}
    mapping_path = OUT_DIR / "mapping.json"
    if mapping_path.exists() and not args.force:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    else:
        mapping = build_mapping(set(published_a), items)
        if mapping_path.exists():
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        else:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.analyze_only:
        res = analyze(published_a)
        (OUT_DIR / "analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: res[k] for k in ("n_paired", "conclusion_allowed")}, ensure_ascii=False))
        return 0

    old_chunks = load_old_chunks()
    new_by_cid = {c["cid"]: c for c in load_new_chunks()}
    done_a = _block_rows(OUT_DIR / "a_prime" / "rows.jsonl") if (OUT_DIR / "a_prime" / "rows.jsonl").exists() else {}
    done_c = _block_rows(OUT_DIR / "c_prime" / "rows.jsonl") if (OUT_DIR / "c_prime" / "rows.jsonl").exists() else {}

    for branch, done in (("a_prime", done_a), ("c_prime", done_c)):
        todo = []
        for m in mapping["mapped"]:
            iid = m["id"]
            if iid in done:
                continue
            row = base_rows[iid]
            item = items[iid]
            todo.append(({**m, "row": row}, item, docs_for(branch, m, item, old_chunks, new_by_cid)))
        if args.limit is not None:
            todo = todo[: args.limit]
        if args.dry_run:
            for m, item, docs in todo[:3]:
                print(f"[dry:{branch}] {m['id']} ({item.get('family')}): {len(docs)} block, {sum(len(d['content']) for d in docs)} ký tự")
            print(f"[dry] {branch}: todo={len(todo)} (đã xong {len(done)})")
            continue
        run_branch(branch, todo, force=args.force)

    if args.dry_run:
        return 0

    settings = {
        "base_round": BASE_ROUND, "referee": fp,
        "env": {k: os.environ.get(k) for k in ("ENABLE_ANSWER_GUARD", "OLLAMA_MODEL", "GENERATION_CACHE_DIR")},
        "n_mapped": mapping["n_mapped"], "n_unmapped": mapping["n_unmapped"],
        "note": "a_prime = (a) chạy lại trên CÂY HIỆN TẠI cho đúng 57 item ghép cặp; "
                "c_prime = cùng item, nội dung là chunk vàng có dấu từ chroma_db_vie, chunk_id khai = gold id cũ (tiền lệ config c).",
    }
    (OUT_DIR / "settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    res = analyze(published_a)
    (OUT_DIR / "analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"n_paired": res["n_paired"], "conclusion_allowed": res["conclusion_allowed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
