"""Test cho audit read-only PA-20 (strict số ngắn). Không chạy model, không đọc round thật."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.diag.referee_strict_number_audit import (  # noqa: E402
    audit_round,
    covers_strict,
    strict_entity_in_answer,
)


def test_strict_short_number_does_not_match_inside_code_or_year():
    answer = "Theo Bản mô tả (năm 2021), chuẩn đầu ra ELO 9; B1; 3/6."
    assert strict_entity_in_answer("1", answer) is False
    assert strict_entity_in_answer("2", "Giai đoạn 2026-2028") is False


def test_strict_short_number_requires_standalone_occurrence():
    assert strict_entity_in_answer("1", "Đó là ELO 1 của chương trình.") is True
    assert strict_entity_in_answer("10", "Đó là ELO 10 của chương trình.") is True


def test_strict_leaves_long_numbers_to_current_matcher():
    assert strict_entity_in_answer("2024", "Năm học 2024-2025") is True
    assert strict_entity_in_answer("2570", "Quyết định số 2570/QĐ-DHAG") is True
    assert strict_entity_in_answer("1050", "Số 1050/TB-ĐHAG") is True


def test_covers_strict_any_entity_and_primary_fallback():
    item = {"required_entities": ["1", "20"]}
    assert covers_strict(item, "Năm 2026 và năm 2021") is False
    assert covers_strict(item, "Điều 20 quy định") is True
    assert covers_strict({"primary_entity": "1050"}, "Số 1050/TB-ĐHAG") is True
    assert covers_strict({"required_entities": []}, "không có gì") is False


def _write_round(tmp_path: Path, rows: list[dict], verdicts: list[dict]) -> None:
    rdir = tmp_path / "rX"
    rdir.mkdir()
    (rdir / "full.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    (rdir / "verdicts_full.jsonl").write_text(
        "\n".join(json.dumps(v, ensure_ascii=False) for v in verdicts) + "\n", encoding="utf-8"
    )


def test_audit_round_counts_flips_without_mutating_input(tmp_path):
    rows = [
        {
            "id": "A",
            "answer": "Theo Bản (2021), ELO 9, B1.",
            "item": {"family": "CLOZE", "required_entities": ["1"], "gold_sentence": "ELO 1"},
        },
        {
            "id": "B",
            "answer": "Đáp án là ELO 1.",
            "item": {"family": "CLOZE", "required_entities": ["1"], "gold_sentence": "ELO 1"},
        },
        {"id": "C", "answer": "", "item": {"family": "CLOZE", "required_entities": ["1"]}},
    ]
    verdicts = [
        {"id": "A", "verdict": "PASS_CORRECT"},
        {"id": "B", "verdict": "PASS_CORRECT"},
        {"id": "C", "verdict": "FAIL_INCOMPLETE"},
    ]
    _write_round(tmp_path, rows, verdicts)
    full_path = tmp_path / "rX" / "full.jsonl"
    before = hashlib.sha256(full_path.read_bytes()).hexdigest()

    summary = audit_round("rX", rounds_dir=tmp_path)

    assert summary["n_rows"] == 3
    assert summary["n_answered"] == 2
    assert summary["n_flips"] == 1
    assert summary["n_flips_of_pass_correct"] == 1
    assert summary["flips"][0]["id"] == "A"
    assert hashlib.sha256(full_path.read_bytes()).hexdigest() == before
