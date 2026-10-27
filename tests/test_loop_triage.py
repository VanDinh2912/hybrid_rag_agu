# -*- coding: utf-8 -*-
"""Unit test triage: lỗi -> dữ liệu train cho ĐÚNG tầng, không rò rỉ test.

Ba luật được kiểm ở đây (triage là chỗ duy nhất vòng lặp được phép "học"):
1. item split=test không bao giờ sinh dòng train (chỉ đếm blocked_test_leak);
2. mọi dòng train phải mang provenance (round, item_id, verdict, lever);
3. câu trả lời mẫu cho tầng sinh là TRÍCH NIÊM từ gold_sentence, không phải văn do
   AI viết lại.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.generator import REFUSAL_TEXT
from tools.loop.triage import build_rows, gold_answer_for

GOLD_SENTENCE = "Mức thu bảo hiểm y tế là 546.480đ/12 tháng/SV."


def make_item(item_id: str, *, split: str = "trainpool", family: str = "EXACT", **over) -> dict:
    base = {
        "id": item_id,
        "family": family,
        "split": split,
        "raw_query": "Bảo hiểm y tế bao nhiêu?",
        "source_document": "tb-bhyt.pdf",
        "gold_chunk_id": 7,
        "gold_sentence": GOLD_SENTENCE,
        "primary_entity": "546.480",
        "required_entities": ["546.480"],
        "topic": "bhyt",
    }
    base.update(over)
    return base


def make_verdict(item_id: str, verdict: str, item: dict, **over) -> dict:
    base = {
        "id": item_id,
        "family": item["family"],
        "split": item["split"],
        "verdict": verdict,
        "raw_query": item["raw_query"],
        "answer_preview": "Mức 700.000đ.",
        "detail": {},
        "predicted_topic": item.get("topic"),
        "predicted_question_type": "TRA_CUU",
        "expected_question_type": None,
        "unsupported": [],
    }
    base.update(over)
    return base


def write_round(tmp_path: Path, pairs: list[tuple[dict, dict]]) -> Path:
    """pairs = [(item, verdict), ...] -> dựng thư mục round đúng cấu trúc run_round."""
    round_dir = tmp_path / "rx"
    round_dir.mkdir(parents=True, exist_ok=True)
    verdicts, results = [], []
    for item, verdict in pairs:
        verdicts.append(verdict)
        results.append(
            {
                "id": item["id"],
                "item": item,
                "answer": "Mức 700.000đ.",
                "contexts": [GOLD_SENTENCE, "Chunk gây nhiễu của văn bản khác, đủ dài để vượt ngưỡng 40 ký tự."],
                "sources": [
                    {"rank": 1, "chunk_id": 7, "source": item["source_document"], "tier": "2", "chars": 40},
                    {"rank": 2, "chunk_id": 8, "source": "khac.pdf", "tier": "1", "chars": 40},
                ],
            }
        )
    (round_dir / "verdicts_full.jsonl").write_text(
        "\n".join(json.dumps(v, ensure_ascii=False) for v in verdicts), encoding="utf-8"
    )
    (round_dir / "full.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results), encoding="utf-8"
    )
    return round_dir


def task_rows(rows: list[dict], task: str) -> list[dict]:
    return [r for r in rows if r["task"] == task]


class TestLawNoTestLeakage:
    def test_item_test_không_sinh_dòng_train(self, tmp_path):
        it_trong = make_item("TRAIN-1", split="trainpool")
        it_test = make_item("TEST-1", split="test")
        round_dir = write_round(
            tmp_path,
            [
                (it_trong, make_verdict("TRAIN-1", "FAIL_FABRICATED", it_trong)),
                (it_test, make_verdict("TEST-1", "FAIL_FABRICATED", it_test)),
            ],
        )
        rows, report = build_rows(round_dir, "rx")
        assert {r["provenance"]["item_id"] for r in rows} == {"TRAIN-1"}
        assert report["stats"]["blocked_test_leak"] == 1

    def test_mọi_dòng_train_đều_có_provenance(self, tmp_path):
        it = make_item("TRAIN-2")
        round_dir = write_round(tmp_path, [(it, make_verdict("TRAIN-2", "FAIL_RETRIEVAL", it))])
        rows, _ = build_rows(round_dir, "rx")
        for row in rows:
            assert {"round", "item_id", "verdict"} <= set(row["provenance"])
            assert row["provenance"]["round"] == "rx"
            assert row["lever"] in {"retrieval", "generation", "refusal", "classifier"}


class TestLeverRouting:
    def test_fail_retrieval_thành_retrieval_pair(self, tmp_path):
        it = make_item("R1")
        round_dir = write_round(tmp_path, [(it, make_verdict("R1", "FAIL_RETRIEVAL", it))])
        rows, report = build_rows(round_dir, "rx")
        pairs = task_rows(rows, "retrieval_pair")
        assert len(pairs) == 1
        assert pairs[0]["positive_chunk_id"] == 7
        assert 7 not in pairs[0]["negative_chunk_ids"] and 8 in pairs[0]["negative_chunk_ids"]
        assert report["failures_by_lever"]["retrieval"][0]["id"] == "R1"

    def test_fail_fabricated_thành_sft_trích_niêm(self, tmp_path):
        it = make_item("G1", family="EXACT")
        round_dir = write_round(tmp_path, [(it, make_verdict("G1", "FAIL_FABRICATED", it))])
        rows, _ = build_rows(round_dir, "rx")
        sft = task_rows(rows, "sft_extractive")
        assert len(sft) == 1
        assistant = sft[0]["messages"][-1]["content"]
        assert GOLD_SENTENCE in assistant  # nội dung DO tài liệu, không do AI viết
        assert "tb-bhyt.pdf" in assistant  # kèm trích dẫn nguồn
        assert sft[0]["gold_chunk_id"] == 7

    def test_hallucinated_on_unanswerable_dạy_từ_chối(self, tmp_path):
        it = make_item("H1", family="REFUSE_OOD", gold_chunk_id=None, expected_answer_type="refuse")
        round_dir = write_round(tmp_path, [(it, make_verdict("H1", "FAIL_HALLUCINATED_ON_UNANSWERABLE", it))])
        rows, _ = build_rows(round_dir, "rx")
        refusal = task_rows(rows, "sft_refusal")
        assert len(refusal) == 1
        assert refusal[0]["messages"][-1]["content"] == REFUSAL_TEXT
        assert "từ chối" in refusal[0]["messages"][0]["content"].lower()

    def test_overrefusal_co_can_cu_trong_cua_so_dinh_sinh_sft_row(self, tmp_path):
        """Bài học r1: 35/38 ca từ chối oan có câu vàng nguyên văn trong prompt.

        Nhãn verdict một mình không phân biệt được 'model không thấy căn cứ' và
        'model thấy mà vẫn từ chối'. `gold_in_top_k` là bằng chứng đo được, nên
        triage phải quy về ĐÚNG tầng: ca thấy-căn cứ-mà-vẫn-từ-chối là lỗi tầng
        sinh và dạy lại được; ca không chứng minh được căn cứ mới là chuyện ngưỡng.
        """
        it = make_item("O1")
        round_dir = write_round(
            tmp_path, [(it, make_verdict("O1", "FAIL_OVERREFUSAL", it, gold_in_top_k=True))]
        )
        rows, report = build_rows(round_dir, "rx")
        sft = task_rows(rows, "sft_extractive")
        assert len(sft) == 1
        assert sft[0]["lever"] == "generation"
        assert sft[0]["provenance"]["note"] == "overrefusal_evidence_in_window"
        assert GOLD_SENTENCE in sft[0]["messages"][-1]["content"]
        assert report["stats"]["sft_extractive_from_overrefusal"] == 1
        assert "guardrail" not in report["failures_by_lever"]

    def test_overrefusal_khong_chung_minh_can_cu_chi_ghi_bao_cao(self, tmp_path):
        it = make_item("O2", gold_chunk_id=None)
        round_dir = write_round(
            tmp_path, [(it, make_verdict("O2", "FAIL_OVERREFUSAL", it, gold_in_top_k=False))]
        )
        rows, report = build_rows(round_dir, "rx")
        assert rows == []
        assert report["failures_by_lever"]["guardrail"][0]["id"] == "O2"
        assert report["stats"]["overrefusal_threshold_only"] == 1

    def test_item_test_khong_bao_gio_vao_sft_du_o_lever_moi(self, tmp_path):
        it = make_item("O3", split="test")
        round_dir = write_round(
            tmp_path, [(it, make_verdict("O3", "FAIL_OVERREFUSAL", it, gold_in_top_k=True))]
        )
        rows, report = build_rows(round_dir, "rx")
        assert rows == []
        assert report["stats"]["blocked_test_leak"] == 1

    def test_chunk_vang_rank_5_van_vao_ngu_canh_cua_dong_train(self, tmp_path):
        """Dòng train không được cắt mất căn cứ: gold rank > 4 phải được ưu tiên.

        `contexts[:4]` cũ sẽ loại chunk vàng ở rank 5 -> tạo dòng train có đáp án
        nằm ngoài ngữ cảnh, tức là tự tay sinh dữ liệu dạy model bịa.
        """
        it = make_item("G9")
        verdict = make_verdict("G9", "FAIL_FABRICATED", it, gold_in_top_k=False)
        round_dir = write_round(tmp_path, [(it, verdict)])
        # dựng lại round với chunk vàng ở rank 5
        contexts = [f"chunk nhiễu {i}" * 20 for i in range(1, 5)] + [GOLD_SENTENCE]
        sources = [
            {"rank": i, "chunk_id": 100 + i, "source": f"nhieu{i}.pdf", "tier": "1"}
            for i in range(1, 5)
        ] + [{"rank": 5, "chunk_id": 7, "source": it["source_document"], "tier": "2"}]
        rows_json = [
            {
                "id": it["id"],
                "item": it,
                "answer": "Mức 700.000đ.",
                "contexts": contexts,
                "sources": sources,
            }
        ]
        (round_dir / "full.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows_json), encoding="utf-8"
        )
        rows, _ = build_rows(round_dir, "rx")
        sft = task_rows(rows, "sft_extractive")
        assert len(sft) == 1
        assert GOLD_SENTENCE in sft[0]["messages"][1]["content"]

    def test_khong_sinh_dong_train_khi_dap_an_khong_co_trong_ngu_canh(self, tmp_path):
        """Bất biến: đích của sft_extractive phải xuất hiện trong ngữ cảnh của chính nó."""
        it = make_item("G8", gold_chunk_id=None, required_entities=["999.999"], primary_entity="999.999")
        it["gold_sentence"] = "Một câu không tồn tại trong các chunk được truy xuất."
        round_dir = write_round(tmp_path, [(it, make_verdict("G8", "FAIL_FABRICATED", it))])
        rows, report = build_rows(round_dir, "rx")
        assert task_rows(rows, "sft_extractive") == []
        assert report["stats"]["skip_sft_target_not_in_context"] == 1

    def test_pass_không_tạo_gì_cả(self, tmp_path):
        it = make_item("P1")
        round_dir = write_round(
            tmp_path,
            [
                (it, make_verdict("P1", "PASS_CORRECT", it)),
                (make_item("P2"), make_verdict("P2", "PENDING_GENERATION", make_item("P2"))),
            ],
        )
        rows, report = build_rows(round_dir, "rx")
        assert rows == []
        assert report["failures_by_lever"] == {}


class TestClassifierLabels:
    def test_chỉ_ghi_nhãn_khi_dự_đoán_sai_và_là_trainpool(self, tmp_path):
        it_sai = make_item("C1", topic="bhyt")
        it_dung = make_item("C2", topic="che-do")
        round_dir = write_round(
            tmp_path,
            [
                (it_sai, make_verdict("C1", "FAIL_RETRIEVAL", it_sai, predicted_topic="khac")),
                (it_dung, make_verdict("C2", "FAIL_RETRIEVAL", it_dung, predicted_topic="che-do")),
                (
                    make_item("C3", split="test", topic="bhyt"),
                    make_verdict("C3", "FAIL_RETRIEVAL", make_item("C3", split="test"), predicted_topic="khac"),
                ),
            ],
        )
        rows, _ = build_rows(round_dir, "rx")
        labels = task_rows(rows, "classifier_label")
        assert [r["provenance"]["item_id"] for r in labels] == ["C1"]
        assert labels[0]["labels"] == {"topic": "bhyt", "question_type": "TRA_CUU"}
        assert labels[0]["predicted"]["topic"] == "khac"

    def test_câu_ngoài_phạm_vi_dán_nhãn_ngoai_pham_vi(self, tmp_path):
        """expected_question_type do verify ghi (family REFUSE_* -> NGOAI_PHAM_VI);
        triage chỉ dùng lại — nguồn sự thật là một chỗ duy nhất."""
        it = make_item("C4", family="REFUSE_OOD", gold_chunk_id=None, expected_answer_type="refuse", topic="bong da")
        round_dir = write_round(
            tmp_path,
            [
                (
                    it,
                    make_verdict(
                        "C4",
                        "FAIL_HALLUCINATED_ON_UNANSWERABLE",
                        it,
                        predicted_topic="the duc",
                        expected_question_type="NGOAI_PHAM_VI",
                    ),
                )
            ],
        )
        rows, _ = build_rows(round_dir, "rx")
        labels = task_rows(rows, "classifier_label")
        assert len(labels) == 1
        assert labels[0]["labels"]["question_type"] == "NGOAI_PHAM_VI"
        assert labels[0]["labels"]["topic"] == "bong da"


class TestGoldAnswerPhrasing:
    def test_cloze_trả_về_giá_trị_thiếu(self):
        it = make_item("Z1", family="CLOZE", primary_entity="2026")
        assert gold_answer_for(it, "kh.pdf").startswith("Giá trị còn thiếu là 2026")

    def test_source_lookup_trả_về_tên_văn_bản(self):
        it = make_item("Z2", family="SOURCE_LOOKUP")
        out = gold_answer_for(it, "tb-bhyt.pdf")
        assert "tb-bhyt.pdf" in out

    def test_trap_phải_nêu_đủ_cả_giá_trị_sai_lẫn_đúng(self):
        it = make_item("Z3", family="TRAP", wrong_value="1.092.960", correct_value="546.480")
        out = gold_answer_for(it, "tb-bhyt.pdf")
        assert "1.092.960" in out and GOLD_SENTENCE in out
