# -*- coding: utf-8 -*-
"""Unit test cho tầng tách truy vấn con SO_SANH (P3.3).

Offline hoàn toàn: fake llm_client cho split_comparison_query; fake Ensemble
+ classifier cho pipeline. Không gọi Ollama/ChromaDB/Gemini, không tốn quota.
"""

import pytest

from src.pipeline import HybridRAGPipeline
from src.retrieval import (
    _clean_subquery_lines,
    _pairwise_overlap_too_high,
    split_comparison_query,
)
from src.text_utils import fold

QUERY_GOC = "So sánh mức học phí khối kỹ thuật và khối kinh tế năm 2026-2027?"


class FakeSplitLLM:
    """Fake llm_client: generate() trả text cố định hoặc ném lỗi."""

    def __init__(self, text=None, exc=None):
        self._text = text
        self._exc = exc
        self.prompts = []

    def generate(self, prompt, temperature=0.0, num_predict=None):
        self.prompts.append(prompt)
        if self._exc is not None:
            raise self._exc
        return self._text or ""


# ---------------------------------------------------------------------------
# split_comparison_query: tách hợp lệ
# ---------------------------------------------------------------------------

class TestSplitValid:
    def test_two_lines_parsed(self):
        llm = FakeSplitLLM("Mức học phí khối kỹ thuật năm 2026-2027?\nMức học phí khối kinh tế năm 2026-2027?")
        result = split_comparison_query(QUERY_GOC, llm_client=llm)
        assert result == [
            "Mức học phí khối kỹ thuật năm 2026-2027?",
            "Mức học phí khối kinh tế năm 2026-2027?",
        ]

    def test_three_lines_with_bullets_and_numbers(self):
        text = (
            "1. Chuẩn đầu ra ELO 6 quy định gì?\n"
            "2) Chuẩn đầu ra ELO 7 quy định gì?\n"
            "- Chuẩn đầu ra ELO 8 quy định gì?"
        )
        result = split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM(text))
        assert len(result) == 3
        assert all(not r.startswith(("1", "2", "-")) for r in result)
        assert all("ELO" in r for r in result)

    def test_blank_lines_and_quotes_are_cleaned(self):
        text = '\n"Mức học phí khối kỹ thuật?"\n\n\n"Mức học phí khối kinh tế?"\n'
        result = split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM(text))
        assert result == ["Mức học phí khối kỹ thuật?", "Mức học phí khối kinh tế?"]


# ---------------------------------------------------------------------------
# split_comparison_query: guardrail suy giảm về [query]
# ---------------------------------------------------------------------------

class TestSplitGuardrail:
    def test_single_line_returns_original(self, capsys):
        result = split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM("Chỉ một dòng duy nhất?"))
        assert result == [QUERY_GOC]
        assert "Guardrail" in capsys.readouterr().out

    def test_four_lines_returns_original(self):
        text = "Vế một?\nVế hai?\nVế ba?\nVế bốn?"
        assert split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM(text)) == [QUERY_GOC]

    def test_empty_output_returns_original(self):
        assert split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM("")) == [QUERY_GOC]
        assert split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM(None)) == [QUERY_GOC]

    def test_identical_lines_are_rejected(self):
        # Qwen tách dở: nhân bản cùng một dòng → overlap 100% → không tách.
        text = "Mức học phí khối kỹ thuật năm 2026-2027?\nMức học phí khối kỹ thuật năm 2026-2027?"
        assert split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM(text)) == [QUERY_GOC]

    def test_near_duplicate_lines_are_rejected(self):
        # Qwen tách dở: hai dòng chỉ khác từ đệm (Jaccard ~0.88 > 0.8) → không tách.
        # Ngược lại cặp ELO "khác nhau đúng 1 token thực thể" (Jaccard ~0.78) vẫn được qua.
        text = (
            "Sinh viên nợ học phí có được dự thi không?\n"
            "Sinh viên nợ học phí có được dự thi không vậy ạ?"
        )
        assert split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM(text)) == [QUERY_GOC]

    def test_entity_differing_lines_are_kept(self):
        # QUYẾT ĐỊNH THIẾT KẾ (P3.3): câu hỏi ELO-đa-thực-thể là SO_SANH hợp lệ chủ lực;
        # guardrail Jaccard không được loại nó (regression test cho metric Jaccard).
        text = (
            "Chuẩn đầu ra ELO 6 quy định những kiến thức nào?\n"
            "Chuẩn đầu ra ELO 7 quy định những kiến thức nào?\n"
            "Chuẩn đầu ra ELO 8 quy định những kiến thức nào?"
        )
        result = split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM(text))
        assert len(result) == 3

    def test_too_long_subquery_rejected(self):
        long_line = "Học phí " + "rất " * 60 + "là bao nhiêu?"
        text = f"{long_line}\nVế còn lại?"
        assert split_comparison_query(QUERY_GOC, llm_client=FakeSplitLLM(text)) == [QUERY_GOC]

    def test_llm_error_returns_original(self, capsys):
        llm = FakeSplitLLM(exc=RuntimeError("ollama chet"))
        result = split_comparison_query(QUERY_GOC, llm_client=llm)
        assert result == [QUERY_GOC]
        assert "[SubQuery] Cảnh báo" in capsys.readouterr().out

    def test_non_string_input_safe(self):
        assert split_comparison_query(None) == []
        assert split_comparison_query(123) == ["123"]


# ---------------------------------------------------------------------------
# Hàm phụ trợ
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_clean_subquery_lines_strips_bullets(self):
        assert _clean_subquery_lines("1. A?\n- B?\n(2) C?") == ["A?", "B?", "C?"]

    def test_pairwise_overlap_same_numbers_filler_rejected(self):
        # Cùng tập số, Jaccard token phi-số = 11/13 ≈ 0.85 > 0.8 → chỉ khác từ đệm → loại.
        a = "sinh viên nợ học phí năm 2026 có được dự thi không"
        b = "sinh viên nợ học phí năm 2026 có được dự thi không vậy ạ"
        assert _pairwise_overlap_too_high([a, b]) is True

    def test_pairwise_overlap_same_numbers_real_diff_kept(self):
        # Cùng tập số nhưng Jaccard = 7/10 = 0.7 ≤ 0.8 → khác nội dung thật → giữ.
        a = "mức học phí khối kỹ thuật năm 2026"
        b = "mức học phí khối kỹ thuật và khối kinh tế năm 2026"
        assert _pairwise_overlap_too_high([a, b]) is False

    def test_pairwise_overlap_entity_diff_kept(self):
        # Khác tập số (ELO 6 vs ELO 7) → Jaccard nội dung bị bỏ qua → giữ (SO_SANH hợp lệ).
        a = "chuẩn đầu ra ELO 6 quy định những kiến thức nào"
        b = "chuẩn đầu ra ELO 7 quy định những kiến thức nào"
        assert _pairwise_overlap_too_high([a, b]) is False


# ---------------------------------------------------------------------------
# Pipeline: nhánh SO_SANH với sub-query (fake ensemble đa nhánh)
# ---------------------------------------------------------------------------

NORMALIZED = "So sanh muc hoc phi khoi ky thuat va khoi kinh te nam 2026-2027?"
SUB_1 = "Mức học phí khối kỹ thuật năm 2026-2027?"
SUB_2 = "Mức học phí khối kinh tế năm 2026-2027?"
SPLIT_OUTPUT = f"{SUB_1}\n{SUB_2}"


class FakeDoc:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


class FakeVectorDB:
    def similarity_search(self, query, k):
        return [FakeDoc("chunk mau", {"source": "s.pdf", "tier": 1, "chunk_id": 0})]


class FakeSLM:
    """Trả normalized cho prompt chuẩn hóa, trả split output cho prompt tách."""

    def __init__(self, split_text=SPLIT_OUTPUT, split_exc=None):
        self._split_text = split_text
        self._split_exc = split_exc
        self.split_prompts = []

    def normalize_query(self, raw_query):
        return NORMALIZED

    def generate(self, prompt, temperature=0.0, num_predict=None):
        # Prompt tách chứa 'tách' (đã fold) ở mọi vị trí; prompt chuẩn hóa thì không.
        if "tach" in fold(prompt):
            self.split_prompts.append(prompt)
            if self._split_exc is not None:
                raise self._split_exc
            return self._split_text
        return NORMALIZED

    def check_connection(self):
        return True, "fake"


class FakeGenerator:
    def __init__(self):
        self.received_docs = None
        self.received_question_type = None

    def generate_answer(self, query, retrieved_docs, question_type=None):
        self.received_docs = retrieved_docs
        self.received_question_type = question_type
        return "answer-mau"


class FakeEnsembleMulti:
    """Trả danh sách docs khác nhau theo thứ tự invoke; ghi lại mọi query."""

    def __init__(self, responses):
        self._responses = [list(r) for r in responses]
        self.weights = [0.5, 0.5]
        self.retrievers = []
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        idx = min(len(self.queries) - 1, len(self._responses) - 1)
        return list(self._responses[idx])


def install_classifier(monkeypatch, labels):
    def fake_classify(query):
        return labels

    monkeypatch.setattr("src.pipeline.classify_query", fake_classify)


def make_so_sanh_pipeline(monkeypatch, ensemble, slm=None):
    monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
    monkeypatch.delenv("BM25_WEIGHT", raising=False)
    monkeypatch.delenv("CHROMA_WEIGHT", raising=False)
    monkeypatch.delenv("RAG_TOP_K", raising=False)
    labels = {"topic": "học phí", "question_type": "SO_SANH", "raw_response": ""}
    install_classifier(monkeypatch, labels)
    generator = FakeGenerator()
    pipeline = HybridRAGPipeline(
        vector_db=FakeVectorDB(),
        local_slm=slm or FakeSLM(),
        generator=generator,
        retriever=ensemble,
    )
    return pipeline, generator


class TestPipelineSubQueryBranch:
    def test_two_branches_invoked_and_merged(self, monkeypatch):
        doc_a1 = FakeDoc("A1", {"source": "hoc-phi.pdf", "chunk_id": 1})
        doc_x = FakeDoc("X", {"source": "hoc-phi.pdf", "chunk_id": 2})
        doc_a1_dup = FakeDoc("A1-nhánh-2", {"source": "hoc-phi.pdf", "chunk_id": 1})
        doc_b1 = FakeDoc("B1", {"source": "hoc-phi.pdf", "chunk_id": 3})
        ensemble = FakeEnsembleMulti([
            [doc_a1, doc_x],        # nhánh sub 1: chunk 1 rank 0, chunk 2 rank 1
            [doc_b1, doc_a1_dup],   # nhánh sub 2: chunk 3 rank 0, chunk 1 (dup) rank 1
        ])
        pipeline, generator = make_so_sanh_pipeline(monkeypatch, ensemble)

        result = pipeline.run(QUERY_GOC, top_k=4)

        # P3.4: nhãn SO_SANH được truyền xuống generator để chọn biến thể prompt.
        assert generator.received_question_type == "SO_SANH"

        # retrieve_k = (4+2) * 2 = 12; 2 nhánh được gọi, không dùng fallback_query.
        assert len(ensemble.queries) == 2
        # Gộp: chunk_id=1 xuất hiện ĐÚNG 1 lần (dedup), tổng 3 chunk.
        chunk_ids = [s["chunk_id"] for s in result["sources"]]
        assert sorted(chunk_ids) == [1, 2, 3]
        # Best-rank: chunk 1 đứng đầu (rank 0 ở nhánh 1 — dù nhánh 2 cũng rank 0,
        # branch đầu thắng); chunk 3 (rank 0 nhánh 2) đứng trước chunk 2 (rank 1 nhánh 1).
        assert chunk_ids == [1, 3, 2]
        # sub_queries lộ ra ngoài result.
        assert result["sub_queries"] == [SUB_1, SUB_2]
        # Cửa sổ generator = effective_top_k = 6 (SO_SANH +2), nhưng chỉ có 3
        # chunk duy nhất sau dedup → generator nhận đúng 3, không phình.
        assert len(result["contexts"]) == 3
        assert generator.received_docs is not None
        assert len(generator.received_docs) == 3

    def test_window_cut_to_retrieve_k(self, monkeypatch):
        # 3 nhánh × 5 chunk phân biệt = 15 chunk; retrieve_k = (4+2) × 2 = 12
        # → merged phải bị cắt còn ĐÚNG 12 (cửa sổ oversampled), gen nhận 6.
        docs = [[FakeDoc(f"b{bi}-{i}", {"source": "s.pdf", "chunk_id": bi * 10 + i})
                 for i in range(5)] for bi in range(3)]
        ensemble = FakeEnsembleMulti(docs)
        slm = FakeSLM(split_text="Vế một?\nVế hai?\nVế ba?")
        pipeline, _ = make_so_sanh_pipeline(monkeypatch, ensemble, slm=slm)

        result = pipeline.run(QUERY_GOC, top_k=4)

        assert len(result["sources"]) == 12  # đúng cửa sổ oversampled
        assert len(result["contexts"]) == 6  # effective_top_k = 4 + 2

    def test_guardrail_falls_back_to_single_path(self, monkeypatch, capsys):
        # Split trả 1 dòng → guardrail → đường đơn với fallback_query như cũ.
        ensemble = FakeEnsembleMulti([[FakeDoc("m", {"source": "s.pdf", "chunk_id": 0})]])
        slm = FakeSLM(split_text="Chỉ một dòng?")
        pipeline, _ = make_so_sanh_pipeline(monkeypatch, ensemble, slm=slm)

        result = pipeline.run(QUERY_GOC, top_k=4)

        # 2 invoke: query chính + fallback_query (đường đơn), không phải 2 nhánh.
        assert len(ensemble.queries) == 2
        assert ensemble.queries[0] == fold(result["expanded_query"])
        assert ensemble.queries[1] == fold(QUERY_GOC)
        assert result["sub_queries"] is None
        assert "Guardrail" in capsys.readouterr().out

    def test_split_exception_falls_back_to_single_path(self, monkeypatch, capsys):
        ensemble = FakeEnsembleMulti([[FakeDoc("m", {"source": "s.pdf", "chunk_id": 0})]])
        slm = FakeSLM(split_exc=RuntimeError("qwen chet"))
        pipeline, _ = make_so_sanh_pipeline(monkeypatch, ensemble, slm=slm)

        result = pipeline.run(QUERY_GOC, top_k=4)

        assert result["answer"] == "answer-mau"     # lượt hỏi không chết
        assert result["sub_queries"] is None
        assert len(ensemble.queries) == 2           # đường đơn + fallback
        assert "[SubQuery] Cảnh báo" in capsys.readouterr().out

    def test_tra_cuu_label_never_splits(self, monkeypatch):
        # Câu TRA_CUU (kể cả bị gán nhầm sau này) không bao giờ vào nhánh tách
        # vì điều kiện enable_subquery=False trong config TRA_CUU.
        ensemble = FakeEnsembleMulti([[FakeDoc("m", {"source": "s.pdf", "chunk_id": 0})]])
        slm = FakeSLM()
        pipeline, generator = make_so_sanh_pipeline(monkeypatch, ensemble, slm=slm)
        # Ghi đè nhãn thành TRA_CUU.
        install_classifier(monkeypatch, {"topic": None, "question_type": "TRA_CUU", "raw_response": ""})

        result = pipeline.run("diem ren luyen 62 thi sao?", top_k=4)

        assert slm.split_prompts == []              # không gọi tầng tách
        assert result["sub_queries"] is None
        assert result["retrieval_config"]["enable_subquery"] is False
        # P3.4: nhãn TRA_CUU vẫn truyền xuống generator (chọn PROMPT_RULES gốc).
        assert generator.received_question_type == "TRA_CUU"

    def test_flag_off_no_split(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "0")
        ensemble = FakeEnsembleMulti([[FakeDoc("m", {"source": "s.pdf", "chunk_id": 0})]])
        slm = FakeSLM()
        generator = FakeGenerator()
        pipeline = HybridRAGPipeline(
            vector_db=FakeVectorDB(),
            local_slm=slm,
            generator=generator,
            retriever=ensemble,
        )
        result = pipeline.run(QUERY_GOC, top_k=4)

        assert slm.split_prompts == []
        assert result["sub_queries"] is None
        assert len(ensemble.queries) == 2
        # P3.4: classifier tắt → question_type None → prompt gốc (cache cũ còn trúng).
        assert generator.received_question_type is None
