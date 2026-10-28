"""Test guardrail chống lệch nghĩa và các hàm thuần của src/generation/local_slm.py."""

from src.generation.local_slm import (
    LocalSLM,
    build_normalize_prompt,
    guardrail_violation,
)


def test_guardrail_accepts_legit_normalization():
    raw = "Ê ad, tui bị ĐTBHK dưới 1.0 thì có bị đuổi học luôn không?"
    norm = "Điểm trung bình học kỳ dưới 1.0 có bị buộc thôi học không?"
    assert guardrail_violation(raw, norm) is None


def test_guardrail_accepts_all_fewshot_pairs():
    pairs = [
        ("cho e hỏi mún xin hoãn học phí thì lm đơn j nộp ở đâu z ạ",
         "Sinh viên cần làm đơn gì và nộp ở đâu để được gia hạn học phí?"),
        ("rớt môn tiên quyết r thì có đc đkí môn đó lại hk ad",
         "Sinh viên chưa đạt môn học tiên quyết có được đăng ký học lại môn đó không?"),
        ("quy che danh hieu Sinh vien 5 tot",
         "Sinh viên cần đạt tiêu chuẩn gì để được xét danh hiệu Sinh viên 5 tốt?"),
    ]
    for raw, norm in pairs:
        assert guardrail_violation(raw, norm) is None


def test_guardrail_flags_observed_topic_drift():
    raw = "Quy ché danh hieu ' 'Sinh vién 5 tot\""
    norm = "Sinh viên có điểm trung bình học kỳ dưới 2.0 có bị buộc thôi học không?"
    reason = guardrail_violation(raw, norm)
    assert reason is not None
    assert "5" in reason


def test_guardrail_flags_number_mutation():
    raw = "ĐTBHK dưới 1.0 có bị đuổi không?"
    norm = "Điểm trung bình học kỳ dưới 2.0 có bị buộc thôi học không?"
    reason = guardrail_violation(raw, norm)
    assert reason is not None
    assert "1.0" in reason


def test_guardrail_flags_invented_numbers():
    raw = "cảnh báo học vụ là gì?"
    norm = "Cảnh báo học vụ theo Điều 12 gồm những mức nào?"
    reason = guardrail_violation(raw, norm)
    assert reason is not None
    assert "12" in reason


def test_guardrail_decimal_comma_equals_dot():
    raw = "đtbhk dưới 1,0 có bị đuổi không?"
    norm = "Điểm trung bình học kỳ dưới 1.0 có bị buộc thôi học không?"
    assert guardrail_violation(raw, norm) is None


def test_guardrail_flags_unrelated_question():
    raw = "học phí có được gia hạn không?"
    norm = "Sinh viên vi phạm kỷ luật sẽ bị xử lý như thế nào?"
    assert guardrail_violation(raw, norm) is not None


def test_prompt_contains_entity_preservation_rules():
    prompt = build_normalize_prompt("câu hỏi thử")
    assert "ĐTBHK" in prompt
    assert "cảnh báo học vụ" in prompt
    assert "mã học phần" in prompt
    assert "Điểm trung bình học kỳ dưới 1.0 có bị buộc thôi học không?" in prompt
    assert "Sinh viên 5 tốt" in prompt
    assert 'Câu hỏi thô: "câu hỏi thử"' in prompt


def _make_slm() -> LocalSLM:
    return LocalSLM(host="http://localhost:9")  # không cần Ollama thật


def test_normalize_query_falls_back_on_guardrail(monkeypatch, capsys):
    slm = _make_slm()
    raw = "Quy ché danh hieu ' 'Sinh vién 5 tot\""
    drift = "Sinh viên có điểm trung bình học kỳ dưới 2.0 có bị buộc thôi học không?"
    monkeypatch.setattr(slm, "generate", lambda prompt, **kw: drift)

    assert slm.normalize_query(raw) == raw.strip()
    out = capsys.readouterr().out
    assert "[LocalSLM-Guardrail] Phát hiện Qwen làm lệch nghĩa — fallback về câu gốc" in out


def test_normalize_query_returns_normalized_when_guardrail_passes(monkeypatch, capsys):
    slm = _make_slm()
    raw = "Ê ad, tui bị ĐTBHK dưới 1.0 thì có bị đuổi học luôn không?"
    norm = "Điểm trung bình học kỳ dưới 1.0 có bị buộc thôi học không?"
    monkeypatch.setattr(slm, "generate", lambda prompt, **kw: norm)

    assert slm.normalize_query(raw) == norm
    assert "[LocalSLM-Guardrail]" not in capsys.readouterr().out
