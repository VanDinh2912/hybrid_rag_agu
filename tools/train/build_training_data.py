#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sinh bộ dữ liệu huấn luyện (SFT / classifier / retrieval) từ đồ án Hybrid RAG AGU.

Triết lý: mọi mẫu đều TRÍCH XUẤT hoặc SUY RA TỪ NGUỒN CÓ THẬT trong repo —
không gọi model để bịa dữ liệu. Mỗi mẫu mang nhãn chất lượng:

  gold   — 100 câu benchmark v3 (câu hỏi + đáp án + trích dẫn do người soạn)
  silver — chunk còn dấu tiếng Việt, docstring mã nguồn, tài liệu markdown
  bronze — chunk OCR mất dấu (chỉ dùng cho tác vụ nhận diện nguồn/tầng/chủ đề
           hoặc truy xuất, KHÔNG dùng để dạy sinh câu trả lời pháp lý)

Nguyên tắc chống rò rỉ: mẫu sinh từ benchmark v3 KHÔNG nằm trong train/val —
chúng được ghi riêng vào *_benchmark_seed.* để người dùng chủ động chọn dùng.
Nếu huấn luyện trên seed rồi đánh giá bằng benchmark v3, kết quả sẽ bị nhiễm.

Cách chạy:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/train/build_training_data.py
    ... --out data/training --seed 42
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.text_utils import fold  # noqa: E402  (chỉ import hàm thuần, không nạp model)

REFUSAL_TEXT = "Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."

# ---------------------------------------------------------------------------
# Cấu hình nguồn
# ---------------------------------------------------------------------------
BENCHMARK_PATH = ROOT / "data/evaluation/benchmark_100_questions_v3.json"
CHROMA_SQLITE = ROOT / "chroma_db/chroma.sqlite3"
ENV_EXAMPLE = ROOT / ".env.example"

DOC_TITLES = {
    "1054-qd-dhag-2020-09-28.pdf": "Quy chế công tác sinh viên (QĐ 1054/QĐ-ĐHAG 2020)",
    "1059-qd-dhag-2020-09-29.pdf": "Quy định đánh giá kết quả rèn luyện (QĐ 1059/QĐ-ĐHAG 2020)",
    "118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf": "Quy chế xét danh hiệu Sinh viên 5 tốt và Sao Tháng Giêng 2026-2028",
    "367-QĐ-ĐU ngay 08-4-2026.pdf": "Kế hoạch Cuộc thi Chính luận năm 2026",
    "888-qd-dhag-2022-08-08.pdf": "Quy định khen thưởng sinh viên (QĐ 888/QĐ-ĐHAG 2022)",
    "QD1133_22815_VNU_ban hanh Quy dinh khen thuong HSSV -1.pdf": "Quy định khen thưởng HSSV cấp ĐHQG-HCM (QĐ 1133)",
    "163-tb-ctsv-thong-bao-ve-viec-bay-von-tin-chap-tai-ngan-hang-acb-theo-ct-acb-dong-hanh-cung-sinh-vien-dhqg-hcm.pdf": "Thông báo vay vốn tín dụng tại ngân hàng ACB",
    "ke-hoach-ttck-kltn-dh24th-2026.pdf": "Kế hoạch thực tập chuyên đề và khóa luận tốt nghiệp DH24TH 2026",
    "KH To chuc HK 261 - 20260612.pdf": "Kế hoạch tổ chức học kỳ 261 năm 2026",
    "TB tham gia BHYT SV NH 2026 - 2027.pdf": "Thông báo tham gia BHYT sinh viên năm học 2026-2027",
    "TB16 THAY DOI CONG RA VAO KTX.pdf": "Thông báo thay đổi giờ ra vào ký túc xá",
    "Thong bao dang ky hoc chuong trinh 2 nam hoc 2026-2027.pdf": "Thông báo đăng ký học chương trình 2 năm 2026-2027",
    "03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf": "Thông báo nộp hồ sơ miễn giảm học phí HKI 2025-2026",
    "05-tb-ctsv-thong-bao-ve-viec-nop-ho-so-huong-che-do-ho-tro-chi-phi-hoc-tap-hki-nam-hoc-2025-2026.pdf": "Thông báo hưởng chế độ hỗ trợ chi phí học tập HKI 2025-2026",
    "1413-HPCQ_Thong bao thu HP HKI NH(2026-2027).pdf": "Thông báo thu học phí HKI năm học 2026-2027",
    "17-tb-ctsv-thong-bao-ve-viec-trien-khai-tin-dung-doi-voi-sinh-vien-cac-nganh-stem.pdf": "Thông báo tín dụng ưu đãi cho sinh viên các ngành STEM",
    "ban-mo-ta-ctdt-nganh-cntt-2021.pdf": "Bản mô tả chương trình đào tạo ngành CNTT 2021",
    "don-dang-ky-hoc-thi-cai-thien.docx": "Mẫu đơn đăng ký học thi cải thiện",
    "don-gia-han-hoc-phi-3.docx": "Mẫu đơn gia hạn học phí",
    "don-xac-nhan-hoan-canh-kho-khan.docx": "Mẫu đơn xác nhận hoàn cảnh khó khăn",
    "don-xin-chuyen-nhom-hoc-phan.docx": "Mẫu đơn xin chuyển nhóm học phần",
    "don-xin-mien-hoc-phan-tieng-anh.docx": "Mẫu đơn xin miễn học phần tiếng Anh",
    "ke-hoach-ttck-kltn-dh24pm-2026.pdf": "Kế hoạch thực tập chuyên đề và KLTN DH24PM 2026",
    "lich-hoc-tap-tuan-shcd-sv-2026-2027-dh24-dh25-dh26.pdf": "Lịch học tập tuần sinh hoạt công dân 2026-2027",
    "Qui dinh muc hoc phi nam hoc 2026-2027.pdf": "Quy định mức học phí năm học 2026-2027",
    "TB_KhaoSatSinhVien_HoTroHocPhi (1).pdf": "Thông báo khảo sát sinh viên hỗ trợ học phí",
}

SOURCE_TOPIC = {
    "1054-qd-dhag-2020-09-28.pdf": "quy chế công tác sinh viên",
    "1059-qd-dhag-2020-09-29.pdf": "đánh giá rèn luyện",
    "118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf": "sinh viên 5 tốt",
    "367-QĐ-ĐU ngay 08-4-2026.pdf": "cuộc thi chính luận",
    "888-qd-dhag-2022-08-08.pdf": "khen thưởng sinh viên",
    "QD1133_22815_VNU_ban hanh Quy dinh khen thuong HSSV -1.pdf": "khen thưởng cấp ĐHQG",
    "163-tb-ctsv-thong-bao-ve-viec-bay-von-tin-chap-tai-ngan-hang-acb-theo-ct-acb-dong-hanh-cung-sinh-vien-dhqg-hcm.pdf": "tài chính sinh viên",
    "ke-hoach-ttck-kltn-dh24th-2026.pdf": "thực tập tốt nghiệp",
    "ke-hoach-ttck-kltn-dh24pm-2026.pdf": "thực tập tốt nghiệp",
    "KH To chuc HK 261 - 20260612.pdf": "hành chính sinh viên",
    "TB tham gia BHYT SV NH 2026 - 2027.pdf": "bảo hiểm y tế",
    "TB16 THAY DOI CONG RA VAO KTX.pdf": "ký túc xá",
    "Thong bao dang ky hoc chuong trinh 2 nam hoc 2026-2027.pdf": "chương trình đào tạo",
    "03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf": "học phí",
    "05-tb-ctsv-thong-bao-ve-viec-nop-ho-so-huong-che-do-ho-tro-chi-phi-hoc-tap-hki-nam-hoc-2025-2026.pdf": "học phí",
    "1413-HPCQ_Thong bao thu HP HKI NH(2026-2027).pdf": "học phí",
    "17-tb-ctsv-thong-bao-ve-viec-trien-khai-tin-dung-doi-voi-sinh-vien-cac-nganh-stem.pdf": "tài chính sinh viên",
    "ban-mo-ta-ctdt-nganh-cntt-2021.pdf": "chương trình đào tạo",
    "don-dang-ky-hoc-thi-cai-thien.docx": "hành chính sinh viên",
    "don-gia-han-hoc-phi-3.docx": "học phí",
    "don-xac-nhan-hoan-canh-kho-khan.docx": "hành chính sinh viên",
    "don-xin-chuyen-nhom-hoc-phan.docx": "chương trình đào tạo",
    "don-xin-mien-hoc-phan-tieng-anh.docx": "chương trình đào tạo",
    "lich-hoc-tap-tuan-shcd-sv-2026-2027-dh24-dh25-dh26.pdf": "hành chính sinh viên",
    "Qui dinh muc hoc phi nam hoc 2026-2027.pdf": "học phí",
    "TB_KhaoSatSinhVien_HoTroHocPhi (1).pdf": "học phí",
}

SYS_AGU = (
    "Bạn là trợ lý học vụ của Trường Đại học An Giang (AGU). Bạn trả lời câu hỏi về "
    "quy chế, quy định đào tạo dựa trên văn bản của Trường. Mỗi câu trả lời phải nêu "
    "căn cứ (Điều/Khoản hoặc tên văn bản nguồn); nếu không đủ thông tin, trả lời đúng "
    f'câu: "{REFUSAL_TEXT}"'
)
SYS_PROJECT = (
    "Bạn là chuyên gia kỹ thuật của đồ án Hybrid RAG tra cứu quy chế AGU. Bạn giải thích "
    "chính xác kiến trúc, từng module, từng hàm, tham số, luồng dữ liệu và quyết định "
    "thiết kế dựa trên mã nguồn thật của repo. Không bịa tên hàm hay số liệu."
)
SYS_TEACHER = (
    "Bạn là giảng viên hướng dẫn đồ án, giải thích từng bước cho sinh viên hiểu bản chất "
    "kỹ thuật, chỉ rõ file/hàm liên quan và lý do thiết kế. Trả lời tiếng Việt, có ví dụ "
    "khi hữu ích."
)

TASK_SYSTEM = {
    "benchmark_qa": SYS_AGU,
    "benchmark_mcq": SYS_AGU,
    "benchmark_faithfulness_check": SYS_AGU,
    "benchmark_question_gen": SYS_AGU,
    "benchmark_citation": SYS_AGU,
    "refusal": SYS_AGU,
    "grounded_refusal": SYS_AGU,
    "corpus_qa": SYS_AGU,
    "corpus_summary": SYS_AGU,
    "corpus_list": SYS_AGU,
    "corpus_cloze": SYS_AGU,
    "corpus_identification": SYS_AGU,
    "corpus_comparison": SYS_AGU,
    "corpus_article_index": SYS_AGU,
    "corpus_topic_index": SYS_AGU,
    "code_qa": SYS_PROJECT,
    "code_signature": SYS_PROJECT,
    "code_params": SYS_PROJECT,
    "code_callsite": SYS_PROJECT,
    "code_file_index": SYS_PROJECT,
    "code_module": SYS_PROJECT,
    "code_tests": SYS_PROJECT,
    "code_env": SYS_PROJECT,
    "code_commands": SYS_PROJECT,
    "code_lesson": SYS_PROJECT,
    "docs_qa": SYS_TEACHER,
    "docs_heading": SYS_TEACHER,
    "normalization": SYS_TEACHER,
    "router_config": SYS_PROJECT,
    "prompt_rules": SYS_PROJECT,
    "metrics": SYS_PROJECT,
    "defense": SYS_TEACHER,
    "grounded_qa": SYS_AGU,
}

STOPWORDS = {
    "la", "cua", "va", "co", "duoc", "trong", "cho", "voi", "de", "nay", "do",
    "nhung", "thi", "ma", "tu", "day", "nen", "can", "phai", "se", "da", "dang",
    "thuc", "hien", "tai", "tren", "thong", "qua", "theo", "xuyen", "tat", "ca",
    "mot", "hai", "ba", "bon", "nam", "sau", "bay", "tam", "chin", "muoi",
    "nhieu", "it", "rat", "hoi", "hoac", "ve", "gom", "chua", "nam", "o",
    "cac", "nhung", "khi", "neu", "boi", "vi", "nen", "vao", "ra", "len",
}

WORD_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------
def fold_tokens(text: str) -> set[str]:
    return {
        tok
        for tok in (fold(w) for w in WORD_RE.findall(text or ""))
        if len(tok) > 1 and tok not in STOPWORDS and not tok.isdigit()
    }


def token_overlap(a: str, b: str) -> float:
    ta, tb = fold_tokens(a), fold_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta)


def diacritic_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    marked = 0
    for c in letters:
        name = unicodedata.name(c, "")
        if c in "đĐ" or (name.startswith("LATIN") and len(unicodedata.normalize("NFD", c)) > 1):
            marked += 1
    return marked / len(letters)


def garbage_ratio(text: str) -> float:
    if not text:
        return 1.0
    bad = sum(1 for c in text if not (c.isalnum() or c.isspace() or c in ".,;:()[]{}%-/–—'\"“”…"))
    return bad / len(text)


def clean_space(text: str) -> str:
    text = text.replace("\r", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [clean_space(p) for p in parts if clean_space(p)]


def trim_at_sentence(text: str, limit: int) -> str:
    text = clean_space(text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    pos = max(cut.rfind(". "), cut.rfind("; "), cut.rfind("\n"))
    if pos > limit * 0.55:
        return cut[: pos + 1].strip()
    return cut.rsplit(" ", 1)[0].strip() + "…"


def is_form_like(title: str, body: str) -> bool:
    """Nhận diện biểu mẫu/đơn từ: dòng chấm điền, lặp nhãn — không hợp để hỏi nội dung.

    Biểu mẫu vẫn hữu ích cho tác vụ nhận diện nguồn và truy xuất, nhưng dùng làm
    câu hỏi "nội dung chính là gì" sẽ dạy model trả lời bằng dòng chấm vô nghĩa.
    """
    if "mau don" in fold(title):
        return True
    if len(re.findall(r"\.{4,}|…{3,}", body)) >= 3:
        return True
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if lines and len(set(lines)) / len(lines) < 0.55:
        return True
    return False


def is_boilerplate(body: str) -> bool:
    """Phần đầu/cuối công văn (Nơi nhận, chữ ký, tiêu đề in hoa) — không có nội dung quy định."""
    folded = fold(body)
    if any(marker in folded for marker in (
            "noi nhan:", "luu: vt", "kt. hieu truong", "pho hieu truong", "phuong thao")):
        return True
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if lines and re.fullmatch(r"\d{1,3}", lines[0]):
        return True
    letters = [c for c in body if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.65:
        return True
    return False


def is_table_like(body: str) -> bool:
    """Bảng số liệu/biểu phí: nhiều dòng ngắn chứa số, mật độ chữ số cao."""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return False
    numeric_lines = sum(1 for line in lines if len(re.findall(r"\d", line)) >= 3)
    short_lines = sum(1 for line in lines if len(line) < 90)
    numeric_tokens = len(re.findall(r"\d[\d.,]*", body))
    words = max(len(body.split()), 1)
    by_lines = numeric_lines / len(lines) > 0.45 and short_lines / len(lines) > 0.5
    by_density = numeric_tokens / words > 0.12 or numeric_tokens / max(len(body), 1) > 0.06
    return by_lines or by_density


def qa_unfriendly(title: str, body: str) -> bool:
    """True nếu chunk không nên dùng để dạy sinh câu trả lời (vẫn dùng được cho định danh/truy xuất)."""
    return is_form_like(title, body) or is_boilerplate(body) or is_table_like(body)


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def doc_title(source: str) -> str:
    return DOC_TITLES.get(source, Path(source).stem)


def tier_label(tier: str) -> str:
    """Tên tầng hiển thị: giữ 'Tầng 1/2', gom nhóm file bổ sung thành 'Bổ sung'."""
    if tier.startswith("Tầng"):
        return tier
    return "Bổ sung"


def citation_of(source: str, article: Optional[str] = None) -> str:
    if article:
        return f"(Điều {article} — {source})"
    return f"({source})"


# ---------------------------------------------------------------------------
# Bộ thu mẫu
# ---------------------------------------------------------------------------
@dataclass
class Item:
    task: str
    quality: str
    user: str
    assistant: str
    meta: dict = field(default_factory=dict)
    system: str = ""
    seed: bool = False  # True = sinh từ benchmark v3, cấm đưa vào train/val

    def __post_init__(self):
        if not self.system:
            self.system = TASK_SYSTEM.get(self.task, SYS_TEACHER)


class DatasetBuilder:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.items: list[Item] = []
        self.classifier: list[dict] = []
        self.classifier_seed: list[dict] = []
        self.classifier_keys: set[tuple[str, Optional[str], str, bool]] = set()
        self.retrieval: list[dict] = []
        self.seen_qa: dict[tuple[str, str], str] = {}
        self.skipped_dup = 0
        self.skipped_conflict = 0

    def add(self, task: str, quality: str, user: str, assistant: str,
            meta: Optional[dict] = None, system: str = "", seed: bool = False) -> None:
        user = clean_space(user)
        assistant = clean_space(assistant)
        if not user or not assistant:
            return
        qkey = (task, fold(user))
        prev = self.seen_qa.get(qkey)
        if prev is not None:
            if prev == fold(assistant):
                self.skipped_dup += 1
            else:
                self.skipped_conflict += 1
            return
        self.seen_qa[qkey] = fold(assistant)
        self.items.append(Item(task=task, quality=quality, user=user,
                               assistant=assistant, meta=meta or {}, system=system,
                               seed=seed))

    def add_classifier(self, text: str, topic: Optional[str], qtype: str,
                       label_source: str, quality: str, seed: bool = False) -> None:
        text = clean_space(text)
        if not text:
            return
        record = {
            "text": text,
            "labels": {"topic": topic, "question_type": qtype},
            "label_source": label_source,
            "quality": quality,
        }
        bucket = self.classifier_seed if seed else self.classifier
        key = (fold(text), topic, qtype, seed)
        if key in self.classifier_keys:
            return
        self.classifier_keys.add(key)
        bucket.append(record)


# ---------------------------------------------------------------------------
# Nạp chunk từ ChromaDB sqlite (không nạp embedding)
# ---------------------------------------------------------------------------
def load_chunks() -> list[dict]:
    if not CHROMA_SQLITE.exists():
        raise SystemExit(f"Không thấy {CHROMA_SQLITE}. Hãy chạy ingest.py trước.")
    con = sqlite3.connect(str(CHROMA_SQLITE))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT m1.string_value AS document,
               m2.int_value    AS chunk_id,
               m3.string_value AS source,
               m4.string_value AS tier
        FROM embeddings e
        JOIN embedding_metadata m1 ON m1.id = e.id AND m1.key = 'chroma:document'
        JOIN embedding_metadata m2 ON m2.id = e.id AND m2.key = 'chunk_id'
        JOIN embedding_metadata m3 ON m3.id = e.id AND m3.key = 'source'
        JOIN embedding_metadata m4 ON m4.id = e.id AND m4.key = 'tier'
        ORDER BY m2.int_value
        """
    ).fetchall()
    con.close()
    chunks = []
    for r in rows:
        text = r["document"] or ""
        source = r["source"] or ""
        article_match = re.search(r"\[Điều\s+(\d+)\.\]", text)
        body = text
        # Bỏ header "[nguồn]" + "- [Điều N.]" để câu trả lời dễ đọc.
        if body.startswith("["):
            end = body.find("]")
            if end != -1:
                body = body[end + 1:]
        body = re.sub(r"^\s*-\s*\[Điều\s+\d+\.\]\s*", "", body)
        body = re.sub(r"^\(phần\s+\d+/\d+\)\s*", "", body)
        chunks.append({
            "chunk_id": int(r["chunk_id"]),
            "source": source,
            "tier": r["tier"] or "Khác",
            "title": doc_title(source),
            "topic": SOURCE_TOPIC.get(source),
            "article": article_match.group(1) if article_match else None,
            "text": text,
            "body": clean_space(body),
            "dia": diacritic_ratio(text),
            "garbage": garbage_ratio(text),
            # Văn bản tiếng Việt đủ dấu đạt ~0,30–0,36; OCR mất dấu rơi xuống <0,10.
            # Ngưỡng 0,22 loại hẳn chunk OCR hỏng nhưng vẫn giữ văn bản gõ máy đủ dấu.
            "clean": diacritic_ratio(text) >= 0.22 and garbage_ratio(text) < 0.30,
        })
    return chunks


def load_benchmark() -> list[dict]:
    data = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    return data["questions"]


# ---------------------------------------------------------------------------
# A. Benchmark (gold) — ghi vào seed riêng
# ---------------------------------------------------------------------------
def build_benchmark(b: DatasetBuilder, bench: list[dict], chunks: list[dict]) -> None:
    by_source = defaultdict(list)
    for c in chunks:
        by_source[c["source"]].append(c)

    for q in bench:
        qid = q["id"]
        answer = q.get("ground_truth_answer") or q.get("expected_answer") or ""
        citation = q.get("ground_truth_citation") or q.get("source_document") or ""
        raw = q["raw_query"]
        normalized = q.get("normalized_query") or raw
        citations = q.get("expected_citations") or []
        source = q.get("source_document") or ""

        if not q.get("in_corpus") or not answer:
            b.add("refusal", "gold", raw, REFUSAL_TEXT,
                  {"benchmark_id": qid, "topic": q["category"], "question_type": q["question_type"]},
                  system=SYS_AGU, seed=True)
            continue

        full = answer
        if citation:
            full = f"{answer}\n\nNguồn: {citation}"
        b.add("benchmark_qa", "gold", raw, full,
              {"benchmark_id": qid, "topic": q["category"], "question_type": q["question_type"],
               "source_document": source, "citations": citations}, system=SYS_AGU, seed=True)
        b.add("benchmark_qa", "gold",
              f"{raw}\n\nYêu cầu: trả lời ngắn gọn trong 1–3 câu, nêu đúng con số/tên gọi quan trọng.",
              f"{trim_at_sentence(answer, 320)}\n\nNguồn: {citation}",
              {"benchmark_id": qid, "style": "concise", "topic": q["category"],
               "question_type": q["question_type"], "source_document": source}, system=SYS_AGU, seed=True)
        b.add("benchmark_citation", "gold",
              f"Đọc câu trả lời sau và nêu căn cứ pháp lý/nguồn cần dẫn kèm:\n\n{answer}",
              f"{citation}\n\nCác ý/giá trị cần dẫn: {', '.join(citations) if citations else 'xem nguồn'}.",
              {"benchmark_id": qid, "source_document": source}, system=SYS_AGU, seed=True)
        b.add("benchmark_question_gen", "gold",
              f"Từ câu trả lời sau, hãy đặt lại câu hỏi học vụ phù hợp (giữ nguyên thực thể):\n\n{answer}",
              raw, {"benchmark_id": qid, "topic": q["category"]}, system=SYS_TEACHER, seed=True)
        b.add("normalization", "gold",
              f'Chuẩn hóa câu hỏi đời thường sau thành một câu hỏi học vụ trang trọng, giữ nguyên mọi con số:\n"{raw}"',
              normalized, {"benchmark_id": qid}, system=SYS_TEACHER, seed=True)

        # Trắc nghiệm 4 lựa chọn: 1 đáp án đúng + 3 đáp án cùng chủ đề.
        pool = [
            x.get("ground_truth_answer") or x.get("expected_answer")
            for x in bench
            if x["id"] != qid and x.get("in_corpus") and
            (x.get("ground_truth_answer") or x.get("expected_answer"))
        ]
        if len(pool) >= 3:
            distractors = b.rng.sample(pool, 3)
            options = [answer] + distractors
            b.rng.shuffle(options)
            letters = "ABCD"
            correct_letter = letters[options.index(answer)]
            option_block = "\n".join(f"{letters[i]}. {trim_at_sentence(opt, 220)}" for i, opt in enumerate(options))
            b.add("benchmark_mcq", "gold",
                  f"Câu hỏi: {raw}\n\nCác lựa chọn:\n{option_block}\n\nChọn đáp án đúng nhất.",
                  f"Đáp án: {correct_letter}. {answer}\n\nNguồn: {citation}",
                  {"benchmark_id": qid, "topic": q["category"], "question_type": q["question_type"],
                   "source_document": source}, system=SYS_AGU, seed=True)

        # Ngữ cảnh đúng: chọn chunk trong đúng nguồn có overlap cao với đáp án.
        source_chunks = [c for c in by_source.get(source, []) if c["clean"]]
        ranked = sorted(source_chunks, key=lambda c: token_overlap(answer, c["body"]), reverse=True)
        if ranked and token_overlap(answer, ranked[0]["body"]) >= 0.30:
            ctx_docs = ranked[:2]
            context = "\n\n".join(f"[Ngữ cảnh {i}] {c['title']} | Tầng: {c['tier']}\n{trim_at_sentence(c['body'], 900)}"
                                  for i, c in enumerate(ctx_docs, start=1))
            b.add("grounded_qa", "gold",
                  f"NGỮ CẢNH:\n{context}\n\nCÂU HỎI: {raw}",
                  full,
                  {"benchmark_id": qid, "topic": q["category"], "question_type": q["question_type"],
                   "source_document": source, "contexts": [c["body"] for c in ctx_docs],
                   "citations": citations}, system=SYS_AGU, seed=True)

            # Kiểm tra trung thực: ngữ cảnh đúng nguồn → TRUNG THỰC.
            b.add("benchmark_faithfulness_check", "gold",
                  f"NGỮ CẢNH:\n{context}\n\nCÂU TRẢ LỜI: {answer}\n\nCâu trả lời có được ngữ cảnh hỗ trợ không? "
                  "Trả lời TRUNG THỰC hoặc KHÔNG TRUNG THỰC kèm lý do ngắn.",
                  "TRUNG THỰC — các thông tin chính trong câu trả lời xuất hiện trong ngữ cảnh cùng văn bản nguồn.",
                  {"benchmark_id": qid, "label": "supported"}, system=SYS_AGU, seed=True)

        # Nhiễu: ngữ cảnh từ văn bản khác → KHÔNG TRUNG THỰC.
        other_sources = [s for s in by_source if s and s != source and any(c["clean"] for c in by_source[s])]
        if other_sources:
            wrong_source = b.rng.choice(other_sources)
            wrong = [c for c in by_source[wrong_source] if c["clean"]]
            wrong_ctx = b.rng.sample(wrong, min(2, len(wrong)))
            overlap = token_overlap(answer, " ".join(c["body"] for c in wrong_ctx))
            if overlap < 0.18:
                context = "\n\n".join(
                    f"[Ngữ cảnh {i}] {c['title']} | Tầng: {c['tier']}\n{trim_at_sentence(c['body'], 900)}"
                    for i, c in enumerate(wrong_ctx, start=1)
                )
                b.add("benchmark_faithfulness_check", "gold",
                      f"NGỮ CẢNH:\n{context}\n\nCÂU TRẢ LỜI: {answer}\n\nCâu trả lời có được ngữ cảnh hỗ trợ không? "
                      "Trả lời TRUNG THỰC hoặc KHÔNG TRUNG THỰC kèm lý do ngắn.",
                      "KHÔNG TRUNG THỰC — ngữ cảnh trích từ văn bản khác, không chứa thông tin mà câu trả lời khẳng định.",
                      {"benchmark_id": qid, "label": "unsupported"}, system=SYS_AGU, seed=True)

        b.add_classifier(raw, q["category"], q["question_type"], "benchmark", "gold", seed=True)
        b.add_classifier(normalized, q["category"], q["question_type"], "benchmark", "gold", seed=True)


# ---------------------------------------------------------------------------
# B. Corpus — QA trích xuất từ chunk còn dấu
# ---------------------------------------------------------------------------
def build_corpus(b: DatasetBuilder, chunks: list[dict]) -> None:
    clean = [c for c in chunks if c["clean"] and len(c["body"]) >= 120]
    by_source_articles = defaultdict(list)

    for c in clean:
        title, source, article = c["title"], c["source"], c["article"]
        body = c["body"]
        cite = citation_of(source, article)
        lead = trim_at_sentence(body, 900)
        form_like = qa_unfriendly(title, body)

        if article:
            by_source_articles[source].append(c)
            if not form_like:
                b.add("corpus_qa", "silver",
                      f"Điều {article} của văn bản “{title}” quy định những nội dung gì?",
                      f"{lead}\n\nNguồn: {cite}",
                      {"source_document": source, "article": article, "tier": c["tier"]})
                b.add("corpus_summary", "silver",
                      f"Tóm tắt ngắn gọn (3–5 gạch đầu dòng) nội dung Điều {article} của “{title}”.",
                      "\n".join(f"- {s}" for s in sentence_split(body)[:4]) + f"\n\nNguồn: {cite}",
                      {"source_document": source, "article": article})

        if form_like:
            continue

        # Mẫu RAG có ngữ cảnh tường minh: dạy model trả lời CHỈ dựa trên đoạn được đưa.
        # Chỉ dùng chunk văn xuôi (đã loại biểu mẫu/bảng số/công văn hành chính ở trên).
        excerpt = trim_at_sentence(body, 700)
        grounded_question = (
            f"Điều {article} của “{title}” quy định những nội dung gì?"
            if article else f"Đoạn trích từ “{title}” quy định những nội dung gì?"
        )
        b.add("grounded_qa", "silver",
              f"NGỮ CẢNH:\n[{title} | {tier_label(c['tier'])}]\n{excerpt}\n\nCÂU HỎI: {grounded_question}",
              f"{lead}\n\nNguồn: {cite}",
              {"source_document": source, "article": article, "tier": c["tier"],
               "contexts": [excerpt], "citations": [cite]})

        # Câu hỏi điền khuyết từ câu có con số (bỏ số hiệu Điều/Khoản).
        for sent in sentence_split(body):
            if not (50 <= len(sent) <= 300):
                continue
            m = NUMBER_RE.search(sent)
            if not m or m.start() < 8:
                continue
            prefix = sent[max(0, m.start() - 12): m.start()].lower()
            if any(k in prefix for k in ("điều", "khoản", "chương", "mục", "phần")):
                continue
            number = m.group(0)
            blanked = sent[: m.start()] + "……" + sent[m.end():]
            b.add("corpus_cloze", "silver",
                  f"Điền thông tin còn thiếu vào chỗ trống (trích “{title}”):\n“{blanked}”",
                  f"{number}\n\nCâu đầy đủ: {sent}\nNguồn: {cite}",
                  {"source_document": source, "article": article})
            break

        # Câu hỏi liệt kê nếu chunk có ≥3 dòng gạch đầu dòng / số thứ tự.
        list_lines = []
        for line in body.splitlines():
            s = line.strip()
            if re.match(r"^(?:[-•+]\s+|\d{1,2}[.)]\s+)", s):
                content = re.sub(r"^(?:[-•+]\s+|\d{1,2}[.)]\s+)", "", s).strip()
                if len(content) >= 12:
                    list_lines.append(content)
        if 3 <= len(list_lines) <= 10:
            b.add("corpus_list", "silver",
                  f"Theo “{title}”{f' (Điều {article})' if article else ''}, hãy liệt kê các mục được đánh dấu trong văn bản.",
                  "\n".join(f"- {x}" for x in list_lines) + f"\n\nNguồn: {cite}",
                  {"source_document": source, "article": article})

    # So sánh 2 điều liên tiếp trong cùng văn bản (tối đa 5 cặp/văn bản).
    for source, arts in by_source_articles.items():
        arts = sorted(arts, key=lambda c: int(c["article"] or 0))
        for a, c in zip(arts[:5], arts[1:6]):
            if a["article"] == c["article"]:
                continue
            b.add("corpus_comparison", "silver",
                  f"So sánh nội dung Điều {a['article']} và Điều {c['article']} của “{a['title']}”.",
                  f"Điều {a['article']}: {trim_at_sentence(a['body'], 420)}\n\n"
                  f"Điều {c['article']}: {trim_at_sentence(c['body'], 420)}\n\n"
                  f"Nguồn: ({a['source']})",
                  {"source_document": source, "article_a": a["article"], "article_b": c["article"]})

    # Mục lục điều của từng văn bản.
    for source, arts in by_source_articles.items():
        labels = sorted({c["article"] for c in arts if c["article"]}, key=int)
        if len(labels) >= 2:
            b.add("corpus_article_index", "silver",
                  f"Văn bản “{doc_title(source)}” có những điều nào trong corpus? Liệt kê số điều.",
                  f"Các điều: {', '.join(labels)}.\nNguồn: ({source})",
                  {"source_document": source})

    # Bản đồ chủ đề → văn bản.
    topic_docs = defaultdict(set)
    for source, topic in SOURCE_TOPIC.items():
        topic_docs[topic].add(source)
    for topic, sources in sorted(topic_docs.items()):
        b.add("corpus_topic_index", "silver",
              f"Những văn bản nào trong corpus thuộc chủ đề “{topic}”?",
              "\n".join(f"- {doc_title(s)} ({s})" for s in sorted(sources)),
              {"topic": topic, "sources": sorted(sources)})

    # Nhận diện nguồn/tầng/chủ đề cho MỌI chunk (kể cả OCR mất dấu).
    for c in chunks:
        body = c["body"]
        if len(body) < 80:
            continue
        excerpt = trim_at_sentence(body, 420)
        b.add("corpus_identification", "bronze",
              f"Đoạn văn sau trích từ văn bản nào trong corpus?\n\n“{excerpt}”",
              f"{c['title']} — file {c['source']} ({tier_label(c['tier'])}).",
              {"source_document": c["source"], "tier": c["tier"], "chunk_id": c["chunk_id"]})
        b.add("corpus_identification", "bronze",
              f"Đoạn văn sau thuộc tầng tài liệu nào?\n\n“{excerpt}”",
              f"{tier_label(c['tier'])} — tài liệu {c['title']} ({c['source']}).",
              {"source_document": c["source"], "tier": c["tier"], "chunk_id": c["chunk_id"]})
        if c["topic"]:
            b.add("corpus_identification", "bronze",
                  f"Đoạn văn sau thuộc chủ đề nào trong 14 chủ đề của bộ quy chế AGU?\n\n“{excerpt}”",
                  f"Chủ đề: {c['topic']}.\nNguồn: {c['title']} ({c['source']}).",
                  {"source_document": c["source"], "topic": c["topic"], "chunk_id": c["chunk_id"]})
        if c["article"]:
            b.add("corpus_identification", "bronze",
                  f"Đoạn văn sau thuộc điều nào của văn bản “{c['title']}”?\n\n“{excerpt}”",
                  f"Điều {c['article']} của {c['title']} ({c['source']}).",
                  {"source_document": c["source"], "article": c["article"], "chunk_id": c["chunk_id"]})
        nums = NUMBER_RE.findall(excerpt)
        if len(nums) >= 3:
            b.add("corpus_identification", "bronze",
                  f"Liệt kê các con số xuất hiện trong đoạn văn sau (giữ nguyên định dạng):\n\n“{excerpt}”",
                  ", ".join(dict.fromkeys(nums)),
                  {"source_document": c["source"], "chunk_id": c["chunk_id"]})


# ---------------------------------------------------------------------------
# C. Mã nguồn — QA từ AST + docstring
# ---------------------------------------------------------------------------
def _doc_summary(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    if not doc:
        return ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", doc) if p.strip()]
    return paragraphs[0] if paragraphs else ""


def _format_args(node: ast.AST) -> str:
    args = getattr(node, "args", None)
    if args is None:
        return ""
    try:
        return ast.unparse(args)
    except Exception:
        return ""


def build_code(b: DatasetBuilder) -> None:
    py_files = sorted((ROOT / "src").rglob("*.py")) + [ROOT / "main.py", ROOT / "ui" / "demo_streamlit.py", ROOT / "scripts" / "benchmark_chunking.py", ROOT / "ingest.py", ROOT / "scripts" / "learn.py"]
    for path in py_files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        mod_doc = ast.get_docstring(tree) or ""
        if mod_doc:
            b.add("code_module", "silver",
                  f"Module `{rel}` trong đồ án Hybrid RAG AGU chịu trách nhiệm gì?",
                  f"{_doc_summary(tree)}\n\nĐịnh nghĩa tại: {rel}. "
                  f"Module gồm {sum(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))} hàm và "
                  f"{sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))} lớp.",
                  {"file": rel}, system=SYS_PROJECT)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            name = node.name
            if name.startswith("__"):
                continue
            doc = ast.get_docstring(node) or ""
            summary = _doc_summary(node)
            if len(doc.strip()) < 40:
                continue
            kind = "lớp" if isinstance(node, ast.ClassDef) else "hàm"
            loc = f"{rel}:{getattr(node, 'lineno', '?')}"
            signature = ""
            if not isinstance(node, ast.ClassDef):
                signature = f"{name}({_format_args(node)})"
            b.add("code_qa", "silver",
                  f"Trong đồ án, {kind} `{name}` ({rel}) làm gì? Giải thích ngắn gọn và chỉ ra vị trí định nghĩa.",
                  f"{summary}\n\nĐịnh nghĩa: {loc}." + (f" Chữ ký: `{signature}`." if signature else ""),
                  {"file": rel, "name": name, "line": getattr(node, "lineno", None)}, system=SYS_PROJECT)
            if signature:
                b.add("code_signature", "silver",
                      f"Nêu chữ ký hàm `{name}` trong `{rel}` và ý nghĩa tham số chính.",
                      f"Chữ ký: `{signature}` — dòng {getattr(node, 'lineno', '?')} của {rel}.\n\n{trim_at_sentence(doc, 700)}",
                      {"file": rel, "name": name}, system=SYS_PROJECT)
            if len(doc) > 220:
                b.add("code_qa", "silver",
                      f"Giải thích chi tiết cơ chế hoạt động của `{name}` ({rel}) theo docstring của mã nguồn.",
                      f"{trim_at_sentence(doc, 1000)}\n\nVị trí: {loc}.",
                      {"file": rel, "name": name}, system=SYS_PROJECT)

    # Test names → hành vi được kiểm chứng.
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            doc = _doc_summary(node)
            human = node.name[len("test_"):].replace("_", " ")
            b.add("code_tests", "silver",
                  f"Bộ test `{rel}` có kiểm chứng hành vi “{human}” không? Nó nằm ở đâu?",
                  f"Có. Test `{node.name}` trong {rel}:{getattr(node, 'lineno', '?')}."
                  + (f" Mô tả: {doc}" if doc else ""),
                  {"file": rel, "test": node.name}, system=SYS_PROJECT)

    # Biến môi trường từ .env.example.
    if ENV_EXAMPLE.exists():
        current_key = None
        current_comment: list[str] = []
        for raw_line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue
            if line.lstrip().startswith("#"):
                current_comment.append(line.lstrip("# ").strip())
                continue
            m = re.match(r"^([A-Z0-9_]+)\s*=\s*([^#]*)(?:#\s*(.*))?$", line.strip())
            if not m:
                continue
            key, value, inline = m.group(1), m.group(2).strip(), (m.group(3) or "").strip()
            desc = " ".join([c for c in current_comment if c][-2:] + ([inline] if inline else []))
            b.add("code_env", "silver",
                  f"Biến môi trường `{key}` trong đồ án có tác dụng gì? Giá trị mặc định là gì?",
                  f"`{key}` — giá trị mặc định: `{value or '(trống)'}`. {desc or 'Xem README mục 3.'}",
                  {"env": key}, system=SYS_PROJECT)
            current_key, current_comment = key, []


# ---------------------------------------------------------------------------
# C2. Mã nguồn — chỉ mục file, tham số, nơi gọi (AST, không cần LLM)
# ---------------------------------------------------------------------------
def _py_files() -> list[Path]:
    files = sorted((ROOT / "src").rglob("*.py"))
    files += [ROOT / name for name in (
        "main.py", "ui/demo_streamlit.py", "scripts/benchmark_chunking.py", "ingest.py",
        "scripts/learn.py")]
    files += sorted((ROOT / "tests").glob("test_*.py"))
    return [p for p in files if p.exists()]


def _call_target(node: ast.Call) -> Optional[str]:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def build_code_index(b: DatasetBuilder) -> None:
    """Sinh câu hỏi về chỉ mục file, tham số hàm và nơi gọi — tất cả suy ra từ AST."""
    defs: dict[str, list[dict]] = defaultdict(list)
    calls: dict[str, list[dict]] = defaultdict(list)
    file_symbols: dict[str, list[dict]] = {}

    for path in _py_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        symbols = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append({
                    "name": node.name,
                    "kind": "lớp" if isinstance(node, ast.ClassDef) else "hàm",
                    "line": getattr(node, "lineno", None),
                })
        file_symbols[rel] = symbols

        def visit(node: ast.AST, stack: list[ast.AST]) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = "lớp" if isinstance(child, ast.ClassDef) else "hàm"
                    is_method = bool(stack) and isinstance(stack[-1], ast.ClassDef)
                    defs[child.name].append({"file": rel, "line": getattr(child, "lineno", None),
                                             "kind": kind, "node": child, "is_method": is_method})
                    visit(child, stack + [child])
                else:
                    if isinstance(child, ast.Call):
                        target = _call_target(child)
                        if target:
                            caller = getattr(stack[-1], "name", "(cấp module)") if stack else "(cấp module)"
                            calls[target].append({"file": rel, "line": getattr(child, "lineno", None),
                                                  "caller": caller})
                    visit(child, stack)

        visit(tree, [])

    # Chỉ mục file: hàm/lớp cấp cao nhất.
    for rel, symbols in file_symbols.items():
        listed = symbols[:20]
        if listed:
            answer = "\n".join(f"- {s['kind']} `{s['name']}` — dòng {s['line']}" for s in listed)
            if len(symbols) > len(listed):
                answer += f"\n- … và {len(symbols) - len(listed)} định nghĩa khác."
        else:
            answer = "File không có hàm/lớp cấp cao nhất; chủ yếu chứa hằng số hoặc mã thực thi."
        b.add("code_file_index", "silver",
              f"File `{rel}` định nghĩa những hàm/lớp cấp cao nhất nào? Nêu kèm số dòng.",
              answer, {"file": rel, "count": len(symbols)}, system=SYS_PROJECT)

    # Tham số hàm: chỉ hỏi khi có ≥2 tham số và docstring đủ nghĩa.
    for name, entries in defs.items():
        for entry in entries:
            if entry.get("is_method"):
                continue
            node = entry["node"]
            if isinstance(node, ast.ClassDef):
                continue
            args = getattr(node, "args", None)
            if args is None or len(args.args) < 2:
                continue
            doc = ast.get_docstring(node) or ""
            if len(doc.strip()) < 40:
                continue
            signature = f"{name}({_format_args(node)})"
            b.add("code_params", "silver",
                  f"Hàm `{name}` trong `{entry['file']}` nhận những tham số nào? "
                  "Nêu chữ ký đầy đủ và ý nghĩa chính.",
                  f"Chữ ký: `{signature}` — dòng {entry['line']} của {entry['file']}.\n\n"
                  f"{trim_at_sentence(doc, 500)}",
                  {"file": entry["file"], "name": name}, system=SYS_PROJECT)

    # Nơi gọi: chỉ sinh cho hàm/module-level; bỏ phương thức vì tên trùng giữa các lớp
    # và lời gọi `.method()` không chỉ rõ lớp nhận.
    for name, entries in defs.items():
        module_level = [e for e in entries if not e.get("is_method")]
        if not module_level:
            continue
        sites = calls.get(name)
        if not sites:
            continue
        # Bỏ chính định nghĩa nếu trùng tên ở nhiều file; vẫn giữ vì câu trả lời nêu file.
        seen_sites = set()
        unique_sites = []
        for site in sites:
            key = (site["file"], site["line"])
            if key in seen_sites:
                continue
            seen_sites.add(key)
            unique_sites.append(site)
        unique_sites.sort(key=lambda s: (s["file"], s["line"] or 0))
        shown = unique_sites[:10]
        answer = "\n".join(
            f"- `{s['file']}:{s['line']}` — trong `{s['caller']}`" for s in shown)
        if len(unique_sites) > len(shown):
            answer += f"\n- … và {len(unique_sites) - len(shown)} nơi gọi khác."
        def_files = ", ".join(sorted({e["file"] for e in module_level}))
        b.add("code_callsite", "silver",
              f"Hàm `{name}` (định nghĩa tại {def_files}) được gọi ở những đâu trong repo?",
              answer, {"name": name, "call_sites": len(unique_sites)}, system=SYS_PROJECT)


# ---------------------------------------------------------------------------
# D. Tài liệu markdown — QA theo mục
# ---------------------------------------------------------------------------
def parse_markdown_sections(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections: list[dict] = []
    current = None
    for line in lines:
        m = re.match(r"^(#{2,3})\s+(.+)$", line)
        if m:
            if current and len(current["body"].strip()) >= 200:
                sections.append(current)
            current = {"heading": m.group(2).strip(), "level": len(m.group(1)), "body": ""}
        elif current is not None:
            current["body"] += line + "\n"
    if current and len(current["body"].strip()) >= 200:
        sections.append(current)
    return sections


def build_docs(b: DatasetBuilder) -> None:
    doc_files = [ROOT / "README.md", ROOT / "docs/architecture/SYSTEM_ARCHITECTURE.md", ROOT / "docs/spec/TAXONOMY.md",
                 ROOT / "docs/planning/ROADMAP.md", ROOT / "docs/guides/TROUBLESHOOTING_GUI.md"]
    doc_files += sorted((ROOT / "docs/bao_cao").glob("*.md"))
    for path in doc_files:
        if not path.exists():
            continue
        rel = path.relative_to(ROOT).as_posix()
        for sec in parse_markdown_sections(path):
            body = re.sub(r"```.*?```", "[đoạn mã]", sec["body"], flags=re.S).strip()
            body = clean_space(body)
            if len(body) < 200:
                continue
            answer = trim_at_sentence(body, 900)
            b.add("docs_qa", "silver",
                  f"Theo tài liệu `{rel}`, mục “{sec['heading']}” trình bày những gì?",
                  f"{answer}\n\nNguồn: {rel} — mục “{sec['heading']}”.",
                  {"file": rel, "heading": sec["heading"]}, system=SYS_TEACHER)
            b.add("docs_heading", "silver",
                  f"Tóm tắt mục “{sec['heading']}” của `{rel}` trong 3 câu.",
                  " ".join(sentence_split(body)[:3]) + f"\n\nNguồn: {rel}.",
                  {"file": rel, "heading": sec["heading"]}, system=SYS_TEACHER)


# ---------------------------------------------------------------------------
# E. Classifier tổng hợp (template) + biến thể benchmark
# ---------------------------------------------------------------------------
TOPIC_KEYWORDS_BANK = {
    "chương trình đào tạo": ["môn học", "mã môn", "tín chỉ", "học kỳ", "môn học trước", "chuẩn đầu ra ELO", "khối kiến thức"],
    "học phí": ["học phí", "miễn giảm học phí", "đơn giá tín chỉ", "gia hạn nộp học phí", "học lại", "cải thiện điểm"],
    "cuộc thi chính luận": ["cuộc thi chính luận", "tác phẩm dự thi", "thể loại bài thi", "dung lượng bài", "hạn nộp bài"],
    "đánh giá rèn luyện": ["điểm rèn luyện", "khung điểm rèn luyện", "tiêu chí cộng điểm", "tiêu chí trừ điểm", "xếp loại rèn luyện"],
    "khen thưởng sinh viên": ["danh hiệu Sinh viên Giỏi", "danh hiệu Sinh viên Xuất sắc", "giấy khen", "mức tiền thưởng", "danh hiệu thi đua"],
    "thực tập tốt nghiệp": ["thực tập tốt nghiệp", "khóa luận tốt nghiệp", "hội đồng chấm", "báo cáo thực tập", "điểm thực tập"],
    "quy chế công tác sinh viên": ["nghỉ học tạm thời", "kỷ luật sinh viên", "nhập học lại", "cố vấn học tập", "nghĩa vụ sinh viên", "thi cử"],
    "sinh viên 5 tốt": ["danh hiệu Sinh viên 5 tốt", "Sao Tháng Giêng", "tiêu chuẩn Sinh viên 5 tốt", "hồ sơ Sinh viên 5 tốt"],
    "thực tập chuyên đề": ["thực tập chuyên đề", "tài liệu nghiệm thu", "cơ sở thực tập", "báo cáo thực tập chuyên đề"],
    "khen thưởng cấp ĐHQG": ["khen thưởng cấp ĐHQG", "Sinh viên Xuất sắc toàn khóa", "Đại học Quốc gia", "mức thưởng ĐHQG"],
    "ký túc xá": ["ký túc xá", "nội trú", "giờ ra vào ký túc xá", "thiết bị điện trong phòng", "nội quy ký túc xá"],
    "tài chính sinh viên": ["vay vốn học tập", "tín dụng ưu đãi ACB", "lãi suất vay", "trả nợ gốc", "hồ sơ vay vốn"],
    "bảo hiểm y tế": ["bảo hiểm y tế", "BHYT", "ứng dụng VssID", "VNeID", "mức thu BHYT"],
    "hành chính sinh viên": ["mẫu đơn", "đơn xác nhận hoàn cảnh khó khăn", "cơ quan xác nhận", "chuyển nhóm học phần", "miễn học phần"],
}

OFF_DOMAIN_QUESTIONS = [
    "Thời tiết ở Long Xuyên ngày mai thế nào?",
    "Giá vàng hôm nay là bao nhiêu?",
    "Làm sao để nấu phở bò ngon?",
    "Điểm chuẩn đại học năm nay của trường khác là bao nhiêu?",
    "Thủ tục xin visa du học Nhật Bản gồm những gì?",
    "Cách học lập trình Python hiệu quả?",
    "Tôi muốn tư vấn tâm lý vì đang stress thi cử.",
    "Giá xăng RON95 hôm nay bao nhiêu?",
    "Cách chăm sóc cây cảnh trong mùa mưa?",
    "Đội bóng nào vô địch World Cup?",
    "Làm thế nào để giảm cân an toàn?",
    "Thủ tục mua xe máy trả góp?",
    "Cách sửa lỗi máy tính không lên màn hình?",
    "Tỉ giá USD hôm nay là bao nhiêu?",
    "Hướng dẫn nấu cơm bằng nồi cơm điện?",
    "Cách đăng ký tài khoản Facebook?",
    "Thủ tục xin hộ chiếu lần đầu?",
    "Cách trồng rau sạch tại nhà?",
    "Địa chỉ bệnh viện gần nhất?",
    "Cách học tiếng Anh giao tiếp cấp tốc?",
    "Giá vé máy bay Hà Nội - Cần Thơ?",
    "Cách làm bánh mì tại nhà?",
    "Làm sao để ngủ ngon hơn?",
    "Cách chọn mua điện thoại thông minh?",
    "Thủ tục đăng ký tạm trú?",
    "Cách chăm sóc da mùa khô?",
    "Làm thế nào để thi bằng lái xe máy?",
    "Cách đầu tư chứng khoán cho người mới?",
    "Cách giảm đau đầu khi làm việc nhiều giờ?",
    "Giá cà phê hôm nay?",
    "Cách tập gym đúng cách?",
    "Làm sao để viết CV xin việc?",
    "Cách đặt vé tàu hỏa?",
    "Thủ tục chuyển trường sang đại học khác?",
    "Cách cài đặt Windows mới?",
    "Cách nuôi mèo con?",
    "Giá điện sinh hoạt tháng này?",
    "Cách học lái ô tô?",
    "Làm sao để có bạn gái?",
    "Cách kiếm tiền online?",
    "Thủ tục xin học bổng du học Mỹ?",
    "Cách giặt áo len không bị co?",
    "Làm sao để bảo vệ môi trường?",
    "Cách sử dụng máy tính Casio?",
    "Giá thịt heo hôm nay?",
    "Cách chữa cảm cúm tại nhà?",
    "Cách chơi guitar cơ bản?",
    "Thủ tục mở tài khoản ngân hàng?",
    "Cách điều trị mụn trứng cá?",
    "Làm sao để học tốt toán?",
    "Cách làm video TikTok?",
    "Giá vàng SJC hôm nay?",
    "Cách trồng cây trong chậu?",
    "Thủ tục xin giấy phép kinh doanh?",
    "Cách chọn mua laptop?",
    "Làm sao để giảm căng thẳng trước kỳ thi?",
    "Cách nấu lẩu thái?",
    "Giá vé xem phim cuối tuần?",
    "Cách sửa xe đạp bị xẹp lốp?",
    "Thủ tục xin nghỉ việc?",
]

PREFIXES = ["", "Cho em hỏi: ", "Em muốn biết: ", "Nhờ tư vấn giúp em: "]


def build_classifier(b: DatasetBuilder, bench: list[dict]) -> None:
    # Biến thể câu hỏi benchmark (giữ nguyên nhãn) — seed riêng.
    replacements = [
        ("quy định như thế nào", "ra sao"),
        ("là bao nhiêu", "là bao nhiêu vậy"),
        ("gồm những gì", "gồm những gì ạ"),
        ("có được", "có được không ạ"),
    ]
    for q in bench:
        raw = q["raw_query"]
        variants = {raw}
        for prefix in PREFIXES[1:]:
            variants.add(prefix + raw)
        for old, new in replacements:
            if old in raw.lower():
                variants.add(re.sub(old, new, raw, flags=re.I))
        for v in sorted(variants)[:5]:
            b.add_classifier(v, q["category"], q["question_type"], "benchmark_variant", "gold", seed=True)

    # Template theo chủ đề + loại câu hỏi.
    for topic, keywords in TOPIC_KEYWORDS_BANK.items():
        for i, kw in enumerate(keywords):
            templates = [
                ("TRA_CUU", f"Theo quy chế AGU, {kw} được quy định như thế nào?"),
                ("TRA_CUU", f"Sinh viên cần biết những gì về {kw}?"),
                ("TRA_CUU", f"{kw.capitalize()} theo quy định hiện hành là gì?"),
                ("TRA_CUU", f"Quy định hiện hành về {kw} là gì?"),
                ("THU_TUC", f"Các bước thực hiện {kw} như thế nào?"),
                ("THU_TUC", f"Hồ sơ, giấy tờ để giải quyết vấn đề {kw} gồm những gì?"),
                ("THU_TUC", f"Thủ tục liên quan đến {kw} cần nộp ở đâu?"),
            ]
            if len(keywords) > 1:
                kw2 = keywords[(i + 1) % len(keywords)]
                templates.append(("SO_SANH", f"So sánh quy định về {kw} và {kw2}?"))
                templates.append(("SO_SANH", f"Giữa {kw} và {kw2} có điểm gì khác nhau?"))
            for qtype, question in templates:
                for prefix in PREFIXES:
                    b.add_classifier(prefix + question, topic, qtype, "template", "silver")
        # Câu hỏi cấp chủ đề.
        for qtype, question in [
            ("TRA_CUU", f"Quy định của Trường về {topic} hiện nay thế nào?"),
            ("THU_TUC", f"Cần chuẩn bị hồ sơ gì cho các vấn đề về {topic}?"),
            ("SO_SANH", f"Các mức quy định về {topic} khác nhau ra sao?"),
        ]:
            b.add_classifier(question, topic, qtype, "template", "silver")

    for question in OFF_DOMAIN_QUESTIONS:
        for prefix in ("", "Cho em hỏi: ", "Em muốn biết: "):
            b.add_classifier(prefix + question, None, "NGOAI_PHAM_VI", "template", "silver")


# ---------------------------------------------------------------------------
# F. Refusal + grounded refusal
# ---------------------------------------------------------------------------
def build_refusal(b: DatasetBuilder, bench: list[dict], chunks: list[dict]) -> None:
    for question in OFF_DOMAIN_QUESTIONS:
        for prefix in ("", "Cho em hỏi: ", "Nhờ trợ lý giải đáp: "):
            b.add("refusal", "silver", prefix + question, REFUSAL_TEXT,
                  {"reason": "out_of_domain"}, system=SYS_AGU)

    clean = [c for c in chunks if c["clean"] and len(c["body"]) >= 200]
    in_corpus = [q for q in bench if q.get("in_corpus")]
    for i in range(150):
        ctx = b.rng.choice(clean)
        candidates = [q for q in in_corpus if q.get("source_document") != ctx["source"]]
        q = b.rng.choice(candidates)
        context_excerpt = trim_at_sentence(ctx["body"], 700)
        if token_overlap(q["raw_query"], context_excerpt) > 0.20:
            continue
        b.add("grounded_refusal", "silver",
              f"NGỮ CẢNH:\n{context_excerpt}\n\nCÂU HỎI: {q['raw_query']}",
              REFUSAL_TEXT,
              {"benchmark_id": q["id"], "context_source": ctx["source"], "reason": "not_in_context"},
              system=SYS_AGU)


# ---------------------------------------------------------------------------
# G. Truy xuất (query → positive + negatives)
# ---------------------------------------------------------------------------
def build_retrieval(b: DatasetBuilder, chunks: list[dict], bench: list[dict]) -> None:
    by_source = defaultdict(list)
    for c in chunks:
        by_source[c["source"]].append(c)

    def add_pair(query: str, positive: dict, quality: str, folded: bool = False) -> None:
        query = clean_space(query)
        if not query:
            return
        key = (fold(query), positive["chunk_id"])
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        others = [c for c in chunks if c["source"] != positive["source"] and len(c["body"]) > 100]
        if len(others) < 3:
            return
        negatives = b.rng.sample(others, 3)
        b.retrieval.append({
            "query": query,
            "positive": positive["body"],
            "positive_source": positive["source"],
            "positive_chunk_id": positive["chunk_id"],
            "negatives": [n["body"] for n in negatives],
            "negative_sources": [n["source"] for n in negatives],
            "quality": quality,
            "folded": folded,
        })

    seen_pairs: set[tuple[str, int]] = set()

    def content_words(text: str, limit: int = 6) -> list[str]:
        """Lấy từ nội dung đầu tiên (bỏ stopwords) để dựng truy vấn từ khóa."""
        picked: list[str] = []
        for word in re.findall(r"[^\W\d_]+", text, re.UNICODE):
            folded_word = fold(word)
            if len(folded_word) < 3 or folded_word in STOPWORDS:
                continue
            if any(fold(existing) == folded_word for existing in picked):
                continue
            picked.append(word)
            if len(picked) >= limit:
                break
        return picked

    def clean_sentence(text: str) -> str:
        text = re.sub(r"^(?:[-+•*]\s+|\d{1,2}[.)]\s+)", "", text.strip())
        return clean_space(text)

    # Từ khóa / số Điều / cấp văn bản cho MỌI chunk (kể cả OCR): query fold nếu chunk mất dấu.
    for c in chunks:
        if len(c["body"]) < 100:
            continue
        folded = not c["clean"]
        quality = "bronze" if folded else "silver"
        if not qa_unfriendly(c["title"], c["body"]):
            words = content_words(c["body"], 6)
            if len(words) >= 3:
                add_pair("Quy định về " + ", ".join(fold(w) if folded else w for w in words[:4]) + "?",
                         c, quality, folded=folded)
            if len(words) >= 6:
                add_pair("Tài liệu về " + ", ".join(fold(w) if folded else w for w in words[3:6]) + "?",
                         c, quality, folded=folded)
            if c["clean"]:
                first = clean_sentence(sentence_split(c["body"])[0]) if sentence_split(c["body"]) else ""
                if len(first) > 30:
                    add_pair(trim_at_sentence(first, 140).rstrip(".") + " là gì?", c, quality)
        if c["article"]:
            title = fold(c["title"]) if folded else c["title"]
            add_pair(f"Điều {c['article']} của {title} quy định gì?",
                     c, quality, folded=folded)

    # Mỗi văn bản một câu hỏi cấp tài liệu (positive = chunk dài nhất — câu trả lời đầy đủ nhất).
    for _source, group in by_source.items():
        group = [c for c in group if len(c["body"]) >= 100]
        if not group:
            continue
        best = max(group, key=lambda c: len(c["body"]))
        folded = not best["clean"]
        title = fold(best["title"]) if folded else best["title"]
        add_pair(f"Quy định về {title} gồm những nội dung gì?", best,
                 "bronze" if folded else "silver", folded=folded)

    for q in bench:
        if not q.get("in_corpus") or not q.get("ground_truth_answer"):
            continue
        source = q.get("source_document")
        pool = by_source.get(source, [])
        if not pool:
            continue
        ranked = sorted(pool, key=lambda c: token_overlap(q["ground_truth_answer"], c["body"]), reverse=True)
        if token_overlap(q["ground_truth_answer"], ranked[0]["body"]) >= 0.28:
            add_pair(q["raw_query"], ranked[0], "gold")


# ---------------------------------------------------------------------------
# H. Tác vụ cấu hình router / prompt / chỉ số / vấn đáp
# ---------------------------------------------------------------------------
def build_router_tasks(b: DatasetBuilder, bench: list[dict]) -> None:
    try:
        from src.retrieval.router import base_config_from_env, get_retrieval_config
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] Không import được router ({exc}) — bỏ qua tác vụ router_config.")
        return

    def config_answer(topic: Optional[str], qtype: str) -> str:
        base = base_config_from_env()
        base.top_k = 4
        cfg = get_retrieval_config({"topic": topic, "question_type": qtype}, base)
        return json.dumps({
            "top_k": cfg.top_k,
            "bm25_weight": cfg.bm25_weight,
            "chroma_weight": cfg.chroma_weight,
            "source_filter": cfg.source_filter,
            "enable_subquery": cfg.enable_subquery,
        }, ensure_ascii=False)

    topics = list(TOPIC_KEYWORDS_BANK.keys())
    types = ["TRA_CUU", "SO_SANH", "THU_TUC", "NGOAI_PHAM_VI"]
    for topic in topics:
        for qtype in types:
            b.add("router_config", "silver",
                  f"Cho nhãn phân loại topic=“{topic}”, question_type=“{qtype}”. "
                  "Hãy nêu cấu hình truy xuất mà router sinh ra (top_k, trọng số BM25/Chroma, lọc nguồn, tách truy vấn con).",
                  config_answer(topic, qtype),
                  {"topic": topic, "question_type": qtype}, system=SYS_PROJECT)
    for q in bench:
        b.add("router_config", "gold",
              f"Cho nhãn phân loại topic=“{q['category']}”, question_type=“{q['question_type']}”. "
              "Hãy nêu cấu hình truy xuất mà router sinh ra.",
              config_answer(q["category"], q["question_type"]),
              {"benchmark_id": q["id"]}, system=SYS_PROJECT, seed=True)

    b.add("prompt_rules", "silver",
          "Generator chọn khối quy tắc prompt nào cho question_type=SO_SANH?",
          "Dùng PROMPT_RULES_SO_SANH: nối thêm phụ lục yêu cầu trình bày BẢNG so sánh theo tiêu chí, "
          "mỗi ô phải có trích dẫn riêng; nếu chỉ đủ căn cứ một vế thì nêu rõ vế còn lại thiếu căn cứ, không bịa.",
          {}, system=SYS_PROJECT)
    b.add("prompt_rules", "silver",
          "Generator chọn khối quy tắc prompt nào cho question_type=THU_TUC?",
          "Dùng PROMPT_RULES_THU_TUC: yêu cầu các bước đánh số theo thứ tự, mỗi bước kèm căn cứ; "
          "liệt kê hồ sơ/giấy tờ sau các bước; bước thiếu căn cứ phải nói rõ.",
          {}, system=SYS_PROJECT)
    b.add("prompt_rules", "silver",
          "Generator xử lý question_type=NGOAI_PHAM_VI thế nào? Có bỏ qua truy xuất không?",
          "KHÔNG bỏ qua truy xuất. Dùng PROMPT_RULES + một dòng nhắc từ chối chuẩn; nếu model tự từ chối, "
          "canonicalize_refusal chuẩn hóa về đúng REFUSAL_TEXT. Lý do: nhãn NGOAI precision thấp, skip sớm sẽ từ chối oan.",
          {}, system=SYS_PROJECT)


def build_handcrafted(b: DatasetBuilder) -> None:
    # Lệnh chạy.
    commands = [
        ("Nạp corpus vào ChromaDB", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe ingest.py"),
        ("Chạy CLI hỏi đáp tương tác", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe main.py"),
        ("Hỏi một câu rồi thoát", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe main.py \"Điều kiện xét tốt nghiệp?\""),
        ("Đổi số chunk ngữ cảnh", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe main.py --top-k 6"),
        ("Chạy toàn bộ test", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest -q"),
        ("Chạy evaluation benchmark", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/assessment/evaluation.py --benchmark data/evaluation/benchmark_100_questions_v3.json"),
        ("Chạy evaluation A/B lượt WITHOUT", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/assessment/evaluation.py --benchmark data/evaluation/benchmark_100_questions_v3.json --output outputs/ab_results_without_classifier.json"),
        ("Chạy evaluation A/B lượt WITH", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/assessment/evaluation.py --benchmark data/evaluation/benchmark_100_questions_v3.json --with-classifier --output outputs/ab_results_with_classifier.json"),
        ("Ước lượng request trước khi chạy", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/assessment/evaluation.py --benchmark data/evaluation/benchmark_100_questions_v3.json --dry-run"),
        ("Đánh giá classifier trên benchmark", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/assessment/evaluate_classifier.py"),
        ("Chạy benchmark 3 chiến lược chunking", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/benchmark_chunking.py"),
        ("Chạy demo Streamlit", "./venv/Scripts/python.exe -m streamlit run ui/demo_streamlit.py"),
        ("Chạy GUI Tkinter", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe ui/app.py"),
        ("Chạy chế độ học (learn)", "PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/learn.py"),
    ]
    for purpose, command in commands:
        b.add("code_commands", "silver",
              f"Lệnh nào dùng để {purpose.lower()} trong đồ án?",
              f"`{command}`\n\nChạy tại thư mục gốc repo; trên Windows dùng Git Bash hoặc PowerShell với PYTHONIOENCODING=utf-8.",
              {"purpose": purpose}, system=SYS_PROJECT)

    # Chỉ số đánh giá.
    metrics = [
        ("Hit@K", "Tỉ lệ câu hỏi có ít nhất một chunk chứa văn bản nguồn đúng nằm trong top K kết quả truy xuất. "
                  "Hit cao nghĩa là recall của bộ truy xuất tốt."),
        ("MRR", "Mean Reciprocal Rank — trung bình của 1/hạng của chunk đúng đầu tiên. Chunk đúng ở hạng 1 cho 1.0, "
                "hạng 2 cho 0.5, hạng 3 cho 0.333… MRR càng cao càng tốt."),
        ("Citation Precision/Recall/F1", "So khớp tập trích dẫn dự đoán với tập trích dẫn kỳ vọng (Điều/Khoản, con số, tên file). "
                                         "F1 là trung bình điều hòa của precision và recall."),
        ("Faithfulness", "Độ trung thực của câu trả lời với ngữ cảnh: tỉ lệ khẳng định trong câu trả lời được ngữ cảnh hỗ trợ. "
                         "Dự án có hai cách đo: LLM judge và heuristic token-overlap."),
        ("Tỉ lệ từ chối", "Phần trăm câu trả lời chứa REFUSAL_MARKER (hoặc đúng REFUSAL_TEXT). Với câu ngoài corpus, "
                          "từ chối đúng là hành vi mong muốn; với câu trong corpus, từ chối là từ chối oan."),
        ("skipped_no_gt", "Câu hỏi không có ground truth (Q96–Q98) được bỏ qua khi chấm Hit/Citation/Faithfulness "
                          "nhưng vẫn được đo hành vi từ chối."),
        ("False refusal", "Tỉ lệ từ chối oan: câu hỏi có ground truth trong corpus nhưng hệ thống lại trả lời từ chối."),
        ("Normalization preservation", "Tỉ lệ con số/số hiệu Điều-Khoản trong câu hỏi gốc còn nguyên sau bước chuẩn hóa bằng Qwen."),
    ]
    for name, desc in metrics:
        b.add("metrics", "silver",
              f"Chỉ số “{name}” trong đồ án đo gì và đọc kết quả thế nào?",
              desc, {"metric": name}, system=SYS_PROJECT)

    # Bài học kỹ thuật / lỗi thật.
    lessons = [
        ("Vì sao phải fold() câu hỏi trước khi gọi EnsembleRetriever?",
         "Vì chunk Tầng 1 được OCR và mất dấu thanh, còn câu hỏi người dùng có dấu. Nếu embed nguyên câu có dấu, vector "
         "bge-m3 của query và chunk lệch nhau; thực nghiệm 15-10 cho thấy query có dấu trả 6 chunk sai nguồn, query đã fold "
         "đưa chunk đúng lên hạng 1. BM25 không bị ảnh hưởng vì bm25_tokenize sinh cả token gốc lẫn token fold."),
        ("Bug REFUSAL_MARKER/fold ở P4.1 là gì?",
         "Trước P4.1, hàm kiểm tra từ chối so REFUSAL_MARKER (còn dấu) với fold(answer) (đã bỏ dấu) nên không bao giờ khớp. "
         "Hệ quả: mọi chỉ số 'từ chối đúng' và 'ảo giác ngoài corpus' của các lượt cũ đều vô nghĩa; baseline '0/3' là artifact "
         "của bug. P4.1 sửa bằng cách fold cả marker."),
        ("Lỗi cache HIT/MISS bất đối xứng (P3.4b) là gì?",
         "Trước P3.4b, nhánh cache HIT trả text trước khi inject trích dẫn, còn MISS trả text sau inject — cùng câu hỏi có thể "
         "ra hai chuỗi khác nhau tùy cache. P3.4b đưa inject_citations_from_metadata thành hậu xử lý dùng chung cho cả HIT và MISS; "
         "câu từ chối chuẩn được giữ nguyên, không gắn trích dẫn."),
        ("Vì sao 429 theo phút thì retry còn 429 PerDay thì dừng?",
         "429 theo phút là giới hạn tạm thời (RPM) — chờ 60 giây rồi thử lại đúng câu, tối đa 3 lần, không đánh mất câu. "
         "429 PerDay là hết quota ngày — chờ tiếp vô ích, nên generator ném lỗi có marker '429 PerDay' để evaluation dừng cả lượt, "
         "giữ nguyên các câu đã chấm và resume hôm sau."),
        ("Resume trong evaluation.py hoạt động thế nào?",
         "load_resumable_entries chỉ nhận lại entry khi file output có cùng benchmark, cùng cờ A/B và đã đủ câu trả lời + điểm judge. "
         "Nhờ vậy chạy lại ĐÚNG lệnh cũ sẽ bỏ qua câu đã chấm (0 request) và chỉ chạy câu thiếu. JSON được flush sau mỗi câu nên "
         "dừng giữa chừng không mất kết quả."),
        ("Vì sao oversampling retrieve_k = 2 × top_k?",
         "Để đo Hit@K trên cửa sổ rộng hơn cửa sổ ngữ cảnh đưa vào generator: bộ truy xuất trả retrieve_k ứng viên, "
         "evaluation đo Hit@retrieve_k, còn generator chỉ nhận top_k đầu. Nhờ vậy không làm phình context mà vẫn đánh giá được recall."),
        ("Ba lớp guardrail của classifier là gì?",
         "Lớp 1: Qwen trả JSON hợp lệ với nhãn chuẩn thì dùng luôn. Lớp 2: JSON lỗi hoặc nhãn lạ thì bổ sung bằng bảng từ khóa "
         "theo chủ đề/loại câu (so khớp không dấu). Lớp 3: từ khóa cũng không khớp thì topic=None, question_type=TRA_CUU; "
         "router hiểu topic=None là không lọc nguồn. Mọi lỗi Ollama đều suy giảm về lớp 3, pipeline không chết."),
        ("Vì sao router KHÔNG bỏ truy xuất với NGOAI_PHAM_VI?",
         "Vì precision của lớp này chỉ 25% ở P2.3 — nhãn sai mà skip truy xuất sẽ từ chối oan câu trả lời được. "
         "Thay vào đó router giữ cấu hình gốc, generator thêm dòng nhắc từ chối chuẩn và cơ chế Soft Refusal xử lý."),
        ("Source filter của router được áp thế nào?",
         "Chỉ 8/14 chủ đề đủ bằng chứng (n≥5 câu trong benchmark v3 và ≥80% câu nằm trong ≤2 nguồn) mới được lọc nguồn. "
         "Nhánh Chroma nhận filter metadata source qua search_kwargs; nhánh BM25 không filter được nên pipeline lọc hậu kiểm theo "
         "metadata sau khi merge, so khớp bằng fold. Nếu filter xóa sạch kết quả, pipeline giữ kết quả chưa lọc và cảnh báo."),
        ("Cache key của generator gồm những gì?",
         "SHA-1 của JSON {model, temperature, prompt_version, prompt}. Đổi model, temperature, prompt hoặc nội dung ngữ cảnh "
         "đều làm key đổi → cache tự vô hiệu, không cần dọn tay. Prompt version hiện là v1.3."),
        ("Vì sao câu trả lời fallback Qwen không được cache?",
         "Để lượt chạy sau còn được thử lại Gemini thật. Nếu cache câu fallback, câu trả lời tạm chất lượng thấp sẽ bị 'đóng băng' "
         "vĩnh viễn trong cache."),
        ("Chunking structure-aware cắt theo đơn vị nào?",
         "Cắt theo cấu trúc văn bản pháp lý: Điều → Khoản → điểm, giữ tiêu đề Điều/Khoản trong chunk và thêm tiền tố phân cấp "
         "(tên văn bản, số Điều) để chunk đứng độc lập vẫn có ngữ cảnh. So với fixed-size, chiến lược này giữ trọn đơn vị quy phạm."),
        ("Vì sao phải chuẩn hóa câu hỏi trước khi truy xuất?",
         "Câu hỏi đời thường có tiếng lóng, viết tắt, sai chính tả làm giảm tương đồng vector với văn bản pháp lý. Local Qwen viết lại "
         "thành câu hỏi học vụ chuẩn, giữ nguyên con số/thực thể. Guardrail token-overlap ≥0.3 và bảo toàn con số chặn Qwen 'drift' "
         "sang chủ đề khác; vi phạm thì dùng nguyên câu gốc."),
        ("Vì sao Q96–Q98 không có ground truth?",
         "Ba câu này cố tình hỏi ngoài phạm vi corpus để đo hành vi từ chối. Chúng có in_corpus=false, expected_answer rỗng, "
         "nên evaluation bỏ qua chấm Hit/Citation/Faithfulness (skipped_no_gt) nhưng vẫn đo xem hệ thống có từ chối hay không."),
        ("Kết quả A/B P4.2 (kịch bản Qwen local) nói gì?",
         "Lượt WITHOUT: Hit@3 60.8%, Hit@5 65.0%, MRR 0.510, Citation F1 13.4%. Lượt WITH: Hit@3 77.3%, Hit@5 78.3%, MRR 0.769, "
         "Citation F1 25.7%. Đây là số liệu thô; phân tích nhân quả chi tiết nằm ở P4.3 (ab_comparison.md), nơi GATE đạt với "
         "Hit@3 tăng 27.1% tương đối."),
        ("Vì sao kịch bản A/B cuối cùng dùng Qwen local thay vì Gemini?",
         "Gemini gemini-3.8-flash bị trần 20 request/ngày (thực tế ~14), không kịp tiến độ; 22 câu Gemini của lượt WITHOUT được "
         "archive thành ab_results_without_classifier_gemini_partial.json. Cả hai lượt Qwen local chạy 100/100 trong ~15 phút, "
         "không tốn quota, cùng một generator nên A/B vẫn công bằng về biến số."),
        ("Vì sao benchmark v3 có 87 TRA_CUU, 5 SO_SANH, 5 THU_TUC, 3 NGOAI_PHAM_VI?",
         "Phân bố phản ánh câu hỏi sinh viên thực tế chủ yếu là tra cứu một thông tin. Các lớp hiếm vẫn được giữ đủ mẫu để đo recall "
         "và huấn luyện few-shot; vì ít mẫu nên mọi so sánh theo lớp hiếm phải đọc kèm n nhỏ."),
        ("Vì sao phải tách truy vấn con cho câu SO_SANH?",
         "Câu so sánh có nhiều vế; một vector query duy nhất dễ chỉ khớp một vế. Tách thành 2–3 truy vấn con, truy xuất từng vế rồi gộp "
         "theo thứ hạng tốt nhất giúp tăng độ phủ. Guardrail 3 điều kiện (số dòng, độ dài, trùng lặp token) đảm bảo tách dở thì quay về "
         "đường đơn."),
        ("Vì sao Qwen 1.5B không được dùng làm generator chính?",
         "Mô hình 1.5B thường không tuân thủ định dạng bảng so sánh, hay echo câu hỏi và bịa khi ngoài phân bố few-shot. Vai trò chính của nó "
         "là chuẩn hóa câu hỏi, phân loại, tách truy vấn con và fallback khi Gemini lỗi — các tác vụ ngắn, có guardrail."),
    ]
    for question, answer in lessons:
        b.add("code_lesson", "silver", question, answer, {}, system=SYS_PROJECT)

    # Câu hỏi vấn đáp đồ án.
    defenses = [
        ("Đồ án giải quyết vấn đề gì?",
         "Xây dựng hệ thống RAG tra cứu quy chế đào tạo AGU cho sinh viên: truy xuất hybrid BM25 + vector, sinh câu trả lời có trích dẫn "
         "Điều/Khoản, chống ảo giác bằng soft refusal, và bổ sung tầng phân loại câu hỏi + router để điều chỉnh truy xuất theo loại câu."),
        ("Vì sao gọi là Hybrid RAG?",
         "Vì truy xuất kết hợp hai nhánh: BM25 (lexical, bắt từ khóa/số hiệu chính xác) và ChromaDB + bge-m3 (semantic, bắt diễn đạt tương đương), "
         "dung hợp bằng Reciprocal Rank Fusion. Hybrid giúp vừa không bỏ sót thuật ngữ pháp lý, vừa hiểu cách diễn đạt đời thường."),
        ("RRF hoạt động thế nào?",
         "Mỗi tài liệu nhận điểm bằng tổng qua các bộ truy xuất của 1/(c + hạng), với c=60. Tài liệu xuất hiện ở hạng cao trong cả hai nhánh "
         "sẽ được cộng điểm và đứng đầu; tài liệu chỉ mạnh ở một nhánh vẫn có cơ hội."),
        ("Tầng phân loại cải thiện hệ thống ở đâu?",
         "Classifier gán chủ đề + loại câu hỏi; router dùng nhãn để chỉnh top_k, trọng số BM25/Chroma, lọc nguồn theo chủ đề và bật tách truy vấn con "
         "cho SO_SANH; generator chọn biến thể prompt theo loại câu. Kết quả A/B cho thấy Hit@3 tăng từ 60.8% lên 77.3% ở kịch bản Qwen local."),
        ("Làm sao chứng minh câu trả lời không bịa?",
         "Ba lớp: prompt cấm dùng kiến thức ngoài ngữ cảnh và buộc trích dẫn; soft refusal khi ngữ cảnh rỗng/không liên quan; đánh giá Faithfulness "
         "bằng LLM judge hoặc heuristic token-overlap, kèm kiểm tra con số trong câu trả lời có xuất hiện trong ngữ cảnh."),
        ("Điểm mạnh và hạn chế của đồ án?",
         "Mạnh: pipeline đầy đủ từ ingest → retrieve → generate → evaluate; guardrail chịu lỗi ở mọi tầng; A/B có kiểm soát biến; tài liệu và test dày. "
         "Hạn chế: corpus Tầng 1 OCR mất dấu; Qwen 1.5B yếu; một số lớp câu hỏi ít mẫu; tầng phân loại precision lớp hiếm chưa cao."),
        ("Nếu được làm lại, bạn thay đổi gì?",
         "Ưu tiên OCR giữ dấu hoặc phục hồi dấu trước khi embed; thêm cross-encoder reranker; tăng mẫu cho SO_SANH/THU_TUC; thay Qwen 1.5B bằng model "
         "3B–7B cho classifier; tự động hóa đánh giá theo từng commit; và tách corpus theo phiên bản văn bản để trích dẫn chính xác hơn."),
    ]
    for question, answer in defenses:
        b.add("defense", "silver", question, answer, {}, system=SYS_TEACHER)


# ---------------------------------------------------------------------------
# Xuất file
# ---------------------------------------------------------------------------
def chat_record(item: Item, idx: int) -> dict:
    return {
        "id": f"{item.task}-{idx:05d}",
        "task": item.task,
        "quality": item.quality,
        "messages": [
            {"role": "system", "content": item.system},
            {"role": "user", "content": item.user},
            {"role": "assistant", "content": item.assistant},
        ],
        "metadata": item.meta,
    }


def alpaca_record(item: Item, idx: int) -> dict:
    return {
        "id": f"{item.task}-{idx:05d}",
        "task": item.task,
        "quality": item.quality,
        "instruction": item.system + "\n\n" + item.user,
        "input": "",
        "output": item.assistant,
        "metadata": item.meta,
    }


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def split_items(items: list[Item], val_percent: int = 3) -> tuple[list[Item], list[Item]]:
    train, val = [], []
    for item in items:
        h = int(sha1_text(item.task + "|" + item.user + "|" + item.assistant)[:8], 16)
        (val if h % 100 < val_percent else train).append(item)
    return train, val


def export(b: DatasetBuilder, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    b.rng.shuffle(b.items)
    b.rng.shuffle(b.classifier)
    b.rng.shuffle(b.classifier_seed)
    b.rng.shuffle(b.retrieval)

    seed_items = [i for i in b.items if i.seed]
    # Mọi mẫu sinh từ benchmark (kể cả normalization/router/grounded_qa) đều nằm trong seed.
    # grounded_refusal là bài tập riêng (ngữ cảnh sai → từ chối), không trộn vào SFT chính.
    # corpus_identification là bài tập phụ trên chunk OCR mất dấu — tách file riêng để
    # không dạy model sinh văn bản hỏng dấu; người dùng muốn trộn thì tự thêm vào.
    aux_tasks = {"grounded_refusal", "corpus_identification"}
    train_pool = [i for i in b.items if not i.seed and i.task not in aux_tasks]
    train, val = split_items(train_pool)
    aux_items = [i for i in b.items if i.task == "corpus_identification"]

    files = {}
    files["sft_benchmark_seed.jsonl"] = write_jsonl(
        out_dir / "sft_benchmark_seed.jsonl",
        (chat_record(i, n) for n, i in enumerate(seed_items)))
    files["sft_benchmark_seed_alpaca.jsonl"] = write_jsonl(
        out_dir / "sft_benchmark_seed_alpaca.jsonl",
        (alpaca_record(i, n) for n, i in enumerate(seed_items)))
    files["sft_train.jsonl"] = write_jsonl(
        out_dir / "sft_train.jsonl", (chat_record(i, n) for n, i in enumerate(train)))
    files["sft_val.jsonl"] = write_jsonl(
        out_dir / "sft_val.jsonl", (chat_record(i, n) for n, i in enumerate(val)))
    files["sft_train_alpaca.jsonl"] = write_jsonl(
        out_dir / "sft_train_alpaca.jsonl", (alpaca_record(i, n) for n, i in enumerate(train)))
    files["sft_val_alpaca.jsonl"] = write_jsonl(
        out_dir / "sft_val_alpaca.jsonl", (alpaca_record(i, n) for n, i in enumerate(val)))

    grounded = [i for i in b.items if i.meta.get("contexts")]
    files["rag_grounded.jsonl"] = write_jsonl(out_dir / "rag_grounded.jsonl", (
        {
            "id": f"rag-{n:05d}",
            "task": i.task,
            "quality": i.quality,
            "split": "benchmark_seed" if i.seed else "train",
            "question": i.user,
            "contexts": i.meta.get("contexts", []),
            "answer": i.assistant,
            "source_document": i.meta.get("source_document"),
            "citations": i.meta.get("citations", []),
            "messages": [
                {"role": "system", "content": i.system},
                {"role": "user", "content": i.user},
                {"role": "assistant", "content": i.assistant},
            ],
        }
        for n, i in enumerate(grounded)))

    refusal_items = [i for i in b.items if i.task in {"refusal", "grounded_refusal"}]
    files["refusal.jsonl"] = write_jsonl(out_dir / "refusal.jsonl", (
        {
            "id": f"refusal-{n:05d}",
            "question": i.user,
            "answer": i.assistant,
            "reason": i.meta.get("reason"),
            "quality": i.quality,
            "benchmark_derived": i.seed,
        }
        for n, i in enumerate(refusal_items)))

    files["retrieval_pairs.jsonl"] = write_jsonl(out_dir / "retrieval_pairs.jsonl", b.retrieval)
    files["classifier_train.jsonl"] = write_jsonl(out_dir / "classifier_train.jsonl", b.classifier)
    files["classifier_benchmark_seed.jsonl"] = write_jsonl(
        out_dir / "classifier_benchmark_seed.jsonl", b.classifier_seed)
    files["corpus_identification.jsonl"] = write_jsonl(
        out_dir / "corpus_identification.jsonl",
        (chat_record(i, n) for n, i in enumerate(aux_items)))

    stats = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files": files,
        "unique_items": len(b.items),
        "train_items": len(train),
        "val_items": len(val),
        "benchmark_seed_items": len(seed_items),
        "grounded_items": len(grounded),
        "refusal_items": len(refusal_items),
        "classifier_train": len(b.classifier),
        "classifier_benchmark_seed": len(b.classifier_seed),
        "retrieval_pairs": len(b.retrieval),
        "corpus_identification_items": len(aux_items),
        "by_task": dict(sorted(Counter(i.task for i in b.items).items())),
        "by_quality": dict(sorted(Counter(i.quality for i in b.items).items())),
        "dedup_skipped": b.skipped_dup,
        "dedup_conflicts": b.skipped_conflict,
        "sources": {
            "benchmark": "data/evaluation/benchmark_100_questions_v3.json",
            "corpus": "chroma_db/chroma.sqlite3 (361 chunk)",
            "code": "AST docstring của src/*.py, main.py, demo_streamlit.py, tests/*.py, .env.example",
            "docs": "README.md, docs/architecture/SYSTEM_ARCHITECTURE.md, docs/spec/TAXONOMY.md, docs/planning/ROADMAP.md, docs/bao_cao/*.md",
        },
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    # Preview 12 mẫu ngẫu nhiên (đủ loại task) để người dùng soi nhanh.
    preview_pool = train[:]
    sample = b.rng.sample(preview_pool, min(12, len(preview_pool)))
    lines = ["# Xem trước dữ liệu huấn luyện", "",
             f"Sinh lúc: {stats['generated_at']} · Tổng mẫu SFT: {len(train)} train + {len(val)} val · "
             f"Seed benchmark: {len(seed_items)} · Classifier: {len(b.classifier)} + {len(b.classifier_seed)} seed · "
             f"Retrieval: {len(b.retrieval)} · Định danh chunk (phụ): {len(aux_items)}", ""]
    for n, item in enumerate(sample, start=1):
        lines += [f"## Mẫu {n} — `{item.task}` ({item.quality})", "",
                  f"**System:** {item.system}", "",
                  f"**User:** {item.user}", "",
                  f"**Assistant:** {item.assistant}", "", "---", ""]
    (out_dir / "preview.md").write_text("\n".join(lines), encoding="utf-8")
    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh dữ liệu huấn luyện từ đồ án Hybrid RAG AGU")
    parser.add_argument("--out", default="data/training", help="thư mục output (mặc định data/training)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    out_dir = ROOT / args.out
    print("Đang nạp corpus từ ChromaDB sqlite...")
    chunks = load_chunks()
    print(f"  {len(chunks)} chunk ({sum(c['clean'] for c in chunks)} còn dấu, "
          f"{sum(not c['clean'] for c in chunks)} OCR mất dấu)")
    bench = load_benchmark()
    print(f"  {len(bench)} câu benchmark v3")

    b = DatasetBuilder(seed=args.seed)
    print("Sinh mẫu benchmark (gold, tách riêng)...")
    build_benchmark(b, bench, chunks)
    print("Sinh mẫu corpus...")
    build_corpus(b, chunks)
    print("Sinh mẫu mã nguồn...")
    build_code(b)
    build_code_index(b)
    print("Sinh mẫu tài liệu...")
    build_docs(b)
    print("Sinh mẫu classifier...")
    build_classifier(b, bench)
    print("Sinh mẫu từ chối...")
    build_refusal(b, bench, chunks)
    print("Sinh cặp truy xuất...")
    build_retrieval(b, chunks, bench)
    print("Sinh tác vụ router/prompt/chỉ số/vấn đáp...")
    build_router_tasks(b, bench)
    build_handcrafted(b)

    print("Xuất file...")
    stats = export(b, out_dir)
    print(json.dumps({k: stats[k] for k in (
        "unique_items", "train_items", "val_items", "benchmark_seed_items",
        "classifier_train", "classifier_benchmark_seed", "retrieval_pairs",
        "dedup_skipped", "dedup_conflicts")}, ensure_ascii=False, indent=2))
    print(f"Xong: {out_dir}")


if __name__ == "__main__":
    main()
