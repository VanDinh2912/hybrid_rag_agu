"""T2 Bước 3 — Kiểm chất lượng OCR mới (EasyOCR vi) so với bản gốc (rapidocr).

Chỉ đọc cache; không gọi model, không sửa corpus/index.
- Trước  = ./.ocr_cache      (rapidocr — mất dấu)
- Sau    = ./.ocr_cache_vie  (EasyOCR vi — giữ dấu)

Số đo mỗi tệp scan:
- word-diacritic ratio trước/sau (định nghĩa như corpus_diacritics).
- tỉ lệ token khớp "từ vựng tiếng Việt" (PROXY tự chứa = hợp token đã fold() của phần
  corpus SẠCH: PDF text-layer + DOCX). KHÔNG phải từ điển chuẩn — chỉ để phát hiện OCR
  sinh rác/không phải tiếng Việt.
- số mốc "Điều N." / "Khoản N." nhận được trước/sau (bảo chứng hồi phục cấu trúc).

Kèm: trích 20 đoạn ngẫu nhiên từ văn bản OCR mới ra tệp để ĐỐI CHIẾU MẮT THƯỜNG với ảnh.

Chạy:  PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/quality_check_vie.py
Ra:    data/loop/diag/corpus_diagnostics/quality_vie.json + manual_20_segments.txt + in bảng.
"""

from __future__ import annotations

import glob
import json
import os
import random
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from src.text_utils import fold  # noqa: E402
from src.loader import DEFAULT_MIN_CHARS_PER_PAGE, DocumentLoader  # noqa: E402
from tools.diag.corpus_diacritics import (  # noqa: E402
    CORPUS_DIR,
    _letter_has_diacritic,
    word_diacritic_ratio,
)

from pypdf import PdfReader  # noqa: E402

OLD_DIR = os.path.join(ROOT, ".ocr_cache")
NEW_DIR = os.path.join(ROOT, ".ocr_cache_vie")
OUT_DIR = os.path.join(ROOT, "data", "loop", "diag", "corpus_diagnostics")

_ARTICLE_RE = re.compile(r"(?i)\b(?:điều|dieu|khoản|khoan)\s+\d+")


def load_cache_dir(d: str) -> dict[str, str]:
    """Gom toàn bộ text OCR trong một thư mục cache, theo stem tệp (bỏ digest)."""
    out: dict[str, list[str]] = {}
    for cf in glob.glob(os.path.join(d, "*.json")):
        stem = os.path.basename(cf).split("__")[0]
        try:
            pages = json.load(open(cf, encoding="utf-8")).get("pages", {})
        except (OSError, ValueError):
            continue
        out.setdefault(stem, []).extend(pages.values())
    return {k: "\n".join(v) for k, v in out.items()}


def vocab_from_clean() -> set[str]:
    """Từ vựng PROXY: token đã fold() của các tệp sạch (PDF text-layer tỉ lệ cao + DOCX)."""
    loader = DocumentLoader(data_dir=CORPUS_DIR)
    vocab: set[str] = set()
    for root, _d, files in os.walk(CORPUS_DIR):
        for fn in files:
            path = os.path.join(root, fn)
            ext = os.path.splitext(fn)[1].lower()
            text = ""
            try:
                if ext == ".docx":
                    from docx import Document as Docx

                    doc = Docx(path)
                    text = "\n".join(p.text for p in doc.paragraphs)
                elif ext == ".pdf":
                    pages = [(p.extract_text() or "") for p in PdfReader(path).pages]
                    # chỉ lấy tệp text-layer (không có trang scan) và đọc tốt
                    if any(len(t.strip()) < DEFAULT_MIN_CHARS_PER_PAGE for t in pages):
                        continue
                    text = "\n".join(pages)
            except Exception:
                continue
            for w in text.split():
                if any(c.isalpha() for c in w):
                    vocab.add(fold(w))
    return vocab


def vocab_ratio(text: str, vocab: set[str]) -> tuple[int, int, float | None]:
    toks = [fold(w) for w in text.split() if any(c.isalpha() for c in w)]
    if not toks:
        return (0, 0, None)
    hit = sum(1 for t in toks if t in vocab)
    return (hit, len(toks), hit / len(toks))


def main() -> None:
    old = load_cache_dir(OLD_DIR)
    new = load_cache_dir(NEW_DIR)
    vocab = vocab_from_clean()
    print(f"[vocab] từ vựng tiếng Việt (proxy) = {len(vocab)} token fold duy nhất")

    stems = sorted(set(old) | set(new))
    rows = []
    for stem in stems:
        o, n = old.get(stem, ""), new.get(stem, "")
        mo, wo, ro = word_diacritic_ratio(o)
        mn, wn, rn = word_diacritic_ratio(n)
        vo, vno, vro = vocab_ratio(n, vocab)
        rows.append({
            "stem": stem,
            "old_words": wo, "old_ratio": ro,
            "new_words": wn, "new_ratio": rn,
            "new_vocab_ratio": vro, "new_vocab_hits": vo,
            "old_article_marks": len(_ARTICLE_RE.findall(o)),
            "new_article_marks": len(_ARTICLE_RE.findall(n)),
            "has_new": bool(n),
        })

    # Tổng corpus theo TỪ: gộp text-layer + docx (đọc tốt) + OCR mới.
    # (text-layer/docx đã đo ở corpus_diacritics; ở đây chỉ cần phần OCR để suy corpus mới.)
    tot_new_w = sum(r["new_words"] or 0 for r in rows)
    tot_new_m = sum(int(round((r["new_ratio"] or 0) * (r["new_words"] or 0))) for r in rows)
    tot_old_w = sum(r["old_words"] or 0 for r in rows)
    tot_old_m = sum(int(round((r["old_ratio"] or 0) * (r["old_words"] or 0))) for r in rows)

    # 20 đoạn ngẫu nhiên để mắt thường đối chiếu ảnh
    rng = random.Random(20261024)
    pool = []
    for stem, txt in new.items():
        for para in re.split(r"\n{2,}", txt):
            para = para.strip()
            if len(para) > 40:
                pool.append((stem, para))
    picks = rng.sample(pool, min(20, len(pool))) if pool else []
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "manual_20_segments.txt"), "w", encoding="utf-8") as f:
        f.write("# 20 đoạn ngẫu nhiên từ OCR EasyOCR(vi) — đối chiếu mắt thường với ảnh gốc\n")
        f.write("# (mở tệp PDF tương ứng, render trang, so số hiệu/Điều/số)\n\n")
        for i, (stem, para) in enumerate(picks, 1):
            f.write(f"[{i}] {stem}\n{para}\n\n")

    payload = {
        "note": "old=.ocr_cache(rapidocr) new=.ocr_cache_vie(EasyOCR vi). vocab_ratio là PROXY "
                "(token fold khớp từ vựng phần corpus sạch), không phải từ điển chuẩn.",
        "ocr_total": {
            "old_words": tot_old_w, "old_marked": tot_old_m,
            "old_ratio": (tot_old_m / tot_old_w) if tot_old_w else None,
            "new_words": tot_new_w, "new_marked": tot_new_m,
            "new_ratio": (tot_new_m / tot_new_w) if tot_new_w else None,
        },
        "per_file": rows,
    }
    json.dump(payload, open(os.path.join(OUT_DIR, "quality_vie.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("\n| tệp | từ(cũ→mới) | dấu cũ | dấu mới | vocab-mới | Điều/Khoản cũ→mới |")
    print("| --- | --- | --- | --- | --- | --- |")
    for r in sorted(rows, key=lambda x: -(x["new_words"] or 0)):
        print("| {stem:44} | {ow}->{nw} | {ro} | {rn} | {vr} | {oa}->{na} |".format(
            stem=r["stem"][:44], ow=r["old_words"], nw=r["new_words"],
            ro=("%.3f" % r["old_ratio"]) if r["old_ratio"] is not None else "—",
            rn=("%.3f" % r["new_ratio"]) if r["new_ratio"] is not None else ("CHƯA OCR" if not r["has_new"] else "—"),
            vr=("%.3f" % r["new_vocab_ratio"]) if r["new_vocab_ratio"] is not None else "—",
            oa=r["old_article_marks"], na=r["new_article_marks"]))
    print(f"\nOCR tổng: cũ {payload['ocr_total']['old_ratio']} → mới {payload['ocr_total']['new_ratio']} "
          f"(theo {tot_new_w} từ). Chi tiết: {OUT_DIR}/quality_vie.json; 20 đoạn: manual_20_segments.txt")


if __name__ == "__main__":
    main()
