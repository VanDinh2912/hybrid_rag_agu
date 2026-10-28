# -*- coding: utf-8 -*-
"""Test T7 — mục 3 đề bài: **đổi ngưỡng thể chế thì cache sinh KHÔNG được tái dùng**.

Đề bài đòi đúng một phép đo: đếm số lần gọi stub. Vì vậy mọi test ở đây chạy `QwenGenerator` thật
với `ollama.Client` bị thay bằng stub (ghi lại prompt, đếm cuộc gọi) và cache trỏ vào `tmp_path`:

| Tình huống | Kỳ vọng |
|---|---|
| Không đổi gì, hỏi lại câu giống hệt | stub **không** tăng, cache vẫn 1 entry |
| Đổi `RESCUE_MIN_SCORE` (0,8 → 0,6) | entry **mới**, stub gọi lại |
| Đổi rồi **trả về cũ** | trúng lại entry gốc, stub không tăng, cache 2 entry cùng tồn tại |
| Đổi `ANSWER_GUARD_MAX_UNSUPPORTED` / `DEC_MAX_UNSUPPORTED` / `NORMALIZE_MIN_CONTAINMENT` | như đổi ngưỡng cứu |
| Thể chế mặc định (mọi biến bị xóa) | khóa cache **giống từng byte** công thức cũ ⇒ 351+ entry còn dùng được |

Không gọi mạng/Ollama/Gemini thật, không ghi `.generation_cache` của repo, không round-trip model.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import src.generator as gen_module
from src.core.cache_policy import (
    DEFAULT_CACHE_TOKEN,
    cache_policy_deviation,
    policy_cache_token,
    policy_fingerprint,
    policy_snapshot,
)
from src.generator import GeminiGenerator, QwenGenerator

QUERY = "Mức học phí khối kỹ thuật là bao nhiêu?"
DOCS = [
    {"content": "Điều 3. Mức thu học phí theo khối ngành.", "source": "hoc-phi.pdf",
     "tier": "1", "chunk_id": 7},
    {"content": "Mức thu áp dụng từ năm học 2026-2027.", "source": "quy-che.pdf",
     "tier": "1", "chunk_id": 8},
]

# Toàn bộ biến thể chế mà `src/core/cache_policy.py` đọc — dọn sạch để "mặc định" thật sự là mặc định.
POLICY_ENV = (
    "ENABLE_ANSWER_RESCUE", "RESCUE_MIN_SCORE",
    "ENABLE_ANSWER_GUARD", "ANSWER_GUARD_MIN_SCORE", "ANSWER_GUARD_MAX_UNSUPPORTED",
    "ENABLE_DECOUPLED_REFUSAL", "DEC_MIN_ENTITY_COVERAGE", "DEC_MIN_TOKEN_OVERLAP",
    "DEC_MIN_RRF_NORM", "DEC_MIN_GROUNDING", "DEC_MAX_UNSUPPORTED",
    "ENABLE_EVIDENCE_SELECTION", "EV_MIN_SENTENCES", "EV_MAX_SENTENCES", "EV_MIN_KEYWORD_HITS",
    "EVIDENCE_RERANKER",
    "NORMALIZE_SANITY_GUARD", "NORMALIZE_MIN_CONTAINMENT",
    "ENABLE_CLASSIFIER", "ENABLE_PROMPT_VARIANT", "GENERATOR_MODEL",
    "GEMINI_MODEL", "GEMINI_TEMPERATURE", "ANSWER_GUARD_MIN_MATCH",
)


class CountingOllama:
    """Stub `ollama.Client`: nhớ mọi prompt đã nhận, trả lời cố định, đếm số lượt."""

    instances: list["CountingOllama"] = []

    def __init__(self, host=None, timeout=None):
        self.calls: list[str] = []
        CountingOllama.instances.append(self)

    def generate(self, model=None, prompt=None, options=None, stream=False):
        self.calls.append(prompt)
        return {"response": "Mức thu học phí khối kỹ thuật là 12 triệu đồng/năm học 2026-2027."}

    @staticmethod
    def total_calls() -> int:
        return sum(len(c.calls) for c in CountingOllama.instances)


@pytest.fixture()
def stub_ollama(monkeypatch):
    CountingOllama.instances = []
    monkeypatch.setattr(gen_module.ollama, "Client", CountingOllama)
    return CountingOllama


@pytest.fixture()
def clear_policy(monkeypatch):
    for var in POLICY_ENV:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    d = tmp_path / "cache"
    monkeypatch.setenv("GENERATION_CACHE_DIR", str(d))
    return d


@pytest.fixture()
def gen(clear_policy, stub_ollama, cache_dir):
    return QwenGenerator(use_cache=True)


def entries(d: Path) -> int:
    return len(list(d.glob("*.json")))


# ---------------------------------------------------------------------------
# Không đổi thể chế ⇒ tái dùng (đếm stub)
# ---------------------------------------------------------------------------

class TestGinKhiKhongDoi:
    def test_hoi_lai_khong_tang_cuoc_goi(self, gen, cache_dir):
        before = CountingOllama.total_calls()
        gen.generate_answer(QUERY, DOCS)
        first = CountingOllama.total_calls()
        assert first > before                       # lượt đầu là MISS, có gọi model
        gen.generate_answer(QUERY, DOCS)
        assert CountingOllama.total_calls() == first  # lượt hai trúng cache
        assert entries(cache_dir) == 1

    def test_hai_the_che_khac_nhung_cung_nguong_thi_cung_key(self, gen, cache_dir, monkeypatch):
        """Đặt ngưỡng = đúng giá trị mặc định thì KHÔNG được tạo entry mới (không phạt oan)."""
        gen.generate_answer(QUERY, DOCS)
        n = CountingOllama.total_calls()
        monkeypatch.setenv("RESCUE_MIN_SCORE", "0.8")   # bằng mặc định
        monkeypatch.setenv("ANSWER_GUARD_MAX_UNSUPPORTED", "1")
        gen.generate_answer(QUERY, DOCS)
        assert CountingOllama.total_calls() == n
        assert entries(cache_dir) == 1


# ---------------------------------------------------------------------------
# Đổi ngưỡng ⇒ cache cũ bị từ chối; đổi lại ⇒ trúng entry cũ
# ---------------------------------------------------------------------------

class TestDoiNguongKhongTaiDung:
    @pytest.mark.parametrize("var,value", [
        ("RESCUE_MIN_SCORE", "0.6"),
        ("ANSWER_GUARD_MAX_UNSUPPORTED", "0"),
        ("ANSWER_GUARD_MAX_UNSUPPORTED", "2"),
        ("DEC_MAX_UNSUPPORTED", "7"),
        ("NORMALIZE_MIN_CONTAINMENT", "0.45"),
        ("EV_MAX_SENTENCES", "9"),
    ])
    def test_doi_nguong_tao_entry_moi(self, gen, cache_dir, monkeypatch, var, value):
        gen.generate_answer(QUERY, DOCS)
        base_calls = CountingOllama.total_calls()
        assert entries(cache_dir) == 1
        monkeypatch.setenv(var, value)
        gen.generate_answer(QUERY, DOCS)
        assert CountingOllama.total_calls() > base_calls, f"{var}={value} vẫn tái dùng cache cũ"
        assert entries(cache_dir) == 2

    @pytest.mark.parametrize("var,value", [
        ("RESCUE_MIN_SCORE", "0.6"),
        ("DEC_MAX_UNSUPPORTED", "7"),
    ])
    def test_tra_ve_cu_trung_lai_entry_goc(self, gen, cache_dir, monkeypatch, var, value):
        gen.generate_answer(QUERY, DOCS)                       # entry A
        calls_a = CountingOllama.total_calls()
        monkeypatch.setenv(var, value)
        gen.generate_answer(QUERY, DOCS)                       # entry B
        calls_b = CountingOllama.total_calls()
        assert calls_b > calls_a
        monkeypatch.delenv(var)                                # về thể chế gốc
        gen.generate_answer(QUERY, DOCS)
        assert CountingOllama.total_calls() == calls_b         # trúng A, không sinh lại
        assert entries(cache_dir) == 2                         # A và B cùng tồn tại

    def test_key_hai_the_che_khac_nhau_va_deu_doc_duoc(self, gen, cache_dir, monkeypatch):
        keys = []
        for val in (None, "0.5", "0.9"):
            if val is None:
                monkeypatch.delenv("RESCUE_MIN_SCORE", raising=False)
            else:
                monkeypatch.setenv("RESCUE_MIN_SCORE", val)
            gen.generate_answer(QUERY, DOCS)
            keys.append(gen._cache_key(gen._build_prompt(QUERY, DOCS), gen.temperature))
        assert len(set(keys)) == 3
        assert entries(cache_dir) == 3

    def test_the_che_lech_lam_doi_khoa_gemini_dung_het(self, clear_policy, cache_dir):
        """`GeminiGenerator` cùng luật — gọi `_cache_key` không cần kết nối (không dựng model)."""
        from types import SimpleNamespace
        g = SimpleNamespace(model_name="gemini-2.5-flash")
        prompt = "PROMPT CO DINH"

        def key() -> str:
            return GeminiGenerator._cache_key(g, prompt, 0.2)

        k_default = key()
        payload = {"model": g.model_name, "temperature": 0.2,
                   "prompt_version": gen_module.effective_prompt_version(), "prompt": prompt}
        assert k_default == hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()                                   # đường mặc định = công thức cũ
        import os
        os.environ["RESCUE_MIN_SCORE"] = "0.55"
        try:
            k_lech = key()
            payload["policy"] = cache_policy_deviation()
            assert k_lech == hashlib.sha1(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
        finally:
            os.environ.pop("RESCUE_MIN_SCORE")
        assert k_default != k_lech

    def test_bat_co_khach_biet_ra_khai_nhat_quan(self, gen, cache_dir, monkeypatch):
        """Cờ rescue BẬT nhưng ngưỡng giữ nguyên: snapshot đổi ⇒ key đổi (chặn 'tái dùng câu
        trả lời của thể chế khác', kể cả khi cờ chỉ bật ở lượt sau)."""
        gen.generate_answer(QUERY, DOCS)
        calls = CountingOllama.total_calls()
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        gen.generate_answer(QUERY, DOCS)
        assert entries(cache_dir) == 2
        assert CountingOllama.total_calls() >= calls


# ---------------------------------------------------------------------------
# Bất biến #2: thể chế mặc định phải giữ khóa CŨ từng byte
# ---------------------------------------------------------------------------

class TestMacDinhGiuKhoaCu:
    def test_deviation_none_duoi_env_rong(self, clear_policy):
        assert cache_policy_deviation() is None

    def test_token_mack_dinh_khong_doi(self, clear_policy):
        assert policy_cache_token() == DEFAULT_CACHE_TOKEN

    def test_khoa_cache_khong_chua_truong_policy_khi_mac_dinh(self, gen, cache_dir, clear_policy):
        prompt = gen._build_prompt(QUERY, DOCS)
        key = gen._cache_key(prompt, gen.temperature)
        payload = {"model": gen.ollama_model, "temperature": gen.temperature,
                   "prompt_version": gen_module.effective_prompt_version(), "prompt": prompt}
        expected = hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        assert key == expected                      # đúng công thức trước T7, từng ký tự

    def test_khoa_lech_them_truong_policy(self, gen, cache_dir, monkeypatch):
        monkeypatch.setenv("RESCUE_MIN_SCORE", "0.42")
        prompt = gen._build_prompt(QUERY, DOCS)
        key = gen._cache_key(prompt, gen.temperature)
        payload = {"model": gen.ollama_model, "temperature": gen.temperature,
                   "prompt_version": gen_module.effective_prompt_version(),
                   "policy": cache_policy_deviation(), "prompt": prompt}
        assert key == hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        assert cache_policy_deviation() is not None

    def test_fps_all_dinh_va_khong_chua_bi_mat(self, clear_policy):
        snap = policy_snapshot()
        assert policy_fingerprint(snap) == policy_fingerprint(snap)
        blob = json.dumps(snap, ensure_ascii=False)
        for word in ("API_KEY", "sk-", "Bearer", "GEMINI_API_KEY"):
            assert word not in blob
