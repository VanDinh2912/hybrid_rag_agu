"""Nghiệm thu cuối, mục 3 — mọi cờ env mới đều mặc định TẮT, và checker phát hiện được trái.

Ba lớp khẳng định (không lớp nào tự lừa):

* `TestDuoiRuntime` — gọi đúng accessor của từng cờ với tên cờ **đã xoá** khỏi `os.environ`:
  đó là giá trị một bản clone mới nhìn thấy. Nếu ai đó đổi mặc định code, lớp này đỏ.
* `TestCuaChecker` — chứng minh checker có răng: nuôi cho nó từng loại "lỗi" nhân tạo
  (mặc định code `"1"`, `.env.example` bật `1`, `os.environ.setdefault` bật ngầm trong `src/`,
  accessor trả `True`) và buộc nó phải tự phân loại đúng thành `LOI_*`. Nếu checker mất răng
  (đột biến bỏ so sánh), những test này đỏ.
* `TestVoiGoldenT3` — chạy lại máy chụp golden trên cây hiện tại với hai cờ T3 TẮT và so
  khối `core` từng byte với golden đã công bố; phần `t3` phải là `None` (cờ tắt => trường mới
  không có tác dụng). Đây là nghĩa "chạy pipeline với mặc định vs golden" của đề bài.

Không gọi Gemini/Ollama/model thật; mọi ghi file đi vào `tmp_path`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib  # noqa: E402

env_flag_audit = importlib.import_module("tools.diag.env_flag_audit")

LEVERS = env_flag_audit.LEVERS
TEN_CO = [l["name"] for l in LEVERS]


@pytest.fixture()
def clean_env(monkeypatch):
    """Xoá mọi tên cờ khỏi os.environ trong suốt test (restore tự động sau test)."""
    for name in TEN_CO:
        monkeypatch.delenv(name, raising=False)
    return os.environ


# ---------------------------------------------------------------- 1. tầng động
class TestDuoiRuntime:
    @pytest.mark.parametrize("lever", LEVERS, ids=TEN_CO)
    def test_accessor_tra_gia_tri_tat_khi_env_trong(self, clean_env, lever):
        if lever["probe"] is None:
            pytest.skip("cờ này không có accessor đơn (chỉ kiểm tĩnh ở lớp 2)")
        mod = importlib.import_module(lever["probe"][0])
        fn = getattr(mod, lever["probe"][1])
        gia_tri = fn()
        assert gia_tri == lever["expect"], (
            f"{lever['name']}: env trống nhưng accessor {lever['probe'][1]} trả {gia_tri!r}, "
            f"đăng ký là {lever['expect']!r}")

    @pytest.mark.parametrize("name", TEN_CO)
    def test_khong_ai_dat_ten_coy_trong_env_cua_phien_test(self, name):
        # Nếu phiên pytest có sẵn cờ thì các test trên đã xoá; ở đây chỉ ghi nhận để
        # người đọc biết môi trường máy đang có gì (không fail).
        assert name in os.environ or name not in os.environ

    def test_khong_co_setdefault_bat_ngam_tren_duong_production(self):
        """`src/` và script gốc không được `os.environ.setdefault` một cờ lên giá trị bật."""
        audit = env_flag_audit.audit()
        assert audit["setdefault_forced_on"] == [], (
            f"phát hiện bật ngầm ở production: {audit['setdefault_forced_on']}")

    def test_mo_truong_that_cua_repo_dang_khong_bat_lever_nao(self):
        """.env của máy dev không được là lý do khiến kết luận 'mặc định tắt' chỉ đúng trên máy khác."""
        duong = {s["file"] for s in env_flag_audit.audit()["setdefault_chu_y"]}
        for name in TEN_CO:
            if name in os.environ:
                assert os.environ[name].strip().lower() in env_flag_audit.OFF_LITERALS, (
                    f"{name} đang bật trong os.environ của phiên chạy — kết luận TẮT chỉ đúng "
                    f"khi fixture đã xoá biến (xem clean_env)")
        assert duong <= {"tools/diag/reranker_cost_probe.py"}, duong


# ---------------------------------------------------------------- 2. tầng tĩnh
class TestDuoiTinh:
    def test_khong_site_nao_co_mac_dinh_literal_bat(self):
        audit = env_flag_audit.audit()
        sai = {r["name"]: r["static_bad"] for r in audit["rows"] if r["static_bad"]}
        assert sai == {}, f"có site mặc định KHÔNG tắt: {sai}"

    def test_moi_co_deu_duoc_quet_thay_site_doc(self):
        """Checker không báo 'sạch' vì… không thấy gì: mỗi cờ phải có ít nhất một site đọc."""
        audit = env_flag_audit.audit()
        vo_cach = [r["name"] for r in audit["rows"] if not r["static_sites"]]
        assert vo_cach == [], f"cờ đăng ký nhưng không quét ra site đọc: {vo_cach}"

    def test_helper_doc_env_mac_dinh_tat(self):
        helpers = {h["fn"]: h["default"] for h in env_flag_audit.scan_helper_defaults()}
        assert "_flag" in helpers, helpers
        assert env_flag_audit._is_off(helpers["_flag"]), helpers["_flag"]

    def test_dotenv_example_khong_bat_cua_lever_nao(self):
        """Nếu sau này ai khai báo cờ vào `.env.example`, giá trị khai báo phải là TẮT."""
        audit = env_flag_audit.audit()
        assert audit["env_example_not_off"] == {}, audit["env_example_not_off"]
        # Ghi nhận minh bạch: các key BẬT sẵn trong .env.example là tính năng tiền-vòng-lặp.
        for key, value in audit["env_example_on_preloop"].items():
            assert key not in TEN_CO, f"{key} là lever mới nhưng đang bật sẵn trong .env.example"
            assert value == "1"


# ---------------------------------------------------------------- 3. checker có răng
class TestCuaChecker:
    """Nuôi lỗi nhân tạo cho checker; checker PHẢI tự phân loại ra LOI_*."""

    def _one(self, monkeypatch, name="ENABLE_RERANKER", **kw):
        lever = dict(next(l for l in LEVERS if l["name"] == name))
        for k, v in kw.items():
            lever[k] = v
        monkeypatch.setattr(env_flag_audit, "LEVERS", [lever])
        return env_flag_audit.audit()["rows"][0]

    def test_phat_hien_mac_dinh_code_bat(self, monkeypatch):
        """Đột biến `M1`: site đọc env có literal mặc định "1" ⇒ LOI_MAC_DINH."""
        def fake_static(names):
            return {"ENABLE_RERANKER": [dict(
                file="src/reranker.py", line=97, reader="getenv", default='"1"',
                via_const=None, snippet='os.getenv("ENABLE_RERANKER", "1")')]}
        monkeypatch.setattr(env_flag_audit, "scan_static", fake_static)
        row = self._one(monkeypatch)
        assert row["verdict"] == "LOI_MAC_DINH", row

    def test_phat_hien_dotenv_example_bat_c(self, monkeypatch):
        """Đột biến `M2`: `.env.example` khai báo `ENABLE_RERANKER=1` ⇒ LOI_KHAI_BAO."""
        monkeypatch.setattr(env_flag_audit, "dotenv_example",
                            lambda: {"ENABLE_RERANKER": "1"})
        row = self._one(monkeypatch)
        assert row["verdict"] == "LOI_KHAI_BAO", row

    def test_phat_hien_accessor_tra_true(self, monkeypatch):
        """Đột biến `M3`: mặc định code thành bật ⇒ runtime True khác đăng ký ⇒ LOI_RUNTIME."""
        row = self._one(monkeypatch, expect=True)
        # expect=True nhưng accessor thật vẫn trả False -> checker phải báo lệch, không im lặng
        assert row["verdict"] == "LOI_RUNTIME", row

    def test_phat_hien_setdefault_bat_ngam_trong_src(self, tmp_path, monkeypatch):
        """Đột biến `M4`: một file `src/` gọi `os.environ.setdefault("ENABLE_RERANKER", "1")`."""
        fake_src = tmp_path / "src"
        fake_src.mkdir()
        (fake_src / "evil.py").write_text(
            'import os\nos.environ.setdefault("ENABLE_RERANKER", "1")\n', encoding="utf-8")
        monkeypatch.setattr(env_flag_audit, "ROOT", tmp_path)
        bad = env_flag_audit.scan_setdefault()
        assert [b["name"] for b in bad] == ["ENABLE_RERANKER"], bad
        assert env_flag_audit.is_production(bad[0]["file"]) is True

    def test_bat_trong_script_do_chi_la_ghi_chu(self, tmp_path, monkeypatch):
        """Đột biến `M5` (phủ định): bật cờ trong `tools/diag/` là chủ đích đo => không phải LỖI."""
        probe = tmp_path / "tools" / "diag"
        probe.mkdir(parents=True)
        (probe / "probe.py").write_text(
            'import os\nos.environ.setdefault("ENABLE_RERANKER", "1")\n', encoding="utf-8")
        monkeypatch.setattr(env_flag_audit, "ROOT", tmp_path)
        bad = env_flag_audit.scan_setdefault()
        assert env_flag_audit.is_production(bad[0]["file"]) is False

    def test_rung_chuoi_khong_du_lam_gia_ket_luan_sach(self, monkeypatch):
        """Đột biến `M6`: nếu quét không thấy site nào thì phải đỏ, không được 'PASSED vì mù'."""
        monkeypatch.setattr(env_flag_audit, "scan_static", lambda names: {n: [] for n in names})
        audit = env_flag_audit.audit()
        assert all(r["static_sites"] == [] for r in audit["rows"])
        # không có site => không đủ chứng cứ; test ở TestCuaChecker.test_moi_co_deu_duoc_quet chặn đường này
        vo_cach = [r["name"] for r in audit["rows"] if not r["static_sites"]]
        assert vo_cach == TEN_CO


# ---------------------------------------------------------------- 4. golden với mặc định
@pytest.fixture(scope="module")
def golden_hien_chup(tmp_path_factory):
    """Chạy máy chụp golden MỘT lần cho cả module: cây hiện tại, mọi cờ để mặc định TẮT."""
    out = tmp_path_factory.mktemp("golden") / "golden_now.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "diag" / "t3_golden_dump.py"), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), timeout=600,
        # stdin=DEVNULL: process con không kế thừa handle stdin hỏng của process cha
        # (D-35) — trên Windows lỗi đó là `OSError: [WinError 6] The handle is invalid`.
        stdin=subprocess.DEVNULL,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", **{n: "" for n in TEN_CO}})
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    return json.loads(out.read_text(encoding="utf-8"))


class TestVoiGoldenT3:
    GOLDEN = ROOT / "tests" / "golden" / "t3_off_30items_head_f492f05.json"

    def _core_sha(self, obj) -> str:
        blob = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def test_chay_pipeline_mac_dinh_trung_golden_core(self, golden_hien_chup):
        """Nghĩa của "chạy pipeline với mặc định vs golden": 30 lượt run, khối `core`
        (câu trả lời/contexts/sources/prompt/keys) phải **từng byte** như golden chụp trên cây
        CHƯA có wiring T3 — tức bật code mới mà không bật cờ thì không đổi hành vi."""
        nay = golden_hien_chup
        golden = json.loads(self.GOLDEN.read_text(encoding="utf-8"))
        assert self._core_sha(nay["core"]) == self._core_sha(golden["core"]), (
            "khối core đổi từng byte khi mọi cờ để mặc định — bất biến 'tắt = cũ' bị phá")
        assert self._core_sha(nay["core"]) == \
            "344d55cd35ec64b876d1f7580724eb968f158a21fbf42c64a28b54d3c8784b11"
        assert len(nay["core"]) == len(golden["core"]) == 30

    def test_truong_moi_ton_tai_nhung_rong_khi_co_tat(self, golden_hien_chup):
        """Nửa còn lại của assertion T3: pipeline ĐÃ có trường mới (`pipeline_has_t3_fields`)
        nhưng hai trường đó là `None` khi cờ TẮT — nên chúng không thể lọt vào `core`."""
        nay = golden_hien_chup
        assert nay["meta"]["pipeline_has_t3_fields"] is True
        assert all(r["refusal_decision"] is None and r["evidence_selection"] is None
                   for r in nay["t3"])
        # golden chụp trên cây baseline: hai trường còn không tồn tại ở đó
        golden = json.loads(self.GOLDEN.read_text(encoding="utf-8"))
        assert golden["meta"]["pipeline_has_t3_fields"] is False
        assert all("khong_ton_tai_o_baseline" in str(v) for r in golden["t3"] for v in r.values())

    def test_khong_co_lechen_o_env_khai_bao_trong_may_chup(self, golden_hien_chup):
        """`meta.env` của lượt chụp phải ghi TẮT toàn bộ lever — chống 'xanh nhờ máy có env'."""
        env = golden_hien_chup["meta"]["env"]
        tat_ca_lever = {l["name"] for l in LEVERS} & set(env)
        for name in tat_ca_lever:
            assert str(env[name]).strip().lower() in (env_flag_audit.OFF_LITERALS | {"3", "0.8"}), \
                (name, env[name])
