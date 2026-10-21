# -*- coding: utf-8 -*-
"""Unit test P4.1 — thống kê chế độ A/B của src/evaluation.py (offline 100%).

Fake entries + fake pipeline: kiểm tra classification_stats (fold, bỏ expected rỗng),
group_metrics, false_refusal_stats, is_skipped_no_gt, estimate_requests (cache tmp)
và việc evaluate_question ghi predicted_labels/retrieval_config vào per-question.
"""

import json

import src.evaluation as ev
from src.evaluation import (
    classification_stats,
    estimate_requests,
    evaluate_question,
    expected_generator_cache_model,
    false_refusal_stats,
    flush_partial_results,
    group_metrics,
    is_skipped_no_gt,
    judge_faithfulness,
    load_resumable_entries,
)
from src.generator import quota_error_kind


def make_entry(
    id="Q01",
    error=None,
    predicted=None,
    expected_type="TRA_CUU",
    category="chương trình đào tạo",
    refusal_expected=False,
    is_refusal=False,
    hit3=True,
    hit5=True,
    hit6=True,
    hit_k=True,
    rr=1.0,
    cit_f1=None,
    faith=0.9,
):
    ok = error is None
    return {
        "id": id,
        "category": category,
        "error": error,
        "predicted_labels": predicted,
        "expected_question_type": expected_type,
        "generation_scoring": "scored",
        "retrieval": {
            "hit_at_3": hit3 if ok else None,
            "hit_at_5": hit5 if ok else None,
            "hit_at_6": hit6 if ok else None,
            "hit_at_k": hit_k if ok else None,
            "reciprocal_rank": rr,
        },
        "refusal_expected": refusal_expected,
        "is_refusal_answer": is_refusal,
        "citations": {"f1": cit_f1} if (ok and cit_f1 is not None) else None,
        "faithfulness": {"score": faith if ok else None, "error": None},
    }


# ---------------------------------------------------------------------------
# classification_stats: accuracy so GT v3 (fold-insensitive)
# ---------------------------------------------------------------------------

class TestClassificationStats:
    def test_none_when_no_predictions(self):
        assert classification_stats([make_entry(predicted=None)]) is None
        assert classification_stats([]) is None

    def test_perfect_accuracy(self):
        entries = [
            make_entry(predicted={"topic": "chương trình đào tạo", "question_type": "TRA_CUU"}),
            make_entry(id="Q02", predicted={"topic": "học phí", "question_type": "SO_SANH"},
                       expected_type="SO_SANH", category="học phí"),
        ]
        stats = classification_stats(entries)
        assert stats["topic_accuracy"] == 1.0
        assert stats["question_type_accuracy"] == 1.0
        assert stats["n_scored"] == 2

    def test_fold_insensitive(self):
        entries = [make_entry(
            predicted={"topic": "Chương Trình Đào Tạo", "question_type": "tra_cuu"},
        )]
        stats = classification_stats(entries)
        assert stats["topic_accuracy"] == 1.0
        assert stats["question_type_accuracy"] == 1.0

    def test_wrong_prediction_counts(self):
        entries = [
            make_entry(predicted={"topic": "học phí", "question_type": "SO_SANH"}),
            make_entry(id="Q02", predicted={"topic": "học phí", "question_type": "SO_SANH"},
                       expected_type="TRA_CUU", category="học phí"),
        ]
        stats = classification_stats(entries)
        assert stats["topic_accuracy"] == 0.5
        assert stats["question_type_accuracy"] == 0.0

    def test_empty_expected_excluded_not_counted_wrong(self):
        entries = [make_entry(
            predicted={"topic": "học phí", "question_type": "TRA_CUU"},
            expected_type="",  # benchmark không có nhãn → không thể sai
            category="",
        )]
        stats = classification_stats(entries)
        assert stats["n_scored"] == 1
        assert stats["n_topic_scored"] == 0
        assert stats["n_type_scored"] == 0
        assert stats["topic_accuracy"] is None
        assert stats["question_type_accuracy"] is None

    def test_error_entries_excluded(self):
        entries = [make_entry(predicted={"topic": "x", "question_type": "TRA_CUU"}, error=" boom")]
        assert classification_stats(entries) is None


# ---------------------------------------------------------------------------
# group_metrics: Hit/MRR/Citation F1/Faithfulness theo nhóm
# ---------------------------------------------------------------------------

class TestGroupMetrics:
    def test_group_by_predicted_type(self):
        entries = [
            make_entry(id="Q01", predicted={"question_type": "TRA_CUU"}, cit_f1=0.5),
            make_entry(id="Q02", predicted={"question_type": "TRA_CUU"}, cit_f1=1.0),
            make_entry(id="Q03", predicted={"question_type": "SO_SANH"}, hit3=False, rr=0.5),
        ]
        groups = group_metrics(entries, lambda e: (e.get("predicted_labels") or {}).get("question_type"))
        assert set(groups) == {"TRA_CUU", "SO_SANH"}
        tra = groups["TRA_CUU"]
        assert tra["n"] == 2
        assert tra["citation_f1"] == 0.75
        assert tra["hit_at_3"] == 1.0
        so = groups["SO_SANH"]
        assert so["n"] == 1
        assert so["hit_at_3"] == 0.0
        assert so["mrr"] == 0.5

    def test_entries_without_key_excluded(self):
        entries = [make_entry(id="Q01", predicted=None)]
        assert group_metrics(entries, lambda e: (e.get("predicted_labels") or {}).get("question_type")) == {}

    def test_group_by_category(self):
        entries = [
            make_entry(id="Q01", category="học phí", cit_f1=0.8),
            make_entry(id="Q02", category="học phí", faith=0.5),
            make_entry(id="Q03", category="ký túc xá"),
        ]
        groups = group_metrics(entries, lambda e: e.get("category"))
        assert groups["học phí"]["n"] == 2
        assert groups["học phí"]["faithfulness"] == 0.7
        assert groups["ký túc xá"]["n"] == 1

    def test_error_entries_excluded(self):
        entries = [make_entry(id="Q01", predicted={"question_type": "TRA_CUU"}, error="x")]
        assert group_metrics(entries, lambda e: (e.get("predicted_labels") or {}).get("question_type")) == {}


# ---------------------------------------------------------------------------
# false_refusal_stats: câu in_corpus=true bị từ chối oan
# ---------------------------------------------------------------------------

class TestFalseRefusalStats:
    def test_overall_and_by_type(self):
        entries = [
            make_entry(id="Q01", predicted={"question_type": "TRA_CUU"}),
            make_entry(id="Q02", predicted={"question_type": "SO_SANH"}, is_refusal=True),   # bị gán nhầm → từ chối oan
            make_entry(id="Q03", predicted={"question_type": "TRA_CUU"}),
        ]
        stats = false_refusal_stats(entries)
        assert stats["n_in_corpus"] == 3
        assert stats["n_false_refusal"] == 1
        assert stats["overall_rate"] == round(1 / 3, 4)
        assert stats["by_predicted_type"]["SO_SANH"]["n_false_refusal"] == 1
        assert stats["by_predicted_type"]["TRA_CUU"]["n_false_refusal"] == 0

    def test_refusal_expected_and_errors_excluded(self):
        entries = [
            make_entry(id="Q97", refusal_expected=True, is_refusal=True),  # câu ngoài corpus — từ chối ĐÚNG
            make_entry(id="Q98", refusal_expected=True, is_refusal=False, error="boom"),
        ]
        stats = false_refusal_stats(entries)
        assert stats["n_in_corpus"] == 0
        assert stats["overall_rate"] is None

    def test_without_labels_keyed_khong_nhan(self):
        entries = [make_entry(id="Q01", predicted=None, is_refusal=True)]
        stats = false_refusal_stats(entries)
        assert stats["by_predicted_type"]["KHONG_NHAN"]["rate"] == 1.0


# ---------------------------------------------------------------------------
# is_skipped_no_gt: Q96–98 GT trống → bỏ qua chấm GT tường minh
# ---------------------------------------------------------------------------

class TestIsSkippedNoGt:
    def test_ngoai_corpus_empty_gt(self):
        q = {"in_corpus": False, "expected_citations": [], "ground_truth_answer": ""}
        assert is_skipped_no_gt(q) is True

    def test_ngoai_corpus_with_citations_not_skipped(self):
        q = {"in_corpus": False, "expected_citations": ["Điều 7"], "ground_truth_answer": ""}
        assert is_skipped_no_gt(q) is False

    def test_in_corpus_never_skipped(self):
        q = {"in_corpus": True, "expected_citations": [], "ground_truth_answer": ""}
        assert is_skipped_no_gt(q) is False


# ---------------------------------------------------------------------------
# estimate_requests: dry-run ước lượng từ .generation_cache/
# ---------------------------------------------------------------------------

class TestEstimateRequests:
    def test_cache_hit_estimation(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        for query in ("muc thu hoc phi", "diem ren luyen xep loai"):
            (cache / f"{abs(hash(query))}.json").write_text(
                json.dumps({"query": query, "answer": "x"}), encoding="utf-8"
            )
        questions = [
            {"raw_query": "Mức thu học phí", "normalized_query": "mức thu học phí"},
            {"raw_query": "Điểm rèn luyện xếp loại", "normalized_query": "điểm rèn luyện"},  # khớp fold
            {"raw_query": "Câu chưa từng hỏi", "normalized_query": "câu mới"},
        ]
        est = estimate_requests(questions, cache, judge_enabled=True)
        assert est["estimated_cache_hits"] == 2
        assert est["generator_requests_est"] == 1
        assert est["judge_requests_max"] == 3
        assert est["total_est_upper"] == 4

    def test_no_cache_dir_zero_hits(self, tmp_path):
        est = estimate_requests([{"raw_query": "a", "normalized_query": "a"}], tmp_path / "khong-ton-tai", False)
        assert est["estimated_cache_hits"] == 0
        assert est["generator_requests_est"] == 1
        assert est["judge_requests_max"] == 0
        assert est["total_est_upper"] == 1


# ---------------------------------------------------------------------------
# evaluate_question: ghi predicted_labels + retrieval_config (fake pipeline)
# ---------------------------------------------------------------------------

class FakePipeline:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, query, top_k):
        self.calls.append((query, top_k))
        return self.result


def fake_result(labels=None, config=None):
    return {
        "sources": [{"rank": 1, "source": "hoc-phi.pdf", "tier": "1", "chunk_id": 1, "preview": "Điều 7. Mức thu."}],
        "contexts": ["Điều 7. Mức thu học phí."],
        "answer": "Mức thu là X (Điều 7 — hoc-phi.pdf)",
        "normalized_query": "mức thu học phí",
        "retrieval_query": "mức thu học phí",
        "labels": labels,
        "retrieval_config": config,
    }


QUESTION = {
    "id": "Q01",
    "category": "chương trình đào tạo",
    "raw_query": "môn học X quy định thế nào?",
    "normalized_query": "quy định về môn học X",
    "source_document": "hoc-phi.pdf",
    "expected_citations": ["Điều 7"],
    "in_corpus": True,
    "question_type": "TRA_CUU",
    "ground_truth_answer": "quy định tại Điều 7",
}


class TestEvaluateQuestionRecords:
    def test_with_classifier_records_labels(self):
        config = {"top_k": 6, "bm25_weight": 0.5, "chroma_weight": 0.5,
                  "source_filter": ["hoc-phi.pdf"], "enable_subquery": False}
        pipeline = FakePipeline(fake_result(
            labels={"topic": "chương trình đào tạo", "question_type": "TRA_CUU"}, config=config,
        ))
        entry = evaluate_question(pipeline, None, QUESTION, top_k=6, retrieve_k=6)
        assert entry["predicted_labels"] == {"topic": "chương trình đào tạo", "question_type": "TRA_CUU"}
        assert entry["retrieval_config"] == config
        assert entry["expected_question_type"] == "TRA_CUU"
        assert entry["generation_scoring"] == "scored"

    def test_without_classifier_labels_none(self):
        pipeline = FakePipeline(fake_result(labels=None, config=None))
        entry = evaluate_question(pipeline, None, QUESTION, top_k=6, retrieve_k=6)
        assert entry["predicted_labels"] is None
        assert entry["retrieval_config"] is None

    def test_skipped_no_gt_marked_and_refusal_measured(self):
        question = {
            **QUESTION,
            "id": "Q97",
            "in_corpus": False,
            "expected_citations": [],
            "ground_truth_answer": "",
        }
        pipeline = FakePipeline(fake_result(labels=None))
        pipeline.result["answer"] = "Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."
        entry = evaluate_question(pipeline, None, question, top_k=6, retrieve_k=6)
        assert entry["generation_scoring"] == "skipped_no_gt"
        assert entry["is_refusal_answer"] is True       # phép đo hành vi từ chối VẪN chạy
        assert entry["refusal_correct"] is True
        assert entry["citations"] is None               # không chấm theo GT


# ---------------------------------------------------------------------------
# Bước 0 P4.2 — mục 3: estimate_requests lọc entry cache theo model
# ---------------------------------------------------------------------------

class TestEstimateRequestsModelFilter:
    def test_other_model_entries_not_counted(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "a.json").write_text(json.dumps(
            {"model": "qwen2.5:1.5b-instruct", "query": "muc thu hoc phi", "answer": "x"}), encoding="utf-8")
        (cache / "b.json").write_text(json.dumps(
            {"model": "gemini-3.8-flash", "query": "diem ren luyen", "answer": "y"}), encoding="utf-8")
        questions = [
            {"raw_query": "Mức thu học phí", "normalized_query": ""},
            {"raw_query": "Điểm rèn luyện", "normalized_query": ""},
        ]
        est = estimate_requests(questions, cache, True, generator_model="gemini-3.8-flash")
        assert est["estimated_cache_hits"] == 1           # chỉ entry Gemini đúng model được tính
        assert est["cache_entries_other_model"] == 1
        assert est["generator_model"] == "gemini-3.8-flash"
        assert est["generator_requests_est"] == 1

    def test_without_model_filter_counts_all(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "a.json").write_text(json.dumps(
            {"model": "qwen2.5:1.5b-instruct", "query": "muc thu hoc phi", "answer": "x"}), encoding="utf-8")
        est = estimate_requests(
            [{"raw_query": "Mức thu học phí", "normalized_query": ""}], cache, True)
        assert est["estimated_cache_hits"] == 1           # hành vi cũ khi không truyền model


class TestExpectedGeneratorCacheModel:
    def test_gemini_from_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
        monkeypatch.delenv("USE_QWEN_GENERATOR", raising=False)
        assert expected_generator_cache_model(False) == "gemini-3.8-flash"

    def test_gemini_default_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        assert expected_generator_cache_model(False) == ev.DEFAULT_MODEL

    def test_qwen_uses_ollama_model_field(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:1.5b-instruct")
        assert expected_generator_cache_model(True) == "qwen2.5:1.5b-instruct"


# ---------------------------------------------------------------------------
# Bước 0 P4.2 — mục 1: judge 429 theo phút (chờ 60s × 3) / PerDay (dừng lượt)
# ---------------------------------------------------------------------------

class _FakeJudgeResponse:
    def __init__(self, text):
        self.text = text


class _MinuteThenOkJudge:
    """Sai 429-theo-phút `fail_times` lần đầu rồi trả JSON claims hợp lệ."""

    def __init__(self, fail_times=2):
        self.fail_times = fail_times
        self.calls = 0

    def generate_content(self, prompt, generation_config=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("429 Resource has been exhausted (e.g. check quota): requests per minute")
        return _FakeJudgeResponse(json.dumps({"claims": [{"text": "a", "supported": True}]}))


class _AlwaysMinuteJudge:
    def __init__(self):
        self.calls = 0

    def generate_content(self, prompt, generation_config=None):
        self.calls += 1
        raise RuntimeError("429 too many requests per minute")


class _PerDayJudge:
    def __init__(self):
        self.calls = 0

    def generate_content(self, prompt, generation_config=None):
        self.calls += 1
        raise RuntimeError("429 quota exceeded. Quota limit: GenerateRequestsPerDay")


class TestQuotaErrorKind:
    def test_perday(self):
        assert quota_error_kind("429 ... GenerateRequestsPerDay ...") == "perday"
        assert quota_error_kind("limit: per day") == "perday"

    def test_minute(self):
        assert quota_error_kind("429 requests per minute") == "minute"
        assert quota_error_kind("Resource has been exhausted (quota)") == "minute"

    def test_none(self):
        assert quota_error_kind("500 Internal Server Error") is None
        assert quota_error_kind("connection reset") is None


class TestJudgeMinuteAndPerDay:
    def test_minute_retried_then_success(self, monkeypatch):
        monkeypatch.setattr(ev.time, "sleep", lambda s: None)  # không chờ 60s thật
        judge = _MinuteThenOkJudge(fail_times=2)
        score, unsupported, error = judge_faithfulness(judge, ["ngữ cảnh"], "câu trả lời")
        assert score == 1.0 and error == ""
        assert judge.calls == 3                                # 2 lỗi phút + 1 thành công

    def test_minute_gives_up_after_3_retries(self, monkeypatch):
        monkeypatch.setattr(ev.time, "sleep", lambda s: None)
        judge = _AlwaysMinuteJudge()
        score, _, error = judge_faithfulness(judge, ["ngữ cảnh"], "câu trả lời")
        assert score is None
        assert "429 theo phút" in error
        assert judge.calls == 4                                # 1 gọi + 3 retry phút

    def test_perday_no_retry_and_marks_perday(self, monkeypatch):
        monkeypatch.setattr(ev.time, "sleep", lambda s: None)
        judge = _PerDayJudge()
        score, _, error = judge_faithfulness(judge, ["ngữ cảnh"], "câu trả lời")
        assert score is None
        assert "PerDay" in error
        assert judge.calls == 1                                # không retry vô ích


# ---------------------------------------------------------------------------
# Bước 0 P4.2 — mục 2: resume an toàn từ file output cũ
# ---------------------------------------------------------------------------

PREV_BENCHMARK = "data/evaluation/benchmark_100_questions_v3.json"


def _write_prev_run(path, entries, benchmark=PREV_BENCHMARK, with_classifier=False, judge_enabled=True):
    path.write_text(json.dumps({
        "meta": {"benchmark": benchmark, "with_classifier": with_classifier, "judge_enabled": judge_enabled},
        "per_question": entries,
    }, ensure_ascii=False), encoding="utf-8")


class TestLoadResumableEntries:
    def test_keeps_only_complete_entries(self, tmp_path, monkeypatch):
        monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)  # suppress tiếng Việt
        out = tmp_path / "ab.json"
        _write_prev_run(out, [
            {"id": "Q01", "answer": "trả lời", "error": None,
             "faithfulness": {"score": 0.9, "error": None}},
            {"id": "Q97", "answer": "Xin lỗi...", "error": None,
             "faithfulness": {"score": 1.0, "error": "refusal"}},          # từ chối chuẩn — hợp lệ
            {"id": "Q02", "answer": "trả lời", "error": None,
             "faithfulness": {"score": None, "error": "429 PerDay"}},      # judge chưa chấm → chạy lại
            {"id": "Q03", "answer": None, "error": "GeneratorError: x", "faithfulness": {}},
        ])
        resumable = load_resumable_entries(out, PREV_BENCHMARK, False, True)
        assert set(resumable) == {"Q01", "Q97"}

    def test_meta_mismatch_skips_resume(self, tmp_path, monkeypatch):
        monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
        out = tmp_path / "ab.json"
        _write_prev_run(out, [
            {"id": "Q01", "answer": "trả lời", "error": None,
             "faithfulness": {"score": 0.9, "error": None}}],
            benchmark="data/evaluation/khac.json")
        assert load_resumable_entries(out, PREV_BENCHMARK, False, True) == {}

    def test_with_classifier_flag_must_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
        out = tmp_path / "ab.json"
        _write_prev_run(out, [
            {"id": "Q01", "answer": "trả lời", "error": None,
             "faithfulness": {"score": 0.9, "error": None}}], with_classifier=True)
        assert load_resumable_entries(out, PREV_BENCHMARK, False, True) == {}
        assert set(load_resumable_entries(out, PREV_BENCHMARK, True, True)) == {"Q01"}

    def test_judge_mode_must_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
        out = tmp_path / "ab.json"
        _write_prev_run(out, [
            {"id": "Q01", "answer": "trả lời", "error": None,
             "faithfulness": {"score": 0.9, "error": None}}], judge_enabled=True)
        # Lượt mới judge tắt: entry cũ judge bật → không resume
        assert load_resumable_entries(out, PREV_BENCHMARK, False, False) == {}
        # Lượt mới judge bật: entry cũ judge bật → resume được
        assert set(load_resumable_entries(out, PREV_BENCHMARK, False, True)) == {"Q01"}

    def test_no_judge_mode_only_requires_answer(self, tmp_path, monkeypatch):
        monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
        out = tmp_path / "ab.json"
        _write_prev_run(out, [
            {"id": "Q01", "answer": "trả lời", "error": None,
             "faithfulness": {"score": None, "error": None}},  # judge tắt → không cần faithfulness score
            {"id": "Q02", "answer": None, "error": "GeneratorError: x",
             "faithfulness": {"score": None, "error": None}},
        ], judge_enabled=False)
        resumable = load_resumable_entries(out, PREV_BENCHMARK, False, False)
        assert set(resumable) == {"Q01"}

    def test_missing_file_empty(self, tmp_path):
        assert load_resumable_entries(tmp_path / "khong-ton-tai.json", PREV_BENCHMARK, False, True) == {}

    def test_corrupt_file_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
        out = tmp_path / "hong.json"
        out.write_text("{không phải json", encoding="utf-8")
        assert load_resumable_entries(out, PREV_BENCHMARK, False, True) == {}


# ---------------------------------------------------------------------------
# Bước 0 P4.2 — mục 3b: flush JSON sau mỗi câu (chống mất kết quả khi bị kill)
# ---------------------------------------------------------------------------

class TestFlushPartialResults:
    def test_roundtrip_with_resume(self, tmp_path):
        out = tmp_path / "partial.json"
        meta = {"benchmark": PREV_BENCHMARK, "with_classifier": False, "judge_enabled": True, "partial": True}
        entries = [
            {**make_entry(id="Q01"), "answer": "trả lời"},   # đủ điều kiện resume
            make_entry(id="Q02", error="GeneratorError: x"),  # câu lỗi → chạy lại
        ]
        flush_partial_results(out, meta, entries, top_k=6)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["meta"]["partial"] is True
        assert [e["id"] for e in data["per_question"]] == ["Q01", "Q02"]
        # File tạm giữa chừng vẫn dùng được cho resume: chỉ nhặt entry trọn vẹn.
        assert set(load_resumable_entries(out, PREV_BENCHMARK, False, True)) == {"Q01"}

    def test_final_write_clears_partial_flag(self, tmp_path):
        out = tmp_path / "final.json"
        meta = {"benchmark": PREV_BENCHMARK, "with_classifier": False, "judge_enabled": True}
        flush_partial_results(out, meta, [make_entry(id="Q01")], top_k=6, partial=False)
        assert json.loads(out.read_text(encoding="utf-8"))["meta"]["partial"] is False

    def test_error_entry_does_not_crash_aggregate(self, tmp_path):
        out = tmp_path / "err.json"
        flush_partial_results(out, {"benchmark": PREV_BENCHMARK, "judge_enabled": True}, [make_entry(id="Q02", error="x")], top_k=6)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["aggregates"]["n_ok"] == 0  # câu lỗi bị loại khỏi chỉ số, không crash
