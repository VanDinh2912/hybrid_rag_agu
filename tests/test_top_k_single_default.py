"""Ghim một mặc định top_k duy nhất (REVIEW §3, 31-10).

Trước đây bốn nơi khai báo bốn giá trị: pipeline 4, router 4, main/evaluation 6,
GUI 6. Test này khóa lại sự thật mới: `src/core/config.DEFAULT_TOP_K = 6` là nguồn
duy nhất; mọi entry point chỉ *override* qua tham số/`--top-k`/`RAG_TOP_K`, không
tự khai báo thêm hằng số.
"""

import inspect
import sys
from pathlib import Path

import pytest

import src.core.config as config
from src.core.pipeline import HybridRAGPipeline
from src.retrieval import router

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _khong_dat_rag_top_k(monkeypatch):
    """Test tự quyết env top_k; `.env` của máy dev không được chen vào."""
    monkeypatch.delenv("RAG_TOP_K", raising=False)


def test_default_top_k_is_six():
    assert config.DEFAULT_TOP_K == 6


def test_default_top_k_is_registered_in_tracked_env():
    # Accessor `top_k_from_env()` đọc qua Settings; thiếu tên trong TRACKED_ENV
    # thì `settings()` ném KeyError thay vì trả giá trị.
    assert "RAG_TOP_K" in config.TRACKED_ENV


def test_router_reexports_the_same_constant():
    assert router.DEFAULT_TOP_K is config.DEFAULT_TOP_K


def test_pipeline_signatures_use_the_shared_default():
    run_default = inspect.signature(HybridRAGPipeline.run).parameters["top_k"].default
    retrieve_default = inspect.signature(HybridRAGPipeline.retrieve).parameters["k"].default
    assert run_default == config.DEFAULT_TOP_K
    assert retrieve_default == config.DEFAULT_TOP_K


def test_evaluation_imports_the_shared_constant():
    from src.assessment import evaluation

    assert evaluation.DEFAULT_TOP_K == config.DEFAULT_TOP_K


def test_top_k_from_env_semantics():
    # Không đặt → mặc định.
    assert config.top_k_from_env() == config.DEFAULT_TOP_K


@pytest.mark.parametrize("value", ["9", "1", "15"])
def test_top_k_from_env_reads_positive_integer(monkeypatch, value):
    monkeypatch.setenv("RAG_TOP_K", value)
    assert config.top_k_from_env() == int(value)


@pytest.mark.parametrize("bad", ["", "abc", "0", "-3", "2.5"])
def test_top_k_from_env_falls_back_to_default(monkeypatch, bad):
    """Giữ ngữ nghĩa router cũ: rỗng/sai định dạng/≤ 0 → mặc định."""
    monkeypatch.setenv("RAG_TOP_K", bad)
    assert config.top_k_from_env() == config.DEFAULT_TOP_K


def test_cli_default_and_override(monkeypatch):
    import main

    monkeypatch.setattr(sys, "argv", ["main.py"])
    assert main.parse_args().top_k == config.DEFAULT_TOP_K

    monkeypatch.setattr(sys, "argv", ["main.py", "-k", "3"])
    assert main.parse_args().top_k == 3  # caller thắng env/mặc định


def test_cli_reads_rag_top_k(monkeypatch):
    import main

    monkeypatch.setenv("RAG_TOP_K", "9")
    monkeypatch.setattr(sys, "argv", ["main.py"])
    assert main.parse_args().top_k == 9


def test_gui_uses_the_shared_default():
    """GUI không import được trong mọi môi trường headless, nên kiểm bằng nguồn."""
    source = (REPO_ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    assert "from src.core.config import DEFAULT_TOP_K" in source
    assert "tk.IntVar(value=DEFAULT_TOP_K)" in source
    assert "top_k=DEFAULT_TOP_K" in source
    assert "DEFAULT_TOP_K = 6" not in source  # không tự khai báo lại
