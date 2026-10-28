"""Kiểm thử T5b build-time: chèn header vào index MỚI, không đụng index cũ.

Bốn hành vi được ghim:
  1. Record giữ nguyên id/metadata, thân chunk nguyên văn, header có Điều/Khoản.
  2. Build vào thư mục mới ⇒ đủ số chunk, id/metadata khớp nguồn; nguồn không đổi băm.
  3. Đích đã có dữ liệu ⇒ từ chối (không xoá/ghi đè).
  4. Đích là index bảo vệ ⇒ từ chối; cờ TẮT ⇒ từ chối build.
"""

from __future__ import annotations

import json
from pathlib import Path

import chromadb
import pytest
from langchain_core.embeddings import Embeddings

from src.indexing.contextual_header import (
    ENABLE_CONTEXTUAL_HEADER_ENV,
    directory_digest,
    parse_chunk,
)
from tools.diag.build_header_index import build_header_index, headerise_records


class FakeEmbeddings(Embeddings):
    """Embedding 3 chiều deterministic — đủ để Chroma ghi/đọc, không tải model."""

    def embed_documents(self, texts):
        return [[1.0, float(len(t) % 7), float(i % 5)] for i, t in enumerate(texts)]

    def embed_query(self, text):
        return [1.0, float(len(text) % 7), 0.0]


ARTICLE = (
    "[A.pdf] - [Điều 8.] \n"
    " 1. Sinh viên đóng phí mỗi tháng.\n"
    "2. Phí nộp theo học kỳ.\n"
    "a) Mức phí do trường quy định."
)
TABLE = "[A.pdf] - [Bảng biểu] \n| Mã | Tên |\n|---|---|\n| 01 | Học phí |"


def make_source(path: Path, docs: list[str]) -> None:
    client = chromadb.PersistentClient(path=str(path))
    col = client.create_collection("agu_regulations")
    col.add(
        ids=["uuid-a", "uuid-b"],
        documents=docs,
        metadatas=[
            {"chunk_id": 1, "source": "A.pdf", "tier": "Tầng 1"},
            {"chunk_id": 2, "source": "A.pdf", "tier": "Tầng 1"},
        ],
        embeddings=[[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]],
    )


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setenv(ENABLE_CONTEXTUAL_HEADER_ENV, "1")


def test_headerise_giu_than_va_them_dieu_khoan():
    rows = [
        {"id": "a", "text": ARTICLE, "metadata": {"chunk_id": 1}},
        {"id": "b", "text": TABLE, "metadata": {"chunk_id": 2}},
    ]
    out = headerise_records(rows)
    stats = out["stats"]
    assert stats["n"] == 2
    assert stats["n_changed"] == 2
    assert stats["n_body_mismatch"] == 0
    assert stats["n_with_article"] == 1
    assert stats["n_with_clause"] == 1
    assert out["rows"][0]["text"].split("\n", 1)[0] == (
        "[A.pdf] - [Điều 8] - [Khoản 1-2] - [Điểm a]"
    )
    assert out["rows"][0]["text"].endswith(parse_chunk(ARTICLE).body)
    assert out["rows"][1]["text"].startswith("[A.pdf] - [Bảng biểu]")
    assert out["rows"][1]["text"].endswith(parse_chunk(TABLE).body)
    assert [r["id"] for r in out["rows"]] == ["a", "b"]


def test_build_ghi_index_moi_du_id_metadata_nguon_khong_doi(tmp_path):
    source = tmp_path / "chroma_db"
    make_source(source, [ARTICLE, TABLE])
    before = directory_digest(source)
    target = tmp_path / "chroma_db_headers"
    report = build_header_index(
        source,
        target,
        embedder=FakeEmbeddings(),
        report_path=tmp_path / "report.json",
    )
    assert report["stored_count"] == 2
    assert report["stored_equals_source"] is True
    assert report["source_unchanged"] is True
    assert directory_digest(source) == before
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["stored_count"] == 2

    col = chromadb.PersistentClient(path=str(target)).get_collection("agu_regulations")
    data = col.get(include=["documents", "metadatas"])
    by_id = {i: (d, m) for i, d, m in zip(data["ids"], data["documents"], data["metadatas"])}
    assert set(by_id) == {"uuid-a", "uuid-b"}
    assert by_id["uuid-a"][1]["chunk_id"] == 1
    assert by_id["uuid-a"][1]["source"] == "A.pdf"
    assert by_id["uuid-a"][0].startswith("[A.pdf] - [Điều 8]")
    assert by_id["uuid-a"][0].endswith(parse_chunk(ARTICLE).body)


def test_dich_da_co_du_lieu_thi_tu_choi(tmp_path):
    source = tmp_path / "chroma_db"
    make_source(source, [ARTICLE, TABLE])
    target = tmp_path / "chroma_db_headers"
    target.mkdir()
    (target / "chroma.sqlite3").write_bytes(b"cu")
    before = directory_digest(target)
    with pytest.raises(SystemExit, match="đã có dữ liệu"):
        build_header_index(source, target, embedder=FakeEmbeddings())
    assert directory_digest(target) == before


def test_dich_la_index_bao_ve_thi_tu_choi(tmp_path, monkeypatch):
    source = tmp_path / "chroma_db"
    make_source(source, [ARTICLE, TABLE])
    monkeypatch.chdir(tmp_path)
    (tmp_path / "chroma_db_vie").mkdir()
    with pytest.raises(ValueError, match="index bảo vệ"):
        build_header_index(source, "chroma_db_vie", embedder=FakeEmbeddings())


def test_co_tat_thi_tu_choi_build(tmp_path, monkeypatch):
    source = tmp_path / "chroma_db"
    make_source(source, [ARTICLE, TABLE])
    monkeypatch.delenv(ENABLE_CONTEXTUAL_HEADER_ENV, raising=False)
    with pytest.raises(SystemExit, match="cần ENABLE_CONTEXTUAL_HEADER=1"):
        build_header_index(source, tmp_path / "headers", embedder=FakeEmbeddings())
    assert not (tmp_path / "headers").exists()
