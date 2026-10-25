# -*- coding: utf-8 -*-
"""T4 — test mục 6–7 của đề bài: giao diện generator chung + cache key theo model/prompt.

Mục 6 hỏi: generator mới (đổi model sinh) có **đúng interface** của `QwenGenerator` /
`GeminiGenerator` không, chọn model qua env và mặc định vẫn là model cũ. Mục 7 hỏi: cache
key có chứa tên model + `PROMPT_VERSION` và đổi model có **không đọc cache cũ** không.

Cách kiểm để không phụ thuộc mạng/GPU:
* chữ ký so bằng `inspect.signature` — cùng tên, cùng thứ tự, cùng giá trị mặc định;
* `canonicalize_refusal` kiểm bằng hành vi: model trả câu từ chối có dấu hiệu
  `REFUSAL_MARKER` + `question_type="ngoai_pham_vi"` ⇒ phải ra ĐÚNG `REFUSAL_TEXT`; nhãn
  khác ⇒ giữ nguyên từng ký tự. Qwen đi qua `ollama.Client` giả, Gemini qua `_call_api` giả;
* cache key kiểm bằng **độ nhạy**: đổi model / prompt / temperature / prompt_version đều
  phải đổi key, còn cùng đầu vào thì trùng key. Không chép lại công thức SHA-1 vào test —
  chép lại là khoá test vào bản cài đặt chứ không khoá vào yêu cầu;
* "không đọc cache cũ": ghi một entry dưới khoá của model A rồi hỏi model B — phải MISS,
  và model A vẫn HIT (chứng minh cache thật sự được dùng, không phải test rỗng).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import src.generator as generator_module
from src.generator import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_MODEL,
    REFUSAL_TEXT,
    GeminiGenerator,
    QwenGenerator,
    canonicalize_refusal,
)
from tools.loop.run_round import generator_model_override

QUERY = "Sinh viên được học lại tối đa bao nhiêu lần?"
DOCS = [{"content": "Sinh viên được học lại tối đa 8 lần.", "source": "quy-che.pdf", "chunk_id": 1}]
NEW_SLUG = "qwen2.5:3b-instruct"
REFUSAL_LIKE = (
    "Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này. "
    "Vui lòng liên hệ Phòng Đào tạo để được hướng dẫn thêm."
)  # cố ý KHÁC REFUSAL_TEXT để thấy được tác dụng của canonicalize_refusal


# ------------------------------------------------------------------ 6. giao diện chung

class TestGiaoDienChung:
    def test_hai_generator_cung_chu_ky_generate_answer(self) -> None:
        qwen = inspect.signature(QwenGenerator.generate_answer)
        gemini = inspect.signature(GeminiGenerator.generate_answer)

        assert [(p.name, p.kind, p.default) for p in qwen.parameters.values()] == [
            (p.name, p.kind, p.default) for p in gemini.parameters.values()
        ]
        assert list(qwen.parameters) == ["self", "query", "retrieved_docs", "temperature",
                                         "question_type", "raw_query"]

    def test_hai_generator_cung_dung_mot_ham_chuan_hoa_tu_choi(self) -> None:
        """`canonicalize_refusal` là hàm MODULE dùng chung — không lớp nào tự viết bản riêng."""
        source = inspect.getsource(generator_module)
        assert source.count("def canonicalize_refusal(") == 1
        assert source.count("canonicalize_refusal(") >= 3  # 1 định nghĩa + 2 chỗ gọi (Gemini/Qwen)

    def test_canonicalize_refusal_chi_chuan_hoa_ngoai_pham_vi(self) -> None:
        assert canonicalize_refusal("... không đủ thông tin ...", "NGOAI_PHAM_VI") == REFUSAL_TEXT
        assert canonicalize_refusal("Câu trả lời có căn cứ.", "NGOAI_PHAM_VI") == "Câu trả lời có căn cứ."
        assert canonicalize_refusal("... không đủ thông tin ...", None) == "... không đủ thông tin ..."
        assert canonicalize_refusal("... không đủ thông tin ...", "TRA_CUU") == "... không đủ thông tin ..."

    def test_qwen_chuan_hoa_tu_choi_qua_duong_sinh(self, monkeypatch, tmp_path: Path) -> None:
        """Nhánh Qwen thật (không cache, không mạng): câu từ chối → đúng `REFUSAL_TEXT`."""
        calls = {"n": 0}

        class FakeResponse(dict):
            pass

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def generate(self, **kwargs):
                calls["n"] += 1
                return FakeResponse(response=REFUSAL_LIKE)

        monkeypatch.setattr(generator_module.ollama, "Client", FakeClient)
        monkeypatch.delenv("ENABLE_ANSWER_RESCUE", raising=False)
        monkeypatch.delenv("ENABLE_ANSWER_GUARD", raising=False)
        gen = QwenGenerator(ollama_model=DEFAULT_OLLAMA_MODEL, use_cache=False)

        assert gen.generate_answer(QUERY, DOCS, question_type="ngoai_pham_vi") == REFUSAL_TEXT
        assert gen.generate_answer(QUERY, DOCS, question_type=None).startswith(REFUSAL_LIKE)
        assert calls["n"] == 2

    def test_gemini_chuan_hoa_tu_choi_qua_duong_sinh(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-t4-contract")
        gen = GeminiGenerator()
        gen.use_cache = False
        monkeypatch.setattr(gen, "_call_api", lambda prompt, temperature: REFUSAL_LIKE)

        assert gen.generate_answer(QUERY, DOCS, question_type="ngoai_pham_vi") == REFUSAL_TEXT
        # Nhãn khác: KHÔNG chuẩn hoá — câu giữ nguyên rồi mới qua bước gắn trích dẫn dùng chung.
        assert gen.generate_answer(QUERY, DOCS, question_type="TRA_CUU").startswith(REFUSAL_LIKE)

    def test_mac_dinh_van_la_model_cu(self, monkeypatch) -> None:
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.delenv("GENERATOR_OLLAMA_MODEL", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)

        assert generator_model_override() is None
        assert QwenGenerator(ollama_model=generator_model_override()).ollama_model == DEFAULT_OLLAMA_MODEL
        assert DEFAULT_OLLAMA_MODEL == "qwen2.5:1.5b-instruct"
        assert GeminiGenerator(api_key="test-key-t4-contract").model_name == DEFAULT_MODEL

    def test_chon_model_qua_env_chi_doi_tang_sinh(self, monkeypatch) -> None:
        """Cùng một biến `GENERATOR_OLLAMA_MODEL`: rỗng = cũ, có slug = model mới."""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.setenv("GENERATOR_OLLAMA_MODEL", NEW_SLUG)
        assert generator_model_override() == NEW_SLUG
        assert QwenGenerator(ollama_model=generator_model_override()).ollama_model == NEW_SLUG

        monkeypatch.setenv("GENERATOR_OLLAMA_MODEL", "   ")
        assert generator_model_override() is None


# ------------------------------------------------------------------------- 7. cache key

class TestCacheKey:
    @pytest.fixture()
    def cache_dir(self, monkeypatch, tmp_path: Path) -> Path:
        path = tmp_path / "cache"
        monkeypatch.setenv("GENERATION_CACHE_DIR", str(path))
        monkeypatch.setenv("GENERATION_CACHE", "0")
        return path

    def test_khoa_doi_theo_model_va_giu_nguyen_khi_cung_dau_vao(self, cache_dir: Path) -> None:
        a = QwenGenerator(ollama_model="model-a", use_cache=True)
        a2 = QwenGenerator(ollama_model="model-a", use_cache=True)
        b = QwenGenerator(ollama_model="model-b", use_cache=True)

        key_a = a._cache_key("prompt", 0.0)
        assert key_a == a2._cache_key("prompt", 0.0)
        assert key_a != b._cache_key("prompt", 0.0)
        assert key_a != a._cache_key("prompt khac", 0.0)
        assert key_a != a._cache_key("prompt", 0.3)

    def test_khoa_doi_theo_prompt_version_bump(self, cache_dir: Path, monkeypatch) -> None:
        """`PROMPT_VERSION` nằm trong khoá: bump version là mọi entry cũ tự vô hiệu."""
        gen = QwenGenerator(ollama_model="model-a", use_cache=True)
        before = gen._cache_key("prompt", 0.0)

        monkeypatch.setattr(generator_module, "effective_prompt_version", lambda: "vTEST-bump")
        after = gen._cache_key("prompt", 0.0)

        assert before != after

    def test_doi_model_khong_doc_cache_cu(self, cache_dir: Path) -> None:
        old = QwenGenerator(ollama_model="model-a", use_cache=True)
        new = QwenGenerator(ollama_model="model-b", use_cache=True)
        key_old = old._cache_key("prompt", 0.0)
        key_new = new._cache_key("prompt", 0.0)
        old._cache_put(key_old, "prompt", 0.0, QUERY, "Câu trả lời của model A")

        # model A HIT (cache thật sự hoạt động) ...
        assert old._cache_get(key_old) == "Câu trả lời của model A"
        # ... nhưng model B mang khoá khác và KHÔNG thấy câu trả lời của A.
        assert key_new != key_old
        assert new._cache_get(key_new) is None

    def test_gemini_cung_tach_khoa_theo_model(self, cache_dir: Path) -> None:
        a = GeminiGenerator(model_name="gemini-a", api_key="test-key-t4-contract")
        b = GeminiGenerator(model_name="gemini-b", api_key="test-key-t4-contract")

        assert a._cache_key("prompt", 0.0) != b._cache_key("prompt", 0.0)


# ------------------------------------------------------- 8. số liệu đã ghi (không ngưỡng)

LATENCY_ARTIFACT = Path(__file__).resolve().parents[1] / "data" / "loop" / "diag" / "t4_latency_20q.json"


def test_so_lieu_muc_8_da_duoc_ghi_lai() -> None:
    """Đề bài mục 8 đòi BÁO SỐ, không đặt ngưỡng: chỉ kiểm bản ghi đọc được và đủ trường."""
    if not LATENCY_ARTIFACT.exists():
        pytest.skip("chưa có data/loop/diag/t4_latency_20q.json")
    report = json.loads(LATENCY_ARTIFACT.read_text(encoding="utf-8"))

    assert report["n_questions"] == 20
    assert report["latency_seconds"]["method"]
    assert report["vram_mib"]["method"]
    assert len(report["per_question"]) == 20
