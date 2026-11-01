"""Đối chiếu corpus ↔ index (hardening 01-11): thuần đọc, phát hiện lệch.

Index giả dựng bằng SQLite tối thiểu: công cụ chỉ đọc `collections`, `embedding_metadata`
(key `source`) và đếm `embeddings`, nên test không cần ChromaDB thật và không mở client.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

from tools.diag import corpus_index_manifest as cim


def _write(path, text: str = "x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _make_index(index_dir, sources: dict[str, int]):
    """chroma.sqlite3 giả: mỗi nguồn `sources[name]` embedding + metadata `source`."""
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


def _corpus(tmp_path):
    corpus = tmp_path / "corpus"
    _write(corpus / "a.pdf", "noi dung a")
    _write(corpus / "sub" / "b.txt", "noi dung b")
    _write(corpus / "ghi-chu.md", "khong phai corpus")
    return corpus


def test_liet_ke_dung_duoi_tep_va_sha256(tmp_path):
    corpus = _corpus(tmp_path)

    entries = cim.corpus_entries(corpus)

    assert [e["rel"] for e in entries] == ["a.pdf", "sub/b.txt"]
    expect = hashlib.sha256("noi dung a".encode("utf-8")).hexdigest()
    assert entries[0]["sha256"] == expect
    assert entries[0]["bytes"] == len("noi dung a")


def test_bao_dung_da_nap_chua_nap_va_nguon_la(tmp_path):
    corpus = _corpus(tmp_path)
    index = tmp_path / "index"
    _make_index(index, {"a.pdf": 3, "la.pdf": 1})

    manifest = cim.build_manifest(corpus, index)
    status = {e["rel"]: (e["status"], e["chunks"]) for e in manifest["files"]}

    assert status == {"a.pdf": ("đã nạp", 3), "sub/b.txt": ("chưa nạp", 0)}
    assert manifest["unindexed"] == ["sub/b.txt"]
    assert manifest["orphan"] == ["la.pdf"]
    assert manifest["chunk_total"] == 4
    assert manifest["collections"] == ["agu_regulations"]
    assert manifest["ok"] is False
    assert any("CHƯA nạp" in reason for reason in manifest["reasons"])
    assert any("KHÔNG có trong corpus" in reason for reason in manifest["reasons"])


def test_ten_tep_trung_khong_doan_da_nap_tep_nao(tmp_path):
    corpus = tmp_path / "corpus"
    _write(corpus / "x" / "trung.pdf")
    _write(corpus / "y" / "trung.pdf")
    index = tmp_path / "index"
    _make_index(index, {"trung.pdf": 2})

    manifest = cim.build_manifest(corpus, index)

    assert {e["status"] for e in manifest["files"]} == {"trùng tên"}
    assert manifest["duplicate_basenames"] == ["trung.pdf"]
    assert manifest["ok"] is False


def test_khong_co_index_thi_moi_tep_deu_chua_nap(tmp_path):
    corpus = _corpus(tmp_path)

    manifest = cim.build_manifest(corpus, tmp_path / "khong-co")

    assert manifest["index_ok"] is False
    assert manifest["chunk_total"] == 0
    assert {e["status"] for e in manifest["files"]} == {"chưa nạp"}
    assert any("không đọc được index" in reason for reason in manifest["reasons"])
    assert manifest["ok"] is False


def test_index_rong_la_lech_du_moi_nguon_khop(tmp_path):
    corpus = tmp_path / "corpus"
    _write(corpus / "a.pdf")
    index = tmp_path / "index"
    _make_index(index, {})

    manifest = cim.build_manifest(corpus, index)

    assert manifest["index_ok"] is True
    assert manifest["ok"] is False
    assert any("rỗng" in reason for reason in manifest["reasons"])


def test_khop_hoan_toan_thi_ok(tmp_path):
    corpus = tmp_path / "corpus"
    _write(corpus / "a.pdf")
    _write(corpus / "b.docx")
    index = tmp_path / "index"
    _make_index(index, {"a.pdf": 2, "b.docx": 1})

    manifest = cim.build_manifest(corpus, index)

    assert manifest["ok"] is True
    assert manifest["reasons"] == []


def test_chi_doc_khong_tai_ghi_index(tmp_path):
    """PA-60: công cụ không được đổi byte index — kiểm bằng sha trước/sau."""
    corpus = tmp_path / "corpus"
    _write(corpus / "a.pdf")
    index = tmp_path / "index"
    _make_index(index, {"a.pdf": 1})
    db = index / "chroma.sqlite3"
    before = db.read_bytes()

    cim.build_manifest(corpus, index)

    assert db.read_bytes() == before
    assert sorted(p.name for p in index.iterdir()) == ["chroma.sqlite3"]


def test_main_check_tra_ma_1_khi_lech_va_0_khi_khop(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    _write(corpus / "a.pdf")
    index = tmp_path / "index"
    _make_index(index, {"a.pdf": 1})

    assert cim.main(["--corpus", str(corpus), "--index", str(index), "--check"]) == 0

    _write(corpus / "moi.pdf")
    assert cim.main(["--corpus", str(corpus), "--index", str(index), "--check"]) == 1
    assert "LỆCH" in capsys.readouterr().out


def test_main_json_la_json_hop_le(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    _write(corpus / "a.pdf")
    index = tmp_path / "index"
    _make_index(index, {"a.pdf": 1})

    rc = cim.main(["--corpus", str(corpus), "--index", str(index), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["files"][0]["status"] == "đã nạp"
