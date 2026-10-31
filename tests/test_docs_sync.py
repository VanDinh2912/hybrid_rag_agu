"""REVIEW §11 — tài liệu đang dùng phải khớp code; tài liệu lịch sử phải có nhãn.

Chỉ đọc file/source; không chạy script đo và không cần dựng model.
"""

from __future__ import annotations

from pathlib import Path

from src.assessment import evaluation
from src.retrieval import vector_db

ROOT = Path(__file__).resolve().parents[1]


def test_docstring_trong_so_khop_hang_so_mac_dinh():
    doc = vector_db.VectorStoreManager.create_ensemble_retriever.__doc__ or ""

    assert "0.4, 0.6" not in doc
    assert "0.5, 0.5" in doc
    assert vector_db.DEFAULT_BM25_WEIGHT == 0.5
    assert vector_db.DEFAULT_VECTOR_WEIGHT == 0.5


def test_logs_readme_tro_dung_script_hien_tai():
    text = (ROOT / "logs" / "README.md").read_text(encoding="utf-8")

    assert "src/evaluate_classifier.py" not in text
    for rel in (
        "src/assessment/evaluate_classifier.py",
        "scripts/benchmark_chunking.py",
        "scripts/export_architecture.py",
        "scripts/learn.py",
    ):
        assert f"`{rel}`" in text
        assert (ROOT / rel).exists(), rel


def test_evaluation_mac_dinh_la_benchmark_v2_va_docstring_noi_ro():
    assert evaluation.BENCHMARK_PATH.name == "benchmark_100_questions_v2.json"
    assert evaluation.BENCHMARK_PATH.exists()

    doc = evaluation.__doc__ or ""
    assert "benchmark_100_questions_v2.json" in doc
    assert "benchmark_100_questions_v3.json" in doc


def test_readme_phan_loai_benchmark_chinh_thuc_va_lich_su():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "CHÍNH THỨC cho lượt A/B" in text
    assert "mặc định của src/assessment/evaluation.py" in text
    for name in (
        "benchmark_100_questions_v3.json",
        "benchmark_100_questions_v2.json",
        "benchmark_questions.json",
    ):
        assert name in text
        assert (ROOT / "data" / "evaluation" / name).exists(), name


def test_tai_lieu_archive_co_nhan_historical():
    for rel in (
        "docs/archive/AUTONOMY_LOG.md",
        "docs/archive/PENDING_APPROVAL.md",
        "docs/archive/reports/test_T7.md",
    ):
        head = "\n".join((ROOT / rel).read_text(encoding="utf-8").splitlines()[:6])
        assert "historical" in head, rel
