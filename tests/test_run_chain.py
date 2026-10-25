"""Test cho `tools/loop/run_chain.py` (T7) — chạy chuỗi round bằng một lệnh.

Bảy tính chất phải giữ, tương ứng từng test bên dưới:

1. `--dry-run` in lệnh nhưng **không chạy** gì (không gọi subprocess).
2. Manifest **tất định**: cùng spec ⇒ cùng bytes; đường dẫn tương đối (không dính ổ đĩa).
3. Thiếu env bắt buộc ⇒ dừng **trước** bước đầu.
4. Thư mục round đã có dữ liệu ⇒ từ chối, không ghi đè; `--resume` mới cho đi tiếp.
5. Biến bí mật (`GEMINI_API_KEY`…) không được đi qua `--set`.
6. Spec sai (round trùng tên) ⇒ dừng.
7. Cổng trả mã 1: có báo cáo ⇒ ghi nhận rồi **đi tiếp** (kết quả âm vẫn phải được quy lỗi);
   không có báo cáo ⇒ dừng vì không đánh giá được.

Không test nào chạy model/round thật: `subprocess.run` bị thay bằng stub.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools.loop import run_chain as rc


def _spec(tmp_path: Path, *, rounds=None, requires=None, out_root=None) -> Path:
    spec = {
        "name": "t_demo",
        "out_root": str(out_root if out_root is not None else tmp_path / "rounds"),
        "defaults": {"ENABLE_CLASSIFIER": "0"},
        "requires": requires or [],
        "rounds": rounds or [{"round": "rx", "phase": "retrieval"}],
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return path


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["run_chain.py", *argv])
    return rc.main()


class _Stub:
    """Thay `subprocess.run`: ghi lại argv, không chạy gì; tuỳ chọn tạo file báo cáo cổng."""

    def __init__(self, create_gate_report: bool = False, gate_rc: int = 0):
        self.calls: list[list[str]] = []
        self.create_gate_report = create_gate_report
        self.gate_rc = gate_rc

    def __call__(self, argv, cwd=None, env=None, **kwargs):
        self.calls.append(list(argv))

        class _P:
            returncode = 0

        if any("gate.py" in a for a in argv):
            _P.returncode = self.gate_rc
            if self.create_gate_report and "--out" not in argv:
                root = Path(argv[argv.index("--rounds-root") + 1])
                cand = argv[argv.index("--candidate") + 1]
                base = argv[argv.index("--baseline") + 1]
                phase = argv[argv.index("--phase") + 1]
                out = root / cand / f"gate_vs_{base}_{phase}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({"passed": self.gate_rc == 0}), encoding="utf-8")
        return _P()


def test_run_chain_dry_run_never_calls_subprocess(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    stub = _Stub()
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--dry-run", "--manifest-out", str(tmp_path / "m.json"))
    assert code == 0
    assert stub.calls == []
    assert (tmp_path / "m.json").exists()


def test_run_chain_manifest_is_deterministic_and_relative(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    stub = _Stub()
    monkeypatch.setattr(rc.subprocess, "run", stub)
    a, b = tmp_path / "m1.json", tmp_path / "m2.json"
    assert _run(monkeypatch, "--chain", str(spec), "--dry-run", "--manifest-out", str(a)) == 0
    assert _run(monkeypatch, "--chain", str(spec), "--dry-run", "--manifest-out", str(b)) == 0
    assert a.read_bytes() == b.read_bytes()
    text = a.read_text(encoding="utf-8")
    assert "D:\\\\" not in text and "/mnt/" not in text
    manifest = json.loads(text)
    assert manifest["steps"][0]["round"] == "rx"
    assert manifest["steps"][0]["argv"][1] == "tools/loop/run_round.py"


def test_run_chain_missing_required_env_stops_before_first_step(tmp_path, monkeypatch):
    spec = _spec(tmp_path, requires=["KHONG_CO_BIEN_NAY_XYZ"])
    monkeypatch.delenv("KHONG_CO_BIEN_NAY_XYZ", raising=False)
    stub = _Stub()
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--no-manifest")
    assert code == 2
    assert stub.calls == []


def test_run_chain_refuses_existing_round_dir_without_resume(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    target = tmp_path / "rounds" / "rx"
    target.mkdir(parents=True)
    (target / "retrieval.jsonl").write_text("{}\n", encoding="utf-8")
    stub = _Stub()
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--no-manifest")
    assert code == 2
    assert stub.calls == []


def test_run_chain_resume_allows_existing_round_dir(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    target = tmp_path / "rounds" / "rx"
    target.mkdir(parents=True)
    (target / "retrieval.jsonl").write_text("{}\n", encoding="utf-8")
    stub = _Stub()
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--resume", "--no-manifest")
    assert code == 0
    assert len(stub.calls) == 1
    assert "--round" in stub.calls[0] and "rx" in stub.calls[0]


def test_run_chain_rejects_secret_set_override(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    stub = _Stub()
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--dry-run", "--no-manifest",
                "--set", "GEMINI_API_KEY=abc")
    assert code == 2
    assert stub.calls == []


def test_run_chain_duplicate_round_names_rejected(tmp_path, monkeypatch):
    spec = _spec(tmp_path, rounds=[{"round": "rx"}, {"round": "rx", "phase": "retrieval"}])
    stub = _Stub()
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--dry-run", "--no-manifest")
    assert code == 2
    assert stub.calls == []


def test_run_chain_gate_failure_with_report_continues_to_attribute(tmp_path, monkeypatch):
    spec = _spec(
        tmp_path,
        rounds=[{"round": "rx", "phase": "retrieval", "gate": {"baseline": "r0"},
                 "attribute": {"compare": "r0"}}],
    )
    stub = _Stub(create_gate_report=True, gate_rc=1)
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--no-manifest")
    assert code == 0
    tools = [Path(c[1]).name for c in stub.calls]
    assert tools == ["run_round.py", "gate.py", "attribute.py"]


def test_run_chain_gate_failure_without_report_stops_chain(tmp_path, monkeypatch):
    spec = _spec(
        tmp_path,
        rounds=[{"round": "rx", "phase": "retrieval", "gate": {"baseline": "r0"},
                 "attribute": {"compare": "r0"}}],
    )
    stub = _Stub(create_gate_report=False, gate_rc=1)
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--no-manifest")
    assert code == 2
    tools = [Path(c[1]).name for c in stub.calls]
    assert tools == ["run_round.py", "gate.py"]  # attribute KHÔNG chạy


@pytest.mark.parametrize("bad", ["KHONGCODAU", "=x"])
def test_run_chain_set_requires_key_value(tmp_path, monkeypatch, bad):
    spec = _spec(tmp_path)
    stub = _Stub()
    monkeypatch.setattr(rc.subprocess, "run", stub)
    code = _run(monkeypatch, "--chain", str(spec), "--dry-run", "--no-manifest", "--set", bad)
    assert code == 2
    assert stub.calls == []
