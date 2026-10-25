"""Unit test cho T1 — ablation tầng sinh (`tools/diag/ablation_generation.py`).

Phạm vi (Test Engineer, 24-10): kiểm phần deterministic của script bằng STUB generator
— KHÔNG gọi Qwen/Gemini/Ollama thật (nguyên tắc #2). Nạp module từ file (namespace package
`tools.diag` không có trong `sys.path` mặc định) và trỏ mọi đường dẫn ra `tmp_path`.

Bảy ca:
  #1 cô lập: chạy các hàm không ghi/sửa `src/`.
  #2 cùng tập item: id ngoài r5 -> từ chối chạy; subset hợp lệ -> chỉ chạy đúng subset.
  #3 (a) chỉ chunk vàng; (c) gold_sentence + đúng 2 câu lân cận; ca biên không crash/lệch chunk.
  #4 (b) số lượt gọi Gemini == số item; dry-run in số dự kiến và KHÔNG gọi stub nào.
  #5 ra đúng `data/loop/diag/<name>/`; thư mục đã có rows -> từ chối trừ khi --force.
  #6 metric (refusal/PASS_CORRECT/fabrication) khớp tính tay; dùng trọng tài thật (chữ ký không đổi).
  #7 bảng quyết định -> T4 / T3 / T2+T6; sát ngưỡng -> "không kết luận được".
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.loop import verify  # noqa: E402  (trọng tài thật — chỉ đọc)


MODPATH = REPO_ROOT / "tools" / "diag" / "ablation_generation.py"


def load_abl():
    """Nạp module ablation_generation từ đường dẫn file (tách import src/ ở mức module)."""
    spec = importlib.util.spec_from_file_location("ablation_generation_under_test", MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


abl = load_abl()


# --------------------------------------------------------------------------- fixtures nhỏ
def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _point_paths(mod, tmp_path: Path, base_ids: list[str]):
    """Trỏ ROUNDS_DIR/TESTSET/DIAG_DIR vào tmp; tạo r5/full.jsonl với đúng `base_ids`."""
    mod.ROUNDS_DIR = tmp_path / "rounds"
    mod.TESTSET = tmp_path / "testset.jsonl"
    mod.DIAG_DIR = tmp_path / "diag"
    rows = [{"id": i, "contexts": [], "sources": [], "normalized_query": f"cau {i}", "labels": {}} for i in base_ids]
    _write_jsonl(mod.ROUNDS_DIR / mod.BASE_ROUND / "full.jsonl", rows)
    _write_jsonl(mod.TESTSET, [{"id": i, "raw_query": f"cau {i}", "family": "EXACT"} for i in base_ids])
    mod.DIAG_DIR.mkdir(parents=True, exist_ok=True)


class StubGenerator:
    """Generator giả: đếm số lần generate_answer và ký lại prompt/docs đã nhận."""

    instances: list["StubGenerator"] = []

    def __init__(self, *a, **k):
        self.calls: list[dict] = []
        StubGenerator.instances.append(self)

    def generate_answer(self, *, query, retrieved_docs, question_type=None, raw_query=None):
        self.calls.append({"query": query, "docs": retrieved_docs, "qtype": question_type})
        return "CAU TRA LOI TINH LE"


@pytest.fixture
def stubbed(monkeypatch):
    StubGenerator.instances = []
    monkeypatch.setattr(abl, "GeminiGenerator", StubGenerator)
    monkeypatch.setattr(abl, "QwenGenerator", StubGenerator)
    return StubGenerator


# ============================================================================ #1 cô lập src/
class TestIsolation:
    def test_chay_docs_for_khong_ghi_vao_src(self):
        src_dir = REPO_ROOT / "src"
        before = {p: p.stat().st_mtime_ns for p in src_dir.rglob("*.py")}
        chunks = {5: {"chunk_id": 5, "text": "noi dung vang", "source": "S", "tier": "T1", "body": "a. b"}}
        abl.docs_for("a_oracle_qwen", {}, {"gold_chunk_id": 5}, chunks)
        abl.docs_for("b_gemini_top6", {"contexts": ["x"], "sources": [{"source": "S"}]}, {}, chunks)
        abl.build_result({"labels": {}}, [{"content": "c", "source": "S", "tier": "T", "chunk_id": 1}], "ans", 0.1)
        after = {p: p.stat().st_mtime_ns for p in src_dir.rglob("*.py")}
        assert before == after  # không file src/ nào bị chạm

    def test_load_chunks_doc_khong_ghi_src(self, tmp_path):
        # load_chunks đọc build_training_data; bảo đảm nó không ghi vào src/ (chỉ đọc).
        src_dir = REPO_ROOT / "src"
        before = sorted((str(p), p.stat().st_mtime_ns) for p in src_dir.rglob("*.py"))
        try:
            abl.load_chunks()  # nếu thiếu dữ liệu sẽ raise; dù sao src/ không đổi
        except Exception:
            pass
        after = sorted((str(p), p.stat().st_mtime_ns) for p in src_dir.rglob("*.py"))
        assert before == after

    def test_chay_ca_run_config_khong_ghi_src_byte_nao(self, tmp_path, monkeypatch, stubbed):
        # Ca #1 bản đầy đủ: chạy TRỌN run_config (có sinh generator stub + chấm trọng tài)
        # trên đường dẫn tmp, rồi so NỘI DUNG từng file src/*.py (không chỉ mtime).
        _point_paths(abl, tmp_path, ["A1"])
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        src_dir = REPO_ROOT / "src"
        before = {p: p.read_bytes() for p in src_dir.rglob("*.py")}
        abl.run_config("a_oracle_qwen", 1, False)
        after = {p: p.read_bytes() for p in src_dir.rglob("*.py")}
        assert before == after  # byte-identical: script chỉ đọc src/, không import-thay-đổi hay ghi


# ============================================================================ #2 cùng tập item
class TestSameItemSet:
    def test_id_ngoai_r5_bi_tu_choi(self, tmp_path, monkeypatch, stubbed):
        base_ids = ["A1", "A2", "A3"]
        _point_paths(abl, tmp_path, base_ids)
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        ids_file = tmp_path / "ids.json"
        ids_file.write_text(json.dumps({"ids": ["A1", "A2", "ZZZ"]}), encoding="utf-8")
        with pytest.raises(SystemExit) as ei:
            abl.run_config("b_gemini_top6", None, True, ids_file=ids_file)
        assert "KHÔNG thuộc 100 item r5" in str(ei.value)

    def test_subset_hop_le_chi_chay_dung_id(self, tmp_path, monkeypatch, stubbed):
        base_ids = ["A1", "A2", "A3"]
        _point_paths(abl, tmp_path, base_ids)
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        ids_file = tmp_path / "ids.json"
        ids_file.write_text(json.dumps({"ids": ["A1", "A3"]}), encoding="utf-8")
        abl.run_config("b_gemini_top6", None, True, ids_file=ids_file)
        # chỉ 2 id (A1,A3) nằm trong todo -> bản in dry-run phải ghi todo=2
        # (không có id nào bị thêm/vượt r5)
        assert (abl.DIAG_DIR / "b_gemini_top6" / "settings.json").exists()
        settings = json.loads((abl.DIAG_DIR / "b_gemini_top6" / "settings.json").read_text(encoding="utf-8"))
        assert settings["n_base_items"] == 2  # đúng subset đã chốt, không phải 3

    def test_them_mot_id_so_voi_verdicts_r5_bi_tu_choi(self, tmp_path, monkeypatch, stubbed):
        # full.jsonl có thêm 1 id ngoài tập đã chấm của r5 => từ chối, nêu id thừa.
        _point_paths(abl, tmp_path, ["A1", "A2", "ZZZ"])
        _write_jsonl(abl.ROUNDS_DIR / abl.BASE_ROUND / "verdicts_full.jsonl",
                     [{"id": "A1"}, {"id": "A2"}])
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        with pytest.raises(SystemExit) as ei:
            abl.run_config("a_oracle_qwen", None, True)
        msg = str(ei.value)
        assert "KHÔNG khớp" in msg and "ZZZ" in msg and "thừa" in msg

    def test_bot_mot_id_so_voi_verdicts_r5_bi_tu_choi(self, tmp_path, monkeypatch, stubbed):
        # full.jsonl thiếu 1 id so với verdicts_full.jsonl => từ chối, nêu id thiếu.
        _point_paths(abl, tmp_path, ["A1"])
        _write_jsonl(abl.ROUNDS_DIR / abl.BASE_ROUND / "verdicts_full.jsonl",
                     [{"id": "A1"}, {"id": "A2"}])
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        with pytest.raises(SystemExit) as ei:
            abl.run_config("c_gold_window_qwen", None, True)
        msg = str(ei.value)
        assert "KHÔNG khớp" in msg and "A2" in msg and "thiếu" in msg


# ============================================================================ #3 ngữ cảnh theo config
class TestDocsForContext:
    def test_a_chi_goi_dung_chunk_vang(self):
        chunks = {
            5: {"chunk_id": 5, "text": "NOI DUNG VANG", "source": "S5", "tier": "T1", "body": "x"},
            6: {"chunk_id": 6, "text": "CHUNK KHAC", "source": "S6", "tier": "T2", "body": "y"},
        }
        docs, reason = abl.docs_for("a_oracle_qwen", {}, {"gold_chunk_id": 5}, chunks)
        assert reason is None
        assert len(docs) == 1
        assert docs[0]["content"] == "NOI DUNG VANG"
        # không chứa text của chunk khác
        assert "CHUNK KHAC" not in docs[0]["content"]

    def test_a_khong_co_gold_chunk_bi_loai(self):
        docs, reason = abl.docs_for("a_oracle_qwen", {}, {}, {5: {"chunk_id": 5, "text": "x", "source": "S", "tier": "T"}})
        assert docs is None and reason == "no_gold_chunk"

    def test_a_prompt_gui_stub_chi_chua_chunk_vang(self, tmp_path, monkeypatch, stubbed):
        # Ca #3 bản tích hợp: chạy trọn (a) rồi BẮT docs mà stub nhận. Row cố tình có
        # sẵn chunk khác trong `contexts` — (a) phải bỏ qua, chỉ gửi đúng chunk vàng.
        _point_paths(abl, tmp_path, ["A1"])
        _write_jsonl(
            abl.ROUNDS_DIR / abl.BASE_ROUND / "full.jsonl",
            [{"id": "A1", "contexts": ["NOI DUNG CHUNK KHAC"],
              "sources": [{"source": "S6", "tier": "T2", "chunk_id": 6}],
              "normalized_query": "cau A1", "labels": {}}],
        )
        _write_jsonl(
            abl.TESTSET,
            [{"id": "A1", "raw_query": "cau A1", "family": "EXACT", "gold_chunk_id": 5}],
        )
        chunks = {
            5: {"chunk_id": 5, "text": "NOI DUNG VANG", "source": "S5", "tier": "T1", "body": "x"},
            6: {"chunk_id": 6, "text": "NOI DUNG CHUNK KHAC", "source": "S6", "tier": "T2", "body": "y"},
        }
        monkeypatch.setattr(abl, "load_chunks", lambda: chunks)
        abl.run_config("a_oracle_qwen", 1, False)
        docs = stubbed.instances[0].calls[0]["docs"]
        assert len(docs) == 1
        assert docs[0]["content"] == "NOI DUNG VANG"
        assert all("CHUNK KHAC" not in d["content"] for d in docs)

    # MỖI câu trong các fixture dưới đây PHẢI dài >= 25 ký tự: `sentence_split` của
    # script LOẠI phần ngắn hơn (`len(p.strip()) >= 25`); nếu câu vàng bị loại thì
    # idx=None -> reason 'gold_sentence_not_in_sentences' (nhiễu fixture, không phải lỗi code).
    def test_c_gold_sentence_kem_dung_2_cau_can(self):
        body = (
            "Trường một là câu dẫn nhập đủ dài. Đây là câu vàng nằm ở giữa đoạn. "
            "Trường ba là câu tiếp theo dài. Trường tư là câu cuối cùng nhé."
        )
        chunks = {7: {"chunk_id": 7, "text": body, "body": body, "source": "S", "tier": "T1"}}
        item = {"gold_chunk_id": 7, "gold_sentence": "Đây là câu vàng nằm ở giữa đoạn."}
        docs, reason = abl.docs_for("c_gold_window_qwen", {}, item, chunks)
        assert reason is None
        sents = abl.sentence_split(body)
        assert len(sents) == 4  # không câu nào bị loại -> cửa sổ tính trên đủ 4 câu
        gi = sents.index("Đây là câu vàng nằm ở giữa đoạn.")
        assert docs[0]["content"] == "\n".join(sents[gi - 1: gi + 2])  # đúng 1 trước + 1 sau
        assert "Trường tư là câu cuối cùng nhé." not in docs[0]["content"]  # không lan ra ngoài cửa sổ

    def test_c_ca_bien_dau_chunk_khong_crash_khong_lech(self):
        body = (
            "Đây là câu vàng ở đầu tiên nhất. Theo sau là câu thứ hai khá dài. "
            "Cuối là câu thứ ba trong đoạn."
        )
        chunks = {8: {"chunk_id": 8, "text": body, "body": body, "source": "S", "tier": "T1"}}
        item = {"gold_chunk_id": 8, "gold_sentence": "Đây là câu vàng ở đầu tiên nhất."}
        docs, reason = abl.docs_for("c_gold_window_qwen", {}, item, chunks)
        assert reason is None
        sents = abl.sentence_split(body)
        assert len(sents) == 3
        assert docs[0]["content"] == "\n".join(sents[0:2])  # gold ở đầu -> không có câu "trước"
        assert "Cuối là câu thứ ba trong đoạn." not in docs[0]["content"]  # không lấy quá 1 câu sau

    def test_c_ca_bien_cuoi_chunk_khong_crash_khong_lech(self):
        body = (
            "Câu mở đầu là câu thứ nhất dài. Câu thứ hai nằm ở giữa đoạn. "
            "Đây là câu vàng ở cuối cùng."
        )
        chunks = {9: {"chunk_id": 9, "text": body, "body": body, "source": "S", "tier": "T1"}}
        item = {"gold_chunk_id": 9, "gold_sentence": "Đây là câu vàng ở cuối cùng."}
        docs, reason = abl.docs_for("c_gold_window_qwen", {}, item, chunks)
        assert reason is None
        sents = abl.sentence_split(body)
        assert len(sents) == 3
        last = len(sents) - 1
        assert docs[0]["content"] == "\n".join(sents[last - 1: last + 2])  # không index vượt đuôi
        assert "Câu mở đầu là câu thứ nhất dài." not in docs[0]["content"]


# ============================================================================ #4 bộ đếm lượt gọi (b) + dry-run
class TestGeminiCallCount:
    def test_dry_run_khong_goi_stub(self, tmp_path, monkeypatch, stubbed):
        _point_paths(abl, tmp_path, ["A1", "A2", "A3"])
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        out = abl.run_config("b_gemini_top6", None, True)
        assert stubbed.instances == []  # dry-run: không sinh generator, không gọi generate_answer

    def test_so_luot_goi_gemini_bang_so_item(self, tmp_path, monkeypatch, stubbed):
        ids = ["A1", "A2", "A3", "A4"]
        _point_paths(abl, tmp_path, ids)
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        # (b) docs_for dùng contexts/sources của row -> rỗng vẫn ra docs rỗng, reason None.
        abl.run_config("b_gemini_top6", None, False)
        assert stubbed.instances, "phải có generator cho (b)"
        total_calls = sum(len(g.calls) for g in stubbed.instances)
        assert total_calls == len(ids)  # đúng 1 lượt/item (đăng ký: mỗi item 1 lượt Gemini)
        # (b) ép QWEN_FALLBACK=0 và dùng GeminiGenerator
        assert stubbed.instances[0].__class__ is abl.GeminiGenerator

    def test_dry_run_in_so_du_kien_va_dung_truoc_khi_goi(self, tmp_path, monkeypatch, capsys, stubbed):
        _point_paths(abl, tmp_path, ["A1", "A2", "A3"])
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        abl.run_config("b_gemini_top6", None, True)
        printed = capsys.readouterr().out
        assert "không gọi model" in printed
        assert "todo=3" in printed
        assert stubbed.instances == []


# ============================================================================ #5 thư mục ra + chống ghi đè
class TestOutputDirSafety:
    def test_ra_dung_dia_chi_diag_config(self, tmp_path, monkeypatch, stubbed):
        _point_paths(abl, tmp_path, ["A1"])
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        out = abl.run_config("a_oracle_qwen", None, True)
        assert out == abl.DIAG_DIR / "a_oracle_qwen"
        assert out.exists() and (out / "settings.json").exists()

    def test_thu_muc_da_co_rows_tu_choi(self, tmp_path, monkeypatch, stubbed):
        _point_paths(abl, tmp_path, ["A1", "A2"])
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        cfg_dir = abl.DIAG_DIR / "b_gemini_top6"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "rows.jsonl").write_text('{"id":"A1","verdict":"PASS_CORRECT"}\n', encoding="utf-8")
        with pytest.raises(SystemExit) as ei:
            abl.run_config("b_gemini_top6", None, False)
        assert "--force" in str(ei.value)

    def test_force_gui_tiep_khong_tu_choi(self, tmp_path, monkeypatch, stubbed):
        _point_paths(abl, tmp_path, ["A1"])
        monkeypatch.setattr(abl, "load_chunks", lambda: {})
        cfg_dir = abl.DIAG_DIR / "b_gemini_top6"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        sentinel = '{"id":"A0","verdict":"KEEPME"}\n'
        (cfg_dir / "rows.jsonl").write_text(sentinel, encoding="utf-8")
        abl.run_config("b_gemini_top6", None, False, force=True)
        # force => append, dòng cũ KHÔNG bị đè mất
        assert (cfg_dir / "rows.jsonl").read_text(encoding="utf-8").startswith(sentinel)


# ============================================================================ #6 metric khớp tính tay + trọng tài
class TestMetrics:
    def _seed_rows(self, tmp_path):
        cfg_dir = abl.DIAG_DIR / "a_oracle_qwen"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        rows = [
            {"id": "1", "family": "EXACT", "verdict": "PASS_CORRECT", "has_gold_chunk": True,
             "is_refusal": False, "answer_chars": 50, "unsupported": []},
            {"id": "2", "family": "EXACT", "verdict": "FAIL_FABRICATED", "has_gold_chunk": True,
             "is_refusal": False, "answer_chars": 40, "unsupported": ["x"]},
            {"id": "3", "family": "EXACT", "verdict": "FAIL_OVERREFUSAL", "has_gold_chunk": True,
             "is_refusal": True, "answer_chars": 0, "unsupported": []},
            {"id": "4", "family": "CLOZE", "verdict": "PASS_CORRECT", "has_gold_chunk": True,
             "is_refusal": False, "answer_chars": 30, "unsupported": []},
            {"id": "5", "family": "CLOZE", "verdict": "PENDING_GENERATION", "has_gold_chunk": True,
             "is_refusal": False, "answer_chars": 0, "unsupported": []},
        ]
        _write_jsonl(cfg_dir / "rows.jsonl", rows)
        (cfg_dir / "settings.json").write_text(
            json.dumps({"referee": verify.referee_fingerprint(), "env": {}, "skipped_items": []}),
            encoding="utf-8",
        )
        return cfg_dir

    def test_refusal_pass_correct_fabrication_khop_tinh_tay(self, tmp_path, monkeypatch):
        _point_paths(abl, tmp_path, [])
        self._seed_rows(tmp_path)
        summary = abl.summarize("a_oracle_qwen")
        overall = summary["overall"]
        decided = [r for r in map(str, ["1", "2", "3", "4"])]  # id 5 = PENDING -> loại
        assert overall["n"] == 4  # 4 câu "decided"
        # refusal_rate = 1 từ chối / 4 decided = 0,25
        assert overall["refusal_rate"] == 0.25
        # pass_correct = 2 (id1,id4) / 4 = 0,5
        assert overall["pass_correct"] == 2 and overall["pass_correct_rate"] == 0.5
        # answered = id1,id2,id4 (không refusal, answer_chars>0) = 3; bịa = id2 => 1/3
        assert overall["fabrication_rate_on_answered"] == round(1 / 3, 4)
        # pass_any (PASS_VERDICTS của trọng tài thật): id1,id4 => 2/4 = 0,5
        assert overall["pass_any_rate"] == round(2 / 4, 4)

    def test_dung_trong_tai_hien_hanh_chu_ky_khong_doi(self, tmp_path, monkeypatch):
        _point_paths(abl, tmp_path, [])
        self._seed_rows(tmp_path)
        summary = abl.summarize("a_oracle_qwen")
        assert summary["referee"] == "9f1179ccab74"
        assert verify.referee_fingerprint() == "9f1179ccab74"  # dùng trọng tài thật, không đổi chữ ký

    def test_dong_error_khong_tinh_vao_overall(self, tmp_path, monkeypatch):
        _point_paths(abl, tmp_path, [])
        cfg = self._seed_rows(tmp_path)
        with (cfg / "rows.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": "E", "error": "RateLimit", "latency_seconds": 1}) + "\n")
        summary = abl.summarize("a_oracle_qwen")
        assert summary["n_errors"] == 1
        assert summary["overall"]["n"] == 4  # dòng error bị loại khỏi overall


# ============================================================================ #7 bảng quyết định
class TestDecisionTable:
    def test_b_cao_a_thap_uu_tien_T4(self):
        assert abl.interpret_decision(0.09, 0.71)["label"] == "T4"

    def test_a_cao_uu_tien_T3(self):
        # (a) cao => BỎ (b), bất kể số (b)
        assert abl.interpret_decision(0.50, None)["label"] == "T3"
        assert abl.interpret_decision(0.50, 0.10)["label"] == "T3"

    def test_ca_hai_thap_uu_tien_T2_T6(self):
        assert abl.interpret_decision(0.05, 0.10)["label"] == "T2+T6"

    def test_a_sat_nguong_khong_ket_luan_duoc(self):
        assert abl.interpret_decision(0.15, 0.71)["label"] == "không kết luận được"

    def test_b_sat_nguong_khong_ket_luan_duoc(self):
        assert abl.interpret_decision(0.05, 0.30)["label"] == "không kết luận được"

    def test_bien_band_chi_lech_mot_chut(self):
        # BAND = 0,02: (a) 0,169 còn trong band -> không kết luận; 0,171 đã ra ngoài -> T3.
        # (b) 0,319 còn trong band; 0,321 ra ngoài -> T4.
        assert abl.interpret_decision(0.169, None)["label"] == "không kết luận được"
        assert abl.interpret_decision(0.171, None)["label"] == "T3"
        assert abl.interpret_decision(0.05, 0.319)["label"] == "không kết luận được"
        assert abl.interpret_decision(0.05, 0.321)["label"] == "T4"

    def test_a_thap_chua_co_b_cho_b(self):
        assert abl.interpret_decision(0.05, None)["label"] == "chờ (b)"
