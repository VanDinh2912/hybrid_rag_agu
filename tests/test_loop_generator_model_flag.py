# -*- coding: utf-8 -*-
"""Unit test cờ T4a `GENERATOR_OLLAMA_MODEL` (`tools/loop/run_round.py`).

Bất biến #2 của dự án: lever mới phải nằm sau cờ env, mặc định TẮT, và "tắt" phải chứng
minh được là hành vi cũ **từng ký tự**. Ở đây "hành vi cũ" nghĩa là:

* `QwenGenerator` nhận `ollama_model=None` ⇒ chuỗi fallback
  `os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL` trong `src/generator.py` còn nguyên;
* `LocalSLM` (bộ chuẩn hóa câu hỏi + splitter) **không bao giờ** nhìn thấy slug mới, vì
  `OLLAMA_MODEL` dẫn năm nơi và đổi nó là đổi bốn tầng cùng lượt (mất one-variable).

Test cũng chốt hai điều round r10 cần để tự ký dụng cụ đo: cache key đổi theo model nên
không đọc nhầm cache của 1,5B, và `temperature`/`num_ctx`/`PROMPT_VERSION` KHÔNG đổi khi
chỉ đổi model.
"""

from __future__ import annotations

import pytest

import src.generator as generator_module
import tools.loop.run_round as run_round
from src.generator import DEFAULT_OLLAMA_MODEL, QwenGenerator
from tools.loop.run_round import (
    _generator_status,
    build_pipeline,
    generator_model_override,
)

SLUG = "qwen2.5:3b-instruct"


class FakeVectorStoreManager:
    def load_vector_store(self) -> str:
        return "vector-stub"


class FakeLocalSLM:
    """Ghi lại đúng kwargs nó nhận được — bằng chứng normalizer không bị đổi model."""

    calls: list[dict] = []

    def __init__(self, **kwargs):
        FakeLocalSLM.calls.append(kwargs)

    def check_connection(self):
        return True, "stub"


class FakeQwenGenerator:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        FakeQwenGenerator.calls.append(kwargs)
        self.model_name = f"local-qwen ({kwargs.get('ollama_model') or DEFAULT_OLLAMA_MODEL})"
        self.ollama_model = kwargs.get("ollama_model") or DEFAULT_OLLAMA_MODEL
        self.temperature = generator_module.QWEN_FALLBACK_TEMPERATURE


class FakeGeminiGenerator:
    def __init__(self, **kwargs):
        self.model_name = "gemini-stub"


class FakePipeline:
    def __init__(self, vector_db=None, local_slm=None, generator=None, **kwargs):
        self.vector_db = vector_db
        self.local_slm = local_slm
        self.generator = generator


@pytest.fixture
def wiring(monkeypatch):
    """Thay bốn dependency của build_pipeline bằng stub, trả về (qwen_kwargs, slm_kwargs)."""
    FakeQwenGenerator.calls = []
    FakeLocalSLM.calls = []
    monkeypatch.setattr(run_round, "VectorStoreManager", FakeVectorStoreManager)
    monkeypatch.setattr(run_round, "LocalSLM", FakeLocalSLM)
    monkeypatch.setattr(run_round, "QwenGenerator", FakeQwenGenerator)
    monkeypatch.setattr(run_round, "HybridRAGPipeline", FakePipeline)
    monkeypatch.setattr(generator_module, "GeminiGenerator", FakeGeminiGenerator)
    return FakeQwenGenerator.calls, FakeLocalSLM.calls


# ---------------------------------------------------------------- cờ mặc định TẮT


def test_mac_dinh_rong_khong_tro_bat_ky_model_nao(monkeypatch):
    monkeypatch.delenv("GENERATOR_OLLAMA_MODEL", raising=False)
    assert generator_model_override() is None


@pytest.mark.parametrize("gia_tri", ["", "   ", "\t"])
def test_chuoi_trang_cung_tinh_la_TAT(monkeypatch, gia_tri):
    """`export GENERATOR_OLLAMA_MODEL=` trên shell là tắt, không phải "model rỗng"."""
    monkeypatch.setenv("GENERATOR_OLLAMA_MODEL", gia_tri)
    assert generator_model_override() is None


def test_tat_thi_build_pipeline_truyen_None_giu_nguyen_fallback(wiring):
    qwen_calls, slm_calls = wiring
    pipeline = build_pipeline("offline_qwen")

    assert qwen_calls == [{"ollama_model": None}]
    assert pipeline.generator.ollama_model == DEFAULT_OLLAMA_MODEL
    assert slm_calls == [{}]  # LocalSLM không nhận gì mới


def test_tat_thi_cache_key_giong_het_nhu_hom_qua():
    """Tắt cờ ⇒ `ollama_model=None` ⇒ SHA-1 đầu vào không đổi ⇒ cache cũ còn giá trị."""
    g_off = QwenGenerator(ollama_model=None)
    g_default = QwenGenerator()
    prompt = "Bối cảnh: ...\nCâu hỏi: Học phí tín chỉ là bao nhiêu?"

    assert g_off.ollama_model == g_default.ollama_model == DEFAULT_OLLAMA_MODEL
    assert g_off._cache_key(prompt, 0.1) == g_default._cache_key(prompt, 0.1)


# ------------------------------------------------------------------- bật cờ


def test_bat_co_doi_tang_sinh_khong_cham_normalizer(wiring, monkeypatch):
    monkeypatch.setenv("GENERATOR_OLLAMA_MODEL", SLUG)
    qwen_calls, slm_calls = wiring
    pipeline = build_pipeline("offline_qwen")

    assert qwen_calls == [{"ollama_model": SLUG}]
    assert pipeline.generator.ollama_model == SLUG
    # Đây là dòng chứng minh "một biến": tầng chuẩn hóa/splitter đứng ngoài.
    assert slm_calls == [{}]


def test_gemini_khong_bien_nho_co_cua_tang_sinh_local(wiring, monkeypatch):
    monkeypatch.setenv("GENERATOR_OLLAMA_MODEL", SLUG)
    qwen_calls, _ = wiring
    pipeline = build_pipeline("gemini")

    assert qwen_calls == []
    assert isinstance(pipeline.generator, FakeGeminiGenerator)


def test_model_moi_miss_cache_cu_nhung_van_tat_mo_cache(tmp_path, monkeypatch):
    """Đổi slug là tự miss (không đọc nhầm câu trả lời của 1,5B) — và chỉ đổi THỨ ĐÓ."""
    g_old = QwenGenerator(ollama_model=DEFAULT_OLLAMA_MODEL)
    g_new = QwenGenerator(ollama_model=SLUG)
    prompt = "Bối cảnh: ...\nCâu hỏi: Sinh viên học lại tối đa bao nhiêu lần?"

    assert g_old._cache_key(prompt, 0.1) != g_new._cache_key(prompt, 0.1)
    # Ba thứ phải GIỮ NGUYÊN khi chỉ đổi model:
    assert g_old.temperature == g_new.temperature == generator_module.QWEN_FALLBACK_TEMPERATURE
    assert g_old.use_cache == g_new.use_cache
    assert generator_module.QWEN_FALLBACK_NUM_CTX == 8192


# ------------------------------------------------------------- manifest tự ký


def test_manifest_ghi_dung_slug_thuc_te_dang_chay():
    class PipelineWithGen:
        generator = FakeQwenGenerator(ollama_model=SLUG)

    status = _generator_status(PipelineWithGen())
    assert status["ollama_model"] == SLUG
    assert status["class"] == "FakeQwenGenerator"
    assert status["num_ctx"] == generator_module.QWEN_FALLBACK_NUM_CTX
    assert status["temperature"] == generator_module.QWEN_FALLBACK_TEMPERATURE
    # Cờ T3 vẫn TẮT ⇒ prompt path phải là v1.3, bằng chứng round chỉ đổi đúng model.
    assert status["prompt_version"] == "v1.3"
    assert status["context_char_caps"] == {"block": 1600, "total": 10000}


def test_manifest_van_ghi_duoc_khi_khong_chay_round_nao():
    """todo rỗng (chấm lại) ⇒ không có pipeline, manifest phải nói được thay vì chết."""
    status = _generator_status(None)
    assert status["class"] == "không chạy (todo rỗng)"
    # Không có instance ⇒ suy ra từ env + mặc định, vẫn là slug mà generator cũ sẽ dùng.
    assert status["ollama_model"] == (
        run_round.os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    )
    assert "unavailable" not in status
