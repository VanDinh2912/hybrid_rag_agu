"""Unit test cho src/core/classifier.py — 100% offline, không Ollama, không mạng.

Phủ 6 nhóm theo prompts/P2_2_classifier_tests.md:
1. Parser JSON: hợp lệ / bọc markdown fence / text thừa / hỏng hoàn toàn.
2. Guardrail: nhãn lạ → bảng từ khóa; không khớp → lớp 3 (topic=None, TRA_CUU).
3. So khớp không dấu: nhãn có/không dấu khớp nhau qua fold().
4. Suy giảm mềm: Ollama ném lỗi / khởi tạo lỗi → fallback, đúng 1 lần gọi (không retry).
5. Few-shot: đủ 14 chủ đề + 4 loại; id ví dụ khớp nguyên văn benchmark v3.
6. Schema: classify_query trả đúng 3 khóa, đúng kiểu dữ liệu.
"""

import json
import re
from pathlib import Path

import pytest

from src.core import classifier
from src.core.classifier import (
    DEFAULT_MODEL,
    DEFAULT_NUM_PREDICT,
    DEFAULT_QUESTION_TYPE,
    DEFAULT_TIMEOUT,
    FEW_SHOT_IDS,
    FEW_SHOT_SAMPLES,
    QUESTION_TYPES,
    TOPICS,
    build_classifier_prompt,
    build_few_shot_examples,
    classify_query,
    extract_json_object,
)
from src.generation.local_slm import LocalSLMError


@pytest.fixture
def install_slm(monkeypatch):
    """Cài FakeSLM vào chỗ classifier.LocalSLM.

    Trả về recorder chứa kwargs khởi tạo (model_name, timeout, num_predict,
    max_retries) và số lần generate() được gọi — để kiểm chứng không retry.
    """

    def _install(raw="", exc=None, init_exc=None):
        state = {"kwargs": None, "calls": 0}

        class _FakeSLM:
            def __init__(self, **kwargs):
                if init_exc is not None:
                    raise init_exc
                state["kwargs"] = kwargs

            def generate(self, prompt, temperature=0.0):
                state["calls"] += 1
                if exc is not None:
                    raise exc
                return raw

        monkeypatch.setattr(classifier, "LocalSLM", _FakeSLM)
        return state

    return _install


class TestExtractJsonObject:
    def test_valid_json(self):
        raw = '{"topic": "học phí", "question_type": "THU_TUC"}'
        assert extract_json_object(raw) == {"topic": "học phí", "question_type": "THU_TUC"}

    def test_markdown_fence(self):
        raw = '```json\n{"topic": null, "question_type": "NGOAI_PHAM_VI"}\n```'
        assert extract_json_object(raw) == {"topic": None, "question_type": "NGOAI_PHAM_VI"}

    def test_extra_text_before_and_after(self):
        raw = 'Dấu hiệu: ngoài quy chế\nA: {"topic": "học phí", "question_type": "TRA_CUU"}'
        assert extract_json_object(raw) == {"topic": "học phí", "question_type": "TRA_CUU"}

    def test_broken_completely(self):
        assert extract_json_object("xin chào bạn") is None
        assert extract_json_object("") is None

    def test_first_block_broken_then_valid_block(self):
        raw = '{"a": } {"topic": "học phí", "question_type": "TRA_CUU"}'
        assert extract_json_object(raw) == {"topic": "học phí", "question_type": "TRA_CUU"}

    def test_brace_inside_string_value(self):
        raw = '{"topic": "a}b", "question_type": "TRA_CUU"}'
        assert extract_json_object(raw)["topic"] == "a}b"

    def test_non_dict_json_returns_none(self):
        assert extract_json_object("[1, 2, 3]") is None
        assert extract_json_object('"chuỗi"') is None


class TestGuardrailLayers:
    def test_valid_json_used_directly(self, install_slm, capsys):
        raw = '{"topic": "học phí", "question_type": "SO_SANH"}'
        install_slm(raw)
        result = classify_query("Đơn giá học phí so với tín chỉ lý thuyết?")
        assert result["topic"] == "học phí"
        assert result["question_type"] == "SO_SANH"
        assert result["raw_response"] == raw
        assert "[Classifier] Cảnh báo" not in capsys.readouterr().out

    def test_unknown_labels_fall_to_keyword_table(self, install_slm, capsys):
        install_slm('{"topic": "bịa đặt", "question_type": "SAI"}')
        result = classify_query("Hồ sơ miễn giảm học phí gồm những giấy tờ gì?")
        assert result["topic"] == "học phí"
        assert result["question_type"] == "THU_TUC"
        assert "bảng từ khóa" in capsys.readouterr().out

    def test_no_keyword_match_falls_to_layer3(self, install_slm):
        install_slm('{"topic": "bịa đặt", "question_type": "SAI"}')
        result = classify_query("Thứ sáu ngày 13 có phải ngày xui xẻo không?")
        assert result["topic"] is None
        assert result["question_type"] == DEFAULT_QUESTION_TYPE

    def test_valid_topic_kept_while_type_keyword_filled(self, install_slm):
        install_slm('{"topic": "học phí", "question_type": "SAI"}')
        result = classify_query("Thủ tục xin gia hạn nộp học phí?")
        assert result["topic"] == "học phí"
        assert result["question_type"] == "THU_TUC"

    def test_broken_json_falls_to_keyword_table(self, install_slm, capsys):
        install_slm("xin chào, tôi không trả json")
        result = classify_query("Quy chế danh hiệu Sinh viên 5 tốt?")
        assert result["topic"] == "sinh viên 5 tốt"
        assert result["question_type"] == DEFAULT_QUESTION_TYPE
        assert "không trả về JSON hợp lệ" in capsys.readouterr().out

    def test_null_topic_is_valid_no_warning(self, install_slm, capsys):
        install_slm('{"topic": null, "question_type": "NGOAI_PHAM_VI"}')
        result = classify_query("Xin visa du học Nhật Bản cần giấy tờ gì?")
        assert result["topic"] is None
        assert result["question_type"] == "NGOAI_PHAM_VI"
        assert "[Classifier] Cảnh báo" not in capsys.readouterr().out


class TestFoldMatching:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("HOC PHI", "học phí"),
            ("hoc phi", "học phí"),
            ("Chương Trình Đào Tạo", "chương trình đào tạo"),
            ("chương trình đào tạo", "chương trình đào tạo"),
            ("Sinh viên 5 tot", "sinh viên 5 tốt"),
        ],
    )
    def test_canonical_topic_accent_insensitive(self, raw, expected):
        assert classifier._canonical_topic(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("thu-tuc", "THU_TUC"),
            ("THU TUC", "THU_TUC"),
            ("tra cứu", "TRA_CUU"),
            ("ngoai pham vi", "NGOAI_PHAM_VI"),
            ("so_sanh", "SO_SANH"),
        ],
    )
    def test_canonical_question_type(self, raw, expected):
        assert classifier._canonical_question_type(raw) == expected

    def test_unknown_labels_return_none(self):
        assert classifier._canonical_topic("bịa đặt") is None
        assert classifier._canonical_topic(None) is None
        assert classifier._canonical_topic(123) is None
        assert classifier._canonical_question_type("SAI") is None
        assert classifier._canonical_question_type(None) is None

    def test_foldable_labels_accepted_end_to_end(self, install_slm, capsys):
        install_slm(raw='{"topic": "HOC PHI", "question_type": "thu-tuc"}')
        result = classify_query("Học phí ngành CNTT?")
        assert result["topic"] == "học phí"
        assert result["question_type"] == "THU_TUC"
        assert "[Classifier] Cảnh báo" not in capsys.readouterr().out


class TestKeywordFallbackAnchors:
    """Thứ tự bảng từ khóa phải ưu tiên đúng các chủ đề dễ nhầm."""

    @pytest.mark.parametrize(
        "query,expected_topic",
        [
            ("thực tập chuyên đề cần nộp tài liệu nghiệm thu gì", "thực tập chuyên đề"),
            ("thực tập tốt nghiệp bao nhiêu tuần", "thực tập tốt nghiệp"),
            ("khen thưởng cấp ĐHQG-HCM do ai chi trả", "khen thưởng cấp ĐHQG"),
            ("quy chế danh hiệu Sinh viên 5 tốt", "sinh viên 5 tốt"),
            ("danh hiệu Sinh viên Xuất sắc năm học", "khen thưởng sinh viên"),
        ],
    )
    def test_anchor_priority(self, install_slm, query, expected_topic):
        install_slm(raw="{}")  # JSON rỗng → buộc rơi xuống bảng từ khóa
        assert classify_query(query)["topic"] == expected_topic


class TestSoftDegradation:
    def test_ollama_error_returns_fallback_and_single_call(self, install_slm, capsys):
        state = install_slm(exc=LocalSLMError("boom"))
        result = classify_query("Học phí bao nhiêu?")
        assert result == {"topic": None, "question_type": "TRA_CUU", "raw_response": ""}
        assert state["calls"] == 1  # không retry vô hạn
        assert "fallback" in capsys.readouterr().out

    def test_init_error_returns_fallback(self, install_slm):
        install_slm(init_exc=RuntimeError("host sai định dạng"))
        result = classify_query("Học phí bao nhiêu?")
        assert result["topic"] is None
        assert result["question_type"] == DEFAULT_QUESTION_TYPE
        assert result["raw_response"] == ""

    def test_unexpected_exception_also_caught(self, install_slm):
        install_slm(exc=ValueError("lỗi bất ngờ"))
        result = classify_query("Học phí bao nhiêu?")
        assert result["question_type"] == DEFAULT_QUESTION_TYPE

    def test_timeout_env_passed_to_slm(self, install_slm, monkeypatch):
        monkeypatch.setenv("CLASSIFIER_TIMEOUT", "3.5")
        state = install_slm(raw='{"topic": "học phí", "question_type": "TRA_CUU"}')
        classify_query("Học phí?")
        assert state["kwargs"]["timeout"] == 3.5
        # Cấu hình chống retry + ngân sách token phải được truyền xuống LocalSLM.
        assert state["kwargs"]["max_retries"] == 0
        assert state["kwargs"]["num_predict"] == DEFAULT_NUM_PREDICT

    @pytest.mark.parametrize("bad_value", ["abc", "0", "-5"])
    def test_invalid_timeout_falls_back_to_default(self, install_slm, monkeypatch, bad_value):
        monkeypatch.setenv("CLASSIFIER_TIMEOUT", bad_value)
        state = install_slm(raw='{"topic": "học phí", "question_type": "TRA_CUU"}')
        classify_query("Học phí?")
        assert state["kwargs"]["timeout"] == DEFAULT_TIMEOUT

    def test_model_resolution_precedence(self, install_slm, monkeypatch):
        monkeypatch.delenv("CLASSIFIER_MODEL", raising=False)
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        state = install_slm(raw="{}")
        classify_query("abc")
        assert state["kwargs"]["model_name"] == DEFAULT_MODEL
        monkeypatch.setenv("OLLAMA_MODEL", "ollama-x")
        classify_query("abc")
        assert state["kwargs"]["model_name"] == "ollama-x"
        monkeypatch.setenv("CLASSIFIER_MODEL", "classifier-y")
        classify_query("abc")
        assert state["kwargs"]["model_name"] == "classifier-y"


class TestFewShot:
    def test_examples_cover_14_topics_and_4_types(self):
        few_shot = build_few_shot_examples()
        labels = [
            json.loads(line[3:])
            for line in few_shot.splitlines()
            if line.startswith("A: ")
        ]
        assert len(labels) == len(FEW_SHOT_SAMPLES) == 16
        assert few_shot.count("Q: ") == 16
        assert few_shot.count("Dấu hiệu: ") == 16
        topics = {label["topic"] for label in labels}
        types = {label["question_type"] for label in labels}
        assert topics == set(TOPICS)  # đủ 14 chủ đề, không thừa nhãn lạ
        assert types == set(QUESTION_TYPES)  # đủ 4 loại
        for question_type in ("SO_SANH", "THU_TUC", "NGOAI_PHAM_VI"):
            count = sum(label["question_type"] == question_type for label in labels)
            assert 2 <= count <= 3  # spec P2.1: 2–3 ví dụ mỗi loại hiếm

    def test_example_ids_match_benchmark_v3(self):
        bench_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "evaluation"
            / "benchmark_100_questions_v3.json"
        )
        questions = {
            q["id"]: q
            for q in json.loads(bench_path.read_text(encoding="utf-8"))["questions"]
        }
        # Danh sách id ghi cứng phải khớp thứ tự dữ liệu few-shot (chống lệch comment).
        assert tuple(sample[0] for sample in FEW_SHOT_SAMPLES) == FEW_SHOT_IDS
        for question_id, topic, question_type, raw_query in FEW_SHOT_SAMPLES:
            assert question_id in questions, f"{question_id} không có trong v3"
            source = questions[question_id]
            assert source["category"] == topic
            assert source["question_type"] == question_type
            assert source["raw_query"] == raw_query

    def test_prompt_contains_query_and_priority_reminder(self):
        prompt = build_classifier_prompt('Câu hỏi "thử" nghiệm')
        assert 'Câu hỏi: "Câu hỏi \'thử\' nghiệm"' in prompt
        assert "NHẮC LẠI" in prompt
        assert "NGOAI_PHAM_VI" in prompt
        assert "Dấu hiệu:" in prompt


class TestSchema:
    def test_result_has_exactly_3_keys_with_right_types(self, install_slm):
        install_slm(raw='{"topic": "học phí", "question_type": "TRA_CUU"}')
        result = classify_query("Học phí ngành CNTT?")
        assert set(result.keys()) == {"topic", "question_type", "raw_response"}
        assert isinstance(result["topic"], str)
        assert result["question_type"] in QUESTION_TYPES
        assert isinstance(result["raw_response"], str)

    def test_topic_none_is_allowed(self, install_slm):
        install_slm(raw='{"topic": null, "question_type": "NGOAI_PHAM_VI"}')
        result = classify_query("Xin visa du học?")
        assert set(result.keys()) == {"topic", "question_type", "raw_response"}
        assert result["topic"] is None
        assert result["question_type"] in QUESTION_TYPES

    def test_empty_query_returns_default_without_calling_model(self, install_slm):
        state = install_slm(raw="OUTPUT_KHONG_DUOC_DUNG")
        result = classify_query("   ")
        assert result == {
            "topic": None,
            "question_type": DEFAULT_QUESTION_TYPE,
            "raw_response": "",
        }
        assert state["calls"] == 0

    def test_non_str_query_raises_type_error(self):
        with pytest.raises(TypeError):
            classify_query(None)
