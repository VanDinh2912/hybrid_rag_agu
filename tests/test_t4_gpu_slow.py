# -*- coding: utf-8 -*-
"""T4 — phần SLOW/thủ công (mục 8 + 9): cần GPU thật / Ollama thật.

Mặc định **không chạy**: đặt `T4_RUN_SLOW=1` mới chạy, để `pytest tests -q` của repo vẫn
tất định và không chiếm GPU. Marker `slow` khai báo trong `tests/conftest.py`.

Vì sao đẩy sang test con (subprocess) thay vì import:
* phép đo adapter cần `torch` + `peft`, mà app `venv/` (nơi chạy pytest) không cài torch —
  `venv_train/Scripts/python.exe` mới có; import thẳng sẽ làm đỏ cả bộ test vì thiếu gói;
* phép đo latency phải chạy ở tiến trình riêng để `nvidia-smi` thấy VRAM của Ollama.

Hai script được gọi là công cụ đo đã công bố (không chép lại phép đo vào test):
`tools/diag/t4_adapter_probe.py` và `tools/diag/t4_latency_probe.py`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PROBE = ROOT / "tools" / "diag" / "t4_adapter_probe.py"
LATENCY_PROBE = ROOT / "tools" / "diag" / "t4_latency_probe.py"
LATENCY_ARTIFACT = ROOT / "data" / "loop" / "diag" / "t4_latency_20q.json"
VENV_TRAIN_PY = ROOT / "venv_train" / "Scripts" / "python.exe"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.getenv("T4_RUN_SLOW") != "1",
                       reason="slow: cần GPU/Ollama; đặt T4_RUN_SLOW=1 để chạy"),
]


def run_json(cmd: list[str], out_path: Path) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True,
                          encoding="utf-8", timeout=900)
    assert proc.returncode == 0, f"{cmd[0]} rc={proc.returncode}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    assert out_path.exists(), f"không thấy {out_path}"
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_adapter_lora_duoc_ap_va_nap_hong_bao_loi(tmp_path: Path) -> None:
    """Mục 9: (a) đầu ra KHÁC base trên ≥1 mẫu; (b) nạp hỏng NÉM LỖI, không lùi im lặng."""
    if not VENV_TRAIN_PY.exists():
        pytest.skip("không có venv_train (torch/peft)")

    out = tmp_path / "adapter_probe.json"
    report = run_json(
        [str(VENV_TRAIN_PY), str(ADAPTER_PROBE), "--out", str(out)],
        out,
    )
    assert report["outputs_differ"] is True
    assert report["base_text"] and report["adapter_text"]
    assert report["failure_probe"]["raised"] is True
    assert report["failure_probe"]["type"], "lỗi phải có loại cụ thể, không phải None"
    assert report["vram_peak_adapter_mib"] > 0


def test_do_vram_va_latency_20_cau(tmp_path: Path) -> None:
    """Mục 8: đo lại 20 câu; test CHỈ kiểm số đo hợp lệ, KHÔNG đặt ngưỡng cứng."""
    out = tmp_path / "latency.json"
    report = run_json([sys.executable, str(LATENCY_PROBE), "--out", str(out)], out)

    assert report["n_questions"] == 20
    lat = report["latency_seconds"]
    assert 0 < lat["p50"] <= lat["p95"] <= lat["max"]
    assert lat["first_call_seconds"] >= lat["min"]
    vram = report["vram_mib"]
    assert vram["peak"] is not None and vram["peak"] > 0
    assert vram["n_samples"] > 0
