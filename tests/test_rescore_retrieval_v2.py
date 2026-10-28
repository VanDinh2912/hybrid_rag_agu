"""Test cho `tools/diag/rescore_retrieval_round_v2.py` (B3, PA-25) — chấm lại offline, 0 model.

Vì sao dụng cụ này cần răng: nó là con đường duy nhất để mở `gate` giữa round mới (chấm
bằng trọng tài v2) và baseline đã đóng r11 (chấm bằng v1). Nếu nó âm thầm đổi verdict hoặc
sửa round cũ thì toàn bộ kết luận r16-vs-r11 mất nghĩa — mà mất nghĩa thì không có tín hiệu
nào báo. Nên mỗi test đều kiểm CẢ hai phía: số chấm lại VÀ round gốc không một byte nào thay đổi.

Bất biến được ghim:
* 0 cuộc gọi model (chỉ `verify.score_item` trên văn bản đã lưu);
* bản công bố còn nguyên (sha256 từng file trước/sau);
* `retrieval.jsonl` chép sang thư mục mới NGUYÊN BYTE (attribute.py/bonus_paired.py cần nó);
* verdict lệch bản công bố ⇒ `main()` trả mã 1, không im lặng coi là tương đương.

Không đụng `data/loop/rounds/`: mọi round dựng trong `tmp_path`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.diag import rescore_retrieval_round_v2 as rr  # noqa: E402
from tools.loop import verify  # noqa: E402

V1 = "9f1179ccab74"
V2 = "2911c69f740d"


def _item(iid: str, gold: int) -> dict:
    return {
        "id": iid, "family": "EXACT", "split": "test", "gold_chunk_id": gold,
        "raw_query": f"Câu hỏi {iid} về Điều 5?", "gold_sentence": "Điều 5 quy định học lại.",
        "required_entities": ["Điều 5"],
    }


def _row(iid: str, gold: int, ranked: list[int]) -> dict:
    return {
        "id": iid, "item": _item(iid, gold), "answer": None, "normalized_query": f"Câu hỏi {iid} về Điều 5?",
        "contexts": [f"nội dung chunk {c}" for c in ranked],
        "sources": [{"rank": i + 1, "chunk_id": c, "source": "kb.docx", "tier": "Tầng 2", "chars": 12}
                    for i, c in enumerate(ranked)],
        "labels": {}, "retrieval_config": None, "error": None, "latency_seconds": 2.5,
    }


@pytest.fixture()
def round_env(tmp_path, monkeypatch):
    """Dựng round rz (3 dòng: vàng trong/ngoài cửa sổ + một dòng error) + bản verdict công bố."""
    old = tmp_path / "rounds"
    rz = old / "rz"
    rz.mkdir(parents=True)
    rows = [
        _row("A", 7, [7, 1, 2, 3, 4, 5, 6]),      # vàng hạng 1 -> PENDING_GENERATION
        _row("B", 9, [1, 2, 3, 4, 5, 6, 7]),      # vàng hạng 7 -> FAIL_RETRIEVAL
    ]
    errored = _row("C", 7, [7])
    errored["error"] = "RerankerUnavailable: không tải được"
    rows.append(errored)
    (rz / "retrieval.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    published = [
        {**verify.score_item(r["item"], r, top_k=6), "latency_seconds": r["latency_seconds"]}
        for r in rows[:2]
    ]
    published.append({"id": "C", "family": "EXACT", "split": "test", "verdict": "FAIL_SYSTEM_ERROR",
                      "severity": 3, "raw_query": "Câu hỏi C về Điều 5?", "answer_preview": "",
                      "unsupported": [], "detail": {"error": errored["error"]}, "latency_seconds": 2.5})
    (rz / "verdicts_retrieval.jsonl").write_text(
        "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in published), encoding="utf-8")
    (rz / "round_summary_retrieval.json").write_text(json.dumps({
        "round": "rz",
        "settings": {"referee": V1, "top_k": 6, "enable_classifier": "1",
                     "retrieval_reranker": {"enabled": True, "query_convention": "fold(query)"}},
        "n_scored": 3, "verdict_counts": {"PENDING_GENERATION": 1, "FAIL_RETRIEVAL": 1,
                                          "FAIL_SYSTEM_ERROR": 1},
    }, ensure_ascii=False), encoding="utf-8")

    ts = tmp_path / "testset.jsonl"
    ts.write_text("".join(json.dumps(r["item"], ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    new = tmp_path / "rounds_v2"
    monkeypatch.setattr(rr, "ROUNDS_OLD", old)
    monkeypatch.setattr(rr, "ROUNDS_NEW", new)
    monkeypatch.setattr(rr, "TESTSET", ts)
    return {"old": old, "rz": rz, "new": new, "rows": rows, "published": published}


def _hash_tree(path: Path) -> dict[str, str]:
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file()}


class TestKhongDungBanCongBo:
    def test_toan_bo_file_round_cu_guyen_byte(self, round_env):
        before = _hash_tree(round_env["old"])
        rr.rescore("rz")
        assert _hash_tree(round_env["old"]) == before, "chấm lại PHẢI chỉ đọc round cũ"

    def test_retrieval_jsonl_chep_sang_nguyen_byte(self, round_env):
        rr.rescore("rz")
        src = (round_env["rz"] / "retrieval.jsonl").read_bytes()
        dst = (round_env["new"] / "rz" / "retrieval.jsonl").read_bytes()
        assert dst == src and len(src) > 0

    def test_thu_muc_moi_tu_chua_du_bo_cua_cong_cu_ghep_cap(self, round_env):
        rep = rr.rescore("rz")
        d = round_env["new"] / "rz"
        for name in ("retrieval.jsonl", "verdicts_retrieval.jsonl", "round_summary_retrieval.json"):
            assert (d / name).exists(), name
        summary = json.loads((d / "round_summary_retrieval.json").read_text(encoding="utf-8"))
        assert summary["settings"]["referee"] == verify.referee_fingerprint() == V2
        assert summary["referee_original"] == V1
        # `gate.compatibility()` còn so testset/top_k/generator/normalize_query/enable_classifier
        # ⇒ những key đó phải được sao sang, không được để trống.
        assert summary["settings"]["enable_classifier"] == "1"
        assert summary["settings"]["retrieval_reranker"]["query_convention"] == "fold(query)"
        assert summary["rescore_of"].endswith("rounds/rz/retrieval.jsonl")
        assert rep["n_rows"] == 3


class TestSoChotVoiBanCongBo:
    def test_khong_lech_thi_bao_duong_va_ma_thoat_0(self, round_env):
        rep = rr.rescore("rz")
        assert rep["n_diff_vs_published"] == 0 and rep["n_item_drift"] == 0
        assert rep["verdict_counts"] == {"PENDING_GENERATION": 1, "FAIL_RETRIEVAL": 1,
                                         "FAIL_SYSTEM_ERROR": 1}
        assert rep["published_counts"] == rep["verdict_counts"]
        out = round_env["new"] / "report.json"
        assert rr.main(["--rounds", "rz", "--out", str(out)]) == 0
        assert json.loads(out.read_text(encoding="utf-8"))["rounds"][0]["round"] == "rz"

    def test_dong_error_van_la_fail_system_error(self, round_env):
        rep = rr.rescore("rz")
        rows = [json.loads(l) for l in
                (round_env["new"] / "rz" / "verdicts_retrieval.jsonl").read_text(encoding="utf-8").splitlines()]
        by_id = {r["id"]: r for r in rows}
        assert by_id["C"]["verdict"] == "FAIL_SYSTEM_ERROR"
        assert by_id["B"]["verdict"] == "FAIL_RETRIEVAL"
        assert by_id["A"]["verdict"] == "PENDING_GENERATION"
        assert rep["verdict_counts"] == dict(rep["published_counts"])

    def test_lech_verdict_phai_bao_va_ma_thoat_1(self, round_env, monkeypatch):
        """Dụng cụ chấm phải TỰ BÁO khi số không khớp bản đã công bố — im lặng là loại lỗi
        nguy hiểm nhất: baseline mới trông hợp lệ nhưng đã đổi nghĩa."""
        monkeypatch.setattr(
            rr, "score_item",
            lambda item, row, top_k=6: {**verify.score_item(item, row, top_k=top_k),
                                        "verdict": "PASS_CORRECT"} if row["id"] == "B"
            else verify.score_item(item, row, top_k=top_k),
        )
        rep = rr.rescore("rz")
        assert rep["n_diff_vs_published"] == 1
        diff = rep["diffs"][0]
        assert diff["id"] == "B" and diff["old"] == "FAIL_RETRIEVAL" and diff["new"] == "PASS_CORRECT"
        out = round_env["new"] / "report.json"
        assert rr.main(["--rounds", "rz", "--out", str(out)]) == 1

    def test_lech_cung_verdict_nhung_khac_gold_in_top_k_cung_bao(self, round_env, monkeypatch):
        good = rr.rescore("rz")
        assert good["n_diff_vs_published"] == 0

        def fake(item, row, top_k=6):
            v = verify.score_item(item, row, top_k=top_k)
            if row["id"] == "A":
                v["gold_in_top_k"] = False
            return v

        monkeypatch.setattr(rr, "score_item", fake)
        rep = rr.rescore("rz")
        assert rep["n_diff_vs_published"] == 1
        assert rep["diffs"][0] == {"id": "A", "old": "PENDING_GENERATION", "new": "PENDING_GENERATION",
                                   "old_gold": True, "new_gold": False}

    def test_item_drift_duoc_dem_khong_tu_doi_ben_nao(self, round_env, monkeypatch):
        """Testset hiện hành khác item đã lưu ⇒ đếm chênh, chấm theo item đã lưu (bằng chứng
        mà round kiến tạo), không âm thầm thay đề bài."""
        ts = Path(round_env["old"]).parent / "testset_drift.jsonl"
        items = [dict(r["item"]) for r in round_env["rows"]]
        items[0]["gold_sentence"] = "Bỏ dấu và đổi nội dung."
        ts.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
        monkeypatch.setattr(rr, "TESTSET", ts)
        rep = rr.rescore("rz")
        assert rep["n_item_drift"] == 1
        assert rep["n_diff_vs_published"] == 0


class TestRengCuaDungCu:
    def test_round_khong_co_retrieval_jsonl_thi_dung(self, round_env):
        with pytest.raises(SystemExit, match="không có retrieval.jsonl"):
            rr.rescore("khong_ton_tai")

    def test_dong_thieu_khac_id_thi_dung(self, round_env):
        p = round_env["rz"] / "retrieval.jsonl"
        lines = p.read_text(encoding="utf-8").splitlines()
        corrupt = json.loads(lines[0])
        corrupt["id"] = "KHAC"
        p.write_text(json.dumps(corrupt, ensure_ascii=False) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="dòng thiếu/khác id"):
            rr.rescore("rz")

    def test_referee_v1_thi_tu_choi_cham_lai(self, round_env, monkeypatch):
        """Chặn ca chạy dụng cụ khi PA-2/PA-20 CHƯA áp dụng — chữ ký phải là v2."""
        monkeypatch.setattr(rr.verify, "referee_fingerprint", lambda: V1)
        with pytest.raises(SystemExit, match="vẫn là v1"):
            rr.main(["--rounds", "rz"])

    def test_khong_goi_model_trong_dong_lai(self, round_env, monkeypatch):
        """0 lượt sinh: chặn mọi đường gọi model ở tầng pipeline/generator."""
        import src.core.pipeline as pipeline_module

        def explode(*a, **k):
            raise AssertionError("chấm lại offline mà chạm pipeline.run/retrieve")

        monkeypatch.setattr(pipeline_module.HybridRAGPipeline, "run", explode, raising=False)
        monkeypatch.setattr(pipeline_module.HybridRAGPipeline, "retrieve", explode, raising=False)
        assert rr.rescore("rz")["n_rows"] == 3

    def test_tat_dinh_cham_lai_hai_lan_cho_cung_verdict(self, round_env):
        def rows() -> list[dict]:
            text = (round_env["new"] / "rz" / "verdicts_retrieval.jsonl").read_text(encoding="utf-8")
            return [json.loads(line) for line in text.splitlines() if line.strip()]

        rr.rescore("rz")
        first = rows()
        rr.rescore("rz")
        assert rows() == first
