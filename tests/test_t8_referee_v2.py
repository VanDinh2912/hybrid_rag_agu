"""B2 — trọng tài v2 (PA-2 + PA-20, duyệt 25-10): hồi quy hành vi + dụng cụ chấm lại.

PA-2  (`src/answer_guard.py`): token mở đầu cụm hoa theo chính tả ("Theo", "Tại", …)
      không còn được tính là tên riêng — gỡ dương-giả `Theo Bản`/`Theo Thông`.
PA-20 (`tools/loop/verify.py`): required_entities là số NGUYÊN VĂN 1–2 chữ số phải
      đứng độc lập — "1" không khớp oan trong "B1"/"2021" (ca C145524027648409).

Test KHÔNG phụ thuộc dữ liệu round: mọi ca là chuỗi dựng sẵn theo đúng bằng chứng đã
ghi ở docs/PENDING_APPROVAL.md (PA-2 24-10 23:08; PA-20 24-10 23:09).
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

from src.answer_guard import _PROPER_RUN_STOPWORDS, _scan_proper_runs, check_grounding  # noqa: E402
from src.text_utils import fold  # noqa: E402
from tools.loop import verify  # noqa: E402

V1_FINGERPRINT = "9f1179ccab74"  # chữ ký TRƯỚC PA-2/PA-20 — phải không còn là hiện tại
V2_FINGERPRINT = "2911c69f740d"  # chữ ký SAU PA-2+PA-20 (25-10): ghim tại đây, một chỗ duy nhất


# ------------------------------------------------------------------ PA-2: cụm proper-noun
class TestProperRunStopwords:
    def test_theo_ban_khong_con_la_ten_rieng(self):
        # Bằng chứng gốc: 2/25 id (b) dính cờ "Theo Bản".
        runs = _scan_proper_runs("Theo Bản mô tả thì ELO là 10.")
        texts = [t for _, _, t in runs]
        assert not any("Theo" in t for t in texts)
        assert all("Bản" not in t.split(" ")[0] for t in texts) or not texts

    def test_theo_thongbao_va_tai_khoan(self):
        runs = _scan_proper_runs(
            "Theo Thông báo số 45 ngày 10/2026, Trường Đại Học An Giang quy định mức 15.")
        texts = [t for _, _, t in runs]
        # "Theo" là stopword nên "Thông" rớt xuống thành cụm 1 từ -> không phải tên riêng.
        assert not any(t.startswith("Theo") or t.startswith("Thông") for t in texts)
        # "Trường Đại Học" (cả 3 từ hoa) vẫn PHẢI được phát hiện — stopword không ăn lan.
        assert any("Trường Đại Học" in t for t in texts)

    def test_danh_sach_stopword_khop_tai_lieu_duyet(self):
        expected = {fold(w) for w in {
            "Theo", "Tại", "Căn", "Các", "Trong", "Nếu", "Khi", "Vì", "Do",
            "Đối", "Phần", "Mục", "Về", "Bằng", "Từ", "Đến", "Với",
        }}
        assert _PROPER_RUN_STOPWORDS == expected

    def test_check_grounding_gỡ_dương_giả_theo_ban(self):
        # answer/cấu trúc dựng theo ca C10492769338965: nội dung đúng, cờ proper sai.
        # ("điểm ELO" cố ý tránh: "Điểm <A-Z>" là luật legal-ref CÓ THẬT, không liên quan PA-2.)
        g = check_grounding(
            "Theo Bản ghi nhận, ELO là 10.",
            ["Bản ghi nhận: ELO của học phần là 10."],
            "Học phần này có ELO bao nhiêu?",
        )
        assert not g.fabricated, [(e.kind, e.text) for e in g.unsupported]

    def test_check_grounding_vẫn_bắt_cụm_hoa_lạ_thật(self):
        # Cụm hoa KHÔNG có trong context và không mở đầu bằng stopword vẫn bị cờ.
        g = check_grounding(
            "Sinh viên nộp cho Quỹ Học Bổng Vượt Trội trước ngày 5.",
            ["Sinh viên nộp hồ sơ học bổng trước ngày 5."],
            "Nộp cho ai?",
        )
        assert g.fabricated


# ------------------------------------------------------------------ PA-20: số ngắn độc lập
class TestShortNumberBoundary:
    @pytest.mark.parametrize("entity,answer,expected", [
        # Đúng 4 ca đăng ký trong PA-20:
        ("1", "Sinh viên nhận ELO 9, mã B1, năm 2021", False),   # dương giả gốc
        ("1", "Sinh viên nhận ELO 1.", True),
        ("2024", "Áp dụng cho năm học 2024-2025", True),          # 4 số -> đường cũ
        ("2570", "Theo quyết định 2570/QĐ-DHAG", True),
        # Biên và bất biến lân cận:
        ("10", "Mức điểm ELO 10 được công bố", True),             # 2 số, đứng độc lập
        ("2", "Trang 2 của văn bản", True),
        ("1", "Mức 15 điểm", False),                              # "1" dính trong "15"
        ("12", "Tháng 12 hạn chót", True),
        ("1.500", "Nộp 1500đ học phí", True),                     # KHÔNG thắt đường _number_in
        ("DH24TA", "Lớp DH24TA nộp BHYT", True),                  # phi-số giữ nguyên
    ])
    def test_entity_in_answer(self, entity, answer, expected):
        assert verify._entity_in_answer(entity, answer) is expected

    def test_answer_covers_gold_không_con_pass_oan_ca_C1455(self):
        item = {"required_entities": ["1"]}
        assert verify._answer_covers_gold(item, "ELO 9, mã B1, năm 2021") is False
        assert verify._answer_covers_gold(item, "ELO 1, mã B1") is True

    def test_verdict_flip_pass_oan_thanh_incomplete(self):
        # Replay đúng khung chấm ca C1455: mọi thực thể trong câu trả lời ĐỀU có căn cứ
        # (không dính FAIL_FABRICATED), nhưng required "1" chỉ khớp trong "B1"/"2021" —
        # trọng tài v1 cho PASS_CORRECT oan, v2 phải hạ FAIL_INCOMPLETE.
        item = {
            "id": "X1", "family": "EXACT", "split": "test",
            "gold_chunk_id": 7, "required_entities": ["1"],
            "raw_query": "ELO của lớp B1 là bao nhiêu?",
        }
        result = {
            "answer": "Mức ELO 9 áp dụng cho lớp B1, năm 2021.",
            "contexts": ["Bảng quy đổi: lớp B1, năm 2021, mức ELO 9."],
            "sources": [{"rank": 1, "chunk_id": 7, "source": "kb.docx", "tier": "Tầng 2"}],
            "labels": {}, "latency_seconds": 1.0,
        }
        row = verify.score_item(item, result, top_k=6)
        assert row["verdict"] == "FAIL_INCOMPLETE", row["verdict"]


# ------------------------------------------------------------------ chữ ký & công cụ chấm lại
class TestFingerprintV2:
    def test_chu_ky_doi_va_oanh_dinh(self):
        fp = verify.referee_fingerprint()
        assert fp == V2_FINGERPRINT
        assert fp != V1_FINGERPRINT
        assert fp == verify.referee_fingerprint()  # deterministic trong cùng cây

    def test_snapshot_v1_tái_sinh_đúng_chữ_ký_cũ(self):
        """Snapshot VĨNH VIỄN ở tests/snapshots/referee_v1 (tmp/ sẽ bị PA-24 dọn)."""
        snap = ROOT / "tests" / "snapshots" / "referee_v1"
        h = hashlib.sha256()
        for p in (snap / "tools" / "loop" / "verify.py", snap / "src" / "answer_guard.py",
                  snap / "src" / "text_utils.py"):
            h.update(p.read_bytes())
        assert h.hexdigest()[:12] == V1_FINGERPRINT


class TestRescoreTool:
    def test_rescore_round_do_duoc_flip_va_khong_dung_round_cu(self, tmp_path, monkeypatch):
        from tools.diag import rescore_rounds_v2 as rs

        old_rounds = tmp_path / "rounds"
        new_rounds = tmp_path / "rounds_v2"
        r = old_rounds / "rz"
        r.mkdir(parents=True)
        item = {
            "id": "Z1", "family": "EXACT", "split": "test", "gold_chunk_id": 7,
            "required_entities": ["1"], "raw_query": "ELO của lớp B1 là bao nhiêu?",
        }
        row = {
            "id": "Z1", "item": item,
            "answer": "Mức ELO 9 áp dụng cho lớp B1, năm 2021.",
            # Mọi thực thể trong câu trả lời đều có căn cứ -> nhánh covers_gold là
            # nhánh QUYẾT ĐỊNH (không để FAIL_FABRICATED che mất phép thử PA-20).
            "contexts": ["Bảng quy đổi: lớp B1, năm 2021, mức ELO 9."],
            "sources": [{"rank": 1, "chunk_id": 7, "source": "kb.docx", "tier": "Tầng 2"}],
            "labels": {}, "latency_seconds": 1.0,
        }
        (r / "full.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        old_verdict = {**row, "verdict": "PASS_CORRECT", "severity": 0, "is_refusal": False}
        del old_verdict["item"]
        (r / "verdicts_full.jsonl").write_text(json.dumps(old_verdict, ensure_ascii=False) + "\n", encoding="utf-8")
        (r / "round_summary_full.json").write_text(
            json.dumps({"settings": {"referee": V1_FINGERPRINT}}), encoding="utf-8")
        ts = tmp_path / "testset.jsonl"
        ts.write_text(json.dumps(item, ensure_ascii=False) + "\n", encoding="utf-8")

        monkeypatch.setattr(rs, "ROUNDS_OLD", old_rounds)
        monkeypatch.setattr(rs, "ROUNDS_NEW", new_rounds)
        monkeypatch.setattr(rs, "TESTSET", ts)

        rep = rs.rescore_round("rz")
        assert rep["n_flips"] == 1
        flip = rep["flips"][0]
        assert flip["old"] == "PASS_CORRECT" and flip["new"] == "FAIL_INCOMPLETE"
        # Round cũ KHÔNG bị đụng tới:
        assert (r / "verdicts_full.jsonl").read_text(encoding="utf-8").count("PASS_CORRECT") == 1
        assert (new_rounds / "rz" / "verdicts_full.jsonl").exists()
        assert rep["referee_v2"] != V1_FINGERPRINT


# ------------------------------------------------------------------ snapshot v1 + chấm lại cross-version
class TestSnapshotRescore:
    """Hạ tầng "chấm lại round đã đóng sau khi trọng tài đổi" (B2):

    * snapshot tại `tests/snapshots/referee_v1` phải TỰ NẠP được (verify.py của nó tính
      ROOT từ `__file__`, nên chỉ cần copy đúng layout) và tự khai chữ ký v1;
    * helper subprocess phải chấm r7 khớp 100/100 verdict đã công bố — bằng chứng
      "round cũ so được với chính nó", không phải với bản mới;
    * snapshot bị sửa một byte -> kit phải NÉM LỖI, không được âm thầm báo lệch 0%.
    """

    SNAP = ROOT / "tests" / "snapshots" / "referee_v1"

    def test_snapshot_khai_nhan_dung_chu_ky_va_khac_hanh_vi_live(self):
        import subprocess
        code = (
            "import sys; sys.path.insert(0, 'tools/loop');"
            "import verify;"
            "print(verify.referee_fingerprint(),"
            " verify._entity_in_answer('1', 'ELO 9, mã B1, năm 2021'))"
        )
        p = subprocess.run([sys.executable, "-c", code], cwd=str(self.SNAP),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL)
        assert p.returncode == 0, p.stderr
        fp, loose = p.stdout.split()
        assert fp == V1_FINGERPRINT
        assert loose == "True", "bản v1 phải còn khớp oan '1' trong B1 — nếu không thì đây không phải v1"
        assert verify._entity_in_answer("1", "ELO 9, mã B1, năm 2021") is False, \
            "bản live phải đã đóng khoảng oan đó (PA-20)"

    def test_registry_quy_dinh_snapshot_theo_chu_ky(self):
        from tools.diag import council_kit as kit

        reg = kit.referee_version_registry(verify.referee_fingerprint())
        assert reg.get(V1_FINGERPRINT, "").endswith("referee_v1")
        assert verify.referee_fingerprint() in reg
        assert kit.snapshot_fingerprint(self.SNAP) == V1_FINGERPRINT

    def test_helper_cham_lai_r7_khop_100_trong_subprocess(self):
        from tools.diag import council_kit as kit

        out = kit.rescore_round_via_snapshot("r7", V1_FINGERPRINT)
        assert out["fingerprint"] == V1_FINGERPRINT
        assert out["n"] == 100 and out["khop"] == 100 and out["lech"] == []

    def test_snapshot_bi_sua_phai_nem_loi_khong_duoc_im(self, tmp_path, monkeypatch):
        import shutil

        from tools.diag import council_kit as kit

        bi = tmp_path / "referee_v1_doctored"
        shutil.copytree(self.SNAP, bi)
        vp = bi / "tools" / "loop" / "verify.py"
        vp.write_bytes(vp.read_bytes() + b"\n# them mot dong vo nghia\n")
        assert kit.snapshot_fingerprint(bi) != V1_FINGERPRINT
        monkeypatch.setattr(kit, "REFEREE_SNAPSHOTS", {V1_FINGERPRINT: bi})
        with pytest.raises(RuntimeError, match="chu_ky_snapshot_lech|helper snapshot chết"):
            kit.rescore_round_via_snapshot("r7", V1_FINGERPRINT)
