"""Bước 0 P5.1 — ui/app.py đọc USE_QWEN_GENERATOR thay vì hardcode GeminiGenerator.

Thuần offline: chỉ mock class generator, không khởi tạo cửa sổ Tkinter,
không gọi Ollama/API thật.
"""

from __future__ import annotations

import ui.app as ui_app


def test_use_qwen_generator_reads_env(monkeypatch):
    """USE_QWEN_GENERATOR=1 → True; =0 hoặc không đặt → False (mặc định giữ Gemini)."""
    monkeypatch.setenv("USE_QWEN_GENERATOR", "1")
    assert ui_app.use_qwen_generator() is True

    monkeypatch.setenv("USE_QWEN_GENERATOR", "0")
    assert ui_app.use_qwen_generator() is False

    monkeypatch.delenv("USE_QWEN_GENERATOR", raising=False)
    assert ui_app.use_qwen_generator() is False


def test_build_generator_qwen_branch(monkeypatch):
    """Nhánh cờ bật: build_generator phải dựng đúng class Qwen được tiêm (mock)."""

    class FakeQwen:
        def __init__(self):
            self.model_name = "fake-qwen"

    monkeypatch.setattr(ui_app, "QwenGenerator", FakeQwen)
    generator = ui_app.build_generator(True)
    assert isinstance(generator, FakeQwen)
    assert generator.model_name == "fake-qwen"


def test_build_generator_gemini_branch(monkeypatch):
    """Nhánh mặc định: build_generator(False) phải dựng đúng class Gemini được tiêm (mock)."""

    class FakeGemini:
        def __init__(self):
            self.model_name = "fake-gemini"

    monkeypatch.setattr(ui_app, "GeminiGenerator", FakeGemini)
    generator = ui_app.build_generator(False)
    assert isinstance(generator, FakeGemini)
    assert generator.model_name == "fake-gemini"
