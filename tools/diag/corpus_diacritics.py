"""T2 Bước 1 — CHỈ ĐỌC: lập bảng chẩn đoán chất lượng dấu thanh cho 26 tệp nguồn.

Mục đích: với mỗi tệp trong ./data/corpus, trả về
  - loại: PDF text-layer / PDF scan / PDF trộn / DOCX
  - số trang chữ (pypdf) vs số trang scan (dưới ngưỡng -> OCR, theo đúng loader thật)
  - tỉ lệ TỪ còn dấu thanh, tách riêng phần pypdf và phần OCR
  - chẩn đoán nguyên nhân mất dấu: font cũ TCVN3/VNI/ABC, ToUnicode hỏng, hay OCR.

Script không sửa gì: không đụng corpus, không ghi đè chroma_db, không gọi model.
Nó tái dùng đúng cách phân loại trang của src.indexing.loader (min_chars_per_page) và đọc
kết quả OCR từ ./​.ocr_cache qua chính DocumentLoader._cache_load, nên số đo phản ánh
đúng văn bản đang nằm trong corpus hiện hành.

Chạy:  PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/corpus_diacritics.py
Ra:    data/loop/diag/corpus_diagnostics/per_file.json  +  in bảng markdown ra stdout.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pypdf import PdfReader  # noqa: E402

from src.indexing.loader import (  # noqa: E402
    DEFAULT_MIN_CHARS_PER_PAGE,
    DocumentLoader,
)

CORPUS_DIR = ROOT / "data" / "corpus"
OUT_DIR = ROOT / "data" / "loop" / "diag" / "corpus_diagnostics"

# Chữ cái có dấu tiếng Việt: ký tự Latin tổ hợp (NFD tách ra >1 codepoint) hoặc đ/Đ.
_VIET_INLINE = set("đĐ")


def _letter_has_diacritic(c: str) -> bool:
    if not c.isalpha():
        return False
    if c in _VIET_INLINE:
        return True
    name = unicodedata.name(c, "")
    return name.startswith("LATIN") and len(unicodedata.normalize("NFD", c)) > 1


def _word_has_diacritic(word: str) -> bool:
    return any(_letter_has_diacritic(c) for c in word)


def word_diacritic_ratio(text: str) -> tuple[int, int, float | None]:
    """(số từ có dấu, tổng số từ có chữ, tỉ lệ). Từ = token whitespace chứa ≥1 chữ cái."""
    words = [w for w in text.split() if any(c.isalpha() for c in w)]
    if not words:
        return (0, 0, None)
    marked = sum(1 for w in words if _word_has_diacritic(w))
    return (marked, len(words), marked / len(words))


def missing_glyph_ratio(text: str) -> float:
    """Tỉ lệ ký tự đáng ngờ: '\ufffd' hoặc nằm ở Latin-1 Supplement nhưng KHÔNG phải
    chữ cái tiếng Việt có dấu. Chữ layer PDF giải mã sai (ToUnicode hỏng / font cũ)
    thường bơm đúng loại ký tự này (Ð Ã § ¬ × ' " )."""
    if not text:
        return 0.0
    letters = [c for c in text if c.isalpha()]
    sus = sum(1 for c in text if c == "\ufffd")
    for c in letters:
        cp = ord(c)
        if 0x80 <= cp <= 0xFF and not _letter_has_diacritic(c):
            sus += 1
    denom = max(len(letters), 1) + sus
    return sus / denom if denom else 0.0


# Tên font di sản tiếng Việt (TCVN3/ABC hay VNI Windows). ".Vn"/"Vn" và "VNI-" là chữ ký
# kinh điển; "ABC"/"TN1"/"TH-"/"SVN-" hay gặp ở bản Word cũ xuất PDF.
_LEGACY_FONT_RE = re.compile(
    r"(^\.?vn[a-z]|^vni[-_]|[-_]vni|abc|^tn\d|^th-|^svn-)", re.IGNORECASE
)


def _font_base_name(font_obj) -> str:
    bf = font_obj.get("/BaseFont")
    return str(bf).lstrip("/") if bf else "?"


def inspect_fonts(reader: PdfReader, max_pages: int = 12) -> dict:
    """Liệt kê BaseFont + cờ có /ToUnicode trên các trang đầu. Trả về tập tên, số font,
    số font có ToUnicode, và danh sách tên khớp mẫu di sản."""
    names: set[str] = set()
    with_tounicode: set[str] = set()
    for page in reader.pages[:max_pages]:
        try:
            font_res = (page.get("/Resources") or {}).get("/Font") or {}
        except Exception:
            continue
        try:
            font_map = font_res.get_object()
        except Exception:
            continue
        for ref in font_map.values():
            try:
                obj = ref.get_object()
            except Exception:
                continue
            nm = _font_base_name(obj)
            names.add(nm)
            if "/ToUnicode" in obj:
                with_tounicode.add(nm)
    legacy = sorted(n for n in names if _LEGACY_FONT_RE.search(_strip_subset(n)))
    return {
        "n_fonts": len(names),
        "n_with_tounicode": len(with_tounicode),
        "tounicode_frac": (len(with_tounicode) / len(names)) if names else None,
        "legacy_fonts": legacy,
        "all_fonts": sorted(names),
    }


def _strip_subset(name: str) -> str:
    """Bỏ tiền tố subset 'ABCDEF+' khỏi tên font khi so mẫu."""
    return re.sub(r"^[A-Z]{6}\+", "", name)


def classify_and_measure(path: str, loader: DocumentLoader) -> dict:
    ext = os.path.splitext(path)[1].lower()
    row: dict = {
        "file": os.path.basename(path),
        "rel": os.path.relpath(path, CORPUS_DIR).replace("\\", "/"),
        "tier": loader._tier_of(path),
        "ext": ext,
        "size_bytes": os.path.getsize(path),
    }

    if ext == ".docx":
        from docx import Document as DocxDocument

        doc = DocxDocument(path)
        parts = [p.text for p in doc.paragraphs]
        for t in doc.tables:
            for r in t.rows:
                parts.append(" ".join(c.text for c in r.cells))
        text = "\n".join(parts)
        marked, total, ratio = word_diacritic_ratio(text)
        row.update(
            kind="DOCX", pages=None, text_pages=None, scan_pages=None,
            ratio=ratio, words=total, marked=marked,
            ocr_ratio=None, text_ratio=ratio, legacy_fonts=[], tounicode_frac=None,
            missing_glyph=missing_glyph_ratio(text),
        )
        return row

    if ext != ".pdf":
        row.update(kind=ext or "?", ratio=None, note="định dạng loader không trích xuất")
        return row

    reader = PdfReader(path)
    pages_text = [(p.extract_text() or "") for p in reader.pages]
    n_pages = len(pages_text)
    scan_pages = [i for i, t in enumerate(pages_text) if len(t.strip()) < DEFAULT_MIN_CHARS_PER_PAGE]
    text_pages = [i for i in range(n_pages) if i not in set(scan_pages)]

    # Phần text-layer (pypdf) thuần
    pypdf_text = "\n".join(pages_text[i] for i in text_pages)
    m_t, w_t, r_t = word_diacritic_ratio(pypdf_text)

    # Phần OCR: đọc từ cache qua chính loader (không gọi lại OCR)
    ocr_text = ""
    if scan_pages:
        cached = loader._cache_load(path, scan_pages)
        if cached is not None:
            ocr_text = "\n".join(cached.get(i, "") for i in scan_pages)
    m_o, w_o, r_o = word_diacritic_ratio(ocr_text)

    # Toàn bộ văn bản pipeline thực sự nạp: trang text = pypdf, trang scan = OCR (nếu cache có).
    merged_parts = [pages_text[i] for i in text_pages]
    merged_parts.append(ocr_text)
    merged = "\n".join(merged_parts)
    m_all, w_all, r_all = word_diacritic_ratio(merged)

    fonts = inspect_fonts(reader)

    if not scan_pages:
        kind = "PDF-TEXT"
    elif not text_pages:
        kind = "PDF-SCAN"
    else:
        kind = "PDF-MIXED"

    row.update(
        kind=kind, pages=n_pages, text_pages=len(text_pages), scan_pages=len(scan_pages),
        ratio=r_all, words=w_all, marked=m_all,
        text_ratio=r_t, text_words=w_t,
        ocr_ratio=r_o, ocr_words=w_o,
        legacy_fonts=fonts["legacy_fonts"],
        tounicode_frac=fonts["tounicode_frac"],
        n_fonts=fonts["n_fonts"],
        missing_glyph=missing_glyph_ratio(pypdf_text if text_pages else merged),
        all_fonts=fonts["all_fonts"],
    )
    return row


def diagnose(row: dict) -> str:
    kind = row.get("kind")
    ratio = row.get("ratio")
    if kind == "DOCX":
        return "đọc tốt" if (ratio or 0) >= 0.6 else "docx mất dấu BẤT THƯỜNG (không phải OCR)"
    if kind == "PDF-SCAN":
        return "OCR rapidocr mất dấu → cần OCR giữ dấu (iii) hoặc bản gốc (ii)"
    if kind == "PDF-MIXED":
        return (
            f"trộn: text {(row.get('text_ratio') or 0):.2f} / OCR {(row.get('ocr_ratio') or 0):.2f} "
            "→ mất dấu chủ yếu do phần scan"
        )
    # PDF-TEXT
    r = ratio or 0.0
    if r >= 0.6:
        return "pypdf đọc tốt (subset font có /Differences chuẩn)"
    if row.get("legacy_fonts"):
        return f"font di sản {row['legacy_fonts']} + không ToUnicode → thử ánh xạ bảng mã (i)"
    if (row.get("missing_glyph") or 0) > 0.15:
        return "ToUnicode hỏng / glyph lạ (mojibake) → không ánh xạ được, cần bản gốc"
    return "text-layer mất dấu không rõ nguyên nhân (đối chiếu glyph thủ công)"


def fmt(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def main() -> None:
    paths = []
    for root, _d, files in os.walk(CORPUS_DIR):
        for fn in files:
            if os.path.splitext(fn)[1].lower() in {".pdf", ".docx", ".doc", ".txt"}:
                paths.append(os.path.join(root, fn))
    paths.sort()

    loader = DocumentLoader(data_dir=str(CORPUS_DIR))

    rows = []
    for p in paths:
        try:
            row = classify_and_measure(p, loader)
        except Exception as exc:
            row = {"file": os.path.basename(p), "rel": os.path.relpath(p, CORPUS_DIR).replace("\\", "/"),
                   "kind": "ERROR", "note": f"lỗi: {exc}"}
        row["cause"] = diagnose(row) if row.get("kind") != "ERROR" else row.get("note", "")
        rows.append(row)

    # Trọng số toàn corpus theo TỪ (không phải theo tệp) — so với con số 18,6% đã công bố.
    tot_words = sum(r.get("words") or 0 for r in rows)
    tot_marked = sum(r.get("marked") or 0 for r in rows)
    corpus_ratio = (tot_marked / tot_words) if tot_words else None
    ocr_words = sum(r.get("ocr_words") or 0 for r in rows)
    text_words = sum(r.get("text_words") or 0 for r in rows)
    ocr_marked = sum(
        int(round((r.get("ocr_ratio") or 0) * (r.get("ocr_words") or 0))) for r in rows
    )
    text_marked = sum(
        int(round((r.get("text_ratio") or 0) * (r.get("text_words") or 0))) for r in rows
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "method": "word-diacritic = (số token whitespace chứa >=1 chu cai co dau Viet) / (so token chua chu cai); "
                  "phan loai trang theo src.indexing.loader.DEFAULT_MIN_CHARS_PER_PAGE; OCR doc tu .ocr_cache qua loader",
        "min_chars_per_page": DEFAULT_MIN_CHARS_PER_PAGE,
        "corpus_word_ratio": corpus_ratio,
        "corpus_words": tot_words,
        "split": {
            "text_layer_words": text_words,
            "text_layer_marked": text_marked,
            "text_layer_ratio": (text_marked / text_words) if text_words else None,
            "ocr_words": ocr_words,
            "ocr_marked": ocr_marked,
            "ocr_ratio": (ocr_marked / ocr_words) if ocr_words else None,
        },
        "per_file": rows,
    }
    (OUT_DIR / "per_file.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Bảng markdown (sắp theo số từ, ưu tiên tệp nặng)
    print("# T2 Bước 1 — bảng chẩn đoán 26 tệp nguồn\n")
    print(f"Tỉ lệ từ có dấu toàn corpus (theo từ): **{fmt(corpus_ratio)}** "
          f"({tot_marked}/{tot_words} từ). "
          f"Tách: text-layer {fmt(payload['split']['text_layer_ratio'])} "
          f"({text_words} từ), OCR {fmt(payload['split']['ocr_ratio'])} ({ocr_words} từ).\n")
    hdr = ("tệp", "loại", "tier", "trang(t/s)", "dấu(tất cả)", "dấu(text)", "dấu(OCR)",
           "cổ đông?/font", "nguyên nhân")
    print("| " + " | ".join(hdr) + " |")
    print("| " + " | ".join("---" for _ in hdr) + " |")
    for r in sorted(rows, key=lambda x: -(x.get("words") or 0)):
        legacy = ", ".join(_strip_subset(f) for f in r.get("legacy_fonts", [])) or "—"
        pageinfo = "—"
        if r.get("pages"):
            pageinfo = f"{r.get('text_pages', 0)}/{r.get('scan_pages', 0)}"
        cells = (
            r["file"][:44],
            str(r.get("kind")),
            str(r.get("tier", "")),
            pageinfo,
            fmt(r.get("ratio")),
            fmt(r.get("text_ratio")),
            fmt(r.get("ocr_ratio")),
            legacy,
            r.get("cause", ""),
        )
        print("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    print(f"\n(Ghi chi tiết: {OUT_DIR / 'per_file.json'})")


if __name__ == "__main__":
    main()
