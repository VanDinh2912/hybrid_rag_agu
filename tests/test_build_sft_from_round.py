# -*- coding: utf-8 -*-
"""Unit test cho `tools/train/build_sft_from_round.py` (T4b — chỉ dựng dữ liệu, không train).

Bốn điều phải chứng minh được bằng test, vì chúng là ràng buộc của đặc tả T4b:

* group split chia theo **tài liệu**, không theo item — một `source_document` không bao giờ
  xuất hiện ở cả hai bên;
* chia **tất định** theo seed (chạy lại phải ra đúng tập holdout, nếu không thì không lần được
  số liệu cũ);
* bỏ trùng theo item id khi gộp nhiều round (cùng một ca từ chối oan trong r5 và r6 không được
  thành hai dòng train);
* số dòng bị chặn (`blocked_test_leak`, `skip_sft_target_not_in_context`) phải thoát ra được
  trong ledger — đó là con số báo cáo, không phải phần phụ.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.train.build_sft_from_round import (
    collect,
    group_split,
    read_items,
    token_cost_proxy,
    write_outputs,
)


def make_item(i: int, doc: str, split: str = "trainpool", family: str = "CLOZE") -> dict:
    return {
        "id": f"ITEM-{i}",
        "raw_query": f"Sinh viên học lại tối đa bao nhiêu lần ({i})?",
        "family": family,
        "split": split,
        "source_document": doc,
        "gold_chunk_id": f"chunk-{i}",
        "primary_entity": "8",
        "required_entities": ["8", "lần"],
        "gold_sentence": f"Sinh viên được học lại tối đa 8 lần đối với học phần {i}.",
    }


def make_round(round_dir: Path, items: list[dict], blocked_no_context: bool = False) -> None:
    """Viết `verdicts_full.jsonl` + `full.jsonl` đủ khung để triage.build_rows chạy được."""
    round_dir.mkdir(parents=True, exist_ok=True)
    verdicts, rows = [], []
    for item in items:
        verdicts.append(
            {
                "id": item["id"],
                "verdict": "FAIL_OVERREFUSAL",
                "gold_in_top_k": True,
                "item": item,
                "answer_preview": "Không đủ thông tin để trả lời.",
            }
        )
        if blocked_no_context:
            contexts, sources = [], []  # không có căn cứ -> skip_sft_target_not_in_context
        else:
            contexts = [f"Mục 4.2: {item['gold_sentence']}", "Văn bản nhiễu không liên quan."]
            sources = [
                {"source": item["source_document"], "chunk_id": item["gold_chunk_id"], "tier": "1"},
                {"source": item["source_document"], "chunk_id": "khac", "tier": "1"},
            ]
        rows.append(
            {
                "id": item["id"],
                "item": item,
                "answer": "Không đủ thông tin để trả lời.",
                "contexts": contexts,
                "sources": sources,
            }
        )
    with (round_dir / "verdicts_full.jsonl").open("w", encoding="utf-8") as fh:
        for v in verdicts:
            fh.write(json.dumps(v, ensure_ascii=False) + "\n")
    with (round_dir / "full.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


@pytest.fixture
def pool(tmp_path: Path) -> Path:
    """Ba tài liệu, năm item trainpool + một item split=test (phải bị chặn)."""
    rounds_root = tmp_path / "rounds"
    items = [
        make_item(1, "quy-che-ctdt.pdf"),
        make_item(2, "quy-che-ctdt.pdf"),
        make_item(3, "quy-che-dao-tao.pdf"),
        make_item(4, "quy-che-dao-tao.pdf"),
        make_item(5, "thong-tu-tai-chinh.pdf"),
        make_item(6, "quy-che-ctdt.pdf", split="test"),
    ]
    make_round(rounds_root / "rfake", items)
    return rounds_root


def test_read_items_lay_duoc_item_tu_verdicts(pool):
    items = read_items(pool / "rfake")
    assert len(items) == 6
    assert items["ITEM-1"]["source_document"] == "quy-che-ctdt.pdf"


def test_collect_giu_dung_nguon_va_chan_leak(pool):
    rows, ledger = collect(["rfake"], pool)
    ids = {r["provenance"]["item_id"] for r in rows}

    assert len(rows) == 5, "năm item trainpool phải cho năm dòng SFT"
    assert "ITEM-6" not in ids, "item split=test không được thành dòng train"
    assert ledger["blocked"]["blocked_test_leak"] == 1
    assert ledger["n_documents"] == 3
    assert {r["group_document"] for r in rows} == {
        "quy-che-ctdt.pdf",
        "quy-che-dao-tao.pdf",
        "thong-tu-tai-chinh.pdf",
    }
    # Đặc tả T4b: nguồn là over-refusal CÓ căn cứ trong cửa sổ.
    assert all(r["provenance"]["note"] == "overrefusal_evidence_in_window" for r in rows)


def test_bat_bien_7_dong_khong_can_cu_bi_chan(tmp_path):
    rounds_root = tmp_path / "rounds"
    make_round(rounds_root / "rnoctx", [make_item(1, "a.pdf")], blocked_no_context=True)
    rows, ledger = collect(["rnoctx"], rounds_root)

    assert rows == []
    assert ledger["blocked"]["skip_sft_target_not_in_context"] == 1


def test_group_split_khong_bao_gio_cat_doi_document(pool):
    rows, _ = collect(["rfake"], pool)
    train, holdout, meta = group_split(rows, test_fraction=0.3, seed=20261024)

    train_docs = {r["group_document"] for r in train}
    hold_docs = {r["group_document"] for r in holdout}
    assert train_docs & hold_docs == set(), "một tài liệu xuất hiện ở cả hai bên"
    assert len(train) + len(holdout) == len(rows)
    assert meta["holdout_documents"] == sorted(meta["holdout_documents"], key=str)
    # Cả ba nhóm document đều không được rỗng.
    assert meta["n_holdout_rows"] >= 1 and meta["n_train_rows"] >= 1


def test_group_split_tat_dinh_theo_seed(pool):
    rows, _ = collect(["rfake"], pool)
    a = group_split(rows, 0.3, 20261024)[2]["holdout_documents"]
    b = group_split(rows, 0.3, 20261024)[2]["holdout_documents"]
    assert a == b, "cùng seed phải trả ra cùng tập holdout (số liệu phải lần lại được)"


def test_gop_nhieng_round_khong_nhan_doi_cung_mot_item(tmp_path, pool):
    """r5 và r6 chấm cùng 100 id: một ca từ chối oan chỉ được thành MỘT dòng train."""
    rounds_root = tmp_path / "rounds"
    items = [make_item(1, "a.pdf"), make_item(2, "b.pdf")]
    make_round(rounds_root / "r5", items)
    make_round(rounds_root / "r6", items)

    rows, ledger = collect(["r5", "r6"], rounds_root)
    assert len(rows) == 2
    assert ledger["blocked"]["deduped_same_item_across_rounds"] == 2
    assert {r["source_round"] for r in rows} == {"r5"}


def test_tat_co_the_bat_dong_refusal_khi_duoc_chp(tmp_path):
    rounds_root = tmp_path / "rounds"
    make_round(rounds_root / "rfake", [make_item(1, "a.pdf")])
    rows_on, _ = collect(["rfake"], rounds_root, include_refusal_rows=True)
    assert len(rows_on) == 1  # không có sft_refusal trong round giả => vẫn đúng một dòng extractive


def test_cost_proxy_dem_dong_vuot_tram_dinh(tmp_path):
    rounds_root = tmp_path / "rounds"
    make_round(rounds_root / "rfake", [make_item(i, "a.pdf") for i in (1, 2)])
    rows, _ = collect(["rfake"], rounds_root)
    cost = token_cost_proxy(rows, max_length=768)

    assert cost["n_rows"] == 2
    assert cost["chars_median"] > 0
    assert cost["rows_estimated_over_max_length"] == 0
    assert "CHƯA kiểm chứng" in cost["note"]


def test_write_outputs_tu_choi_ghi_de(tmp_path, pool):
    rows, _ = collect(["rfake"], pool)
    train, holdout, meta = group_split(rows, 0.3, 20261024)
    out = tmp_path / "t4b"
    write_outputs(out, train, holdout, {"group_split": meta})

    assert (out / "sft_train.jsonl").is_file()
    assert (out / "manifest.json").is_file()
    with pytest.raises(SystemExit):
        write_outputs(out, train, holdout, {"group_split": meta})


ADAPTER_TOKENIZER = Path(__file__).resolve().parent.parent / "models" / "qwen25_05b_sft_adapter"


@pytest.mark.skipif(not ADAPTER_TOKENIZER.is_dir(), reason="không có tokenizer cục bộ trong checkout")
def test_exact_token_lengths_dung_duong_tokenize_false(pool):
    """Chốt bằng test: `apply_chat_template(tokenize=True)` trả 2 token trên transformers 5.x.

    Nếu ai đó "đơn giản hóa" hàm này về đường đó, phép đo chi phí độ dài dòng train sẽ
    thành số giả (mọi dòng đều "vừa" 768) và lượt train sẽ cắt mất căn cứ mà không báo.
    """
    import importlib.util

    if importlib.util.find_spec("transformers") is None:
        pytest.skip("venv này không có transformers")

    from transformers import PreTrainedTokenizerFast

    from tools.train.build_sft_from_round import exact_token_lengths

    rows, _ = collect(["rfake"], pool)
    # max_length=64 cố ý: dòng giả lập chỉ vài trăm ký tự, cần ngưỡng thấp để kiểm tra
    # logic "đếm rồi so", không phải để tái hiện số của round thật.
    out = exact_token_lengths(rows, str(ADAPTER_TOKENIZER), max_length=64)

    tok = PreTrainedTokenizerFast.from_pretrained(str(ADAPTER_TOKENIZER), local_files_only=True)
    text = tok.apply_chat_template(rows[0]["messages"], tokenize=False, add_generation_prompt=False)
    assert len(text) > 200  # dòng có ngữ cảnh, không phải chuỗi rỗng
    assert out["tokens_min"] >= 30, f"token thật phải ra con số, nhận {out['tokens_min']}"
    assert out["rows_over_max_length"] == len(rows)
    assert out["method"].startswith("tokenizer thật")
    # Đường hỏng (tokenize=True) — nếu nó bắt đầu trả số ĐÚNG thì template đã được sửa,
    # và lúc đó phải xem lại toàn bộ script train/eval.
    assert len(tok.apply_chat_template(rows[0]["messages"], tokenize=True)) in (0, 1, 2)

