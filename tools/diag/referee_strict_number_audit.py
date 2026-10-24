"""Audit CHỈ ĐỌC: required_entities số ngắn khớp oan trong mã khác.

Bối cảnh (PA-20): trọng tài hiện tại dùng `_answer_covers_gold` -> `_number_in`; với
required_entities là số 1–2 chữ số, số vàng có thể "khớp" bên trong "B1"/"2021"/"2026-2028".
Script này KHÔNG phải trọng tài chính thức và KHÔNG sửa bất kỳ file nào ngoài `--out`.
Nó chỉ đọc `full.jsonl` + `verdicts_full.jsonl` của các round đã đóng, so hai cách khớp
(hiện tại vs strict `(?<!\\w)…(?!\\w)`), và liệt kê các dòng bị đổi trạng thái "covers gold".

Chạy:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/referee_strict_number_audit.py
    ... --rounds r5,r8,r9,r10 --out data/loop/diag/referee_strict_number_audit.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.text_utils import fold  # noqa: E402
from tools.loop.verify import (  # noqa: E402
    _answer_covers_gold,
    _entity_in_answer,
    referee_fingerprint,
)

ROUNDS_DIR = ROOT / "data" / "loop" / "rounds"
DEFAULT_OUT = ROOT / "data" / "loop" / "diag" / "referee_strict_number_audit.json"


def strict_entity_in_answer(entity: str, answer: str) -> bool:
    """Bản strict CHỈ cho số 1–2 chữ số: phải đứng độc lập, không nằm trong B1/2021.

    Các loại thực thể khác giữ nguyên hành vi hiện tại để audit chỉ đo đúng một thay đổi.
    """
    ent = (entity or "").strip()
    if re.fullmatch(r"\d{1,2}", ent):
        return (
            re.search(rf"(?<![\w]){re.escape(fold(ent))}(?![\w])", fold(answer))
            is not None
        )
    return _entity_in_answer(ent, answer)


def covers_strict(item: dict[str, Any], answer: str) -> bool:
    """Mô phỏng `_answer_covers_gold` với strict_entity_in_answer."""
    required = [e for e in item.get("required_entities", []) if e]
    if not required:
        primary = item.get("primary_entity")
        return strict_entity_in_answer(primary, answer) if primary else False
    return any(strict_entity_in_answer(e, answer) for e in required)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def audit_round(round_name: str, *, rounds_dir: Path = ROUNDS_DIR) -> dict[str, Any]:
    """Trả dict tổng hợp; không ghi file."""
    full_path = rounds_dir / round_name / "full.jsonl"
    verdict_path = rounds_dir / round_name / "verdicts_full.jsonl"
    if not full_path.exists() or not verdict_path.exists():
        raise FileNotFoundError(f"thiếu {full_path} hoặc {verdict_path}")

    verdicts = {row["id"]: row.get("verdict") for row in load_jsonl(verdict_path)}
    flips: list[dict[str, Any]] = []
    n_rows = n_answered = 0
    for row in load_jsonl(full_path):
        n_rows += 1
        answer = row.get("answer") or ""
        if not answer:
            continue
        n_answered += 1
        item = row.get("item") or {}
        current = _answer_covers_gold(item, answer)
        strict = covers_strict(item, answer)
        if current and not strict:
            flips.append(
                {
                    "id": row.get("id"),
                    "family": (item.get("family") or row.get("family")),
                    "verdict": verdicts.get(row.get("id")),
                    "required_entities": item.get("required_entities"),
                    "gold_sentence": (item.get("gold_sentence") or "")[:240],
                    "answer_preview": answer[:240],
                }
            )
    return {
        "round": round_name,
        "n_rows": n_rows,
        "n_answered": n_answered,
        "n_covers_now": sum(
            1
            for row in load_jsonl(full_path)
            if (row.get("answer") or "")
            and _answer_covers_gold(row.get("item") or {}, row.get("answer") or "")
        ),
        "n_flips": len(flips),
        "n_flips_of_pass_correct": sum(1 for f in flips if f["verdict"] == "PASS_CORRECT"),
        "flips": flips,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit read-only PA-20 (không phải trọng tài).")
    parser.add_argument("--rounds", default="r5,r8,r9,r10")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out = {
        "note": (
            "CHỈ ĐỌC — không phải trọng tài chính thức, không dùng thay số round. "
            "Strict chỉ áp cho required_entities là số 1-2 chữ số."
        ),
        "referee_fingerprint": referee_fingerprint(),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_rule": r"(?<![\w])<số>(?![\w])",
        "rounds": [],
    }
    for name in [x.strip() for x in args.rounds.split(",") if x.strip()]:
        summary = audit_round(name)
        out["rounds"].append(summary)
        print(
            f"[audit] {name}: rows={summary['n_rows']} flips={summary['n_flips']} "
            f"flips_of_PASS_CORRECT={summary['n_flips_of_pass_correct']}"
        )
        for f in summary["flips"]:
            print(f"   - {f['id']} verdict={f['verdict']} required={f['required_entities']}")

    if args.dry_run:
        print("[audit] dry-run: không ghi file")
        return 0
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[audit] ghi {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
