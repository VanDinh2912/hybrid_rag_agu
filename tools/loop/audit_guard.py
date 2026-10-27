"""Audit trọng tài trên dữ liệu A/B cũ: phân loại từng khẳng định bị đánh dấu.

`calibrate_guard.py` cho BIẾT tỉ lệ; script này trả lời câu hỏi khó hơn —
"16 câu bị gọi là không căn cứ đó, bao nhiêu là AI bịa thật, bao nhiêu là do
truy xuất không kéo đúng chunk, và bao nhiêu là báo động giả của chính trọng
tài?" Không có bước này thì vòng lặp sẽ đổ lỗi sai tầng và retrain nhầm.

Ba nhãn cho mỗi thực thể bị flag:
- FABRICATED  : không tồn tại ở BẤT KỲ đâu trong corpus (361 chunk) -> AI bịa.
- UNSOURCED   : có trong corpus nhưng không nằm trong contexts đã truy xuất ->
                lỗi truy xuất/chọn ngữ cảnh, câu trả lời không sai sự thật.
- LOOKS_LIKE_FORMATTING : xuất hiện trong corpus với tư cách một phần của cụm dài
                hơn ("Ban Giám" <- "Ban Giám hiệu") hoặc toàn bộ là chữ in hoa
                vang lại nhãn prompt ("NGỮ CẢNH") -> báo động giả của trọng tài,
                phải sửa ở `src/answer_guard.py`, không phải ở model.

Chạy: python tools/loop/audit_guard.py [outputs/ab_results_with_classifier.json]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.answer_guard import check_grounding, fold  # noqa: E402


def corpus_text() -> str:
    """Toàn bộ văn bản corpus (đã fold) lấy từ ChromaDB sqlite — không nạp embedding."""
    import sqlite3

    sqlite_path = ROOT / "chroma_db" / "chroma.sqlite3"
    if not sqlite_path.exists():
        raise SystemExit(f"Không thấy {sqlite_path}. Hãy chạy ingest.py trước.")
    con = sqlite3.connect(str(sqlite_path))
    cur = con.cursor()
    rows = cur.execute(
        "SELECT string_value FROM embedding_metadata WHERE key = 'chroma:document'"
    ).fetchall()
    con.close()
    return fold(" \n ".join((r[0] or "") for r in rows))


def classify(entity_text: str, kind: str, hay: str) -> tuple[str, str]:
    """Một thực thể bị flag -> FABRICATED / UNSOURCED / LOOKS_LIKE_FORMATTING."""
    needle = fold(entity_text)
    if re.fullmatch(r"[\d.,\s]+", entity_text):
        variants = {needle, needle.replace(".", "").replace(",", "").replace(" ", "")}
        hit = any(re.search(rf"(?<!\d){re.escape(v)}(?!\d)", hay) for v in variants if v)
    else:
        hit = needle in hay
    if not hit:
        return "FABRICATED", "không xuất hiện ở bất kỳ chunk nào"
    if kind == "proper":
        # Cụm trong câu trả lời là MỘT PHẦN của cụm dài hơn trong tài liệu
        # ("Ban Giám" <- "Ban Giám hiệu") -> trọng tài cắt nhầm ranh giới.
        longer = re.search(rf"{re.escape(needle)}[ ]?\w+", hay)
        if longer and longer.group(0).strip() != needle:
            return "LOOKS_LIKE_FORMATTING", f"một phần của '{longer.group(0).strip()}' trong tài liệu"
        if entity_text.upper() == entity_text:
            return "LOOKS_LIKE_FORMATTING", "toàn bộ viết hoa — vang lại nhãn prompt"
    return "UNSOURCED", "có trong corpus nhưng không nằm trong contexts đã truy xuất"


def audit(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("per_question", [])
    hay = corpus_text()
    counter: Counter = Counter()
    detail: list[dict] = []
    for e in entries:
        answer = e.get("answer") or ""
        contexts = e.get("contexts") or []
        question = e.get("raw_query") or ""
        if not answer or not contexts or e.get("error") or e.get("is_refusal_answer"):
            continue
        rep = check_grounding(
            answer, contexts, question,
            extra_haystack=[str(s.get("source") or "") for s in (e.get("sources") or [])],
        )
        counter["scored"] += 1
        if not rep.unsupported:
            counter["clean"] += 1
            continue
        counter["flagged_answers"] += 1
        labels = {}
        for ent in rep.unsupported:
            label, why = classify(ent.text, ent.kind, hay)
            counter[f"{label}:{ent.kind}"] += 1
            labels[ent.text] = (label, why)
            detail.append(
                {
                    "id": e.get("id"),
                    "entity": ent.text,
                    "kind": ent.kind,
                    "label": label,
                    "why": why,
                    "answer_preview": re.sub(r"\s+", " ", answer)[:140],
                }
            )
        # Một câu bị gọi là bịa đặt CHỈ vì formatting -> trọng tài sai, không phải model.
        kinds = {lab for lab, _ in labels.values()}
        if kinds == {"LOOKS_LIKE_FORMATTING"}:
            counter["answer_wrongly_flagged"] += 1
        elif "FABRICATED" in kinds:
            counter["answer_really_fabricated"] += 1
        elif "UNSOURCED" in kinds:
            counter["answer_is_retrieval_problem"] += 1
    return {"file": str(path), "counter": dict(counter), "detail": detail}


def main() -> None:
    paths = sys.argv[1:] or ["outputs/ab_results_with_classifier.json"]
    all_detail = []
    for rel in paths:
        result = audit(ROOT / rel)
        print(f"\n=== {rel} ===")
        for key in sorted(result["counter"]):
            print(f"  {key}: {result['counter'][key]}")
        print("\n  Phân bố theo nhãn (mỗi thực thể):")
        for label in ("FABRICATED", "UNSOURCED", "LOOKS_LIKE_FORMATTING"):
            n = sum(1 for d in result["detail"] if d["label"] == label)
            print(f"    - {label}: {n}")
        print("\n  Mẫu FABRICATED (bịa thật):")
        for d in [d for d in result["detail"] if d["label"] == "FABRICATED"][:12]:
            print(f"    [{d['id']}] {d['kind']} '{d['entity']}' — {d['answer_preview'][:90]}")
        print("\n  Mẫu LOOKS_LIKE_FORMATTING (trọng tài phải sửa):")
        for d in [d for d in result["detail"] if d["label"] == "LOOKS_LIKE_FORMATTING"][:12]:
            print(f"    [{d['id']}] {d['kind']} '{d['entity']}' — {d['why']}")
        all_detail.extend(result["detail"])

    out = ROOT / "tmp" / "guard_audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(all_detail, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> chi tiết từng thực thể: {out}")


if __name__ == "__main__":
    main()
