"""Nạp corpus vào ChromaDB (PA-16/PA-29: mặc định KHÔNG xoá index đang có dữ liệu).

Ba chế độ:
    python ingest.py --dry-run                    # in kế hoạch, không đọc corpus/không mở DB/không ghi
    python ingest.py                              # lần đầu (index chưa có hoặc rỗng)
    INGEST_ALLOW_RESET=1 python ingest.py --yes   # build lại toàn bộ lên index hiện có
"""

import argparse
import os
import shutil
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv() # Tự động nạp file .env (CHROMA_PERSIST_DIR, ...)

from src.core.paths import CHROMA_DIR, CORPUS_DIR
from src.indexing.chunking import DocumentChunker, has_article_structure
from src.indexing.loader import DocumentLoader
from src.retrieval.vector_db import VectorStoreManager

#: Cờ env bảo vệ index (PA-16), mặc định TẮT. `1` = cho phép xoá thư mục đích đã có dữ liệu.
ALLOW_RESET_ENV = "INGEST_ALLOW_RESET"


class IndexResetRefused(RuntimeError):
    """Từ chối xoá thư mục index đã có dữ liệu (PA-16).

    Dùng `RuntimeError` chứ không phải `SystemExit` để đường gọi thư viện (GUI tab "Nạp dữ
    liệu") bắt được và hiển thị; `main()` đổi thành `SystemExit` cho CLI.
    """


def _index_facts(persist_dir: str) -> dict:
    """Đếm mục/tệp/byte của thư mục index — chỉ đọc metadata, KHÔNG mở ChromaDB."""
    exists = os.path.isdir(persist_dir)
    n_entries = len(os.listdir(persist_dir)) if exists else 0
    n_files = 0
    n_bytes = 0
    if exists:
        for root, _dirs, names in os.walk(persist_dir):
            for name in names:
                fp = os.path.join(root, name)
                try:
                    n_bytes += os.path.getsize(fp)
                    n_files += 1
                except OSError:
                    pass
    return {"exists": exists, "n_entries": n_entries, "n_files": n_files, "n_bytes": n_bytes}


def describe_reset(persist_dir: str) -> dict:
    """Quyết định (thuần, không đụng đĩa) có được phép xoá `persist_dir` hay không."""
    facts = _index_facts(persist_dir)
    allow = os.getenv(ALLOW_RESET_ENV, "").strip() == "1"
    non_empty = facts["n_entries"] > 0
    return {
        **facts,
        "path": os.path.abspath(persist_dir),
        "non_empty": non_empty,
        "allow_reset": allow,
        "will_delete": bool(non_empty and allow),
        "refused": bool(non_empty and not allow),
    }


def reset_guard(persist_dir: str, *, allow_reset: bool = False) -> dict:
    """Trả kế hoạch nếu được phép; ném `IndexResetRefused` nếu thư mục đích đã có dữ liệu.

    `allow_reset=True` dành cho đường gọi ĐÃ có xác nhận riêng của người dùng (GUI hỏi
    `askyesno`, CLI hỏi `--yes`) — env `INGEST_ALLOW_RESET` vẫn là cổng cho mọi đường khác.
    """
    plan = describe_reset(persist_dir)
    if plan["refused"] and not allow_reset:
        raise IndexResetRefused(
            f"[an toàn] '{plan['path']}' đã có dữ liệu — từ chối xoá. "
            f"Đặt {ALLOW_RESET_ENV}=1 nếu THẬT SỰ muốn build lại toàn bộ index này."
        )
    return plan


def _corpus_files(corpus_dir: str) -> list[str]:
    """Liệt kê tệp corpus theo đúng phần mở rộng loader đọc — chỉ đọc tên tệp, không OCR."""
    out = []
    if os.path.isdir(corpus_dir):
        for root, _dirs, names in os.walk(corpus_dir):
            out += [os.path.join(root, n) for n in names
                    if n.lower().endswith((".txt", ".pdf", ".docx"))]
    return sorted(out)


def run_ingestion(db_manager: VectorStoreManager | None = None, reset: bool = True, log=print,
                  allow_reset: bool = False):
    """Quét corpus → chunking → nhúng → persist. Trả về (db_manager, vector_db, total_chunks).

    reset=True xóa cả thư mục ChromaDB (dùng cho ingest.py). Khi learn.py gọi với
    db_manager có sẵn và reset=False, bge-m3 được tái sử dụng và collection cũ bị
    xóa an toàn ngay trong create_vector_store — tránh rmtree vấp khóa file khi
    client ChromaDB trong learn.py còn mở.

    PA-16: với reset=True, thư mục đích đã có dữ liệu mà `INGEST_ALLOW_RESET` chưa bật và
    `allow_reset` không được truyền ⇒ ném `IndexResetRefused` TRƯỚC khi đọc corpus. `allow_reset`
    chỉ dành cho đường gọi đã hỏi người dùng (GUI `askyesno` / CLI `--yes`).

    `log` là callback nhận từng dòng tiến trình (mặc định `print` cho CLI). GUI truyền
    callback đẩy vào queue thay vì đổi `sys.stdout` toàn cục (REVIEW §8).
    """
    # Neo theo gốc dự án (REVIEW §4): cùng một thư mục dù chạy từ đâu.
    persist_dir = str(CHROMA_DIR)

    if reset:
        plan = reset_guard(persist_dir, allow_reset=allow_reset)
        if plan["exists"]:
            shutil.rmtree(persist_dir)
            if plan["non_empty"]:
                log(f"\n[1/4] Đã xóa ChromaDB cũ tại '{persist_dir}' (reset toàn bộ index).")
            else:
                log(f"\n[1/4] Đã xóa thư mục ChromaDB rỗng tại '{persist_dir}' — sẽ tạo mới.")
        else:
            log(f"\n[1/4] Chưa có ChromaDB tại '{persist_dir}' — sẽ tạo mới.")
    else:
        log("\n[1/4] Không reset thư mục DB (chế độ learn) — collection cũ bị xóa khi nạp mới.")

    loader = DocumentLoader(data_dir=str(CORPUS_DIR))
    documents = loader.load_documents()
    if not documents:
        raise SystemExit(
            f"Thư mục '{loader.data_dir}' chưa có tài liệu (.txt/.pdf/.docx). "
            "Hãy đặt văn bản quy chế vào đó rồi chạy lại."
        )
    log(f"\n[2/4] Đã quét {len(documents)} file:")
    ocr_files = {os.path.basename(path) for path, *_ in loader.ocr_stats}
    for doc in documents:
        tag = " [OCR]" if doc["title"] in ocr_files else ""
        log(f"      - [{doc['tier']}] {doc['title']} ({len(doc['content']):,} ký tự){tag}")
    if loader.ocr_stats:
        pages = sum(ocr_pages for _path, ocr_pages, _total, _chars in loader.ocr_stats)
        chars = sum(_ocr_chars for _path, _ocr_pages, _total, _ocr_chars in loader.ocr_stats)
        log(f"      OCR (file scan ảnh): {len(loader.ocr_stats)} file, {pages} trang, {chars:,} ký tự")
    if loader.skipped:
        log(f"      Không đọc được {len(loader.skipped)} file:")
        for path, reason in loader.skipped:
            log(f"      - {os.path.relpath(path, loader.data_dir)}: {reason}")

    chunker = DocumentChunker()
    chunks = []
    log("\n[3/4] Chunking:")
    for doc in documents:
        doc_chunks = chunker.chunk_document(doc)
        chunks.extend(doc_chunks)
        strategy = "Điều/Khoản" if has_article_structure(doc["content"]) else "fallback đoạn văn"
        log(f"      - [{doc['tier']}] {doc['title']}: {len(doc_chunks)} chunks ({strategy})")
    if not chunks:
        raise SystemExit("Không tạo được chunk nào — kiểm tra nội dung trích xuất có ra chữ không.")
    log(f"      Tổng cộng: {len(chunks)} chunks")
    tier_stats = Counter(chunk["tier"] for chunk in chunks)
    log("      Theo tầng: " + ", ".join(f"{tier} = {n}" for tier, n in sorted(tier_stats.items())))

    log("\n[4/4] Nhúng bge-m3 và lưu vào ChromaDB...")
    if db_manager is None:
        db_manager = VectorStoreManager()
    vector_db = db_manager.create_vector_store(chunks)
    return db_manager, vector_db, len(chunks)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="ingest.py",
        description=(
            "Nạp data/corpus vào ChromaDB. Nếu thư mục index đã có dữ liệu, lệnh TỪ CHỐI xoá "
            f"trừ khi đặt {ALLOW_RESET_ENV}=1; CLI còn cần --yes để xác nhận."
        ),
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="in kế hoạch đọc/ghi rồi thoát; không đọc corpus, không mở ChromaDB, không ghi/xoá",
    )
    ap.add_argument(
        "--yes", action="store_true",
        help=f"xác nhận xoá index hiện có (chỉ có hiệu lực khi {ALLOW_RESET_ENV}=1)",
    )
    return ap.parse_args(argv)


def _print_dry_run(persist_dir: str, plan: dict) -> None:
    corpus_dir = str(CORPUS_DIR)
    files = _corpus_files(corpus_dir)
    size_mb = plan["n_bytes"] / 1e6
    print("[DRY-RUN] Không đọc corpus, không mở ChromaDB, không ghi/xoá gì.")
    print(f"  corpus : {os.path.abspath(corpus_dir)} — {len(files)} tệp .txt/.pdf/.docx")
    print(f"  index  : {plan['path']} — tồn tại={plan['exists']}, {plan['n_entries']} mục, "
          f"{plan['n_files']} tệp, {size_mb:.1f} MB")
    if plan["refused"]:
        print(f"  reset  : TỪ CHỐI — đặt {ALLOW_RESET_ENV}=1 và thêm --yes nếu thật sự muốn xoá index.")
    elif plan["will_delete"]:
        print(f"  reset  : SẼ XOÁ toàn bộ thư mục index ({ALLOW_RESET_ENV}=1).")
    else:
        print("  reset  : không cần xoá (thư mục chưa có hoặc rỗng).")
    print("  số chunk hiện có: KHÔNG đọc — mở ChromaDB có thể tái ghi byte (PA-60).")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    persist_dir = str(CHROMA_DIR)
    plan = describe_reset(persist_dir)

    if args.dry_run:
        _print_dry_run(persist_dir, plan)
        return 0

    if plan["refused"]:
        raise SystemExit(
            f"[an toàn] '{plan['path']}' đã có dữ liệu — từ chối xoá. "
            f"Đặt {ALLOW_RESET_ENV}=1 nếu THẬT SỰ muốn build lại toàn bộ index này."
        )
    if plan["will_delete"] and not args.yes:
        if sys.stdin.isatty():
            answer = input(f"Xoá toàn bộ index tại '{plan['path']}'? Gõ 'yes' để tiếp tục: ")
            if answer.strip().lower() not in {"yes", "y"}:
                raise SystemExit("Đã huỷ — không xoá gì.")
        else:
            raise SystemExit(
                f"[an toàn] '{plan['path']}' sẽ bị xoá nhưng stdin không tương tác — "
                "thêm --yes để xác nhận (hoặc bỏ cờ để giữ nguyên index)."
            )

    print("--- INGESTION: NẠP CORPUS TỪ data/corpus/ VÀO CHROMADB ---")
    try:
        db_manager, vector_db, total = run_ingestion(allow_reset=True)
    except IndexResetRefused as exc:
        raise SystemExit(str(exc)) from None
    stored = vector_db._collection.count()

    if stored == total:
        print(f"\nTHÀNH CÔNG: {stored}/{total} chunks đã lưu tại '{db_manager.persist_directory}'.")
        print("Chạy 'python main.py' để hỏi - đáp (chạy thực) hoặc 'python scripts/learn.py' để test & học.")
    else:
        raise SystemExit(f"LỖI: ChromaDB chứa {stored} chunks, kỳ vọng {total}.")
    return 0


if __name__ == "__main__":
    main()