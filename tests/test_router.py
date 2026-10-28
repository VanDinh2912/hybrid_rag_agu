"""Unit test cho src/retrieval/router.py — hàm thuần, offline 100%, không gọi model."""

import pytest

from src.core.classifier import TOPICS
from src.retrieval.router import (
    DEFAULT_TOP_K,
    MIN_QUESTIONS_FOR_SOURCE_FILTER,
    SO_SANH_TOP_K_BONUS,
    THU_TUC_BM25_WEIGHT,
    THU_TUC_CHROMA_WEIGHT,
    TOPIC_SOURCE_FILTER,
    RetrievalConfig,
    base_config_from_env,
    get_retrieval_config,
)


@pytest.fixture
def base() -> RetrievalConfig:
    return RetrievalConfig(top_k=4, bm25_weight=0.5, chroma_weight=0.5)


class TestLabelsNoneOrMalformed:
    def test_none_labels_returns_base_values(self, base):
        config = get_retrieval_config(None, base)
        assert config == base

    def test_returns_copy_not_same_object(self, base):
        config = get_retrieval_config(None, base)
        assert config is not base
        config.top_k = 99  # sửa bản sao không được ảnh hưởng base
        assert base.top_k == 4

    @pytest.mark.parametrize("bad_labels", ["SO_SANH", 42, ["SO_SANH"], ("a",)])
    def test_non_dict_labels_returns_base(self, base, bad_labels):
        assert get_retrieval_config(bad_labels, base) == base

    def test_empty_dict_returns_base(self, base):
        assert get_retrieval_config({}, base) == base

    def test_missing_keys_returns_base(self, base):
        assert get_retrieval_config({"confidence": 0.9}, base) == base

    def test_unknown_label_values_fall_back(self, base):
        labels = {"topic": "chủ đề không tồn tại", "question_type": "KHONG_BIET"}
        assert get_retrieval_config(labels, base) == base


class TestQuestionTypeAdjustments:
    def test_tra_cuu_keeps_base(self, base):
        assert get_retrieval_config({"question_type": "TRA_CUU"}, base) == base

    def test_so_sanh_raises_top_k_and_enables_subquery(self, base):
        config = get_retrieval_config({"question_type": "SO_SANH"}, base)
        assert config.top_k == base.top_k + SO_SANH_TOP_K_BONUS
        assert config.enable_subquery is True
        # Các trường còn lại giữ nguyên base.
        assert config.bm25_weight == base.bm25_weight
        assert config.chroma_weight == base.chroma_weight
        assert config.source_filter == base.source_filter

    def test_so_sanh_never_below_base_top_k(self):
        tiny_base = RetrievalConfig(top_k=1, bm25_weight=0.5, chroma_weight=0.5)
        config = get_retrieval_config({"question_type": "SO_SANH"}, tiny_base)
        assert config.top_k >= tiny_base.top_k

    def test_thu_tuc_reweights_bm25_heavier(self, base):
        config = get_retrieval_config({"question_type": "THU_TUC"}, base)
        assert config.bm25_weight == THU_TUC_BM25_WEIGHT
        assert config.chroma_weight == THU_TUC_CHROMA_WEIGHT
        assert config.bm25_weight > config.chroma_weight
        # top_k và subquery không đổi.
        assert config.top_k == base.top_k
        assert config.enable_subquery is False

    def test_ngoai_pham_vi_keeps_base(self, base):
        # NGOAI_PHAM_VI KHÔNG skip truy xuất (quyết định 2026-10-20) — nhắc từ
        # chối là việc tầng generator (P3.4), router giữ nguyên cấu hình gốc.
        config = get_retrieval_config({"question_type": "NGOAI_PHAM_VI"}, base)
        assert config == base

    def test_question_type_case_and_accent_insensitive(self, base):
        config = get_retrieval_config({"question_type": "so sanh"}, base)
        assert config.enable_subquery is True
        config = get_retrieval_config({"question_type": "Thủ Tục"}, base)
        assert config.bm25_weight == THU_TUC_BM25_WEIGHT


class TestTopicSourceFilter:
    @pytest.mark.parametrize(
        "topic",
        ["chương trình đào tạo", "học phí", "cuộc thi chính luận", "đánh giá rèn luyện",
         "khen thưởng sinh viên", "thực tập tốt nghiệp", "quy chế công tác sinh viên",
         "sinh viên 5 tốt"],
    )
    def test_filtered_topics_have_sources(self, base, topic):
        config = get_retrieval_config({"topic": topic}, base)
        assert config.source_filter is not None
        assert config.source_filter == list(TOPIC_SOURCE_FILTER[topic])

    @pytest.mark.parametrize(
        "topic",
        ["bảo hiểm y tế", "hành chính sinh viên", "khen thưởng cấp ĐHQG",
         "ký túc xá", "tài chính sinh viên", "thực tập chuyên đề"],
    )
    def test_small_topics_not_filtered(self, base, topic):
        # 6 chủ đề n=1–3 câu trong benchmark: cố ý không lọc (phòng thủ).
        config = get_retrieval_config({"topic": topic}, base)
        assert config.source_filter is None

    def test_hoc_phi_has_two_sources(self, base):
        config = get_retrieval_config({"topic": "học phí"}, base)
        assert len(config.source_filter) == 2

    def test_topic_none_means_no_filter(self, base):
        config = get_retrieval_config({"topic": None}, base)
        assert config.source_filter is None

    def test_topic_accent_insensitive(self, base):
        config = get_retrieval_config({"topic": "HOC PHI"}, base)
        assert config.source_filter == list(TOPIC_SOURCE_FILTER["học phí"])

    def test_combined_type_and_topic(self, base):
        labels = {"topic": "học phí", "question_type": "SO_SANH"}
        config = get_retrieval_config(labels, base)
        assert config.top_k == base.top_k + SO_SANH_TOP_K_BONUS
        assert config.enable_subquery is True
        assert config.source_filter is not None

    def test_type_adjustment_survives_unknown_topic(self, base):
        labels = {"topic": "xyz", "question_type": "SO_SANH"}
        config = get_retrieval_config(labels, base)
        assert config.enable_subquery is True
        assert config.source_filter is None


class TestSafetyGuards:
    @pytest.mark.parametrize(
        "question_type", [None, "TRA_CUU", "SO_SANH", "THU_TUC", "NGOAI_PHAM_VI"],
    )
    def test_weights_sum_always_positive(self, base, question_type):
        labels = {} if question_type is None else {"question_type": question_type}
        config = get_retrieval_config(labels, base)
        assert config.bm25_weight + config.chroma_weight > 0

    def test_base_isolation_after_adjustment(self, base):
        get_retrieval_config({"question_type": "SO_SANH", "topic": "học phí"}, base)
        assert base.top_k == 4
        assert base.source_filter is None
        assert base.enable_subquery is False


class TestBaseConfigFromEnv:
    def test_defaults_match_current_system(self, monkeypatch):
        monkeypatch.delenv("RAG_TOP_K", raising=False)
        monkeypatch.delenv("BM25_WEIGHT", raising=False)
        monkeypatch.delenv("CHROMA_WEIGHT", raising=False)
        config = base_config_from_env()
        assert config.top_k == DEFAULT_TOP_K
        assert config.bm25_weight == 0.5
        assert config.chroma_weight == 0.5
        assert config.source_filter is None
        assert config.enable_subquery is False

    def test_reads_env_values(self, monkeypatch):
        monkeypatch.setenv("RAG_TOP_K", "6")
        monkeypatch.setenv("BM25_WEIGHT", "0.7")
        monkeypatch.setenv("CHROMA_WEIGHT", "0.3")
        config = base_config_from_env()
        assert config.top_k == 6
        assert config.bm25_weight == 0.7
        assert config.chroma_weight == 0.3

    @pytest.mark.parametrize("bad", ["abc", "0", "-3"])
    def test_invalid_env_falls_back(self, monkeypatch, bad):
        monkeypatch.setenv("RAG_TOP_K", bad)
        assert base_config_from_env().top_k == DEFAULT_TOP_K


class TestFilterTableIntegrity:
    def test_filtered_topics_are_canonical(self):
        for topic in TOPIC_SOURCE_FILTER:
            assert topic in TOPICS

    def test_filtered_topics_have_min_evidence(self):
        # Không thể tái kiểm tra số câu trong benchmark ở đây (bảng ghi cứng
        # theo quyết định thiết kế), nhưng bảng phải khớp danh sách 8 chủ đề
        # đã chốt với ngướng MIN_QUESTIONS_FOR_SOURCE_FILTER = 5.
        assert len(TOPIC_SOURCE_FILTER) == 8
        assert MIN_QUESTIONS_FOR_SOURCE_FILTER == 5

    def test_sources_are_nonempty_strings(self):
        for topic, sources in TOPIC_SOURCE_FILTER.items():
            assert len(sources) >= 1
            for source in sources:
                assert isinstance(source, str) and source.strip()
