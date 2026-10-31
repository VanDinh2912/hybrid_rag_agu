import os
import shutil
from collections import Counter

from dotenv import load_dotenv

load_dotenv() # Tự động nạp file .env (CHROMA_PERSIST_DIR, ...)

from src.core.paths import CHROMA_DIR, CORPUS_DIR
from src.indexing.chunking import DocumentChunker, has_article_structure
from src.indexing.loader import DocumentLoader
from src.retrieval.vector_db import VectorStoreManager


def run_ingestion(db_manager: VectorStoreManager | None = None, reset: bool = True, log=print):
    """Quét corpus → chunking → nhúng → persist. Trả về (db_manager, vector_db, total_chunks).

    reset=True xóa cả thư mục ChromaDB (dùng cho ingest.py). Khi learn.py gọi với
    db_manager có sẵn và reset=False, bge-m3 được tái sử dụng và collection cũ bị
    xóa an toàn ngay trong create_vector_store — tránh rmtree vấp khóa file khi
    client ChromaDB trong learn.py còn mở.

    `log` là callback nhận từng dòng tiến trình (mặc định `print` cho CLI). GUI truyền
    callback đẩy vào queue thay vì đổi `sys.stdout` toàn cục (REVIEW §8).
    """
    # Neo theo gốc dự án (REVIEW §4): cùng một thư mục dù chạy từ đâu.
    persist_dir = str(CHROMA_DIR)

    if reset:
        if os.path.isdir(persist_dir):
            shutil.rmtree(persist_dir)
            log(f"\n[1/4] Đã xóa ChromaDB cũ tại '{persist_dir}' (reset toàn bộ index).")
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
        chars = sum(ocr_chars for _path, _ocr_pages, _total, ocr_chars in loader.ocr_stats)
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


def main():
    print("--- INGESTION: NẠP CORPUS TỪ data/corpus/ VÀO CHROMADB ---")
    db_manager, vector_db, total = run_ingestion()
    stored = vector_db._collection.count()

    if stored == total:
        print(f"\nTHÀNH CÔNG: {stored}/{total} chunks đã lưu tại '{db_manager.persist_directory}'.")
        print("Chạy 'python main.py' để hỏi - đáp (chạy thực) hoặc 'python scripts/learn.py' để test & học.")
    else:
        raise SystemExit(f"LỖI: ChromaDB chứa {stored} chunks, kỳ vọng {total}.")


if __name__ == "__main__":
    main()
