"""Test đòn bẩy T3 #3 — `ENABLE_EVIDENCE_SELECTION` (extract-then-generate).

Nghĩa vụ như mọi lever của vòng lặp P5: cờ TẮT thì cửa sổ generator và log không đổi một
byte; cờ BẬT thì chỉ làm đúng việc đã đăng ký trong `data/loop/README.md` (mục T3) — chọn
3–5 CÂU bằng chứng, không đủ chuẩn thì GIỮ NGUYÊN cửa sổ.
"""

import importlib

import pytest

from src.generation.evidence_selection import (
    Reranker,
    TIER_KEYWORDS,
    TIER_SOURCE_NAME,
    evidence_selection_enabled,
    get_reranker,
    min_keyword_hits,
    question_terms,
    rank_candidates,
    reranker_status,
    select_evidence,
    sentence_budget,
    split_sentences,
    source_name_keys,
)

QUESTION = "Sinh viên học lại tối đa bao nhiêu lần mỗi học phần?"

# Các câu DƯỚI ĐÂY phải là đúng đơn vị mà `split_sentences` sinh ra (tách sau `. ; :`),
# vì đó là đơn vị mà đòn bẩy thao tác — không phải "câu" theo cảm tính.
S1 = "Sinh viên được phép đăng ký học lại tối đa 2 lần cho mỗi học phần không đạt."
S2 = "Học phí học kỳ được tính theo số tín chỉ đăng ký và nộp tại phòng tài chính trước ngày 15."
S3 = "Sinh viên thuộc diện học lại phải đăng ký trên hệ thống trong tuần đầu của học kỳ."
S4 = "Văn bản này do Trường Đại học An Giang ban hành áp dụng cho các khóa đại học hệ chính quy."
S5 = "Giảng viên bộ môn gửi bảng điểm về phòng đào tạo sau khi kết thúc học phần được ba ngày."

DOC_A = {
    "page_content": " ".join([S1, S2, S3, S4]),
    "metadata": {"source": "quy-che-dao-tai-1054-qd-dhag-2020-09-29.pdf", "tier": 1, "chunk_id": 11},
}
DOC_B = {
    "page_content": " ".join([S5, S2, S3]),
    "metadata": {"source": "khac-2021.pdf", "tier": 2, "chunk_id": 22},
}


class Doc:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


def docs():
    return [Doc(DOC_A["page_content"], dict(DOC_A["metadata"])), Doc(DOC_B["page_content"], dict(DOC_B["metadata"]))]


@pytest.fixture(autouse=True)
def _no_model_downloads(monkeypatch):
    """Test không được tải model thật (hàng GB) — chặn CrossEncoder và reset cache module."""
    import sys
    import types

    import src.generation.evidence_selection as es

    broken = types.ModuleType("sentence_transformers")

    def _boom(*a, **k):
        raise RuntimeError("test môi trường: cấm tải model")

    broken.CrossEncoder = _boom
    monkeypatch.setitem(sys.modules, "sentence_transformers", broken)
    es._RERANKER = None
    yield
    es._RERANKER = None


# --------------------------------------------------------------------------------- cờ
def test_flag_default_off(monkeypatch):
    monkeypatch.delenv("ENABLE_EVIDENCE_SELECTION", raising=False)
    assert evidence_selection_enabled() is False
    for value in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("ENABLE_EVIDENCE_SELECTION", value)
        assert evidence_selection_enabled() is False
    monkeypatch.setenv("ENABLE_EVIDENCE_SELECTION", "1")
    assert evidence_selection_enabled() is True


def test_budget_defaults_and_guard_against_nonsense(monkeypatch):
    monkeypatch.delenv("EV_MIN_SENTENCES", raising=False)
    monkeypatch.delenv("EV_MAX_SENTENCES", raising=False)
    assert sentence_budget() == (3, 5)
    monkeypatch.setenv("EV_MIN_SENTENCES", "9")
    monkeypatch.setenv("EV_MAX_SENTENCES", "2")  # max < min => kẹp về mặc định đã đăng ký
    assert sentence_budget() == (3, 5)


# ------------------------------------------------------------------ luật chia câu
def test_sentence_law_matches_testset():
    """Câu của module PHẢI là câu của trọng tài, nếu không phép đo mất nghĩa."""
    from tools.loop.testset import sentence_split

    for text in (DOC_A["page_content"], S1, "a. b.", "only short", "Dài. " * 20):
        assert split_sentences(text) == sentence_split(text)


# ------------------------------------------------------------------ ranking deterministic
def test_tier_priority_entity_over_keywords_over_source_name():
    cands = rank_candidates(QUESTION, docs(), [DOC_A["metadata"]["source"]])
    by_sentence = {c.sentence: c for c in cands}
    assert by_sentence[S1].tier == TIER_KEYWORDS  # chia sẻ >=2 từ khóa với câu hỏi
    assert by_sentence[S1].keyword_hits >= 2
    assert cands[0].tier >= TIER_KEYWORDS  # câu đứng đầu phải là câu liên quan
    # câu lạc đề triệt để (không một từ khóa nào của câu hỏi) phải rơi xuống tier thấp
    off_topic = [Doc(S5 + " " + S2, {"chunk_id": 99, "source": "tap-chi.pdf"})]
    weak = rank_candidates("Mã số thuế của doanh nghiệp là bao nhiêu?", off_topic, [])
    assert all(c.tier <= TIER_SOURCE_NAME for c in weak)


def test_ranking_is_stable_without_reranker():
    """Không có reranker thì thứ tự vẫn cố định: tier, rồi hạng chunk, rồi vị trí câu."""
    first = [c.sentence for c in rank_candidates(QUESTION, docs(), [])]
    second = [c.sentence for c in rank_candidates(QUESTION, docs(), [])]
    assert first == second


def test_source_name_keys_ignore_short_tokens():
    keys = source_name_keys(["quy-che-dao-tai-1054-qd-dhag-2020-09-29.pdf", "a4.pdf"])
    assert "1054" in keys and "2020" in keys  # số hiệu văn bản: tín hiệu mạnh nhất của tên nguồn
    assert "quy" not in keys and "tai" not in keys  # mảnh 3 ký tự: khớp loạn, bị loại
    assert "quy-che-dao-tai-1054-qd-dhag-2020-09-29" in keys  # cả tên (fold giữ dấu gạch nối)
    assert "" not in keys


def test_question_terms_keeps_nouns_and_drops_function_words():
    terms = question_terms(QUESTION)
    assert {"hoc", "vien", "phan"} <= terms
    assert not ({"va", "cua", "bao", "nhieu", "moi"} & terms)
    assert question_terms("") == set()


# --------------------------------------------------------------------------- select
def test_keeps_original_window_when_too_few_sentences(monkeypatch):
    monkeypatch.delenv("EV_MIN_SENTENCES", raising=False)
    lonely = [Doc("Văn bản chỉ có một câu duy nhất nói về học phí và dates.", {"chunk_id": 1, "source": "x.pdf"})]
    window, info = select_evidence(QUESTION, lonely, source_names=["y.pdf"])
    assert info["applied"] is False
    assert info["reason"] == "not_enough_qualifying_sentences"
    assert window == lonely  # đúng những object cửa sổ gốc — không copy, không dựng lại


def test_min_keyword_hits_env_override(monkeypatch):
    monkeypatch.delenv("EV_MIN_KEYWORD_HITS", raising=False)
    assert min_keyword_hits() == 2
    monkeypatch.setenv("EV_MIN_KEYWORD_HITS", "4")
    assert min_keyword_hits() == 4
    monkeypatch.setenv("EV_MIN_KEYWORD_HITS", "0")  # 0/âm => kẹp về mặc định đã đăng ký
    assert min_keyword_hits() == 2


def test_applies_when_enough_sentences_and_preserves_metadata():
    window, info = select_evidence(QUESTION, docs(), source_names=[DOC_A["metadata"]["source"]])
    assert info["applied"] is True
    assert 3 <= info["n_sentences"] <= 5
    assert info["chars_after"] < info["chars_before"]
    originals = [d.metadata for d in docs()]
    for new in window:
        assert new.metadata in originals  # chunk_id/source/tier còn nguyên cho trích dẫn
    text = " ".join(d.page_content for d in window)
    assert S1 in text  # câu chia nhiều từ khóa nhất với câu hỏi phải được giữ


def test_never_adds_text():
    """Văn bản đầu ra là tập con các câu đã cắt từ cửa sổ — không tự chế câu mới."""
    window, info = select_evidence(QUESTION, docs(), source_names=[])
    if not info["applied"]:
        pytest.skip("cửa sổ fixture không đủ câu đạt chuẩn")
    originals = set()
    for d in docs():
        originals.update(split_sentences(d.page_content))
    for d in window:
        for s in split_sentences(d.page_content):
            assert s in originals


def test_sentences_keep_reading_order_within_a_chunk():
    """Cắt câu không được đảo thứ tự đọc trong cùng một chunk (model mất mạch nếu đảo)."""
    original = " ".join([S1, S3, S4, S2])
    window, info = select_evidence(QUESTION, [Doc(original, DOC_A["metadata"])], source_names=[])
    if not info["applied"]:
        pytest.skip("không đủ câu đạt chuẩn")
    for d in window:
        positions = [original.index(s) for s in split_sentences(d.page_content)]
        assert positions == sorted(positions)
        assert positions  # không có cửa sổ rỗng


# --------------------------------------------------------------------------- reranker
class FakeEmbeddings:
    """Hàm nhúng giả: vector theo độ dài, để kiểm đường lùi bi-encoder không cần model thật."""

    def embed_documents(self, texts):
        return [[1.0, float(len(t) % 7)] for t in texts]

    def embed_query(self, text):
        return [1.0, float(len(text) % 7)]


def test_cross_encoder_unavailable_falls_back_to_bi_encoder(monkeypatch):
    import sys
    import types

    broken = types.ModuleType("sentence_transformers")

    def _boom(*a, **k):
        raise RuntimeError("không tải được weight")

    broken.CrossEncoder = _boom
    monkeypatch.setitem(sys.modules, "sentence_transformers", broken)
    rr = get_reranker(FakeEmbeddings(), force_reload=True)
    assert rr.kind == "bi_encoder"
    assert rr.scores("hỏi", ["a", "bb"]) != []
    status = reranker_status()
    assert status["kind"] == "bi_encoder"
    assert status["requested"]  # manifest phải thấy cả cái ĐÃ XIN và cái DÙNG


def test_no_embeddings_no_cross_encoder_is_none(monkeypatch):
    import sys
    import types

    broken = types.ModuleType("sentence_transformers")
    broken.CrossEncoder = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline"))
    monkeypatch.setitem(sys.modules, "sentence_transformers", broken)
    rr = get_reranker(None, force_reload=True)
    assert rr.kind == "none"
    assert rr.scores("q", ["a"]) == [0.0]


def test_cross_encoder_path_used_when_available(monkeypatch):
    import sys
    import types

    class FakeCE:
        def predict(self, pairs):
            return [0.9 if "hoc lai" in s else 0.1 for _, s in pairs]

    ok = types.ModuleType("sentence_transformers")
    ok.CrossEncoder = lambda name: FakeCE()
    monkeypatch.setitem(sys.modules, "sentence_transformers", ok)
    rr = get_reranker(force_reload=True)
    assert rr.kind == "cross_encoder"
    assert rr.scores("q", ["sinh viên hoc lai", "ban in tai xuong"])[0] > rr.scores("q", ["x"])[0]


# --------------------------------------------------------------------- chống rò đáp án
def test_module_does_not_read_answer_side_fields():
    """Bất biến #6: runtime không được chạm `gold_*`/`required_entities`/`primary_entity`."""
    from src.generation import evidence_selection

    source = importlib.import_module(evidence_selection.__name__).__doc__ or ""
    import pathlib

    code = pathlib.Path(evidence_selection.__file__).read_text(encoding="utf-8")
    body = code.split('"""', 2)[2]  # bỏ docstring (nói về các trường đó để cảnh báo)
    for forbidden in ("gold_sentence", "gold_chunk_id", "required_entities", "primary_entity"):
        assert forbidden not in body
    assert "gold_sentence" in source  # docstring phải ghi rõ luật, code thì không dùng


# ------------------------------------------------------------------ pipeline integration
class FakeLeg:
    def __init__(self, docs):
        self.docs = docs
        self.calls = 0
        self.k = None
        self.search_kwargs = {}

    def invoke(self, query):
        self.calls += 1
        return self.docs


class FakeEnsemble:
    def __init__(self, legs, fused):
        self.retrievers = legs
        self.weights = [1.0, 1.0]
        self.fused = fused
        self.calls = 0

    def invoke(self, query):
        self.calls += 1
        return self.fused


class FakeLocalSLM:
    def __init__(self, normalized):
        self._normalized = normalized

    def generate(self, prompt, temperature=0.0):
        return self._normalized


class RecordingGenerator:
    def __init__(self, answer="Trả lời mẫu có căn cứ."):
        self.answer = answer
        self.received_docs = None
        self.calls = 0

    def generate_answer(self, query, retrieved_docs, question_type=None, raw_query=None):
        self.calls += 1
        self.received_docs = list(retrieved_docs)
        return self.answer


def make_pipeline():
    from src.core.pipeline import HybridRAGPipeline

    fused = docs()
    ensemble = FakeEnsemble([FakeLeg(fused), FakeLeg(fused)], fused)
    gen = RecordingGenerator()
    pipeline = HybridRAGPipeline(
        vector_db=None, local_slm=FakeLocalSLM(QUESTION), generator=gen, retriever=ensemble
    )
    return pipeline, gen


def test_pipeline_off_window_is_untouched(monkeypatch, capsys):
    monkeypatch.delenv("ENABLE_EVIDENCE_SELECTION", raising=False)
    pipeline, gen = make_pipeline()
    result = pipeline.run(QUESTION)
    out = capsys.readouterr().out
    assert "[EvidenceSelection]" not in out
    assert gen.calls == 1
    assert result["evidence_selection"] is None
    # từng ký tự: cửa sổ generator và `contexts` vẫn là nguyên văn chunk
    assert [d.page_content for d in gen.received_docs] == result["contexts"]
    assert result["contexts"] == [DOC_A["page_content"], DOC_B["page_content"]]


def test_pipeline_on_trims_window_but_keeps_recall_and_metadata(monkeypatch):
    monkeypatch.setenv("ENABLE_EVIDENCE_SELECTION", "1")
    pipeline, gen = make_pipeline()
    result = pipeline.run(QUESTION)
    info = result["evidence_selection"]
    if not info["applied"]:
        pytest.skip("fixture không đủ câu đạt chuẩn — đường lùi đã có test riêng")
    chars_after = sum(len(c) for c in result["contexts"])
    assert chars_after < info["chars_before"]
    assert info["n_sentences"] <= 5
    # metadata còn nguyên cho trích dẫn và cho hậu kiểm
    assert {d.metadata["chunk_id"] for d in gen.received_docs} <= {11, 22}
    # câu chữ phải là câu nguyên văn lấy từ chunk gốc (không tự chế văn bản)
    originals = [old.page_content for old in docs()]
    for new in gen.received_docs:
        for s in split_sentences(new.page_content):
            assert any(s in o for o in originals)
    # `sources` (cửa sổ recall để đo gold@k) KHÔNG bị đòn bẩy này động vào
    assert [s["chunk_id"] for s in result["sources"]] == [11, 22]

