# -*- coding: utf-8 -*-
"""Unit test P3.4 — biến thể prompt theo question_type + từ chối NGOAI_PHAM_VI.

Offline hoàn toàn: không gọi Gemini/Ollama thật; cache Qwen trỏ sang tmp_path.
Trọng tâm:
1. None → prompt gốc GIỐNG HỆT từng ký tự (cache cũ còn trúng).
2. SO_SANH/THU_TUC/NGOAI_PHAM_VI → biến thể đúng, refusal luôn đã resolve.
3. Biến thể tạo key cache khác (cache tự tách nhánh).
4. Pipeline truyền question_type xuống generator.
5. P3.4b — inject là hậu xử lý dùng chung HIT/MISS: MISS ≡ HIT từng ký tự,
   từ chối chuẩn HIT nguyên vẹn, entry cũ (text chưa inject) vẫn HIT đúng.
"""

import json
from types import SimpleNamespace

import pytest

import src.generator as gen_module
from src.generator import (
    NGOAI_PHAM_VI_EXTRA_LINE,
    PROMPT_RULES,
    PROMPT_RULES_NGOAI_PHAM_VI,
    PROMPT_RULES_SO_SANH,
    PROMPT_RULES_THU_TUC,
    QwenGenerator,
    GeminiGenerator,
    REFUSAL_MARKER,
    REFUSAL_TEXT,
    GeneratorError,
    build_prompt,
    canonicalize_refusal,
    quota_error_kind,
    select_prompt_rules,
)
QUERY = "So sánh mức học phí khối kỹ thuật và khối kinh tế?"
DOCS = [
    {"content": "Điều 3. Mức thu học phí theo khối ngành.", "source": "hoc-phi.pdf", "tier": "1", "chunk_id": 7},
    {"content": "Mức thu áp dụng từ năm học 2026-2027.", "source": "quy-che.pdf", "tier": "1", "chunk_id": 8},
]


# ---------------------------------------------------------------------------
# select_prompt_rules: chọn biến thể
# ---------------------------------------------------------------------------

class TestSelectPromptRules:
    def test_none_returns_base_rules(self):
        assert select_prompt_rules(None) is PROMPT_RULES

    def test_tra_cuu_returns_base_rules(self):
        assert select_prompt_rules("TRA_CUU") is PROMPT_RULES

    def test_empty_string_returns_base_rules(self):
        assert select_prompt_rules("") is PROMPT_RULES

    def test_unknown_label_returns_base_rules(self):
        assert select_prompt_rules("LOAI_LA") is PROMPT_RULES

    def test_so_sanh_variant(self):
        rules = select_prompt_rules("SO_SANH")
        assert rules is PROMPT_RULES_SO_SANH
        assert "BẢNG" in rules
        assert "TIÊU CHÍ" in rules
        assert "Mỗi Ô" in rules

    def test_thu_tuc_variant(self):
        rules = select_prompt_rules("THU_TUC")
        assert rules is PROMPT_RULES_THU_TUC
        assert "Bước 1" in rules
        assert "BƯỚC ĐÁNH SỐ" in rules

    def test_ngoai_pham_vi_variant(self):
        rules = select_prompt_rules("NGOAI_PHAM_VI")
        assert rules is PROMPT_RULES_NGOAI_PHAM_VI
        assert NGOAI_PHAM_VI_EXTRA_LINE in rules

    def test_fold_insensitive(self):
        assert select_prompt_rules("so_sanh") is PROMPT_RULES_SO_SANH
        assert select_prompt_rules("So_Sanh") is PROMPT_RULES_SO_SANH
        assert select_prompt_rules("  thu_tuc  ") is PROMPT_RULES_THU_TUC


# ---------------------------------------------------------------------------
# build_prompt: None phải byte-identical; biến thể phải khác và refusal resolved
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_none_is_byte_identical_to_old_formula(self):
        docs = list(DOCS)
        context_block = "\n\n".join(
            f"[Ngữ cảnh {i}] Nguồn: {d['source']} | Tầng: {d['tier']} | chunk_id: {d['chunk_id']}\n{d['content']}"
            for i, d in enumerate(docs, start=1)
        )
        expected = (
            f"NGỮ CẢNH TRUY XUẤT TỪ VECTOR DB ({len(docs)} đoạn):\n{context_block}\n\n"
            f"CÂU HỎI CỦA SINH VIÊN: {QUERY}\n\n"
            f"{PROMPT_RULES.format(refusal=REFUSAL_TEXT)}\n\n"
            "TRẢ LỜI:"
        )
        assert build_prompt(QUERY, docs) == expected
        assert build_prompt(QUERY, docs, question_type=None) == expected

    def test_variants_differ_from_base(self):
        base = build_prompt(QUERY, DOCS)
        assert build_prompt(QUERY, DOCS, "SO_SANH") != base
        assert build_prompt(QUERY, DOCS, "THU_TUC") != base
        assert build_prompt(QUERY, DOCS, "NGOAI_PHAM_VI") != base

    def test_all_variants_have_resolved_refusal(self):
        for qt in (None, "TRA_CUU", "SO_SANH", "THU_TUC", "NGOAI_PHAM_VI"):
            prompt = build_prompt(QUERY, DOCS, qt)
            assert REFUSAL_TEXT in prompt
            assert "{refusal}" not in prompt

    def test_so_sanh_prompt_contains_table_rules(self):
        prompt = build_prompt(QUERY, DOCS, "SO_SANH")
        assert "BẢNG so sánh" in prompt
        assert "NGUỒN của từng vế" in prompt

    def test_ngoai_prompt_contains_extra_line(self):
        prompt = build_prompt(QUERY, DOCS, "NGOAI_PHAM_VI")
        assert NGOAI_PHAM_VI_EXTRA_LINE in prompt


# ---------------------------------------------------------------------------
# QwenGenerator offline: biến thể prompt + cache tự tách key
# ---------------------------------------------------------------------------

class FakeOllamaClient:
    """Thay ollama.Client: ghi lại prompt, trả câu trả lời cố định, đếm số lần gọi."""

    instances = []

    def __init__(self, host=None, timeout=None):
        self.calls = []

        FakeOllamaClient.instances.append(self)

    def generate(self, model=None, prompt=None, options=None, stream=False):
        self.calls.append(prompt)
        return {"response": "cau tra loi mau"}


@pytest.fixture()
def fake_ollama(monkeypatch):
    FakeOllamaClient.instances = []
    monkeypatch.setattr(gen_module.ollama, "Client", FakeOllamaClient)
    return FakeOllamaClient


@pytest.fixture()
def qwen_gen(monkeypatch, tmp_path):
    monkeypatch.setenv("GENERATION_CACHE_DIR", str(tmp_path / "cache"))
    return QwenGenerator(use_cache=True)


class TestQwenGeneratorVariants:
    def test_none_prompt_unchanged(self, fake_ollama, qwen_gen):
        expected = qwen_gen._build_prompt(QUERY, DOCS)
        assert "dạng bảng" not in expected  # đường None không nhét dòng biến thể
        qwen_gen.generate_answer(QUERY, DOCS)
        assert fake_ollama.instances[-1].calls[-1] == expected

    def test_so_sanh_adds_table_line(self, fake_ollama, qwen_gen):
        qwen_gen.generate_answer(QUERY, DOCS, question_type="SO_SANH")
        prompt = fake_ollama.instances[-1].calls[-1]
        assert "dạng bảng" in prompt

    def test_thu_tuc_adds_steps_line(self, fake_ollama, qwen_gen):
        qwen_gen.generate_answer(QUERY, DOCS, question_type="THU_TUC")
        prompt = fake_ollama.instances[-1].calls[-1]
        assert "Bước 1" in prompt

    def test_ngoai_adds_refusal_line(self, fake_ollama, qwen_gen):
        qwen_gen.generate_answer(QUERY, DOCS, question_type="NGOAI_PHAM_VI")
        prompt = fake_ollama.instances[-1].calls[-1]
        assert NGOAI_PHAM_VI_EXTRA_LINE in prompt

    def test_empty_context_refuses_exactly(self, fake_ollama, qwen_gen):
        assert qwen_gen.generate_answer(QUERY, [], question_type="SO_SANH") == REFUSAL_TEXT
        assert fake_ollama.instances == []  # không gọi Ollama


class TestQwenGeneratorCacheSeparation:
    def test_variant_creates_new_key_base_reuses_old(self, fake_ollama, qwen_gen, tmp_path):
        cache_dir = tmp_path / "cache"

        def total_calls():
            return sum(len(c.calls) for c in fake_ollama.instances)

        qwen_gen.generate_answer(QUERY, DOCS)                    # miss → ghi cache
        qwen_gen.generate_answer(QUERY, DOCS)                    # trúng cache cũ
        assert total_calls() == 1
        assert len(list(cache_dir.glob("*.json"))) == 1

        qwen_gen.generate_answer(QUERY, DOCS, question_type="SO_SANH")  # key mới → gọi lại
        assert total_calls() == 2
        assert len(list(cache_dir.glob("*.json"))) == 2

        # TRA_CUU → vẫn PROMPT_RULES gốc → cùng key với đường None.
        qwen_gen.generate_answer(QUERY, DOCS, question_type="TRA_CUU")
        assert total_calls() == 2                                # trúng cache, không gọi mới
        assert len(list(cache_dir.glob("*.json"))) == 2


# ---------------------------------------------------------------------------
# GeminiGenerator offline (fake _call_api): biến thể + refusal regression
# ---------------------------------------------------------------------------

@pytest.fixture()
def gemini_gen(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-p34-offline")
    monkeypatch.setenv("GENERATION_CACHE", "0")  # unit test không đụng cache thật
    instance = GeminiGenerator()
    instance.captured_prompts = []

    def fake_call_api(prompt, temperature):
        instance.captured_prompts.append(prompt)
        return "cau tra loi gemini"

    monkeypatch.setattr(instance, "_call_api", fake_call_api)
    return instance


class TestGeminiGeneratorVariants:
    def test_none_prompt_is_base(self, gemini_gen):
        gemini_gen.generate_answer(QUERY, DOCS)
        expected = build_prompt(QUERY, DOCS)
        assert gemini_gen.captured_prompts[-1] == expected

    def test_thu_tuc_prompt_has_steps(self, gemini_gen):
        gemini_gen.generate_answer(QUERY, DOCS, question_type="THU_TUC")
        assert "BƯỚC ĐÁNH SỐ" in gemini_gen.captured_prompts[-1]

    def test_so_sanh_prompt_has_table(self, gemini_gen):
        gemini_gen.generate_answer(QUERY, DOCS, question_type="SO_SANH")
        assert "BẢNG so sánh" in gemini_gen.captured_prompts[-1]

    def test_ngoai_prompt_has_extra_line(self, gemini_gen):
        gemini_gen.generate_answer(QUERY, DOCS, question_type="NGOAI_PHAM_VI")
        assert NGOAI_PHAM_VI_EXTRA_LINE in gemini_gen.captured_prompts[-1]

    def test_empty_context_refuses_exactly(self, gemini_gen):
        assert gemini_gen.generate_answer(QUERY, [], question_type="NGOAI_PHAM_VI") == REFUSAL_TEXT
        assert gemini_gen.captured_prompts == []  # không gọi API


# ---------------------------------------------------------------------------
# canonicalize_refusal: NGOAI tự từ chối → chuỗi chuẩn; trả lời có căn cứ → giữ nguyên
# ---------------------------------------------------------------------------

class TestCanonicalizeRefusal:
    def test_ngoai_refusal_with_extra_text_canonicalized(self):
        raw = f"{REFUSAL_TEXT} (hoc-phi.pdf)"
        assert canonicalize_refusal(raw, "NGOAI_PHAM_VI") == REFUSAL_TEXT

    def test_ngoai_substantive_answer_untouched(self):
        raw = "Kế hoạch do Khoa CNTT phê duyệt. (ke-hoach.pdf)"
        assert canonicalize_refusal(raw, "NGOAI_PHAM_VI") == raw

    def test_non_ngoai_refusal_untouched(self):
        raw = f"{REFUSAL_TEXT} (hoc-phi.pdf)"
        assert canonicalize_refusal(raw, None) == raw
        assert canonicalize_refusal(raw, "SO_SANH") == raw
        assert canonicalize_refusal(raw, "TRA_CUU") == raw

    def test_marker_detection(self):
        raw = "Tài liệu hiện có không đủ thông tin để trả lời. (a.pdf)"
        assert REFUSAL_MARKER in raw
        assert canonicalize_refusal(raw, "NGOAI_PHAM_VI") == REFUSAL_TEXT

    def test_empty_answer_untouched(self):
        assert canonicalize_refusal("", "NGOAI_PHAM_VI") == ""


class TestRefusalCanonicalizationEndToEnd:
    def test_qwen_ngoai_refusal_returns_exact_string(self, fake_ollama, monkeypatch, tmp_path):
        monkeypatch.setenv("GENERATION_CACHE_DIR", str(tmp_path / "cache"))
        gen = QwenGenerator(use_cache=True)

        class RefusingClient(FakeOllamaClient):
            def generate(self, model=None, prompt=None, options=None, stream=False):
                self.calls.append(prompt)
                return {"response": f"{REFUSAL_TEXT} (ke-hoach-ttck-kltn-dh24th-2026.pdf)"}

        monkeypatch.setattr(gen_module.ollama, "Client", RefusingClient)
        out = gen.generate_answer(QUERY, DOCS, question_type="NGOAI_PHAM_VI")
        assert out == REFUSAL_TEXT  # không đính kèm trích dẫn phá chuỗi chuẩn
        # Cache lưu dạng chuẩn → lượt sau trúng cache vẫn đúng chuỗi.
        out2 = gen.generate_answer(QUERY, DOCS, question_type="NGOAI_PHAM_VI")
        assert out2 == REFUSAL_TEXT

    def test_qwen_non_ngoai_refusal_keeps_citation(self, fake_ollama, monkeypatch, tmp_path):
        monkeypatch.setenv("GENERATION_CACHE_DIR", str(tmp_path / "cache2"))
        gen = QwenGenerator(use_cache=True)

        class RefusingClient(FakeOllamaClient):
            def generate(self, model=None, prompt=None, options=None, stream=False):
                self.calls.append(prompt)
                return {"response": REFUSAL_TEXT}

        monkeypatch.setattr(gen_module.ollama, "Client", RefusingClient)
        out = gen.generate_answer(QUERY, DOCS)  # question_type None → hành vi cũ
        assert out != REFUSAL_TEXT
        assert "hoc-phi.pdf" in out  # trích dẫn vẫn được đính kèm như trước

    def test_gemini_ngoai_refusal_returns_exact_string(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-p34-offline")
        monkeypatch.setenv("GENERATION_CACHE", "0")
        instance = GeminiGenerator()
        raw = f"{REFUSAL_TEXT} Ngữ cảnh không chứa thông tin liên quan."

        def fake_call_api(prompt, temperature):
            return raw

        monkeypatch.setattr(instance, "_call_api", fake_call_api)
        out = instance.generate_answer(QUERY, DOCS, question_type="NGOAI_PHAM_VI")
        assert out == REFUSAL_TEXT


# ---------------------------------------------------------------------------
# Cache entry content: đủ thông tin tra vết (query/prompt)
# ---------------------------------------------------------------------------

class TestCacheEntryContent:
    def test_entry_records_query_and_answer(self, fake_ollama, qwen_gen, tmp_path):
        qwen_gen.generate_answer(QUERY, DOCS, question_type="SO_SANH")
        entries = list((tmp_path / "cache").glob("*.json"))
        assert len(entries) == 1
        entry = json.loads(entries[0].read_text(encoding="utf-8"))
        assert entry["query"] == QUERY
        assert entry["answer"] == "cau tra loi mau"


# ---------------------------------------------------------------------------
# P3.4b — inject là hậu xử lý dùng chung HIT/MISS: cùng câu hỏi → cùng chuỗi
# ---------------------------------------------------------------------------

def _total_calls(clients):
    return sum(len(c.calls) for c in clients)


class TestCacheHitMissSymmetry:
    def test_no_prompt_version_bump(self):
        assert gen_module.PROMPT_VERSION == "v1.3"  # entry cũ 308 file vẫn hợp lệ

    def test_qwen_hit_identical_to_miss(self, fake_ollama, qwen_gen):
        miss = qwen_gen.generate_answer(QUERY, DOCS)
        assert "hoc-phi.pdf" in miss  # MISS luôn có trích dẫn
        hit = qwen_gen.generate_answer(QUERY, DOCS)
        assert hit == miss  # HIT giống từng ký tự lượt MISS
        assert _total_calls(fake_ollama.instances) == 1  # API đúng 1 lần

    def test_qwen_hit_idempotent_across_calls(self, fake_ollama, qwen_gen):
        results = [qwen_gen.generate_answer(QUERY, DOCS) for _ in range(3)]
        assert results[0] == results[1] == results[2]
        assert _total_calls(fake_ollama.instances) == 1  # cache không tự ghi đè

    def test_qwen_refusal_hit_stays_pure(self, fake_ollama, monkeypatch, tmp_path):
        """MISS từ chối chuẩn → cache chuỗi chuẩn → HIT KHÔNG gắn trích dẫn."""
        monkeypatch.setenv("GENERATION_CACHE_DIR", str(tmp_path / "cache3"))
        gen = QwenGenerator(use_cache=True)

        class RefusingClient(FakeOllamaClient):
            def generate(self, model=None, prompt=None, options=None, stream=False):
                self.calls.append(prompt)
                return {"response": f"{REFUSAL_TEXT} ke-ca voi phan thua cua model"}

        monkeypatch.setattr(gen_module.ollama, "Client", RefusingClient)
        miss = gen.generate_answer(QUERY, DOCS, question_type="NGOAI_PHAM_VI")
        assert miss == REFUSAL_TEXT
        entry = json.loads(next((tmp_path / "cache3").glob("*.json")).read_text(encoding="utf-8"))
        assert entry["answer"] == REFUSAL_TEXT  # cache lưu dạng chuẩn
        hit = gen.generate_answer(QUERY, DOCS, question_type="NGOAI_PHAM_VI")
        assert hit == REFUSAL_TEXT  # HIT nguyên chuỗi chuẩn, không có trích dẫn
        assert _total_calls(RefusingClient.instances) == 1

    def test_gemini_hit_identical_to_miss(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-p34b-offline")
        monkeypatch.setenv("GENERATION_CACHE", "1")
        monkeypatch.setenv("GENERATION_CACHE_DIR", str(tmp_path / "gcache"))
        instance = GeminiGenerator()
        api_calls = []

        def fake_call_api(prompt, temperature):
            api_calls.append(prompt)
            return "Cau tra loi gemini chua co trich dan."

        monkeypatch.setattr(instance, "_call_api", fake_call_api)
        miss = instance.generate_answer(QUERY, DOCS)
        assert "hoc-phi.pdf" in miss
        hit = instance.generate_answer(QUERY, DOCS)
        assert hit == miss  # HIT ≡ MISS từng ký tự
        assert len(api_calls) == 1

    def test_old_qwen_entry_pre_inject_still_hit_and_injected(self, fake_ollama, qwen_gen, tmp_path):
        """Entry cũ (viết tay, text CHƯA inject đúng như cache trước P3.4b) → HIT,
        được inject đúng, không gọi API, không bump version."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True)
        prompt = qwen_gen._build_prompt(QUERY, DOCS)
        key = qwen_gen._cache_key(prompt, qwen_gen.temperature)
        entry = {
            "prompt_sha1": key,
            "model": qwen_gen.ollama_model,
            "temperature": qwen_gen.temperature,
            "query": QUERY,
            "answer": "cau tra loi cu chua inject",
            "created_at": "2026-10-19T00:00:00",
        }
        (cache_dir / f"{key}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

        out = qwen_gen.generate_answer(QUERY, DOCS)
        assert out.startswith("cau tra loi cu chua inject")  # nội dung gốc giữ nguyên
        assert "hoc-phi.pdf" in out  # HIT giờ có trích dẫn như MISS
        assert _total_calls(fake_ollama.instances) == 0  # không gọi API

    def test_old_gemini_entry_pre_inject_still_hit_and_injected(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-p34b-offline")
        monkeypatch.setenv("GENERATION_CACHE", "1")
        monkeypatch.setenv("GENERATION_CACHE_DIR", str(tmp_path / "gcache2"))
        instance = GeminiGenerator()
        cache_dir = tmp_path / "gcache2"
        cache_dir.mkdir(parents=True)
        prompt = build_prompt(QUERY, DOCS)
        key = instance._cache_key(prompt, instance.temperature)
        entry = {
            "prompt_sha1": key,
            "model": instance.model_name,
            "temperature": instance.temperature,
            "query": QUERY,
            "answer": "cau tra loi gemini cu chua inject",
            "created_at": "2026-10-19T00:00:00",
        }
        (cache_dir / f"{key}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

        def fail_call_api(prompt, temperature):  # HIT thì không được chạm API
            raise AssertionError("HIT entry cũ vẫn gọi API — sai thiết kế P3.4b")

        monkeypatch.setattr(instance, "_call_api", fail_call_api)
        out = instance.generate_answer(QUERY, DOCS)
        assert out.startswith("cau tra loi gemini cu chua inject")
        assert "hoc-phi.pdf" in out


# ---------------------------------------------------------------------------
# Bước 0 P4.2 (mục 1): _call_api retry 429 theo phút (chờ 60s × 3) + PerDay dừng ngay
# ---------------------------------------------------------------------------

def _bare_gemini_generator() -> GeminiGenerator:
    """GeminiGenerator bỏ qua __init__ (không đụng API key/config thật)."""
    gen = GeminiGenerator.__new__(GeminiGenerator)
    gen.model = None
    gen.max_output_tokens = 128
    gen.max_retries = 2
    gen.model_name = "gemini-fake"
    return gen


class TestCallApiQuotaRetry:
    def test_minute_429_retried_then_success(self, monkeypatch):
        gen = _bare_gemini_generator()
        calls = {"n": 0}

        class Resp:
            text = "  ok  "

        def fake_generate(prompt, generation_config=None):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise RuntimeError("429 Resource has been exhausted: requests per minute")
            return Resp()

        gen.model = SimpleNamespace(generate_content=fake_generate)
        monkeypatch.setattr(gen_module.time, "sleep", lambda s: None)
        assert gen._call_api("p", 0.0) == "ok"
        assert calls["n"] == 3                       # 2 lỗi phút + 1 thành công

    def test_minute_429_gives_up_after_3_retries(self, monkeypatch):
        gen = _bare_gemini_generator()
        calls = {"n": 0}

        def fake_generate(prompt, generation_config=None):
            calls["n"] += 1
            raise RuntimeError("429 too many requests per minute")

        gen.model = SimpleNamespace(generate_content=fake_generate)
        monkeypatch.setattr(gen_module.time, "sleep", lambda s: None)
        with pytest.raises(GeneratorError):
            gen._call_api("p", 0.0)
        assert calls["n"] == 4                       # 1 gọi + đúng 3 retry phút

    def test_perday_no_retry_with_explicit_marker(self, monkeypatch):
        gen = _bare_gemini_generator()
        calls = {"n": 0}

        def fake_generate(prompt, generation_config=None):
            calls["n"] += 1
            raise RuntimeError("429 quota exceeded. limit: GenerateRequestsPerDay")

        gen.model = SimpleNamespace(generate_content=fake_generate)
        monkeypatch.setattr(gen_module.time, "sleep", lambda s: None)
        with pytest.raises(GeneratorError) as excinfo:
            gen._call_api("p", 0.0)
        assert "PerDay" in str(excinfo.value)        # marker để evaluation dừng cả lượt
        assert calls["n"] == 1                       # không chờ/retry vô ích

    def test_quota_error_kind_prioritizes_perday(self):
        # Thông điệp chứa cả "429" lẫn "PerDay" phải phân loại là perday, không phải minute.
        assert quota_error_kind("429 You exceeded... GenerateRequestsPerDay") == "perday"
