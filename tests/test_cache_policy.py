"""Unit test T7 — khóa CHÍNH SÁCH cho cache tầng sinh (`src/cache_policy.py`).

Vì sao phải có: cache sinh văn bản vốn chỉ băm `{model, temperature, prompt_version,
prompt}`. Nhưng đổi ngưỡng cứu câu từ chối / guard / chọn câu bằng chứng thì câu trả
lời cũ vẫn trúng cache và round sau "tái dùng câu trả lời của thể chế cũ" — phép đo
lever trông như vô hiệu. Test dưới đây ghim hai đầu của hợp đồng:

  1. Cùng env ⇒ cùng dấu vân tay; đổi bất kỳ ngưỡng/cờ nào trong danh sách ⇒ đổi.
  2. `GeminiGenerator._cache_key` có mang dấu vân tay đó (đổi ngưỡng ⇒ cache miss).

Không gọi model, không mạng, không đọc/ghi cache thật. Fixture xóa toàn bộ env liên
quan để kết quả không phụ thuộc shell của người chạy.
"""

from __future__ import annotations

import json
import re

import pytest

from src import evidence_selection
from src.cache_policy import (
    DEFAULT_CACHE_TOKEN,
    POLICY_KEY_VERSION,
    cache_policy_deviation,
    policy_cache_token,
    policy_fingerprint,
    policy_snapshot,
)
from src.generator import GeminiGenerator, QwenGenerator

# Mọi biến mà `policy_snapshot()` có thể đọc. Thêm lever mới thì thêm tên vào đây —
# test `test_policy_snapshot_shape_matches_contract` sẽ nhắc nếu cấu trúc đổi.
POLICY_ENVS = (
    "ENABLE_ANSWER_RESCUE",
    "RESCUE_MIN_SCORE",
    "ENABLE_ANSWER_GUARD",
    "ANSWER_GUARD_MIN_SCORE",
    "ANSWER_GUARD_MAX_UNSUPPORTED",
    "ENABLE_DECOUPLED_REFUSAL",
    "DEC_MIN_ENTITY_COVERAGE",
    "DEC_MIN_TOKEN_OVERLAP",
    "DEC_MIN_RRF_NORM",
    "DEC_MIN_GROUNDING",
    "DEC_MAX_UNSUPPORTED",
    "ENABLE_EVIDENCE_SELECTION",
    "EV_MIN_SENTENCES",
    "EV_MAX_SENTENCES",
    "EV_MIN_KEYWORD_HITS",
    "EVIDENCE_RERANKER",
    "NORMALIZE_SANITY_GUARD",
    "NORMALIZE_MIN_CONTAINMENT",
)

SECRET_ENVS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "CHROMA_API_KEY")

HEX12 = re.compile(r"^[0-9a-f]{12}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


@pytest.fixture()
def clean_env(monkeypatch):
    """Xóa cả biến chính sách lẫn biến bí mật để test độc lập với shell."""
    for name in POLICY_ENVS + SECRET_ENVS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _generator(model_name: str = "gemini-test-model") -> GeminiGenerator:
    """Dựng generator KHÔNG gọi `__init__` (không cần API key, không chạm mạng)."""
    gen = object.__new__(GeminiGenerator)
    gen.model_name = model_name
    return gen


def _qwen(model_name: str = "qwen-test-model") -> QwenGenerator:
    """Dựng QwenGenerator KHÔNG gọi `__init__` (không cần Ollama, không chạm mạng)."""
    gen = object.__new__(QwenGenerator)
    gen.ollama_model = model_name
    return gen


# --------------------------------------------------------------------------- ổn định


def test_policy_fingerprint_same_env_returns_same_12_hex(clean_env):
    first = policy_fingerprint()
    second = policy_fingerprint()
    assert first == second
    assert HEX12.match(first), f"phải là 12 hex thường, nhận {first!r}"


def test_policy_fingerprint_unrelated_env_does_not_change(clean_env):
    # Model đi vào khóa cache ở trường riêng (`model`), KHÔNG vào dấu vân tay chính sách.
    baseline = policy_fingerprint()
    clean_env.setenv("GEMINI_MODEL", "mot-model-khac")
    clean_env.setenv("GEMINI_TEMPERATURE", "0.9")
    assert policy_fingerprint() == baseline


def test_policy_snapshot_shape_matches_contract(clean_env):
    assert set(policy_snapshot()) == {
        "policy_key_version",
        "prompt_version",
        "rescue",
        "guard",
        "decoupled_refusal",
        "evidence_selection",
        "normalize_sanity",
    }


def test_policy_key_version_change_changes_fingerprint(clean_env):
    snapshot = policy_snapshot()
    baseline = policy_fingerprint(snapshot)
    bumped = dict(snapshot)
    bumped["policy_key_version"] = POLICY_KEY_VERSION + "-next"
    assert policy_fingerprint(bumped) != baseline


# ------------------------------------------------------------------ đổi ngưỡng ⇒ đổi


def test_policy_fingerprint_changes_when_rescue_min_score_changes(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("RESCUE_MIN_SCORE", "0.55")
    assert policy_fingerprint() != baseline


def test_policy_fingerprint_invalid_rescue_min_score_falls_back_to_default(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("RESCUE_MIN_SCORE", "khong-phai-so")
    assert policy_fingerprint() == baseline


def test_policy_fingerprint_changes_when_answer_guard_enabled(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("ENABLE_ANSWER_GUARD", "1")
    assert policy_fingerprint() != baseline


def test_policy_fingerprint_changes_when_guard_max_unsupported_changes(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("ANSWER_GUARD_MAX_UNSUPPORTED", "3")
    assert policy_fingerprint() != baseline


def test_policy_fingerprint_changes_when_decoupled_refusal_enabled(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    snapshot = policy_snapshot()
    # Bật cờ này còn đổi cả prompt version (v2.0-extract-only) — hai lý do cộng lại.
    assert policy_fingerprint() != baseline
    assert snapshot["decoupled_refusal"]["enabled"] is True
    assert snapshot["prompt_version"].startswith("v2.")


def test_policy_fingerprint_changes_when_dec_min_entity_coverage_changes(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("DEC_MIN_ENTITY_COVERAGE", "0.55")
    assert policy_fingerprint() != baseline


def test_policy_fingerprint_changes_when_evidence_budget_changes(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("ENABLE_EVIDENCE_SELECTION", "1")
    clean_env.setenv("EV_MAX_SENTENCES", "9")
    after = policy_snapshot()
    assert after["evidence_selection"]["enabled"] is True
    assert after["evidence_selection"]["max_sentences"] == 9
    assert policy_fingerprint() != baseline


def test_policy_fingerprint_changes_when_evidence_reranker_requested_changes(clean_env, monkeypatch):
    # Reranker có thể đã được dựng bởi test khác trong cùng process ⇒ ép về "chưa dựng"
    # để hàm phân giải đọc đúng biến EVIDENCE_RERANKER.
    monkeypatch.setattr(evidence_selection, "_RERANKER", None, raising=False)
    clean_env.setenv("EVIDENCE_RERANKER", "cross-encoder")
    first = policy_fingerprint()
    clean_env.setenv("EVIDENCE_RERANKER", "none")
    assert policy_fingerprint() != first


def test_policy_fingerprint_changes_when_normalize_sanity_guard_enabled(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("NORMALIZE_SANITY_GUARD", "1")
    assert policy_fingerprint() != baseline


def test_policy_fingerprint_changes_when_min_containment_changes(clean_env):
    baseline = policy_fingerprint()
    clean_env.setenv("NORMALIZE_MIN_CONTAINMENT", "0.45")
    assert policy_fingerprint() != baseline


# ---------------------------------------------------------------------- không bí mật


def test_policy_snapshot_contains_no_sensitive_env_values(clean_env):
    sentinels = {
        "GEMINI_API_KEY": "sentinel-gemini-key-abc123",
        "GOOGLE_API_KEY": "sentinel-google-key-def456",
        "OPENAI_API_KEY": "sentinel-openai-key-ghi789",
        "CHROMA_API_KEY": "sentinel-chroma-key-jkl012",
    }
    for name, value in sentinels.items():
        clean_env.setenv(name, value)

    dump = json.dumps(policy_snapshot(), ensure_ascii=False, sort_keys=True)
    for value in sentinels.values():
        assert value not in dump
    for name in sentinels:
        assert name not in dump
    assert "api_key" not in dump.lower()
    assert "secret" not in dump.lower()


# -------------------------------------------------------------------- khóa cache sinh


def test_cache_key_same_regime_and_prompt_is_stable(clean_env):
    gen = _generator()
    first = gen._cache_key("Câu hỏi mẫu?", 0.0)
    second = gen._cache_key("Câu hỏi mẫu?", 0.0)
    assert first == second
    assert HEX40.match(first)


def test_cache_key_changes_when_policy_threshold_changes(clean_env):
    gen = _generator()
    baseline = gen._cache_key("Câu hỏi mẫu?", 0.0)
    clean_env.setenv("RESCUE_MIN_SCORE", "0.55")
    assert gen._cache_key("Câu hỏi mẫu?", 0.0) != baseline


def test_cache_key_changes_when_model_or_prompt_or_temperature_changes(clean_env):
    gen = _generator()
    baseline = gen._cache_key("Câu hỏi mẫu?", 0.0)
    assert gen._cache_key("Câu hỏi mẫu?", 0.7) != baseline
    assert gen._cache_key("Câu hỏi khác?", 0.0) != baseline
    assert _generator("gemini-model-khac")._cache_key("Câu hỏi mẫu?", 0.0) != baseline


def test_cache_key_payload_contains_prompt_version_and_policy(clean_env):
    """Thể chế MẶC ĐỊNH ⇒ khóa đúng công thức cũ 4 trường (bất biến #2, cache cũ còn dùng)."""
    import hashlib

    from src.generator import effective_prompt_version

    expected = hashlib.sha1(
        json.dumps(
            {
                "model": "gemini-test-model",
                "temperature": 0.0,
                "prompt_version": effective_prompt_version(),
                "prompt": "Câu hỏi mẫu?",
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert _generator()._cache_key("Câu hỏi mẫu?", 0.0) == expected


def test_cache_key_payload_has_policy_token_when_threshold_deviates(clean_env):
    """Lệch mặc định ⇒ payload mang thêm `policy` đúng bằng token lệch (ghim cấu trúc)."""
    import hashlib

    from src.cache_policy import cache_policy_deviation, policy_cache_token
    from src.generator import effective_prompt_version

    clean_env.setenv("RESCUE_MIN_SCORE", "0.55")
    deviation = cache_policy_deviation()
    assert deviation == policy_cache_token() and deviation is not None

    expected = hashlib.sha1(
        json.dumps(
            {
                "model": "gemini-test-model",
                "temperature": 0.0,
                "prompt_version": effective_prompt_version(),
                "policy": deviation,
                "prompt": "Câu hỏi mẫu?",
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert _generator()._cache_key("Câu hỏi mẫu?", 0.0) == expected


def test_cache_key_does_not_change_when_only_secret_env_changes(clean_env):
    gen = _generator()
    baseline = gen._cache_key("Câu hỏi mẫu?", 0.0)
    clean_env.setenv("GEMINI_API_KEY", "rotated-key-xyz")
    assert gen._cache_key("Câu hỏi mẫu?", 0.0) == baseline


# ------------------------------------------------------- đường Qwen (fallback + loop)


def test_qwen_cache_key_changes_when_policy_threshold_changes(clean_env):
    """Vòng lặp chạy Qwen qua cache này — thiếu policy là lever mới bị cache cũ che."""
    gen = _qwen()
    baseline = gen._cache_key("Câu hỏi mẫu?", 0.0)
    clean_env.setenv("RESCUE_MIN_SCORE", "0.55")
    assert gen._cache_key("Câu hỏi mẫu?", 0.0) != baseline


def test_qwen_cache_key_payload_contains_prompt_version_and_policy(clean_env):
    """Thể chế mặc định ⇒ Qwen giữ đúng công thức cũ 4 trường (cache cũ còn dùng)."""
    import hashlib

    from src.generator import effective_prompt_version

    expected = hashlib.sha1(
        json.dumps(
            {
                "model": "qwen-test-model",
                "temperature": 0.0,
                "prompt_version": effective_prompt_version(),
                "prompt": "Câu hỏi mẫu?",
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert _qwen()._cache_key("Câu hỏi mẫu?", 0.0) == expected


# ----------------------------------------------------------- token lệch & mốc mặc định


def test_policy_cache_token_default_matches_cleared_env(clean_env):
    """Mốc `DEFAULT_CACHE_TOKEN` phải trùng thể chế mặc định. Đỏ = default module đổi
    (phải đăng ký lại token + cân nhắc bump CACHE_TOKEN_VERSION) hoặc payload token đổi."""
    assert policy_cache_token() == DEFAULT_CACHE_TOKEN


def test_cache_policy_deviation_none_at_default_token_when_threshold_changes(clean_env):
    assert cache_policy_deviation() is None
    clean_env.setenv("ANSWER_GUARD_MAX_UNSUPPORTED", "2")
    assert cache_policy_deviation() == policy_cache_token()
    assert cache_policy_deviation() != DEFAULT_CACHE_TOKEN


def test_cache_policy_token_ignores_decoupled_flag_but_not_its_thresholds(clean_env):
    """Cờ T3 đã được `prompt_version` mã hóa ⇒ token không đổi; nhưng ngưỡng DEC thì đổi."""
    baseline = policy_cache_token()
    clean_env.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    assert policy_cache_token() == baseline
    clean_env.setenv("DEC_MIN_ENTITY_COVERAGE", "0.55")
    assert policy_cache_token() != baseline
