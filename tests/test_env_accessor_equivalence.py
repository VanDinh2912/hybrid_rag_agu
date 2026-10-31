"""REVIEW §5 — accessor trong `src.core.config` phải sao chép ĐÚNG site đọc env cũ.

Mỗi test triển khai lại công thức CŨ ngay trong test (không import code cũ đã xoá) rồi
so với hàm đã chuyển. Env được đặt/xoá qua `monkeypatch`, `settings()` tự dựng lại ảnh
chụp nên không cần xoá cache thủ công.

Phạm vi: router (trọng số + 3 site cờ/ngưỡng), reranker (8 site), query normalizer
(2 site). Pipeline chỉ chuyển hai trọng số RRF — kiểm qua `float_required`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core import config  # noqa: E402
from src.core.query_normalizer import (  # noqa: E402
    DEFAULT_NORMALIZE_MIN_CONTAINMENT,
    normalize_min_containment,
    normalize_sanity_guard_enabled,
)
from src.retrieval import reranker, router  # noqa: E402


# --------------------------------------------------------------- công thức CŨ
def _old_flag(name: str, default: str = "0") -> bool:
    import os

    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _old_int_env(name: str, default: int, minimum: int = 1) -> int:
    import os

    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(float(raw)))
    except ValueError:
        return default


def _old_float(name: str, default: float) -> float:
    import os

    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _old_text_or(name: str, default: str) -> str:
    import os

    return os.getenv(name) or default


def _old_text_strip_or(name: str, default: str) -> str:
    import os

    return os.getenv(name, "").strip() or default


def _old_guard() -> bool:
    import os

    return (os.getenv("NORMALIZE_SANITY_GUARD") or "0").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    )


def _old_containment() -> float:
    import os

    raw = (os.getenv("NORMALIZE_MIN_CONTAINMENT") or "").strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_NORMALIZE_MIN_CONTAINMENT
    return min(1.0, max(0.0, value))


CASES = [
    None,  # xoá env
    "",
    " ",
    "abc",
    "0",
    "1",
    "true",
    " off ",
    "-2",
    "3",
    "3.9",
    "12",
    " 7 ",
    "1.5",
]


@pytest.mark.parametrize("raw", CASES, ids=lambda v: "unset" if v is None else repr(v))
class TestRouter:
    def test_bm25_chroma_weight(self, monkeypatch, raw):
        for name, default in (("BM25_WEIGHT", router.DEFAULT_BM25_WEIGHT),
                              ("CHROMA_WEIGHT", router.DEFAULT_VECTOR_WEIGHT)):
            monkeypatch.delenv(name, raising=False)
            if raw is not None:
                monkeypatch.setenv(name, raw)
            cfg = router.base_config_from_env()
            assert cfg.bm25_weight == _old_float("BM25_WEIGHT", router.DEFAULT_BM25_WEIGHT)
            assert cfg.chroma_weight == _old_float("CHROMA_WEIGHT", router.DEFAULT_VECTOR_WEIGHT)

    def test_soft_filter_flag(self, monkeypatch, raw):
        monkeypatch.delenv("ROUTER_SOFT_FILTER", raising=False)
        if raw is not None:
            monkeypatch.setenv("ROUTER_SOFT_FILTER", raw)
        assert router.router_soft_filter_enabled() == _old_flag("ROUTER_SOFT_FILTER")

    def test_rank_bonus(self, monkeypatch, raw):
        monkeypatch.delenv("ROUTER_FILTER_RANK_BONUS", raising=False)
        if raw is not None:
            monkeypatch.setenv("ROUTER_FILTER_RANK_BONUS", raw)
        old = _old_int_env("ROUTER_FILTER_RANK_BONUS", router.DEFAULT_FILTER_RANK_BONUS, 0)
        assert router.router_filter_rank_bonus() == old

    def test_source_quota(self, monkeypatch, raw):
        monkeypatch.delenv("ROUTER_SOURCE_QUOTA", raising=False)
        if raw is not None:
            monkeypatch.setenv("ROUTER_SOURCE_QUOTA", raw)
        assert router.router_source_quota() == _old_int_env("ROUTER_SOURCE_QUOTA", 0, 0)


@pytest.mark.parametrize("raw", CASES, ids=lambda v: "unset" if v is None else repr(v))
class TestReranker:
    def test_flags(self, monkeypatch, raw):
        for name, fn in (
            ("ENABLE_RERANKER", reranker.reranker_enabled),
            ("RERANKER_KEEP_CANDIDATES", reranker.reranker_keep_candidates),
            ("RERANKER_FALLBACK", reranker.reranker_fallback_enabled),
        ):
            monkeypatch.delenv(name, raising=False)
            if raw is not None:
                monkeypatch.setenv(name, raw)
            assert fn() == _old_flag(name), name

    def test_ints(self, monkeypatch, raw):
        for name, fn, default in (
            ("RERANKER_CANDIDATE_POOL", reranker.reranker_candidate_pool, reranker.DEFAULT_CANDIDATE_POOL),
            ("RERANKER_MAX_LENGTH", reranker.reranker_max_length, reranker.DEFAULT_MAX_LENGTH),
            ("RERANKER_BATCH_SIZE", reranker.reranker_batch_size, reranker.DEFAULT_BATCH_SIZE),
        ):
            monkeypatch.delenv(name, raising=False)
            if raw is not None:
                monkeypatch.setenv(name, raw)
            assert fn() == _old_int_env(name, default), name

    def test_texts(self, monkeypatch, raw):
        monkeypatch.delenv("RERANKER_DEVICE", raising=False)
        if raw is not None:
            monkeypatch.setenv("RERANKER_DEVICE", raw)
        assert reranker.reranker_device() == _old_text_strip_or("RERANKER_DEVICE", reranker.DEFAULT_DEVICE)


@pytest.mark.parametrize("raw", CASES, ids=lambda v: "unset" if v is None else repr(v))
class TestNormalizer:
    def test_guard(self, monkeypatch, raw):
        monkeypatch.delenv("NORMALIZE_SANITY_GUARD", raising=False)
        if raw is not None:
            monkeypatch.setenv("NORMALIZE_SANITY_GUARD", raw)
        assert normalize_sanity_guard_enabled() == _old_guard()

    def test_min_containment(self, monkeypatch, raw):
        monkeypatch.delenv("NORMALIZE_MIN_CONTAINMENT", raising=False)
        if raw is not None:
            monkeypatch.setenv("NORMALIZE_MIN_CONTAINMENT", raw)
        old = _old_containment()
        new = normalize_min_containment()
        if old != old:  # NaN
            return
        assert new == old


def test_float_required_matches_old_float(monkeypatch):
    """Hai trọng số RRF của pipeline dùng `float_required` — phải ném y như `float()` cũ."""
    for raw in ("0.3", " 0.3 ", "abc", ""):
        monkeypatch.setenv("BM25_WEIGHT", raw)
        try:
            old = float(raw)
        except ValueError:
            with pytest.raises(ValueError):
                config.settings().float_required("BM25_WEIGHT", 0.5)
        else:
            assert config.settings().float_required("BM25_WEIGHT", 0.5) == old


def test_catalog_mentions_every_migrated_name():
    """Mọi biến REVIEW §5 đã chuyển phải có tên trong `TRACKED_ENV` (một nguồn chụp)."""
    expected = {
        "ROUTER_SOFT_FILTER",
        "ROUTER_FILTER_RANK_BONUS",
        "ROUTER_SOURCE_QUOTA",
        "ENABLE_RERANKER",
        "RERANKER_KEEP_CANDIDATES",
        "RERANKER_FALLBACK",
        "RERANKER_CANDIDATE_POOL",
        "RERANKER_MAX_LENGTH",
        "RERANKER_BATCH_SIZE",
        "RERANKER_MODEL",
        "RERANKER_DEVICE",
        "NORMALIZE_SANITY_GUARD",
        "NORMALIZE_MIN_CONTAINMENT",
    }
    assert expected <= set(config.TRACKED_ENV)
