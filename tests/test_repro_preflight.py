# -*- coding: utf-8 -*-
"""Test cho `tools/diag/repro_preflight.py` — cổng chặn 2 hư hỏng âm thầm của 31-10.

Hai hư hỏng thật đã xảy ra và không cổng nào bắt được:

1. `chroma_db/` bị dựng lại thành 443 chunk (mọi số neo 361 mất hiệu lực);
2. `data/training/` (gitignore + ngoài manifest) bị tái sinh 1.635 → 2.089 dòng.

Test chạy trên **cây giả trong `tmp_path`** (sqlite tự dựng, tệp nhỏ) — không mở index thật,
không gọi model, không đọc `.env`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.diag import repro_preflight as rp


def _mk_chroma(path: Path, chunks: int, sources: int, tiers: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE embeddings (id TEXT PRIMARY KEY)")
    con.execute(
        "CREATE TABLE embedding_metadata (id INTEGER, key TEXT, string_value TEXT, "
        "int_value INTEGER, float_value REAL, bool_value INTEGER)"
    )
    for i in range(chunks):
        con.execute("INSERT INTO embeddings (id) VALUES (?)", (f"c{i}",))
    tier_cycle = [t for t, n in tiers.items() for _ in range(n)]
    for i in range(chunks):
        src = f"src-{i % max(sources, 1)}"
        con.execute("INSERT INTO embedding_metadata VALUES (?,?,?,?,?,?)",
                    (i, "source", src, None, None, None))
        con.execute("INSERT INTO embedding_metadata VALUES (?,?,?,?,?,?)",
                    (i, "tier", tier_cycle[i % len(tier_cycle)], None, None, None))
    con.commit()
    con.close()


def _mk_tree(root: Path, *, chunks=6, sources=3, tiers=None, corpus_files=3, train_rows=4):
    tiers = tiers or {"Tầng 1": chunks}
    _mk_chroma(root / "chroma_db" / "chroma.sqlite3", chunks, sources, tiers)
    corpus = root / "data" / "corpus"
    for i in range(corpus_files):
        (corpus / f"t{i}.pdf").parent.mkdir(parents=True, exist_ok=True)
        (corpus / f"t{i}.pdf").write_bytes(b"%PDF-1.4")
    train = root / "data" / "training"
    train.mkdir(parents=True, exist_ok=True)
    (train / "sft_train.jsonl").write_text("".join('{"a":1}\n' for _ in range(train_rows)),
                                           encoding="utf-8")
    (train / "note.md").write_text("x", encoding="utf-8")
    return root


def _pins_for(root: Path) -> dict:
    chroma = rp.read_chroma_facts(root / "chroma_db" / "chroma.sqlite3")
    chroma["sha256"] = {
        str(p.relative_to(root)).replace("\\", "/"): rp.sha256_file(p)
        for p in sorted((root / "chroma_db").rglob("*")) if p.is_file()
    }
    return {
        "chroma_db": chroma,
        "corpus": rp.count_corpus(root / "data" / "corpus"),
        "data_training": rp.count_training(root / "data" / "training"),
    }


def _levels(rows):
    return {lvl for lvl, _ in rows}


def test_facts_va_pin_khop_thi_khong_hong(tmp_path):
    root = _mk_tree(tmp_path)
    pins = _pins_for(root)
    rows = rp.evaluate(
        pins,
        rp.read_chroma_facts(root / "chroma_db" / "chroma.sqlite3"),
        rp.count_corpus(root / "data" / "corpus"),
        rp.count_training(root / "data" / "training"),
        pins["chroma_db"]["sha256"],
        None,
    )
    assert rp.FAIL not in _levels(rows), rows
    assert any("361" in m or "6 chunk" in m for _, m in rows)


def test_index_bi_dung_lai_thi_HONG(tmp_path):
    root = _mk_tree(tmp_path)
    pins = _pins_for(root)
    # dựng lại index: 6 -> 9 chunk
    (root / "chroma_db" / "chroma.sqlite3").unlink()
    _mk_chroma(root / "chroma_db" / "chroma.sqlite3", 9, 3, {"Tầng 1": 9})
    rows = rp.evaluate(
        pins,
        rp.read_chroma_facts(root / "chroma_db" / "chroma.sqlite3"),
        rp.count_corpus(root / "data" / "corpus"),
        rp.count_training(root / "data" / "training"),
        {}, None,
    )
    assert any(lvl == rp.FAIL and "chunk" in m for lvl, m in rows), rows


def test_training_tai_sinh_thi_HONG(tmp_path):
    root = _mk_tree(tmp_path)
    pins = _pins_for(root)
    (root / "data" / "training" / "sft_train.jsonl").write_text('{"a":1}\n' * 9, encoding="utf-8")
    rows = rp.evaluate(
        pins,
        rp.read_chroma_facts(root / "chroma_db" / "chroma.sqlite3"),
        rp.count_corpus(root / "data" / "corpus"),
        rp.count_training(root / "data" / "training"),
        pins["chroma_db"]["sha256"],
        None,
    )
    assert any(lvl == rp.FAIL and "dòng" in m for lvl, m in rows), rows
    assert any(lvl == rp.FAIL and "byte lệch" in m for lvl, m in rows), rows


def test_byte_index_doi_chi_la_canh_bao(tmp_path):
    """PA-60: Chroma tái ghi byte khi mở — không được coi là hỏng tái lập."""
    root = _mk_tree(tmp_path)
    pins = _pins_for(root)
    rows = rp.evaluate(
        pins,
        rp.read_chroma_facts(root / "chroma_db" / "chroma.sqlite3"),
        rp.count_corpus(root / "data" / "corpus"),
        rp.count_training(root / "data" / "training"),
        {k: "deadbeef" for k in pins["chroma_db"]["sha256"]},
        None,
    )
    assert rp.FAIL not in _levels(rows)
    assert any(lvl == rp.WARN and "PA-60" in m for lvl, m in rows)


def test_corpus_nhieu_hon_index_thi_canh_bao_443(tmp_path):
    root = _mk_tree(tmp_path, corpus_files=5)
    pins = _pins_for(root)
    pins["corpus"]["files"] = 3          # pin theo lúc index được dựng
    rows = rp.evaluate(
        pins,
        rp.read_chroma_facts(root / "chroma_db" / "chroma.sqlite3"),
        rp.count_corpus(root / "data" / "corpus"),
        rp.count_training(root / "data" / "training"),
        pins["chroma_db"]["sha256"],
        None,
    )
    assert rp.FAIL not in _levels(rows)
    assert any(lvl == rp.WARN and "ingest.py" in m for lvl, m in rows)


def test_env_lever_va_skip_env_khac_nhau(tmp_path):
    root = _mk_tree(tmp_path)
    pins = _pins_for(root)
    args = (
        pins,
        rp.read_chroma_facts(root / "chroma_db" / "chroma.sqlite3"),
        rp.count_corpus(root / "data" / "corpus"),
        rp.count_training(root / "data" / "training"),
        pins["chroma_db"]["sha256"],
    )
    co_lever = rp.evaluate(*args, "b79d26b01345")
    assert any(lvl == rp.WARN and "b79d26b01345" in m for lvl, m in co_lever)
    bo_qua = rp.evaluate(*args, rp.SKIP)
    assert any(lvl == rp.OK and "BỎ QUA" in m for lvl, m in bo_qua)


def test_cli_rc_theo_pin(tmp_path, capsys):
    root = _mk_tree(tmp_path)
    pin_file = tmp_path / "pins.json"
    pin_file.write_text(json.dumps(_pins_for(root), ensure_ascii=False), encoding="utf-8")
    rc = rp.main(["--root", str(root), "--pins", str(pin_file), "--skip-env"])
    assert rc == 0, capsys.readouterr().out
    # phá index -> rc 1
    (root / "chroma_db" / "chroma.sqlite3").unlink()
    _mk_chroma(root / "chroma_db" / "chroma.sqlite3", 9, 3, {"Tầng 1": 9})
    rc = rp.main(["--root", str(root), "--pins", str(pin_file), "--skip-env"])
    assert rc == 1, capsys.readouterr().out


def test_khong_import_chromadb():
    """Cổng này phải chạy được trên máy chưa cài Chroma client; mở client = tái ghi byte (PA-60)."""
    import ast

    tree = ast.parse(Path(rp.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert "chromadb" not in names, names
