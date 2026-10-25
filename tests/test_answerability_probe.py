"""Test cho `tools/diag/answerability_probe.py` (B4) — toàn bộ trên tmp_path, 0 model, 0 Chroma.

Vì sao bộ test này phải có răng: probe dựng nhãn NEG bằng cách THAY ô vàng bằng ứng viên hạng
kề tiếp, mà văn bản ô bù chỉ đọc được từ index trên đĩa. Nếu việc đọc đó hỏng, script có hai
đường sai rất dễ trượt: (1) âm thầm chấm cửa sổ 5 ô (nhãn đổi nghĩa), hoặc (2) gọi model sinh
để "bù" văn bản (phạm cam kết 0 lượt sinh của đề bài). Mỗi test dưới đây chốt một trong hai
đường đó, cộng với bất biến của phép đo AUC và của ngưỡng 0,75 ĐÃ ĐĂNG KÝ TRƯỚC.
"""

import json
import math
from pathlib import Path

import pytest

from tools.diag import answerability_probe as ap

# Text của một ô dài hơn 24 ký tự để phép thử `gold_sentence` (ngưỡng chống chuỗi ngắn) chạy được.
TEXT_TPL = "van ban chunk {cid} noi dung dai them vao"


def text_of(cid) -> str:
    return TEXT_TPL.format(cid=cid)


class FakeTexts:
    """Thay cho `IndexTexts`: trả văn bản theo chunk_id, đếm lượt đọc, không chạm đĩa.

    Chữ ký giống hệt lớp thật (`persist_dir`, `collection`) để `main()` nối tham số mà không
    vỡ test — đây chính là chỗ từng thiếu wiring.
    """

    def __init__(self, persist_dir=None, collection=None, missing=()):
        self.missing = set(missing)
        self.requested = []
        # `main()` ghi `texts.persist_dir.name` vào báo cáo — fixture phải có thật.
        self.persist_dir = Path(str(persist_dir or "fake_index"))
        self.collection = collection or "fake"

    def text_for(self, chunk_id):
        self.requested.append(chunk_id)
        return "" if chunk_id in self.missing else text_of(chunk_id)

    def stats(self):
        return {"persist_dir": "fake", "collection": "fake",
                "n_reads": len(self.requested), "n_miss": 0, "error": None}


GOLD_ID = 777  # không trùng dải id đuôi 1001..1012


def row(*, iid="A1", doc="a.pdf", gold=GOLD_ID, gold_rank=1, pool=12, n_window=6,
        gold_sentence="", entities=(), error=None, contexts=None, sources=None):
    """Một dòng round mô phỏng `full.jsonl`: cửa sổ `n_window` ô + ứng viên đuôi, id theo hạng."""
    ids = [gold if k == gold_rank else 1000 + k for k in range(1, pool + 1)]
    srcs = sources if sources is not None else [
        {"rank": r, "chunk_id": c, "source": doc, "tier": "Tầng 1"}
        for r, c in enumerate(ids, start=1)]
    ctx = contexts if contexts is not None else [text_of(c) for c in ids[:n_window]]
    it = {
        "id": iid, "family": "EXACT", "source_document": doc, "gold_chunk_id": gold,
        "raw_query": f"câu hỏi {iid}?", "gold_sentence": gold_sentence,
        "required_entities": list(entities),
    }
    return {"id": iid, "item": it, "sources": srcs, "contexts": ctx,
            "error": error, "latency_seconds": 1.0}


def docs_in_partition(partition: str, n: int) -> list[str]:
    """Tên tài liệu thật sự rơi vào partition mong muốn (md5 tất định nhưng không đoán được)."""
    out, i = [], 0
    while len(out) < n:
        d = f"tl-{i}.pdf"
        if ap.split_of(d) == partition:
            out.append(d)
        i += 1
    return out


def build(rows, *, k=6, texts=None):
    return ap.build_pairs(rows, k=k, texts=texts if texts is not None else FakeTexts())


def fake_scores(pairs, pos, neg):
    return [{"id": p["id"],
             "ce_max": {"pos": pos, "neg": neg},
             "ce_mean": {"pos": pos, "neg": neg},
             "ce_top2": {"pos": pos, "neg": neg}} for p in pairs]


# ------------------------------------------------------------------ group split theo tài liệu
class TestGroupSplit:
    def test_cung_tai_lieu_luon_cung_partition(self):
        assert ap.split_of("1054-qd-dhag.pdf") == ap.split_of("1054-qd-dhag.pdf")

    def test_partition_chi_là_train_eval_hoac_khong_ro_tai_lieu(self):
        assert {ap.split_of(d) for d in ("a.pdf", "b.pdf", "c.pdf", "d.pdf", "")} <= {
            "train", "eval", "khong_ro_tai_lieu"}

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_item_thiếu_tên_tài_liệu_không_bị_md5_v_nhét_vào_một_partition_thật(self, bad):
        """13/100 dòng r5 không có `source_document`; gộp hết vào một bên sẽ vừa rò vừa phồng mẫu."""
        assert ap.split_of(bad) == "khong_ro_tai_lieu"

    def test_split_khong_phu_thuoc_thu_tu_danh_sach(self):
        docs = [f"tai-lieu-{i}.pdf" for i in range(20)]
        assert {d: ap.split_of(d) for d in docs} == {d: ap.split_of(d) for d in reversed(docs)}

    def test_cả_hai_partition_đều_có_tài_liệu(self):
        """Một partition trống ⇒ `eval_clean` vô nghĩa mà báo cáo vẫn in ra số đẹp."""
        parts = {ap.split_of(f"tl-{i}.pdf") for i in range(20)}
        assert parts == {"train", "eval"}


# ------------------------------------------------------------------ dựng cặp POS/NEG
class TestBuildPairs:
    def test_cặp_chỉ_khác_nhau_ở_viên_một_vàng_bị_thay_bằng_hạng_kề_tiếp(self):
        pairs, skip = build([row()])
        assert not any(skip.values())
        p = pairs[0]
        assert text_of(GOLD_ID) in p["pos_chunks"]
        assert all(text_of(GOLD_ID) not in t for t in p["neg_chunks"])
        assert p["filler_chunk_id"] == 1007  # hạng 7 = ứng viên kề tiếp cửa sổ, không phải ngẫu nhiên
        assert p["neg_chunks"][-1] == text_of(1007)

    def test_NEG_giữ_đúng_k_ô(self):
        pairs, _ = build([row()])
        assert len(pairs[0]["neg_chunks"]) == 6 and len(pairs[0]["pos_chunks"]) == 6

    def test_vàng_ở_giữa_cửa_sổ_thì_cac_o_con_lai_giữ_nguyên_thứ_tự(self):
        pairs, _ = build([row(gold_rank=3)])
        p = pairs[0]
        assert p["pos_chunks"] == [text_of(c) for c in [1001, 1002, GOLD_ID, 1004, 1005, 1006]]
        # rút ô giữa, các ô còn lại giữ nguyên thứ tự, ô bù đứng cuối
        assert p["neg_chunks"][:5] == [text_of(c) for c in [1001, 1002, 1004, 1005, 1006]]
        assert p["neg_chunks"][5] == text_of(1007)
        assert p["gold_rank"] == 3
        assert p["neg_ranks"] == [1, 2, 3, 4, 5, 6]        # hạng VỊ TRÍ (cửa sổ thật luôn có ô 1)
        assert p["neg_source_ranks"] == [1, 2, 4, 5, 6, 7]  # hạng truy xuất gốc, để đối chiếu

    def test_hạng_gốc_không_được_trở_thành_feature_vì_tiết_lộ_nhãn(self):
        """Regression chống leakage: nếu `neg_ranks` dùng hạng truy xuất gốc thì NEG chỉ mất
        hạng 1 khi chunk vàng đang chiếm hạng 1 ⇒ mốc hạng tự biết nhãn, AUC thành trần gian lận."""
        p_vàng_hạng_1 = build([row(gold_rank=1)])[0][0]
        p_vàng_hạng_3 = build([row(gold_rank=3)])[0][0]
        assert p_vàng_hạng_1["neg_ranks"] == p_vàng_hạng_3["neg_ranks"]
        assert p_vàng_hạng_1["neg_source_ranks"] != p_vàng_hạng_3["neg_source_ranks"]

    def test_vàng_ngoài_cửa_sổ_bị_đếm_chứ_không_bị_dùng_làm_POS(self):
        r = row()
        r["item"]["gold_chunk_id"] = 4242  # id này không xuất hiện trong 6 ô nào cả
        pairs, skip = build([r])
        assert pairs == [] and skip.get("vang_ngoai_cua_so") == 1

    def test_dòng_lỗi_bị_đếm_riêng(self):
        pairs, skip = build([row(error="boom")])
        assert pairs == [] and skip.get("loi_tinh_nang") == 1

    def test_khong_co_chunk_vang_thì_loại(self):
        r = row(gold=None)
        pairs, skip = build([r])
        assert pairs == [] and skip.get("khong_co_chunk_vang") == 1

    def test_hết_ứng_viên_bù_thì_đếm_chứ_không_chấm_cửa_sổ_lẹm(self):
        pairs, skip = build([row(pool=6)])
        assert pairs == [] and skip.get("khong_con_ung_vien_de_bu") == 1

    def test_không_đọc_được_text_ô_bù_thì_loại_và_đếm(self):
        """Đường sai (1): NEG 5 ô mà vẫn báo AUC — nhãn đổi nghĩa không ai biết."""
        pairs, skip = build([row()], texts=FakeTexts(missing={1007}))
        assert pairs == [] and skip.get("khong_doc_duoc_text_ung_vien_bu") == 1

    def test_thiếu_contexts_trong_round_thì_đếm(self):
        pairs, skip = build([row(contexts=["a", "b", "c"])])
        assert pairs == [] and skip.get("thieu_text_trong_round_jsonl") == 1

    def test_quên_nối_texts_thì_0_cặp_chứ_không_phải_cặp_rỗng_text(self):
        """Đường sai (2): `texts=None` (thiếu wiring) không được biến NEG thành chuỗi rỗng rồi chấm."""
        pairs, skip = ap.build_pairs([row()], k=6, texts=None)
        assert pairs == [] and skip.get("khong_doc_duoc_text_ung_vien_bu") == 1

    def test_split_doc_lấy_theo_tài_liệu_của_item(self):
        doc = docs_in_partition("eval", 1)[0]
        pairs, _ = build([row(doc=doc)])
        assert pairs[0]["split_doc"] == "eval"
        assert pairs[0]["source_document"] == doc

    def test_mỗi_dòng_một_cặp_id_độc_nhất(self):
        pairs, _ = build([row(iid=f"A{i}", gold=GOLD_ID + i) for i in range(5)])
        assert len(pairs) == 5 and len({p["id"] for p in pairs}) == 5


# ------------------------------------------------------------------ cờ nhiễu nhãn
class TestStillAnswerable:
    def test_gold_sentence_còn_nằm_trong_NEG_thì_gắn_cờ(self):
        r = row(gold_sentence=text_of(1002))  # câu vàng trùng text ô hạng 2 (vẫn còn trong NEG)
        pairs, _ = build([r])
        assert pairs[0]["still_answerable"] == "gold_sentence_con_neg"

    def test_required_entities_phủ_được_NEG_thì_gắn_cờ(self):
        pairs, _ = build([row(entities=["chunk 1002"])])
        assert pairs[0]["still_answerable"] == "required_entities_du_bo_trong_neg"

    def test_NEG_sạch_thì_cờ_rỗng(self):
        pairs, _ = build([row(entities=["ký_hiệu_không_exists"])])
        assert pairs[0]["still_answerable"] == ""

    def test_câu_vàng_dưới_24_ký_tự_không_được_dùng_để_gắn_cờ(self):
        """Chống cờ giả: chuỗi ngắn ('chunk 1') khớp mọi cửa sổ."""
        pairs, _ = build([row(gold_sentence="chunk 1002")])
        assert pairs[0]["still_answerable"] == ""


# ------------------------------------------------------------------ AUC
class TestAuc:
    def test_tách_hoàn_hảo_bằng_1(self):
        assert ap.auc([3.0, 4.0], [1.0, 2.0]) == 1.0

    def test_ngược_hều_bằng_0(self):
        assert ap.auc([1.0, 2.0], [3.0, 4.0]) == 0.0

    def test_bằng_nhau_toàn_bộ_thì_0_5(self):
        assert ap.auc([2.0, 2.0], [2.0, 2.0]) == 0.5

    def test_một_nhóm_rỗng_trả_none(self):
        assert ap.auc([], [1.0]) is None and ap.auc([1.0], []) is None

    def test_auc_không_phu_thuoc_thu_tu_input(self):
        pos, neg = [5.0, 1.0, 3.0], [2.0, 4.0]
        assert ap.auc(pos, neg) == ap.auc(list(reversed(pos)), list(reversed(neg)))

    def test_tie_tính_0_5_không_phải_0_hoặc_1(self):
        assert ap.auc([2.0, 3.0], [1.0, 2.0]) == 0.875


class TestRankFeature:
    def test_điểm_là_âm_của_hạng_nhỏ_nhất_trong_cửa_sổ(self):
        p = {"pos_ranks": [3, 1, 2], "neg_ranks": [2, 4, 7]}
        assert ap.rank_feature(p, "pos") == -1.0
        assert ap.rank_feature(p, "neg") == -2.0

    def test_cửa_sổ_rỗng_tra_NaN_không_ném_lỗi(self):
        assert math.isnan(ap.rank_feature({"pos_ranks": []}, "pos"))

    def test_mốc_hạng_phẳng_theo_construction_và_script_phải_báo_vậy(self):
        """POS và NEG đều giữ hạng 1 ⇒ min(rank) hằng số ⇒ AUC 0,5; phải có cờ `rank_min_phang`
        để không ai đọc số 0,5 đó thành 'cross-encoder thua hạng' hay 'hạng vô dụng'."""
        pairs, _ = build([row(), row(iid="A2", gold=GOLD_ID + 1, gold_rank=2)])
        agg = ap.aggregate_scores(fake_scores(pairs, 5.0, 1.0), pairs)
        blk = next(iter(agg.values()))
        assert blk["auc"]["ce_max"] == 1.0
        assert blk["auc"]["rank_min"] == 0.5
        assert blk["rank_min_phang"] is True


# ------------------------------------------------------------------ gộp điểm
class TestAggregate:
    def test_eval_và_pooled_tách_nhau_theo_partition(self):
        eval_docs = docs_in_partition("eval", 3)
        train_docs = docs_in_partition("train", 3)
        pairs, _ = build([row(iid=f"E{i}", gold=GOLD_ID + i, doc=d) for i, d in enumerate(eval_docs)]
                         + [row(iid=f"T{i}", gold=GOLD_ID + 90 + i, doc=d) for i, d in enumerate(train_docs)])
        agg = ap.aggregate_scores(fake_scores(pairs, 5.0, 1.0), pairs)
        assert agg["pooled_clean"]["n_pairs"] == len(pairs)
        assert agg["eval_clean"]["n_pairs"] == len(eval_docs)

    def test_partition_trống_thì_scope_không_xuất_hiện_không_biến_thành_0(self):
        """`aggregate_scores` bỏ qua scope rỗng — nếu nó trả n=0 thì `ket_luan` đọc thành 'âm'."""
        pairs, _ = build([row(iid="T1", gold=GOLD_ID + 1, doc=docs_in_partition("train", 1)[0])])
        agg = ap.aggregate_scores(fake_scores(pairs, 5.0, 1.0), pairs)
        assert "eval_clean" not in agg
        assert agg["pooled_clean"]["n_pairs"] == 1

    def test_cặp_thiếu_tên_tài_liệu_chỉ_ở_pooled_không_phục_vào_eval(self):
        """`khong_ro_tai_lieu` không được được tính như "eval" — nó là ca không nhóm được."""
        unknown = [row(iid=f"U{i}", gold=GOLD_ID + i, doc="") for i in range(3)]
        pairs, _ = build(unknown)
        assert {p["split_doc"] for p in pairs} == {"khong_ro_tai_lieu"}
        agg = ap.aggregate_scores(fake_scores(pairs, 5.0, 1.0), pairs)
        assert "eval_clean" not in agg and "eval_all" not in agg
        assert agg["pooled_clean"]["n_pairs"] == 3
        assert ap.ket_luan(agg, {}, {})["verdict"] == "KHONG_DO_DUOC"

    def test_clean_loại_cặp_still_answerable_all_thì_giữ_lại(self):
        pairs, _ = build([row(iid=f"A{i}", gold=GOLD_ID + i) for i in range(4)])
        for p in pairs[:2]:
            p["still_answerable"] = "gold_sentence_con_neg"
        agg = ap.aggregate_scores(fake_scores(pairs, 5.0, 1.0), pairs)
        assert agg["pooled_all"]["n_pairs"] == 4
        assert agg["pooled_clean"]["n_pairs"] == 2

    def test_mẫu_quá_nhỏ_phải_in_ra_cờ(self):
        pairs, _ = build([row(iid=f"A{i}", gold=GOLD_ID + i) for i in range(3)])
        agg = ap.aggregate_scores(fake_scores(pairs, 5.0, 1.0), pairs)
        assert agg and all(blk["mau_qua_nho"] is True for blk in agg.values())

    def test_chỉ_chấm_subset_thì_AUC_tính_trên_ca_bđã_chấm(self):
        pairs, _ = build([row(iid=f"A{i}", gold=GOLD_ID + i) for i in range(6)])
        agg = ap.aggregate_scores(fake_scores(pairs[:2], 5.0, 1.0), pairs)
        assert agg["pooled_clean"]["n_pairs"] == 2


# ------------------------------------------------------------------ kết luận
class TestKetLuan:
    def _agg(self, auc_value, n):
        return {"eval_clean": {"n_pairs": n, "auc": {"ce_max": auc_value, "rank_min": 0.5},
                               "mau_qua_nho": n < ap.MIN_PAIRS_FOR_CONCLUSION}}

    def test_đúng_ngưỡng_075_là_CO_TIN_HIEU(self):
        """Tiêu chí ghi '≥ 0,75'; if sai thành '>' thì ca sát ngưỡng đổi kết luận."""
        assert ap.ket_luan(self._agg(0.75, 40), {}, {})["verdict"] == "CO_TIN_HIEU"

    def test_dưới_ngưỡng_là_AM_DUNG_và_dừng(self):
        kl = ap.ket_luan(self._agg(0.7499, 40), {}, {})
        assert kl["verdict"] == "AM_DUNG" and "DỪNG" in kl["ly_do"]

    def test_mẫu_nhỏ_không_được_kết_luận_dù_AUC_đẹp(self):
        """Ngã rẻ nhất: 12 cặp AUC 1,0 mà báo CO_TIN_HIEU ⇒ phải là MAU_QUA_NHO."""
        assert ap.ket_luan(self._agg(1.0, 12), {}, {})["verdict"] == "MAU_QUA_NHO"

    def test_không_có_cặp_nào_là_KHONG_DO_DUOC_kèm_nguyên_nhân(self):
        kl = ap.ket_luan({}, {}, {"khong_doc_duoc_text_ung_vien_bu": 30})
        assert kl["verdict"] == "KHONG_DO_DUOC"
        assert kl["so_khong_duoc_tinh"]["khong_doc_duoc_text_ung_vien_bu"] == 30

    def test_ngưỡng_đăng_ký_trước_không_đổi(self):
        assert ap.AUC_THRESHOLD == 0.75 and ap.MIN_PAIRS_FOR_CONCLUSION == 30


# ------------------------------------------------------------------ CLI
class TestMain:
    @pytest.fixture()
    def round_env(self, tmp_path, monkeypatch):
        rounds = tmp_path / "rounds"
        (rounds / "rz").mkdir(parents=True)
        docs = docs_in_partition("eval", 3) + docs_in_partition("train", 3)
        rows = [row(iid=f"R{i}", gold=GOLD_ID + i, doc=d) for i, d in enumerate(docs)]
        (rounds / "rz" / "full.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        monkeypatch.setattr(ap, "ROUNDS", rounds)
        monkeypatch.setattr(ap, "IndexTexts", FakeTexts)
        return tmp_path

    def test_build_only_dựng_nhãn_ra_đĩa_và_0_lượt_model(self, round_env, monkeypatch):
        def explode(*a, **k):
            raise AssertionError("score_with_cross_encoder bị gọi khi --build-only")

        monkeypatch.setattr(ap, "score_with_cross_encoder", explode)
        out = round_env / "probe.json"
        ds = round_env / "labelset.jsonl"
        rc = ap.main(["--round", "rz", "--phase", "full", "--build-only",
                      "--dataset-out", str(ds), "--out", str(out)])
        result = json.loads(out.read_text(encoding="utf-8"))
        assert rc == 0  # dựng được 6 cặp ⇒ bước build-only thành công; AUC chưa đo là đúng thiết kế
        assert result["n_pairs"] == 6 and result["n_scored"] == 0
        assert result["model_meta"]["mode"] == "build_only"
        assert result["aggregate"] == {}
        assert len(ds.read_text(encoding="utf-8").splitlines()) == result["n_pairs"]

    def test_main_nối_index_vào_build_pairs_không_phải_None(self, round_env):
        """Regression: quên `texts=` ở main() ⇒ mọi cặp bị loại, báo cáo in '0 cặp' như kết quả âm."""
        out = round_env / "probe.json"
        rc = ap.main(["--round", "rz", "--build-only",
                      "--dataset-out", str(round_env / "ds.jsonl"), "--out", str(out)])
        result = json.loads(out.read_text(encoding="utf-8"))
        assert rc == 0 and result["n_pairs"] == 6
        assert result["index"]["collection"] == "fake" and result["index"]["n_reads"] == 6

    def test_không_có_round_thì_dừng_bằng_SystemExit(self, round_env):
        with pytest.raises(SystemExit) as excinfo:
            ap.main(["--round", "khong_ton_tai", "--build-only",
                     "--dataset-out", str(round_env / "ds.jsonl"), "--out", str(round_env / "p.json")])
        assert "không có" in str(excinfo.value)

    def test_đọc_tập_nhãn_sẵn_không_ghi_đè_bất_kỳ_file_nào(self, round_env):
        ds = round_env / "ds.jsonl"
        before_out = round_env / "p1.json"
        ap.main(["--round", "rz", "--build-only", "--dataset-out", str(ds), "--out", str(before_out)])
        snapshot = ds.read_bytes()
        other = round_env / "khac.jsonl"
        ap.main(["--round", "rz", "--dataset-in", str(ds), "--dataset-out", str(other),
                 "--out", str(round_env / "p2.json")])
        assert ds.read_bytes() == snapshot
        assert not other.exists()

    def test_đọc_index_lỗi_vẫn_chạy_nhưng_báo_đỏ(self, round_env, monkeypatch):
        class Broken(FakeTexts):
            def text_for(self, chunk_id):
                return ""

        monkeypatch.setattr(ap, "IndexTexts", Broken)
        out = round_env / "p.json"
        rc = ap.main(["--round", "rz", "--build-only", "--dataset-out", str(round_env / "ds.jsonl"),
                      "--out", str(out)])
        result = json.loads(out.read_text(encoding="utf-8"))
        assert rc == 1 and result["n_pairs"] == 0
        assert result["ket_luan"]["verdict"] == "KHONG_DO_DUOC"
        assert result["skipped"]["khong_doc_duoc_text_ung_vien_bu"] == 6

    def test_bước_chấm_gọi_đúng_một_hàm_model_dùng_tập_nhãn_vừa_dựng(self, round_env, monkeypatch):
        seen = {}

        def fake_score(pairs, *, model_id, device, max_length=512):
            seen["n"] = len(pairs)
            seen["model_id"] = model_id
            return fake_scores(pairs, 5.0, 1.0), {"model_id": model_id, "device": device,
                                                  "n_pairs_scored": len(pairs) * 12, "mode": "scored"}

        monkeypatch.setattr(ap, "score_with_cross_encoder", fake_score)
        out = round_env / "p.json"
        rc = ap.main(["--round", "rz", "--model", "BAAI/fake-model", "--device", "cpu",
                      "--dataset-out", str(round_env / "ds.jsonl"), "--out", str(out)])
        result = json.loads(out.read_text(encoding="utf-8"))
        assert rc == 0  # scored nhưng chỉ 6 cặp < 30 ⇒ MAU_QUA_NHO (kết luận trung thực), không phải lỗi dụng cụ
        assert seen["model_id"] == "BAAI/fake-model" and seen["n"] == 6
        assert result["ket_luan"]["verdict"] == "MAU_QUA_NHO"
        assert result["aggregate"]["pooled_clean"]["auc"]["ce_max"] == 1.0

    def test_max_windows_chấm_subset_nhưng_vẫn_ghi_dủ_tập_nhãn(self, round_env, monkeypatch):
        def fake_score(pairs, *, model_id, device, max_length=512):
            return fake_scores(pairs, 5.0, 1.0), {"mode": "scored", "n": len(pairs)}

        monkeypatch.setattr(ap, "score_with_cross_encoder", fake_score)
        out = round_env / "p.json"
        ap.main(["--round", "rz", "--model", "BAAI/fake", "--max-windows", "2",
                 "--dataset-out", str(round_env / "ds.jsonl"), "--out", str(out)])
        result = json.loads(out.read_text(encoding="utf-8"))
        assert result["n_scored"] == 2 and result["n_pairs"] == 6
        assert result["aggregate"]["pooled_clean"]["n_pairs"] == 2

    def test_không_bao_giờ_ghi_vào_thư_mục_round(self, round_env):
        """Dụng cụ đo chỉ ĐỌC round; ghi đè `full.jsonl` là phạm quy tắc artifact đã công bố."""
        rd = round_env / "rounds" / "rz"
        before = {p.name: p.read_bytes() for p in rd.iterdir()}
        ap.main(["--round", "rz", "--build-only", "--dataset-out", str(round_env / "ds.jsonl"),
                 "--out", str(round_env / "p.json")])
        assert {p.name: p.read_bytes() for p in rd.iterdir()} == before
