"""Nghiệm thu cuối, mục 7 (D-35 stdin + D-36 console) — máy kiểm không được **suy diễn từ lỗi môi trường**.

Chuyện đã xảy ra thật sau commit `c508876`: chạy `pytest tests/test_final_*.py` bằng Python
hệ thống 3.14 với stdin đã đóng (`… < /dev/null`) làm `subprocess.run([...], capture_output=True)`
văng `OSError: [WinError 6] The handle is invalid`. Hệ quả quan sát được:

* `council_kit.git_state()` trả `khong-co-git` cho `src/text_utils.py` — một file **đã tracked và
  sạch**: công cụ suy diễn "repo không có git" từ một lỗi spawn, đúng kiểu sai lầm mà câu hỏi 2
  ("trọng tài có đáng tin không") sinh ra để bắt;
* fixture của `tests/test_final_secret_scan.py` chết ở `tracked_files("tracked")` — 6 test ERROR.

Dưới `venv/Scripts/python.exe` (interpreter đã dùng để đo mọi số công bố) bộ test vẫn xanh, nên đây
không phải lỗi logic mà là **độ mong manh của công cụ đo**. Hai lớp siết, cả hai tất định:

* `TestGhimNguon` — bằng AST, mọi lời gọi `subprocess.run/Popen/check_*` trong phạm vi nghiệm thu
  cuối phải truyền `stdin=` (theo khuôn `docs_consistency_check.py` đã dùng từ đợt T7), kèm test
  chống-rỗng để không "xanh vì không tìm thấy lời gọi nào".
* `TestGhiNhanCuaGitState` — thay `council_kit.subprocess` bằng bản giả để buộc từng nhánh nhãn:
  lỗi spawn ở lời gọi thứ hai không được âm thầm crash, và lỗi spawn KHÔNG được biến thành
  `tracked-sach`/`chua-commit`.
* `TestHienTrangDungCuDo` — ghim bằng chứng thật của ba file dụng cụ đo (PA-26) và số file mà
  `secret_scan` đọc được.

Lớp thứ tư, **D-36**, không phải chuyện stdin mà là chuyện bảng mã: `tools/diag/council_check_gold6.py`
in dòng chứa `ĐẠT — 0,5186`; trên console Windows (máy đo dùng **cp1258** — `chcp` 1258) `print` văng
`UnicodeEncodeError` và script trả **exit code 1**, tức người tái lập thấy "máy kiểm FAILED" dù phép đo
hoàn toàn đúng (`TestMayInKhongChiuLoiConsole`: điều khiển âm + ghim khối reconfigure UTF-8 + chạy thật
process con bị nén bảng mã).

Không mạng, không Gemini, không model; chỉ ghi vào `tmp_path` (thực ra không cần ghi gì).
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KITPATH = ROOT / "tools" / "diag" / "council_kit.py"
SCANPATH = ROOT / "tools" / "diag" / "secret_scan.py"

#: Phạm vi nghiệm thu cuối: các máy kiểm chỉ-đọc + hai bộ test trực tiếp gọi subprocess.
PHAM_VI = [
    "tools/diag/council_kit.py",
    "tools/diag/secret_scan.py",
    "tools/diag/final_number_audit.py",
    "tools/diag/env_flag_audit.py",
    "tools/diag/train_data_audit.py",
    "tools/diag/docs_consistency_check.py",
    "tests/test_final_secret_scan.py",
    "tests/test_final_env_flag_defaults.py",
]

TEN_LOI_GOI = {"run", "Popen", "check_output", "check_call"}
NHAN_HOP_LE = {"tracked-sach", "tracked-ban", "chua-commit", "thieu-file", "khong-co-git"}


def _nap(path: Path, ten: str):
    spec = importlib.util.spec_from_file_location(ten, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[ten] = mod
    spec.loader.exec_module(mod)
    return mod


def _loi_goi_subprocess(rel: str) -> list[tuple[str, bool]]:
    """Mọi lời gọi `subprocess.<X>()` trong file: `(tên hàm, có truyền stdin hay không)`."""
    src = (ROOT / rel).read_text(encoding="utf-8")
    ket_qua: list[tuple[str, bool]] = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Attribute) and f.attr in TEN_LOI_GOI
                and isinstance(f.value, ast.Name) and f.value.id == "subprocess"):
            ket_qua.append((f.attr, any(k.arg == "stdin" for k in node.keywords)))
    return sorted(ket_qua)


def _gan_subprocess_gia(monkeypatch, kit, *, loi_o_lan: int | None = None,
                        rc_dau: int = 0, rc_sau: int = 0, stdout_sau: str = ""):
    """Thay `kit.subprocess`: gọi 1 = `git ls-files`, gọi 2 = `git status --porcelain`."""
    calls: list[tuple[list, dict]] = []

    class Gia:
        DEVNULL = subprocess.DEVNULL

        @staticmethod
        def run(argv, **kw):
            calls.append((list(argv), dict(kw)))
            if loi_o_lan is not None and len(calls) == loi_o_lan:
                raise OSError(22, "The handle is invalid")
            lan = len(calls)
            return type("R", (), {
                "returncode": rc_dau if lan == 1 else rc_sau,
                "stdout": "" if lan == 1 else stdout_sau,
            })()

    monkeypatch.setattr(kit, "subprocess", Gia)
    return calls


# ------------------------------------------------------------------ 1. ghim nguồn (AST)
class TestGhimNguon:
    @pytest.mark.parametrize("rel", PHAM_VI)
    def test_khong_co_loi_goi_subprocess_thieu_stdin(self, rel):
        thieu = [ten for ten, co_stdin in _loi_goi_subprocess(rel) if not co_stdin]
        assert not thieu, (
            f"{rel}: {len(thieu)} lời gọi subprocess không truyền stdin {sorted(set(thieu))} — "
            "sẽ văng WinError 6 khi chạy test với stdin đóng (D-35)")

    def test_pham_vi_khong_bi_lam_trong(self):
        """Chống 'xanh vì không thấy gì': phải đếm được >= 8 lời gọi trong phạm vi."""
        so_luong = sum(len(_loi_goi_subprocess(r)) for r in PHAM_VI)
        assert so_luong >= 8, f"chỉ thấy {so_luong} lời gọi — phạm vi hoặc tên hàm đã bị đổi?"

    def test_dinh_vi_dung_file(self):
        """Mutation không lọt nhờ xoá cả lời gọi: số lời gọi mỗi file là con số đã ghim.

        council_kit.py: 2 -> 3 từ B2 (25-10) — thêm lời gọi helper subprocess chấm lại
        round trên cây snapshot v1; lời gọi mới cũng phải mang `stdin=DEVNULL` và đã
        nằm trong vòng kiểm tra của `test_khong_co_loi_goi_subprocess_thieu_stdin`.
        """
        dem = {r: len(_loi_goi_subprocess(r)) for r in PHAM_VI}
        assert dem["tools/diag/council_kit.py"] == 3, dem
        assert dem["tools/diag/final_number_audit.py"] == 1, dem
        assert dem["tools/diag/secret_scan.py"] == 1, dem
        assert dem["tools/diag/docs_consistency_check.py"] == 1, dem
        assert dem["tests/test_final_secret_scan.py"] == 2, dem
        assert dem["tests/test_final_env_flag_defaults.py"] == 1, dem

    def test_khuon_mau_co_truoc_tu_dot_T7(self):
        """`docs_consistency_check.py` đã truyền DEVNULL từ đợt T7 — đây là khuôn có trước, không phải phát minh mới."""
        src = (ROOT / "tools" / "diag" / "docs_consistency_check.py").read_text(encoding="utf-8")
        assert "stdin=subprocess.DEVNULL" in src


# ------------------------------------------------------ 2. nhãn git_state với subprocess giả
class TestGhiNhanCuaGitState:
    def test_git_chay_duoc_va_status_sach_thu_tracked_sach(self, monkeypatch):
        kit = _nap(KITPATH, "kit_stdin_1")
        _gan_subprocess_gia(monkeypatch, kit, rc_dau=0, rc_sau=0)
        assert kit.git_state("src/text_utils.py") == "tracked-sach"

    def test_status_co_duong_dan_thu_tracked_ban(self, monkeypatch):
        kit = _nap(KITPATH, "kit_stdin_2")
        _gan_subprocess_gia(monkeypatch, kit, rc_dau=0, rc_sau=0,
                            stdout_sau=" M src/text_utils.py\n")
        assert kit.git_state("src/text_utils.py") == "tracked-ban"

    def test_loi_spawn_o_loi_goi_thu_hai_khong_duoc_crash(self, monkeypatch):
        """Bản trước D-35 đặt `git status` NGOÀI `try` => văng exception, không có nhãn nào."""
        kit = _nap(KITPATH, "kit_stdin_3")
        calls = _gan_subprocess_gia(monkeypatch, kit, loi_o_lan=2, rc_dau=0)
        assert kit.git_state("src/text_utils.py") == "khong-co-git"
        assert len(calls) == 2, calls

    def test_loi_spawn_khong_duoc_bao_tracked_sach(self, monkeypatch):
        """Suy diễn nguy hiểm nhất: git không chạy được mà vẫn báo 'không đổi so với HEAD'."""
        kit = _nap(KITPATH, "kit_stdin_4")
        _gan_subprocess_gia(monkeypatch, kit, loi_o_lan=1)
        nhan = kit.git_state("src/text_utils.py")
        assert nhan == "khong-co-git"
        assert nhan not in {"tracked-sach", "tracked-ban", "chua-commit"}

    def test_ls_files_bao_khong_phai_thu_chua_commit(self, monkeypatch):
        kit = _nap(KITPATH, "kit_stdin_5")
        _gan_subprocess_gia(monkeypatch, kit, rc_dau=1)
        assert kit.git_state("src/answer_guard.py") == "chua-commit"

    def test_thieu_file_khong_go_subprocess(self, monkeypatch):
        kit = _nap(KITPATH, "kit_stdin_6")
        calls = _gan_subprocess_gia(monkeypatch, kit)
        assert kit.git_state(ROOT / "khong-ton-tai-trong-repo.py") == "thieu-file"
        assert calls == [], "file không tồn tại thì không được gọi git"

    def test_moi_nhan_deu_nam_trong_bang_nhan_hop_le(self, monkeypatch):
        kit = _nap(KITPATH, "kit_stdin_7")
        _gan_subprocess_gia(monkeypatch, kit, rc_dau=0, rc_sau=0)
        assert kit.git_state("src/text_utils.py") in NHAN_HOP_LE
        _gan_subprocess_gia(monkeypatch, kit, loi_o_lan=1)
        assert kit.git_state("src/text_utils.py") in NHAN_HOP_LE


# ------------------------------------------- 3. bằng chứng thật: dụng cụ đo không bị mislabel
class TestHienTrangDungCuDo:
    def test_ba_file_dung_cu_do_khong_bi_bao_khong_co_git(self):
        """Máy có git thật: không file nào trong ba file dụng cụ đo được nhãn `khong-co-git`."""
        kit = _nap(KITPATH, "kit_stdin_that")
        nhan = {f: kit.git_state(f) for f in
                ["tools/loop/verify.py", "src/answer_guard.py", "src/text_utils.py"]}
        assert set(nhan.values()) <= NHAN_HOP_LE, nhan
        assert "khong-co-git" not in nhan.values(), nhan

    def test_ghim_hien_trang_pa_26(self):
        """Q1 27-10: PA-42(a) đã duyệt => cả ba file dụng cụ đo đã vào git, sạch."""
        kit = _nap(KITPATH, "kit_stdin_that2")
        assert kit.git_state("src/text_utils.py") == "tracked-sach"
        assert kit.git_state("tools/loop/verify.py") == "tracked-sach"
        assert kit.git_state("src/answer_guard.py") == "tracked-sach"

    def test_secret_scan_doc_du_file_du_oc_cua_stdin(self):
        """`tracked_files('tracked')` phải trả danh sách thật — không im lặng trả rỗng."""
        mod = _nap(SCANPATH, "secret_scan_stdin")
        files = mod.tracked_files("tracked")
        assert len(files) > 200, len(files)
        assert "src/text_utils.py" in files


# ------------------------------------------------ 4. máy in không chịu nổi lỗi console (D-36)
BAO_STDOUT = "reconfigure(encoding=\"utf-8\", errors=\"replace\")"
MAY_KIEM = [
    "tools/diag/council_check_fabrication.py",
    "tools/diag/council_check_referee.py",
    "tools/diag/council_check_gold6.py",
    "tools/diag/env_flag_audit.py",
    "tools/diag/secret_scan.py",
    "tools/diag/train_data_audit.py",
    "tools/diag/final_number_audit.py",
]


def _con(nen_console: bool, lenh: list[str], env_extra: dict | None = None, *,
         bang_ma: str = "cp1252"):
    """Chạy một process Python con; nếu `nen_console` thì **nén** stdout/stderr về `bang_ma`.

    `bang_ma` mặc định là cp1252 vì nó tất định (mọi máy Windows đều có), nhưng hiểm hoạ THẬT
    trên máy đo là **cp1258** — `chcp` = 1258 và `locale.getpreferredencoding()` = cp1258
    (bằng chứng: `tmp/probe_no_utf8.txt`, traceback `encodings\\cp1258.py`). Hai bảng mã này
    cùng một lớp hỏng: không mã hoá được `ệ`/` ạ` ⇒ điều khiển âm chạy trên cả hai.
    """
    nen = ("import sys\n"
           f"sys.stdout.reconfigure(encoding='{bang_ma}')\n"
           f"sys.stderr.reconfigure(encoding='{bang_ma}')\n") if nen_console else ""
    code = nen + "\n".join(lenh)
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL, env=env, timeout=600)


class TestMayInKhongChiuLoiConsole:
    """`python tools/diag/council_check_gold6.py` trên console bảng mã Windows từng chết với
    `UnicodeEncodeError` và **exit code 1** — người tái lập đọc thành "máy kiểm KHÔNG ĐẠT"
    trong khi nguyên nhân chỉ là bảng mã. Máy kiểm phải báo đúng nguyên nhân (D-36)."""

    @pytest.mark.parametrize("bang_ma", ["cp1252", "cp1258"])
    def test_nen_console_khong_in_duoc_tieng_viet_co_dau(self, bang_ma):
        """Điều khiển âm: chứng minh hiểm hoạ là THẬT trên interpreter này (không suy đoán).

        cp1252 = stand-in tất định, cp1258 = bảng mã thật của máy đo (`chcp` 1258).
        Nếu một ngày Python mặc định in UTF-8 trên Windows, test này đỏ và khối guard
        phía dưới trở nên thừa — lúc đó phải bỏ guard **có chủ đích**, không âm thầm.
        """
        r = _con(True, ["print('ĐẠT — 0,5186 câu, chữ ký 9f1179ccab74')"], bang_ma=bang_ma)
        assert r.returncode != 0, (bang_ma, r.stdout)
        assert "UnicodeEncodeError" in (r.stderr or ""), (bang_ma, r.returncode, r.stderr[:300])
        assert bang_ma in (r.stderr or ""), f"traceback không nêu {bang_ma}: nghi ngờ nén nhầm chỗ"

    @pytest.mark.parametrize("rel", MAY_KIEM)
    def test_khoi_bao_stdout_co_don(self, rel):
        """Mỗi máy kiểm phải tự đặt UTF-8 **trước** `def main` (lúc import) và bọc trong `try`."""
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert BAO_STDOUT in src, f"{rel}: không thấy khối reconfigure UTF-8"
        assert src.index(BAO_STDOUT) < src.index("def main("), f"{rel}: khối đặt quá trễ"
        assert "except Exception" in src[: src.index("def main(")], f"{rel}: reconfigure không được bọc try"

    @pytest.mark.parametrize("rel,rc_ky_vong", [
        ("tools/diag/council_check_fabrication.py", 0),
        ("tools/diag/council_check_gold6.py", 0),
        ("tools/diag/council_check_referee.py", 0),
        ("tools/diag/secret_scan.py", 0),
    ])
    def test_ep_bang_console_cp1252_van_in_va_thoat_dung_ma(self, rel, rc_ky_vong):
        """Ép console về cp1252 rồi chạy thật: phải in được và trả đúng mã phán quyết."""
        lenh = [
            "import importlib.util as u, sys",
            f"spec = u.spec_from_file_location('tool', r'{ROOT / rel}')",
            "m = u.module_from_spec(spec); spec.loader.exec_module(m)",
            "raise SystemExit(m.main([]))",
        ]
        r = _con(True, lenh)
        assert "UnicodeEncodeError" not in (r.stderr or ""), (rel, (r.stderr or "")[-400:])
        assert r.returncode == rc_ky_vong, (rel, r.returncode, (r.stderr or "")[-400:])
        assert "CÂU HỎI" in r.stdout or "secret-scan" in r.stdout, (rel, r.stdout[:200])

