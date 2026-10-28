"""Unit test cho src/core/pipeline.py — fake 3 tầng dưới, không gọi Ollama/ChromaDB/Gemini."""

import pytest

from src.core.pipeline import HybridRAGPipeline
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

    # normalize_user_query() gọi llm_client.generate(); thiếu method này thì nó rơi
    # xuống nhánh tự tạo ollama.Client và gọi Ollama thật khi chạy test.
    def generate(self, prompt, temperature=0.0):
        return self._normalized


class FakeGenerator:
    def __init__(self):
        self.received_query = None
        self.received_docs = None
        self.received_question_type = None
        self.received_raw_query = None

    def generate_answer(self, query, retrieved_docs, question_type=None, raw_query=None):
        self.received_query = query
        self.received_docs = retrieved_docs
        self.received_question_type = question_type
        self.received_raw_query = raw_query
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

    def test_generator_nhan_ca_cau_hoi_goc_for_rescue(self):
        """P5.12b: `raw_query` xuống generator phải là câu THÔ của sinh viên.

        Lớp cứu từ chối oan (`ENABLE_ANSWER_RESCUE`) xét điều kiện "câu hỏi đòi một giá
        trị cụ thể" trên cả hai văn bản, vì bộ chuẩn hóa Local SLM đôi khi trả về một câu
        khác hẳn (đo: 16/300 lượt sinh ở r0/r1/r3 mất hơn 70% token câu gốc).
        """
        pipeline, _, generator = make_pipeline()
        raw = "sinh viên đóng bảo hiểm y tế bao nhiêu tiền?"
        pipeline.run(raw)
        assert generator.received_raw_query == raw
        assert generator.received_query == NORMALIZED  # prompt không đổi, cache không đổi key


# --- P3.2: tầng phân loại + router qua ENABLE_CLASSIFIER ---------------------

FAKE_LABELS = {"topic": None, "question_type": "TRA_CUU", "raw_response": "raw-mau"}


def install_classifier(monkeypatch, labels=None, exc=None):
    """Gắn fake classify_query vào src.core.pipeline; trả về list ghi nhận các lần gọi."""
    calls = []

    def fake_classify(query):
        calls.append(query)
        if exc is not None:
            raise exc
        return labels if labels is not None else dict(FAKE_LABELS)

    monkeypatch.setattr("src.core.pipeline.classify_query", fake_classify)
    return calls


class TestClassifierFlagDisabled:
    def test_flag_off_classifier_not_called(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "0")
        calls = install_classifier(monkeypatch)
        pipeline, vector_db, _ = make_pipeline()
        result = pipeline.run("diem ren luyen 62 thi sao?")

        assert calls == []  # KHÔNG được gọi classifier
        assert result["labels"] is None
        assert result["retrieval_config"] is None
        # Đường cũ nguyên vẹn: retrieve_k = top_k(4) × oversample(2) = 8.
        _, k = vector_db.received[0]
        assert k == 8

    def test_flag_defaults_to_off(self, monkeypatch):
        monkeypatch.delenv("ENABLE_CLASSIFIER", raising=False)
        calls = install_classifier(monkeypatch)
        pipeline, _, _ = make_pipeline()
        pipeline.run("diem ren luyen 62 thi sao?")
        assert calls == []

    def test_result_has_new_fields_even_when_off(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "0")
        install_classifier(monkeypatch)
        pipeline, _, _ = make_pipeline()
        result = pipeline.run("diem ren luyen 62 thi sao?")
        # 2 trường mới luôn tồn tại (không phá cấu trúc cũ) nhưng = None.
        assert "labels" in result and "retrieval_config" in result
        assert result["labels"] is None
        assert result["retrieval_config"] is None


class TestClassifierFlagEnabled:
    def test_labels_and_config_exposed_in_result(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        calls = install_classifier(monkeypatch)
        pipeline, _, _ = make_pipeline()
        result = pipeline.run("diem ren luyen 62 thi sao?")

        assert calls == ["diem ren luyen 62 thi sao?"]  # classifier nhận câu THÔ
        assert result["labels"] == FAKE_LABELS
        cfg = result["retrieval_config"]
        assert cfg is not None
        assert cfg["top_k"] == 4  # TRA_CUU giữ nguyên base (top_k param mặc định)
        assert cfg["bm25_weight"] == 0.5
        assert cfg["chroma_weight"] == 0.5
        assert cfg["source_filter"] is None
        assert cfg["enable_subquery"] is False

    def test_so_sanh_config_applied_to_oversampling(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        labels = {"topic": None, "question_type": "SO_SANH", "raw_response": ""}
        install_classifier(monkeypatch, labels=labels)
        pipeline, vector_db, _ = make_pipeline()
        result = pipeline.run("diem ren luyen 62 thi sao?")

        # SO_SANH: top_k 4 + 2 = 6 → retrieve_k = 12, bật subquery.
        assert result["retrieval_config"]["top_k"] == 6
        assert result["retrieval_config"]["enable_subquery"] is True
        _, k = vector_db.received[0]
        assert k == 12

    def test_filtered_topic_and_thu_tuc_config(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        labels = {"topic": "học phí", "question_type": "THU_TUC", "raw_response": ""}
        install_classifier(monkeypatch, labels=labels)
        pipeline, vector_db, _ = make_pipeline()
        result = pipeline.run("mien giam hoc phi can giay to gi?")

        cfg = result["retrieval_config"]
        assert cfg["bm25_weight"] == 0.6  # THU_TUC nghiêng về BM25
        assert cfg["chroma_weight"] == 0.4
        assert cfg["source_filter"] is not None
        assert len(cfg["source_filter"]) == 2  # học phí có 2 nguồn
        # THU_TUC không đổi top_k → retrieve_k vẫn 8.
        _, k = vector_db.received[0]
        assert k == 8

    def test_classifier_exception_falls_back(self, monkeypatch, capsys):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        install_classifier(monkeypatch, exc=RuntimeError("qwen chet"))
        pipeline, vector_db, generator = make_pipeline()
        result = pipeline.run("diem ren luyen 62 thi sao?")

        # Lượt hỏi không chết: câu trả lời vẫn có, cấu hình lùi về gốc.
        assert result["answer"] == "answer-mau"
        assert result["labels"] is None
        assert result["retrieval_config"] is None
        _, k = vector_db.received[0]
        assert k == 8  # retrieve_k theo top_k gốc 4 × 2
        assert "[Classifier] Cảnh báo" in capsys.readouterr().out


class FakeChromaSubRetriever:
    """Giả lập sub-retriever Chroma có search_kwargs (để kiểm filter được gán)."""

    def __init__(self):
        self.search_kwargs = {"k": 12}


class FakeEnsemble:
    """Giả lập EnsembleRetriever: trả về docs cố định, có weights/retrievers."""

    def __init__(self, docs):
        self.retrievers = [FakeChromaSubRetriever()]
        self.weights = [0.5, 0.5]
        self._docs = docs
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return list(self._docs)


def make_pipeline_with_ensemble(monkeypatch, docs):
    """Pipeline dùng FakeEnsemble thay vì similarity_search để test nhánh hybrid."""
    monkeypatch.delenv("BM25_WEIGHT", raising=False)
    monkeypatch.delenv("CHROMA_WEIGHT", raising=False)
    monkeypatch.delenv("RAG_TOP_K", raising=False)
    vector_db = FakeVectorDB()
    generator = FakeGenerator()
    ensemble = FakeEnsemble(docs)
    pipeline = HybridRAGPipeline(
        vector_db=vector_db,
        local_slm=FakeLocalSLM(NORMALIZED),
        generator=generator,
        retriever=ensemble,
    )
    return pipeline, ensemble


class TestEnsemblePlumbingWithClassifier:
    DOCS = [
        FakeDoc("chunk s1", {"source": "1059-qd-dhag-2020-09-29.pdf", "chunk_id": 1}),
        FakeDoc("chunk s2", {"source": "888-qd-dhag-2022-08-08.pdf", "chunk_id": 2}),
        FakeDoc("chunk khac", {"source": "other.pdf", "chunk_id": 3}),
    ]

    def test_source_filter_post_filters_docs(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        labels = {"topic": "đánh giá rèn luyện", "question_type": "TRA_CUU", "raw_response": ""}
        install_classifier(monkeypatch, labels=labels)
        pipeline, ensemble = make_pipeline_with_ensemble(monkeypatch, self.DOCS)
        result = pipeline.run("diem ren luyen 62 thi sao?")

        # Chỉ giữ chunk thuộc nguồn được lọc; chunk "khac" bị loại hậu kiểm.
        sources = result["sources"]
        assert len(sources) == 1
        assert sources[0]["source"] == "1059-qd-dhag-2020-09-29.pdf"

    def test_chroma_sub_retriever_gets_filter_kwarg(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        labels = {"topic": "đánh giá rèn luyện", "question_type": "TRA_CUU", "raw_response": ""}
        install_classifier(monkeypatch, labels=labels)
        pipeline, ensemble = make_pipeline_with_ensemble(monkeypatch, self.DOCS)
        pipeline.run("diem ren luyen 62 thi sao?")
        assert ensemble.retrievers[0].search_kwargs.get("filter") == {
            "source": {"$in": ["1059-qd-dhag-2020-09-29.pdf"]}
        }

    def test_thu_tuc_weights_applied_per_query(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        labels = {"topic": None, "question_type": "THU_TUC", "raw_response": ""}
        install_classifier(monkeypatch, labels=labels)
        pipeline, ensemble = make_pipeline_with_ensemble(monkeypatch, self.DOCS)
        pipeline.run("mien giam hoc phi can giay to gi?")
        assert ensemble.weights == [0.6, 0.4]

    def test_flag_off_restores_init_weights_and_no_filter(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLASSIFIER", "0")
        install_classifier(monkeypatch)
        pipeline, ensemble = make_pipeline_with_ensemble(monkeypatch, self.DOCS)
        result = pipeline.run("diem ren luyen 62 thi sao?")

        # Đường cũ: trọng số khởi tạo nguyên vẹn, không filter, không lọc docs.
        assert ensemble.weights == [0.5, 0.5]
        assert "filter" not in ensemble.retrievers[0].search_kwargs
        assert len(result["sources"]) == len(self.DOCS)


class TestSoftSourceFilter:
    """ROUTER_SOFT_FILTER=1: nguồn router chọn được ƯU TIÊN chứ không bị CẮT.

    Bắt buộc có vì vòng lặp đo được 217/308 FAIL_RETRIEVAL do cửa sổ truy xuất
    mất chunk vàng đúng vì phép cắt cứng này.
    """

    DOCS = [
        FakeDoc("chunk khac 1", {"source": "khac-1.pdf", "chunk_id": 3}),
        FakeDoc("chunk s2", {"source": "888-qd-dhag-2022-08-08.pdf", "chunk_id": 2}),
        FakeDoc("chunk s1", {"source": "1059-qd-dhag-2020-09-29.pdf", "chunk_id": 1}),
    ]

    LABELS = {"topic": "đánh giá rèn luyện", "question_type": "TRA_CUU", "raw_response": ""}

    def test_mặc_định_vẫn_cắt_cứng_như_trước(self, monkeypatch):
        monkeypatch.delenv("ROUTER_SOFT_FILTER", raising=False)
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        install_classifier(monkeypatch, labels=self.LABELS)
        pipeline, ensemble = make_pipeline_with_ensemble(monkeypatch, self.DOCS)
        result = pipeline.run("diem ren luyen 62 thi sao?")
        assert [s["chunk_id"] for s in result["sources"]] == [1]

    def test_bật_lọc_mềm_giữ_đủ_cửa_sổ_và_đẩy_nguồn_đúng_lên_đầu(self, monkeypatch):
        monkeypatch.setenv("ROUTER_SOFT_FILTER", "1")
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        install_classifier(monkeypatch, labels=self.LABELS)
        pipeline, ensemble = make_pipeline_with_ensemble(monkeypatch, self.DOCS)
        result = pipeline.run("diem ren luyen 62 thi sao?")

        # Không mất chunk nào; chunk thuộc nguồn router chọn vượt lên trước.
        assert [s["chunk_id"] for s in result["sources"]] == [1, 3, 2]

    def test_lọc_mềm_phải_bỏ_filter_lúc_tìm_trong_chroma(self, monkeypatch):
        """Nếu vẫn gán filter lúc search thì ứng viên ngoài nguồn không bao giờ
        xuất hiện — 'mềm' chỉ còn trên danh nghĩa."""
        monkeypatch.setenv("ROUTER_SOFT_FILTER", "1")
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        install_classifier(monkeypatch, labels=self.LABELS)
        pipeline, ensemble = make_pipeline_with_ensemble(monkeypatch, self.DOCS)
        pipeline.run("diem ren luyen 62 thi sao?")
        assert "filter" not in ensemble.retrievers[0].search_kwargs

    def test_bonus_đổi_được_cường_độ_ưu_tiên(self, monkeypatch):
        monkeypatch.setenv("ROUTER_SOFT_FILTER", "1")
        monkeypatch.setenv("ROUTER_FILTER_RANK_BONUS", "0")
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        install_classifier(monkeypatch, labels=self.LABELS)
        pipeline, ensemble = make_pipeline_with_ensemble(monkeypatch, self.DOCS)
        result = pipeline.run("diem ren luyen 62 thi sao?")

        # bonus=0 => không ưu tiên gì, giữ nguyên thứ tự RRF nhưng vẫn không cắt.
        assert [s["chunk_id"] for s in result["sources"]] == [3, 2, 1]

    def test_hạn_ngạch_nguồn_chừa_suất_cho_nguồn_khac(self, monkeypatch):
        """P5.14: bonus >= cỡ cửa sổ làm MỘT nguồn chiếm trọn cửa sổ — đúng cơ chế r2
        mất 21 item gold@6. ROUTER_SOURCE_QUOTA=1 buộc nguồn được ưu tiên nhả suất."""
        docs = [
            FakeDoc("chunk khac 1", {"source": "khac-1.pdf", "chunk_id": 3}),
            FakeDoc("chunk s2", {"source": "888-qd-dhag-2022-08-08.pdf", "chunk_id": 2}),
            FakeDoc("chunk s1", {"source": "1059-qd-dhag-2020-09-29.pdf", "chunk_id": 1}),
            FakeDoc("chunk s1 lan hai", {"source": "1059-qd-dhag-2020-09-29.pdf", "chunk_id": 4}),
        ]
        monkeypatch.setenv("ROUTER_SOFT_FILTER", "1")
        monkeypatch.setenv("ROUTER_FILTER_RANK_BONUS", "12")
        monkeypatch.delenv("ROUTER_SOURCE_QUOTA", raising=False)
        monkeypatch.setenv("ENABLE_CLASSIFIER", "1")
        install_classifier(monkeypatch, labels=self.LABELS)
        pipeline, _ = make_pipeline_with_ensemble(monkeypatch, docs)
        no_quota = [s["chunk_id"] for s in pipeline.run("diem ren luyen 62 thi sao?")["sources"]]
        assert no_quota == [1, 4, 3, 2]

        monkeypatch.setenv("ROUTER_SOURCE_QUOTA", "1")
        pipeline, _ = make_pipeline_with_ensemble(monkeypatch, docs)
        limited = [s["chunk_id"] for s in pipeline.run("diem ren luyen 62 thi sao?")["sources"]]
        # 1059 chỉ còn 1 suất ở đầu, hai nguồn khác được vào lại, phần hoãn xuống cuối.
        assert limited == [1, 3, 2, 4]


class FakeEnsembleRetriever:
    """Giả lập EnsembleRetriever — chỉ cần có .invoke để pipeline nhận là retriever hybrid."""

    def __init__(self):
        self.received = []

    def invoke(self, query):
        self.received.append(query)
        return [FakeDoc("noi dung chunk mau", {"source": "1054.pdf", "tier": 1, "chunk_id": 0})]


class TestHybridRetrieverReceivesFoldedQuery:
    def test_ensemble_invoke_gets_folded_query(self):
        # Tài liệu Tầng 1 mất dấu thanh vì OCR: Chroma leg cần query đã fold, nếu không
        # truy xuất semantic trượt hẳn sang file khác (bài học thực nghiệm 15-10).
        pipeline, _, _ = make_pipeline()
        retriever = FakeEnsembleRetriever()
        pipeline.ensemble_retriever = retriever

        docs = pipeline.retrieve(NORMALIZED, k=4)

        assert retriever.received == [fold(NORMALIZED)]
        assert docs[0].page_content == "noi dung chunk mau"

    def test_fallback_query_also_folded(self):
        pipeline, _, _ = make_pipeline()
        retriever = FakeEnsembleRetriever()
        pipeline.ensemble_retriever = retriever

        pipeline.retrieve(NORMALIZED, k=4, fallback_query="Cố vấn học tập họp mấy lần?")

        assert retriever.received == [
            fold(NORMALIZED),
            fold("Cố vấn học tập họp mấy lần?"),
        ]


class TestRunGuards:
    def test_blank_question_raises(self):
        pipeline, _, _ = make_pipeline()
        with pytest.raises(ValueError):
            pipeline.run("   ")
