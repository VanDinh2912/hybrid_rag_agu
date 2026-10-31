"""Ghim `src/core/paths.py` — đường dẫn neo theo gốc dự án (REVIEW §4, 31-10).

Lỗi cũ: `Path("data/...")`, `Path("outputs/...")`, `Path("logs/...")` phụ thuộc CWD,
nên chạy từ root repo / IDE / thư mục khác cho ba vị trí khác nhau. Test này kiểm:

1. Hằng số tuyệt đối và nằm dưới `PROJECT_ROOT`.
2. Cùng kết quả khi import từ CWD khác (subprocess).
3. Override trong env: tương đối → theo gốc dự án; tuyệt đối → giữ nguyên.
4. Các module đã chuyển thật sự dùng hằng số dùng chung.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from src.core import paths

REPO_ROOT = paths.PROJECT_ROOT


def test_project_root_is_repo_root():
    assert REPO_ROOT == REPO_ROOT.resolve()
    assert (REPO_ROOT / "src" / "core" / "paths.py").is_file()
    assert (REPO_ROOT / "main.py").is_file()


@pytest.mark.parametrize(
    "name",
    ["DATA_DIR", "CORPUS_DIR", "EVALUATION_DIR", "LOGS_DIR", "OUTPUTS_DIR",
     "CACHE_DIR", "CHROMA_DIR"],
)
def test_directories_are_absolute_and_under_root(name):
    value = getattr(paths, name)
    assert value.is_absolute(), f"{name}={value}"
    assert value == value.resolve(), f"{name}={value} chưa được chuẩn hóa"
    assert REPO_ROOT in value.parents or value == REPO_ROOT, f"{name}={value} nằm ngoài gốc"


def test_default_layout_matches_repository():
    # So với tên thư mục thật trong repo, không dựa vào CWD của pytest.
    assert paths.DATA_DIR == REPO_ROOT / "data"
    assert paths.CORPUS_DIR == REPO_ROOT / "data" / "corpus"
    assert paths.EVALUATION_DIR == REPO_ROOT / "data" / "evaluation"
    assert paths.LEARNING_DIR == REPO_ROOT / "data" / "learning"
    assert paths.LOGS_DIR == REPO_ROOT / "logs"
    assert paths.OUTPUTS_DIR == REPO_ROOT / "outputs"
    assert paths.CHROMA_DIR == REPO_ROOT / "chroma_db"
    assert paths.OCR_CACHE_DIR == REPO_ROOT / ".cache" / "ocr" / "rapidocr"


def _chay_paths(cwd, env_extra=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.pop("PYTHONIOENCODING", None)
    for key in (
        "RAG_DATA_DIR", "RAG_CORPUS_DIR", "RAG_EVALUATION_DIR", "RAG_LOGS_DIR",
        "RAG_OUTPUTS_DIR", "RAG_CACHE_DIR", "CHROMA_PERSIST_DIR",
    ):
        env.pop(key, None)
    env.update(env_extra or {})
    code = (
        "import json, src.core.paths as p;"
        "print(json.dumps({k: str(getattr(p, k)) for k in "
        "['PROJECT_ROOT','DATA_DIR','CORPUS_DIR','LOGS_DIR','CHROMA_DIR']}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
    )
    assert out.returncode == 0, out.stderr
    import json

    return json.loads(out.stdout.strip().splitlines()[-1])


def test_import_from_another_cwd_still_points_to_project_root(tmp_path):
    from_root = _chay_paths(REPO_ROOT)
    from_other = _chay_paths(tmp_path)
    assert from_other == from_root
    assert from_other["PROJECT_ROOT"] == str(REPO_ROOT)


def test_relative_env_override_resolves_against_project_root(tmp_path):
    got = _chay_paths(
        tmp_path,
        {
            "RAG_DATA_DIR": "alt_data",
            "RAG_CORPUS_DIR": "alt_corpus",
            "RAG_LOGS_DIR": "alt_logs",
            "CHROMA_PERSIST_DIR": "./alt_chroma",
        },
    )
    assert got["DATA_DIR"] == str(REPO_ROOT / "alt_data")
    assert got["CORPUS_DIR"] == str(REPO_ROOT / "alt_corpus")
    assert got["LOGS_DIR"] == str(REPO_ROOT / "alt_logs")
    assert got["CHROMA_DIR"] == str(REPO_ROOT / "alt_chroma")


def test_absolute_env_override_is_kept(tmp_path):
    target = tmp_path / "custom_data"
    got = _chay_paths(tmp_path, {"RAG_DATA_DIR": str(target)})
    assert got["DATA_DIR"] == str(target)


def test_query_normalizer_uses_shared_paths():
    from src.core import query_normalizer

    assert query_normalizer.NORMALIZATION_PAIRS_PATH == paths.LEARNING_DIR / "normalization_pairs.json"
    assert query_normalizer.GHI_CHU_HOC_THEM_PATH == paths.CORPUS_DIR / "ghi_chu_hoc_them.txt"
    assert query_normalizer.BENCHMARK_QUESTIONS_PATH == paths.EVALUATION_DIR / "benchmark_questions.json"


def test_evaluation_uses_shared_paths():
    from src.assessment import evaluation

    assert evaluation.BENCHMARK_PATH == paths.EVALUATION_DIR / "benchmark_100_questions_v2.json"
    assert evaluation.RESULTS_PATH == paths.OUTPUTS_DIR / "evaluation_results.json"
    assert evaluation.SUMMARY_PATH == paths.OUTPUTS_DIR / "evaluation_summary.md"


def test_loader_defaults_use_shared_paths():
    from src.indexing import loader

    assert loader.DEFAULT_CACHE_DIR == str(paths.OCR_CACHE_DIR)
    assert loader.DocumentLoader.__init__.__defaults__[0] == str(paths.CORPUS_DIR)


def test_ingest_module_is_wired_to_shared_paths():
    """Ingest không được gọi ở đây; chỉ kiểm nó import hằng số dùng chung."""
    import importlib

    ingest = importlib.import_module("ingest")
    assert ingest.CHROMA_DIR == paths.CHROMA_DIR
    assert ingest.CORPUS_DIR == paths.CORPUS_DIR
