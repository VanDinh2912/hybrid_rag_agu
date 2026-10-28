# -*- coding: utf-8 -*-
"""Unit test cho nhánh USE_QWEN_GENERATOR của main.py (Bước 0, P3.3).

Mock hoàn toàn QwenGenerator/GeminiGenerator — không gọi Ollama hay Gemini thật,
không tốn quota. Mục tiêu: chứng minh main.py đọc cờ đúng ngữ nghĩa như
src/assessment/evaluation.py (=1 → Qwen local kèm cảnh báo OFFLINE; mặc định → Gemini).
"""

import pytest

import main


class FakeQwenGenerator:
    def __init__(self):
        self.model_name = "local-qwen (fake)"
        self.temperature = 0.1


class FakeGeminiGenerator:
    def __init__(self):
        self.model_name = "gemini-fake"
        self.temperature = 0.0


@pytest.fixture()
def fake_engines(monkeypatch):
    """Gắn fake vào cả hai constructor; trả về dict ghi nhận lần gọi."""
    calls = {"qwen": 0, "gemini": 0}

    def fake_qwen():
        calls["qwen"] += 1
        return FakeQwenGenerator()

    def fake_gemini():
        calls["gemini"] += 1
        return FakeGeminiGenerator()

    monkeypatch.setattr(main, "QwenGenerator", fake_qwen)
    monkeypatch.setattr(main, "GeminiGenerator", fake_gemini)
    return calls


class TestUseQwenGeneratorFlag:
    def test_flag_on(self, monkeypatch):
        monkeypatch.setenv("USE_QWEN_GENERATOR", "1")
        assert main.use_qwen_generator() is True

    def test_flag_off_explicit(self, monkeypatch):
        monkeypatch.setenv("USE_QWEN_GENERATOR", "0")
        assert main.use_qwen_generator() is False

    def test_flag_missing_defaults_off(self, monkeypatch):
        monkeypatch.delenv("USE_QWEN_GENERATOR", raising=False)
        assert main.use_qwen_generator() is False


class TestBuildGenerator:
    def test_qwen_branch_uses_qwen_and_warns(self, fake_engines, capsys):
        gen = main.build_generator(use_qwen=True)

        assert isinstance(gen, FakeQwenGenerator)
        assert fake_engines == {"qwen": 1, "gemini": 0}
        out = capsys.readouterr().out
        assert "OFFLINE" in out          # cảnh báo chế độ offline phải lộ rõ
        assert "USE_QWEN_GENERATOR" in out

    def test_gemini_branch_default(self, fake_engines, capsys):
        gen = main.build_generator(use_qwen=False)

        assert isinstance(gen, FakeGeminiGenerator)
        assert fake_engines == {"qwen": 0, "gemini": 1}
        assert "OFFLINE" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# P3.5 — khối "Phân loại & Cấu hình" trong print_result
# ---------------------------------------------------------------------------

def make_result(labels=None, retrieval_config=None, sub_queries=None):
    return {
        "raw_query": "học phí một tín chỉ là bao nhiêu?",
        "normalized_query": "mức thu học phí theo tín chỉ",
        "answer": "Mức thu theo Điều 7 (1059-qd-dhag-2020-09-29.pdf)",
        "sources": [],
        "labels": labels,
        "retrieval_config": retrieval_config,
        "sub_queries": sub_queries,
    }


class TestPrintResultClassifierBlock:
    def test_no_labels_prints_nothing_extra(self, capsys):
        main.print_result(make_result(), 1.0)
        out = capsys.readouterr().out
        assert "[2b]" not in out                      # cờ tắt → output như cũ
        assert "PHÂN LOẠI & CẤU HÌNH" not in out

    def test_labels_block_with_split(self, capsys):
        labels = {"topic": "hoc_phi", "question_type": "SO_SANH"}
        cfg = {
            "top_k": 8,
            "bm25_weight": 0.4,
            "chroma_weight": 0.6,
            "source_filter": ["1059-qd-dhag.pdf"],
            "enable_subquery": True,
        }
        subs = ["mức học phí khối kỹ thuật", "mức học phí khối kinh tế"]
        main.print_result(make_result(labels=labels, retrieval_config=cfg, sub_queries=subs), 1.0)
        out = capsys.readouterr().out
        assert "PHÂN LOẠI & CẤU HÌNH" in out
        assert "hoc_phi" in out
        assert "SO_SANH" in out
        assert "top_k=8" in out
        assert "lọc nguồn: 1059-qd-dhag.pdf" in out
        assert "Tách truy vấn con" in out
        assert "CÓ (2 nhánh)" in out
        assert "(1) mức học phí khối kỹ thuật" in out
        assert "(2) mức học phí khối kinh tế" in out

    def test_labels_block_without_split(self, capsys):
        labels = {"topic": "hoc_phi", "question_type": "TRA_CUU"}
        cfg = {
            "top_k": 6,
            "bm25_weight": 0.5,
            "chroma_weight": 0.5,
            "source_filter": [],
            "enable_subquery": False,
        }
        main.print_result(make_result(labels=labels, retrieval_config=cfg, sub_queries=None), 1.0)
        out = capsys.readouterr().out
        assert "Tách truy vấn con" in out
        assert ": KHÔNG" in out
        assert "Danh sách" not in out
