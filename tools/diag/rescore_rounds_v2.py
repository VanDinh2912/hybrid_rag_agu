"""B2 — chấm lại OFFLINE mọi round đã đóng (từ full.jsonl) bằng trọng tài v2 (PA-2+PA-20).

Đề bài duyệt 25-10: "chấm lại OFFLINE mọi round đã đóng từ full.jsonl vào thư mục mới,
không đụng bản cũ; báo bảng verdict cũ vs mới theo round".

Phạm vi: các round CÓ `full.jsonl` = r0, r1, r3, r5, r5b, r6, r7, r8, r9, r10
(r2/r4/r11+ là retrieval-only — verdict pha TRUY XUẤT không đi qua `_answer_covers_gold`
hay cờ proper của PA-2; kiểm bằng code: nhánh `retrieval_only` trong `verify.score_item`
chỉ dùng `gold_chunk_id`/cửa sổ, hai bản vá không chạm — nên không chấm lại).

Nguyên tắc:
- ĐỌC `data/loop/rounds/<r>/full.jsonl`, GHI `data/loop/rounds_v2/<r>/` — round cũ
  không một byte nào bị sửa; chạy lại lệnh này ghi đè chính rounds_v2 (artifact của
  phiên này, chưa công bố số liệu nào khác từ nó).
- Item lấy từ CHÍNH dòng full.jsonl (`row["item"]`) — round chấm bằng chứng kiến đã lưu,
  không suy đoán; đối chiếu với testset hiện hành và ĐẾM chênh (không tự đổi bên nào).
- Không gọi model, 0 token Gemini.

Lệnh tái lập:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/rescore_rounds_v2.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.loop import verify  # noqa: E402  (trọng tài v2 — PA-2 + PA-20 đã duyệt)
from tools.loop.verify import aggregate, score_item  # noqa: E402

ROUNDS_OLD = ROOT / "data" / "loop" / "rounds"
ROUNDS_NEW = ROOT / "data" / "loop" / "rounds_v2"
TESTSET = ROOT / "data" / "loop" / "testset_v1.jsonl"

FULL_ROUNDS = ("r0", "r1", "r3", "r5", "r5b", "r6", "r7", "r8", "r9", "r10")

# Các chỉ báo đưa vào bảng so sánh cũ/mới.
KEY_VERDICTS = ("PASS_CORRECT", "PASS_REFUSAL", "PASS_CORRECTED_TRAP", "FAIL_INCOMPLETE",
                "FAIL_RETRIEVAL", "FAIL_OVERREFUSAL", "FAIL_FABRICATED",
                "FAIL_CONFIRMED_FALSE_PREMISE", "FAIL_HALLUCINATED_ON_UNANSWERABLE",
                "FAIL_SYSTEM_ERROR", "PENDING_GENERATION")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _rate_block(rows: list[dict]) -> dict:
    decided = [r for r in rows if r.get("verdict") != "PENDING_GENERATION"]
    n = len(decided)
    answered = [r for r in decided if not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0]
    return {
        "n_decided": n,
        "counts": {k: sum(1 for r in decided if r.get("verdict") == k) for k in KEY_VERDICTS},
        "pass_correct": sum(1 for r in decided if r.get("verdict") == "PASS_CORRECT"),
        "refusal_rate": round(sum(1 for r in decided if r.get("is_refusal")) / n, 4) if n else None,
        "fabrication_rate_on_answered": (
            round(sum(1 for r in answered if r.get("unsupported")) / len(answered), 4) if answered else None
        ),
    }


def rescore_round(name: str) -> dict:
    old_dir = ROUNDS_OLD / name
    rows_raw = load_jsonl(old_dir / "full.jsonl")
    items_now = {r["id"]: r for r in load_jsonl(TESTSET)}

    verdicts: list[dict] = []
    n_item_drift = 0
    for row in rows_raw:
        item = row.get("item") or {}
        if item.get("id") != row.get("id"):
            raise SystemExit(f"[{name}] dòng thiếu/khác id — không phải full.jsonl chuẩn: {row.get('id')!r}")
        ref = items_now.get(row["id"])
        if ref is not None and ref != item:
            n_item_drift += 1
        if row.get("error"):
            verdicts.append({
                "id": row["id"], "family": item.get("family"), "split": item.get("split"),
                "verdict": "FAIL_SYSTEM_ERROR", "severity": 3, "raw_query": item.get("raw_query"),
                "answer_preview": "", "unsupported": [], "detail": {"error": row["error"]},
            })
            continue
        verdicts.append(score_item(item, row, top_k=6))

    new_dir = ROUNDS_NEW / name
    new_dir.mkdir(parents=True, exist_ok=True)
    with (new_dir / "verdicts_full.jsonl").open("w", encoding="utf-8") as fh:
        for v in verdicts:
            fh.write(json.dumps(v, ensure_ascii=False) + "\n")

    old_summary_path = old_dir / "round_summary_full.json"
    old_referee = None
    if old_summary_path.exists():
        try:
            old_referee = json.loads(old_summary_path.read_text(encoding="utf-8")).get("settings", {}).get("referee")
        except (json.JSONDecodeError, AttributeError):
            old_referee = None

    decided = [v for v in verdicts if v.get("verdict") != "PENDING_GENERATION"]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "round": name,
        "rescore_of": f"data/loop/rounds/{name}/full.jsonl",
        "settings": {"top_k": 6, "referee": verify.referee_fingerprint(),
                     "referee_original": old_referee},
        "n_scored": len(verdicts),
        "n_item_drift_vs_current_testset": n_item_drift,
        "verdict_counts": dict(Counter(v["verdict"] for v in verdicts)),
        "by_family": aggregate(verdicts, "family"),
        "by_split": aggregate(verdicts, "split"),
        "fabrication_rate_on_answered": _rate_block(verdicts)["fabrication_rate_on_answered"],
        "refusal_rate": _rate_block(verdicts)["refusal_rate"],
    }
    (new_dir / "round_summary_full.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- cũ vs mới: verdict công bố (verdicts_full.jsonl cũ) so verdict chấm lại
    old_verdicts_path = old_dir / "verdicts_full.jsonl"
    old_rows = {r["id"]: r for r in load_jsonl(old_verdicts_path)} if old_verdicts_path.exists() else {}
    new_rows = {v["id"]: v for v in verdicts}
    flips = []
    for iid in sorted(set(old_rows) & set(new_rows)):
        ov, nv = old_rows[iid].get("verdict"), new_rows[iid].get("verdict")
        if ov != nv:
            flips.append({"id": iid, "family": new_rows[iid].get("family"),
                          "old": ov, "new": nv,
                          "old_unsupported": len(old_rows[iid].get("unsupported") or []),
                          "new_unsupported": len(new_rows[iid].get("unsupported") or []),
                          "answer_preview": (new_rows[iid].get("answer_preview") or "")[:140]})
    only_new = sorted(set(new_rows) - set(old_rows))
    return {
        "round": name,
        "old": _rate_block(list(old_rows.values())) if old_rows else None,
        "new": _rate_block(verdicts),
        "n_old_rows": len(old_rows), "n_new_rows": len(verdicts),
        "ids_only_in_new": only_new,
        "n_flips": len(flips), "flips": flips,
        "referee_original": old_referee, "referee_v2": verify.referee_fingerprint(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Chấm lại offline các round full bằng trọng tài v2.")
    ap.add_argument("--rounds", default=",".join(FULL_ROUNDS))
    args = ap.parse_args()
    if verify.referee_fingerprint() == "9f1179ccab74":
        raise SystemExit("[referee] vẫn là v1 — PA-2/PA-20 chưa được áp dụng?")

    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "referee_v2": verify.referee_fingerprint(), "rounds": []}
    for name in [r.strip() for r in args.rounds.split(",") if r.strip()]:
        rep = rescore_round(name)
        report["rounds"].append(rep)
        old = rep["old"] or {}
        print("[{0}] verdict đổi: {1}  (cũ {2} -> mới {3} PASS_CORRECT; refusal {4} -> {5})".format(
            name, rep["n_flips"], old.get("pass_correct", "?"), rep["new"]["pass_correct"],
            old.get("refusal_rate", "?"), rep["new"]["refusal_rate"]))

    out = ROUNDS_NEW / "compare_v1_v2.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[out] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
