"""Đo chất lượng chính một ChromaDB index (chỉ ĐỌC): tỉ lệ từ có dấu + phân bố theo chunk.

Dùng để có số "trước/sau" lấy từ ĐÚNG đối tượng mà RAG truy xuất (các chunk đã lưu),
thay vì đo trên tệp nguồn — vì chunking có thể thêm/bớt văn bản.

Cách chạy:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/measure_index.py --db ./chroma_db     --out data/loop/diag/corpus_diagnostics/index_before.json
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/measure_index.py --db ./chroma_db_vie --out data/loop/diag/corpus_diagnostics/index_after.json

Không ghi vào DB, không xoá gì cả; file JSON xuất là sản phẩm duy nhất.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chromadb  # noqa: E402

from tools.diag.corpus_diacritics import word_diacritic_ratio  # noqa: E402


def collection_documents(db_dir: Path) -> tuple[str, list[str]]:
    client = chromadb.PersistentClient(path=str(db_dir))
    collections = client.list_collections()
    if not collections:
        raise SystemExit(f"không có collection nào trong {db_dir}")
    if len(collections) > 1:
        print(f"[cảnh báo] {db_dir} có {len(collections)} collection: "
              f"{[c.name for c in collections]} — dùng collection đầu tiên")
    col = collections[0]
    got = col.get(include=["documents"])
    return col.name, list(got.get("documents") or [])


def measure(db_dir: Path) -> dict:
    name, docs = collection_documents(db_dir)
    marked = words = 0
    lt5 = ge50 = empty = 0
    ratios = []
    for text in docs:
        m, w, r = word_diacritic_ratio(text or "")
        if w == 0 or r is None:
            empty += 1
            continue
        marked += m
        words += w
        ratios.append(r)
        if r < 0.05:
            lt5 += 1
        if r >= 0.50:
            ge50 += 1
    ratios.sort()
    return {
        "db": str(db_dir),
        "collection": name,
        "chunks": len(docs),
        "chunks_empty": empty,
        "word_diacritic": round(marked / words, 4) if words else None,
        "marked": marked,
        "words": words,
        "chunks_lt5pct": lt5,
        "chunks_ge50pct": ge50,
        "chunk_ratio_median": round(ratios[len(ratios) // 2], 4) if ratios else None,
        "chunk_ratio_p10": round(ratios[len(ratios) // 10], 4) if ratios else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    stats = measure(Path(args.db))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))
    print(f"[ghi] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
