# -*- coding: utf-8 -*-
"""Đối chiếu corpus ↔ index: tệp nào đã nạp, tệp nào chưa, nguồn lạ, tên trùng.

Vì sao có file này: `data/corpus/` và `chroma_db/` là hai danh sách có thể lệch nhau mà
không ai báo — thêm PDF vào corpus rồi quên ingest, hoặc đổi tên tệp sau khi nạp, đều
cho ra index "trông bình thường" nhưng thiếu/ thừa nội dung. Công cụ này chỉ ĐỌC:

1. liệt kê mọi tệp `data/corpus` với `sha256` + số byte,
2. đọc tên nguồn đã nạp từ `chroma.sqlite3` bằng SQLite **read-only + immutable**
   (không mở ChromaDB client — mở client có thể tái ghi byte, PA-60),
3. in trạng thái từng tệp và liệt kê lệch: `chưa nạp`, `trùng tên`, `nguồn lạ`.

Ba chế độ:

    venv/Scripts/python.exe tools/diag/corpus_index_manifest.py               # in bảng
    venv/Scripts/python.exe tools/diag/corpus_index_manifest.py --json        # JSON đầy đủ
    venv/Scripts/python.exe tools/diag/corpus_index_manifest.py --check       # rc=1 khi lệch

Mặc định đọc `data/corpus` + `chroma_db`; `--corpus/--index` để chỉ định bản khác (ví dụ
index dựng trong `tmp/` trước khi hoán đổi). Không ghi tệp nào, không tạo thư mục.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # chạy trực tiếp từ bất kỳ CWD nào
    sys.path.insert(0, str(ROOT))

from src.core.paths import CHROMA_DIR, CORPUS_DIR  # noqa: E402

#: Đúng phần mở rộng `ingest._corpus_files`/loader đọc — công cụ không tự mở rộng phạm vi.
CORPUS_SUFFIXES = (".txt", ".pdf", ".docx")
CHUNK = 1024 * 1024


class IndexUnreadable(RuntimeError):
    """Không tìm/ không đọc được `chroma.sqlite3` của thư mục index."""


def sha256_file(path: Path) -> str:
    """SHA-256 luồng 1 MiB — tệp corpus có thể hàng trăm MB."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def corpus_entries(corpus_dir: str | Path) -> list[dict]:
    """Mọi tệp corpus (đệ quy) theo thứ tự `rel` — kèm tên, byte, sha256."""
    base = Path(corpus_dir)
    entries: list[dict] = []
    if not base.is_dir():
        return entries
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        if path.suffix.lower() not in CORPUS_SUFFIXES:
            continue
        entries.append({
            "rel": path.relative_to(base).as_posix(),
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return entries


def read_index_sources(index_dir: str | Path) -> dict:
    """Đọc tên nguồn + số chunk từ `chroma.sqlite3` (read-only, KHÔNG mở client)."""
    db = Path(index_dir) / "chroma.sqlite3"
    if not db.is_file():
        raise IndexUnreadable(f"không thấy {db}")
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro&immutable=1", uri=True)
    except sqlite3.Error as exc:
        raise IndexUnreadable(f"không mở được {db} (read-only): {exc}") from exc
    try:
        collections = [row[0] for row in con.execute("select name from collections order by name")]
        sources = {
            str(name): int(count)
            for name, count in con.execute(
                "select string_value, count(*) from embedding_metadata "
                "where key = 'source' and string_value is not null group by string_value "
                "order by string_value"
            )
        }
        chunks = int(con.execute("select count(*) from embeddings").fetchone()[0])
    except sqlite3.Error as exc:
        raise IndexUnreadable(f"schema {db} không đọc được: {exc}") from exc
    finally:
        con.close()
    return {"path": str(db), "collections": collections, "sources": sources, "chunks": chunks}


def build_manifest(corpus_dir: str | Path = CORPUS_DIR, index_dir: str | Path = CHROMA_DIR) -> dict:
    """Dựng báo cáo corpus↔index (thuần đọc). `ok=False` kèm `reasons` khi có lệch."""
    entries = corpus_entries(corpus_dir)
    by_name: dict[str, list[str]] = {}
    for entry in entries:
        by_name.setdefault(entry["name"], []).append(entry["rel"])

    try:
        index = read_index_sources(index_dir)
        index_ok = True
        error = ""
    except IndexUnreadable as exc:
        index = {"path": str(Path(index_dir) / "chroma.sqlite3"), "collections": [],
                 "sources": {}, "chunks": 0}
        index_ok = False
        error = str(exc)

    for entry in entries:
        twins = by_name[entry["name"]]
        chunks = index["sources"].get(entry["name"], 0)
        if len(twins) > 1:
            status = "trùng tên"
        elif chunks > 0:
            status = "đã nạp"
        else:
            status = "chưa nạp"
        entry["chunks"] = chunks
        entry["status"] = status

    orphan = sorted(name for name in index["sources"] if name not in by_name)
    duplicate = sorted(name for name, rels in by_name.items() if len(rels) > 1)
    unindexed = [entry["rel"] for entry in entries if entry["status"] == "chưa nạp"]

    reasons: list[str] = []
    if not index_ok:
        reasons.append(f"không đọc được index: {error}")
    elif index["chunks"] == 0:
        reasons.append("index rỗng (0 chunk)")
    if unindexed:
        reasons.append(f"{len(unindexed)} tệp corpus CHƯA nạp: {', '.join(unindexed)}")
    if orphan:
        reasons.append(f"{len(orphan)} nguồn trong index KHÔNG có trong corpus: {', '.join(orphan)}")
    if duplicate:
        reasons.append(f"{len(duplicate)} tên tệp corpus trùng: {', '.join(duplicate)}")

    return {
        "corpus_dir": str(Path(corpus_dir)),
        "index_dir": str(Path(index_dir)),
        "index_ok": index_ok,
        "index_error": error,
        "collections": index["collections"],
        "chunk_total": index["chunks"],
        "files": entries,
        "unindexed": unindexed,
        "orphan": orphan,
        "duplicate_basenames": duplicate,
        "ok": not reasons,
        "reasons": reasons,
    }


def print_manifest(manifest: dict) -> None:
    """Bảng dễ đọc cho người vận hành (không phải định dạng máy — dùng `--json`)."""
    print(f"corpus : {manifest['corpus_dir']} — {len(manifest['files'])} tệp")
    print(f"index  : {manifest['index_dir']} — {manifest['chunk_total']} chunk"
          f" ({', '.join(manifest['collections']) or 'không có collection'})")
    print()
    width = max((len(f['rel']) for f in manifest['files']), default=4)
    for entry in manifest['files']:
        mark = {"đã nạp": "OK ", "chưa nạp": "THIẾU", "trùng tên": "TRÙNG"}[entry["status"]]
        print(f"  [{mark:5s}] {entry['rel']:<{width}}  {entry['bytes']:>10,} B  "
              f"{entry['chunks']:>4d} chunk  {entry['sha256'][:16]}")
    if manifest["orphan"]:
        print("\nNguồn trong index nhưng KHÔNG có trong corpus:")
        for name in manifest["orphan"]:
            print(f"  - {name}")
    if manifest["duplicate_basenames"]:
        print("\nTên tệp corpus trùng (không xác định được đã nạp tệp nào):")
        for name in manifest["duplicate_basenames"]:
            print(f"  - {name}")
    print()
    if manifest["ok"]:
        print("[corpus-index] KẾT LUẬN: KHỚP — mọi tệp corpus đã nạp, không nguồn lạ/trùng tên.")
    else:
        print("[corpus-index] KẾT LUẬN: LỆCH")
        for reason in manifest["reasons"]:
            print(f"  - {reason}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tools/diag/corpus_index_manifest.py",
        description="Đối chiếu data/corpus với chroma.sqlite3 (chỉ đọc): đã nạp / chưa nạp / nguồn lạ.",
        epilog="Thêm --check để nhận mã thoát 1 khi có lệch (dùng được làm cổng CI).",
    )
    parser.add_argument("--corpus", default=str(CORPUS_DIR),
                        help=f"thư mục corpus (mặc định {CORPUS_DIR})")
    parser.add_argument("--index", default=str(CHROMA_DIR),
                        help=f"thư mục index chứa chroma.sqlite3 (mặc định {CHROMA_DIR})")
    parser.add_argument("--json", action="store_true",
                        help="in JSON đầy đủ thay vì bảng người đọc")
    parser.add_argument("--check", action="store_true",
                        help="mã thoát 1 khi có lệch, 0 khi khớp (mặc định luôn 0 sau khi in)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_manifest(args.corpus, args.index)
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print_manifest(manifest)
    if args.check and not manifest["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
