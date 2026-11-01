"""Duyệt hàng đợi phản hồi (hardening 01-11): dry-run, áp tệp, cổng index, hoán đổi.

Không chạy `ingest.py` thật và không gọi model: `rebuild_index` được thay bằng hàm dựng
SQLite giả cùng schema tối thiểu mà `corpus_index_manifest` đọc. Mọi đường dẫn đích đều
trỏ vào `tmp_path`, nên test không chạm `chroma_db`/`data/` của repo.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

import ui.feedback_controller as fc
from tools.diag import feedback_promote as promote


# ------------------------------------------------------------------- dựng dữ liệu giả
def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _make_index(index_dir, sources):
    index_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(index_dir / "chroma.sqlite3"))
    con.executescript(
        "create table collections(id text primary key, name text);"
        "create table embedding_metadata(id text, key text, string_value text,"
        " int_value integer, float_value real, bool_value integer);"
        "create table embeddings(id text primary key);"
    )
    con.execute("insert into collections values ('c1', 'agu_regulations')")
    n = 0
    for name, count in sources.items():
        for _ in range(count):
            n += 1
            con.execute("insert into embeddings values (?)", (f"e{n}",))
            con.execute(
                "insert into embedding_metadata values (?, 'source', ?, null, null, null)",
                (f"e{n}", name),
            )
    con.commit()
    con.close()


def _queue_record(raw_query, requested, **overrides):
    data = {
        "raw_query": raw_query,
        "normalized_query": f"{raw_query} (chuẩn)",
        "answer": "trả lời cũ",
        "sources": [],
    }
    kwargs = dict(
        ground_truth="đáp án trần",
        citation="Điều 1",
        source_doc="1054.pdf",
        normalized_truth="câu chuẩn hóa?",
        requested=requested,
    )
    kwargs.update(overrides)
    return fc.queue_record(data, "wrong", "Đáp án chuẩn: đáp án trần\nCăn cứ: Điều 1", **kwargs)


def _setup(tmp_path, requested, *, with_target=True):
    corpus = tmp_path / "corpus"
    _write(corpus / "a.pdf")
    _write(corpus / "b.txt")
    queue_dir = tmp_path / "queue"
    fc.enqueue_feedback(queue_dir, _queue_record("học phí bao nhiêu?", requested))
    benchmark = _write(tmp_path / "benchmark.json", '{"version": "2.1", "questions": []}')
    pairs = _write(tmp_path / "pairs.json", '{"version": "1.1", "pairs": []}')
    notes = corpus / "ghi_chu_hoc_them.txt"
    target = tmp_path / "chroma_db"
    old_marker = None
    if with_target:
        target.mkdir(parents=True)
        old_marker = _write(target / "OLD_MARKER.txt", "index cũ")
    work = tmp_path / "work"
    return {
        "corpus": corpus, "queue": queue_dir, "benchmark": benchmark, "pairs": pairs,
        "notes": notes, "target": target, "old_marker": old_marker, "work": work,
        "benchmark_before": benchmark.read_text(encoding="utf-8"),
        "pairs_before": pairs.read_text(encoding="utf-8"),
    }


def _args(data, *extra):
    return [
        "--queue-dir", str(data["queue"]), "--corpus", str(data["corpus"]),
        "--target-index", str(data["target"]), "--benchmark", str(data["benchmark"]),
        "--pairs", str(data["pairs"]), "--notes", str(data["notes"]),
        "--work-dir", str(data["work"]), *extra,
    ]


def _fake_rebuild(corpus, sources_from_corpus=True):
    """Trả hàm rebuild giả: dựng index mới từ đúng các tệp corpus hiện có."""
    def _rebuild(new_index, _log_path):
        if sources_from_corpus:
            names = sorted(p.name for p in corpus.rglob("*") if p.is_file())
        else:
            names = sorted(p.name for p in corpus.rglob("*") if p.is_file())[:-1]  # thiếu 1 tệp
        _make_index(new_index, {name: 1 for name in names})
        return 0
    return _rebuild


# ---------------------------------------------------------------------------- dry-run
def test_mac_dinh_chi_in_ke_hoach_khong_ghi_gi(tmp_path, capsys, monkeypatch):
    data = _setup(tmp_path, {"benchmark": True, "normalization_pair": True, "corpus_note": False})
    monkeypatch.setattr(promote, "rebuild_index", lambda *_a, **_k: pytest.fail("dry-run không rebuild"))

    rc = promote.main(_args(data))

    assert rc == 0
    assert data["benchmark"].read_text(encoding="utf-8") == data["benchmark_before"]
    assert len(list(data["queue"].glob("*.json"))) == 1
    assert not data["work"].exists()
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "benchmark_questions.json" in out


def test_json_dry_run_hop_le(tmp_path, capsys):
    data = _setup(tmp_path, {"benchmark": True})

    assert promote.main(_args(data, "--json")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["records"] == 1
    assert payload["needs_rebuild"] is False
    assert payload["items"][0]["requested"]["benchmark"] is True


def test_hang_doi_co_tep_hong_thi_dung_truoc_khi_ap(tmp_path, capsys):
    data = _setup(tmp_path, {"benchmark": True})
    (data["queue"] / "zzz-hong.json").write_text("{ hong", encoding="utf-8")

    rc = promote.main(_args(data, "--apply", "--yes"))

    assert rc == 1
    assert data["benchmark"].read_text(encoding="utf-8") == data["benchmark_before"]
    assert "TỆP HỎNG" in capsys.readouterr().out


def test_apply_thieu_yes_thi_khong_lam_gi(tmp_path):
    data = _setup(tmp_path, {"benchmark": True})

    assert promote.main(_args(data, "--apply")) == 2
    assert data["benchmark"].read_text(encoding="utf-8") == data["benchmark_before"]
    assert len(list(data["queue"].glob("*.json"))) == 1


# ------------------------------------------------------------------- áp không cần rebuild
def test_apply_ghi_benchmark_va_pairs_roi_dong_hang_doi(tmp_path, monkeypatch):
    data = _setup(tmp_path, {"benchmark": True, "normalization_pair": True, "corpus_note": False})
    monkeypatch.setattr(promote, "rebuild_index", lambda *_a, **_k: pytest.fail("không có corpus_note"))

    assert promote.main(_args(data, "--apply", "--yes")) == 0

    benchmark = json.loads(data["benchmark"].read_text(encoding="utf-8"))
    assert benchmark["questions"][0]["expected_answer"] == "đáp án trần"
    assert benchmark["questions"][0]["source_document"] == "1054.pdf"
    pairs = json.loads(data["pairs"].read_text(encoding="utf-8"))
    assert pairs["pairs"][0]["normalized_query"] == "câu chuẩn hóa?"
    assert not data["notes"].exists()  # không xin corpus_note ⇒ không ghi bài học
    assert list(data["queue"].glob("*.json")) == []
    applied = list((data["queue"] / "applied").glob("*/*.json"))
    assert len(applied) == 1


# ------------------------------------------------------- áp + rebuild + cổng + hoán đổi
def test_apply_co_corpus_note_dung_index_moi_chay_cong_roi_hoan_doi(tmp_path, monkeypatch):
    data = _setup(tmp_path, {"corpus_note": True})
    monkeypatch.setattr(promote, "referee_fingerprint", lambda: promote.EXPECTED_REFEREE_FINGERPRINT)
    monkeypatch.setattr(promote, "rebuild_index", _fake_rebuild(data["corpus"]))

    assert promote.main(_args(data, "--apply", "--yes")) == 0

    assert (data["target"] / "chroma.sqlite3").is_file()
    assert (data["work"] / "chroma_db_before" / "OLD_MARKER.txt").is_file()
    assert not (data["target"] / "OLD_MARKER.txt").exists()
    assert "Ghi chú học thêm" in data["notes"].read_text(encoding="utf-8")
    assert data["benchmark"].read_text(encoding="utf-8") == data["benchmark_before"]
    assert data["pairs"].read_text(encoding="utf-8") == data["pairs_before"]
    assert list(data["queue"].glob("*.json")) == []


def test_rebuild_hong_thi_tra_tep_hoc_ve_va_khong_hoan_doi(tmp_path, monkeypatch, capsys):
    data = _setup(tmp_path, {"benchmark": True, "corpus_note": True})
    monkeypatch.setattr(promote, "rebuild_index", lambda *_a, **_k: 3)

    rc = promote.main(_args(data, "--apply", "--yes"))

    assert rc == 1
    assert data["benchmark"].read_text(encoding="utf-8") == data["benchmark_before"]
    assert not data["notes"].exists()
    assert data["old_marker"].is_file()
    assert len(list(data["queue"].glob("*.json"))) == 1
    assert "ingest.py trả mã 3" in capsys.readouterr().out


def test_cong_do_thi_khong_hoan_doi_va_tra_tep_ve(tmp_path, monkeypatch, capsys):
    data = _setup(tmp_path, {"corpus_note": True})
    monkeypatch.setattr(promote, "referee_fingerprint", lambda: promote.EXPECTED_REFEREE_FINGERPRINT)
    # Index mới thiếu một tệp corpus ⇒ corpus_index_manifest báo lệch.
    monkeypatch.setattr(promote, "rebuild_index", _fake_rebuild(data["corpus"], sources_from_corpus=False))

    rc = promote.main(_args(data, "--apply", "--yes"))

    assert rc == 1
    assert data["old_marker"].is_file()
    assert not data["notes"].exists()
    assert len(list(data["queue"].glob("*.json"))) == 1
    assert "CỔNG ĐỎ" in capsys.readouterr().out


def test_fingerprint_sai_la_cong_do(tmp_path, monkeypatch):
    data = _setup(tmp_path, {"corpus_note": True})
    monkeypatch.setattr(promote, "referee_fingerprint", lambda: "deadbeef0000")
    monkeypatch.setattr(promote, "rebuild_index", _fake_rebuild(data["corpus"]))

    assert promote.main(_args(data, "--apply", "--yes")) == 1
    assert data["old_marker"].is_file()


def test_khong_cho_dung_thu_muc_bao_ve_lam_index_moi(tmp_path, monkeypatch):
    data = _setup(tmp_path, {"corpus_note": True})
    monkeypatch.setattr(promote, "rebuild_index", lambda *_a, **_k: pytest.fail("không được rebuild"))
    # Đích nằm trong `chroma_db` của repo ⇒ ensure_separate_index_target phải từ chối.
    args = _args(data, "--apply", "--yes")
    args[args.index("--work-dir") + 1] = str(promote.ROOT / "chroma_db")

    assert promote.main(args) == 1
    assert data["benchmark"].read_text(encoding="utf-8") == data["benchmark_before"]
    assert len(list(data["queue"].glob("*.json"))) == 1


# -------------------------------------------------------------------------- hàm thuần
def test_swap_tu_choi_index_moi_khong_co_sqlite(tmp_path):
    new = tmp_path / "new"
    new.mkdir()
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(promote.PromoteError):
        promote.swap_index(new, target, tmp_path / "backup")
    assert target.is_dir()


def test_plan_liet_ke_dung_muc_duoc_yeu_cau(tmp_path):
    records = [
        (tmp_path / "a.json", _queue_record("câu 1", {"benchmark": True})),
        (tmp_path / "b.json", _queue_record("câu 2", {"corpus_note": True})),
    ]

    dry = promote.plan(records)

    assert dry["records"] == 2
    assert dry["needs_rebuild"] is True
    assert dry["targets"] == ["benchmark_questions.json", "ghi_chu_hoc_them.txt + rebuild index"]
