"""Chế độ test & học (learn): hỏi - đáp với người làm trọng tài.

Vòng lặp: nhập câu hỏi → hệ thống trả lời → người đánh giá.
Nếu trả lời sai: dán thông tin đúng → bài học được ghi vào
data/corpus/ghi_chu_hoc_them.txt (tự đóng gói theo cấu trúc 'Điều N.' để bộ
chunk nhận được), rebuild ChromaDB (không reset thư mục, tái dùng bge-m3
đã nạp) và ghi 1 dòng log vào outputs/learning_log.csv.
"""

import csv
import os
import re
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from ingest import run_ingestion
from src.generator import GeminiGenerator
from src.local_slm import LocalSLM
from src.pipeline import HybridRAGPipeline
from src.vector_db import VectorStoreManager

NOTES_PATH = os.path.join("data", "corpus", "ghi_chu_hoc_them.txt")
LOG_PATH = os.path.join("outputs", "learning_log.csv")


def read_correction() -> str:
    print("Dán thông tin ĐÚNG (mỗi dòng một ý, kết thúc bằng một dòng trống):")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines).strip()


def append_note(question: str, correction: str) -> None:
    os.makedirs(os.path.dirname(NOTES_PATH), exist_ok=True)
    if os.path.exists(NOTES_PATH):
        with open(NOTES_PATH, "r", encoding="utf-8") as f:
            # Chỉ quét heading do chính hệ thống sinh ("Điều N. Ghi chú học thêm ..."):
            # quét mọi mốc "Điều N." sẽ đếm nhầm cả trích dẫn ngườê dùng dán trong phần chỉnh sửa,
            # làm bộ đếm nhảy loạn và ghi đè mất Điều cũ.
            numbers = [int(n) for n in re.findall(r"Điều\s+(\d+)\.\s+Ghi chú học thêm", f.read())]
        article_no = max(numbers, default=1000) + 1
    else:
        with open(NOTES_PATH, "w", encoding="utf-8") as f:
            f.write("FILE GHI CHÚ HỌC THÊM — các mục bên dưới do chế độ learn (learn.py) bổ sung.\n\n")
        article_no = 1001

    with open(NOTES_PATH, "a", encoding="utf-8") as f:
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


def main():
    print("--- CHẾ ĐỘ TEST & HỌC (LEARN) ---")
    print("Người làm trọng tài: trả lời sai thì dán thông tin đúng, hệ thống học ngay và ghi log.")
    print("Gõ 'exit' để thoát.\n")

    db_manager = VectorStoreManager()
    vector_db = db_manager.load_vector_store()
    indexed = vector_db._collection.count()
    if indexed == 0:
        raise SystemExit("ChromaDB rỗng — chạy 'python ingest.py' trước khi vào chế độ learn.")

    local_slm = LocalSLM(model_name=os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b-instruct"))
    pipeline = HybridRAGPipeline(local_slm=local_slm, vector_db=vector_db, generator=GeminiGenerator())
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
            result = pipeline.run(question, top_k=4)
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
        pipeline.vector_db = vector_db
        chunks_after = vector_db._collection.count()
        log_learning(question, result["answer"], correction, chunks_before, chunks_after)
        print(f"HỌC XONG: {chunks_before} → {chunks_after} chunks. Log: '{LOG_PATH}'.")
        print("Hỏi lại câu đó để kiểm chứng kiến thức mới.\n")


if __name__ == "__main__":
    main()
