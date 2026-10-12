"""Unit test cho src/pipeline.py — fake 3 tầng dưới, không gọi Ollama/ChromaDB/Gemini."""

import pytest

from src.pipeline import HybridRAGPipeline
from src.text_utils import fold

# Câu chuẩn hóa giả lập từ Qwen (có dấu tiếng Việt) — chỉ dùng hằng này xuyên suốt
# để khỏi lệch chính tả giữa fake SLM và phần assert.
NORMALIZED = "Sinh vien có 62 diem ren luyen duoc xep loai gi?"


class FakeDoc:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


class FakeVectorDB:
    def __init__(self):
        self.received = []  # (query, k) từ mọi lần gọi similarity_search

    def similarity_search(self, query, k):
        self.received.append((query, k))
        return [FakeDoc("noi dung chunk mau", {"source": "1054.pdf", "tier": 1, "chunk_id": 0})]


class FakeLocalSLM:
    def __init__(self, normalized):
        self._normalized = normalized

    def normalize_query(self, raw):
        return self._normalized


class FakeGenerator:
    def __init__(self):
        self.received_query = None

    def generate_answer(self, query, retrieved_docs):
        self.received_query = query
        return "answer-mau"


def make_pipeline(normalized=NORMALIZED):
    vector_db = FakeVectorDB()
    generator = FakeGenerator()
    pipeline = HybridRAGPipeline(
        vector_db=vector_db,
        local_slm=FakeLocalSLM(normalized),
        generator=generator,
    )
    return pipeline, vector_db, generator


class TestRunFoldsQueryBeforeRetrieval:
    def test_similarity_search_receives_folded_query(self):
        # Khi bật mở rộng từ khóa, query gửi xuống vector_db phải là dạng đã fold của expanded query
        pipeline, vector_db, _ = make_pipeline()
        result = pipeline.run("diem ren luyen 62 thi sao?")

        query_sent, k = vector_db.received[0]
        assert query_sent == fold(result["expanded_query"])
        assert query_sent.isascii()  # fold triệt để: không còn dấu tiếng Việt
        # top_k mặc định (4) × oversample_factor (2) = 8 chunk gửi xuống ChromaDB.
        assert k == 8  # oversampling: generator chỉ dùng 4 đầu, retrieval lấy 8

    def test_retrieval_query_exposed_in_result(self):
        pipeline, _, _ = make_pipeline()
        result = pipeline.run("diem ren luyen 62 thi sao?")
        assert result["retrieval_query"] == fold(result["expanded_query"])

    def test_expand_query_disabled(self):
        pipeline, vector_db, _ = make_pipeline()
        pipeline.expand_query = False
        result = pipeline.run("diem ren luyen 62 thi sao?")
        query_sent, _ = vector_db.received[0]
        assert query_sent == fold(NORMALIZED)
        assert result["retrieval_query"] == fold(result["normalized_query"])

    def test_generator_still_gets_normalized_query(self):
        # Chỉ tầng retrieval fold và mở rộng từ khóa; generator nhận câu chuẩn hóa nguyên văn có dấu.
        pipeline, _, generator = make_pipeline()
        pipeline.run("diem ren luyen 62 thi sao?")
        assert generator.received_query == NORMALIZED


class TestRunGuards:
    def test_blank_question_raises(self):
        pipeline, _, _ = make_pipeline()
        with pytest.raises(ValueError):
            pipeline.run("   ")
