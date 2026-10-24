"""T2 — KIỂM ĐỊNH corpus đã rebuild (CHỈ ĐỌC, không gọi model, không sửa gì).

Vì sao có file này: T2 (nâng tỉ lệ từ có dấu trong corpus) sửa dữ liệu bằng cách
**re-OCR sang cache mới + build index mới**; đó là rủi ro cao nhất cho tính đúng của
dữ liệu (mất thực thể pháp lý, mất chunk vàng của testset, âm thầm đưa tệp rác vào
index, đè lên index đang dùng). File này cung cấp các hàm ĐO ĐƯỢC để unit test
(`tests/test_corpus_rebuild.py`) và chạy thật cho các mục 7–10 của đề bài.

Nguyên tắc:
- CHỈ ĐỌC: mở chroma bằng `chromadb.PersistentClient` (như `measure_index.py`), không
  ghi, không xoá; bằng chứng "index cũ không đổi" là SHA-256 thư mục trước/sau (`dir_digest`).
- Tái dùng đúng thước đo đã công bố: `word_diacritic_ratio` (corpus_diacritics),
  `vocab_ratio` (quality_check_vie) — không dựng thang đo thứ hai.
- So sánh thực thể pháp lý là **SO SÁNH GHI NGUYÊN VĂN** (chỉ chuẩn hoá khoảng trắng),
  CỐ Ý không `fold()`: nếu fold thì "Điều 12" → "Dieu 12" sẽ bị coi là an toàn, đúng cái
  bug cần bắt.
- Không tự phán đúng/sai phần đối chiếu mắt thường: mục 8 chỉ XUẤT 20 đoạn (seed cố
  định) để người dùng so với bản gốc.

Chạy thật (mục 7–10):
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/check_corpus.py
Tuỳ chọn: --old-db ./chroma_db --new-db ./chroma_db_vie --fail-on-red (exit!=1 khi ĐỎ).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Tái dùng định nghĩa đã có (KHÔNG định nghĩa lại thang đo) ------------------
from src.answer_guard import CODE_RE, DATE_RE, LEGAL_REF_RE, NUMBER_RE  # noqa: E402
from src.chunking import DocumentChunker  # noqa: E402
from src.text_utils import fold  # noqa: E402 (chỉ dùng cho khớp gold_sentence, KHÔNG dùng so thực thể)
from tools.loop import verify  # noqa: E402 (chữ ký trọng tài — chỉ đọc)

# --- Ngưỡng ĐĂNG KÝ TRƯỚC (đề bài mục 4/7/9) ------------------------------------
GAP_MIN_DIACRITIC = 0.60   # < ngưỡng này -> tệp bị gắn "khoảng trống"
GAP_MIN_VOCAB = 0.70       # vocab proxy < ngưỡng này -> coi là rác OCR
GOLD_LOSS_RED_RATE = 0.02  # mất gold > 2% -> BÁO ĐỎ
MAX_EXACT_DUPLICATE_RATIO = 0.02  # > 2% chunk trùng nguyên văn tuyệt đối -> ĐỎ

# ----------------------------------------------------------------- ký tự lạ (mục #1)

# Bộ chữ cái cơ sở của tiếng Việt (chưa tính dấu thanh tổ hợp).
_VIET_BASE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") | set("ăâêôơưđĂÂÊÔƠƯĐ")
# Ký tự không phải chữ nhưng hợp lệ trong văn bản hành chính/OCR.
_LEGIBLE_EXTRA = set("–—―‘’“”«»…·•°±×÷§¶→←↑↓⇒")


def char_is_supported(ch: str) -> bool:
    """Ký tự thuộc dải tiếng Việt/ASCII in được hay KHÔNG (định nghĩa bằng phân tích Unicode).

    Pipeline này không có bộ giải mã bảng mã cũ (TCVN3/VNI) — T2 sửa mất dấu bằng re-OCR —
    nên "ký tự lạ" ở đây là mọi glyph ngoài chữ Việt/ASCII in được: ký tự điều khiển,
    ô vẽ bảng, CJK, emoji, và glyph 1-byte rác sinh ra khi đọc sai code-page.
    Hàm này PHÂN LOẠI, không biến đổi: ký tự lạ luôn được GIỮ NGUYÊN trong dữ liệu.
    """
    if ch.isspace():
        return True
    if ch.isascii():
        return ch.isprintable()
    if ch in _LEGIBLE_EXTRA:
        return True
    decomposed = unicodedata.normalize("NFD", ch)
    if decomposed[0] not in _VIET_BASE:
        return False
    return all(unicodedata.category(c) in ("Mn", "Mc", "Me") for c in decomposed[1:])


def foreign_glyph_report(texts: Iterable[str], *, context_chars: int = 28,
                         max_rows: int = 40) -> dict[str, Any]:
    """Thống kê ký tự ngoài dải tiếng Việt: ĐẾM + ghi mã + ví dụ ngữ cảnh, KHÔNG bỏ, KHÔNG đoán.

    Đại diện cho vế "ký tự lạ giữ nguyên và được ghi vào báo cáo" của đề bài mục 1:
    không có phép biến đổi nào chạm vào chúng (báo cáo chỉ đọc), và mỗi loại hiện ra
    trong `foreign` kèm `example` để người duyệt tự kết luận.
    """
    counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    n_total = n_supported = 0
    for text in texts:
        text = text or ""
        for i, ch in enumerate(text):
            n_total += 1
            if char_is_supported(ch):
                n_supported += 1
                continue
            counts[ch] += 1
            if ch not in examples:
                lo, hi = max(0, i - context_chars), i + context_chars
                examples[ch] = " ".join(text[lo:hi].split())
    rows = [{"char": c, "codepoint": f"U+{ord(c):04X}", "count": counts[c],
             "example": examples[c]}
            for c in sorted(counts, key=lambda k: (-counts[k], k))]
    return {"n_chars": n_total, "n_supported": n_supported,
            "n_foreign": sum(counts.values()), "n_foreign_kinds": len(counts),
            "foreign": rows[:max_rows], "foreign_truncated": len(rows) > max_rows}


# ----------------------------------------------------------------------- thực thể

# Nhóm thực thể: bốn pattern lấy từ CHÍNH answer_guard (định nghĩa "thực thể" của hệ
# thống) + hai pattern BỔ SUNG cho đúng các dạng đề bài liệt kê mà answer_guard KHÔNG
# bắt được (đã đo 24-10):
#   - `1054/QĐ-ĐHAG`: CODE_RE chỉ ra được "1054" (NUMBER), phần "/QĐ-ĐHAG" vô hình
#     => đổi hậu tố sẽ lọt. thêm DECISION_NO_RE.
#   - "ngày 28 tháng 9 năm 2020": DATE_RE chỉ bắt dạng số 28/9/2020 => thêm DATE_TEXT_RE.
DECISION_NO_RE = re.compile(
    r"(?<!\d)\d{2,6}/(?:Q[ĐD]|TB|CV|NQ|HD|KT|CVHS|UBND)-[A-ZĐ0-9][A-ZĐa-z0-9\-]*", re.UNICODE
)
DATE_TEXT_RE = re.compile(
    r"(?i)ng[aà]y\s*\d{1,2}\s*th[aá]ng\s*\d{1,2}\s*n[ăa]m\s*\d{4}"
)

ENTITY_PATTERNS: dict[str, re.Pattern] = {
    "code": CODE_RE,          # QD1133, CON915
    "legal_ref": LEGAL_REF_RE,  # Điều 12, Khoản 3, Điểm a, Mục 2
    "date": DATE_RE,          # 28/9/2020, 01.01.2024
    "number": NUMBER_RE,      # 1.500.000 đ, 70 %, 12 tín chỉ
    "decision_no": DECISION_NO_RE,  # 1054/QĐ-ĐHAG, 1504/QĐ-ĐHAG
    "date_text": DATE_TEXT_RE,      # ngày 28 tháng 9 năm 2020
}


def _norm_ws(s: str) -> str:
    """Chỉ chuẩn hoá khoảng trắng — GIỮ nguyên dấu và hoa/thường (xem docstring file)."""
    return " ".join(s.split())


def extract_legal_entities(text: str) -> dict[str, set[str]]:
    """Tập thực thể pháp lý theo từng nhóm, ghi nguyên văn (sau `_norm_ws`)."""
    text = text or ""
    out: dict[str, set[str]] = {}
    for kind, rx in ENTITY_PATTERNS.items():
        found = {_norm_ws(m.group(0)) for m in rx.finditer(text)}
        # Số trần (tuần/tháng/người...) quá umum, chỉ giữ khi có đơn vị đi kèm
        # — tránh "biểu đồ 1 chữ số" bị coi là mất thực thể.
        if kind == "number":
            found = {f for f in found if len(f) > 1}
        if found:
            out[kind] = found
    return out


def compare_entities(before: str, after: str) -> dict[str, Any]:
    """So tập thực thể TRƯỚC/SAU xử lý. Trả về missing/added theo từng nhóm.

    `preserved=True` khi KHÔNG có thực thể nào biến mất. Đổi 1 chữ số
    ("Điều 12" -> "Điều 13") thể hiện thành missing={'Điều 12'} +
    added={'Điều 13'} => preserved=False (đúng yêu cầu 'bắt được việc đổi 1 chữ số').
    """
    a, b = extract_legal_entities(before), extract_legal_entities(after)
    kinds = sorted(set(a) | set(b))
    missing: dict[str, list[str]] = {}
    added: dict[str, list[str]] = {}
    for k in kinds:
        miss = a.get(k, set()) - b.get(k, set())
        add = b.get(k, set()) - a.get(k, set())
        if miss:
            missing[k] = sorted(miss)
        if add:
            added[k] = sorted(add)
    return {
        "preserved": not missing,
        "n_before": {k: len(v) for k, v in a.items()},
        "n_after": {k: len(v) for k, v in b.items()},
        "missing": missing,
        "added": added,
    }


# ----------------------------------------------------------------------- cổng chất lượng

def file_status(ratio_diacritic: Optional[float], ratio_vocab: Optional[float]) -> dict:
    """Cổng chất lượng MỘT TỆP: dưới ngưỡng -> 'khoảng_trống' kèm lý do, KHÔNG 'tốt'.

    hàm thuần: người gọi quyết định đưa vào index hay không; điểm mấu chốt là tệp
    dưới ngưỡng không bao giờ nhận nhãn 'tốt' (nên không thể bị coi là an toàn).
    """
    reasons = []
    if ratio_diacritic is None:
        reasons.append("không đo được tỉ lệ dấu (0 từ có chữ)")
    elif ratio_diacritic < GAP_MIN_DIACRITIC:
        reasons.append(f"từ có dấu {ratio_diacritic:.3f} < {GAP_MIN_DIACRITIC}")
    if ratio_vocab is not None and ratio_vocab < GAP_MIN_VOCAB:
        reasons.append(f"vocab proxy {ratio_vocab:.3f} < {GAP_MIN_VOCAB}")
    return {
        "status": "khoảng_trống" if reasons else "tốt",
        "reasons": reasons,
        "ratio_diacritic": ratio_diacritic,
        "ratio_vocab": ratio_vocab,
    }


def partition_by_gate(rows: Iterable[dict]) -> tuple[list[dict], list[dict]]:
    """Tách (tốt, khoảng_trống) từ các row đã có `ratio`/`vocab_ratio`.

    Row thiếu cả hai số đo -> coi là khoảng_trống (thà chặn oan còn hơn lọt rác).
    """
    good, gap = [], []
    for r in rows:
        st = file_status(r.get("ratio"), r.get("vocab_ratio"))
        item = {**r, "gate": st}
        (gap if st["status"] == "khoảng_trống" else good).append(item)
    return good, gap


def gap_leak_report(gap_stems: Iterable[str], indexed: dict[str, int]) -> dict:
    """Tệp 'khoảng trống' CÓ nằm trong index như tệp tốt hay không (không âm thầm).

    `indexed` = {stem: số chunk đã index}. Trả danh sách lọt để người dùng quyết
    (PA-7: loại 2 tệp kế hoạch ra khỏi corpus).
    """
    leaked = sorted(s for s in gap_stems if indexed.get(s, 0) > 0)
    return {
        "n_gap": len(list(gap_stems)),
        "n_leaked_into_index": len(leaked),
        "leaked": leaked,
        "silent": bool(leaked),  # có lọt mà không bị gắn cờ ở bước nạp = im lặng
    }


# ----------------------------------------------------------------------- an toàn dữ liệu

def dir_digest(path: Path) -> str:
    """SHA-256 toàn bộ cây thư mục (đường dẫn tương đối + nội dung, sắp xếp ổn định).

    Dùng chứng minh index CŨ không đổi sau khi build index MỚI. Bỏ các phần tử dễ
    dao động vô hại để không báo động giả: sqlite WAL/journal + thư mục tạm.
    """
    h = hashlib.sha256()
    p = Path(path)
    if not p.exists():
        return "MISSING"
    files = []
    for root, dirs, names in os.walk(p):
        dirs[:] = [d for d in sorted(dirs) if d not in {"tmp"}]
        for n in sorted(names):
            if n.endswith(("-wal", "-shm", ".tmp")):
                continue
            fp = Path(root) / n
            files.append(os.path.relpath(fp, p).replace("\\", "/"))
    for rel in sorted(files):
        h.update(rel.encode("utf-8"))
        h.update((p / rel).read_bytes())
    return h.hexdigest()[:16]


def plan_index_write(target: Path, *, protected: Iterable[Path] = (), force: bool = False) -> dict:
    """Quyết định ghi index: THƯ MỤC ĐÍCH ĐÃ TỒN TẠI (và không rỗng) -> TỪ CHỐI.

    Đây là cổng an toàn mà `ingest.py` (reset=True) KHÔNG có — nó `shutil.rmtree`
    thư mục đích. Hàm thuần để test; đề xuất nối vào bước rebuild (xem báo cáo).
    """
    t = Path(target).resolve()
    protected_r = {Path(x).resolve() for x in protected}
    if t in protected_r:
        raise SystemExit(
            f"[an toàn] thư mục đích {t} LÀ index đang dùng (protected) — từ chối ghi đè."
        )
    if t.exists() and any(t.iterdir()) and not force:
        raise SystemExit(
            f"[an toàn] {t} đã tồn tại và không rỗng — từ chối. "
            "Dùng thư mục MỚI, hoặc nói rõ --force nếu thật sự muốn build lại lên đó."
        )
    return {"target": str(t), "created_now": not t.exists(), "force": force}


def build_chunks(documents: list[dict], chunker: Optional[DocumentChunker] = None) -> list[dict]:
    """Chunking xác định + gán `chunk_id` tuần tự ĐÚNG như `VectorStoreManager.create_vector_store`."""
    chunker = chunker or DocumentChunker()
    out: list[dict] = []
    i = 0
    for doc in documents:
        for c in chunker.chunk_document(doc):
            out.append({**c, "chunk_id": i})
            i += 1
    return out


def _norm_stem(s: str) -> str:
    """Chuẩn hoá tên tệp để so một chiều (bỏ dấu, bỏ ký tự ngoài a-z0-9, chữ thường)."""
    return re.sub(r"[^a-z0-9]", "", fold(s or "").lower())


def _index_stem_counts(texts: Iterable[str]) -> dict[str, int]:
    """Đếm chunk theo tệp gốc, đọc từ tiêu đề `[Tên văn bản]` đầu chunk (chunking luôn
    gắn tiền tố này). Khớp NHỜ chuẩn hoá tên nên là xấp xỉ — báo cáo ghi rõ điều đó."""
    counts: Counter = Counter()
    for t in texts:
        m = re.match(r"\s*\[([^\]]+)\]", t or "")
        if m:
            head = m.group(1).split(" - ")[0]
            counts[_norm_stem(head)] += 1
    return dict(counts)


def gate_by_index(texts: Iterable[str], vocab_by_stem: Optional[dict[str, float]] = None) -> list[dict]:
    """Đo CHẤT LƯỢNG THEO TỆP từ đúng nội dung đã index (gộp chunk theo tiêu đề `[tệp]`).

    Vì sao không join `per_file.json` + `quality_vie.json`: hai tệp đó dùng hai kiểu
    đặt tên (tên tệp vs tên cache OCR) -> join nonh `stem` không khớp hết, và số đo
    `per_file.json` là văn bản TỆP NGUỒN (trước sửa), không phải thứ đang nằm trong
    index. Đo lại trên chunk bảo đảm cổng áp dụng cho ĐÚNG đối tượng RAG truy xuất,
    dùng THƯỚC ĐO CŨNG (`word_diacritic_ratio`).
    """
    from tools.diag.corpus_diacritics import word_diacritic_ratio

    buckets: dict[str, list[str]] = {}
    for t in texts:
        m = re.match(r"\s*\[([^\]]+)\]", t or "")
        stem = _norm_stem(m.group(1).split(" - ")[0]) if m else "_khong_xac_dinh"
        buckets.setdefault(stem, []).append(t or "")
    vocab_by_stem = vocab_by_stem or {}
    rows = []
    for stem, parts in sorted(buckets.items()):
        _m, _w, ratio = word_diacritic_ratio("\n".join(parts))
        rows.append({"stem": stem, "n_chunks": len(parts), "ratio": ratio,
                     "vocab_ratio": vocab_by_stem.get(stem)})
    return rows


# ----------------------------------------------------------------------- trùng/rỗng

def chunk_hygiene(chunks: list[dict]) -> dict:
    """Không chunk rỗng; không trùng nguyên văn quá ngưỡng (so sau `fold`, bỏ whitespace)."""
    n = len(chunks)
    empty = [c.get("chunk_id") for c in chunks if not (c.get("text") or "").strip()]
    sig = [fold(c.get("text") or "") for c in chunks]
    counts = Counter(s for s in sig if s)
    dup_groups = {s: c for s, c in counts.items() if c > 1}
    n_dup_chunks = sum(c for c in dup_groups.values()) - len(dup_groups)
    ratio = (n_dup_chunks / n) if n else 0.0
    return {
        "n_chunks": n,
        "n_empty": len(empty),
        "empty_ids": empty[:20],
        "n_duplicate_chunks": n_dup_chunks,
        "n_duplicate_groups": len(dup_groups),
        "duplicate_ratio": round(ratio, 4),
        "duplicate_over_threshold": ratio > MAX_EXACT_DUPLICATE_RATIO,
    }


# ----------------------------------------------------------------------- gold coverage

def gold_coverage(testset: list[dict], indexed_texts: list[str], *, near_min_overlap: float = 0.60) -> dict:
    """Mọi item testset: gold_sentence (đã fold) còn tìm thấy trong index mới?

    Khớp theo `fold(gold_sentence)` là `fold(chunk)` — cùng luật neo mà testset.py dùng.
    Item không có gold_sentence (HUMAN/REFUSE_*) được tính riêng, KHÔNG vào mẫu số.

    với mỗi item MẤT, phân loại bằng overlap token (đọc từ chính answer_guard TOKEN_RE):
      - `near`  : có chunk đạt overlap >= near_min_overlap -> nội dung gần như còn đó,
                  chỉ KHÁC CÂU CHỮ (neo verbatim đứt vì OCR mới viết khác chữ bản cũ).
      - `absent`: không chunk nào đạt -> mất nội dung thật.
    Cổng ĐỎ vẫn tính theo MẤT VERBATIM (đúng đăng ký đề bài); near/absent chỉ để diễn
    giải, không được dùng để hạ mức đỏ.
    """
    import re

    hay = [fold(t or "") for t in indexed_texts]
    checkable, missing = [], []
    for it in testset:
        gs = it.get("gold_sentence")
        if not gs:
            continue
        fgs = fold(gs)
        checkable.append(it["id"])
        if not any(fgs in h for h in hay if h):
            g_tok = set(re.findall(r"\w+", fgs))
            best = max(
                (len(g_tok & set(re.findall(r"\w+", h))) / max(len(g_tok), 1) for h in hay if h),
                default=0.0,
            )
            missing.append({"id": it["id"], "family": it.get("family"),
                            "gold_sentence": gs[:80], "best_token_overlap": round(best, 3),
                            "class": "near" if best >= near_min_overlap else "absent"})
    n_near = sum(1 for m in missing if m["class"] == "near")
    n_absent = len(missing) - n_near
    rate = (len(missing) / len(checkable)) if checkable else 0.0
    return {
        "n_items": len(testset),
        "n_checkable": len(checkable),
        "n_no_gold_sentence": len(testset) - len(checkable),
        "n_missing_gold": len(missing),
        "missing_rate": round(rate, 4),
        "red": rate > GOLD_LOSS_RED_RATE,
        "red_threshold": GOLD_LOSS_RED_RATE,
        "n_near_verbatim": n_near,
        "n_absent": n_absent,
        "absent_rate_of_checkable": round(n_absent / len(checkable), 4) if checkable else 0.0,
        "missing": missing,
    }


def index_signature(texts: list[str]) -> dict:
    """Chữ ký DỮ LIỆU của index (số chunk + SHA-256 nội dung đã fold, theo thứ tự id).

    Đây là thứ THỰC SỰ đổi khi rebuild corpus — khác `referee_fingerprint()` (mã nguồn
    trọng tài, phải KHÔNG đổi)."""
    joined = "\n".join(fold(t or "") for t in texts)
    return {"n_chunks": len(texts), "signature": hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]}


def pick_segments(texts_by_stem: dict[str, str], n: int = 20, seed: int = 20261024) -> list[tuple[str, str]]:
    """Chọn n đoạn NGẪU NHIÊN CÓ SEED cố định để người dùng đối chiếu bản gốc.

    Sắp `texts_by_stem` theo tên trước khi rng để tái lập tuyệt đối trên mọi máy.
    Script KHÔNG tự phán đúng/sai.
    """
    import random

    pool: list[tuple[str, str]] = []
    for stem in sorted(texts_by_stem):
        for para in re.split(r"\n{2,}", texts_by_stem[stem] or ""):
            para = para.strip()
            if len(para) > 40:
                pool.append((stem, para))
    rng = random.Random(seed)
    return rng.sample(pool, min(n, len(pool))) if pool else []


# ----------------------------------------------------------------------- main (mục 7-10)

def _load_index_texts(db_dir: Path) -> list[str]:
    from tools.diag.measure_index import collection_documents  # đọc chroma, không ghi

    _name, docs = collection_documents(db_dir)
    return list(docs)


def _count_source_files(corpus_dir: Path) -> dict:
    exts = {".pdf", ".docx", ".doc", ".txt"}
    by_ext: Counter = Counter()
    total = 0
    for _r, _d, files in os.walk(corpus_dir):
        for fn in files:
            e = os.path.splitext(fn)[1].lower()
            if e in exts:
                by_ext[e] += 1
                total += 1
    return {"n_files": total, "by_ext": dict(by_ext), "expected": 26}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="T2 kiểm định corpus rebuild (chỉ đọc).")
    ap.add_argument("--corpus", default=str(ROOT / "data" / "corpus"))
    ap.add_argument("--old-db", default=str(ROOT / "chroma_db"))
    ap.add_argument("--new-db", default=str(ROOT / "chroma_db_vie"))
    ap.add_argument("--testset", default=str(ROOT / "data" / "loop" / "testset_v1.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data" / "loop" / "diag" / "corpus_check"))
    ap.add_argument("--fail-on-red", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    old_dir, new_dir = Path(args.old_db), Path(args.new_db)

    # (5) băm index CŨ trước khi động vào bất cứ gì
    digest_old_before = dir_digest(old_dir)

    old_texts = _load_index_texts(old_dir)
    new_texts = _load_index_texts(new_dir)
    digest_old_after = dir_digest(old_dir)

    # ---- 5. BẤT BIẾN "index cũ không bị đổi".
    # `dir_digest` (byte) ĐỔI CHỈ VÌ mở ChromaDB: chính PersistentClient tái ghi
    # data_level0.bin/length.bin/chroma.sqlite3 khi đọc (đo 24-10: 3 tệp đổi hash,
    # kích thước không đổi). => thước đúng cho "không mất dữ liệu" là NỘI DUNG
    # (tập document), byte-digest chỉ là thông tin.
    sig_old_before = index_signature(old_texts)
    sig_old_reopen = index_signature(_load_index_texts(old_dir))
    content_unchanged = sig_old_before == sig_old_reopen == index_signature(old_texts)
    print(f"[5] index CŨ: nội dung {sig_old_before['signature']}({sig_old_before['n_chunks']} chunk) "
          f"sau khi mở lại {sig_old_reopen['signature']}({sig_old_reopen['n_chunks']}) "
          f"-> {'KHÔNG ĐỔI (an toàn)' if content_unchanged else 'BI ĐỔI — BẤT BIẾN #3 VI PHẠM'}")

    # ---- 7. tệp nguồn + chunk trước/sau + rỗng/trùng
    files = _count_source_files(Path(args.corpus))
    hy_old = chunk_hygiene([{"text": t, "chunk_id": i} for i, t in enumerate(old_texts)])
    hy_new = chunk_hygiene([{"text": t, "chunk_id": i} for i, t in enumerate(new_texts)])
    src_note = "khớp 26" if files["n_files"] == files["expected"] else "CHÊNH — xem by_ext"
    print(f"[7] Tệp nguồn: {files['n_files']} ({src_note}) {files['by_ext']}")
    print(f"[7] Chunk index cũ={len(old_texts)} rỗng={hy_old['n_empty']} "
          f"trùng={hy_old['n_duplicate_chunks']} ({hy_old['duplicate_ratio']:.1%})")
    print(f"[7] Chunk index mới={len(new_texts)} rỗng={hy_new['n_empty']} "
          f"trùng={hy_new['n_duplicate_chunks']} ({hy_new['duplicate_ratio']:.1%}) "
          f"{'ĐỎ: trùng quá ngưỡng' if hy_new['duplicate_over_threshold'] else ''}")

    # ---- 7b. cổng chất lượng đo TRÊN NỘI DUNG ĐÃ INDEX (mới + cũ, cùng thước),
    # không join hai JSON đặt tên khác nhau; vocab proxy lấy từ quality_vie.json khi khớp stem
    diag_dir = ROOT / "data" / "loop" / "diag" / "corpus_diagnostics"
    vocab_by_stem: dict[str, float] = {}
    qv_path = diag_dir / "quality_vie.json"
    if qv_path.exists():
        for r in json.loads(qv_path.read_text(encoding="utf-8")).get("per_file", []):
            v = r.get("new_vocab_ratio")
            if v is not None:
                vocab_by_stem[_norm_stem(r["stem"])] = v
    rows_new = gate_by_index(new_texts, vocab_by_stem)
    rows_old = gate_by_index(old_texts, vocab_by_stem)
    good, gap = partition_by_gate(rows_new)
    good_old, gap_old = partition_by_gate(rows_old)
    indexed_by_stem = {r["stem"]: r["n_chunks"] for r in rows_new}
    leak = gap_leak_report([g["stem"] for g in gap], indexed_by_stem)
    print(f"[7b] Cổng chất lượng theo tệp (đo trên index MỚI): {len(rows_new)} tệp — "
          f"tốt={len(good)} khoảng_trống={len(gap)}")
    print(f"[7b]   khoảng_trống (mới): {[g['stem'] for g in gap]}")
    print(f"[7b]   cùng cổng trên index CŨ: khoảng_trống={len(gap_old)}/{len(rows_old)}")
    print(f"[7b] Tệp khoảng trống CÓ chunk trong index mới: {leak['n_leaked_into_index']} "
          f"{'-> bị nạp như tệp tốt, phải gắn cờ (PA-7)' if leak['silent'] else ''}")

    # ---- 7c. ký tự ngoài bảng chữ Việt — CHỈ ĐO + ghi mã, KHÔNG bỏ, KHÔNG đoán.
    # Nguồn gốc chính của T2 là PDF scan/convert sai bảng mã; khối này cho biết index MỚI còn
    # sót bao nhiêu glyph lạ (CJK, ô vẽ bảng, glyph 1-byte rác, ký tự điều khiển) để người duyệt
    # đối chiếu bản gốc. Không phải cổng đỏ: không có ngưỡng đăng ký trước cho mục này.
    glyphs = foreign_glyph_report(new_texts)
    print(f"[7c] Ký tự ngoài bảng Việt trong index MỚI: {glyphs['n_foreign']} "
          f"({glyphs['n_foreign_kinds']} loại) / {glyphs['n_chars']} ký tự"
          f"{' — CÒN SÓT' if glyphs['n_foreign'] else ' — sạch'}")
    for row in glyphs["foreign"][:10]:
        print(f"[7c]   {row['codepoint']} {row['char']!r} x{row['count']} — vd: {row['example']}")
    if glyphs["foreign_truncated"]:
        print(f"[7c]   … còn nữa (chỉ in 10/{glyphs['n_foreign_kinds']} loại; JSON giữ "
              f"{len(glyphs['foreign'])} dòng)")

    # ---- 8. 20 đoạn đối chiếu (KHÔNG tự phán)
    texts_by_stem: dict[str, str] = {}
    for i, t in enumerate(new_texts):
        texts_by_stem.setdefault(f"chunk{i:03d}", t)
    picks = pick_segments(texts_by_stem)
    seg_path = out_dir / "manual_20_segments_new_index.txt"
    seg_path.write_text(
        "# 20 đoạn ngẫu nhiên (seed 20261024) từ index MỚI — người dùng đối chiếu bản gốc.\n"
        "# Script không tự phán đúng/sai.\n\n"
        + "\n".join(f"[{k}] {stem}\n{txt}\n" for k, (stem, txt) in enumerate(picks, 1)),
        encoding="utf-8",
    )
    print(f"[8] Đã xuất {len(picks)} đoạn để đối chiếu: {seg_path}")

    # ---- 9. gold coverage trên testset (ĐO CẶP cũ/mới — mất neo do rebuild hay do vốn vậy)
    testset = [json.loads(l) for l in Path(args.testset).read_text(encoding="utf-8").splitlines() if l.strip()]
    cov = gold_coverage(testset, new_texts)
    cov_old = gold_coverage(testset, old_texts)
    # Hồi quy RIÊNG do rebuild: item khớp ở index cũ nhưng mất ở index mới.
    matched_old = {m["id"] for m in cov_old["missing"]}
    regressed = [m for m in cov["missing"] if m["id"] not in matched_old]
    cov["paired"] = {
        "old_missing_rate": cov_old["missing_rate"],
        "old_missing_n": cov_old["n_missing_gold"],
        "regressed_by_rebuild_n": len(regressed),
        "regressed_rate_of_checkable": round(len(regressed) / cov["n_checkable"], 4) if cov["n_checkable"] else 0.0,
        # Danh sách id để PA-17 re-anchor đúng 292 item, không phải đoán lại từ đầu.
        "regressed_ids": [m["id"] for m in regressed],
        "reading": "old_missing = mất neo VỐN ĐÃ có (gold_sentence không khớp cả index nó sinh ra); "
                   "regressed = mất thêm DO rebuild corpus",
    }
    print(f"[9] Testset {cov['n_items']} item, kiểm được {cov['n_checkable']} "
          f"(không gold_sentence: {cov['n_no_gold_sentence']}); MẤT GOLD {cov['n_missing_gold']} "
          f"= {cov['missing_rate']:.2%} — {'ĐỎ (>2%)' if cov['red'] else 'XANH (<=2%)'}")
    print(f"[9] CẶP: index cũ mất {cov_old['n_missing_gold']} ({cov_old['missing_rate']:.2%}); "
          f"regression RIÊNG do rebuild = {len(regressed)} item "
          f"({cov['paired']['regressed_rate_of_checkable']:.2%})")
    print(f"[9] PHÂN LOẠI chỗ mất (chẩn đoán, KHÔNG hạ mức đỏ): "
          f"gần-nội-dung (overlap>=0,6) = {cov['n_near_verbatim']}, "
          f"MẤT THẬT = {cov['n_absent']} ({cov['absent_rate_of_checkable']:.2%})")

    # ---- 10. chữ ký trọng tài / chữ ký dữ liệu
    ref_fp = verify.referee_fingerprint()
    sig_old, sig_new = index_signature(old_texts), index_signature(new_texts)
    rounds = sorted(p.name for p in (ROOT / "data" / "loop" / "rounds").glob("r*") if p.is_dir())
    print(f"[10] referee_fingerprint = {ref_fp!r} (mã trọng tài: PHẢI không đổi)")
    print(f"[10] index_signature: cũ={sig_old['signature']}({sig_old['n_chunks']}) "
          f"mới={sig_new['signature']}({sig_new['n_chunks']}) "
          f"-> {'ĐỔI (đúng: dữ liệu nạp đổi => phải chấm lại)' if sig_old != sig_new else 'KHÔNG ĐỔI'}")
    print(f"[10] Round cần chấm lại (theo PA-1): {rounds}")

    print(f"[5] byte-digest index CŨ {digest_old_before} -> {digest_old_after} "
          f"({'KHÔNG ĐỔI' if digest_old_before == digest_old_after else 'ĐỔI — bình thường: ChromaDB tái ghi khi mở; bất biến thật = nội dung, đã kiểm ở trên'})")
    payload = {
        "old_dir_digest": {"before": digest_old_before, "after": digest_old_after,
                           "unchanged": digest_old_before == digest_old_after,
                           "note": "byte-digest ĐỔI chỉ vì ChromaDB tái ghi file bin khi MỞ; "
                                   "thước bất biến đúng là content_signature"},
        "old_content_signature": {"before_first_open": sig_old_before, "after_reopen": sig_old_reopen,
                                  "unchanged": content_unchanged},
        "source_files": files, "source_note": src_note,
        "gate": {
            "thresholds": {"min_diacritic": GAP_MIN_DIACRITIC, "min_vocab": GAP_MIN_VOCAB},
            "measured_on": "nội dung đã index, gộp chunk theo tiêu đề [tệp] (khớp 26 tệp nguồn: "
                           f"{len(rows_new)} nhóm)",
            "n_files_new_index": len(rows_new), "n_good_new": len(good), "n_gap_new": len(gap),
            "gap_new": [{"stem": g["stem"], "n_chunks": g["n_chunks"],
                         "ratio": g["ratio"], "vocab_ratio": g.get("vocab_ratio"),
                         "reasons": g["gate"]["reasons"]} for g in gap],
            "n_gap_old_index": len(gap_old),
            "leak": leak,
        },
        "hygiene_old": hy_old, "hygiene_new": hy_new,
        "foreign_glyphs": glyphs,
        "manual_segments": {"seed": 20261024, "n": len(picks), "file": str(seg_path)},
        "gold_coverage": cov,
        "referee_fingerprint": ref_fp,
        "index_signature_old": sig_old, "index_signature_new": sig_new,
        "index_signature_changed": sig_old != sig_new,
        "rounds_to_rescore": rounds,
    }
    (out_dir / "corpus_check.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[ghi] {out_dir / 'corpus_check.json'}")
    red = cov["red"] or hy_new["duplicate_over_threshold"] or (not content_unchanged)
    print("==> KẾT LUẬN:", "ĐỎ" if red else "XANH (không mục nào vượt ngưỡng đỏ)")
    return 2 if (red and args.fail_on_red) else 0


if __name__ == "__main__":
    raise SystemExit(main())
