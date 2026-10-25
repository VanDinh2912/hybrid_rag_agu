# -*- coding: utf-8 -*-
"""T6b — tính precision/recall của TRỌNG TÀI so với nhãn tay.

Ăn vào:
  * phiếu gán nhãn ĐÃ ĐIỀN `nhan_tay` (referee_labeling_<round>.jsonl)
  * manifest do referee_sample.py sinh ra: id -> verdict -> tầng quy chiếu của trọng tài

Trọng tài "dự đoán" một trong 4 lớp bằng cách ánh xạ verdict của nó (VERDICT_TO_STRATUM).
Người đọc cũng chọn một trong 4 lớp đó. So khớp -> độ chính xác toàn cục, ma trận nhầm lẫn,
precision/recall/F1 theo từng lớp, và Cohen's kappa (đo sự đồng thuận vượt trên ngẫu nhiên).

`nhan_tay == khong_ro` bị LOẠI khỏi các chỉ số (không phải phán quyết) nhưng vẫn báo số lượng.

Đọc bằng chứng cho báo cáo: một verdict chỉ đáng tin để làm "cân" nếu trọng tài khớp người
trên từng lớp, đặc biệt lớp "sai" (phát hiện bịa) và "tu_boi_oan" (không phạt oan).

Dùng:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/referee_agreement.py --round r5
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIAG = ROOT / "data" / "loop" / "diag"

CLASSES = ("dung", "sai", "tu_boi_dung", "tu_boi_oan")

VERDICT_TO_STRATUM = {
    "PASS_CORRECT": "dung",
    "PASS_CORRECTED_TRAP": "dung",
    "PASS_REFUSAL": "tu_boi_dung",
    "FAIL_OVERREFUSAL": "tu_boi_oan",
    "FAIL_FABRICATED": "sai",
    "FAIL_CONFIRMED_FALSE_PREMISE": "sai",
    "FAIL_HALLUCINATED_ON_UNANSWERABLE": "sai",
    "FAIL_INCOMPLETE": "sai",
    "FAIL_RETRIEVAL": "sai",
}

CLASS_LABEL = {
    "dung": "Đúng & có căn cứ",
    "sai": "Sai / không căn cứ",
    "tu_boi_dung": "Từ chối đúng",
    "tu_boi_oan": "Từ chối oan",
}

ALLOWED_LABELS = CLASSES + ("khong_ro",)


class LabelError(ValueError):
    """Phiếu gán nhãn hỏng: thiếu nhãn (chế độ strict) hoặc nhãn sai định dạng."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def validate_labels(rows: list[dict], allow_missing: bool = True) -> None:
    """Kiểm phiếu TRƯỚC khi tính điểm.

    * nhãn khác rỗng nhưng không nằm trong 4 lớp + `khong_ro` => LUÔN báo lỗi
      (không im lặng bỏ dòng: một nhãn gõ sai sẽ làm precision/recall lệch mà không ai biết);
    * nhãn rỗng => báo lỗi khi `allow_missing=False` (chế độ chấm chính thức, `--strict`).
    """
    problems: list[str] = []
    for r in rows:
        rid = r.get("id") or "(không id)"
        label = (r.get("nhan_tay") or "").strip()
        if not label:
            if not allow_missing:
                problems.append(f"{rid}: thiếu nhãn tay")
            continue
        if label not in ALLOWED_LABELS:
            problems.append(f"{rid}: nhãn không hợp lệ {label!r} (chỉ nhận {', '.join(ALLOWED_LABELS)})")
    if problems:
        raise LabelError(problems)


def score_labels(rows: list[dict], verdict_by_id: dict[str, str]) -> dict:
    """Tính toàn bộ chỉ số từ phiếu đã điền + ánh xạ verdict -> tầng.

    Hàm thuần (không đọc/ghi đĩa) để test được bằng phiếu giả có đáp án biết trước.
    """
    filled, unfilled, no_referee = [], [], []
    for r in rows:
        label = (r.get("nhan_tay") or "").strip()
        rid = r["id"]
        if not label:
            unfilled.append(rid)
            continue
        ref_stratum = VERDICT_TO_STRATUM.get(verdict_by_id.get(rid, ""))
        if ref_stratum is None:
            no_referee.append(rid)
            continue
        filled.append((label, ref_stratum, rid, verdict_by_id.get(rid, "")))

    scored = [(h, rf) for h, rf, _, _ in filled if h in CLASSES]
    unclear = [(h, rf) for h, rf, _, _ in filled if h == "khong_ro"]
    n = len(scored)
    correct = sum(1 for h, rf in scored if h == rf)
    return {
        "n_worksheet_rows": len(rows),
        "n_filled": len(filled),
        "n_unfilled": len(unfilled),
        "n_no_referee": len(no_referee),
        "n_unclear_dropped": len(unclear),
        "n_scored": n,
        "overall_accuracy": round(correct / n, 4) if n else None,
        "cohen_kappa": cohen_kappa(scored, list(CLASSES)),
        "per_class": per_class_metrics(scored, list(CLASSES)),
        "confusion_human_rows_x_referee_cols": confusion_matrix(scored, list(CLASSES)),
        "referee_verdict_breakdown": dict(Counter(v for _, _, _, v in filled)),
        "unfilled_ids": unfilled,
        "no_referee_ids": no_referee,
        "class_labels": CLASS_LABEL,
    }


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def cohen_kappa(pairs: list[tuple[str, str]], classes: list[str]) -> float | None:
    """Cohen's kappa cho hai định danh trên cùng tập mẫu (không suy rộng)."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in classes)
    if pe >= 1.0:
        return None  # một phía đơn nhãn -> kappa không định nghĩa
    return round((po - pe) / (1 - pe), 4)


def per_class_metrics(pairs: list[tuple[str, str]], classes: list[str]) -> dict:
    out = {}
    for c in classes:
        tp = sum(1 for h, r in pairs if r == c and h == c)
        fp = sum(1 for h, r in pairs if r == c and h != c)
        fn = sum(1 for h, r in pairs if r != c and h == c)
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        f1 = (
            round(2 * prec * rec / (prec + rec), 4)
            if prec and rec and (prec + rec)
            else (0.0 if (prec is not None and rec is not None) else None)
        )
        out[c] = {
            "support_human": sum(1 for h, _ in pairs if h == c),
            "n_predicted_by_referee": tp + fp,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(prec, 4) if prec is not None else None,
            "recall": round(rec, 4) if rec is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }
    return out


def confusion_matrix(pairs: list[tuple[str, str]], classes: list[str]) -> dict:
    m: dict[str, dict[str, int]] = {h: {r: 0 for r in classes} for h in classes}
    for h, r in pairs:
        m[h][r] += 1
    return m


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--round", default="r5")
    ap.add_argument("--worksheet", default="")
    ap.add_argument("--manifest", default="")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="báo lỗi nếu còn dòng thiếu nhãn tay (dùng khi chấm chính thức)",
    )
    args = ap.parse_args()

    ws_path = Path(args.worksheet) if args.worksheet else DIAG / f"referee_labeling_{args.round}.jsonl"
    man_path = Path(args.manifest) if args.manifest else DIAG / "referee_sample_manifest.json"
    if not ws_path.exists():
        raise SystemExit(f"Thiếu phiếu gán nhãn: {ws_path}")
    if not man_path.exists():
        raise SystemExit(f"Thiếu manifest: {man_path} (chạy referee_sample.py trước)")

    rows = read_jsonl(ws_path)
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    verdict_by_id = {s["id"]: s["referee_verdict"] for s in manifest.get("samples", [])}

    try:
        validate_labels(rows, allow_missing=not args.strict)
    except LabelError as exc:
        raise SystemExit(f"Phiếu gán nhãn KHÔNG hợp lệ ({len(exc.problems)} dòng):\n  - "
                         + "\n  - ".join(exc.problems[:20])
                         + ("\n  ..." if len(exc.problems) > 20 else ""))

    stats = score_labels(rows, verdict_by_id)
    n = stats["n_scored"]
    unclear = stats["n_unclear_dropped"]
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "round": args.round,
        "worksheet": str(ws_path),
        **stats,
    }

    out_path = DIAG / f"referee_agreement_{args.round}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # Bảng tóm tắt ra console (ASCII, tránh lỗi cp1258 khi in tiếng Việt có dấu).
    print(f"[T6b-agreement] round={args.round} n_scored={n} (dropped unclear={unclear}, "
          f"unfilled={stats['n_unfilled']})")
    print(f"[T6b-agreement] overall_accuracy={stats['overall_accuracy']}  "
          f"cohen_kappa={result['cohen_kappa']}")
    header = f"{'class':14}{'sup':>5}{'nP':>5}{'prec':>8}{'rec':>8}{'f1':>8}"
    print(header)
    for c in CLASSES:
        m = result["per_class"][c]
        fmt = lambda x: "-" if x is None else f"{x:.3f}"
        print(f"{c:14}{m['support_human']:>5}{m['n_predicted_by_referee']:>5}"
              f"{fmt(m['precision']):>8}{fmt(m['recall']):>8}{fmt(m['f1']):>8}")
    print(f"[T6b-agreement] ghi: {out_path}")


if __name__ == "__main__":
    main()
