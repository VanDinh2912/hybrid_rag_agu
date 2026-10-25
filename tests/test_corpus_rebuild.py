"""Unit test cho T2 — kiểm định corpus rebuild (`tools/diag/check_corpus.py`).

Phạm vi (Test Engineer, 24-10): các HÀM THUẦN của checker bằng dữ liệu ngắn tự dựng —
KHÔNG gọi model, KHÔNG đọc chroma_db thật, không đụng tệp corpus. Đường thật (mục 7–10)
chạy ở `tools/diag/check_corpus.py` (báo cáo test_T2.md), không phải ở đây.

Sáu ca đề bài:
  #1 bảng mã/normalisation: pipeline này KHÔNG remap TCVN3/VNI (T2 chọn re-OCR); phép
     chuẩn hoá ký tự DUY NHẤT áp dụng là `fold` -> test idempotent + giữ ký tự lạ.
  #2 bảo toàn thực thể pháp lý + bắt được đổi 1 chữ số.
  #3 chỉ số chất lượng (từ có dấu, vocab proxy) khớp tính tay.
  #4 cổng chất lượng: dưới ngưỡng -> 'khoảng_trống', không nhận nhãn 'tốt'.
  #5 an toàn dữ liệu: build vào thư mục MỚI; từ chối nếu đích đã tồn tại; băm index cũ.
  #6 xác định: cùng input -> cùng chunk, cùng thứ tự, cùng id.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.text_utils import fold  # noqa: E402
from tools.diag.corpus_diacritics import word_diacritic_ratio  # noqa: E402
from tools.diag.quality_check_vie import vocab_ratio  # noqa: E402

MODPATH = REPO_ROOT / "tools" / "diag" / "check_corpus.py"


def load_cc():
    spec = importlib.util.spec_from_file_location("check_corpus_under_test", MODPATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_corpus_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


cc = load_cc()


# ================================================================ #1 normalisation / bảng mã
class TestEncodingNormalisation:
    """Không có bộ remap TCVN3/VNI trong pipeline này (T2 = re-OCR). Phép chuẩn hoá
    ký tự duy nhất chạm vào văn bản là `fold`, dùng để SO KHỚP (không ghi lại corpus)."""

    def test_fold_idempotent_chay_hai_lan_khong_doi(self):
        for s in ["Điều 12", "TRƯỜNG ĐẠI HỌC AN GIANG", "日本😀 1.500.000đ", "Khoản 3 a"]:
            assert fold(fold(s)) == fold(s)

    def test_fold_giu_ky_tu_la_khong_boc_duoc_xoa_hoac_doan(self):
        # Nhật/Ký tự emoji/Hoa không thuộc bảng tiếng Việt -> PHẢI còn nguyên, không bị âm thầm bỏ.
        out = fold("日本😀 abc")
        assert "日本" in out and "😀" in out

    def test_pipeline_khong_co_boi_remap_byte_tcvn3_vni(self):
        # Chứng minh bằng phủ định: `check_corpus` không expose hàm ánh xạ bảng mã nào
        # (T2 sửa mất dấu bằng re-OCR, không phải giải mã code-page).
        mapper = [n for n in dir(cc) if "tcvn" in n.lower() or "vni" in n.lower()
                  or "codepage" in n.lower() or ("map" in n.lower() and "legacy" in n.lower())]
        assert mapper == []

    def test_khong_dung_fold_de_so_sanh_thu_tu_phap_ly(self):
        # fold("Điều")=='dieu' -> nếu so thực thể bằng fold thì 'Điều 12' vs 'dieu 12'
        # bị coi là an toàn (bỏ lọt mất dấu). Test khoá hành vi so NGUYÊN VĂN của checker.
        r = cc.compare_entities("Điều 12", "dieu 12")
        assert r["preserved"] is False  # mất dấu THẬT sự bị tính là thay đổi thực thể


# ================================================================ #2 bảo toàn thực thể pháp lý
SAMPLES = [
    "1054/QĐ-ĐHAG", "1504/QĐ-ĐHAG", "QD1133",
    "Điều 12", "Khoản 3", "Điểm a", "Mục 2",
    "28/9/2020", "ngày 28 tháng 9 năm 2020",
    "1.500.000 đồng", "70 %", "12 tín chỉ",
]


class TestEntityPreservation:
    def test_extract_bat_du_danh_sach_thuc_the_mau(self):
        text = " ".join(SAMPLES)
        found = {e for v in cc.extract_legal_entities(text).values() for e in v}
        # mỗi thực thể mẫu phải xuất hiện (khớp một phần vì NUMBER_RE tách đơn vị)
        for probe in ["1054/QĐ-ĐHAG", "Điều 12", "Khoản 3", "28/9/2020", "70 %"]:
            assert any(probe in f for f in found), f"không bắt được {probe}"

    def test_sao_chep_nguyen_van_thuc_the_duoc_bao_toan(self):
        text = "Quyết định 1054/QĐ-ĐHAG Điều 12 Khoản 3 ngày 28/9/2020 thu 1.500.000 đồng."
        r = cc.compare_entities(text, text)
        assert r["preserved"] is True and r["missing"] == {}

    def test_so_sanh_bat_duoc_doi_mot_chu_so(self):
        before = "Xử lý theo Điều 12 của quy chế."
        after = "Xử lý theo Điều 13 của quy chế."  # đổi đúng 1 chữ số
        r = cc.compare_entities(before, after)
        assert r["preserved"] is False
        assert "Điều 12" in r["missing"]["legal_ref"]
        assert "Điều 13" in r["added"]["legal_ref"]

    def test_so_sanh_bat_duoc_mat_hoan_toan_thuc_the(self):
        before = "Ban hành kèm QĐ 1054/QĐ-ĐHAG ngày 28/9/2020."
        after = "Ban hành kèm ngày 28/9/2020."  # mất số hiệu
        r = cc.compare_entities(before, after)
        assert r["preserved"] is False
        assert any("1054" in m for m in r["missing"]["decision_no"])

    def test_khong_phan_biet_hoa_thuong_cua_tu_thuong_khong_phai_thuc_the(self):
        # chữ thường không mang thực thể -> thêm/bớt hoa không tạo 'missing' giả
        before = "Điều 5 quy định."
        after = "Điều 5 quy định"  # chỉ khác dấu chấm
        assert cc.compare_entities(before, after)["preserved"] is True


# ================================================================ #3 chỉ số chất lượng
class TestQualityMetrics:
    def test_word_diacritic_ratio_co_dau_het_bang_1(self):
        _m, _t, r = word_diacritic_ratio("Điều khoản ngày tháng năm")
        assert r == 1.0

    def test_word_diacritic_ratio_khong_dau_bang_0(self):
        _m, _t, r = word_diacritic_ratio("Dieu khoan ngay thang nam")
        assert r == 0.0

    def test_word_diacritic_ratio_tron_khop_tinh_tay(self):
        # "Điều khoản Dieu khoan xyz": 5 từ có chữ, 2 từ có dấu -> 0,4
        m, t, r = word_diacritic_ratio("Điều khoản Dieu khoan xyz")
        assert (m, t, r) == (2, 5, 0.4)

    def test_word_diacritic_ratio_khong_tu_tra_none(self):
        assert word_diacritic_ratio("123 456 ...")[2] is None

    def test_vocab_ratio_khop_tinh_tay(self):
        hit, total, r = vocab_ratio("dieu khoan abc", {"dieu", "khoan"})
        assert (hit, total) == (2, 3) and abs(r - 2 / 3) < 1e-9

    def test_vocab_ratio_gi_giong_nguyen_van_giup_vocab_fold(self):
        # vocab đã fold + hàm fold cả token -> "Điều" vẫn khớp "dieu": đây là proxy
        # "có phải tiếng Việt không", KHÔNG phải đo mất dấu (việc đó thuộc word_diacritic_ratio).
        _h, _t, r = vocab_ratio("Điều", {"dieu"})
        assert r == 1.0
        h, t, r2 = vocab_ratio("Điều xyz", {"dieu"})
        assert (h, t, r2) == (1, 2, 0.5)

    def test_vocab_ratio_khong_token_chu_tra_none(self):
        assert vocab_ratio("123 45.6% ...", {"dieu"})[2] is None


# ================================================================ #4 cổng chất lượng
class TestQualityGate:
    def test_duoi_nguong_nhan_nhan_khoang_trong_khong_phai_tot(self):
        st = cc.file_status(0.30, 0.90)  # dấu < 0,60
        assert st["status"] == "khoảng_trống" and st["reasons"]

    def test_vocab_thap_cung_bi_cam(self):
        assert cc.file_status(0.80, 0.50)["status"] == "khoảng_trống"

    def test_tren_du_nguong_nhan_tot(self):
        assert cc.file_status(0.80, 0.85)["status"] == "tốt"

    def test_khong_do_duoc_dau_bi_xep_khoang_trong_fail_closed(self):
        assert cc.file_status(None, None)["status"] == "khoảng_trống"

    def test_partition_khong_dem_tep_khoang_trong_vao_danh_sach_tot(self):
        rows = [{"stem": "good", "ratio": 0.9, "vocab_ratio": 0.9},
                {"stem": "gap", "ratio": 0.1, "vocab_ratio": 0.4}]
        good, gap = cc.partition_by_gate(rows)
        assert [g["stem"] for g in good] == ["good"]
        assert [g["stem"] for g in gap] == ["gap"]

    def test_leak_report_bao_tep_khoang_trong_lot_vao_index(self):
        rep = cc.gap_leak_report(["a", "b"], {"a": 3, "b": 0})
        assert rep["n_leaked_into_index"] == 1 and rep["leaked"] == ["a"] and rep["silent"] is True


# ================================================================ #5 an toàn dữ liệu
def _mk_tree(root: Path, name: str, files: dict[str, str]) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        fp = d / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(content.encode("utf-8"))
    return d


class TestDataSafety:
    def test_dir_digest_on_dinh_truoc_sau_khong_doi_khi_ghi_thu_muc_khac(self, tmp_path):
        old = _mk_tree(tmp_path, "chroma_db", {"a.bin": "DATA", "sub/b": "x"})
        before = cc.dir_digest(old)
        _mk_tree(tmp_path, "chroma_db_vie", {"a.bin": "NEW"})  # build ở NƠI KHÁC
        assert cc.dir_digest(old) == before  # index cũ không bị chạm

    def test_dir_digest_thay_doi_khi_noi_dung_doi(self, tmp_path):
        d = _mk_tree(tmp_path, "db", {"a": "1"})
        h1 = cc.dir_digest(d)
        (d / "a").write_bytes(b"2")
        assert cc.dir_digest(d) != h1

    def test_dir_digest_bo_wal_shm(self, tmp_path):
        d = _mk_tree(tmp_path, "db", {"x.sqlite3": "A", "x.sqlite3-wal": "W"})
        stable = cc.dir_digest(d)
        (d / "x.sqlite3-wal").write_bytes(b"CHANGED")  # WAL dao động vô hại
        assert cc.dir_digest(d) == stable

    def test_dir_digest_thu_muc_thieu_tra_missing(self, tmp_path):
        assert cc.dir_digest(tmp_path / "khong_ton_tai") == "MISSING"

    def test_plan_index_write_tu_choi_gui_de_len_dich_da_ton_tai(self, tmp_path):
        _mk_tree(tmp_path, "chroma_db_vie", {"a": "x"})
        with pytest.raises(SystemExit) as ei:
            cc.plan_index_write(tmp_path / "chroma_db_vie")
        assert "--force" in str(ei.value)

    def test_plan_index_write_cho_phep_thu_muc_moi(self, tmp_path):
        plan = cc.plan_index_write(tmp_path / "chroma_new")
        assert plan["created_now"] is True

    def test_plan_index_write_tu_choi_de_len_index_dang_dung_du_force(self, tmp_path):
        protected = _mk_tree(tmp_path, "chroma_db", {"a": "x"})
        with pytest.raises(SystemExit) as ei:
            cc.plan_index_write(protected, protected=[protected], force=True)
        assert "LÀ index đang dùng" in str(ei.value)

    def test_plan_index_write_force_cho_phep_build_lai_tep_tu_chon(self, tmp_path):
        d = _mk_tree(tmp_path, "target", {"a": "x"})
        plan = cc.plan_index_write(d, force=True)
        assert plan["force"] is True


# ================================================================ #6 tính xác định
DOC_STRUCTURED = {"title": "Quy chế", "tier": "Tầng 1",
                  "content": "Điều 1. Nội dung một đủ dài để tạo chunk.\n\n"
                             "Điều 2. Nội dung hai cũng khá dài cho chunk.\n\n"
                             "Điều 3. Nội dung ba dài thêm chút nữa nhé."}
DOC_FALLBACK = {"title": "Thông báo", "tier": "Tầng 2",
                "content": "Đây là đoạn văn một khá dài. Đây là đoạn văn hai cũng dài. "
                           "Đây là đoạn ba để đủ khối lượng."}


class TestDeterminism:
    def test_build_chunks_hai_lan_giong_het_id_va_thu_tu(self):
        docs = [DOC_STRUCTURED, DOC_FALLBACK]
        a = cc.build_chunks(docs)
        b = cc.build_chunks(docs)
        assert [c["chunk_id"] for c in a] == [c["chunk_id"] for c in b]
        assert [c["text"] for c in a] == [c["text"] for c in b]
        assert a == b

    def test_chunk_id_danh_tuan_tu_lien_tuc(self):
        out = cc.build_chunks([DOC_STRUCTURED, DOC_FALLBACK])
        assert [c["chunk_id"] for c in out] == list(range(len(out)))

    def test_build_chunks_khong_rong_voi_dau_vao_trong(self):
        assert cc.build_chunks([]) == []

    def test_index_signature_on_dinh_theo_noi_dung_va_thu_tu(self):
        s1 = cc.index_signature(["abc", "def"])
        s2 = cc.index_signature(["abc", "def"])
        s3 = cc.index_signature(["def", "abc"])
        assert s1 == s2 and s1["signature"] != s3["signature"]

    def test_pick_segments_seed_co_dinh_tai_lap_giong_het(self):
        data = {f"s{i}": ("Đoạn dài đủ điều kiện để vào pool. " * 3) for i in range(30)}
        p1 = cc.pick_segments(data, n=20, seed=20261024)
        p2 = cc.pick_segments(data, n=20, seed=20261024)
        assert p1 == p2 and len(p1) <= 20

    def test_pick_segments_doi_seed_thi_khac(self):
        data = {f"s{i}": ("Đoạn dài đủ điều kiện để vào pool. " * 3) for i in range(30)}
        assert cc.pick_segments(data, 20, 1) != cc.pick_segments(data, 20, 2)


# ================================================================ #9 gold coverage + hygiene (thuần)
class TestGoldCoverageAndHygiene:
    def test_gold_con_tim_thay_khong_bi_tinh_mat(self):
        idx = ["[Quy chế] - [Điều 1] điều mười hai khoản ba ngày hai mươi"]
        ts = [{"id": "A", "family": "EXACT", "gold_sentence": "khoản ba"}]
        cov = cc.gold_coverage(ts, idx)
        assert cov["n_missing_gold"] == 0 and cov["red"] is False

    def test_gold_mat_han_that_phan_loai_absent(self):
        idx = ["[Khác] nội dung hoàn toàn không liên quan tới câu vàng đã cho"]
        ts = [{"id": "A", "family": "EXACT", "gold_sentence": "thực thể xyz 999"}]
        cov = cc.gold_coverage(ts, idx)
        assert cov["n_missing_gold"] == 1
        assert cov["missing"][0]["class"] == "absent"

    def test_gold_doi_chuOCR_phan_loai_near_khong_han_muc_do(self):
        # nội dung gần giống nhưng khác chữ -> near (vẫn tính vào missing verbatim, không ẩn)
        idx = ["[Quy chế] sinh viên năm nhất học kỳ một"]
        ts = [{"id": "A", "family": "CLOZE", "gold_sentence": "sinh viên năm hai học kỳ một"}]
        cov = cc.gold_coverage(ts, idx)
        assert cov["n_missing_gold"] == 1 and cov["n_near_verbatim"] == 1

    def test_item_khong_gold_sentence_khong_vao_mau_so(self):
        cov = cc.gold_coverage([{"id": "H", "family": "HUMAN", "gold_sentence": ""}], ["x"])
        assert cov["n_checkable"] == 0 and cov["n_no_gold_sentence"] == 1

    def test_hygiene_bat_chunk_rong(self):
        h = cc.chunk_hygiene([{"text": "   ", "chunk_id": 0}, {"text": "abc def", "chunk_id": 1}])
        assert h["n_empty"] == 1

    def test_hygiene_bat_chunk_trung_nguyen_van(self):
        dup = "Nội dung giống hệt nhau xuất hiện hai lần."
        h = cc.chunk_hygiene([{"text": dup, "chunk_id": 0}, {"text": dup, "chunk_id": 1}])
        assert h["n_duplicate_chunks"] == 1 and h["n_duplicate_groups"] == 1

    def test_hygiene_khong_trung_kh_no_red(self):
        h = cc.chunk_hygiene([{"text": "khác nhau hoàn toàn một", "chunk_id": 0},
                              {"text": "khác nhau hoàn toàn hai", "chunk_id": 1}])
        assert h["duplicate_over_threshold"] is False


# ================================================================ #1b ký tự ngoài bảng Việt
class TestForeignGlyphs:
    """Đề bài mục #1: ký tự lạ phải ĐƯỢC GHI NHẬN và GIỮ NGUYÊN — cấm bỏ, cấm đoán.

    Bộ phân loại dùng phân tích Unicode (NFD) thay vì bảng mã cứng: một glyph tiếng Việt
    dựng sẵn hay dựng tổ hợp đều phải được nhận; CJK/emoji/ký tự điều khiển phải bị đánh dấu.
    """

    @pytest.mark.parametrize("ch", ["a", "Z", " ", "\t", "\n", "đ", "Đ", "ă", "ộ", "ữ",
                                    "–", "“", "…", "→", "§", "°"])
    def test_ky_tu_thuoc_dai_viet_ascii_duoc_chap_nhan(self, ch):
        assert cc.char_is_supported(ch) is True

    @pytest.mark.parametrize("ch", ["日", "本", "😀", "Ð", "а",  # CJK, emoji, eth, Cyrillic
                                    "\x00", "\x07", "\ufeff"])
    def test_ky_tu_ngoai_dai_viet_bi_danh_dau(self, ch):
        assert cc.char_is_supported(ch) is False

    def test_nguyen_am_viet_dung_to_hop_van_duoc_nhan(self):
        # "ộ" = o + dấu mũ + dấu nặng; hàm phân tích NFD nên đúng cả khi tệp lưu dạng tổ hợp.
        # (NFD sắp lại dấu theo combining class nên so qua NFC, không so chuỗi thô.)
        decomposed = "o\u0302\u0323"
        import unicodedata
        assert unicodedata.normalize("NFC", decomposed) == "ộ"
        assert cc.char_is_supported("ộ") is True

    def test_dau_to_hop_dung_rieng_le_bi_coi_la_la(self):
        # Dấu thanh đứng một mình không tạo thành ký tự tiếng Việt hợp lệ.
        assert cc.char_is_supported("\u0302") is False

    def test_bao_cao_dem_dung_va_khong_bo_sot(self):
        rep = cc.foreign_glyph_report(["Điều 12 日本", "khoản 日本"])
        assert rep["n_chars"] == len("Điều 12 日本") + len("khoản 日本")
        assert rep["n_foreign"] == 4          # 日本 xuất hiện 2 lần trong mỗi câu
        assert rep["n_foreign_kinds"] == 2
        assert rep["n_supported"] + rep["n_foreign"] == rep["n_chars"]

    def test_moi_dong_co_ma_unicode_va_vi_du_nguyen_van(self):
        rep = cc.foreign_glyph_report(["quy chế 日本 áp dụng"])
        row = rep["foreign"][0]
        assert row["char"] == "日" and row["codepoint"] == "U+65E5"
        assert row["count"] == 1
        assert "日" in row["example"] and "quy chế" in row["example"]

    def test_sap_xep_theo_so_lan_giam_dan(self):
        rep = cc.foreign_glyph_report(["😀😀😀 日日 Ð"])
        assert [r["char"] for r in rep["foreign"]] == ["😀", "日", "Ð"]
        assert [r["count"] for r in rep["foreign"]] == [3, 2, 1]

    def test_cung_so_lan_thi_sap_theo_ma_tang_dan(self):
        rep = cc.foreign_glyph_report(["本日"])
        assert [r["char"] for r in rep["foreign"]] == ["日", "本"]

    def test_max_rows_cat_dung_va_bao_truncated(self):
        rep = cc.foreign_glyph_report(["😀日本Ð"], max_rows=2)
        assert len(rep["foreign"]) == 2 and rep["foreign_truncated"] is True
        assert rep["n_foreign_kinds"] == 4  # đếm vẫn đủ, chỉ dòng hiển thị bị cắt

    def test_khong_cat_khi_duoi_nguong(self):
        rep = cc.foreign_glyph_report(["😀"], max_rows=40)
        assert rep["foreign_truncated"] is False

    def test_van_ban_sach_tra_ve_rong_khong_bao_do_gia(self):
        rep = cc.foreign_glyph_report(["Điều 12 khoản 3 – quy chế", ""])
        assert rep["n_foreign"] == 0 and rep["foreign"] == []
        assert rep["n_foreign_kinds"] == 0 and rep["foreign_truncated"] is False

    def test_bao_cao_chi_doc_khong_sua_du_lieu_dau_vao(self):
        texts = ["Điều 12 日本", "khoản 日本"]
        snapshot = list(texts)
        cc.foreign_glyph_report(texts)
        assert texts == snapshot  # tham chiếu và nội dung không bị chạm

    def test_vi_du_ngan_duoc_chuan_hoa_khoang_trang(self):
        rep = cc.foreign_glyph_report(["a\n\n  😀\t\tb"], context_chars=6)
        assert rep["foreign"][0]["example"] == "a 😀 b"


# ================================================================ #1/#2 bảo toàn nguyên văn qua cắt chunk
DOC_VERBATIM = {
    "title": "Quyết định 1054/QĐ-ĐHAG",
    "tier": "Tầng 1",
    "content": (
        "Căn cứ Quyết định số 1054/QĐ-ĐHAG ngày 28/9/2020 của Hiệu trưởng "
        "Trường Đại học An Giang.\n\n"
        "Điều 12. Mức học phí là 1.500.000 đồng cho 12 tín chỉ, tăng 70 % so với "
        "năm trước; áp dụng từ ngày 28 tháng 9 năm 2020 cho sinh viên đại học "
        "chính quy.\n\n"
        "Khoản 3. Sinh viên thuộc diện chính sách được giảm 50 % học phí theo "
        "quy định hiện hành của Nhà trường."
    ),
}


class TestVerbatimPreservation:
    """Đề bài #1 ("đầu ra đúng 100% từng ký tự") + #2 (thực thể còn nguyên) áp lên
    ĐƯỜNG THẬT của checker: `build_chunks` là bước duy nhất chạm vào văn bản trước khi
    ghi index. Không có bộ remap bảng mã, nên tính chất cần khoá là: cắt chunk KHÔNG
    được fold / bỏ dấu / sửa ký tự — chỉ được THÊM tiền tố `[tên văn bản] - [Điều N.]`.

    Vì sao phải có: các test khác chỉ so lần chạy này với lần chạy kia (xác định) nên
    một đột biến `fold(text)` trong `build_chunks` vẫn "xác định" và lọt toàn bộ 78 test.
    """

    def _texts(self, doc=None):
        return [c["text"] for c in cc.build_chunks([doc or DOC_VERBATIM])]

    def test_khong_bo_ky_tu_nao_cua_nguon_khi_cat_chunk(self):
        # Đếm ký tự (bỏ whitespace: chunker được phép đổi cách xuống dòng/gộp đoạn).
        need = Counter(re.sub(r"\s", "", DOC_VERBATIM["content"]))
        got = Counter(re.sub(r"\s", "", "\n".join(self._texts())))
        missing = need - got  # theo từng ký tự, kể cả dấu thanh
        assert not missing, f"ký tự nguồn bị mất: {dict(list(missing.items())[:10])}"

    def test_ky_tu_co_dau_con_nguyen_khong_bi_fold(self):
        joined = "\n".join(self._texts())
        for probe in ["Điều 12", "Khoản 3", "Trường Đại học An Giang",
                      "chính sách", "giảm 50 %"]:
            assert probe in joined, f"mất nguyên văn (có dấu): {probe!r}"
        # dạng đã bỏ dấu KHÔNG được xuất hiện thay cho bản gốc
        assert "Dieu 12" not in joined and "Truong Dai hoc" not in joined

    def test_thuc_the_phap_ly_nguyen_van_sau_khi_cat_chunk(self):
        joined = "\n".join(self._texts())
        for probe in ["1054/QĐ-ĐHAG", "Điều 12", "1.500.000 đồng",
                      "70 %", "12 tín chỉ", "28/9/2020"]:
            assert probe in joined
        r = cc.compare_entities(DOC_VERBATIM["content"], joined)
        assert r["preserved"] is True and r["missing"] == {}
