"""Chế độ test & học (learn): hỏi - đáp với người làm trọng tài.

Vòng lặp: nhập câu hỏi → hệ thống trả lời → người đánh giá.
Nếu trả lời sai: dán thông tin đúng → bài học được ghi vào
data/corpus/ghi_chu_hoc_them.txt (tự đóng gói theo cấu trúc 'Điều N.' để bộ
chunk nhận được), rebuild ChromaDB (không reset thư mục, tái dùng bge-m3
đã nạp), làm mới cả bộ truy xuất lai (BM25 + vector) và ghi 1 dòng log vào
logs/learning/learning_log.csv.
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Script chạy từ gốc repo nhưng nằm ở scripts/ ⇒ tự thêm gốc dự án vào sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest import _corpus_files, _index_facts, describe_reset, run_ingestion
from src.generator import QwenGenerator
from src.generation.local_slm import LocalSLM
from src.core.config import DEFAULT_TOP_K
from src.core.paths import CHROMA_DIR, CORPUS_DIR, LOGS_DIR
from src.core.pipeline import HybridRAGPipeline, RetrieverRebuildError
from src.retrieval.vector_db import VectorStoreManager

# Neo theo gốc dự án (REVIEW §4) — script chạy được từ bất kỳ CWD nào.
NOTES_PATH = str(CORPUS_DIR / "ghi_chu_hoc_them.txt")
LOG_PATH = str(LOGS_DIR / "learning" / "learning_log.csv")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """PA-29(c): thêm `--help`/`--dry-run` — bắt buộc trước khi chạy thật."""
    parser = argparse.ArgumentParser(
        prog="scripts/learn.py",
        description="Chế độ test & học có trọng tài: hỏi - đáp, sai thì dạy lại và rebuild index.",
        epilog="Chạy `--dry-run` trước để xem tệp nào sẽ bị ghi mà không mở ChromaDB, không gọi model.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="In các tệp sẽ đọc/ghi rồi thoát; không mở ChromaDB, không gọi model.")
    return parser.parse_args(argv)


def print_dry_run() -> int:
    """Chỉ đọc metadata trên đĩa — không mở ChromaDB (mở ra có thể tái ghi byte, PA-60)."""
    persist_dir = str(CHROMA_DIR)
    facts = _index_facts(persist_dir)
    plan = describe_reset(persist_dir)
    corpus_files = _corpus_files(str(CORPUS_DIR))
    print("[DRY-RUN] Chế độ learn — không ghi tệp nào, không mở ChromaDB, không gọi model.")
    print(f"  corpus : {CORPUS_DIR} ({len(corpus_files)} tệp .txt/.pdf/.docx)")
    print(f"  index  : {plan['path']} — {facts['n_files']} tệp, {facts['n_bytes']:,} B")
    if not facts["exists"] or facts["n_files"] == 0:
        print("           [CẢNH BÁO] index trống/không tồn tại ⇒ chạy `python ingest.py` trước.")
    print(f"  bài học: {NOTES_PATH} — {'GHI THÊM mục mới' if os.path.exists(NOTES_PATH) else 'tạo mới'}")
    print(f"  log    : {LOG_PATH}")
    print("  không reset thư mục index; mỗi bài học dựng lại collection (reset=False).")
    print("  (Số chunk hiện có: KHÔNG đọc — mở ChromaDB có thể tái ghi byte theo PA-60.)")
    return 0


def read_correction() -> str:
    print("Dán thông tin ĐÚNG (mỗi dòng một ý, kết thúc bằng một dòng trống):")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines).strip()


def append_note(question: str, correction: str, notes_path: str | None = None) -> None:
    """Ghi một mục học vào `data/corpus/ghi_chu_hoc_them.txt` (hoặc `notes_path` khác)."""
    notes_path = notes_path or NOTES_PATH
    os.makedirs(os.path.dirname(notes_path), exist_ok=True)
    if os.path.exists(notes_path):
        with open(notes_path, "r", encoding="utf-8") as f:
            # Chỉ quét heading do chính hệ thống sinh ("Điều N. Ghi chú học thêm ..."):
            # quét mọi mốc "Điều N." sẽ đếm nhầm cả trích dẫn ngườê dùng dán trong phần chỉnh sửa,
            # làm bộ đếm nhảy loạn và ghi đè mất Điều cũ.
            numbers = [int(n) for n in re.findall(r"Điều\s+(\d+)\.\s+Ghi chú học thêm", f.read())]
        article_no = max(numbers, default=1000) + 1
    else:
        with open(notes_path, "w", encoding="utf-8") as f:
            f.write("FILE GHI CHÚ HỌC THÊM — các mục bên dưới do chế độ learn (learn.py) bổ sung.\n\n")
        article_no = 1001

    with open(notes_path, "a", encoding="utf-8") as f:
        f.write(f"Điều {article_no}. Ghi chú học thêm ngày {datetime.now():%Y-%m-%d %H:%M}\n")
        f.write(f"Câu hỏi: {question}\n")
        f.write(f"Nội dung chính xác: {correction}\n\n")


def log_learning(question: str, wrong_answer: str, correction: str,
                 chunks_before: int, chunks_after: int) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    new_file = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["thoi_gian", "cau_hoi", "dap_an_sai", "thong_tin_da_hoc",
                             "file_bai_hoc", "chunks_truoc", "chunks_sau"])
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            question,
            wrong_answer,
            correction,
            os.path.basename(NOTES_PATH),
            chunks_before,
            chunks_after,
        ])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        return print_dry_run()

    print("--- CHẾ ĐỘ TEST & HỌC (LEARN) ---")
    print("Người làm trọng tài: trả lời sai thì dán thông tin đúng, hệ thống học ngay và ghi log.")
    print("Gõ 'exit' để thoát.\n")

    db_manager = VectorStoreManager()
    vector_db = db_manager.load_vector_store()
    indexed = vector_db._collection.count()
    if indexed == 0:
        raise SystemExit("ChromaDB rỗng — chạy 'python ingest.py' trước khi vào chế độ learn.")

    local_slm = LocalSLM(model_name=os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b-instruct"))
    # D-44: sinh câu trả lời bằng Qwen local (Ollama). Không dùng Gemini trong chế độ
    # learn — vòng lặp này chạy hoàn toàn offline và không tiêu quota.
    pipeline = HybridRAGPipeline(local_slm=local_slm, vector_db=vector_db, generator=QwenGenerator())
    print(f"Pipeline sẵn sàng ({indexed} chunks).\n")

    while True:
        try:
            question = input("Câu hỏi > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKết thúc chế độ learn.")
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit", "thoat", "thoát"}:
            print("Kết thúc chế độ learn.")
            break

        try:
            result = pipeline.run(question, top_k=DEFAULT_TOP_K)
        except KeyboardInterrupt:
            print("\n[Đã hủy] Ngắt lượt hỏi này (Ctrl+C).\n")
            continue
        except Exception as exc:
            print(f"\n[LỖI] {type(exc).__name__}: {exc}\n")
            continue
        print(f"\n[Chuẩn hóa bởi Qwen] {result['normalized_query']}")
        print(f"[Trả lời] {result['answer']}\n")

        if input("Đáp án đúng chưa? [Enter/y = đúng, n = sai] > ").strip().lower() != "n":
            print()
            continue

        correction = read_correction()
        if not correction:
            print("Không có nội dung học — bỏ qua.\n")
            continue

        chunks_before = pipeline.vector_db._collection.count()
        append_note(question, correction)
        print(f"\nĐã ghi bài học vào '{NOTES_PATH}'. Đang học lại (rebuild collection)...")
        _db, vector_db, _total = run_ingestion(db_manager=db_manager, reset=False)
        try:
            # Gán vector_db là chưa đủ: BM25 vẫn giữ document cũ ⇒ phải dựng lại retriever.
            pipeline.replace_vector_db(vector_db)
        except RetrieverRebuildError as exc:
            print(f"\n[LỖI] Đã nạp corpus mới nhưng chưa làm mới được bộ truy xuất: {exc}\n")
            continue
        chunks_after = vector_db._collection.count()
        log_learning(question, result["answer"], correction, chunks_before, chunks_after)
        print(f"HỌC XONG: {chunks_before} → {chunks_after} chunks. Log: '{LOG_PATH}'.")
        print("Hỏi lại câu đó để kiểm chứng kiến thức mới.\n")

    return 0


if __name__ == "__main__":
    main()
