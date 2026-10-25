# -*- coding: utf-8 -*-
"""Test T7 — mục 1–2 đề bài: driver chuỗi round (`tools/loop/run_chain.py`).

Ba điều đề bài nêu phải **đo** được, không phải mô tả:

1. `--dry-run` in **đúng chuỗi lệnh + đúng env của TỪNG round** và không chạy gì (stub subprocess
   không nhận cuộc gọi nào). Env phải theo thứ tự ưu tiên đã đăng ký:
   `defaults cấp chuỗi < defaults cấp bước < env cấp bước < --set`.
2. **Thiếu biến bắt buộc ⇒ dừng sớm kèm thông báo**, kể cả biến bắt buộc *của một bước ở giữa chuỗi*
   (preflight phải nhìn xuyên suốt, không để chạy nửa chuỗi rồi mới chết).
3. **Hai lần chạy trên cùng dữ liệu mẫu nhỏ ⇒ cùng một manifest** (từng byte), và manifest **nói
   đúng** cái đã được export cho tiến trình con — manifest không được là "bản quảng cáo".
4. Round mới luôn vào **thư mục mới** `<out_root>/<round>`; thư mục đã có dữ liệu ⇒ **từ chối, không
   ghi đè** (file cũ còn nguyên bytes); `--resume` mới được đi tiếp; thư mục rỗng thì cho phép.

Toàn bộ test thay `subprocess.run` bằng stub — không chạy model, không gọi Gemini/Ollama, không ghi
`data/loop/rounds/` thật.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools.loop import run_chain as rc

ROOT = Path(__file__).resolve().parents[1]


class RecordingStub:
    """Thay `subprocess.run`: ghi argv + env đã nhận, không chạy gì, có thể tạo báo cáo cổng."""

    def __init__(self, *, gate_rc: int = 0, make_gate_report: bool = False, touch_round: bool = False):
        self.calls: list[dict] = []
        self.gate_rc = gate_rc
        self.make_gate_report = make_gate_report
        self.touch_round = touch_round

    def __call__(self, argv, cwd=None, env=None, **kwargs):
        self.calls.append({"argv": [str(a) for a in argv], "env": dict(env or {}), "cwd": str(cwd)})
        if self.touch_round and "run_round.py" in " ".join(map(str, argv)):
            root = Path(str(argv[argv.index("--out-root") + 1]))
            rnd = root / str(argv[argv.index("--round") + 1])
            rnd.mkdir(parents=True, exist_ok=True)
            (rnd / "retrieval.jsonl").write_text('{"id": "L1"}\n', encoding="utf-8")

        class _P:
            returncode = 0

        if any("gate.py" in str(a) for a in argv):
            _P.returncode = self.gate_rc
            if self.make_gate_report:
                root = Path(str(argv[argv.index("--rounds-root") + 1]))
                cand = str(argv[argv.index("--candidate") + 1])
                base = str(argv[argv.index("--baseline") + 1])
                phase = str(argv[argv.index("--phase") + 1])
                out = root / cand / f"gate_vs_{base}_{phase}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({"passed": self.gate_rc == 0}), encoding="utf-8")
        return _P()


@pytest.fixture()
def sample(tmp_path: Path) -> dict:
    """Dữ liệu mẫu nhỏ: một testset 3 câu + spec hai round có env khác nhau."""
    ts = tmp_path / "sample_testset.jsonl"
    ts.write_text(
        "\n".join(json.dumps({"id": f"L{i}", "question": f"câu {i}"}) for i in (1, 2, 3)) + "\n",
        encoding="utf-8",
    )
    out_root = tmp_path / "rounds"
    spec = {
        "name": "t7_probe",
        "out_root": str(out_root),
        "defaults": {"ENABLE_CLASSIFIER": "0", "CHAIN_VAR": "chuoi"},
        "requires": [],
        "rounds": [
            {"round": "a1", "phase": "retrieval", "testset": str(ts),
             "defaults": {"CHAIN_VAR": "buoc-mac-dinh", "STEP_DEFAULT": "co"},
             "env": {"CHAIN_VAR": "buoc-env"},
             "gate": {"baseline": "r0"}},
            {"round": "b2", "phase": "retrieval", "testset": str(ts), "env": {"ONLY_B": "1"}},
        ],
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return {"spec": spec_path, "out_root": out_root, "testset": ts, "tmp": tmp_path}


def _run(monkeypatch, stub, *argv) -> tuple[int, RecordingStub]:
    monkeypatch.setattr(rc.subprocess, "run", stub)
    monkeypatch.setattr(sys, "argv", ["run_chain.py", *argv])
    return rc.main(), stub


def round_calls(stub: RecordingStub) -> list[dict]:
    """Chỉ những cuộc gọi `run_round.py` (chuỗi còn gọi thêm gate/attribute)."""
    return [c for c in stub.calls if "run_round.py" in " ".join(c["argv"])]


# ---------------------------------------------------------------------------
# 1. dry-run: in đúng lệnh + env từng round, không chạy gì
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_khong_goi_subprocess(self, sample, monkeypatch, capsys):
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                          "--dry-run", "--no-manifest")
        assert code == 0
        assert stub.calls == []
        out = capsys.readouterr().out
        assert "DRY-RUN" in out

    def test_dry_run_in_du_lenh_va_env_cua_tung_round(self, sample, monkeypatch, capsys):
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                          "--dry-run", "--no-manifest")
        out = capsys.readouterr().out
        assert code == 0 and stub.calls == []
        for rnd in ("a1", "b2"):
            assert f"round={rnd}" in out
        # env của round a1 phải hiện đủ ba lớp, env của b2 phải có ONLY_B
        assert "CHAIN_VAR=" in out and "STEP_DEFAULT=co" in out and "ONLY_B=1" in out
        # argv phải là lệnh thiệt (tool + round + phase + out-root), không phải mô tả
        assert "tools/loop/run_round.py" in out
        assert "--round a1" in out and "--round b2" in out
        assert "gate.py" in out                     # bước chấm cũng được in ra ở dry-run

    def test_thieu_bien_bat_buoc_o_giua_chuoi_dung_truoc_buoc_dau(self, sample, monkeypatch, capsys):
        spec = json.loads(sample["spec"].read_text(encoding="utf-8"))
        spec["rounds"][1]["require"] = ["BIEN_KHONG_CO_ABC"]
        sample["spec"].write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]), "--no-manifest")
        assert code == 2
        assert stub.calls == []                     # KHÔNG chạy nửa chuỗi
        err = capsys.readouterr().err
        assert "BIEN_KHONG_CO_ABC" in err and "b2" in err

    def test_bien_bat_buoc_thoa_man_boi_env_cua_chinh_buoc(self, sample, monkeypatch):
        spec = json.loads(sample["spec"].read_text(encoding="utf-8"))
        spec["rounds"][1]["require"] = ["ONLY_B"]
        spec["rounds"][1]["env"] = {"ONLY_B": "1"}
        sample["spec"].write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]), "--no-manifest")
        assert code == 0
        assert len(round_calls(stub)) == 2

    def test_thieu_bien_cap_chuoi_dung_som(self, sample, monkeypatch, capsys):
        spec = json.loads(sample["spec"].read_text(encoding="utf-8"))
        spec["requires"] = ["THIEU_CAP_CHUOI_XYZ"]
        sample["spec"].write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        monkeypatch.delenv("THIEU_CAP_CHUOI_XYZ", raising=False)
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]), "--no-manifest")
        assert code == 2 and stub.calls == []
        assert "THIEU_CAP_CHUOI_XYZ" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 2. thứ tự ưu tiên env + manifest "nói đúng"
# ---------------------------------------------------------------------------

class TestThuTuuEnvVaManifest:
    def test_uu_tien_set_cuoi_cung_va_lop_truoc_ghi_de_lop_sau(self, sample, monkeypatch):
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                          "--set", "CHAIN_VAR=cli", "--no-manifest")
        assert code == 0
        env_a = stub.calls[0]["env"]
        assert env_a["CHAIN_VAR"] == "cli"          # --set thắng env cấp bước
        assert env_a["STEP_DEFAULT"] == "co"        # defaults cấp bước vẫn còn
        assert env_a["ENABLE_CLASSIFIER"] == "0"    # defaults cấp chuỗi vẫn còn
        assert "ONLY_B" not in env_a                # env của bước khác KHÔNG rỉ sang

    def test_the_hien_thu_mack_dinh_khong_bi_set_che(self, sample, monkeypatch):
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]), "--no-manifest")
        env_a = stub.calls[0]["env"]
        assert env_a["CHAIN_VAR"] == "buoc-env"     # env cấp bước > defaults cấp bước
        assert round_calls(stub)[1]["env"]["CHAIN_VAR"] == "chuoi"  # bước không ghi gì ⇒ mặc định cấp chuỗi

    def test_hai_lan_chay_cung_manifest_bytes(self, sample, monkeypatch, tmp_path):
        m1, m2 = tmp_path / "m1.json", tmp_path / "m2.json"
        for out in (m1, m2):
            code, _ = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                           "--dry-run", "--manifest-out", str(out))
            assert code == 0
        assert m1.read_bytes() == m2.read_bytes()

    def test_manifest_cua_chay_that_khop_dung_nhieu_dang_chay(self, sample, monkeypatch, tmp_path):
        """Manifest không được là "bản quảng cáo": argv/env ghi trong đó phải là argv/env đã export."""
        out = tmp_path / "m.json"
        stub = RecordingStub()
        code, stub = _run(monkeypatch, stub, "--chain", str(sample["spec"]),
                          "--manifest-out", str(out))
        assert code == 0
        manifest = json.loads(out.read_text(encoding="utf-8"))
        rows = manifest["steps"]
        assert [r["round"] for r in rows] == ["a1", "b2"]
        for row, call in zip(rows, round_calls(stub)):
            assert row["argv"] == call["argv"][: len(row["argv"])]
            for k, v in row["env"].items():
                assert call["env"][k] == v
        assert rows[0]["post"][0]["tool"] == "gate"
        # cổng phải đọc ĐÚNG gốc round của chuỗi (lỗi cũ: spec out_root riêng -> gate tìm ở data/loop)
        assert rows[0]["post"][0]["argv"][rows[0]["post"][0]["argv"].index("--rounds-root") + 1] == \
            str(sample["out_root"])

    def test_manifest_cua_hai_lan_chay_that_giong_nhau(self, sample, monkeypatch, tmp_path):
        """Hai lần chạy THẬT (stub) trên cùng spec + cùng dữ liệu mẫu ⇒ manifest từng byte một."""
        m1, m2 = tmp_path / "m1.json", tmp_path / "m2.json"
        for out in (m1, m2):
            code, _ = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                            "--manifest-out", str(out))
            assert code == 0
        assert m1.read_bytes() == m2.read_bytes()
        manifest = json.loads(m1.read_text(encoding="utf-8"))
        assert manifest["spec_sha256"] and manifest["chain"] == "t7_probe"

    def test_spec_sha256_doi_khi_spec_doi(self, sample, monkeypatch, tmp_path):
        out = tmp_path / "m.json"
        code, _ = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                       "--dry-run", "--manifest-out", str(out))
        first = json.loads(out.read_text(encoding="utf-8"))
        spec = json.loads(sample["spec"].read_text(encoding="utf-8"))
        spec["rounds"][0]["env"]["CHAIN_VAR"] = "khac"
        sample["spec"].write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        code, _ = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                       "--dry-run", "--manifest-out", str(out))
        second = json.loads(out.read_text(encoding="utf-8"))
        assert first["spec_sha256"] != second["spec_sha256"]
        assert first["steps"][0]["env"] != second["steps"][0]["env"]


# ---------------------------------------------------------------------------
# 3. thư mục round: mới thì ghi, đã có dữ liệu thì từ chối
# ---------------------------------------------------------------------------

class TestThuMucRound:
    def test_round_moi_vao_thu_muc_moi_duoc_truyen_xuong_argv(self, sample, monkeypatch):
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]), "--no-manifest")
        assert code == 0
        argv = stub.calls[0]["argv"]
        assert Path(argv[argv.index("--out-root") + 1]) == sample["out_root"]
        assert argv[argv.index("--round") + 1] == "a1"

    def test_thu_muc_da_co_du_lieu_bi_tu_choi_va_khong_ghi_de(self, sample, monkeypatch):
        target = sample["out_root"] / "a1"
        target.mkdir(parents=True)
        old = target / "retrieval.jsonl"
        old.write_text('{"id": "DU_CU"}\n', encoding="utf-8")
        before = old.read_bytes()
        stub = RecordingStub(touch_round=True)
        code, stub = _run(monkeypatch, stub, "--chain", str(sample["spec"]), "--no-manifest")
        assert code == 2
        assert stub.calls == []
        assert old.read_bytes() == before                  # không bị ghi đè
        assert not (sample["out_root"] / "b2").exists()     # không tạo thư mục cho bước sau

    def test_thu_muc_rong_van_duoc_chay(self, sample, monkeypatch):
        (sample["out_root"] / "a1").mkdir(parents=True)
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]), "--no-manifest")
        assert code == 0 and len(round_calls(stub)) == 2

    def test_resume_duoc_go_de_va_van_khong_xoa_du_lieu_cu(self, sample, monkeypatch):
        target = sample["out_root"] / "a1"
        target.mkdir(parents=True)
        old = target / "retrieval.jsonl"
        old.write_text('{"id": "DU_CU"}\n', encoding="utf-8")
        before = old.read_bytes()
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                          "--resume", "--no-manifest")
        assert code == 0 and len(round_calls(stub)) == 2
        assert old.read_bytes() == before

    def test_kiem_du_moi_thu_muc_truoc_buoc_dau(self, sample, monkeypatch):
        """Round thứ HAI đã có dữ liệu cũng phải bị chặn TRƯỚC khi round một chạy."""
        (sample["out_root"] / "b2").mkdir(parents=True)
        (sample["out_root"] / "b2" / "full.jsonl").write_text("{}\n", encoding="utf-8")
        code, stub = _run(monkeypatch, RecordingStub(touch_round=True), "--chain", str(sample["spec"]),
                          "--no-manifest")
        assert code == 2
        assert stub.calls == []


# ---------------------------------------------------------------------------
# 4. chốt thêm: biến bí mật trong spec (không tái lập được) bị từ chối lúc nạp
# ---------------------------------------------------------------------------

class TestChanBiMatTrongSpec:
    @pytest.mark.parametrize("block", ["defaults", "env"])
    def test_key_api_trong_spec_bi_tu_choi(self, sample, monkeypatch, block):
        spec = json.loads(sample["spec"].read_text(encoding="utf-8"))
        spec["rounds"][0][block] = {"GEMINI_API_KEY": "abc"}
        sample["spec"].write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]), "--no-manifest")
        assert code == 2 and stub.calls == []

    def test_chi_chay_mot_bang_bang_only_nhung_manifest_ghi_ca_chuoi(self, sample, monkeypatch, capsys):
        out = sample["tmp"] / "m.json"
        code, stub = _run(monkeypatch, RecordingStub(), "--chain", str(sample["spec"]),
                          "--only", "b2", "--manifest-out", str(out))
        assert code == 0
        assert len(stub.calls) == 1 and stub.calls[0]["argv"][stub.calls[0]["argv"].index("--round") + 1] == "b2"
        assert [r["round"] for r in json.loads(out.read_text(encoding="utf-8"))["steps"]] == ["a1", "b2"]
