"""Test đòn bẩy T3 — `ENABLE_DECOUPLED_REFUSAL` (quyền từ chối rời khỏi tầng sinh).

Hai nghĩa vụ, đúng bất biến #2 của vòng lặp P5:
* CỜ TẮT = hành vi cũ từng ký tự: prompt Qwen, key cache và lời gọi generator
  không đổi một byte; không một dòng code T3 nào chạy (không đo hạng nhánh,
  không phát sinh luật, không thay câu trả lời).
* CỜ BẬT = năm luật từ chối đã đăng ký trong `data/loop/README.md` (mục T3) chạy
  đúng như văn bản, kể cả các trường hợp biên.

Không gọi Ollama/ChromaDB/Gemini: mọi tầng dưới là fake.
"""

import hashlib
import json

import pytest

from src.generator import (
    EXTRACT_ONLY_HEAD,
    EXTRACT_ONLY_PROMPT_VERSION,
    NGOAI_PHAM_VI_EXTRA_LINE,
    PROMPT_VERSION,
    QwenGenerator,
    REFUSAL_TEXT,
    effective_prompt_version,
)
from src.generation.refusal_policy import (
    REFUSAL_REASON_EMPTY,
    REFUSAL_REASON_MODEL_REFUSES,
    REFUSAL_REASON_NO_EVIDENCE,
    REFUSAL_REASON_OFF_TOPIC,
    REFUSAL_REASON_UNGROUNDED,
    REFUSAL_REASON_WEAK_RANK,
    decide_post_generation,
    decide_pre_generation,
    decoupled_refusal_enabled,
    rrf_norm,
)
from src.text_utils import fold

# ------------------------------------------------------------------ ngữ cảnh fixture
# Câu hỏi + chunk ĐÃ ĐO là đạt luật 2 (overlap token nội dung "vien"/"phan" = 1,0).
QUESTION = "Sinh viên học lại tối đa bao nhiêu lần mỗi học phần?"
GOLD_CONTEXT = (
    "Điều 15, Khoản 2: Sinh viên được phép đăng ký học lại tối đa 2 lần cho mỗi "
    "học phần không đạt."
)
# Chunk KHÔNG liên quan: không chứa token nội dung nào của câu hỏi (đã kiểm ở test dưới).
OFF_TOPIC_CONTEXT = "Giáo trình in tại xưởng in nội bộ, khổ A4, đóng gáy keo nhiệt."

LEG_BM25_DOC = GOLD_CONTEXT
DOC_KW = {"source": "1054-qy-de-dhag-2021.pdf", "tier": 1, "chunk_id": 7}


def qwen():
    return QwenGenerator(use_cache=False)


# ------------------------------------------------------------------------ cờ mặc định
def test_flag_default_off(monkeypatch):
    monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
    assert decoupled_refusal_enabled() is False
    for value in ("0", "false", "no", "FALSE", ""):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", value)
        assert decoupled_refusal_enabled() is False
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    assert decoupled_refusal_enabled() is True


# --------------------------------------------------------- OFF: prompt byte-identical
# Chuỗi đầu prompt gốc được GHIM CỨNG ở đây (chép nguyên văn từ bản trước T3). Nếu ai đó
# sửa đường OFF, test này đỏ — đúng nghĩa vụ "tắt cờ = không đổi hành vi đã nghiệm thu".
EXPECTED_OFF_HEAD = (
    "Bạn là trợ lý học vụ Trường Đại học An Giang (AGU). Chỉ được dùng thông tin trong "
    "NGỮ CẢNH dưới đây, tuyệt đối không dùng kiến thức bên ngoài, không bịa số Điều/Khoản.\n"
    "Trả lời bằng tiếng Việt, ngắn gọn (dưới 200 từ), mỗi ý PHẢI kèm căn cứ pháp lý:\n"
    "- Nếu ngữ cảnh có đánh số: (Điều N, Khoản M — Tên_file.pdf)\n"
    "- Nếu không đánh số: (Tên_file.pdf)\n"
    "Ví dụ: (Điều 14, Khoản 5 — 1059-qd-dhag-2020-09-29.pdf)\n"
    f'Nếu NGỮ CẢNH không đủ căn cứ, trả lời đúng một câu: "{REFUSAL_TEXT}"\n'
)


def docs():
    return [{"source": DOC_KW["source"], "tier": str(DOC_KW["tier"]), "content": GOLD_CONTEXT}]


@pytest.mark.parametrize(
    "env_value", [None, "0", "false"], ids=["unset", "0", "false"]
)
def test_off_prompt_equals_golden(monkeypatch, env_value):
    if env_value is None:
        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
    else:
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", env_value)
    prompt = qwen()._build_prompt(QUESTION, docs())
    assert prompt.startswith(EXPECTED_OFF_HEAD)
    assert f'Nếu NGỮ CẢNH không đủ căn cứ, trả lời đúng một câu: "{REFUSAL_TEXT}"' in prompt
    assert prompt.endswith(f"\n\nCÂU HỎI: {QUESTION}\nTRẢ LỜI:")
    assert effective_prompt_version() == PROMPT_VERSION == "v1.3"


@pytest.mark.parametrize("question_type", ["so_sanh", "thu_tuc", "ngoai_pham_vi", None])
def test_off_prompt_with_type_matches_legacy_shape(monkeypatch, question_type):
    """Đường OFF vẫn nối đúng dòng định dạng cũ (P3.4) — không đổi một ký tự."""
    monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
    prompt = qwen()._build_prompt(QUESTION, docs(), question_type=question_type)
    line = QwenGenerator.QWEN_FORMAT_LINES.get(question_type or "", "")
    if line:
        assert prompt.startswith(EXPECTED_OFF_HEAD + line + "\n")
    else:
        assert prompt.startswith(EXPECTED_OFF_HEAD)


# ---------------------------------------------------------------- OFF: cache cũ còn nguyên
def _legacy_key(model, temperature, prompt):
    """Công thức key TRƯỚC T3 — tính lại độc lập để chứng minh entry cũ vẫn trúng."""
    payload = json.dumps(
        {
            "model": model,
            "temperature": temperature,
            "prompt_version": "v1.3",
            "prompt": prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def test_off_cache_key_unchanged(monkeypatch):
    monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
    g = qwen()
    prompt = g._build_prompt(QUESTION, docs())
    assert g._cache_key(prompt, 0.1) == _legacy_key(g.ollama_model, 0.1, prompt)


def test_on_cache_key_is_a_separate_namespace(monkeypatch):
    """Cùng một chuỗi prompt nhưng hai hành vi phải nằm hai không gian cache riêng."""
    g = qwen()
    same_prompt = "prompt-giong-het-nhau"
    monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
    key_off = g._cache_key(same_prompt, 0.1)
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    key_on = g._cache_key(same_prompt, 0.1)
    assert key_off == _legacy_key(g.ollama_model, 0.1, same_prompt)  # cache cũ còn nguyên
    assert key_on != key_off
    assert effective_prompt_version() == EXTRACT_ONLY_PROMPT_VERSION


# ----------------------------------------------------------------- ON: không còn lời mời từ chối
def test_on_prompt_removes_refusal_affordance(monkeypatch):
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    prompt = qwen()._build_prompt(QUESTION, docs(), question_type="ngoai_pham_vi")
    assert REFUSAL_TEXT not in prompt
    # Marker mà tầng ngoài dùng để nhận diện lời từ chối không được xuất hiện trong prompt:
    assert "khong du thong tin" not in fold(prompt)
    assert "không đủ thông tin" not in prompt
    # Dòng từ chối của nhãn NGOAI_PHAM_VI bị bỏ, nhưng bản trích xuất vẫn cấm bịa:
    assert NGOAI_PHAM_VI_EXTRA_LINE not in prompt
    assert "CẤM tự viết ra số Điều/Khoản" in prompt
    assert prompt.startswith(EXTRACT_ONLY_HEAD)


def test_on_prompt_keeps_context_and_question_tail(monkeypatch):
    """Chỉ đổi PHẦN HƯỚNG DẪN; phần NGỮ CẢNH + CÂU HỎI phải giống hệt đường OFF."""
    g = qwen()
    monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
    off = g._build_prompt(QUESTION, docs())
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    on = g._build_prompt(QUESTION, docs())
    tail = "\nNGỮ CẢNH:\n"
    assert off.split(tail, 1)[1] == on.split(tail, 1)[1]


def test_on_prompt_keeps_format_line_for_so_sanh(monkeypatch):
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    prompt = qwen()._build_prompt(QUESTION, docs(), question_type="so_sanh")
    assert QwenGenerator.QWEN_FORMAT_LINES["so_sanh"] in prompt


# ------------------------------------------------------------------------ luật 1-3 (pre)
def test_law1_no_evidence():
    d = decide_pre_generation(question=QUESTION, contexts=[])
    assert d.refuse and d.reason == REFUSAL_REASON_NO_EVIDENCE
    short = decide_pre_generation(question=QUESTION, contexts=["ngắn"])
    assert short.refuse and short.reason == REFUSAL_REASON_NO_EVIDENCE


def test_law2_off_topic_window():
    # bằng chứng thô: chunk lạc đề không chia token nội dung nào với câu hỏi
    assert "vien" not in fold(OFF_TOPIC_CONTEXT)
    assert "phan" not in fold(OFF_TOPIC_CONTEXT)
    d = decide_pre_generation(question=QUESTION, contexts=[OFF_TOPIC_CONTEXT])
    assert d.refuse and d.reason == REFUSAL_REASON_OFF_TOPIC
    assert d.features["n_relevant_chunks"] == 0


def test_law3_weak_rank_and_pass():
    pairs_ok = [(1, 1), (3, 2)]
    d = decide_pre_generation(
        question=QUESTION, contexts=[GOLD_CONTEXT, OFF_TOPIC_CONTEXT], leg_ranks=pairs_ok,
        bm25_weight=1.0, vector_weight=1.0,
    )
    assert d.refuse is False
    assert d.features["rrf_norm"] == 1.0

    d_weak = decide_pre_generation(
        question=QUESTION, contexts=[GOLD_CONTEXT], leg_ranks=[(12, 9)],
        bm25_weight=1.0, vector_weight=1.0,
    )
    assert d_weak.refuse and d_weak.reason == REFUSAL_REASON_WEAK_RANK
    assert d_weak.features["rrf_norm"] < 0.90


def test_rrf_unavailable_is_not_silently_accepted():
    """Không đo được hạng thì KHÔNG được coi là đạt — phải ghi dấu vào features."""
    for leg_ranks in (None, [(None, None)], [[]][:0]):
        d = decide_pre_generation(question=QUESTION, contexts=[GOLD_CONTEXT], leg_ranks=leg_ranks)
        assert d.refuse is False
        assert d.features.get("rrf_unavailable") is True


def test_rrf_norm_math():
    assert rrf_norm(1, 1, bm25_weight=1.0, vector_weight=1.0) == 1.0
    # một nhánh hạng nhất, nhánh kia tụt: vẫn trên ngưỡng 0,90 đến ~hạng 6
    assert rrf_norm(1, 6, bm25_weight=1.0, vector_weight=1.0) > 0.90
    assert rrf_norm(10, 10, bm25_weight=1.0, vector_weight=1.0) < 0.90
    assert rrf_norm(None, None, bm25_weight=1.0, vector_weight=1.0) is None
    # tổng trọng số khác 1 vẫn chuẩn hóa đúng (chia cho cực đại của chính weights đó)
    assert rrf_norm(1, 1, bm25_weight=3.0, vector_weight=9.0) == 1.0


# ---------------------------------------------------------------------- luật 4-5 (post)
def test_law5_model_still_refuses():
    d = decide_post_generation(
        question=QUESTION, contexts=[GOLD_CONTEXT],
        answer="Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này.",
    )
    assert d.refuse and d.reason == REFUSAL_REASON_MODEL_REFUSES


def test_law_post_empty_answer():
    d = decide_post_generation(question=QUESTION, contexts=[GOLD_CONTEXT], answer="   ")
    assert d.refuse and d.reason == REFUSAL_REASON_EMPTY


def test_law4_ungrounded_number_is_refused():
    d = decide_post_generation(
        question=QUESTION,
        contexts=[GOLD_CONTEXT],
        answer="Sinh viên được đăng ký học lại tối đa 99 lần mỗi học phần. (1054-qy-de-dhag-2021.pdf)",
        source_names=[DOC_KW["source"]],
    )
    assert d.refuse and d.reason == REFUSAL_REASON_UNGROUNDED
    assert d.features["n_unsupported"] >= 1


def test_law4_grounded_answer_passes():
    d = decide_post_generation(
        question=QUESTION,
        contexts=[GOLD_CONTEXT],
        answer="Sinh viên được đăng ký học lại tối đa 2 lần cho mỗi học phần không đạt. (Điều 15, Khoản 2)",
        source_names=[DOC_KW["source"]],
    )
    assert d.refuse is False
    assert d.features["grounding_score"] == 1.0


def test_law4_score_none_is_accepted_by_registration():
    """Đã đăng ký trước: câu không có khẳng định kiểm chứng được => CHẤP NHẬN."""
    d = decide_post_generation(
        question=QUESTION,
        contexts=[GOLD_CONTEXT],
        answer="Quy chế cho phép sinh viên đăng ký học lại khi học phần không đạt.",
        source_names=[DOC_KW["source"]],
    )
    assert d.refuse is False
    assert d.features["grounding_score"] is None


def test_post_carries_pre_features_through():
    pre = decide_pre_generation(question=QUESTION, contexts=[GOLD_CONTEXT], leg_ranks=[(1, 1)])
    post = decide_post_generation(
        question=QUESTION, contexts=[GOLD_CONTEXT], answer="Trả lời 2 lần (Điều 15).",
        pre_features=pre.features,
    )
    assert post.features["best_rank_bm25"] == 1
    assert post.features["rrf_norm"] == 1.0


# ---------------------------------------------------------------- pipeline integration
class FakeDoc:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


class FakeLeg:
    """Một nhánh của Ensemble: ghi lại số lần bị gọi để chứng minh đường OFF không đo gì."""

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


class CountingGenerator:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0
        self.received_docs = None

    def generate_answer(self, query, retrieved_docs, question_type=None, raw_query=None):
        self.calls += 1
        self.received_docs = retrieved_docs
        return self.answer


def make_pipeline(answer="Trả lời mẫu.", normalized=None, legs=None, fused=None):
    from src.core.pipeline import HybridRAGPipeline

    normalized = normalized or QUESTION
    bm25 = FakeLeg(legs[0] if legs else [FakeDoc(GOLD_CONTEXT, DOC_KW)])
    vector = FakeLeg(legs[1] if legs else [FakeDoc(GOLD_CONTEXT, DOC_KW)])
    ensemble = FakeEnsemble([bm25, vector], fused or [FakeDoc(GOLD_CONTEXT, DOC_KW)])
    gen = CountingGenerator(answer)
    pipeline = HybridRAGPipeline(
        vector_db=None,
        local_slm=FakeLocalSLM(normalized),
        generator=gen,
        retriever=ensemble,
    )
    return pipeline, ensemble, (bm25, vector), gen


def test_pipeline_off_does_not_touch_t3(monkeypatch, capsys):
    monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
    pipeline, ensemble, legs, gen = make_pipeline(answer="Sinh viên được học lại tối đa 2 lần.")
    result = pipeline.run(QUESTION)
    out = capsys.readouterr().out
    assert "[DecoupledRefusal]" not in out
    assert all(leg.calls == 0 for leg in legs)
    assert ensemble.calls == 2  # hành vi cũ: 1 lượt query chính + 1 lượt fallback_query
    assert gen.calls == 1
    assert result["answer"] == "Sinh viên được học lại tối đa 2 lần."
    assert result["refusal_decision"] is None
    assert pipeline.last_leg_ranks is None


def test_pipeline_on_refuses_before_spending_a_generation(monkeypatch, capsys):
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    off_topic = [FakeDoc(OFF_TOPIC_CONTEXT, {"source": "tap-chi.pdf", "tier": 3, "chunk_id": 42})]
    pipeline, ensemble, legs, gen = make_pipeline(fused=off_topic, normalized=QUESTION)
    result = pipeline.run(QUESTION)
    out = capsys.readouterr().out
    assert gen.calls == 0  # không tốn một lượt sinh cho câu đã bị luật 2 chặn
    assert result["answer"] == REFUSAL_TEXT
    assert result["refusal_decision"]["reason"] == REFUSAL_REASON_OFF_TOPIC
    assert "[DecoupledRefusal] pre refuse=1 reason=off_topic_window" in out
    assert all(leg.calls == 1 for leg in legs)  # chỉ đường BẬT mới đo hạng từng nhánh


def test_pipeline_on_passes_grounded_answer(monkeypatch, capsys):
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    answer = "Sinh viên được đăng ký học lại tối đa 2 lần cho mỗi học phần không đạt. (Điều 15, Khoản 2)"
    pipeline, _, _, gen = make_pipeline(answer=answer)
    result = pipeline.run(QUESTION)
    out = capsys.readouterr().out
    assert gen.calls == 1
    assert result["answer"] == answer  # không bị tầng ngoài ghi đè
    assert result["refusal_decision"]["stage"] == "post"
    assert result["refusal_decision"]["refuse"] is False
    assert "[DecoupledRefusal] pre refuse=0" in out


def test_pipeline_on_replaces_fabricated_answer(monkeypatch):
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    fabricated = "Sinh viên được đăng ký học lại tối đa 99 lần. (1054-qy-de-dhag-2021.pdf)"
    pipeline, _, _, gen = make_pipeline(answer=fabricated)
    result = pipeline.run(QUESTION)
    assert result["answer"] == REFUSAL_TEXT
    assert result["refusal_decision"]["reason"] == REFUSAL_REASON_UNGROUNDED


def test_pipeline_on_uses_per_leg_ranks_for_weak_rank_law(monkeypatch):
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
    chunk = FakeDoc(GOLD_CONTEXT, DOC_KW)
    # chunk vàng tụt hạng ở cả hai nhánh -> rrf_norm < 0,90 -> luật 3 chặn
    bm25_leg = [FakeDoc(f"dot thu {i}", {"source": "khac.pdf", "tier": 3, "chunk_id": 100 + i}) for i in range(11)]
    bm25_leg.append(chunk)
    vector_leg = [FakeDoc(f"dot thu {i}", {"source": "khac.pdf", "tier": 3, "chunk_id": 100 + i}) for i in range(8)]
    vector_leg.append(chunk)
    pipeline, _, _, gen = make_pipeline(legs=[bm25_leg, vector_leg], fused=[chunk])
    result = pipeline.run(QUESTION)
    assert gen.calls == 0
    assert result["refusal_decision"]["reason"] == REFUSAL_REASON_WEAK_RANK
    assert pipeline.last_leg_ranks[str(DOC_KW["chunk_id"])] == (12, 9)
