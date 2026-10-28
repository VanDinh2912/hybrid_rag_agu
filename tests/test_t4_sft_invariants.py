# -*- coding: utf-8 -*-
"""T4 — test 5 bất biến dữ liệu SFT (mục 1–5 của đề bài) + artifact đã công bố.

Bộ test này KHÔNG train, KHÔNG nạp model, KHÔNG gọi mạng. Nó kiểm hai lớp:

* **Bộ sinh** (`tools/train/build_sft_from_round.py` → `triage.build_rows`): dòng giả thiếu căn cứ
  phải bị loại và đếm vào `skip_sft_target_not_in_context`; item `split=test` bị chặn.
* **Bộ kiểm** (`tools/diag/check_sft_invariants.py`): phát hiện đúng các vi phạm — kể cả
  những vi phạm bộ sinh hiện hành CÒN mắc (luật 2/N ở PA-28), nên test ghi rõ trạng thái
  "hiện hành" thay vì hạ kỳ vọng cho xanh.

Ba điều cố ý:

1. Không sửa test cũ; mọi ca mới nằm ở file này.
2. `check_no_leak` / `check_group_split` mặc định **DỪNG** khi phát hiện rò rỉ — test chứng
   minh đúng hành vi dừng đó, không chỉ kiểm cờ boolean.
3. Artifact thật `data/training/t4b_r5r8r9r10` được đo nguyên trạng: mục 1–4 xanh, mục 5
   **ĐỎ vì dữ liệu** (13/13 dòng train > 768 token). Đó là số đo, không phải lỗi test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.generator import REFUSAL_TEXT
from src.text_utils import fold
from tools.train.build_sft_from_round import collect
from tools.diag.check_sft_invariants import (
    DEFAULT_ARTIFACT,
    DEFAULT_MAX_LENGTH,
    DEFAULT_ROUNDS,
    SftInvariantError,
    article_of,
    check_artifact,
    check_evidence_in_context,
    check_format,
    check_group_split,
    check_no_leak,
    check_refusal_labels,
    context_of,
    load_artifact,
    load_jsonl,
    read_round_items,
)

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------ bộ dựng dữ liệu giả

def make_item(i: int, doc: str, split: str = "trainpool", **overrides) -> dict:
    item = {
        "id": f"ITEM-{i}",
        "raw_query": f"Sinh viên học lại tối đa bao nhiêu lần ({i})?",
        "family": "CLOZE",
        "split": split,
        "source_document": doc,
        "gold_chunk_id": f"chunk-{i}",
        "primary_entity": "8",
        "required_entities": ["8", "lần"],
        "gold_sentence": f"Sinh viên được học lại tối đa 8 lần đối với học phần {i}.",
    }
    item.update(overrides)
    return item


def make_round(round_dir: Path, items: list[dict], contexts_for=None) -> None:
    """Viết round giả đủ khung cho `triage.build_rows` (verdicts_full + full)."""
    round_dir.mkdir(parents=True, exist_ok=True)
    verdicts, rows = [], []
    for item in items:
        verdicts.append(
            {"id": item["id"], "verdict": "FAIL_OVERREFUSAL", "gold_in_top_k": True,
             "item": item, "answer_preview": "Không đủ thông tin để trả lời."}
        )
        if contexts_for is not None:
            contexts, sources = contexts_for(item)
        else:
            contexts = [f"Mục 4.2: {item['gold_sentence']}", "Văn bản nhiễu không liên quan."]
            sources = [
                {"source": item["source_document"], "chunk_id": item["gold_chunk_id"], "tier": "1"},
                {"source": item["source_document"], "chunk_id": "khac", "tier": "1"},
            ]
        rows.append({"id": item["id"], "item": item, "answer": "Không đủ thông tin để trả lời.",
                     "contexts": contexts, "sources": sources})
    for name, payload in (("verdicts_full.jsonl", verdicts), ("full.jsonl", rows)):
        with (round_dir / name).open("w", encoding="utf-8") as fh:
            for row in payload:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def make_row(item_id: str, context: str, *, task: str = "sft_extractive",
             verdict: str = "FAIL_INCOMPLETE", answer: str = "", doc: str | None = None) -> dict:
    row = {
        "task": task,
        "messages": [
            {"role": "system", "content": "Chỉ trả lời dựa trên ngữ cảnh được cung cấp."},
            {"role": "user", "content": f"Ngữ cảnh:\n{context}\n\nCâu hỏi: câu hỏi giả?"},
            {"role": "assistant", "content": answer or "Câu trả lời trích niêm."},
        ],
        "provenance": {"round": "rX", "item_id": item_id, "verdict": verdict},
    }
    if doc is not None:
        row["group_document"] = doc
    return row


def write_artifact(root: Path, train: list[dict], holdout: list[dict]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, rows in (("sft_train.jsonl", train), ("sft_holdout.jsonl", holdout)):
        with (root / name).open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (root / "manifest.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    return root


@pytest.fixture
def items_3docs() -> dict[str, dict]:
    """3 tài liệu, mỗi tài liệu 2 item; item 7 là split=test."""
    return {
        "ITEM-1": make_item(1, "quy-che-ctdt.pdf"),
        "ITEM-2": make_item(2, "quy-che-ctdt.pdf"),
        "ITEM-3": make_item(3, "so-tay-sv.pdf"),
        "ITEM-4": make_item(4, "so-tay-sv.pdf"),
        "ITEM-5": make_item(5, "quy-dinh-thi.pdf"),
        "ITEM-6": make_item(6, "quy-dinh-thi.pdf"),
        "ITEM-7": make_item(7, "quy-che-ctdt.pdf", split="test"),
    }


# ---------------------------------------------------------------------- 1. bất biến 7

class TestBatBien7:
    def test_dong_thieu_ca_thuc_the_va_nguon_bi_loai_va_dem(self, tmp_path: Path) -> None:
        """Ngữ cảnh chỉ có nhiễu, không nguồn không thực thể → loại + đếm (đề bài mục 1)."""
        rounds_root = tmp_path / "rounds"
        item = make_item(1, "quy-che-ctdt.pdf", required_entities=["42"], primary_entity="42",
                         gold_sentence="Quy định về thời hạn nộp hồ sơ xét tốt nghiệp.")
        make_round(
            rounds_root / "r1", [item],
            contexts_for=lambda it: (["Văn bản nhiễu không liên quan."], []),
        )
        rows, ledger = collect(["r1"], rounds_root)

        assert [r for r in rows if r.get("task") == "sft_extractive"] == []
        assert ledger["blocked"]["skip_sft_target_not_in_context"] == 1

    def test_dong_thieu_thuc_the_nhung_du_nguon_va_cau_vang_hien_hanh_van_giu(
        self, tmp_path: Path
    ) -> None:
        """HIỆN HÀNH (PA-28): luật `min(2, len(frags))` giữ dòng chỉ phủ nguồn + câu vàng.

        Đây KHÔNG phải hành vi mong muốn theo đề bài mục 1 (thực thể phải có mặt). Test ghim
        đúng trạng thái đang chạy để (a) nếu ai sửa luật thì biết mình đang sửa gì, (b) bộ kiểm
        ở ca dưới vẫn báo ĐỎ cho chính dòng này — tức khoảng trống được phát hiện, không bị che.
        """
        rounds_root = tmp_path / "rounds"
        item = make_item(1, "quy-che-ctdt.pdf", required_entities=["42"], primary_entity="42",
                         gold_sentence="Quy định về thời hạn nộp hồ sơ xét tốt nghiệp.")
        make_round(
            rounds_root / "r1", [item],
            contexts_for=lambda it: ([f"{it['source_document']}: Quy định về thời hạn nộp hồ sơ xét tốt nghiệp."],
                                     [{"source": it["source_document"], "chunk_id": it["gold_chunk_id"]}]),
        )
        rows, ledger = collect(["r1"], rounds_root)
        kept = [r for r in rows if r.get("task") == "sft_extractive"]

        assert len(kept) == 1, "luật 2/N hiện hành giữ dòng nguồn + câu vàng"
        assert ledger["blocked"].get("skip_sft_target_not_in_context", 0) == 0
        evidence = check_evidence_in_context(kept, {"ITEM-1": item})
        assert evidence["ok"] is False
        assert evidence["missing_by_kind"].get("entity") == 1

    def test_checker_bat_dong_thieu_thuc_the(self) -> None:
        item = make_item(1, "quy-che-ctdt.pdf", required_entities=["42"], primary_entity="42")
        row = make_row("ITEM-1", "quy-che-ctdt.pdf: Sinh viên được học lại tối đa 8 lần.")
        evidence = check_evidence_in_context([row], {"ITEM-1": item})

        assert evidence["ok"] is False
        assert evidence["missing_by_kind"]["entity"] >= 1
        assert evidence["rows_missing_mandatory"][0]["item_id"] == "ITEM-1"

    def test_checker_bat_dong_thieu_nguon(self) -> None:
        item = make_item(1, "quy-che-ctdt.pdf")
        row = make_row("ITEM-1", "Sinh viên được học lại tối đa 8 lần, không nêu tệp.")
        evidence = check_evidence_in_context([row], {"ITEM-1": item})

        assert evidence["ok"] is False
        assert evidence["missing_by_kind"] == {"source": 1}

    def test_checker_chap_nhan_dong_du_thuc_the_va_nguon(self) -> None:
        item = make_item(1, "quy-che-ctdt.pdf")
        row = make_row("ITEM-1", f"quy-che-ctdt.pdf: {item['gold_sentence']}")
        evidence = check_evidence_in_context([row], {"ITEM-1": item})

        assert evidence["ok"] is True
        assert evidence["rows_missing_mandatory"] == []
        assert evidence["n_rows"] == 1

    def test_thieu_cau_vang_chi_la_thong_tin_khong_phai_do(self) -> None:
        """Câu vàng thiếu = INFO (PA-28 đang cho phép); thực thể + nguồn đủ thì không đỏ."""
        item = make_item(1, "quy-che-ctdt.pdf")
        row = make_row("ITEM-1", "quy-che-ctdt.pdf: Học lại tối đa 8 lần, không có câu vàng nguyên văn.")
        evidence = check_evidence_in_context([row], {"ITEM-1": item})

        assert evidence["ok"] is True
        assert evidence["rows_missing_gold_sentence"] == ["ITEM-1"]


# ------------------------------------------------------------------------ 2. chặn rò rỉ

class TestChanRoRi:
    def test_ro_ri_theo_id_bi_bat_va_dung(self, items_3docs: dict[str, dict]) -> None:
        train = [make_row("ITEM-7", "quy-che-ctdt.pdf: nội dung bất kỳ")]
        with pytest.raises(SftInvariantError, match="Rò rỉ test-set"):
            check_no_leak(train, items_3docs)
        assert check_no_leak(train, items_3docs, raise_on_leak=False)["id_leaks"] == ["ITEM-7"]

    def test_ro_ri_theo_gold_sentence_da_fold_bi_bat(self, items_3docs: dict[str, dict]) -> None:
        test_sentence = items_3docs["ITEM-7"]["gold_sentence"]
        mangled = fold(test_sentence).upper()  # khác nguyên văn, chỉ khớp sau fold
        assert mangled != test_sentence
        train = [make_row("ITEM-1", f"quy-che-ctdt.pdf: {mangled}")]

        with pytest.raises(SftInvariantError, match="Rò rỉ test-set"):
            check_no_leak(train, items_3docs)
        report = check_no_leak(train, items_3docs, raise_on_leak=False)
        assert [x["item_id"] for x in report["sentence_leaks"]] == ["ITEM-7"]

    def test_khong_ro_ri_tra_ve_xanh(self, items_3docs: dict[str, dict]) -> None:
        train = [make_row("ITEM-1", f"quy-che-ctdt.pdf: {items_3docs['ITEM-1']['gold_sentence']}")]

        report = check_no_leak(train, items_3docs)
        assert report["ok"] is True
        assert report["n_test_items"] == 1

    def test_co_che_dong_theo_item_split_test_cua_bo_sinh(self, tmp_path: Path) -> None:
        """Lớp thứ nhất: `triage` chặn item split=test bằng `blocked_test_leak`."""
        rounds_root = tmp_path / "rounds"
        make_round(rounds_root / "r1", [make_item(1, "quy-che-ctdt.pdf", split="test")])
        rows, ledger = collect(["r1"], rounds_root)

        assert [r for r in rows if r.get("task") == "sft_extractive"] == []
        assert ledger["blocked"]["blocked_test_leak"] == 1

    def test_check_artifact_dung_khi_co_dong_test_trong_train(
        self, tmp_path: Path, items_3docs: dict[str, dict]
    ) -> None:
        rounds_root = write_rounds(tmp_path / "rounds", items_3docs)
        artifact = write_artifact(
            tmp_path / "artifact",
            [make_row("ITEM-7", "quy-che-ctdt.pdf: nội dung")],
            [make_row("ITEM-2", "quy-che-ctdt.pdf: nội dung")],
        )
        with pytest.raises(SftInvariantError, match="Rò rỉ test-set"):
            check_artifact(artifact, ["r1"], rounds_root=rounds_root, raise_on_violation=True)


def write_rounds(root: Path, items: dict[str, dict]) -> Path:
    make_round(root / "r1", list(items.values()))
    return root


# ------------------------------------------------------------------------- 3. group split

class TestGroupSplit:
    def test_ba_tai_lieu_moi_tai_lieu_mot_phia(self, items_3docs: dict[str, dict]) -> None:
        train = [make_row(k, "ctx", doc=v["source_document"]) for k, v in items_3docs.items()
                 if v["split"] == "trainpool" and v["source_document"] != "quy-dinh-thi.pdf"]
        holdout = [make_row("ITEM-5", "ctx", doc="quy-dinh-thi.pdf"),
                   make_row("ITEM-6", "ctx", doc="quy-dinh-thi.pdf")]

        report = check_group_split(train, holdout, items_3docs)
        assert report["ok"] is True
        assert report["document_overlap"] == []
        assert len(report["holdout_documents"]) == 1

    def test_tron_split_theo_item_bi_bat(self, items_3docs: dict[str, dict]) -> None:
        """Đột biến 'chia theo item': hai item CÙNG tài liệu rơi hai phía → phải dừng."""
        train = [make_row("ITEM-1", "ctx", doc="quy-che-ctdt.pdf"),
                 make_row("ITEM-3", "ctx", doc="so-tay-sv.pdf")]
        holdout = [make_row("ITEM-2", "ctx", doc="quy-che-ctdt.pdf")]

        with pytest.raises(SftInvariantError, match="Group split rò rỉ"):
            check_group_split(train, holdout, items_3docs)
        assert check_group_split(train, holdout, items_3docs, raise_on_overlap=False)[
            "document_overlap"] == ["quy-che-ctdt.pdf"]

    def test_article_of_uu_tien_item_roi_cau_vang_roi_ngu_canh(self) -> None:
        assert article_of({"article": "Điều 12"})[0] == "12"
        assert article_of({"article": "Điều 12"})[1] == "item"
        assert article_of({"gold_sentence": "Theo Điều 15, sinh viên ..."})[:2] == ("15", "gold_sentence")
        assert article_of({}, "[tai-lieu.pdf] - [Điều 24.]\nNội dung ...")[:2] == ("24", "context")
        assert article_of({}, "Nội dung không có số Điều") == (None, "")

    def test_hai_dong_cung_dieu_khac_tai_lieu_khong_bi_coi_la_trung(self) -> None:
        """Khoá nhóm là (tài liệu, Điều) — cùng 'Điều 12' ở hai tệp khác nhau là hợp lệ."""
        items = {"A": make_item(1, "tep-a.pdf", article="Điều 12"),
                 "B": make_item(2, "tep-b.pdf", article="Điều 12")}
        train = [make_row("A", "ctx", doc="tep-a.pdf")]
        holdout = [make_row("B", "ctx", doc="tep-b.pdf")]

        report = check_group_split(train, holdout, items)
        assert report["ok"] is True
        assert report["article_overlap"] == []
        assert report["n_document_article_groups"] == 2


# ----------------------------------------------------------------------- 4. nhãn từ chối

class TestNhanTuChoi:
    def test_ca_khong_dap_an_bi_gan_nhan_tra_loi_bi_bat(self, items_3docs: dict[str, dict]) -> None:
        row = make_row("ITEM-1", "ctx", task="sft_extractive",
                       verdict="FAIL_HALLUCINATED_ON_UNANSWERABLE")
        report = check_refusal_labels([row], items_3docs)

        assert report["ok"] is False
        assert report["by_kind"] == {"unanswerable_labeled_answer": 1}

    def test_sft_refusal_phai_dung_cau_chuan(self, items_3docs: dict[str, dict]) -> None:
        row = make_row("ITEM-1", "ctx", task="sft_refusal",
                       verdict="FAIL_HALLUCINATED_ON_UNANSWERABLE", answer="Tôi không biết.")
        report = check_refusal_labels([row], items_3docs)

        assert report["ok"] is False
        assert report["by_kind"] == {"refusal_text_differs": 1}

    def test_sft_refusal_tu_verdict_tra_loi_duoc_bi_bat(self, items_3docs: dict[str, dict]) -> None:
        row = make_row("ITEM-1", "ctx", task="sft_refusal",
                       verdict="FAIL_INCOMPLETE", answer=REFUSAL_TEXT)
        report = check_refusal_labels([row], items_3docs)

        assert report["ok"] is False
        assert report["by_kind"] == {"refusal_from_answerable": 1}

    def test_refusal_dung_thi_xanh(self, items_3docs: dict[str, dict]) -> None:
        row = make_row("ITEM-1", "ctx", task="sft_refusal",
                       verdict="FAIL_CONFIRMED_FALSE_PREMISE", answer=REFUSAL_TEXT)
        report = check_refusal_labels([row], items_3docs)

        assert report["ok"] is True
        assert report["n_refusal_rows"] == 1


# ---------------------------------------------------------------------------- 5. định dạng

class TestDinhDang:
    def test_dong_hong_parse_thi_dung_kem_so_dong(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.jsonl"
        path.write_text('{"a": 1}\n{khong-phai-json}\n', encoding="utf-8")

        with pytest.raises(SftInvariantError, match="dòng 2 không parse được"):
            load_jsonl(path)

    def test_dong_rong_va_trung_bi_bat(self) -> None:
        good = make_row("ITEM-1", "ctx")
        empty = {"task": "sft_extractive",
                 "messages": [{"role": "user", "content": ""}],
                 "provenance": {"item_id": "ITEM-2"}}
        report = check_format([good, empty, make_row("ITEM-1", "ctx")], max_length=10_000)

        assert report["ok"] is False
        assert report["empty_rows"] == [1]
        assert report["duplicate_rows"] == [{"row": 2, "same_as": 0}]

    def test_vuot_max_length_bi_bat(self) -> None:
        rows = [make_row("ITEM-1", "ctx"), make_row("ITEM-2", "ctx")]
        report = check_format(rows, max_length=100, exact_lengths={"ITEM-1": 99, "ITEM-2": 101})

        assert report["ok"] is False
        assert [x["item_id"] for x in report["rows_over_max_length"]] == ["ITEM-2"]
        assert report["token_method"] == {"manifest": 2}

    def test_duoi_max_length_thi_xanh(self) -> None:
        report = check_format([make_row("ITEM-1", "ctx")], max_length=768,
                              exact_lengths={"ITEM-1": 768})
        assert report["ok"] is True, "biên: đúng 768 là ĐẠT (trần cho phép, không phải < 768)"


# ---------------------------------------------------------------- artifact đã công bố

@pytest.fixture(scope="module")
def real_artifact() -> dict:
    if not (DEFAULT_ARTIFACT / "sft_train.jsonl").exists():
        pytest.skip(f"không có artifact {DEFAULT_ARTIFACT}")
    return load_artifact(DEFAULT_ARTIFACT)


@pytest.fixture(scope="module")
def real_items() -> dict[str, dict]:
    if not (ROOT / "data" / "loop" / "rounds").is_dir():
        pytest.skip("không có data/loop/rounds")
    return read_round_items(DEFAULT_ROUNDS)


class TestArtifactThat:
    def test_bon_bat_bien_dau_xanh(self, real_artifact: dict, real_items: dict) -> None:
        report = check_artifact(DEFAULT_ARTIFACT, DEFAULT_ROUNDS)
        assert report["1_evidence_in_context"]["ok"] is True, report["1_evidence_in_context"]["rows_missing_mandatory"]
        assert report["2_no_test_leak"]["ok"] is True
        assert report["3_group_split"]["ok"] is True
        assert report["4_refusal_labels"]["ok"] is True
        assert report["red_checks"] == ["5_format_and_length"]

    def test_artifact_that_dai_hon_tran_768_o_moi_dong_train(self, real_artifact: dict) -> None:
        train = check_format(
            real_artifact["train"], DEFAULT_MAX_LENGTH,
            exact_lengths={r["item_id"]: r["tokens"]
                           for r in real_artifact["manifest"]["token_lengths"]["train"]["per_row"]},
        )
        assert len(train["rows_over_max_length"]) == len(real_artifact["train"]) == 13
        assert train["tokens_max"] == 1707
        assert train["ok"] is False, "ĐỎ của DỮ LIỆU: train_sft_lora sẽ cắt cụt dòng này"

    def test_artifact_that_giu_dung_so_dong_va_cau_truc(self, real_artifact: dict) -> None:
        train, holdout = real_artifact["train"], real_artifact["holdout"]
        assert (len(train), len(holdout)) == (13, 10)
        assert {r["task"] for r in train + holdout} == {"sft_extractive"}
        assert all(r["provenance"]["round"] in DEFAULT_ROUNDS for r in train + holdout)

    def test_artifact_that_khong_ro_ri_test(self, real_artifact: dict, real_items: dict) -> None:
        report = check_no_leak(real_artifact["train"], real_items, raise_on_leak=False)
        assert report["ok"] is True
        assert report["n_test_items"] > 0, "nếu 0 thì phép kiểm rỗng, không chứng minh gì"

    def test_context_lay_dung_phan_ngu_canh_khong_gom_cau_hoi(self) -> None:
        row = make_row("ITEM-1", "quy-che-ctdt.pdf: nội dung")
        assert context_of(row).startswith("Ngữ cảnh:\nquy-che-ctdt.pdf")
        assert "câu hỏi giả" not in context_of(row)


def test_cli_chay_duoc_va_tra_json() -> None:
    """CLI là đường chạy thật của mục 1–5; hỏng CLI thì báo cáo trong docs không tái lập được."""
    if not (DEFAULT_ARTIFACT / "sft_train.jsonl").exists():
        pytest.skip("không có artifact")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "diag" / "check_sft_invariants.py")],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), env=env,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout[: proc.stdout.rindex("}") + 1])
    assert payload["verdict"] in ("XANH", "ĐỎ")
    assert payload["checks"]["3_group_split"] is True
