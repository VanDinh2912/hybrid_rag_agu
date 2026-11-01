# -*- coding: utf-8 -*-
"""PA-29 + PA-16: dry-run/xác nhận cho script CLI và cổng bảo vệ index.

Ba tầng được ghim:

1. `ingest.py --dry-run` chỉ ĐỌC metadata (không mở ChromaDB, không gọi `run_ingestion`).
2. `run_ingestion(reset=True)` từ chối xoá thư mục đã có dữ liệu khi `INGEST_ALLOW_RESET`
   chưa bật; CLI còn đòi `--yes` (hoặc trả lời `yes`) khi cờ đã bật. GUI đã hỏi `askyesno`
   nên được truyền `allow_reset=True` — test ở `test_ui_split_modules.py`.
3. `scripts/learn.py` và `src/assessment/analyze_ab.py` có `--dry-run` không ghi gì;
   `--help` của cả ba script trả mã 0. Máy kiểm tài liệu miễn `--help` cho script GUI
   (`HELP_WHITELIST`) và không truyền khoá API xuống tiến trình con.

Mọi test chạy trên thư mục tạm; không đụng `chroma_db/` thật.
"""

from __future__ import annotations

import builtins
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import ingest as ing
import scripts.learn as learn
from src.assessment import analyze_ab
from tools.diag import docs_consistency_check as dc


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------

def _snapshot(directory: Path) -> dict[str, tuple[str, int]]:
    """Tên tệp → (sha256, mtime_ns): chứng minh dry-run không tái ghi byte nào."""
    out: dict[str, tuple[str, int]] = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(directory))] = (
                hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
    return out


def _make_index(tmp_path: Path) -> Path:
    idx = tmp_path / "idx"
    (idx / "nested").mkdir(parents=True)
    (idx / "chroma.sqlite3").write_bytes(b"fake-chroma-bytes")
    (idx / "nested" / "segment.bin").write_bytes(b"0123456789")
    return idx


def _make_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.txt").write_text("Điều 1. Nội dung", encoding="utf-8")
    (corpus / "b.pdf").write_bytes(b"%PDF-1.4")
    (corpus / "bo_qua.json").write_text("{}", encoding="utf-8")
    return corpus


def _boom(*_args, **_kwargs):
    raise AssertionError("đường này không được chạy trong dry-run")


# ---------------------------------------------------------------------------
# ingest.py — dry-run
# ---------------------------------------------------------------------------

class TestIngestDryRun:
    def test_dry_run_khong_ghi_khong_mo_db(self, monkeypatch, tmp_path, capsys):
        idx = _make_index(tmp_path)
        corpus = _make_corpus(tmp_path)
        monkeypatch.setattr(ing, "CHROMA_DIR", idx)
        monkeypatch.setattr(ing, "CORPUS_DIR", corpus)
        monkeypatch.delenv(ing.ALLOW_RESET_ENV, raising=False)
        monkeypatch.setattr(ing, "run_ingestion", _boom)
        monkeypatch.setattr(ing, "VectorStoreManager", _boom)

        before = _snapshot(idx)
        assert ing.main(["--dry-run"]) == 0
        out = capsys.readouterr().out

        assert "[DRY-RUN]" in out
        assert "2 tệp .txt/.pdf/.docx" in out          # .json không tính
        assert "TỪ CHỐI" in out                        # index có dữ liệu, cờ TẮT
        assert "KHÔNG đọc" in out
        assert _snapshot(idx) == before

    def test_dry_run_index_rong_bao_khong_can_xoa(self, monkeypatch, tmp_path, capsys):
        idx = tmp_path / "idx"
        idx.mkdir()
        monkeypatch.setattr(ing, "CHROMA_DIR", idx)
        monkeypatch.setattr(ing, "CORPUS_DIR", _make_corpus(tmp_path))
        monkeypatch.delenv(ing.ALLOW_RESET_ENV, raising=False)
        monkeypatch.setattr(ing, "run_ingestion", _boom)

        assert ing.main(["--dry-run"]) == 0
        assert "không cần xoá" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# PA-16 — cổng env + --yes
# ---------------------------------------------------------------------------

class TestIndexResetGuard:
    def test_index_co_du_lieu_bi_tu_choi(self, monkeypatch, tmp_path):
        idx = _make_index(tmp_path)
        monkeypatch.setattr(ing, "CHROMA_DIR", idx)
        monkeypatch.delenv(ing.ALLOW_RESET_ENV, raising=False)

        with pytest.raises(ing.IndexResetRefused) as excinfo:
            ing.run_ingestion(reset=True)
        assert ing.ALLOW_RESET_ENV in str(excinfo.value)
        assert (idx / "chroma.sqlite3").exists()       # chưa bị xoá

    def test_describe_reset_env_bat_thi_se_xoa(self, monkeypatch, tmp_path):
        idx = _make_index(tmp_path)
        monkeypatch.setattr(ing, "CHROMA_DIR", idx)
        monkeypatch.delenv(ing.ALLOW_RESET_ENV, raising=False)
        plan_off = ing.describe_reset(str(idx))
        assert plan_off["refused"] and not plan_off["will_delete"]

        monkeypatch.setenv(ing.ALLOW_RESET_ENV, "1")
        plan_on = ing.describe_reset(str(idx))
        assert plan_on["will_delete"] and not plan_on["refused"]
        # đường GUI: xác nhận riêng ⇒ cho qua dù env TẮT
        monkeypatch.delenv(ing.ALLOW_RESET_ENV, raising=False)
        assert ing.reset_guard(str(idx), allow_reset=True)["non_empty"] is True

    def test_index_rong_khong_can_co(self, monkeypatch, tmp_path):
        idx = tmp_path / "idx"
        idx.mkdir()
        monkeypatch.delenv(ing.ALLOW_RESET_ENV, raising=False)
        plan = ing.reset_guard(str(idx))
        assert plan["non_empty"] is False and plan["refused"] is False

    def test_run_ingestion_chuyen_allow_reset_xuong_guard(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ing, "CHROMA_DIR", tmp_path / "idx")
        seen = {}

        class _Stop(RuntimeError):
            pass

        def _guard(persist_dir, *, allow_reset=False):
            seen.update(persist_dir=persist_dir, allow_reset=allow_reset)
            raise _Stop

        monkeypatch.setattr(ing, "reset_guard", _guard)
        with pytest.raises(_Stop):
            ing.run_ingestion(reset=True, allow_reset=True)
        assert seen["allow_reset"] is True
        assert seen["persist_dir"].endswith("idx")

    def test_cli_env_tat_thi_systemexit_va_khong_xoa(self, monkeypatch, tmp_path):
        idx = _make_index(tmp_path)
        monkeypatch.setattr(ing, "CHROMA_DIR", idx)
        monkeypatch.delenv(ing.ALLOW_RESET_ENV, raising=False)
        monkeypatch.setattr(ing, "run_ingestion", _boom)

        with pytest.raises(SystemExit) as excinfo:
            ing.main([])
        assert "từ chối xoá" in str(excinfo.value)
        assert (idx / "chroma.sqlite3").read_bytes() == b"fake-chroma-bytes"

    def test_cli_env_bat_stdin_khong_tuong_tac_doi_yes(self, monkeypatch, tmp_path):
        idx = _make_index(tmp_path)
        monkeypatch.setattr(ing, "CHROMA_DIR", idx)
        monkeypatch.setenv(ing.ALLOW_RESET_ENV, "1")
        monkeypatch.setattr(ing, "run_ingestion", _boom)
        monkeypatch.setattr(ing.sys, "stdin", SimpleNamespace(isatty=lambda: False))

        with pytest.raises(SystemExit) as excinfo:
            ing.main([])
        assert "--yes" in str(excinfo.value)
        assert (idx / "chroma.sqlite3").exists()

    def test_cli_env_bat_tra_loi_khong_thi_huy(self, monkeypatch, tmp_path):
        idx = _make_index(tmp_path)
        monkeypatch.setattr(ing, "CHROMA_DIR", idx)
        monkeypatch.setenv(ing.ALLOW_RESET_ENV, "1")
        monkeypatch.setattr(ing, "run_ingestion", _boom)
        monkeypatch.setattr(ing.sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "khong")

        with pytest.raises(SystemExit) as excinfo:
            ing.main([])
        assert "huỷ" in str(excinfo.value)
        assert (idx / "chroma.sqlite3").exists()

    def test_cli_yes_sau_xac_nhan_chay_tiep(self, monkeypatch, tmp_path, capsys):
        idx = _make_index(tmp_path)
        monkeypatch.setattr(ing, "CHROMA_DIR", idx)
        monkeypatch.setenv(ing.ALLOW_RESET_ENV, "1")
        captured = {}

        def _fake_run(**kwargs):
            captured.update(kwargs)
            return (SimpleNamespace(persist_directory="idx"),
                    SimpleNamespace(_collection=SimpleNamespace(count=lambda: 5)), 5)

        monkeypatch.setattr(ing, "run_ingestion", _fake_run)
        assert ing.main(["--yes"]) == 0
        assert captured["allow_reset"] is True
        assert "THÀNH CÔNG: 5/5" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# learn.py / analyze_ab.py — --dry-run & --help
# ---------------------------------------------------------------------------

class TestLearnDryRun:
    def test_dry_run_khong_mo_chromadb_hay_goi_model(self, monkeypatch, tmp_path, capsys):
        idx = _make_index(tmp_path)
        corpus = _make_corpus(tmp_path)
        monkeypatch.setattr(learn, "CHROMA_DIR", idx)
        monkeypatch.setattr(learn, "CORPUS_DIR", corpus)
        monkeypatch.setattr(learn, "NOTES_PATH", str(tmp_path / "ghi_chu.txt"))
        monkeypatch.setattr(learn, "LOG_PATH", str(tmp_path / "learning_log.csv"))
        monkeypatch.setattr(learn, "VectorStoreManager", _boom)
        monkeypatch.setattr(learn, "HybridRAGPipeline", _boom)
        monkeypatch.setattr(learn, "LocalSLM", _boom)

        before = _snapshot(tmp_path)
        assert learn.main(["--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "[DRY-RUN]" in out
        assert "2 tệp .txt/.pdf/.docx" in out
        assert "KHÔNG đọc" in out
        assert _snapshot(tmp_path) == before


class TestAnalyzeAbDryRun:
    def test_dry_run_khong_ghi_outputs(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(analyze_ab, "ROOT", tmp_path)
        bench = tmp_path / "bench.json"
        bench.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(analyze_ab, "BENCH_PATH", bench)
        monkeypatch.setattr(analyze_ab, "WITHOUT_PATH", tmp_path / "wo.json")
        monkeypatch.setattr(analyze_ab, "WITH_PATH", tmp_path / "w.json")
        monkeypatch.setattr(analyze_ab, "CLASSIFIER_RESULTS", tmp_path / "cls.json")
        out_md = tmp_path / "outputs" / "ab_comparison.md"
        fig_dir = tmp_path / "outputs" / "figures"
        monkeypatch.setattr(analyze_ab, "OUT_MD", out_md)
        monkeypatch.setattr(analyze_ab, "FIG_DIR", fig_dir)
        monkeypatch.setattr(analyze_ab, "load_all", _boom)

        assert analyze_ab.main(["--dry-run"]) == 0
        text = capsys.readouterr().out
        assert "[DRY-RUN]" in text
        assert "bench.json" in text and "THIẾU" in text
        assert not out_md.exists() and not fig_dir.exists()


@pytest.mark.parametrize("module", [ing, learn, analyze_ab], ids=["ingest", "learn", "analyze_ab"])
def test_help_tra_ma_0(module):
    with pytest.raises(SystemExit) as excinfo:
        module.parse_args(["--help"])
    assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# docs_consistency_check — whitelist GUI + dọn env bí mật
# ---------------------------------------------------------------------------

def _minimal_repo(root: Path, readme: str) -> Path:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "DECISION_LOG.md").write_text(
        "| ID | Ngày | Giả thuyết | Số đo quyết định | Nguồn | Trạng thái |\n|---|---|---|---|---|---|\n",
        encoding="utf-8")
    (root / "docs" / "planning").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "planning" / "ROADMAP.md").write_text("# Lộ trình\n", encoding="utf-8")
    (root / "README.md").write_text(readme, encoding="utf-8")
    return root


class TestCheckerHelpWhitelist:
    def test_script_gui_duoc_mien_help(self, tmp_path):
        root = _minimal_repo(tmp_path, "# A\n\n```bash\npython ui/app.py\n```\n")
        (root / "ui").mkdir()
        (root / "ui" / "app.py").write_text("import tkinter\n", encoding="utf-8")

        out = dc.check_all(root)
        assert out["command_warnings"] == []
        assert out["help_exempt"] == ["ui/app.py"]
        assert any("miễn --help" in n for n in out["notes"])

    def test_script_thuong_khong_argparse_van_la_canh_bao(self, tmp_path):
        root = _minimal_repo(tmp_path, "# A\n\n```bash\npython scripts/plain.py\n```\n")
        (root / "scripts").mkdir()
        (root / "scripts" / "plain.py").write_text("print('x')\n", encoding="utf-8")

        out = dc.check_all(root)
        assert any("scripts/plain.py" in w for w in out["command_warnings"])
        assert out["help_exempt"] == []


def test_run_help_khong_truyen_khoa_api(monkeypatch, tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "envcheck.py").write_text(
        "import os, sys\n"
        "keys = ('GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_GENAI_API_KEY','HF_TOKEN','HUGGING_FACE_HUB_TOKEN')\n"
        "sys.exit(1 if any(os.environ.get(k) for k in keys) else 0)\n",
        encoding="utf-8")
    for key in dc.SECRET_ENV:
        monkeypatch.setenv(key, "secret")

    res = dc.run_help(tmp_path, ["tools/envcheck.py"])
    assert res[0]["rc"] == 0, res[0]["stderr_tail"]