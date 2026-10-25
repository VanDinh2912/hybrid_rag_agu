"""B3 — chấm lại OFFLINE các round PHA TRUY XUẤT bằng trọng tài v2 (PA-2 + PA-20).

Vì sao cần một script riêng (không mở rộng `rescore_rounds_v2.py`): script đó đã commit
và artifact của nó (`data/loop/rounds_v2/compare_v1_v2.json`) đã công bố trong
`docs/reports/B2.md`; luật tự trị cấm chạy lại dụng cụ đo ghi đè artifact đã công bố.
Ở đây chỉ thêm THƯ MỤC MỚI, không sửa gì ở `data/loop/rounds/`.

Vì sao round truy xuất cần chấm lại: `tools/loop/gate.py::compatibility()` từ chối so hai
round khác chữ ký trọng tài (đúng thiết kế — xem `docs/reports/B2.md`). Round mới r16 bắt
buộc chấm bằng v2 (`2911c69f740d`) vì PA-2/PA-20 đã được duyệt, còn baseline r11 đã đóng
ghi `9f1179ccab74`. Thông báo của cổng chỉ đường hợp lệ: "chạy lại lệnh round của round
cũ khi <phase>.jsonl đã đủ dòng để chấm lại, rồi mới mở cổng" — script này làm đúng bước
đó KHÔNG gọi model: đọc `retrieval.jsonl` của round cũ, chấm lại từng dòng bằng
`verify.score_item` giống hệt `tools/loop/run_round.py:526-537`, ghi vào thư mục mới.

Kiểm chứng bắt buộc trước khi dùng baseline mới: verdict chấm lại PHẢI khớp verdict đã
công bố (với pha retrieval, PA-2/PA-20 chỉ chạm tầng sinh — `_answer_covers_gold`/cờ
proper — nên số chênh phải bằng 0). Nếu lệch, in từng ca và KHÔNG coi là tương đương.

Lệnh tái lập:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/rescore_retrieval_round_v2.py \
        --rounds r11,r12
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.loop import verify  # noqa: E402
from tools.loop.run_round import _percentile, lever_of  # noqa: E402  (giống hệt dụng cụ ghi round)
from tools.loop.verify import aggregate, score_item  # noqa: E402

ROUNDS_OLD = ROOT / "data" / "loop" / "rounds"
ROUNDS_NEW = ROOT / "data" / "loop" / "rounds_v2"
TESTSET = ROOT / "data" / "loop" / "testset_v1.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _median(values: list[float]):
    """Đúng công thức run_round.py:615 — phần tử thứ `n//2` của danh sách đã sắp xếp."""
    return sorted(values)[len(values) // 2] if values else None


def _phan_vi(values: list[float], q: float):
    """p95 theo `_percentile` của run_round (phần tử thứ ceil(q*n)-1, có round 2)."""
    got = _percentile(list(values), q)
    return round(got, 2) if isinstance(got, float) else got


def rescore(name: str, *, phase: str = "retrieval", top_k: int = 6) -> dict:
    old_dir = ROUNDS_OLD / name
    rows_path = old_dir / f"{phase}.jsonl"
    if not rows_path.exists():
        raise SystemExit(f"[{name}] không có {rows_path.name} — round này không phải {phase}-only?")

    rows = load_jsonl(rows_path)
    items_now = {r["id"]: r for r in load_jsonl(TESTSET)}
    n_item_drift = 0
    verdicts: list[dict] = []
    for row in rows:
        item = row.get("item") or {}
        if item.get("id") != row.get("id"):
            raise SystemExit(f"[{name}] dòng thiếu/khác id — không phải {phase}.jsonl chuẩn: {row.get('id')!r}")
        ref = items_now.get(row["id"])
        if ref is not None and ref != item:
            n_item_drift += 1
        if row.get("error"):  # giống hệt nhánh error trong run_round.py:530
            verdicts.append({
                "id": row["id"], "family": item.get("family"), "split": item.get("split"),
                "verdict": "FAIL_SYSTEM_ERROR", "severity": 3, "raw_query": item.get("raw_query"),
                "answer_preview": "", "unsupported": [], "detail": {"error": row["error"]},
            })
            continue
        verdicts.append(score_item(item, row, top_k=top_k))

    new_dir = ROUNDS_NEW / name
    new_dir.mkdir(parents=True, exist_ok=True)
    # attribute.py / bonus_paired.py đọc cả verdicts LẪN <phase>.jsonl — chép nguyên byte
    # sang thư mục mới để round chấm lại tự chứa (thư mục cũ không bị chạm).
    shutil.copy2(rows_path, new_dir / f"{phase}.jsonl")
    with (new_dir / f"verdicts_{phase}.jsonl").open("w", encoding="utf-8") as fh:
        for v in verdicts:
            fh.write(json.dumps(v, ensure_ascii=False) + "\n")

    old_summary_path = old_dir / f"round_summary_{phase}.json"
    old_summary = json.loads(old_summary_path.read_text(encoding="utf-8")) if old_summary_path.exists() else {}
    old_settings = dict(old_summary.get("settings") or {})
    referee_original = old_settings.get("referee")
    settings = dict(old_settings)
    settings["referee"] = verify.referee_fingerprint()

    latencies = [v["latency_seconds"] for v in verdicts if v.get("latency_seconds")]
    answered = [v for v in verdicts if not v.get("is_refusal") and v.get("answer_chars", 0) > 0]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "round": name,
        "rescore_of": f"data/loop/rounds/{name}/{phase}.jsonl",
        "rescore_reason": (
            "mở cổng gate với round mới chấm bằng trọng tài v2 — compatibility() từ chối "
            "so hai chữ ký khác nhau"
        ),
        "settings": settings,
        "n_scored": len(verdicts),
        "n_item_drift_vs_current_testset": n_item_drift,
        "verdict_counts": dict(Counter(v["verdict"] for v in verdicts)),
        "by_family": aggregate(verdicts, "family"),
        "by_split": aggregate(verdicts, "split"),
        "failures_by_lever": dict(Counter(lever_of(v) for v in verdicts)),
        "fabrication_rate_on_answered": (
            round(sum(1 for v in answered if v["unsupported"]) / len(answered), 4) if answered else None
        ),
        "refusal_rate": round(sum(1 for v in verdicts if v.get("is_refusal")) / len(verdicts), 4) if verdicts else None,
        "median_latency": _median(latencies),
        "p95_latency": _phan_vi(latencies, 0.95),
        "referee_original": referee_original,
        "referee_v2": verify.referee_fingerprint(),
    }
    (new_dir / f"round_summary_{phase}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- đối chiếu với verdict ĐÃ CÔNG BỐ: pha retrieval không được đổi gì
    old_verdicts_path = old_dir / f"verdicts_{phase}.jsonl"
    old_rows = {r["id"]: r for r in load_jsonl(old_verdicts_path)} if old_verdicts_path.exists() else {}
    new_rows = {v["id"]: v for v in verdicts}
    diffs = []
    for iid in sorted(set(old_rows) | set(new_rows)):
        ov, nv = old_rows.get(iid, {}).get("verdict"), new_rows.get(iid, {}).get("verdict")
        og = bool(old_rows.get(iid, {}).get("gold_in_top_k"))
        ng = bool(new_rows.get(iid, {}).get("gold_in_top_k"))
        if ov != nv or og != ng:
            diffs.append({"id": iid, "old": ov, "new": nv, "old_gold": og, "new_gold": ng})
    try:
        out_dir_rel = str(new_dir.relative_to(ROOT)).replace("\\", "/")
    except ValueError:  # test chạy trong tmp_path — không nằm dưới ROOT
        out_dir_rel = str(new_dir).replace("\\", "/")
    return {
        "round": name,
        "phase": phase,
        "n_rows": len(verdicts),
        "n_published_rows": len(old_rows),
        "n_diff_vs_published": len(diffs),
        "diffs": diffs[:20],
        "n_item_drift": n_item_drift,
        "verdict_counts": summary["verdict_counts"],
        "published_counts": dict(Counter(r.get("verdict") for r in old_rows.values())),
        "referee_original": referee_original,
        "referee_v2": verify.referee_fingerprint(),
        "out_dir": out_dir_rel,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Chấm lại offline round pha truy xuất bằng trọng tài v2.")
    ap.add_argument("--rounds", default="r11,r12")
    ap.add_argument("--phase", default="retrieval", choices=["retrieval", "full"])
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--out", default="", help="ghi báo cáo đối chiếu JSON (mặc định rounds_v2/rescore_<phase>_v2.json)")
    args = ap.parse_args(argv)
    if verify.referee_fingerprint() == "9f1179ccab74":
        raise SystemExit("[referee] vẫn là v1 — PA-2/PA-20 chưa được áp dụng?")

    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "referee_v2": verify.referee_fingerprint(), "phase": args.phase, "rounds": []}
    rc = 0
    for name in [r.strip() for r in args.rounds.split(",") if r.strip()]:
        rep = rescore(name, phase=args.phase, top_k=args.top_k)
        report["rounds"].append(rep)
        print("[{0}] {1} dòng: {2} verdict {3}; so với bản công bố: {4} lệch; item drift {5}".format(
            rep["round"], rep["n_rows"], rep["phase"],
            " ".join(f"{k}={v}" for k, v in sorted(rep["verdict_counts"].items())),
            rep["n_diff_vs_published"], rep["n_item_drift"]))
        for d in rep["diffs"]:
            print("   LỆCH:", d)
        if rep["n_diff_vs_published"]:
            rc = 1
    out = Path(args.out) if args.out else ROUNDS_NEW / f"rescore_{args.phase}_v2.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[out] {out}")
    print("[ket luan]", "tương đương bản công bố — dùng được làm baseline" if rc == 0
          else "CÓ verdict lệch — KHÔNG được coi là tương đương, phải giải thích trước khi mở cổng")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
