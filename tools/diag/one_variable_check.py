# -*- coding: utf-8 -*-
"""T4 — kiểm "một biến" bằng bằng chứng trên đĩa, không bằng lời khai.

Round đổi model sinh chỉ được gọi là one-variable nếu NHỮNG THỨ KHÔNG PHẢI TẦNG SINH vẫn
giống hệt: cửa ngữ cảnh (`contexts`), danh sách nguồn+kèm hạng (`sources`), và bản chuẩn hóa
câu hỏi mà pipeline đưa vào prompt (`normalized_query`). Nếu một trong ba cái đổi, thì số
chênh về model đã lẫn thay đổi ở tầng truy xuất/đầu vào.

So sánh từng ký tự trên phần id hai round có chung. Ghi JSON vào
`data/loop/diag/one_variable_check.json`.

    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/one_variable_check.py \
        --candidate r10 --baseline r5
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ROUNDS = ROOT / "data" / "loop" / "rounds"
FIELDS = ("contexts", "sources", "normalized_query", "labels", "retrieval_config")


def load_rows(round_name: str) -> dict[str, dict]:
    path = ROUNDS / round_name / "full.jsonl"
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows.setdefault(row["id"], row)
    return rows


def digest(value) -> str:
    return hashlib.sha1(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--out", default=str(ROOT / "data" / "loop" / "diag" / "one_variable_check.json"))
    args = ap.parse_args()

    cand, base = load_rows(args.candidate), load_rows(args.baseline)
    common = sorted(set(cand) & set(base))
    report: dict[str, dict] = {}
    mismatches: dict[str, list[str]] = {}
    for field in FIELDS:
        same = [i for i in common if digest(cand[i].get(field)) == digest(base[i].get(field))]
        report[field] = {
            "identical": len(same),
            "differing": len(common) - len(same),
            "note": "so SHA-1 trên toàn bộ cấu trúc của trường, từng ký tự",
        }
        mismatches[field] = [
            i for i in common if digest(cand[i].get(field)) != digest(base[i].get(field))
        ][:10]

    answers_differ = sum(1 for i in common if (cand[i].get("answer") or "") != (base[i].get("answer") or ""))
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate": args.candidate,
        "baseline": args.baseline,
        "n_common": len(common),
        "n_candidate_only": len(set(cand) - set(base)),
        "n_baseline_only": len(set(base) - set(cand)),
        "non_generation_fields": report,
        "answer_text_differing": answers_differ,
        "mismatch_ids_first10": mismatches,
        "conclusion_rule": "one-variable CHỈ được chấp nhận khi contexts/sources/normalized_query "
        "identical = n_common (answer khác là ĐÚNG vì đó là biến số đang đo)",
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
