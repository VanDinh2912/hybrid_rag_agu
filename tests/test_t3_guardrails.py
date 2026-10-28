"""Kiểm thử T3 — `ENABLE_DECOUPLED_REFUSAL` + `ENABLE_EVIDENCE_SELECTION` (stub generator).

Bốn nhóm của đề bài (24-10):
  A. Cờ TẮT — ca quan trọng nhất: 30 lượt `pipeline.run` cố định phải cho đầu ra
     **byte-identical** với golden chụp từ bản cây code TRƯỚC khi nối T3
     (`git archive HEAD` = f492f05; tại đó `src/core/pipeline.py` chưa có dòng T3 nào — đã kiểm
     bằng grep), và cache key không đổi.
  B. Decoupled refusal: prompt mới không còn chỉ dẫn từ chối (regex có răng), câu bịa bị
     guard chặn -> trả ĐÚNG một chuỗi canonical (so `==`), câu có căn cứ thì trả lời,
     luật pre chặn mà KHÔNG gọi generator (đếm = 0), ngưỡng đọc từ cấu hình với ba ca
     biên (đúng bằng / ngay dưới / ngay trên), guard chạy trước khi ghi cache, cache key
     chứa PROMPT_VERSION mới, và ba ca bất thường.
  C. Evidence selection: 3–5 câu, thứ tự theo quy tắc đã đăng ký, câu chứa thực thể phía
     câu hỏi được ưu tiên, deterministic kể cả khi điểm bằng nhau, mọi câu là chuỗi con
     nguyên văn của ngữ cảnh.
  D. Chống bịa: 10 câu hỏi "không có đáp án" tổng hợp — cờ BẬT phải từ chối cả 10.

Nguyên tắc Test Engineer đã áp:
- Không gọi Ollama/ChromaDB/Gemini, không tải model reranker (`sentence_transformers` bị
  chặn bằng module giả); mọi tầng dưới là fake, generator là stub trả chuỗi cố định.
- Test nào mô tả HIỆN TRẠNG chứ không phải hành vi mong đợi đều ghi chữ
  "ĐẶC TẢ HIỆN TRẠNG" ngay trong tên/docstring và được dẫn về `docs/reports/test_T3.md`.
- Thực thể dùng để quyết định luôn lấy từ phía CÂU HỎI (bất biến #6 — không đọc
  `gold_sentence`/`required_entities` của testset ở runtime).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.generation.evidence_selection import (  # noqa: E402
    TIER_ENTITY,
    TIER_KEYWORDS,
    TIER_SOURCE_NAME,
    Reranker,
    evidence_selection_enabled,
    rank_candidates,
    select_evidence,
    sentence_budget,
    split_sentences,
)
from src.generator import (  # noqa: E402
    EXTRACT_ONLY_HEAD,
    EXTRACT_ONLY_PROMPT_VERSION,
    PROMPT_VERSION,
    QwenGenerator,
    REFUSAL_TEXT,
)
from src.generator import build_prompt as gemini_build_prompt  # noqa: E402
from src.generator import effective_prompt_version, looks_like_refusal  # noqa: E402
from src.generation.refusal_policy import (  # noqa: E402
    DEFAULT_MAX_UNSUPPORTED,
    DEFAULT_MIN_ENTITY_COVERAGE,
    DEFAULT_MIN_GROUNDING,
    DEFAULT_MIN_RRF_NORM,
    DEFAULT_MIN_TOKEN_OVERLAP,
    REFUSAL_REASON_EMPTY,
    REFUSAL_REASON_MODEL_REFUSES,
    REFUSAL_REASON_NO_EVIDENCE,
    REFUSAL_REASON_OFF_TOPIC,
    REFUSAL_REASON_UNGROUNDED,
    REFUSAL_REASON_WEAK_RANK,
    chunk_relevance,
    decide_post_generation,
    decide_pre_generation,
    decoupled_refusal_enabled,
    rrf_norm,
    thresholds,
)
from src.text_utils import fold  # noqa: E402

GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "t3_off_30items_head_f492f05.json"

ALL_FLAGS = (
    "ENABLE_DECOUPLED_REFUSAL", "ENABLE_EVIDENCE_SELECTION", "ENABLE_CLASSIFIER",
    "ENABLE_ANSWER_RESCUE", "ENABLE_ANSWER_GUARD", "ENABLE_RERANKER", "GENERATION_CACHE",
    "GENERATION_CACHE_DIR",
    "DEC_MIN_ENTITY_COVERAGE", "DEC_MIN_TOKEN_OVERLAP", "DEC_MIN_RRF_NORM",
    "DEC_MIN_GROUNDING", "DEC_MAX_UNSUPPORTED",
    "EV_MIN_SENTENCES", "EV_MAX_SENTENCES", "EV_MIN_KEYWORD_HITS", "EVIDENCE_RERANKER",
    "OLLAMA_MODEL", "OLLAMA_HOST", "BM25_WEIGHT", "CHROMA_WEIGHT",
)

OFF_LEVERS = ("ENABLE_CLASSIFIER", "ENABLE_ANSWER_RESCUE", "ENABLE_ANSWER_GUARD",
              "ENABLE_RERANKER", "GENERATION_CACHE")


@pytest.fixture(autouse=True)
def _env_and_reranker_sandbox():
    """Mỗi test chạy trong môi trường cờ sạch; reranker toàn cục reset; cấm tải model thật."""
    saved = dict(os.environ)
    for key in ALL_FLAGS:
        os.environ.pop(key, None)
    for key in OFF_LEVERS:
        os.environ[key] = "0"
    broken = types.ModuleType("sentence_transformers")
    broken.CrossEncoder = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("test môi trường: cấm tải model hàng GB")
    )
    sys.modules["sentence_transformers"] = broken
    import src.generation.evidence_selection as es

    es._RERANKER = None
    try:
        yield
    finally:
        es._RERANKER = None
        os.environ.clear()
        os.environ.update(saved)


def load_harness():
    """Máy chụp golden (`tools/diag/t3_golden_dump.py`) — chạy trong-process cho test A."""
    modpath = REPO_ROOT / "tools" / "diag" / "t3_golden_dump.py"
    spec = importlib.util.spec_from_file_location("t3_golden_dump_under_test", modpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["t3_golden_dump_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


# ================================================================ đồ giả dùng chung
class FakeDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


class FakeLeg:
    def __init__(self, docs):
        self.docs = docs
        self.calls = 0

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
    """Bộ 'chuẩn hóa' giả: trả đúng chuỗi đã cho — không gọi model."""

    def __init__(self, normalized: str):
        self._normalized = normalized

    def generate(self, prompt, temperature: float = 0.0):
        return self._normalized


class StubGenerator:
    """Stub generator: trả chuỗi cố định, đếm lượt gọi, ghi lại cửa sổ đã nhận."""

    def __init__(self, answer: str):
        self.answer = answer
        self.calls = 0
        self.received_docs: list = []
        self.received_query = None

    def generate_answer(self, query, retrieved_docs, **kwargs):
        self.calls += 1
        self.received_query = query
        self.received_docs = list(retrieved_docs)
        return self.answer


def make_pipeline(docs, answer="Trả lời mẫu."):
    from src.core.pipeline import HybridRAGPipeline

    fused = [FakeDoc(d["content"], dict(d["metadata"])) for d in docs]
    legs = [FakeLeg(fused), FakeLeg(fused)]
    ensemble = FakeEnsemble(legs, fused)
    gen = StubGenerator(answer)
    pipeline = HybridRAGPipeline(
        vector_db=None,
        local_slm=FakeLocalSLM(docs[0]["q"]),
        generator=gen,
        retriever=ensemble,
    )
    return pipeline, gen, legs, ensemble


# ================================================================ fixture nội dung
Q_RETAKE = "Sinh viên học lại tối đa bao nhiêu lần mỗi học phần?"
CTX_RETAKE = (
    "Điều 15, Khoản 2: Sinh viên được phép đăng ký học lại tối đa 2 lần cho mỗi "
    "học phần không đạt. Quy định áp dụng từ khóa 2021."
)
CTX_OFF_TOPIC = (
    "Giáo trình in tại xưởng in nội bộ, khổ A4, đóng gáy keo nhiệt trong ba ngày làm việc."
)
MD_RETAKE = {"source": "1054-qd-dhag-2020-09-29.pdf", "tier": 1, "chunk_id": 7}
MD_OFF = {"source": "xuong-in.pdf", "tier": 3, "chunk_id": 8}

# Ca biên luật 2: câu hỏi có HAI thực thể (Điều 15, Điều 99) và ba token nội dung;
# ngữ cảnh chỉ chứa MỘT thực thể và một phần token -> coverage 0,5 / overlap 0,6667
# (đã đo bằng `chunk_relevance`, xem test). Cần cả hai < 1,0 thì mới nâng ngưỡng lên
# "ngay trên" được — với Q_RETAKE/CTX_RETAKE, overlap luôn = 1,0 nên không thử biên được.
Q_BOUNDARY = "Điều 15 và Điều 99 quy định sinh viên học lại tối đa bao nhiêu lần mỗi học phần?"
CTX_BOUNDARY = (
    "Điều 15 nêu rõ giảng viên bộ môn gửi bảng điểm về phòng đào tạo sau ba ngày."
)

ITEM_ON = {"q": Q_RETAKE, "content": CTX_RETAKE, "metadata": MD_RETAKE}
ITEM_OFF = {"q": Q_RETAKE, "content": CTX_OFF_TOPIC, "metadata": MD_OFF}

# CÓ CĂN CỨ: mỗi khẳng định kiểm chứng được đều chép được nguyên văn từ CTX_RETAKE.
GROUNDED_ANSWER = (
    "Sinh viên được đăng ký học lại tối đa 2 lần cho mỗi học phần không đạt "
    "(Điều 15, Khoản 2 — 1054-qd-dhag-2020-09-29.pdf)."
)
# BỊA: "99 lần" không tồn tại trong ngữ cảnh.
FABRICATED_ANSWER = "Sinh viên được đăng ký học lại tối đa 99 lần cho mỗi học phần."


# ================================================================ A. Cờ TẮT = golden
class TestOffGolden:
    def test_file_golden_la_baseline_chua_co_T3_wiring(self):
        assert GOLDEN_PATH.exists(), f"thiếu golden {GOLDEN_PATH}"
        payload = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        # Chụp từ cây `git archive HEAD`: pipeline chưa có hai khóa T3.
        assert payload["meta"]["pipeline_has_t3_fields"] is False
        assert len(payload["core"]) == 30
        assert payload["meta"]["env"]["ENABLE_DECOUPLED_REFUSAL"] == "0"
        assert payload["meta"]["env"]["ENABLE_EVIDENCE_SELECTION"] == "0"

    def test_off_30item_dau_ra_byte_identical_voi_golden(self):
        harness = load_harness()
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        core = [harness.run_item(item)["core"] for item in harness.build_items()]
        assert len(core) == 30
        now = json.dumps(core, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        before = json.dumps(golden["core"], ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        assert hashlib.sha256(now).hexdigest() == hashlib.sha256(before).hexdigest()
        assert core == golden["core"]  # từng item, từng khóa — không "xấp xỉ"

    def test_off_hai_khoa_moi_cua_pipeline_deu_khong_phat_hanh(self):
        harness = load_harness()
        rows = [harness.run_item(item) for item in harness.build_items()]
        assert all(r["t3"]["refusal_decision"] is None for r in rows)
        assert all(r["t3"]["evidence_selection"] is None for r in rows)

    def test_off_khong_do_hang_tung_nhanh_va_generator_goi_dung_mot_lan(self):
        """Số lượt retrieve phải bằng đúng baseline; T3 không được thêm lượt nào khi tắt.

        `ensemble_calls` là 1 hay 2 tùy câu hỏi có sinh được `fallback_query` khác câu
        gốc hay không (đã đo: 15/30 mỗi loại) — nên so với golden, không hardcode con số.
        """
        harness = load_harness()
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        baseline_calls = [r["ensemble_calls"] for r in golden["core"]]
        rows = [harness.run_item(item) for item in harness.build_items()]
        assert [r["core"]["ensemble_calls"] for r in rows] == baseline_calls
        for r in rows:
            core = r["core"]
            assert core["leg_calls"] == [0, 0], "đường tắt không được đo hạng từng nhánh"
            assert core["gen_calls"] == 1

    def test_off_cache_key_qwen_trung_cong_thuc_legacy(self):
        """Bất biến cache: cờ TẮT vẫn dùng v1.3 nên mọi entry cũ còn giá trị."""
        harness = load_harness()
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        rows = [harness.run_item(item) for item in harness.build_items()]
        assert [r["core"]["qwen_cache_key"] for r in rows] == [g["qwen_cache_key"] for g in golden["core"]]
        assert len({r["core"]["qwen_cache_key"] for r in rows}) == 30
        assert [r["core"]["qwen_prompt_sha1"] for r in rows] == [g["qwen_prompt_sha1"] for g in golden["core"]]

    def test_off_pipeline_khong_sinh_dong_log_cua_T3(self, monkeypatch, capsys):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "0")
        monkeypatch.setenv("ENABLE_EVIDENCE_SELECTION", "0")
        assert decoupled_refusal_enabled() is False and evidence_selection_enabled() is False
        pipeline, gen, legs, _ = make_pipeline([ITEM_ON], answer=GROUNDED_ANSWER)
        pipeline.run(Q_RETAKE, top_k=1)
        out = capsys.readouterr().out
        assert "[DecoupledRefusal]" not in out
        assert "[EvidenceSelection]" not in out
        assert all(leg.calls == 0 for leg in legs)
        assert gen.calls == 1


# ============================================ A1' — bất biến TẮT khi env còn giá trị lever TẮT
class TestOffInvariantWhenDisabledLeversConfigured:
    """A1 ("cờ TẮT ⇒ đầu ra byte-identical + cache key không đổi") mới được chứng minh trong
    **môi trường env rỗng**: fixture autouse xoá sạch `DEC_*`/`EV_*`/`ANSWER_GUARD_*` cho mọi
    test. Nhưng vòng lặp P5 cấu hình bằng env — một round TẮT cờ vẫn có thể thừa hưởng
    `DEC_MIN_RRF_NORM`/`EV_MAX_SENTENCES` của round trước. Câu hỏi chưa ai kiểm: khi đó cờ TẮT
    có trả lại đúng hành vi cũ?

    Đo được HAI kết quả khác nhau (25-10):
      - ĐẦU RA (answer, contexts, prompt, số lượt gọi, docs generator nhận) **không đổi** —
        đúng bất biến, vì `pipeline` chỉ đọc ngưỡng khi cờ BẬT.
      - KHÓA CACHE **đổi** — `src/cache_policy.policy_cache_token()` gồm mọi ngưỡng bất kể
        `enabled`, nên khóa TẮT không còn là khóa legacy `v1.3` khi env có `DEC_*`/`EV_*`.

    Test thứ hai là **ĐẶC TẢ HIỆN TRẠNG** (đề xuất PA-27): nó ghim điều đang xảy ra, không
    phải điều mong muốn. Khi sửa `cache_policy.py` (chỉ đưa ngưỡng của lever đang BẬT vào
    token), test đó sẽ đỏ và phải thay bằng "khóa TẮT = legacy bất kể env" — cố ý để không
    ai sửa lặng lẽ.
    """

    ENV_DISABLED_LEVERS = {
        "DEC_MIN_RRF_NORM": "0.5",          # lever T3 đang TẮT
        "EV_MAX_SENTENCES": "3",            # lever T3 đang TẮT
        "ANSWER_GUARD_MIN_SCORE": "0.75",   # guard đang TẮT
    }

    def _set(self):
        for k, v in self.ENV_DISABLED_LEVERS.items():
            os.environ[k] = v

    def _core(self):
        harness = load_harness()
        return [harness.run_item(item)["core"] for item in harness.build_items()]

    def test_dau_ra_van_trung_golden_khi_env_con_nguong_cua_lever_tat(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["core"]
        self._set()
        core = self._core()
        no_key = lambda rows: [  # noqa: E731 — so mọi mặt TRỪ khóa cache (kiểm riêng bên dưới)
            {k: v for k, v in row.items() if k != "qwen_cache_key"} for row in rows
        ]
        assert no_key(core) == no_key(golden)  # câu trả lời/ngữ cảnh/prompt/lượt gọi y nguyên
        assert [r["qwen_prompt_sha1"] for r in core] == [g["qwen_prompt_sha1"] for g in golden]
        assert all(r["gen_calls"] == 1 for r in core)
        # ... nhưng KHÓA CACHE thì đã tách khỏi golden:
        assert [r["qwen_cache_key"] for r in core] != [g["qwen_cache_key"] for g in golden]

    def test_DAC_TA_HIEN_TRANG_khoa_cache_TAT_tach_khi_env_co_nguong_lever_tat(self):
        from src.core.cache_policy import cache_policy_deviation

        assert cache_policy_deviation() is None, "env rỗng phải là thể chế mặc định đã đăng ký"
        seen = {}
        for k, v in self.ENV_DISABLED_LEVERS.items():
            os.environ[k] = v
            token = cache_policy_deviation()
            assert token is not None, f"{k} (lever đang TẮT) phải làm token lệch theo hiện trạng"
            seen[k] = token
            os.environ.pop(k)
        # mỗi ngưỡng tạo một không gian cache riêng, và bỏ hết thì quay lại mặc định
        assert len(set(seen.values())) == len(seen)
        assert cache_policy_deviation() is None


# ================================================================ B2. prompt không còn lời mời từ chối
REFUSAL_AFFORDANCE_RES = [
    re.compile(r"không\s+đủ\s+thông\s+tin", re.IGNORECASE),
    re.compile(r"không\s+đủ\s+căn\s+cứ", re.IGNORECASE),
    re.compile(r"không\s+tìm\s+thấy", re.IGNORECASE),
    re.compile(r"trả\s+lời\s+đúng\s+một\s+câu", re.IGNORECASE),
    re.compile(r"(h[aã]y|có\s+thể|được\s+phép)\s+(từ\s+chối|bỏ\s+qua)", re.IGNORECASE),
]
REFUSAL_AFFORDANCE_FOLDED = [
    re.compile(r"khong\s+du\s+thong\s+tin", re.IGNORECASE),
    re.compile(r"khong\s+du\s+can\s+cu", re.IGNORECASE),
    re.compile(r"khong\s+tim\s+thay", re.IGNORECASE),
    re.compile(r"tra\s+loi\s+dung\s+mot\s+cau", re.IGNORECASE),
]


def affordance_hits(prompt: str) -> list[str]:
    """Danh sách chỉ dẫn từ chối bắt được (so cả bản có dấu lẫn bản đã fold)."""
    hay = fold(prompt)
    labels = [rx.pattern for rx in REFUSAL_AFFORDANCE_RES if rx.search(prompt)]
    labels += [rx.pattern for rx in REFUSAL_AFFORDANCE_FOLDED if rx.search(hay)]
    if REFUSAL_TEXT in prompt or fold(REFUSAL_TEXT) in hay:
        labels.append("canonical REFUSAL_TEXT")
    return labels


def qwen_prompt(**kwargs):
    return QwenGenerator(use_cache=False, temperature=0.1)._build_prompt(
        Q_RETAKE,
        [{"source": MD_RETAKE["source"], "tier": str(MD_RETAKE["tier"]), "content": CTX_RETAKE}],
        **kwargs,
    )


class TestPromptHasNoRefusalAffordance:
    def test_ON_prompt_regex_khong_con_chi_dan_tu_choi(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        prompt = qwen_prompt()
        assert affordance_hits(prompt) == []
        assert prompt.startswith(EXTRACT_ONLY_HEAD)
        assert not looks_like_refusal(prompt)

    @pytest.mark.parametrize("question_type", ["so_sanh", "thu_tuc", "ngoai_pham_vi"])
    def test_ON_prompt_regex_sach_cho_moi_nhan_cau_hoi(self, monkeypatch, question_type):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        prompt = qwen_prompt(question_type=question_type)
        assert affordance_hits(prompt) == []
        assert REFUSAL_TEXT not in prompt

    def test_ON_chi_duoc_noi_ve_tu_choi_trong_cau_cam_model_lam_viec_do(self, monkeypatch):
        """Đề bài cấm cụm 'từ chối'. Bản trích xuất thuần CÓ nói cụm này, nhưng chỉ trong
        câu cấm ('bạn KHÔNG được quyền từ chối'). Test ghim đúng phạm vi đó: mọi lần xuất
        hiện phải nằm ngay sau một phủ định."""
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        prompt = qwen_prompt()
        occurrences = list(re.finditer(r"từ chối", prompt, re.IGNORECASE))
        assert occurrences, "đầu prompt phải nói rõ quyền phán quyết thuộc tầng khác"
        for m in occurrences:
            before = prompt[max(0, m.start() - 40): m.start()]
            assert re.search(r"(không|KHÔNG)\s+(được\s+quyền|quyền)\s*$", before), before

    def test_regex_co_rang_ON_path_off_prompt_phai_bat_duoc(self, monkeypatch):
        """Chứng minh bộ regex không rỗng: đường TẮT chứa đúng những cụm bị cấm."""
        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
        prompt = qwen_prompt()
        hits = affordance_hits(prompt)
        assert len(hits) >= 2
        assert "canonical REFUSAL_TEXT" in hits

    def test_DUONG_GEMINI_hien_trang_khong_co_nhanh_T3_dac_ta_hien_trang(self, monkeypatch):
        """ĐẶC TẢ HIỆN TRẠNG (không phải nghiệm thu): `build_prompt` của GeminiGenerator
        không nhánh theo cờ T3 -> đường Gemini vẫn còn nguyên lời mời từ chối. Vòng lặp P5
        chạy Qwen/Ollama nên phép đo r8/r9 không liên quan; báo cáo ghi là lỗ hổng PA-14."""
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        docs = [
            {
                "source": MD_RETAKE["source"],
                "tier": str(MD_RETAKE["tier"]),
                "chunk_id": MD_RETAKE["chunk_id"],
                "content": CTX_RETAKE,
            }
        ]
        prompt = gemini_build_prompt(Q_RETAKE, docs)
        assert REFUSAL_TEXT in prompt  # hành vi cũ, giữ nguyên khi cờ bật
        assert affordance_hits(prompt), "đường Gemini vẫn còn nguyên lời mời từ chối"


# ================================================================ B3-B5. phán quyết tầng ngoài
class TestOuterRefusal:
    def test_ON_cau_tra_loi_tu_tin_nhung_thuc_the_khong_co_trong_ngu_canh_bi_guard_chan(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        pipeline, gen, _, _ = make_pipeline([ITEM_ON], answer=FABRICATED_ANSWER)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert gen.calls == 1  # có tốn một lượt sinh
        assert result["answer"] == REFUSAL_TEXT  # so ==, không phải "chứa"
        assert result["refusal_decision"]["stage"] == "post"
        assert result["refusal_decision"]["reason"] == REFUSAL_REASON_UNGROUNDED
        assert result["refusal_decision"]["features"]["n_unsupported"] >= 1

    @pytest.mark.parametrize(
        "fabricated",
        [
            FABRICATED_ANSWER,
            "Học phí học kỳ là 12.345.678 đồng, nộp trước ngày 31 tháng 12 năm 2030.",
            "Sinh viên được miễn 75 % học phí khi thuộc diện chính sách.",
            "Thư viện mở cửa đến 23 giờ 30 phút tất cả các ngày, kể cả Chủ nhật.",
            "Điều 99, Khoản 8 quy định thời hạn bảo lưu là 48 tháng.",
        ],
        ids=["so-lan", "tien-va-ngay", "ty-le-%", "gio-mo-cua", "dieu-khoan-bia"],
    )
    def test_ON_moi_dang_thuc_the_bia_deu_tra_ve_dung_mot_chuoi_canonical(self, monkeypatch, fabricated):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        pipeline, _, _, _ = make_pipeline([ITEM_ON], answer=fabricated)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert result["answer"] == REFUSAL_TEXT
        assert result["answer"].strip() == REFUSAL_TEXT  # không dính khoảng trắng/trích dẫn
        assert result["refusal_decision"]["refuse"] is True

    def test_ON_ngu_canh_du_va_cau_co_can_cu_thi_tra_loi_khong_tu_choi(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        pipeline, gen, _, _ = make_pipeline([ITEM_ON], answer=GROUNDED_ANSWER)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert gen.calls == 1
        assert result["answer"] == GROUNDED_ANSWER
        assert result["refusal_decision"]["stage"] == "post"
        assert result["refusal_decision"]["refuse"] is False
        assert result["refusal_decision"]["features"]["n_unsupported"] == 0

    def test_ON_diem_truy_xuat_thap_tu_choi_ma_khong_goi_generator(self, monkeypatch):
        """Luật 3: chunk vàng tụt hạng ở cả hai nhánh -> chặn TRƯỚC khi sinh, stub đếm 0."""
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        gold = FakeDoc(CTX_RETAKE, MD_RETAKE)
        filler = [
            FakeDoc(f"Lớp bổ trợ thứ {i} do phòng Đào tạo quản lý vận hành hằng tuần.",
                    {"source": f"ph-{i}.pdf", "tier": 3, "chunk_id": 200 + i})
            for i in range(11)
        ]
        ensemble = FakeEnsemble([FakeLeg(filler + [gold]), FakeLeg(filler[:8] + [gold])], [gold])
        gen = StubGenerator(GROUNDED_ANSWER)
        from src.core.pipeline import HybridRAGPipeline

        pipeline = HybridRAGPipeline(vector_db=None, local_slm=FakeLocalSLM(Q_RETAKE),
                                     generator=gen, retriever=ensemble)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert gen.calls == 0
        assert result["answer"] == REFUSAL_TEXT
        assert result["refusal_decision"]["reason"] == REFUSAL_REASON_WEAK_RANK
        assert result["refusal_decision"]["features"]["rrf_norm"] < DEFAULT_MIN_RRF_NORM
        assert result["refusal_decision"]["features"]["best_rank_bm25"] == 12

    def test_ON_do_phu_thuc_the_thap_tu_choi_ma_khong_goi_generator(self, monkeypatch):
        """Luật 2: cửa sổ lạc đề, không chia thực thể/từ khóa nào với câu hỏi -> chặn pre."""
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        pipeline, gen, _, _ = make_pipeline([ITEM_OFF], answer=GROUNDED_ANSWER)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert gen.calls == 0
        assert result["answer"] == REFUSAL_TEXT
        assert result["refusal_decision"]["reason"] == REFUSAL_REASON_OFF_TOPIC
        assert result["refusal_decision"]["features"]["n_relevant_chunks"] == 0

    def test_ON_khong_co_ngu_canh_luat_1_chan_truoc_khong_goi_generator(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        ensemble = FakeEnsemble([FakeLeg([]), FakeLeg([])], [])
        gen = StubGenerator("sẽ không được gọi")
        from src.core.pipeline import HybridRAGPipeline

        pipeline = HybridRAGPipeline(vector_db=None, local_slm=FakeLocalSLM(Q_RETAKE),
                                     generator=gen, retriever=ensemble)
        result = pipeline.run(Q_RETAKE, top_k=2)
        assert gen.calls == 0
        assert result["answer"] == REFUSAL_TEXT
        assert result["refusal_decision"]["reason"] == REFUSAL_REASON_NO_EVIDENCE

    def test_ON_model_van_tu_choi_thi_tang_ngoai_tra_dung_chuoi_canonical(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        pipeline, _, _, _ = make_pipeline([ITEM_ON], answer=REFUSAL_TEXT)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert result["answer"] == REFUSAL_TEXT
        assert result["refusal_decision"]["reason"] == REFUSAL_REASON_MODEL_REFUSES

    def test_OFF_cung_du_lieu_khong_he_bi_chan_hanh_vi_cu(self, monkeypatch):
        """Chiều ngược lại của bất biến: tắt cờ thì câu bịa đi qua -> chứng minh các test
        B3–B5 không phải test rỗng (lever thật sự tạo ra khác biệt)."""
        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
        pipeline, gen, _, _ = make_pipeline([ITEM_ON], answer=FABRICATED_ANSWER)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert gen.calls == 1
        assert result["answer"] == FABRICATED_ANSWER
        assert result["refusal_decision"] is None


# ================================================================ B6. ngưỡng biên + nguồn ngưỡng
class TestThresholdBoundaries:
    def test_nguong_mac_dinh_khop_bang_dang_ky_truoc(self):
        assert thresholds() == {
            "min_entity_coverage": DEFAULT_MIN_ENTITY_COVERAGE,
            "min_token_overlap": DEFAULT_MIN_TOKEN_OVERLAP,
            "min_rrf_norm": DEFAULT_MIN_RRF_NORM,
            "min_grounding": DEFAULT_MIN_GROUNDING,
            "max_unsupported": DEFAULT_MAX_UNSUPPORTED,
        }
        assert (DEFAULT_MIN_ENTITY_COVERAGE, DEFAULT_MIN_TOKEN_OVERLAP, DEFAULT_MIN_RRF_NORM,
                DEFAULT_MIN_GROUNDING, DEFAULT_MAX_UNSUPPORTED) == (0.34, 0.20, 0.90, 0.60, 1)

    def test_nguong_doc_tu_cau_hinh_dao_chieu_phan_quyet_khi_env_doi(self):
        """Cùng dữ liệu, hai giá trị ngưỡng -> hai phán quyết: chứng minh không hardcode."""
        norm = rrf_norm(4, 4, bm25_weight=1.0, vector_weight=1.0)
        os.environ["DEC_MIN_RRF_NORM"] = f"{norm:.10f}"
        at = decide_pre_generation(question=Q_RETAKE, contexts=[CTX_RETAKE], leg_ranks=[(4, 4)])
        os.environ["DEC_MIN_RRF_NORM"] = f"{norm + 1e-9:.10f}"
        above = decide_pre_generation(question=Q_RETAKE, contexts=[CTX_RETAKE], leg_ranks=[(4, 4)])
        assert at.refuse is False and at.features["rrf_norm"] == pytest.approx(norm)
        assert above.refuse is True and above.reason == REFUSAL_REASON_WEAK_RANK

    def test_rrf_dung_bang_nguong_dat_ngay_duoi_bi_chan(self):
        th = thresholds()["min_rrf_norm"]
        ok = decide_pre_generation(question=Q_RETAKE, contexts=[CTX_RETAKE], leg_ranks=[(1, 1)])
        assert ok.refuse is False and ok.features["rrf_norm"] >= th
        weak = decide_pre_generation(question=Q_RETAKE, contexts=[CTX_RETAKE], leg_ranks=[(10, 10)])
        assert weak.refuse is True and weak.features["rrf_norm"] < th
        # ca "ngay tren" nguong: hạ ngưỡng xuống sát dưới giá trị của hạng 10 -> vẫn đạt
        os.environ["DEC_MIN_RRF_NORM"] = f"{weak.features['rrf_norm']:.10f}"
        assert decide_pre_generation(
            question=Q_RETAKE, contexts=[CTX_RETAKE], leg_ranks=[(10, 10)]).refuse is False

    def test_do_phu_va_overlap_dung_nguong_va_dao_chieu_quanh_nguong(self):
        """Luật 2 (OR của coverage/overlap): ngưỡng = giá trị đo -> ĐẠT (>=); cao hơn
        1 micron -> CHẶN; thấp hơn 1 micron -> ĐẠT. Ngưỡng đọc từ `thresholds()`."""
        rel = chunk_relevance(Q_BOUNDARY, [CTX_BOUNDARY])
        assert rel[0]["relevant"] is True
        cov, ovl = rel[0]["coverage"], rel[0]["overlap"]
        assert cov is not None and 0.0 < cov < 1.0, "fixture phải có coverage hữu tỉ để thử biên"
        assert ovl is not None and 0.0 < ovl < 1.0, "fixture phải có overlap hữu tỉ để thử biên"

        def decide():
            return decide_pre_generation(question=Q_BOUNDARY, contexts=[CTX_BOUNDARY])

        # đúng bằng ngưỡng đo được -> vẫn liên quan (>=), không từ chối
        os.environ["DEC_MIN_ENTITY_COVERAGE"] = f"{cov:.10f}"
        os.environ["DEC_MIN_TOKEN_OVERLAP"] = f"{ovl:.10f}"
        assert decide().refuse is False
        # ngay trên cả hai ngưỡng -> cả hai vế OR đều trượt -> luật 2 chặn
        os.environ["DEC_MIN_ENTITY_COVERAGE"] = f"{cov + 1e-6:.10f}"
        os.environ["DEC_MIN_TOKEN_OVERLAP"] = f"{ovl + 1e-6:.10f}"
        blocked = decide()
        assert blocked.refuse is True and blocked.reason == REFUSAL_REASON_OFF_TOPIC
        assert blocked.features["n_relevant_chunks"] == 0
        # ngay dưới -> đạt lại
        os.environ["DEC_MIN_ENTITY_COVERAGE"] = f"{cov - 1e-6:.10f}"
        os.environ["DEC_MIN_TOKEN_OVERLAP"] = f"{ovl - 1e-6:.10f}"
        assert decide().refuse is False
        # cổng đăng ký vẫn là 0,34 — test không tự đổi mặc định
        os.environ.pop("DEC_MIN_ENTITY_COVERAGE", None)
        assert thresholds()["min_entity_coverage"] == DEFAULT_MIN_ENTITY_COVERAGE

    def test_luat_2_la_or_mot_ve_dat_la_du(self):
        """Ghim ngữ nghĩa đã đăng ký: coverage đạt dù overlap trượt (và ngược lại)."""
        rel = chunk_relevance(Q_BOUNDARY, [CTX_BOUNDARY])
        cov, ovl = rel[0]["coverage"], rel[0]["overlap"]
        os.environ["DEC_MIN_ENTITY_COVERAGE"] = f"{cov:.10f}"      # vế 1 đạt đúng bằng
        os.environ["DEC_MIN_TOKEN_OVERLAP"] = "1.0"                  # vế 2 trượt (0,6667 < 1,0)
        assert decide_pre_generation(question=Q_BOUNDARY, contexts=[CTX_BOUNDARY]).refuse is False
        os.environ["DEC_MIN_ENTITY_COVERAGE"] = "1.0"                # vế 1 trượt (0,5 < 1,0)
        os.environ["DEC_MIN_TOKEN_OVERLAP"] = f"{ovl:.10f}"          # vế 2 đạt đúng bằng
        assert decide_pre_generation(question=Q_BOUNDARY, contexts=[CTX_BOUNDARY]).refuse is False

    def test_grounding_dung_bang_va_sat_nguong(self):
        d = decide_post_generation(question=Q_RETAKE, contexts=[CTX_RETAKE], answer=GROUNDED_ANSWER,
                                   source_names=[MD_RETAKE["source"]])
        assert d.refuse is False and d.features["grounding_score"] == 1.0
        th = thresholds()["min_grounding"]
        os.environ["DEC_MIN_GROUNDING"] = "1.0"  # đúng bằng điểm đo -> vẫn đạt
        assert decide_post_generation(
            question=Q_RETAKE, contexts=[CTX_RETAKE], answer=GROUNDED_ANSWER,
            source_names=[MD_RETAKE["source"]]).refuse is False
        os.environ["DEC_MIN_GROUNDING"] = "1.0000001"  # ngoài [0,1] -> env hỏng, kẹp về mặc định
        assert thresholds()["min_grounding"] == DEFAULT_MIN_GROUNDING
        assert th == DEFAULT_MIN_GROUNDING

    def test_env_vo_ly_khong_duoc_dem_nhap_vao_nguong(self):
        for bad in ("abc", "-1", "2.5", ""):
            os.environ["DEC_MIN_GROUNDING"] = bad
            assert thresholds()["min_grounding"] == DEFAULT_MIN_GROUNDING, bad
        os.environ["DEC_MAX_UNSUPPORTED"] = "-4"
        assert thresholds()["max_unsupported"] == DEFAULT_MAX_UNSUPPORTED

    def test_max_unsupported_hien_trang_bi_luat_fabricated_che_khu_dac_ta_hien_trang(self, monkeypatch):
        """ĐẶC TẢ HIỆN TRẠNG: `fabricated == bool(unsupported)` trong answer_guard, nên vế
        'unsupported > trần (1)' của luật 4 KHÔNG bao giờ quyết định — một thực thể chưa
        căn cứ đã chặn. Trần hiệu dụng là 0, NGHIÊM HƠN con số 1 đã đăng ký.
        Báo cáo test_T3 đề xuất PA-15 (hoặc sửa luật, hoặc đăng ký lại trần 0)."""
        two_bad = "Học phí là 11.111.111 đồng và miễn 88 % cho diện chính sách."
        os.environ["DEC_MAX_UNSUPPORTED"] = "9"  # trần cực rộng
        d = decide_post_generation(question=Q_RETAKE, contexts=[CTX_RETAKE], answer=two_bad,
                                   source_names=[MD_RETAKE["source"]])
        assert d.features["n_unsupported"] >= 1
        assert d.refuse is True and d.reason == REFUSAL_REASON_UNGROUNDED

    def test_khong_do_duoc_hang_khong_duoc_coi_la_dat(self):
        for leg_ranks in (None, [(None, None)]):
            d = decide_pre_generation(question=Q_RETAKE, contexts=[CTX_RETAKE], leg_ranks=leg_ranks)
            assert d.refuse is False
            assert d.features.get("rrf_unavailable") is True

    def test_source_luat_khong_hardcode_nguong_so_sanh_chi_dung_tu_thresholds(self):
        """`decide_*` phải so với `th[...]`, không có chữ số ngưỡng rải rác trong code."""
        import inspect

        import src.generation.refusal_policy as rp

        for fn in (rp.decide_pre_generation, rp.decide_post_generation):
            body = "".join(inspect.getsource(fn).splitlines(keepends=True)[1:])
            for hard in ("0.34", "0.20", "0.90", "0.60", ">= 1", "> 1"):
                assert hard not in body, f"{fn.__name__} hardcode {hard!r}"
            assert "th[" in body


# ================================================================ B7-B8. thứ tự guard/cache
class FakeOllama:
    """Thế chỗ `src.generator.ollama.Client`: ghi prompt đã nhận, trả chuỗi cố định."""

    def __init__(self, answer: str):
        self.answer = answer
        self.prompts: list[str] = []

    def __call__(self, host=None, timeout=None):
        return _FakeOllamaConnection(self)


class _FakeOllamaConnection:
    def __init__(self, owner: FakeOllama):
        self.owner = owner

    def generate(self, model=None, prompt=None, options=None, stream=False):
        self.owner.prompts.append(prompt)
        return {"response": self.owner.answer}


def qwen_pipeline(docs, ollama_answer: str, cache_dir: Path, monkeypatch):
    """Pipeline thật + QwenGenerator thật (Ollama giả) + cache thật trong tmp_path."""
    import src.generator as gen_module
    from src.core.pipeline import HybridRAGPipeline

    fake = FakeOllama(ollama_answer)
    monkeypatch.setattr(gen_module.ollama, "Client", fake)
    monkeypatch.setenv("GENERATION_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("GENERATION_CACHE", "1")
    qwen = QwenGenerator(use_cache=True, temperature=0.1)
    fused = [FakeDoc(d["content"], dict(d["metadata"])) for d in docs]
    ensemble = FakeEnsemble([FakeLeg(fused), FakeLeg(fused)], fused)
    pipeline = HybridRAGPipeline(vector_db=None, local_slm=FakeLocalSLM(docs[0]["q"]),
                                 generator=qwen, retriever=ensemble)
    return pipeline, fake, qwen


def cache_entries(cache_dir: Path) -> list[dict]:
    if not cache_dir.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(cache_dir.glob("*.json"))]


class TestCacheOrderAndNamespace:
    def test_OFF_cache_key_dung_bang_cong_thuc_legacy_v1_3(self, monkeypatch):
        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
        g = QwenGenerator(use_cache=False, temperature=0.1)
        prompt = "mot-chuoi-prompt-co-dinh"
        payload = json.dumps({"model": g.ollama_model, "temperature": 0.1,
                             "prompt_version": "v1.3", "prompt": prompt},
                            ensure_ascii=False, sort_keys=True)
        assert g._cache_key(prompt, 0.1) == hashlib.sha1(payload.encode("utf-8")).hexdigest()
        assert effective_prompt_version() == PROMPT_VERSION == "v1.3"

    def test_ON_cache_key_chua_PROMPT_VERSION_moi(self, monkeypatch):
        g = QwenGenerator(use_cache=False, temperature=0.1)
        prompt = "prompt-giong-het-nhau"
        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
        key_off = g._cache_key(prompt, 0.1)
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        key_on = g._cache_key(prompt, 0.1)
        assert effective_prompt_version() == EXTRACT_ONLY_PROMPT_VERSION
        assert key_on != key_off
        payload = json.dumps({"model": g.ollama_model, "temperature": 0.1,
                             "prompt_version": EXTRACT_ONLY_PROMPT_VERSION, "prompt": prompt},
                            ensure_ascii=False, sort_keys=True)
        assert key_on == hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def test_bat_tat_co_khong_doc_nham_cache_cua_che_do_kia(self, monkeypatch, tmp_path):
        """Entry của đường TẮT không được đường BẬT đọc, và ngược lại."""
        cache_dir = tmp_path / "cache"
        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
        p_off, fake_off, _ = qwen_pipeline([ITEM_ON], "cau-tra-loi-duong-TAT", cache_dir, monkeypatch)
        first = p_off.run(Q_RETAKE, top_k=1)
        assert len(fake_off.prompts) == 1 and "cau-tra-loi-duong-TAT" in first["answer"]

        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        p_on, fake_on, _ = qwen_pipeline([ITEM_ON], "cau-tra-loi-duong-BAT", cache_dir, monkeypatch)
        second = p_on.run(Q_RETAKE, top_k=1)
        assert len(fake_on.prompts) == 1, "bật cờ phải MISS thật, không ăn entry của chế độ kia"
        assert "cau-tra-loi-duong-TAT" not in second["answer"]

        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
        p_back, fake_back, _ = qwen_pipeline([ITEM_ON], "KHONG-QUYEN-GOI-LAI", cache_dir, monkeypatch)
        p_back.run(Q_RETAKE, top_k=1)
        assert fake_back.prompts == [], "tắt cờ trở lại phải trúng lại entry cũ"

    def test_luat_chan_truoc_sinh_khong_ghi_bat_ky_entry_nao(self, monkeypatch, tmp_path):
        """Đề bài mục 7: ca bị chặn TRƯỚC khi sinh thì cache phải rỗng."""
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        cache_dir = tmp_path / "cache"
        pipeline, fake, _ = qwen_pipeline([ITEM_OFF], "cau-se-bi-chan", cache_dir, monkeypatch)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert result["answer"] == REFUSAL_TEXT
        assert fake.prompts == []  # không tốn một lượt sinh
        assert cache_entries(cache_dir) == []

    def test_luat_chan_sau_sinh_refusal_khong_bao_gio_vao_cache(self, monkeypatch, tmp_path):
        """Đề bài mục 7, vế khó: luật 4-5 chặn SAU khi sinh. Entry cache là văn bản THÔ
        của model (hành vi cũ, có chủ đích), KHÔNG bao giờ là REFUSAL_TEXT; lần hai trúng
        cache vẫn phải bị chặn vì phán quyết là hàm deterministic của (answer, contexts)."""
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        cache_dir = tmp_path / "cache"
        pipeline, fake, _ = qwen_pipeline([ITEM_ON], FABRICATED_ANSWER, cache_dir, monkeypatch)
        first = pipeline.run(Q_RETAKE, top_k=1)
        assert first["answer"] == REFUSAL_TEXT
        assert len(fake.prompts) == 1
        entries = cache_entries(cache_dir)
        assert entries, "generator vẫn lưu văn bản thô của model"
        assert all(e["answer"] != REFUSAL_TEXT for e in entries)
        assert all("khong du thong tin" not in fold(e["answer"]) for e in entries)

        pipeline2, fake2, _ = qwen_pipeline([ITEM_ON], "KHONG-GOI-LAI", cache_dir, monkeypatch)
        second = pipeline2.run(Q_RETAKE, top_k=1)
        assert fake2.prompts == []  # trúng cache
        assert second["answer"] == REFUSAL_TEXT
        assert second["refusal_decision"]["reason"] == REFUSAL_REASON_UNGROUNDED

    def test_tat_co_trung_lai_entry_cu_khong_bi_lan_boi_che_do_bat(self, monkeypatch, tmp_path):
        """Chạy đường BẬT trước, rồi TẮT: đường TẮT phải MISS (không đọc entry của BẬT)."""
        cache_dir = tmp_path / "cache"
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        p_on, fake_on, _ = qwen_pipeline([ITEM_ON], "cau-tra-loi-duong-BAT", cache_dir, monkeypatch)
        p_on.run(Q_RETAKE, top_k=1)
        assert len(fake_on.prompts) == 1
        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
        p_off, fake_off, _ = qwen_pipeline([ITEM_ON], "cau-tra-loi-duong-TAT", cache_dir, monkeypatch)
        result = p_off.run(Q_RETAKE, top_k=1)
        assert len(fake_off.prompts) == 1, "đường TẮT không được ăn entry của đường BẬT"
        assert "duong-BAT" not in result["answer"]


# ================================================================ B9. ca bất thường
class TestAbnormalCases:
    def test_ngu_canh_rong_khong_crash_tra_ve_refusal(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        ensemble = FakeEnsemble([FakeLeg([]), FakeLeg([])], [])
        gen = StubGenerator("sẽ không được gọi")
        from src.core.pipeline import HybridRAGPipeline

        pipeline = HybridRAGPipeline(vector_db=None, local_slm=FakeLocalSLM(Q_RETAKE),
                                     generator=gen, retriever=ensemble)
        result = pipeline.run(Q_RETAKE, top_k=2)
        assert gen.calls == 0
        assert result["answer"] == REFUSAL_TEXT
        assert result["contexts"] == []

    @pytest.mark.parametrize("flag", ["0", "1"], ids=["off", "on"])
    def test_cau_hoi_rong_bi_tu_choi_o_tang_pipeline(self, monkeypatch, flag):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", flag)
        monkeypatch.setenv("ENABLE_EVIDENCE_SELECTION", flag)
        pipeline, gen, _, _ = make_pipeline([ITEM_ON])
        with pytest.raises(ValueError):
            pipeline.run("   ")
        assert gen.calls == 0

    def test_cau_hoi_chi_khac_dau_cho_cung_phan_quyet_va_cung_s_do(self):
        """Corpus OCR mất dấu là chuyện thật: bản không dấu phải cho cùng phán quyết."""
        accented = "Sinh viên được phép học lại tối đa mấy lần mỗi học phần?"
        unaccented = "Sinh vien duoc phep hoc lai toi da may lan moi hoc phan?"
        assert fold(accented) == fold(unaccented)
        d1 = decide_pre_generation(question=accented, contexts=[CTX_RETAKE])
        d2 = decide_pre_generation(question=unaccented, contexts=[CTX_RETAKE])
        assert d1.refuse == d2.refuse
        for key in ("coverage", "overlap", "n_relevant_chunks"):
            assert d1.features.get(key) == d2.features.get(key), key

    def test_metadata_thieu_source_khong_lam_giay_ca_hai_lever(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        monkeypatch.setenv("ENABLE_EVIDENCE_SELECTION", "1")
        doc = {"q": Q_RETAKE, "content": CTX_RETAKE, "metadata": {"chunk_id": 5}}
        pipeline, gen, _, _ = make_pipeline([doc], answer=GROUNDED_ANSWER)
        result = pipeline.run(Q_RETAKE, top_k=1)
        assert isinstance(result["refusal_decision"], dict)
        assert result["answer"] in {GROUNDED_ANSWER, REFUSAL_TEXT}

    def test_doc_khong_must_la_chu_khong_lam_no_module(self):
        """Chuỗi trần (không phải Document) vẫn đi được đường chọn câu — không crash."""
        cands = rank_candidates(Q_RETAKE, [CTX_RETAKE], [], reranker=Reranker("none"))
        assert all(isinstance(c.sentence, str) for c in cands)


# ================================================================ C. evidence selection
S1 = "Sinh viên được phép đăng ký học lại tối đa 2 lần cho mỗi học phần không đạt."
S2 = "Học phí học kỳ chính quy là 7.400.000 đồng và nộp trước ngày 15 tháng 10 hàng năm."
S3 = "Sinh viên thuộc diện học lại phải đăng ký trên hệ thống trong tuần đầu của học kỳ."
S4 = "Giảng viên bộ môn gửi bảng điểm về phòng đào tạo sau khi kết thúc học phần được ba ngày."
S5 = "Thư viện tầng hai mở cửa từ 7 giờ đến 19 giờ các ngày trong tuần."
S6 = "Văn bản do Trường Đại học An Giang ban hành áp dụng cho các khóa đại học hệ chính quy."


class Doc2:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


def window_docs():
    return [
        Doc2(" ".join([S1, S2, S3]),
             {"source": "quy-che-dao-tai-1054-qd-dhag-2020-09-29.pdf", "tier": 1, "chunk_id": 11}),
        Doc2(" ".join([S4, S5, S6]),
             {"source": "khac-2021.pdf", "tier": 2, "chunk_id": 22}),
    ]


@pytest.fixture()
def no_reranker():
    """Xếp hạng chỉ theo bậc thang thực thể/từ khóa -> deterministic tuyệt đối."""
    import src.generation.evidence_selection as es

    es._RERANKER = Reranker("none")
    yield
    es._RERANKER = None


class TestEvidenceWindowShape:
    def test_so_cau_trong_bang_3_den_5(self, no_reranker):
        lo, hi = sentence_budget()
        window, info = select_evidence(Q_RETAKE, window_docs(), source_names=[])
        assert info["applied"] is True
        assert lo <= info["n_sentences"] <= hi == 5
        assert 3 <= info["n_sentences"] <= 5
        total = sum(len(split_sentences(d.page_content)) for d in window)
        assert total == info["n_sentences"]

    def test_ngu_canh_ngan_hon_min_thi_giu_nguyen_window_va_ghi_ly_do(self, no_reranker):
        """Đề bài cho phép 'ít hơn nếu ngắn hơn' — quy tắc ĐÃ ĐĂNG KÝ là GIỮ NGUYÊN cửa sổ
        chunk gốc (không tự chế cửa sổ 1–2 câu, vì sẽ cắt căn cứ của câu hỏi khó)."""
        lonely = [Doc2("Văn bản chỉ có đúng một câu duy nhất nói về biểu mẫu trực tuyến.",
                       {"chunk_id": 1, "source": "x.pdf"})]
        window, info = select_evidence(Q_RETAKE, lonely, source_names=["y.pdf"])
        assert info["applied"] is False
        assert info["reason"] == "not_enough_qualifying_sentences"
        assert window == lonely  # đúng các object cửa sổ gốc

    def test_thu_tu_giua_chunk_theo_hang_goc_trong_chunk_theo_mach_doc(self, no_reranker):
        docs = window_docs()
        window, info = select_evidence(Q_RETAKE, docs, source_names=[])
        assert info["applied"] is True
        order = [d.metadata["chunk_id"] for d in window]
        assert order == sorted(order), "chunk hạng cao hơn phải đứng trước"
        for d in window:
            original = next(o.page_content for o in docs
                            if o.metadata["chunk_id"] == d.metadata["chunk_id"])
            positions = [original.index(s) for s in split_sentences(d.page_content)]
            assert positions == sorted(positions), "trong một chunk phải giữ mạch đọc gốc"
            assert positions, "không có cửa sổ rỗng"

    def test_khong_cat_tuy_tien_khi_so_cau_dat_chuan_nho_hon_max(self, no_reranker):
        """Số câu chọn = min(số câu đạt chuẩn, EV_MAX) — không tự cắt bớt khi dưới trần.

        "Đạt chuẩn" theo đúng luật đã đăng ký: ưu tiên nhóm tier >= 2 (strong); chỉ khi
        nhóm đó dưới EV_MIN mới nới xuống tier >= 1 (relaxed) — nên `applied` phải khớp
        luật nới, không phải chỉ `strong >= lo`.
        """
        lo, hi = sentence_budget()
        docs = [Doc2(" ".join([S1, S2, S3]), {"chunk_id": 11, "source": "a-2020.pdf"})]
        cands = rank_candidates(Q_RETAKE, docs, [], reranker=Reranker("none"))
        qualifying = [c for c in cands if c.tier >= TIER_KEYWORDS]
        relaxed = [c for c in cands if c.tier >= TIER_SOURCE_NAME]
        window, info = select_evidence(Q_RETAKE, docs, source_names=[])
        expect_applied = len(qualifying) >= lo or len(relaxed) >= lo
        assert info["applied"] is expect_applied
        if info["applied"]:
            used = qualifying if len(qualifying) >= lo else relaxed
            assert info["n_sentences"] == min(len(used), hi)
            assert info["relaxed_to_source_name"] is (len(qualifying) < lo)

    def test_noi_bac_xuong_source_name_khi_tier_cao_khong_du_min(self, no_reranker):
        """Câu hỏi không có thực thể/từ khóa mạnh -> bậc thang phải nới xuống tier 1 và
        ghi dấu `relaxed_to_source_name` (không câm lặng)."""
        q = "Chi phí in giáo trình A4 tại xưởng nội bộ là bao nhiêu?"
        docs = [Doc2(" ".join([S4, S5, S6]), {"chunk_id": 44, "source": "xuong-in-a4-2022.pdf"})]
        _, info = select_evidence(q, docs, source_names=["xuong-in-a4-2022.pdf"])
        if info["applied"]:
            assert info["min_sentences"] <= info["n_sentences"]


class TestEvidenceEntityPriority:
    def test_cau_chua_thuc_the_phi_cau_hoi_luoc_duoc_chon_khi_vua_ngan_sach(self, no_reranker):
        q = "Mức học phí 7.400.000 đồng phải nộp trước ngày nào?"
        docs = [Doc2(" ".join([S5, S2]), {"chunk_id": 11, "source": "a.pdf"})]  # 2 câu, 1 có thực thể
        window, info = select_evidence(q, docs, source_names=[])
        cands = rank_candidates(q, docs, [], reranker=Reranker("none"))
        entity_cands = [c for c in cands if c.tier == TIER_ENTITY]
        assert entity_cands and entity_cands[0].sentence == S2
        if info["applied"]:
            assert S2 in " ".join(d.page_content for d in window)
        else:  # đường lùi: cả cửa sổ gốc (bao gồm S2) được giữ
            assert S2 in window[0].page_content

    def test_khong_chon_cau_tier_thap_khi_con_cau_tier_cao_bi_loai(self, no_reranker):
        """Ưu tiên bậc thang: khi vượt EV_MAX ở tier cao thì không được nhặt tier thấp vào."""
        q = "Điều 15 quy định học lại mấy lần và học phí 7.400.000 đồng nộp ngày nào?"
        docs = [Doc2(" ".join([S1, S2, S3, S4, S5, S6]), {"chunk_id": 11, "source": "a.pdf"})]
        window, info = select_evidence(q, docs, source_names=[])
        assert info["applied"] is True
        chosen = set()
        for d in window:
            chosen.update(split_sentences(d.page_content))
        cands = rank_candidates(q, docs, [], reranker=Reranker("none"))
        tiers_chosen = [c.tier for c in cands if c.sentence in chosen]
        tiers_left_out = [c.tier for c in cands if c.sentence not in chosen]
        assert min(tiers_chosen) >= max(tiers_left_out)

    def test_thuc_the_khong_co_trong_ngu_canh_khong_lam_hong_phep_chon(self, no_reranker):
        """Câu hỏi chứa thực thể mà ngữ cảnh không có -> tier 3 rỗng, không crash, không bịa."""
        q = "Sinh viên được cấp mã số 99.88.77 khi nào và học lại mấy lần?"
        docs = window_docs()
        window, info = select_evidence(q, docs, source_names=[])
        cands = rank_candidates(q, docs, [], reranker=Reranker("none"))
        assert not [c for c in cands if "99" in c.sentence]  # không tự chế câu có số lạ
        originals = [d.page_content for d in docs]
        for d in window:
            for s in split_sentences(d.page_content):
                assert any(s in o for o in originals)

    def test_the_case_so_nhieu_cau_entity_hon_max_thi_quyet_dinh_theo_tier(self, no_reranker):
        _, hi = sentence_budget()
        q = "Học phí 7.400.000 đồng, 2 lần học lại, 19 giờ mở cửa: mỗi cái là bao nhiêu?"
        many = [Doc2(" ".join([S1, S2, S5, S3, S4, S6]), {"chunk_id": 1, "source": "a.pdf"})]
        window, info = select_evidence(q, many, source_names=[])
        assert info["n_sentences"] <= hi


class TestEvidenceDeterminismAndVerbatim:
    def test_cung_input_cho_cung_tap_chon_va_thu_tu(self, no_reranker):
        a, ia = select_evidence(Q_RETAKE, window_docs(), source_names=[])
        b, ib = select_evidence(Q_RETAKE, window_docs(), source_names=[])
        assert [d.page_content for d in a] == [d.page_content for d in b]
        assert [d.metadata for d in a] == [d.metadata for d in b]
        assert ia == ib

    def test_tie_break_on_dinh_khi_diem_bang_nhau_het(self, no_reranker):
        """Reranker 'none' cho mọi điểm 0.0 -> thứ tự quyết bằng (doc_index, sent_index)."""
        rr = Reranker("none")
        assert set(rr.scores(Q_RETAKE, [S1, S2, S3, S4, S5, S6])) == {0.0}
        cands = rank_candidates(Q_RETAKE, window_docs(), [], reranker=rr)
        top_tier = cands[0].tier
        keys = [(c.doc_index, c.sent_index) for c in cands if c.tier == top_tier]
        assert keys == sorted(keys)

    def test_moi_cau_tra_ve_la_chuoi_con_nguyen_van_cua_ngu_canh(self, no_reranker):
        docs = window_docs()
        originals = [d.page_content for d in docs]
        window, info = select_evidence(Q_RETAKE, docs, source_names=[])
        assert info["applied"] is True
        for d in window:
            for s in split_sentences(d.page_content):
                assert any(s in o for o in originals), f"câu không có nguồn gốc: {s!r}"

    def test_metadata_song_nguyen_de_trich_dan_khong_doi_cho_dua(self, no_reranker):
        docs = window_docs()
        window, info = select_evidence(Q_RETAKE, docs, source_names=[])
        assert {d.metadata["chunk_id"] for d in window} <= {11, 22}
        for d in window:
            original = next(o for o in docs if o.metadata["chunk_id"] == d.metadata["chunk_id"])
            assert d.metadata == original.metadata

    def test_cua_so_moi_khong_chua_s_ngoai_ngu_canh_goc(self, no_reranker):
        docs = window_docs()
        joined_before = " ".join(d.page_content for d in docs)
        window, info = select_evidence(Q_RETAKE, docs, source_names=[])
        joined_after = " ".join(d.page_content for d in window)
        for token in set(re.findall(r"\d+", joined_after)):
            assert token in joined_before, f"số {token} xuất hiện mà không có trong gốc"
        assert info["chars_after"] <= info["chars_before"]


class TestEvidenceInPipeline:
    def test_ON_cua_so_generator_bi_cat_conh_recall_khong_doi(self, monkeypatch):
        monkeypatch.setenv("ENABLE_EVIDENCE_SELECTION", "1")
        import src.generation.evidence_selection as es

        es._RERANKER = Reranker("none")
        docs = [
            {"q": Q_RETAKE, "content": " ".join([S1, S2, S3]),
             "metadata": {"chunk_id": 11, "source": "a-2020.pdf", "tier": 1}},
            {"q": Q_RETAKE, "content": " ".join([S4, S5, S6]),
             "metadata": {"chunk_id": 22, "source": "b-2021.pdf", "tier": 2}},
        ]
        pipeline, gen, _, _ = make_pipeline(docs, answer=GROUNDED_ANSWER)
        result = pipeline.run(Q_RETAKE, top_k=2)
        info = result["evidence_selection"]
        assert info is not None
        if info["applied"]:
            assert info["n_sentences"] <= 5
            assert sum(len(c) for c in result["contexts"]) <= info["chars_before"]
            assert [s["chunk_id"] for s in result["sources"]] == [11, 22]  # recall không đổi
            for d in gen.received_docs:
                for s in split_sentences(d.page_content):
                    assert any(s in doc["content"] for doc in docs)
        else:
            assert result["contexts"] == [d["content"] for d in docs]

    def test_OFF_evidence_khong_dong_vao_cua_so(self, monkeypatch):
        monkeypatch.delenv("ENABLE_EVIDENCE_SELECTION", raising=False)
        docs = [
            {"q": Q_RETAKE, "content": " ".join([S1, S2, S3]),
             "metadata": {"chunk_id": 11, "source": "a-2020.pdf", "tier": 1}},
            {"q": Q_RETAKE, "content": " ".join([S4, S5, S6]),
             "metadata": {"chunk_id": 22, "source": "b-2021.pdf", "tier": 2}},
        ]
        pipeline, gen, _, _ = make_pipeline(docs, answer=GROUNDED_ANSWER)
        result = pipeline.run(Q_RETAKE, top_k=2)
        assert result["evidence_selection"] is None
        assert result["contexts"] == [d["content"] for d in docs]
        assert [d.page_content for d in gen.received_docs] == [d["content"] for d in docs]


# ================================================================ D. chống bịa (hồi quy an toàn)
# 10 câu hỏi KHÔNG CÓ ĐÁP ÁN trong ngữ cảnh + stub generator trả lời TỰ TIN (mô phỏng model
# bịa). Yêu cầu D: cờ BẬT phải từ chối cả 10; một câu trả lời = ĐỎ.
UNANSWERABLE = [
    ("Trường có ký túc xá bao nhiêu phòng?", S1),
    ("Học phí liên thông văn bằng hai là bao nhiêu?", S5),
    ("Thời gian xét học bổng vượt cấp là bao lâu?", "Giáo trình in tại xưởng in nội bộ, khổ A4, đóng gáy keo nhiệt trong ba ngày."),
    ("Trường ký hợp đồng với ngân hàng nào để hỗ trợ vay?", "Máy photocopy tầng hai do phòng Hành chính quản lý, liên hệ số nội bộ 108."),
    ("Sinh viên được vay tối đa bao nhiêu tiền mỗi học kỳ?", S5),
    ("Mẫu đơn xin nghỉ học mang mã số nào?", "Biên bản họp hội đồng sư phạm ngày 12 tháng 3 ghi nhận 27 đại biểu tham dự."),
    ("Lễ tốt nghiệp của khóa 2019 tổ chức ngày nào?", S1),
    ("Khu thể dục thể thao đặt ở cơ sở nào?", S4),
    ("Học phần giáo dục quốc phòng kéo dài bao nhiêu tuần?", S6),
    ("Thư viện cho mượn tối đa bao nhiêu đầu sách mỗi lần?", "Xưởng in nhận hồ sơ đóng gáy keo nhiệt trong ba ngày làm việc."),
]

CONFIDENT_LIES = [
    "Nhà trường có ký túc xá 240 phòng, sức chứa 960 sinh viên.",
    "Học phí liên thông văn bằng hai là 18.500.000 đồng mỗi học kỳ.",
    "Thời gian xét học bổng vượt cấp là 45 ngày làm việc, nộp tại phòng CTSA.",
    "Trường ký hợp đồng với ngân hàng BIDV chi nhánh An Giang, hạn mức 40 triệu.",
    "Sinh viên được vay tối đa 25.000.000 đồng mỗi học kỳ với lãi suất 0,5 %.",
    "Mẫu đơn xin nghỉ học mang mã số MT-2019-07, ban hành ngày 3 tháng 4 năm 2019.",
    "Lễ tốt nghiệp khóa 2019 tổ chức ngày 20 tháng 11 tại hội trường A.",
    "Khu thể dục thể thao đặt tại cơ sở 2, đường Hà Hoàng Hổ, khai năm 2018.",
    "Học phần giáo dục quốc phòng kéo dài 8 tuần với 160 tiết.",
    "Thư viện cho mượn tối đa 6 đầu sách trong 21 ngày, gia hạn 2 lần.",
]

ALL_REASONS = {
    REFUSAL_REASON_NO_EVIDENCE, REFUSAL_REASON_OFF_TOPIC, REFUSAL_REASON_WEAK_RANK,
    REFUSAL_REASON_UNGROUNDED, REFUSAL_REASON_MODEL_REFUSES, REFUSAL_REASON_EMPTY,
}


class TestRefusesAllUnanswerable:
    @pytest.mark.parametrize("index", range(len(UNANSWERABLE)),
                             ids=[f"ca{i:02d}" for i in range(len(UNANSWERABLE))])
    def test_ON_ca_khong_co_dap_an_bi_tu_choi(self, monkeypatch, index):
        question, context = UNANSWERABLE[index]
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        item = {"q": question, "content": context,
                "metadata": {"source": "qc-dao-tai.pdf", "tier": 1, "chunk_id": 60 + index}}
        pipeline, gen, _, _ = make_pipeline([item], answer=CONFIDENT_LIES[index])
        result = pipeline.run(question, top_k=1)
        assert result["answer"] == REFUSAL_TEXT, (
            f"ĐỎ: ca {index} trả lời bịa thay vì từ chối -> {result['answer']!r}"
        )
        assert result["refusal_decision"]["refuse"] is True
        assert result["refusal_decision"]["reason"] in ALL_REASONS

    def test_DU_MUOI_CA_DEU_TU_CHOI_khong_le_chu_cai_nao(self, monkeypatch):
        """Bảng tổng hợp: 10/10 từ chối, kèm lý do từng ca cho báo cáo."""
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        rows = []
        for i, (question, context) in enumerate(UNANSWERABLE):
            item = {"q": question, "content": context,
                    "metadata": {"source": "qc-dao-tai.pdf", "tier": 1, "chunk_id": 70 + i}}
            pipeline, gen, _, _ = make_pipeline([item], answer=CONFIDENT_LIES[i])
            result = pipeline.run(question, top_k=1)
            rows.append({"id": i, "answer": result["answer"],
                         "reason": result["refusal_decision"]["reason"],
                         "stage": result["refusal_decision"]["stage"],
                         "gen_calls": gen.calls})
        refused = [r for r in rows if r["answer"] == REFUSAL_TEXT]
        assert len(refused) == 10, [r for r in rows if r["answer"] != REFUSAL_TEXT]
        assert all(r["reason"] in ALL_REASONS for r in refused)
        # luật pre (không tốn lượt sinh) phải chiếm đa số — đây là ý nghĩa "không gọi generator"
        assert sum(1 for r in refused if r["stage"] == "pre") >= 8

    def test_DUONG_TAT_khong_chan_ca_nay_hanh_vi_cu(self, monkeypatch):
        monkeypatch.delenv("ENABLE_DECOUPLED_REFUSAL", raising=False)
        question, context = UNANSWERABLE[0]
        item = {"q": question, "content": context,
                "metadata": {"source": "qc-dao-tai.pdf", "tier": 1, "chunk_id": 91}}
        pipeline, gen, _, _ = make_pipeline([item], answer=CONFIDENT_LIES[0])
        result = pipeline.run(question, top_k=1)
        assert gen.calls == 1
        assert result["answer"] == CONFIDENT_LIES[0]
        assert result["refusal_decision"] is None
