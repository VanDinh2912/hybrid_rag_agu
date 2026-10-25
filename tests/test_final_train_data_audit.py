"""Nghiệm thu cuối, mục 5 — bất biến #7 + chặn rò rỉ trên dữ liệu train cuối (code-QA + họ loop).

Máy kiểm là `tools/diag/train_data_audit.py` (chỉ đọc). Test ở đây làm hai việc:

* `TestCoCuaMayKiem` — gieo lỗi nhân tạo vào **dữ liệu giả trong bộ nhớ** và buộc máy kiểm bắt
  đúng loại: rò rỉ nội dung thật vs chỉ trùng id (lỗi đặt tên), file trích không tồn tại, dòng
  trích vượt số dòng thật, định danh code bịa trong câu trả lời. Nếu máy kiểm mềm đi, đỏ.
* `TestSoThatCuaRepo` — ghim số thật 25-10 để mọi thay đổi dữ liệu phải đi qua một lần cập nhật
  kỳ vọng có chủ đích: 10.619 dòng/12 file khớp manifest, 0 rò rỉ nội dung, 3 id trùng tên,
  0 vi phạm #7 code-QA, và họ loop vẫn ĐỎ **chỉ** ở 5_format_and_length (đỏ dữ liệu PA-11/PA-12).

Không gọi model/Gemini; chỉ đọc `data/training/`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "diag" / "train_data_audit.py"


def _nap():
    spec = importlib.util.spec_from_file_location("train_data_audit_under_test", MODPATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["train_data_audit_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


tda = _nap()


def dong(task: str, i: str, hoi: str, dap: str, **meta) -> dict:
    return {"id": i, "task": task,
            "messages": [{"role": "user", "content": hoi},
                         {"role": "assistant", "content": dap}],
            "metadata": meta or {}}


# ---------------------------------------------------------------- 1. máy kiểm có răng
class TestCoCuaMayKiem:
    def test_fold_bo_dau_va_punctuation(self):
        assert tda.norm("Điều 12, Khoản 3!") == tda.norm("điều 12 khoản 3")
        assert tda.norm("Đào tạo") == tda.norm("đào  tạo")

    def test_id_trung_ten_nhung_khac_noi_dung_khong_phai_roi_le(self):
        """Nuôi M1 (bẫy dương tính giả): hai bản ghi cùng id, khác câu hỏi ⇒ chỉ `trung_ten`."""
        a = [dong("code_tests", "x-1", "Test A kiểm gì?", "đáp án A")]
        b = [dong("code_tests", "x-1", "Test B kiểm gì?", "đáp án B")]
        ket_qua = tda._doi_phia(a, b, ["x-1"])
        assert ket_qua["roi_le"] == []
        assert len(ket_qua["trung_ten"]) == 1

    def test_id_trung_va_cau_hoi_giong_thi_bao_roi_le(self):
        """Nuôi M2: cùng id, cùng câu hỏi (khác hoa/thường/dấu) ⇒ rò rỉ NỘI DUNG."""
        a = [dong("sft", "q-1", "Điều 12 quy định gì?", "đáp án")]
        b = [dong("seed", "q-1", "  điều 12 quy định gì? ", "đáp án khác")]
        ket_qua = tda._doi_phia(a, b, ["q-1"])
        assert len(ket_qua["roi_le"]) == 1, ket_qua
        assert ket_qua["trung_ten"] == []

    def test_bat_duoc_file_trich_khong_ton_tai(self, tmp_path, monkeypatch):
        """Nuôi M3: `metadata.file` trỏ tới file không có ⇒ `file_thieu`, `ok=False`."""
        monkeypatch.setattr(tda, "ROOT", tmp_path)
        rows = [dong("code_qa", "c-1", "Hàm f làm gì?", "`f` cộng hai số.", file="khong/co.py")]
        bao_cao = tda.self_contained_code_qa(rows)
        assert bao_cao["file_thieu"] and bao_cao["ok"] is False

    def test_bat_duoc_dong_trich_vuot_qua_file(self, tmp_path, monkeypatch):
        """Nuôi M4: trích `line=9999` trong file 3 dòng ⇒ `line_vuot`."""
        monkeypatch.setattr(tda, "ROOT", tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        rows = [dong("code_qa", "c-2", "f ở đâu?", "Định nghĩa ở `src/a.py`.",
                     file="src/a.py", line=9999)]
        bao_cao = tda.self_contained_code_qa(rows)
        assert bao_cao["line_vuot"] and bao_cao["ok"] is False

    def test_bat_duoc_dinh_danh_bia_trong_dap_an(self, tmp_path, monkeypatch):
        """Nuôi M5: câu trả lời trích ``ham_khong_ton_tai`` không có trong file ⇒ vi phạm #7."""
        monkeypatch.setattr(tda, "ROOT", tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("def that_ham():\n    return 1\n", encoding="utf-8")
        rows = [dong("code_qa", "c-3", "Có hàm nào?",
                     "Hàm `ham_khong_ton_tai` xử lý việc đó, xem `that_ham`.",
                     file="src/a.py")]
        bao_cao = tda.self_contained_code_qa(rows)
        bia = [v["token"] for v in bao_cao["dinh_danh_khong_co"]]
        assert "ham_khong_ton_tai" in bia, bao_cao
        assert "that_ham" not in bia, "định danh thật phải lọt qua"
        assert bao_cao["dinh_danh_kiem_tra"] == 2

    def test_dinh_danh_duoi_duong_dan_khong_bi_trung_bat(self, tmp_path, monkeypatch):
        """Đường dẫn `src/a.py` trong answer không bị coi là 'định danh bịa' (đã kiểm ở luật 1)."""
        monkeypatch.setattr(tda, "ROOT", tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("def that_ham():\n    return 1\n", encoding="utf-8")
        rows = [dong("code_qa", "c-4", "Ở đâu?", "Xem `src/a.py`, hàm `that_ham`.", file="src/a.py")]
        bao_cao = tda.self_contained_code_qa(rows)
        assert bao_cao["dinh_danh_khong_co"] == []


# ---------------------------------------------------------------- 2. số thật của repo
@pytest.fixture(scope="module")
def kiem_toan():
    return dict(dem=tda.line_counts(), leak=tda.leak_checks(),
                sc=tda.self_contained_code_qa(tda.read_jsonl(tda.TRAIN_DIR / "sft_train.jsonl")),
                loop=tda.loop_family(sorted(p.name for p in tda.TRAIN_DIR.glob("t4b*") if p.is_dir())))


class TestSoThatCuaRepo:
    def test_du_12_file_dem_dung_nhau_manifest(self, kiem_toan):
        dem = kiem_toan["dem"]
        assert len(dem["rows"]) == 12
        assert dem["so_file_lech_manifest"] == 0
        assert dem["total_dong"] == 10619, dem["total_dong"]
        by_file = {r["file"]: r["dong_thuc"] for r in dem["rows"]}
        assert by_file["sft_train.jsonl"] == 1635
        assert by_file["sft_val.jsonl"] == 50
        assert by_file["sft_benchmark_seed.jsonl"] == 680
        assert by_file["classifier_train.jsonl"] == 2778
        assert by_file["classifier_benchmark_seed.jsonl"] == 447

    def test_khong_roi_le_noi_dung_giua_cac_tap(self, kiem_toan):
        leak = kiem_toan["leak"]
        assert leak["tong_roi_le_thuc"] == 0, {
            k: v for k, v in leak.items() if k != "theo_id"}

    def test_ghim_3_id_trung_ten_khong_phai_roi_le(self, kiem_toan):
        """Hiện trạng đã ghi: bộ đếm id theo task nên `code_tests-00049` (train) trùng tên với
        `code_tests-00049` (val) nhưng khác nội dung. Ghim lại để nếu dữ liệu rebuild và số
        này đổi, người làm phải cập nhật có chủ đích."""
        leak = kiem_toan["leak"]
        assert leak["tong_id_trung_ten"] == 3, leak["phan_tich_id"]
        for cuoc in leak["phan_tich_id"].values():
            assert cuoc["roi_le"] == []

    def test_retrieval_pairs_khong_co_ban_gia_lap(self, kiem_toan):
        khac = kiem_toan["leak"]["theo_khac"]
        assert khac["retrieval_query_positive_trung_nguyen_ve"] == 0
        assert khac["retrieval_query_trung_nhau_nhung_khac_positive"] == 82

    def test_bat_bien_7_tren_dong_train_code_qa(self, kiem_toan):
        sc = kiem_toan["sc"]
        assert sc["n_rows"] == 1635
        assert sc["co_trich_file"] == 1049
        assert sc["file_thieu"] == [] and sc["line_vuot"] == []
        assert sc["dinh_danh_kiem_tra"] == 890
        assert sc["dinh_danh_khong_co"] == []
        assert sc["ok"] is True

    def test_ho_loop_do_chi_o_muc_5_du_lieu(self, kiem_toan):
        roots = kiem_toan["loop"]["roots"]
        assert [r["root"] for r in roots] == ["t4b_r5", "t4b_r5r6r7", "t4b_r5r8r9r10"]
        for r in roots:
            assert "error" not in r, r
            # #7 và chống rò rỉ phải XANH; ĐỎ duy nhất là độ dài dòng (PA-11/PA-12)
            assert r["checks"]["1_evidence_in_context"] is True, r["root"]
            assert r["checks"]["2_no_test_leak"] is True, r["root"]
            assert r["evidence_missing_mandatory"] == 0, r["root"]
            assert r["id_leaks"] == 0 and r["sentence_leaks"] == 0, r["root"]
            assert r["verdict"] == "ĐỎ" and r["red_checks"] == ["5_format_and_length"], r["root"]
        thu = next(r for r in roots if r["root"] == "t4b_r5r8r9r10")
        assert thu["n_train_rows"] == 13 and thu["n_holdout_rows"] == 10
        assert thu["evidence_missing_gold_sentence"] == 5  # INFO, đã ghi ở PA-28
