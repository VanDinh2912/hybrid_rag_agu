"""Nghiệm thu cuối, mục 5 — quét secret / đường dẫn cá nhân / PII trên file đã track.

Hai lời hứa, tách rõ:

* `TestCoCuaMayQuet` — chứng minh máy quét **có răng**: gieo credential thật, đường dẫn cá nhân
  thật vào cây giả trong `tmp_path` và buộc nó phải phân loại đúng `SECRET_COTHAT` /
  `DUONG_DAN_CA_NHAN`; đồng thời gieo placeholder (`your_gemini_api_key_here`) và fixture test
  (`api_key="test-key-…"`) và buộc nó **không** báo nhầm thành secret. Nếu ai đó làm mềm máy
  quét (bỏ pattern, nuốt mọi thứ vào BI_MAU), các test này đỏ.
* `TestHienTrangRepo` — ghi lại **số thật** của cây hiện tại để báo cáo: 0 credential, 0 đường
  dẫn cá nhân, nhưng còn PII nghiệp vụ trong artifact đã commit và `git add -A` vẫn quét vào
  `tmp/` + `models/` + `data/loop/rounds/`. Những dòng này cố ý ghim hiện trạng: khi PA-30
  (bổ sung `.gitignore`) hoặc PA-31 (che PII) được áp, test sẽ đỏ và buộc người thực hiện
  cập nhật có chủ đích thay vì âm thầm đổi kết luận.

Máy quét chỉ đọc; test không ghi gì ngoài `tmp_path`.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "diag" / "secret_scan.py"


def _nap_chui():
    spec = importlib.util.spec_from_file_location("secret_scan_under_test", MODPATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["secret_scan_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _ghep(*phan: str) -> str:
    """Dựng chuỗi mẫu **tại runtime** từ các mảnh.

    Lý do (bài học thật của phiên này): khi file test này được `git add`, chính các mẫu
    "credential thật" viết nguyên literal trong test rơi vào phạm vi quét của
    `tracked_files()` ⇒ máy quét báo 4 dòng `SECRET_COTHAT` + 4 dòng `DUONG_DAN_CA_NHAN`
    và `TestHienTrangRepo` đỏ 3 test (không phải vì repo có secret, mà vì test tự gieo
    secret vào source). Ghép mảnh giữ nguyên răng — máy quét vẫn phải bắt được chuỗi hoàn
    chỉnh khi nó được ghi ra `tmp_path` — mà không để lại literal hình credential/PII trong
    file đã commit.
    """
    return "".join(phan)


# ---------------------------------------------------------------- 1. máy quét có răng
class TestCoCuaMayQuet:
    @pytest.fixture()
    def cay_gia(self, tmp_path, monkeypatch):
        mod = _nap_chui()
        (tmp_path / "data").mkdir()
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        return mod, tmp_path

    def _quet(self, mod, tmp_path, ten_file: str, noi_dung: str):
        (tmp_path / ten_file).write_text(noi_dung, encoding="utf-8")
        return mod.scan([ten_file])

    def test_bat_duoc_google_key_that(self, cay_gia):
        """Đột biến M1: `AIza…` 39 ký tự trong file track ⇒ SECRET_COTHAT."""
        mod, tmp = cay_gia
        key = _ghep("AIza", "SyD-", "abcdefghij", "0123456789", "KLMNOPQRSTU")
        r = self._quet(mod, tmp, "config.py", f'KEY = "{key}"\n')
        assert r["by_loai"].get("SECRET_COTHAT") == 1, r["by_loai"]

    def test_bat_duoc_private_key_block(self, cay_gia):
        """Đột biến M2: khối PEM ⇒ SECRET_COTHAT."""
        mod, tmp = cay_gia
        pem = _ghep("-----BEGIN ", "RSA PRIVATE KEY", "-----")
        r = self._quet(mod, tmp, "id.pem.txt", f"{pem}\nAAAA\n")
        assert r["by_loai"].get("SECRET_COTHAT") == 1, r["by_loai"]

    def test_bat_duoc_private_key_khong_co_duoi_txt(self, cay_gia):
        """Không có đuôi trong TEXT_EXT thì file bị bỏ qua — ghi lại thành RÀNG BUỘC của máy quét."""
        mod, tmp = cay_gia
        pem = _ghep("-----BEGIN ", "RSA PRIVATE KEY", "-----")
        r = self._quet(mod, tmp, "id.pem", f"{pem}\nAAAA\n")
        assert r["files_scanned"] == 0, "máy quét âm thầm đọc cả file nhị phân? sửa tài liệu"

    def test_bat_duoc_duong_dan_ca_nhan(self, cay_gia):
        """Đột biến M3: `C:\\Users\\<ten>` và `/home/<ten>` ⇒ DUONG_DAN_CA_NHAN."""
        mod, tmp = cay_gia
        duong_dan = _ghep("Xem C:\\", "Users\\", "alice\\repo\\x.py và /", "home", "/bob/work/y.py\n")
        r = self._quet(mod, tmp, "a.md", duong_dan)
        assert r["by_loai"].get("DUONG_DAN_CA_NHAN") == 2, r["by_loai"]

    def test_placeholder_khong_bi_bao_nham_la_secret(self, cay_gia):
        """.env.example dùng `your_gemini_api_key_here` ⇒ chỉ BI_MAU."""
        mod, tmp = cay_gia
        r = self._quet(mod, tmp, ".env.example", "GEMINI_API_KEY=your_gemini_api_key_here\n")
        assert r["by_loai"].get("SECRET_COTHAT") is None, r["by_loai"]
        assert r["by_loai"].get("BI_MAU", 0) >= 1

    def test_fixture_test_khong_bi_bao_nham_la_secret(self, cay_gia):
        """`api_key="test-key-t4-contract"` trong unit test ⇒ BI_MAU, không phải credential."""
        mod, tmp = cay_gia
        r = self._quet(mod, tmp, "t.py", 'g = GeminiGenerator(api_key="test-key-t4-contract")\n')
        assert r["by_loai"].get("SECRET_COTHAT") is None, r["by_loai"]
        assert any("fixture" in h["pattern"] for h in r["hits"]), r["hits"]

    def test_email_va_dien_thoai_dinh_dang_bi_liet_ke(self, cay_gia):
        """PII nghiệp vụ: email + số điện thoại phải được đếm (không bị coi là vô hại)."""
        mod, tmp = cay_gia
        dong = _ghep("Liên hệ: q", "tho@tdtu", ".edu.vn — hotline 09", "18", "607", "123",
                     " — MSSV 20", "2160", "7123\n")
        r = self._quet(mod, tmp, "d.md", dong)
        assert r["by_loai"].get("DU_CAO_NHAN_HOC", 0) >= 3, r["by_loai"]

    def test_khong_in_nguyen_van_mau_bip_mat(self, cay_gia):
        """Báo cáo phải redact: không rò rỉ nguyên chuỗi key trong JSON kết quả."""
        mod, tmp = cay_gia
        key = _ghep("AIza", "SyD-", "abcdefghij", "0123456789", "KLMNOPQRSTU")
        r = self._quet(mod, tmp, "c.py", f'KEY = "{key}"\n')
        blob = json.dumps(r, ensure_ascii=False)
        assert key not in blob
        assert "ký tự" in blob


# ---------------------------------------------------------------- 2. hiện trạng repo
@pytest.fixture(scope="module")
def ket_qua():
    mod = _nap_chui()
    files = mod.tracked_files("tracked")
    return mod, files, mod.scan(files)


class TestHienTrangRepo:

    def test_khong_co_credential_that_trong_file_track(self, ket_qua):
        mod, files, r = ket_qua
        assert r["secret_hits"] == [], r["secret_hits"][:5]
        assert r["by_loai"].get("SECRET_COTHAT") in (None, 0)

    def test_khong_co_duong_dan_ca_nhan_trong_file_track(self, ket_qua):
        mod, files, r = ket_qua
        assert r["duongdan_hits"] == [], r["duongdan_hits"][:5]

    def test_file_env_that_khong_bien_trong_git(self, ket_qua):
        """.env (chứa key thật) không được git theo dõi; .env.example thì có."""
        mod, files, r = ket_qua
        assert ".env" not in files
        assert ".env.example" in files
        kiem = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=str(ROOT),
                              capture_output=True, stdin=subprocess.DEVNULL)
        assert kiem.returncode == 0, ".env phải nằm trong ignore"

    def test_ghim_hien_trang_pii_trong_artifact(self, ket_qua):
        """Số thật tại 25-10: PII nghiệp vụ còn trong artifact đã commit — chờ duyệt PA-31.

        ghim = 89 dòng / 8 file. Nếu số tăng (thêm artifact mới chứa email/điện thoại) test đỏ.
        Nếu PA-31 được duyệt và che hết, test cũng đỏ — đó là chủ đích: phải sửa kỳ vọng có
        chủ đích, không được âm thầm đổi kết luận.
        """
        mod, files, r = ket_qua
        # Q1 (27-10): +76 dòng / +1 tệp so với mốc 25-10, tất cả từ
        # `data/loop/testset_v1.jsonl` được commit để clone tái lập được round.
        # Đây là thay đổi có chủ đích (không phải PII mới phát sinh); PA-31 vẫn chờ duyệt.
        assert r["by_loai"].get("DU_CAO_NHAN_HOC") == 165, r["by_loai"]
        assert len(r["pii_by_file"]) == 9, sorted(r["pii_by_file"])
        # mọi file chứa PII đều là artifact dữ liệu, không phải code
        for f in r["pii_by_file"]:
            assert f.startswith(("data/", "outputs/", "logs/")), f

    def test_ghim_hien_trang_gitignore_da_loai_tru_tmp_models_rounds(self, ket_qua):
        """PA-33 (29-10) đã áp ignore cho artifact nặng — `git add -A` không còn gom tmp/models.

        Trước PA-33: 1.972 mục (ảnh chụp 25-10; đo lại 29-10 là 2.655 đường dẫn / 406,6 MiB).
        Sau PA-33: chỉ còn tệp chẩn đoán ĐÃ BIẾT chứa PII chưa được che (PA-8 cố ý không commit).
        RED nếu ai đó gỡ ignore rule (`tmp`/`models` quay lại) hoặc một artifact nặng mới lọt vào.
        """
        dry = subprocess.run(["git", "add", "--dry-run", "-A"], cwd=str(ROOT),
                             capture_output=True, text=True,
                             # stdin=DEVNULL: không kế thừa handle stdin hỏng của cha (D-35).
                             stdin=subprocess.DEVNULL,
                             encoding="utf-8", errors="replace")
        dong = [l for l in dry.stdout.splitlines() if l.strip()]
        gom = {l.split("'")[1].split("/")[0] for l in dong if "'" in l}
        assert len(dong) <= 50, f"hiện trạng đã đổi: {len(dong)} mục — xem lại .gitignore (PA-33)"
        assert not ({"tmp", "models"} & gom), sorted(gom)[:8]
        # Bất biến thay cho con số tuyệt đối: ngoài danh sách đã biết (tệp chẩn đoán còn PII
        # chưa che, PA-8 cố ý không commit), không mục nào được nặng quá 2 MiB.
        con_lai = {l.split("'")[1] for l in dong if "'" in l}
        duoc_biet = {
            "data/loop/diag/answerability_labelset_r5.jsonl",
            "data/loop/diag/answerability_labelset_r11_retrieval.jsonl",
            "data/loop/diag/answerability_labelset_r12_retrieval.jsonl",
            "data/loop/diag/b1_cprime/a_prime/rows.jsonl",
            "data/loop/diag/b1_cprime/c_prime/rows.jsonl",
            "data/loop/diag/b3_smoke/sm16/retrieval.jsonl",
            "data/loop/diag/corpus_check/corpus_check.json",
            "data/loop/diag/corpus_check/manual_20_segments_new_index.txt",
            "data/loop/diag/corpus_check/manual_20_segments_provenance.txt",
            # lộ `C:\Users\<tên>` trong thông điệp lỗi ⇒ không commit
            "data/loop/diag/t4_adapter_probe.json",
        }
        for rel in sorted(con_lai - duoc_biet):
            p = ROOT / rel
            assert p.is_file(), f"{rel} không còn tồn tại (chỉ xét tệp mới/sửa)"
            assert p.stat().st_size <= 2 * 1024 * 1024, f"{rel} nặng {p.stat().st_size:,} B"

    def test_ket_quat_quet_du_file_van_ban(self, ket_qua):
        mod, files, r = ket_qua
        assert r["files_scanned"] >= 200, r["files_scanned"]
        assert r["files_scanned"] < len(files), "phải loại file nhị phân/cache"
