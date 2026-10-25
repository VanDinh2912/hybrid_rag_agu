# -*- coding: utf-8 -*-
"""Unit test tầng AnswerGuard (vòng lặp tự kiểm chứng chống bịa đặt).

Bối cảnh lỗi thực đã xảy ra: `outputs/ab_results_with_classifier.json` câu Q01
trả lời mã `CON515` trong khi tài liệu ghi `CON915` — metric cũ (token-overlap)
chấm ĐÚNG. Các test dưới đây chốt rằng lớp kiểm chứng theo THỰC THỂ bắt được
kiểu lỗi đó và production chặn được nó.

Offline hoàn toàn: không gọi Ollama/Gemini thật, cache trỏ tmp_path.
"""

import json
from types import SimpleNamespace

import pytest

import src.generator as gen_module
from src.answer_guard import (
    Entity,
    answer_guard_enabled,
    check_grounding,
    extract_entities,
    guard_qwen_answer,
    is_enough_evidence,
    refusal_thresholds,
)
from src.generator import REFUSAL_TEXT, QwenGenerator

CONTEXTS = [
    "Điều 3. Mức thu học phí khối kỹ thuật là 450.000 đồng/tín chỉ.",
    "Quyết định 1054-QĐ/ĐHAG ban hành ngày 15/09/2024 về danh hiệu Sinh viên 5 tốt.",
    "Lớp CON915 thuộc học phần Công nghệ Web, tổ chức tại Cơ sở Long Xuyên.",
]

DOCS = [{"content": c, "source": "quy-che.pdf", "tier": "1", "chunk_id": i} for i, c in enumerate(CONTEXTS)]


# ---------------------------------------------------------------------------
# extract_entities: nhận diện khẳng định
# ---------------------------------------------------------------------------

class TestExtractEntities:
    def test_số_và_mã_và_điều_bị_bắt(self):
        kinds = {e.kind for e in extract_entities("Điều 99 thu 500.000 đồng, lớp CON515.")}
        assert {"legal", "number", "code"} <= kinds

    def test_điều_không_bị_tính_hai_lần_số_trần(self):
        ents = [e for e in extract_entities("Căn cứ Điều 12 của quy chế.")]
        assert [e.kind for e in ents] == ["legal"]
        assert ents[0].text.startswith("Điều 12")

    def test_biến_thể_số_nhóm_ngàn(self):
        assert extract_entities("1.500.000 đồng")[0].keys() >= {"1500000", "1.500.000"}

    def test_end_của_entity_dùng_cho_cloze(self):
        assert Entity("code", "CON915", 4).end == 10

    def test_tên_riêng_là_cụm_viết_hoa_liền_kề(self):
        ents = [e for e in extract_entities("Học phần Công Nghệ Web khai giảng.") if e.kind == "proper"]
        assert any("Công Nghệ Web" in e.text for e in ents)

    def test_cụm_trong_nháp_cho_phép_không_bị_tính_là_thực_thể(self):
        assert [e for e in extract_entities("Danh hiệu Sinh Viên trao cuối năm.") if e.kind == "proper"] == []

    def test_từ_lặp_nguyên_hản_là_lỗi_bộ_sinh_không_phải_khẳng_định(self):
        """Model chép lại đúng khung cảnh hệ thống dán vào block ("[1] x.pdf (Tầng 1)")
        thành "Tầng Tầng 1". 3/4 bản nháp bị guard chặn trong audit r1 có chuỗi này,
        2 ca CHỈ vì nó. Không được thành thực thể — nhưng hai từ KHÁC nhau vẫn phải thành
        cụm (test dưới) để luật này không nới tay với tên riêng bịa."""
        assert [e for e in extract_entities("Quy định (Tầng Tầng 2) áp dụng.") if e.kind == "proper"] == []
        assert [e for e in extract_entities("Theo nguồn Nguồn chính thức.") if e.kind == "proper"] == []
        # PA-2 (duyệt 25-10): stopwords như "Theo" bị LOẠI KHỎI cụm, nhưng cụm thật
        # ("Quyết Định") vẫn phải bị bắt — luật mới chỉ cắt dương-giả, không nới tên riêng.
        proper = [e for e in extract_entities("Theo Quyết Định 1059 của quy chế.") if e.kind == "proper"]
        assert any("Quyết Định" in e.text for e in proper), (
            "PA-2 không được xóa tên riêng thật khỏi tầm ngắm"
        )
        assert all("Theo" not in e.text for e in proper), (
            "PA-2: 'Theo' là hư từ dẫn nhập, không còn được đứng đầu cụm proper-noun"
        )



# ---------------------------------------------------------------------------
# check_grounding: trọng tài deterministic
# ---------------------------------------------------------------------------

class TestCheckGrounding:
    def test_câu_đúng_căn_cứ_cho_score_1(self):
        rep = check_grounding(
            "Học phí khối kỹ thuật là 450.000 đồng/tín chỉ (Điều 3).", CONTEXTS
        )
        assert not rep.fabricated
        assert rep.grounding_score == 1.0

    def test_số_bịa_bị_gọi_tên(self):
        rep = check_grounding("Học phí là 500.000 đồng theo Điều 99.", CONTEXTS)
        bad = {e.text for e in rep.unsupported}
        assert "500.000" in bad
        assert "99" in bad or any("Điều 99" in e.text for e in rep.unsupported)
        assert rep.grounding_score < 1.0

    def test_regression_con515_vs_con915(self):
        """Vụ Q01 trong ab_results: metric cũ chấm đúng, guard phải chặn."""
        rep = check_grounding("Lớp học phần là CON515.", CONTEXTS)
        assert rep.fabricated
        assert [e.text for e in rep.unsupported] == ["CON515"]

    def test_thực_thể_do_người_hỏi_nêu_không_phải_là_bịa(self):
        rep = check_grounding("Lớp CON515 không có trong kế hoạch.", CONTEXTS, question="Lớp CON515 mở chưa?")
        assert not rep.fabricated

    def test_khẳng_định_không_đo_lường_cho_score_None(self):
        rep = check_grounding("Quy chế quy định chung về đào tạo.", CONTEXTS)
        assert rep.entities_total == 0
        assert rep.grounding_score is None

    def test_refusal_không_bị_tính_là_bịa(self):
        rep = check_grounding(REFUSAL_TEXT, [])
        assert not rep.fabricated

    def test_to_dict_chỉ_giữ_chỨ_thực_thể_lỗi(self):
        d = check_grounding("Mức 500.000 đồng.", CONTEXTS).to_dict()
        assert {"grounding_score", "entities_total", "n_supported", "n_unsupported", "unsupported"} <= set(d)
        assert d["unsupported"][0]["kind"] == "number"

    def test_marker_đầu_dòng_không_phải_khẳng_định(self):
        """Audit 23/10: 42/45 'thực thể không căn cứ' là số thứ tự markdown."""
        answer = "Quy trình gồm:\n1. Nộp đơn.\n2. Chờ xét.\n12) Nhận kết quả."
        rep = check_grounding(answer, CONTEXTS)
        assert rep.entities_total == 0
        assert not rep.fabricated

    def test_số_tiền_đầu_dòng_vẫn_phải_chứng_minh(self):
        """Chỉ 'số + chấm/ngoặc đơn' mới là marker; số có đơn vị vẫn bị soi."""
        rep = check_grounding("Các khoản:\n- Học phí 500.000 đồng.", CONTEXTS)
        assert [e.text for e in rep.unsupported] == ["500.000"]

    def test_extra_haystack_cho_phép_số_trong_tên_file(self):
        answer = "Căn cứ mục này (1054-qd-dhag-2020-09-28.pdf)."
        chunk = "Một chunk nói về nội dung khác hoàn toàn, đủ dài để vượt ngưỡng 40 ký tự."
        assert check_grounding(answer, [chunk]).fabricated
        assert not check_grounding(
            answer, [chunk], extra_haystack=["1054-qd-dhag-2020-09-28.pdf"]
        ).fabricated

    def test_thresholds_đọc_env(self, monkeypatch):
        monkeypatch.setenv("ANSWER_GUARD_MIN_SCORE", "0.9")
        monkeypatch.setenv("ANSWER_GUARD_MAX_UNSUPPORTED", "3")
        assert refusal_thresholds() == (0.9, 3)

    def test_thresholds_lỗi_env_quy_về_mặc_định(self, monkeypatch):
        monkeypatch.setenv("ANSWER_GUARD_MIN_SCORE", "abc")
        assert refusal_thresholds()[0] == 0.6

    def test_is_enough_evidence(self):
        assert is_enough_evidence(CONTEXTS)
        assert not is_enough_evidence([])
        assert not is_enough_evidence(["quá ngắn"])


# ---------------------------------------------------------------------------
# guard_qwen_answer: 1 lượt tự sửa, vẫn sai thì từ chối
# ---------------------------------------------------------------------------

class TestGuardQwenAnswer:
    def test_câu_đ_căn_cứ_không_gọi_lại(self):
        calls = []

        def fn(p):
            calls.append(p)
            return ""

        out = guard_qwen_answer(
            text="Học phí là 450.000 đồng/tín chỉ.",
            question="Học phí?",
            docs=DOCS,
            generate_fn=fn,
            prompt="PROMPT",
        )
        assert out == "Học phí là 450.000 đồng/tín chỉ."
        assert calls == []

    def test_lượt_sửa_đúng_căn_cứ_được_chấp_nhận(self):
        seen = []

        def fn(p):
            seen.append(p)
            return "Học phí là 450.000 đồng/tín chỉ."

        out = guard_qwen_answer(
            text="Học phí là 500.000 đồng.", question="Học phí?", docs=DOCS,
            generate_fn=fn, prompt="PROMPT GỐC",
        )
        assert out == "Học phí là 450.000 đồng/tín chỉ."
        assert len(seen) == 1
        assert "CẢNH BÁO KIỂM CHỨNG" in seen[0] and "500.000" in seen[0]

    def test_vẫn_sai_sau_lượt_sửa_thì_từ_chối_chuẩn(self):
        def fn(p):
            return "Học phí là 700.000 đồng."

        out = guard_qwen_answer(
            text="Học phí là 500.000 đồng.", question="Học phí?", docs=DOCS,
            generate_fn=fn, prompt="PROMPT",
        )
        assert out == REFUSAL_TEXT

    def test_generate_fn_ném_lỗi_thì_từ_chối_an_toàn(self):
        def fn(p):
            raise RuntimeError("ollama overloaded")

        assert guard_qwen_answer(
            text="Học phí 500.000 đồng.", question="?", docs=DOCS,
            generate_fn=fn, prompt="P",
        ) == REFUSAL_TEXT

    def test_tên_file_trong_docs_được_tính_là_căn_cứ(self):
        """Pipeline tự inject tên văn bản vào cuối câu trả lời — guard không được
        coi số trong tên file là chữ model bịa."""
        docs = [{"content": "Nội dung chunk không chứa mã quyết định.", "source": "1054-qd-dhag-2020-09-28.pdf",
                 "tier": "1", "chunk_id": 1}]
        out = guard_qwen_answer(
            text="Căn cứ (1054-qd-dhag-2020-09-28.pdf).", question="Căn cứ nào?",
            docs=docs, generate_fn=lambda p: "không dùng tới", prompt="P", log=lambda *a: None,
        )
        assert out == "Căn cứ (1054-qd-dhag-2020-09-28.pdf)."

    def test_trọng_tài_lỗi_thì_không_chặn(self, monkeypatch):
        import src.answer_guard as ag

        def boom(*a, **k):
            raise RuntimeError("bug trong guard")

        monkeypatch.setattr(ag, "check_grounding", boom)
        out = guard_qwen_answer(
            text="Học phí 500.000 đồng.", question="?", docs=DOCS,
            generate_fn=lambda p: "", prompt="P", log=lambda *a: None,
        )
        assert out == "Học phí 500.000 đồng."


# ---------------------------------------------------------------------------
# answer_guard_enabled + wiring vào QwenGenerator
# ---------------------------------------------------------------------------

class ScriptedClient:
    instances = []

    def __init__(self, host=None, timeout=None):
        self.calls = []
        ScriptedClient.instances.append(self)

    def generate(self, model=None, prompt=None, options=None, stream=False):
        self.calls.append(prompt)
        return self.script.pop(0) if self.script else {"response": "hết kịch bản"}

    script = []


@pytest.fixture()
def scripted(monkeypatch):
    ScriptedClient.instances = []
    ScriptedClient.script = []
    monkeypatch.setattr(gen_module.ollama, "Client", ScriptedClient)
    return ScriptedClient


@pytest.fixture()
def qwen(monkeypatch, tmp_path):
    monkeypatch.setenv("GENERATION_CACHE_DIR", str(tmp_path / "cache"))
    return QwenGenerator(use_cache=True)


class TestEnabledFlag:
    def test_mặc_định_tắt(self, monkeypatch):
        monkeypatch.delenv("ENABLE_ANSWER_GUARD", raising=False)
        assert answer_guard_enabled() is False

    @pytest.mark.parametrize("val", ["1", "true", "YES", " on "])
    def test_các_cách_bật(self, monkeypatch, val):
        monkeypatch.setenv("ENABLE_ANSWER_GUARD", val)
        assert answer_guard_enabled() is True


class TestGeneratorWiring:
    def test_guard_tắt_gi_nguyên_hành_vi_cũ(self, scripted, qwen, monkeypatch):
        monkeypatch.delenv("ENABLE_ANSWER_GUARD", raising=False)
        scripted.script = [{"response": "Học phí là 500.000 đồng theo Điều 99."}]
        out = qwen.generate_answer("Học phí?", DOCS)
        assert out.startswith("Học phí là 500.000 đồng theo Điều 99.")
        assert sum(len(c.calls) for c in scripted.instances) == 1  # không retry

    def test_guard_bật_chặn_câu_bịa_v_v_từ_chối(self, scripted, qwen, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_GUARD", "1")
        scripted.script = [
            {"response": "Học phí là 500.000 đồng theo Điều 99."},   # bịa
            {"response": "Học phí là 800.000 đồng."},                 # vẫn bịa
        ]
        out = qwen.generate_answer("Học phí?", DOCS)
        assert REFUSAL_TEXT in out
        assert "500.000" not in out and "800.000" not in out
        assert sum(len(c.calls) for c in scripted.instances) == 2

    def test_guard_bật_cho_lượt_tự_sủa_đúng_đi_qua(self, scripted, qwen, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_GUARD", "1")
        scripted.script = [
            {"response": "Lớp học phần là CON515."},
            {"response": "Lớp học phần là CON915."},
        ]
        out = qwen.generate_answer("Lớp nào?", DOCS)
        assert "CON915" in out and "CON515" not in out
        retry_prompt = scripted.instances[-1].calls[-1]
        assert "CẢNH BÁO KIỂM CHỨNG" in retry_prompt

    def test_guard_bật_lưu_cache_sau_khi_đã_kiểm_chứng(self, scripted, qwen, monkeypatch, tmp_path):
        monkeypatch.setenv("ENABLE_ANSWER_GUARD", "1")
        scripted.script = [
            {"response": "Học phí là 500.000 đồng."},
            {"response": "Học phí là 700.000 đồng."},
        ]
        first = qwen.generate_answer("Học phí?", DOCS)
        calls_before = sum(len(c.calls) for c in scripted.instances)
        second = qwen.generate_answer("Học phí?", DOCS)
        assert first == second
        assert sum(len(c.calls) for c in scripted.instances) == calls_before  # trúng cache
        entry = json.loads(next((tmp_path / "cache").glob("*.json")).read_text(encoding="utf-8"))
        assert REFUSAL_TEXT in entry["answer"]  # cache KHÔNG lưu câu bịa

    def test_guard_bật_không_động_vào_từ_chối_ngoại_phạm_vi(self, scripted, qwen, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_GUARD", "1")
        scripted.script = [{"response": REFUSAL_TEXT}]
        assert qwen.generate_answer("Câu hỏi ngoài phạm vi?", DOCS, question_type="NGOAI_PHAM_VI") == REFUSAL_TEXT
        assert sum(len(c.calls) for c in scripted.instances) == 1
