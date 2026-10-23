"""T2 Bước 2 — Re-OCR các PDF scan bằng EasyOCR (vi) vào CACHE MỚI, không đụng bản gốc.

Bảo thủ:
- KHÔNG sửa src/loader.py, KHÔNG ghi vào ./.ocr_cache (cache rapidocr gốc).
- Viết vào ./​.ocr_cache_vie/ theo ĐÚNG naming của DocumentLoader._cache_file, để nếu
  người dùng sau này bật qua OCR_CACHE_DIR=.ocr_cache_vie thì pipeline đọc được ngay.
- Chỉ OCR những trang mà pipeline hiện hành coi là scan (< DEFAULT_MIN_CHARS_PER_PAGE).
- Checkpoint theo TỪNG TRANG: trang nào đã có trong cache là bỏ qua; chạy lại không lặp.
- Không dùng mô hình khôi phục dấu: EasyOCR nhận diện trực tiếp từ ảnh.

Chạy (nền):  PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/reocr_vie.py
Kiểm tra nhanh 1 tệp:  ... reocr_vie.py --only 1054
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from src.loader import DEFAULT_MIN_CHARS_PER_PAGE, DocumentLoader  # noqa: E402

CORPUS_DIR = os.path.join(ROOT, "data", "corpus")
VIE_CACHE_DIR = os.path.join(ROOT, ".ocr_cache_vie")


def scan_pages_of(path: str) -> list[int]:
    reader = PdfReader(path)
    return [
        i for i, page in enumerate(reader.pages)
        if len((page.extract_text() or "").strip()) < DEFAULT_MIN_CHARS_PER_PAGE
    ]


def load_pages(cache_file: str) -> dict[int, str]:
    if not os.path.exists(cache_file):
        return {}
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return {int(k): v for k, v in json.load(f).get("pages", {}).items()}
    except (OSError, ValueError):
        return {}


def save_pages(cache_file: str, pages: dict[int, str]) -> None:
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    tmp = cache_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"pages": {str(k): v for k, v in pages.items()}}, f, ensure_ascii=False)
    os.replace(tmp, cache_file)  # ghi nguyên tử để checkpoint không hỏng giữa dòng


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="chỉ tệp có chuỗi này trong tên")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    loader = DocumentLoader(data_dir=CORPUS_DIR, ocr_cache_dir=VIE_CACHE_DIR)

    pdfs = []
    for root, _d, files in os.walk(CORPUS_DIR):
        for fn in files:
            if fn.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, fn))
    pdfs.sort()
    if args.only:
        pdfs = [p for p in pdfs if args.only in os.path.basename(p)]

    import easyocr

    reader = easyocr.Reader(["vi"], gpu=False, verbose="ERROR")

    total_new = 0
    t_start = time.perf_counter()
    for path in pdfs:
        sp = scan_pages_of(path)
        if not sp:
            continue
        cache_file = loader._cache_file(path)
        pages = load_pages(cache_file)
        todo = [i for i in sp if i not in pages]
        if not todo:
            print(f"[skip] {os.path.basename(path)[:50]:50} {len(sp)} trang đã OCR", flush=True)
            continue
        print(f"[OCR-vie] {os.path.basename(path)[:55]} — còn {len(todo)}/{len(sp)} trang", flush=True)
        with pdfium.PdfDocument(path) as pdf:
            for idx in todo:
                t0 = time.perf_counter()
                img = pdf[idx].render(scale=args.dpi / 72).to_pil().convert("RGB")
                lines = reader.readtext(np.array(img), detail=0, paragraph=False)
                pages[idx] = "\n".join(s.strip() for s in lines if s.strip())
                save_pages(cache_file, pages)  # checkpoint từng trang
                total_new += 1
                print(f"    trang {idx + 1}: {len(pages[idx]):,} ký tự ({time.perf_counter() - t0:.0f}s) "
                      f"[tổng {time.perf_counter() - t_start:.0f}s]", flush=True)

    print(f"\nHOÀN TẤT: OCR mới {total_new} trang vào {VIE_CACHE_DIR} "
          f"trong {time.perf_counter() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
