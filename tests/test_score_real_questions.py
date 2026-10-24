# -*- coding: utf-8 -*-
"""Test khung T6c (score_real_questions) — KHÔNG gọi model.

Chứng minh ba thứ ghép đúng: `score_one` chấm grounding + phát hiện từ chối trên pipeline
giả lập; `help_rate_ci` trả CI trên nhãn tay; `summarize` đếm đúng số câu đã được người đọc
điền. Nhờ stub, test chạy tức thì, không nạp Ollama/Chroma.
"""

from src.generator import REFUSAL_TEXT
from tools.eval import score_real_questions as rq


class StubPipeline:
    def __init__(self, answer, contexts):
        self._answer = answer
        self._contexts = contexts

    def run(self, question, top_k=6):
        return {
            "answer": self._answer,
            "contexts": self._contexts,
            "sources": [{"source": "quy-che.pdf", "chunk_id": "1", "rank": 1}],
        }


def test_score_one_grounded_not_refusal():
    row = {"id": "RQ-1", "question": "Trường có khoa Công nghệ thông tin không?"}
    pipe = StubPipeline(
        answer="Có, trường có khoa Công nghệ thông tin.",
        contexts=["Trường có khoa Công nghệ thông tin đào tạo cử nhân."],
    )
    out = rq.score_one(pipe, row, top_k=6)
    assert out["is_refusal"] is False
    assert out["grounding_score"] is not None and out["grounding_score"] >= 0.5
    assert out["co_giup_duoc_khong"] == ""  # cột người đọc giữ trống cho người điền


def test_score_one_detects_refusal():
    row = {"id": "RQ-2", "question": "Mật khẩu wifi thư viện là gì?"}
    pipe = StubPipeline(answer=REFUSAL_TEXT, contexts=["Tài liệu chỉ nói về quy chế đào tạo."])
    out = rq.score_one(pipe, row, top_k=6)
    assert out["is_refusal"] is True
    assert out["grounding_score"] is None  # câu từ chối không có khẳng định kiểm được


def test_preserves_existing_human_label():
    row = {"id": "RQ-3", "question": "Có A không?", "co_giup_duoc_khong": "co", "ghi_chu": "ok"}
    out = rq.score_one(StubPipeline("Có A.", ["A ở đây."]), row, top_k=6)
    assert out["co_giup_duoc_khong"] == "co"
    assert out["ghi_chu"] == "ok"


def test_help_rate_ci_counts_and_bounds():
    ci = rq.help_rate_ci([1.0, 0.0, 0.5, 1.0])
    assert ci["n"] == 4
    assert ci["mean"] == 0.625
    lo, hi = ci["ci95"]
    assert lo <= 0.625 <= hi
    assert "CI RỘNG" in ci["note"]


def test_summarize_counts_labeled_rows():
    scored = [
        {"is_refusal": False, "grounding_score": 1.0, "n_unsupported": 0, "co_giup_duoc_khong": "co"},
        {"is_refusal": True, "grounding_score": None, "n_unsupported": 0, "co_giup_duoc_khong": "khong"},
        {"is_refusal": False, "grounding_score": 0.5, "n_unsupported": 1, "co_giup_duoc_khong": ""},
    ]
    s = rq.summarize(scored)
    assert s["n_scored"] == 3
    assert s["n_human_labeled"] == 2
    assert s["refusals"] == 1
    assert s["n_fabricated_any"] == 1
    assert s["help_rating"]["n"] == 2  # chỉ 2 dòng có nhãn tay hợp lệ


def test_real_questions_filters_examples_and_blanks():
    rows = [
        {"id": "e", "question": "ví dụ", "example": True},
        {"id": "b", "question": "   "},
        {"id": "r", "question": "câu thật"},
    ]
    got = rq.real_questions(rows, include_examples=False)
    assert [g["id"] for g in got] == ["r"]
    got2 = rq.real_questions(rows, include_examples=True)
    assert "e" in [g["id"] for g in got2]
