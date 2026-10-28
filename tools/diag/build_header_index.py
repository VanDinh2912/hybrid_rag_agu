"""Build index T5b: chèn contextual header vào ĐẦU mỗi chunk rồi embed lại.

Vì sao làm từ index có sẵn thay vì chạy lại `ingest.py`
------------------------------------------------------
T5b chỉ được đổi **chuỗi đem đi embed + BM25**, không được đổi ranh giới chunk.
Đọc đúng bộ chunk đã persist (`chroma_db/` hoặc `indexes/experimental/chroma_db_vie/`), giữ
nguyên `chunk_id`/`source`/`tier`, chỉ thay `page_content` bằng bản có header — nhờ vậy
so sánh với round nền là "một biến" (header), không lẫn chunking/OCR.

An toàn
-------
- Đích bắt buộc qua `ensure_separate_index_target()`: không bao giờ ghi
  `chroma_db/` hay `chroma_db_vie/` (kể cả bản đã dời vào `indexes/experimental/`).
- Đích đã tồn tại và có tệp ⇒ từ chối, KHÔNG xoá/ghi đè.
- Chỉ đọc index nguồn; báo cáo kèm SHA-256 của cây nguồn trước/sau để chứng minh.
- Cờ `ENABLE_CONTEXTUAL_HEADER=1` là điều kiện bắt buộc: công cụ này không được
  âm thầm build một index "header" mà thực ra không có header.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import chromadb  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402

from src.contextual_header import (  # noqa: E402
    ENABLE_CONTEXTUAL_HEADER_ENV,
    build_header,
    contextual_header_enabled,
    contextualize_text,
    directory_digest,
    ensure_separate_index_target,
    parse_chunk,
)

COLLECTION = "agu_regulations"


def read_index(path: str | os.PathLike[str], collection: str = COLLECTION) -> dict:
    """Đọc id/tài liệu/metadata của một index đã persist (chỉ đọc)."""
    client = chromadb.PersistentClient(path=str(path))
    col = client.get_collection(collection)
    data = col.get(include=["documents", "metadatas"])
    rows = []
    for doc_id, text, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        rows.append({"id": doc_id, "text": text or "", "metadata": dict(meta or {})})
    rows.sort(key=lambda r: int(r["metadata"].get("chunk_id", 0)))
    return {"rows": rows}


def read_index_via_copy(path: str | os.PathLike[str], collection: str = COLLECTION) -> dict:
    """Đọc index qua BẢN SAO tạm.

    Chroma/SQLite có thể ghi WAL (đổi byte của tệp) ngay khi mở, dù chỉ `get()`.
    T5b cam kết không đụng index nguồn, nên mọi lần đọc phải diễn ra trên bản sao:
    digest của nguồn trước/sau khi đó mới là bằng chứng trung thực.
    """
    with tempfile.TemporaryDirectory(
        prefix="t5b_read_", ignore_cleanup_errors=True
    ) as tmp:
        copy = Path(tmp) / "index"
        shutil.copytree(Path(path), copy)
        return read_index(copy, collection)


def headerise_records(rows: Sequence[dict], *, title_key: Optional[str] = None) -> dict:
    """Chuyển từng record sang bản có header; KHÔNG đọc/ghi đĩa.

    `title_key`: nếu truyền, lấy tên văn bản từ `metadata[title_key]` thay vì
    header cũ. Mặc định None = dùng tên văn bản đã có trong dòng đầu chunk.
    """
    out: list[dict] = []
    stats = {
        "n": len(rows),
        "n_changed": 0,
        "n_with_article": 0,
        "n_with_clause": 0,
        "n_with_point": 0,
        "n_with_chapter": 0,
        "n_body_mismatch": 0,
        "examples": [],
    }
    for row in rows:
        original = row["text"]
        title = (row.get("metadata") or {}).get(title_key) if title_key else None
        decorated = contextualize_text(original, title=title)
        old_body = parse_chunk(original).body
        if not decorated.endswith(old_body):
            stats["n_body_mismatch"] += 1
            raise ValueError(
                f"chunk_id={row.get('metadata', {}).get('chunk_id')} mất thân nguyên văn — dừng."
            )
        header = build_header(original, title=title)[0]
        if decorated != original:
            stats["n_changed"] += 1
        if header.article:
            stats["n_with_article"] += 1
        if header.clause:
            stats["n_with_clause"] += 1
        if header.point:
            stats["n_with_point"] += 1
        if header.chapter:
            stats["n_with_chapter"] += 1
        if len(stats["examples"]) < 3:
            stats["examples"].append(
                {"chunk_id": row.get("metadata", {}).get("chunk_id"),
                 "header": decorated.split("\n", 1)[0]}
            )
        out.append(
            {
                "id": row["id"],
                "text": decorated,
                "metadata": dict(row.get("metadata") or {}),
            }
        )
    return {"rows": out, "stats": stats}


def build_header_index(
    source_index: str | os.PathLike[str],
    target_index: str | os.PathLike[str],
    *,
    collection: str = COLLECTION,
    report_path: Optional[str | os.PathLike[str]] = None,
    embedder: Optional[Embeddings] = None,
    title_key: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Đọc `source_index` → chèn header → ghi collection mới vào `target_index`."""
    target = ensure_separate_index_target(target_index)
    source = Path(source_index)
    if target == source.resolve():
        raise ValueError("Index đích trùng index nguồn — từ chối.")
    if target.exists() and any(target.iterdir()):
        raise SystemExit(
            f"[an toàn] '{target}' đã có dữ liệu — T5b chỉ build vào thư mục MỚI, không ghi đè."
        )
    if not contextual_header_enabled():
        raise SystemExit(
            f"[cờ] cần {ENABLE_CONTEXTUAL_HEADER_ENV}=1 thì mới build index header; "
            "cờ TẮT sẽ tạo bản sao y nguyên index nguồn (vô nghĩa cho T5b)."
        )

    digest_before = directory_digest(source)
    source_rows = read_index_via_copy(source, collection)["rows"]
    if not source_rows:
        raise SystemExit(f"[nguồn] '{source}' rỗng — không có gì để build.")
    converted = headerise_records(source_rows, title_key=title_key)
    digest_after = directory_digest(source)

    report: dict[str, Any] = {
        "kind": "T5b — contextual header index (build-time)",
        "source_index": str(source.resolve()),
        "source_count": len(source_rows),
        "target_index": str(target),
        "collection": collection,
        "title_key": title_key,
        "source_digest_before": digest_before,
        "source_digest_after": digest_after,
        "source_unchanged": digest_before == digest_after,
        "source_read_via_copy": True,
        "stats": converted["stats"],
        "dry_run": dry_run,
    }
    if dry_run:
        return report

    if embedder is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        embedder = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    from langchain_chroma import Chroma

    documents = [
        Document(page_content=row["text"], metadata=row["metadata"])
        for row in converted["rows"]
    ]
    store = Chroma.from_documents(
        documents=documents,
        embedding=embedder,
        ids=[row["id"] for row in converted["rows"]],
        collection_name=collection,
        persist_directory=str(target),
    )
    stored = store._collection.count()
    report["stored_count"] = stored
    report["stored_equals_source"] = stored == len(source_rows)
    if report_path is not None:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build index T5b có contextual header.")
    parser.add_argument("--source-index", default="./chroma_db")
    parser.add_argument("--target-index", required=True)
    parser.add_argument("--collection", default=COLLECTION)
    parser.add_argument("--report", default=None)
    parser.add_argument("--title-key", default=None,
                        help="khóa metadata chứa tên văn bản (mặc định: tên trong header cũ)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = build_header_index(
        args.source_index,
        args.target_index,
        collection=args.collection,
        report_path=args.report,
        title_key=args.title_key,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
