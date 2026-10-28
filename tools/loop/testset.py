"""Sinh bộ test chống bịa đặt có gold MÁY KIỂM CHỨNG ĐƯỢC cho vòng lặp tự huấn luyện.

Nguyên tắc cứng (không có ngoại lệ):
1._gold không do AI viết. Mọi gold là chuỗi trích NGUYÊN VĂN từ chunk trong
   ChromaDB (kèm offset) hoặc là giá trị số/mã rút từ chunk đó. Không có câu nào
   "tôi nghĩ đáp án là vậy".
2. Item nào không kiểm chứng được bằng code thì KHÔNG vào bộ test (bỏ, không đoán).
3. Split theo VĂN BẢN (document-level), không theo câu: toàn bộ chunk của một file
   PDF chỉ thuộc MỘT phía. Nhờ vậy không đáp án của câu test nào từng xuất hiện
   trong dữ liệu train của bất kỳ mô hình nào.
4. Pool mẫu câu TEST và TRAIN DISJOINT nhau. Classifier v1 (20/10) từng đạt điểm
   ảo vì học thuộc mẫu câu; nếu để test và train dùng chung template thì vòng lặp
   sẽ tự lừa mình đúng cái bẫy đó.
5. Câu "không trả lời được" phải chứng minh KHÔNG CÓ BẰNG CHỨNG bằng cách quét
   toàn corpus (fold). Từ nào xuất hiện ở bất kỳ chunk nào thì bị loại khỏi họ này.

Ba họ item:
- EXACT    : chunk văn bản đủ dấu → gold là câu nguyên văn + thực thể bắt buộc.
- NUMERIC  : chunk OCR mất dấu nhưng SỐ còn đúng → gold là giá trị số/mã + nguồn.
- REFUSE   : out-of-domain / mã văn bản không tồn tại / bẫy phản đề (số bị sửa sai).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.answer_guard import extract_entities  # noqa: E402
from src.text_utils import fold  # noqa: E402

OUT_DIR = ROOT / "data" / "loop"
RANDOM_STATE = 20261023

# ---------------------------------------------------------------------------
# Nạp chunk bằng định nghĩa "clean" của chính repo (một nguồn sự thật duy nhất)
# ---------------------------------------------------------------------------


def load_builder_module():
    spec = importlib.util.spec_from_file_location(
        "btd", str(ROOT / "tools" / "train" / "build_training_data.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["btd"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Sample câu hỏi: hai pool RỜI NHAU
# ---------------------------------------------------------------------------

# Pool A — dành cho TRAINPOOL (mô hình được phép học thuộc cấu trúc này)
POOL_A = {
    "number": [
        "Mức {kw} là bao nhiêu?",
        "{kw} được quy định là bao nhiêu?",
        "Cho biết {kw} hiện hành.",
    ],
    "code": [
        "Mã {kw} là gì?",
        "{kw} có mã số là gì?",
    ],
    "legal": [
        "Nội dung này nằm ở Điều nào?",
        "Quy định này thuộc Điều bao nhiêu?",
    ],
    "date": [
        "{kw} áp dụng từ thời điểm nào?",
        "Thời điểm có hiệu lực của {kw} là khi nào?",
    ],
    "confirm_trap": [
        "{kw} là {wrong} phải không?",
        "Tôi nghe {kw} bằng {wrong}, đúng không?",
    ],
    "out_of_domain": [
        "{kw} của trường mình như thế nào?",
        "Trường có {kw} không?",
    ],
    "missing_doc": [
        "Theo {doc}, {kw} được quy định ra sao?",
    ],
}

# Pool B — dành cho TEST: diễn đạt khác, có thêm hư từ học vụ, KHÔNG dùng ở train
POOL_B = {
    "number": [
        "Em muốn biết {kw} hiện tại được tính là bao nhiêu ạ?",
        "Hiện tại thì {kw} là bao nhiêu vậy thầy/cô?",
        "Dạ cho em hỏi mức {kw} đang áp dụng là bao nhiêu ạ?",
        "{kw} năm học này em cần đóng/báo về là bao nhiêu ạ?",
    ],
    "code": [
        "Dạ mã {kw} mà hệ thống dùng là gì vậy thầy/cô?",
        "Em cần tra chính xác mã của {kw} thì nó là mã nào ạ?",
    ],
    "legal": [
        "Dạ cái này em muốn dẫn chứng thì nó nằm ở Điều nào của văn bản ạ?",
        "Em cần ghi căn cứ pháp lý, vậy nội dung này thuộc Điều bao nhiêu ạ?",
    ],
    "date": [
        "Dạ mốc thời gian bắt đầu áp dụng cho {kw} là khi nào ạ?",
        "Em cần biết {kw} có hiệu lực từ ngày nào để đối chiếu ạ?",
    ],
    "confirm_trap": [
        "Bạn em nói {kw} là {wrong}, vậy có đúng không ạ?",
        "Em đọc ở đâu đó thấy {kw} bằng {wrong}, đúng không thầy/cô?",
        "{kw} mà {wrong} thì có phải thông tin chính thức không ạ?",
    ],
    "out_of_domain": [
        "Dạ trường mình có chính sách về {kw} không ạ, em cần căn cứ cụ thể?",
        "Em hỏi về {kw} thì trong quy định của trường có nói tới không ạ?",
        "{kw} của Trường Đại học An Giang được quy định ở văn bản nào ạ?",
    ],
    "missing_doc": [
        "Dạ theo văn bản {doc} thì {kw} được quy định thế nào ạ?",
        "Em cần trích dẫn từ {doc} cho nội dung {kw}, giúp em với ạ?",
    ],
}

# Từ khóa ứng với đơn vị tiền/tỷ lệ để câu hỏi không tối nghĩa.
UNIT_KEYWORD = {
    "đ": "học phí",
    "dong": "học phí",
    "%": "tỷ lệ",
    "tín chỉ": "số tín chỉ",
    "tc": "số tín chỉ",
    "ngày": "số ngày",
    "tuần": "số tuần",
    "buổi": "số buổi",
    "năm": "số năm",
    "tháng": "số tháng",
    "giờ": "số giờ",
    "lượt": "số lượt",
    "người": "số người",
    "hồ sơ": "số hồ sơ",
    "SV": "số sinh viên",
}

# Chủ đề nghi ngờ là ngoài phạm vi corpus — chỉ được dùng nếu code chứng minh
# KHÔNG xuất hiện ở bất kỳ chunk nào (see `verify_absence`).
OUT_OF_DOMAIN_CANDIDATES = [
    "học bổng Eiffel",
    "điểm IELTS đầu ra",
    "phí giữ xe đạp điện",
    "chính sách nghỉ thai sản cho giảng viên",
    "quỹ đầu tư mạo hiểm sinh viên",
    "chương trình trao đổi học kỳ tại Nhật Bản",
    "dịch vụ nấu ăn ký túc xá",
    "bảo hiểm trách nhiệm dân sự ô tô",
    "xét học bổng tài trợ doanh nghiệp Hàn Quốc",
    "phí thi lại IELTS",
    "chế độ nghỉ hưu sớm",
    "thuế thu nhập cá nhân của sinh viên đi làm thêm",
    "visa du học Hàn Quốc",
    "chương trình cử nhân tuyển sinh khóa 2015",
    "giáo trình tiếng Nga",
    "phòng lab thực tế ảo",
    "chính sách cho vay mua nhà ở xã hội",
    "học phí đào tạo lái xe",
]

# Mã văn bản KHÔNG tồn tại trong corpus (được kiểm tra lại bằng code).
MISSING_DOC_CODES = [
    "1999-QĐ-ĐHAG-2019",
    "4567-QĐ-ĐHAG-2024",
    "QĐ-8888/2023",
    "00-TB-CTSV-VIETSA",
    "CVHS-9999-2020",
    "1357-QD-DHAG-2018",
]

NUMERIC_MUTATORS = [lambda n: str(int(float(n) * 2)), lambda n: str(int(float(n)) + 1)]

# ---------------------------------------------------------------------------


def stable_int(text: str, salt: int = 0) -> int:
    digest = hashlib.sha256(f"{salt}:{text}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def doc_split(source: str) -> str:
    """Chia VĂN BẢN: ~55% document sang TEST, phần còn lại sang TRAINPOOL."""
    return "test" if (stable_int(fold(source), 7) % 100) < 55 else "trainpool"


def sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.;:])\s+", text)
    return [p.strip() for p in parts if p and len(p.strip()) >= 25]


def keyword_from_span(sentence: str, start: int, max_words: int = 6) -> str:
    """Cụm danh từ đứng trước thực thể, cắt theo TỪ NGUYÊN VẸN.

    Bản cũ cắt theo 60 ký tự nên sinh 'ân công giảng dạy' (mất chữ 'ph'), tức là
    câu hỏi rác; đo trên câu hỏi rác thì mọi chỉ số của vòng lặp mất nghĩa.
    """
    head = sentence[:start]
    head = re.split(r"[,;:\(\)\n]", head)[-1].strip()
    head = re.sub(r"^(và|hoặc|là|bằng|tương ứng|cụ thể|theo đó|gồm)[\s:]+", "", head, flags=re.I)
    head = head.strip(" .-–")
    if len(head) < 3:
        head = re.split(r"[,;:]", sentence[:start])[0].strip()
    words = head.split(" ")
    return " ".join(words[-max_words:])


def pick(pool: dict, kind: str, rng: random.Random, item_id: str) -> str:
    options = pool.get(kind) or pool["number"]
    return options[rng.randrange(len(options))]


def extract_keyword_or_topic(sentence: str, start: int, unit: Optional[str], topic: Optional[str], title: str) -> str:
    kw = keyword_from_span(sentence, start)
    kw = re.sub(r"\s+", " ", kw).strip()
    if unit and any(u in (unit or "") for u in UNIT_KEYWORD):
        for key, label in UNIT_KEYWORD.items():
            if key in (unit or ""):
                kw = f"{kw} ({label})" if len(kw) > 6 else label
                break
    if len(kw) < 4:
        kw = topic or title or "quy định này"
    return kw


def build_items(chunks: list[dict], builder) -> tuple[list[dict], Counter]:
    items: list[dict] = []
    stats: Counter = Counter()
    rng = random.Random(RANDOM_STATE)
    all_text_folded = fold(" \n ".join(c["text"] for c in chunks))

    # ---------------- EXACT + trap từ chunk đủ dấu ----------------
    for c in chunks:
        if not c["clean"]:
            continue
        split = doc_split(c["source"])
        pool = POOL_A if split == "trainpool" else POOL_B
        for sentence in sentence_split(c["body"]):
            if len(sentence) > 320 or builder.is_boilerplate(sentence):
                continue
            ents = [e for e in extract_entities(sentence) if e.kind in ("number", "code", "legal", "date")]
            if not ents:
                continue
            primary = max(ents, key=lambda e: (len(e.text), e.start))
            kw = extract_keyword_or_span_safe(sentence, primary, c, builder)
            item_id = f"{split[0].upper()}{stable_int(c['source'] + sentence + primary.text):010d}"
            kind = "date" if primary.kind == "date" else ("legal" if primary.kind == "legal" else ("code" if primary.kind == "code" else "number"))
            question = pick(pool, kind, rng, item_id).format(
                kw=kw, wrong="", doc=c["title"]
            )
            items.append(
                {
                    "id": item_id,
                    "family": "EXACT",
                    "split": split,
                    "kind": kind,
                    "raw_query": question,
                    "source_document": c["source"],
                    "gold_chunk_id": c["chunk_id"],
                    "gold_sentence": sentence,
                    "gold_span_sha": hashlib.sha1(sentence.encode()).hexdigest()[:12],
                    "required_entities": sorted({e.text for e in ents}),
                    "primary_entity": primary.text,
                    "primary_kind": primary.kind,
                    "topic": c["topic"] or "khác",
                    "expected_answer_type": "value",
                    "pool": "A" if split == "trainpool" else "B",
                    "evidence_quality": "clean",
                }
            )
            stats[f"EXACT:{split}:{kind}"] += 1

            # ----- trap: sửa giá trị số rồi hỏi xác nhận (gold = phủ định) -----
            # Kèm hai điều kiện để bẫy ĐÁNG TIN CÂY:
            #  - không bắt năm (1980..2100): nhân đôi/nh cộng năm cho số vô nghĩa;
            #  - giá trị sai không được xuất hiện ở BẤT KỲ đâu trong corpus, nếu không
            #    trả lời theo số sai vẫn có thể đúng và item mất giá trị kiểm chứng.
            if primary.kind == "number" and not re.fullmatch(r"(19|20)\d{2}", primary.text):
                try:
                    digits = re.sub(r"[.,]", "", primary.text)
                    base = float(digits) if digits else None
                except ValueError:
                    base = None
                if base and base >= 2:
                    mutated = NUMERIC_MUTATORS[rng.randrange(len(NUMERIC_MUTATORS))](str(int(base)))
                    mutated_free = not re.search(
                        rf"(?<!\d){re.escape(mutated)}(?!\d)", all_text_folded
                    )
                    if mutated_free and not re.fullmatch(r"(19|20)\d{2}", mutated):
                        trap_id = f"T{stable_int(item_id + mutated):010d}"
                        trap_split = split
                        trap_pool = POOL_A if trap_split == "trainpool" else POOL_B
                        items.append(
                            {
                                "id": trap_id,
                                "family": "TRAP",
                                "split": trap_split,
                                "kind": "number",
                                "raw_query": pick(trap_pool, "confirm_trap", rng, trap_id).format(
                                    kw=kw, wrong=mutated, doc=c["title"]
                                ),
                                "source_document": c["source"],
                                "gold_chunk_id": c["chunk_id"],
                                "gold_sentence": sentence,
                                "wrong_value": mutated,
                                "correct_value": primary.text,
                                # primary_entity = giá trị ĐÚNG (bản trước lấy số sai
                                # nên cổng đối chiếu nguyên văn fail 76 item).
                                "required_entities": [primary.text],
                                "primary_entity": primary.text,
                                "primary_kind": "number",
                                "topic": c["topic"] or "khác",
                                "expected_answer_type": "refuse_or_correct",
                                "pool": "A" if trap_split == "trainpool" else "B",
                                "evidence_quality": "clean",
                            }
                        )
                        stats[f"TRAP:{trap_split}"] += 1

    # ---------------- NUMERIC từ chunk OCR (số còn đúng, chữ thì hỏng dấu) ----------------
    for c in chunks:
        if c["clean"]:
            continue
        split = doc_split(c["source"])
        pool = POOL_A if split == "trainpool" else POOL_B
        for sentence in sentence_split(c["body"]):
            if len(sentence) > 300:
                continue
            ents = [e for e in extract_entities(sentence) if e.kind in ("number", "legal", "date")]
            big = [e for e in ents if len(e.text) >= 3]  # số >=3 chữ số đặc hiệu hơn
            if not big:
                continue
            primary = max(big, key=lambda e: len(e.text))
            kw_folded = keyword_from_span(sentence, primary.start)
            kw_folded = sanitize_keyword(kw_folded, c["topic"], c["title"])
            if len(kw_folded) < 5:
                continue
            item_id = f"N{stable_int(c['source'] + sentence + primary.text):010d}"
            kind = "legal" if primary.kind == "legal" else ("date" if primary.kind == "date" else "number")
            items.append(
                {
                    "id": item_id,
                    "family": "NUMERIC",
                    "split": split,
                    "kind": kind,
                    "raw_query": pick(pool, kind, rng, item_id).format(kw=kw_folded, wrong="", doc=c["title"]),
                    "source_document": c["source"],
                    "gold_chunk_id": c["chunk_id"],
                    "gold_sentence": sentence,
                    "required_entities": [primary.text],
                    "primary_entity": primary.text,
                    "primary_kind": primary.kind,
                    "topic": c["topic"] or "khác",
                    "expected_answer_type": "value",
                    "pool": "A" if split == "trainpool" else "B",
                    "evidence_quality": "ocr_folded",
                }
            )
            stats[f"NUMERIC:{split}:{kind}"] += 1

    # ---------------- REFUSE: ngoài phạm vi, chứng minh absence bằng code ----------------
    refuse_split = "test"
    for kw in OUT_OF_DOMAIN_CANDIDATES:
        if fold(kw).split()[0] in all_text_folded and any(t in all_text_folded for t in fold(kw).split() if len(t) > 4):
            stats["REFUSE:rejected_present"] += 1
            continue
        item_id = f"R{stable_int('ood' + kw):010d}"
        items.append(
            {
                "id": item_id,
                "family": "REFUSE_OOD",
                "split": refuse_split,
                "kind": "out_of_domain",
                "raw_query": pick(POOL_B, "out_of_domain", rng, item_id).format(kw=kw, wrong="", doc=""),
                "source_document": None,
                "gold_chunk_id": None,
                "gold_sentence": None,
                "required_entities": [],
                "primary_entity": kw,
                "primary_kind": "keyword",
                "absence_proof": {"query_terms": fold(kw).split(), "corpus_hits": 0},
                "topic": "ngoai_pham_vi",
                "expected_answer_type": "refuse",
                "pool": "B",
                "evidence_quality": "verified_absent",
            }
        )
        stats["REFUSE_OOD:test"] += 1

    for code in MISSING_DOC_CODES:
        if fold(code) in all_text_folded:
            stats["REFUSE:rejected_doc_present"] += 1
            continue
        item_id = f"M{stable_int('doc' + code):010d}"
        items.append(
            {
                "id": item_id,
                "family": "REFUSE_MISSING_DOC",
                "split": "test",
                "kind": "missing_doc",
                "raw_query": pick(POOL_B, "missing_doc", rng, item_id).format(kw="quy định này", wrong="", doc=code),
                "source_document": None,
                "gold_chunk_id": None,
                "gold_sentence": None,
                "required_entities": [],
                "primary_entity": code,
                "primary_kind": "code",
                "absence_proof": {"needle": fold(code), "corpus_hits": 0},
                "topic": "ngoai_pham_vi",
                "expected_answer_type": "refuse",
                "pool": "B",
                "evidence_quality": "verified_absent",
            }
        )
        stats["REFUSE_MISSING_DOC:test"] += 1

    return items, stats


def sanitize_keyword(raw: str, topic: Optional[str], title: str) -> str:
    """Ép cụm từ khóa thành danh từ sạch, không cắt giữa từ, không chứa số/rác.

    Lý do: bản đầu lấy 60 ký tự cuối trước thực thể nên sinh câu hỏi kiểu
    'ân công giảng dạy là bao nhiêu?' (cắt mất chữ 'ph') — đo trên câu hỏi rác
    thì mọi chỉ số của vòng lặp mất nghĩa. Keyword không đạt thì lùi về topic
    hoặc tiêu đề văn bản, luôn là tiếng Việt gõ máy sạch.
    """
    kw = re.sub(r"\s+", " ", (raw or "")).strip(" .,;:-–()[]")
    # Cắt về biên giới từ nguyên vẹn (bỏ âm tiết đầu nếu bị cụt).
    parts = kw.split(" ")
    if parts and not re.match(r"^[A-ZÀ-ỹĐđ]", parts[0]) and len(parts) > 1:
        parts = parts[1:]
    kw = " ".join(parts)
    # Không chấp nhận: chứa số, chứa ký tự OCR lạ, quá ngắn, quá dài, hoặc là
    # từ chung chung không phân biệt được chủ đề.
    if (
        not kw
        or re.search(r"\d", kw)
        or re.search(r"[^\w\sÀ-ỹĐđ'’\-\.,/()]", kw)
        or len(kw) < 8
        or len(kw) > 48
        or fold(kw) in {"quy định này", "thời gian", "đơn vị", "cụ thể", "như sau", "sau đó"}
    ):
        kw = (topic or "").strip()
    if len(kw) < 4 or kw == "khác":
        kw = re.sub(r"\s*\.(pdf|docx?)$", "", (title or "")).strip()
    if len(kw) > 60:
        kw = kw[:60].rsplit(" ", 1)[0]
    return kw or "quy định này"


def extract_keyword_or_span_safe(sentence: str, entity, chunk, builder) -> str:
    kw = extract_keyword_or_topic(sentence, entity.start, None, chunk["topic"], chunk["title"])
    return sanitize_keyword(kw, chunk["topic"], chunk["title"])


def build_cloze_ocr(chunks: list[dict], all_text_folded: str, stats: Counter) -> list[dict]:
    """CLOZE trên chunk OCR mất dấu: SỐ vẫn còn đúng nên gold vẫn kiểm chứng được.

    Văn bản xung quanh không dấu nên câu hỏi xấu, nhưng phần được đo (điền đúng
    giá trị số từ ngữ cảnh, không bịa số khác) là phần cốt lõi của mục tiêu
    'không bịa đặt'. Vì corpus chỉ 62/361 chunk đủ dấu, đây là cách duy nhất để
    có bộ test lớn mà không bịa gold.
    """
    items: list[dict] = []
    rng = random.Random(RANDOM_STATE + 31)
    for c in chunks:
        if c["clean"]:
            continue
        split = doc_split(c["source"])
        for sentence in sentence_split(c["body"]):
            if len(sentence) < 60 or len(sentence) > 300:
                continue
            ents = [
                e
                for e in extract_entities(sentence)
                if e.kind in ("number", "legal", "date") and len(re.sub(r"\D", "", e.text) or e.text) >= 3
            ]
            if not ents:
                continue
            for target in ents[:2]:
                masked = (sentence[: target.start] + "____" + sentence[target.end:]).strip()
                masked = re.sub(r"\s+", " ", masked)
                cid = f"O{stable_int(c['source'] + masked + target.text):010d}"
                items.append(
                    {
                        "id": cid,
                        "family": "CLOZE_OCR",
                        "split": split,
                        "kind": "cloze",
                        "raw_query": f"Điền giá trị còn thiếu cho đoạn trích từ {c['title']}: \"{masked}\"",
                        "source_document": c["source"],
                        "gold_chunk_id": c["chunk_id"],
                        "gold_sentence": sentence,
                        "required_entities": [target.text],
                        "primary_entity": target.text,
                        "primary_kind": target.kind,
                        "topic": c["topic"] or "khác",
                        "expected_answer_type": "value",
                        "pool": "trainpool" if split == "trainpool" else "test",
                        "evidence_quality": "ocr_folded",
                    }
                )
                stats[f"CLOZE_OCR:{split}:{target.kind}"] += 1

            # Trap OCR: chỉ tạo khi số sai KHÔNG tồn tại ở bất kỳ đâu trong corpus.
            primary = max(ents, key=lambda e: len(e.text))
            if primary.kind == "number" and not re.fullmatch(r"(19|20)\d{2}", primary.text):
                digits = re.sub(r"[.,]", "", primary.text)
                if digits.isdigit() and int(digits) >= 20:
                    mutated = str(int(int(digits) * 2))
                    if (
                        not re.search(rf"(?<!\d){re.escape(mutated)}(?!\d)", all_text_folded)
                        and not re.fullmatch(r"(19|20)\d{2}", mutated)
                    ):
                        tid = f"P{stable_int(c['source'] + primary.text + mutated):010d}"
                        kw = sanitize_keyword(keyword_from_span(sentence, primary.start), c["topic"], c["title"])
                        pool = POOL_A if split == "trainpool" else POOL_B
                        items.append(
                            {
                                "id": tid,
                                "family": "TRAP_OCR",
                                "split": split,
                                "kind": "number",
                                "raw_query": pick(pool, "confirm_trap", rng, tid).format(
                                    kw=kw, wrong=mutated, doc=c["title"]
                                ),
                                "source_document": c["source"],
                                "gold_chunk_id": c["chunk_id"],
                                "gold_sentence": sentence,
                                "wrong_value": mutated,
                                "correct_value": primary.text,
                                "required_entities": [primary.text],
                                "primary_entity": primary.text,
                                "primary_kind": "number",
                                "topic": c["topic"] or "khác",
                                "expected_answer_type": "refuse_or_correct",
                                "pool": "trainpool" if split == "trainpool" else "test",
                                "evidence_quality": "ocr_folded",
                            }
                        )
                        stats[f"TRAP_OCR:{split}"] += 1
    return items


def load_human_anchor(chunks: list[dict]) -> list[dict]:
    """Benchmark 100 câu VIẾT TAY (v3) làm neo hồi quy, đánh dấu chống rò rỉ.

    Caveat trung thực: bộ seed phân loại v2 đã từng dùng các câu này khi chọn siêu
    tham số (memory P2.3), nên trên HUMAN ta không được gọi kết quả là "held-out
    tuyệt đối". Vì vậy item mang cờ `contaminated_by_v2_classifier` và vòng lặp
    cấm thêm HUMAN vào bất kỳ trainpool nào ở các round sau.
    """
    path = ROOT / "data" / "evaluation" / "benchmark_100_questions_v3.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = {c["source"] for c in chunks}
    items: list[dict] = []
    for q in data.get("questions", []):
        if not q.get("in_corpus") or not q.get("raw_query"):
            continue
        src = q.get("source_document") or ""
        items.append(
            {
                "id": f"H{q['id']}",
                "family": "HUMAN",
                # Không bao giờ vào trainpool, kể cả file nằm ở phía train.
                "split": "test",
                "kind": "human",
                "raw_query": q["raw_query"],
                "source_document": src if src in sources else None,
                "gold_chunk_id": None,
                "gold_sentence": q.get("ground_truth_answer") or q.get("expected_answer") or "",
                "required_entities": [e for e in (q.get("expected_citations") or []) if e],
                "primary_entity": (q.get("expected_citations") or [""])[0],
                "primary_kind": "human",
                "topic": q.get("category") or "khác",
                "expected_answer_type": "refuse" if q.get("question_type") == "NGOAI_PHAM_VI" else "value",
                "pool": "human",
                "evidence_quality": "human_written",
                "contaminated_by_v2_classifier": True,
            }
        )
    return items


def build_extra_families(chunks: list[dict], builder, stats: Counter) -> list[dict]:
    """Bốn họ câu hỏi mở rộng, mỗi họ đều có gold kiểm chứng bằng code.

    CLOZE là họ quan trọng nhất cho mục tiêu 'không bịa': model phải điền đúng
    GIÁ TRỊ từ ngữ cảnh; điền sai số = bịa kiểu thay thế, đúng loại lỗi mà
    token-overlap 0.3 không phát hiện nổi.
    """
    items: list[dict] = []
    rng = random.Random(RANDOM_STATE + 11)
    for c in chunks:
        if not c["clean"]:
            continue
        split = doc_split(c["source"])
        pool = POOL_A if split == "trainpool" else POOL_B
        pool_key = "trainpool" if split == "trainpool" else "test"
        for sentence in sentence_split(c["body"]):
            if len(sentence) > 300 or len(sentence) < 45 or builder.is_boilerplate(sentence):
                continue
            ents = [e for e in extract_entities(sentence) if e.kind in ("number", "code", "legal", "date")]
            if not ents:
                continue

            # --- CLOZE: che một thực thể, yêu cầu điền lại ---
            for target in ents[:2]:
                masked = sentence[: target.start] + "____" + sentence[target.end:]
                masked = re.sub(r"\s+", " ", masked).strip()
                if len(masked) < 40:
                    continue
                cid = f"C{stable_int(c['source'] + masked + target.text):010d}"
                items.append(
                    {
                        "id": cid,
                        "family": "CLOZE",
                        "split": split,
                        "kind": "cloze",
                        "raw_query": (
                            f"Điền giá trị còn thiếu cho đoạn trích từ {c['title']}: \"{masked}\""
                        ),
                        "source_document": c["source"],
                        "gold_chunk_id": c["chunk_id"],
                        "gold_sentence": sentence,
                        "required_entities": [target.text],
                        "primary_entity": target.text,
                        "primary_kind": target.kind,
                        "topic": c["topic"] or "khác",
                        "expected_answer_type": "value",
                        "pool": pool_key,
                        "evidence_quality": "clean",
                    }
                )
                stats[f"CLOZE:{split}:{target.kind}"] += 1

            primary = max(ents, key=lambda e: len(e.text))
            kw = sanitize_keyword(keyword_from_span(sentence, primary.start), c["topic"], c["title"])

            # --- REVERSE_LEGAL: cho số Điều, hỏi nội dung ---
            legal = next((e for e in ents if e.kind == "legal"), None)
            if legal and len(sentence) > 70:
                rid = f"V{stable_int(c['source'] + legal.text + sentence[:40]):010d}"
                items.append(
                    {
                        "id": rid,
                        "family": "REVERSE_LEGAL",
                        "split": split,
                        "kind": "legal",
                        "raw_query": f"{legal.text} trong {c['title']} quy định nội dung gì?",
                        "source_document": c["source"],
                        "gold_chunk_id": c["chunk_id"],
                        "gold_sentence": sentence,
                        "required_entities": [primary.text] if primary.text else [],
                        "primary_entity": legal.text,
                        "primary_kind": "legal",
                        "topic": c["topic"] or "khác",
                        "expected_answer_type": "value",
                        "pool": pool_key,
                        "evidence_quality": "clean",
                    }
                )
                stats[f"REVERSE_LEGAL:{split}"] += 1

            # --- SOURCE_LOOKUP: cho nội dung, hỏi văn bản nào (kiểm citation) ---
            sid = f"S{stable_int(c['source'] + sentence[:60]):010d}"
            snippet = re.sub(r"\s+", " ", sentence)[:90]
            items.append(
                {
                    "id": sid,
                    "family": "SOURCE_LOOKUP",
                    "split": split,
                    "kind": "source",
                    "raw_query": f"Quy định \"{snippet}\" nằm trong văn bản nào?",
                    "source_document": c["source"],
                    "gold_chunk_id": c["chunk_id"],
                    "gold_sentence": sentence,
                    "required_entities": [c["source"]],
                    "primary_entity": c["source"],
                    "primary_kind": "source",
                    "topic": c["topic"] or "khác",
                    "expected_answer_type": "value",
                    "pool": pool_key,
                    "evidence_quality": "clean",
                }
            )
            stats[f"SOURCE_LOOKUP:{split}"] += 1

            # --- YESNO_FACT: nêu ĐÚNG giá trị rồi hỏi xác nhận (gold = đồng tình) ---
            if primary.kind == "number" and len(primary.text) >= 3:
                yid = f"Y{stable_int(c['source'] + kw + primary.text):010d}"
                items.append(
                    {
                        "id": yid,
                        "family": "YESNO_FACT",
                        "split": split,
                        "kind": "number",
                        "raw_query": f"{kw} là {primary.text}, thông tin này có đúng theo quy định không?",
                        "source_document": c["source"],
                        "gold_chunk_id": c["chunk_id"],
                        "gold_sentence": sentence,
                        "required_entities": [primary.text],
                        "primary_entity": primary.text,
                        "primary_kind": "number",
                        "topic": c["topic"] or "khác",
                        "expected_answer_type": "confirm",
                        "pool": pool_key,
                        "evidence_quality": "clean",
                    }
                )
                stats[f"YESNO_FACT:{split}"] += 1
    return items


def dedupe(items: list[dict]) -> tuple[list[dict], int]:
    """Loại câu trùng, và quan trọng hơn: loại câu HAI GOLD khác nhau.

    Cùng một câu hỏi mà trỏ tới hai chunk vàng khác nhau nghĩa là câu hỏi mơ hồ;
    giữ lại thì chỉ số vòng lặp đo sự may rủi chứ không đo năng lực.
    """
    by_query: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_query[fold(item["raw_query"])].append(item)
    kept: list[dict] = []
    ambiguous = 0
    for _query, group in by_query.items():
        golds = {i.get("gold_chunk_id") for i in group}
        if len(golds) > 1:
            ambiguous += 1
            continue
        kept.append(group[0])
    return kept, ambiguous


def resolve_id_collisions(items: list[dict]) -> tuple[list[dict], int]:
    """Ép mọi item có id ĐỘC NHẤT, giữ nguyên thứ tự.

    id là hash của (nguồn + câu + thực thể chính), không chứa mẫu câu, nên hai câu
    hỏi khác nhau cùng sinh từ một mảnh vàng có thể va id. Vòng lặp chấm theo id:
    hai item trùng id nghĩa là `item_by_id` chỉ giữ một, mọi phép so khớp
    (gold_chunk_id, family, split) của item còn lại bị sai im lặng, và resume bỏ
    qua câu chưa chạy. Lỗi này từng làm 811 item thật chỉ còn 805 id.

    Luật tất định: lần xuất hiện đầu giữ id gốc, các lần sau thêm `#2`, `#3`…
    """
    seen: dict[str, int] = defaultdict(int)
    collisions = 0
    for item in items:
        base = item["id"]
        seen[base] += 1
        if seen[base] > 1:
            collisions += 1
            item["id"] = f"{base}#{seen[base]}"
    return items, collisions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT_DIR / "testset_v1.jsonl"))
    parser.add_argument("--max-per-family", type=int, default=0)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    builder = load_builder_module()
    chunks = builder.load_chunks()
    items, stats = build_items(chunks, builder)
    items += build_extra_families(chunks, builder, stats)
    all_text_folded = fold(" \n ".join(c["text"] for c in chunks))
    items += build_cloze_ocr(chunks, all_text_folded, stats)
    human = load_human_anchor(chunks)
    stats["HUMAN:test"] = len(human)
    items, ambiguous = dedupe(items + human)
    stats["dropped_ambiguous_query"] = ambiguous

    if args.max_per_family:
        counts: Counter = Counter()
        trimmed = []
        for item in items:
            if item["family"] == "HUMAN":
                trimmed.append(item)
                continue
            if counts[item["family"]] >= args.max_per_family:
                continue
            counts[item["family"]] += 1
            trimmed.append(item)
        items = trimmed

    # self-check: không được để gold nào lệch khỏi chunk gốc một ký tự nào
    items, id_collisions = resolve_id_collisions(items)
    stats["id_collisions_resolved"] = id_collisions
    assert len({i["id"] for i in items}) == len(items), "id không độc nhất -> chấm điểm sai im lặng"
    by_id = {c["chunk_id"]: c for c in chunks}
    corpus_sources = {c["source"] for c in chunks}
    bad = 0
    for item in items:
        if item["family"] in ("REFUSE_OOD", "REFUSE_MISSING_DOC", "HUMAN"):
            continue
        if item["family"] == "SOURCE_LOOKUP":
            # Gold là TÊN VĂN BẢN, không nằm trong body sau khi bỏ header -> kiểm
            # trực tiếp rằng file đó có thật trong corpus.
            if item["source_document"] not in corpus_sources:
                bad += 1
            continue
        chunk = by_id.get(item["gold_chunk_id"])
        if not chunk or fold(item["gold_sentence"]) not in fold(chunk["body"]):
            bad += 1
        elif fold(item["primary_entity"]) not in fold(chunk["body"]):
            bad += 1
    assert bad == 0, f"{bad} item có gold không khớp nguyên văn với chunk -> sửa generator, không xuất testset"

    # leakage check: pool B (test) không được xuất hiện ở pool A (train)
    a_forms = {p for pool in POOL_A.values() for p in pool}
    b_forms = {p for pool in POOL_B.values() for p in pool}
    assert not (a_forms & b_forms), "Pool mẫu câu TEST và TRAIN phải rời nhau tuyệt đối"

    train_rows = [i for i in items if i["split"] == "trainpool"]
    test_rows = [i for i in items if i["split"] == "test"]

    with open(args.out, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    corpus_fingerprint = hashlib.sha256(
        "\n".join(f"{c['chunk_id']}:{len(c['text'])}" for c in sorted(chunks, key=lambda x: x["chunk_id"])).encode()
    ).hexdigest()[:16]

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "testset_version": "v1",
        "n_items": len(items),
        "n_unique_ids": len({i["id"] for i in items}),
        "n_id_collisions_resolved": id_collisions,
        "n_trainpool": len(train_rows),
        "n_test": len(test_rows),
        "family_counts": dict(Counter(i["family"] for i in items)),
        "split_family_counts": {f"{i['family']}:{i['split']}": 0 for i in items},
        "stats": dict(stats),
        "n_chunks": len(chunks),
        "n_clean_chunks": sum(1 for c in chunks if c["clean"]),
        "n_documents": len({c["source"] for c in chunks}),
        "corpus_fingerprint": corpus_fingerprint,
        "split_rule": "document-level (hash fold(source)%100 < 55 => test)",
        "template_pools_are_disjoint": True,
        "gold_construction": "verbatim span từ chroma:document; không câu nào có gold do AI viết",
    }
    manifest["split_family_counts"] = dict(Counter(f"{i['family']}:{i['split']}" for i in items))
    (OUT_DIR / "testset_v1_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
