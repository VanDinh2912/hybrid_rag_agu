"""Nghiệm thu cuối, mục 6 — ba script trả lời **câu hỏi hội đồng** (bịa / trọng tài / gold@6).

Ba script được nghiệm thu ở hai lớp, và lớp nào cũng bắt buộc phải có răng:

* `TestCau1…` / `TestCau2…` / `TestCau3…` — ghim từng con số in ra, kèm đường dẫn file nguồn,
  để hội đồng hỏi "số này từ đâu" thì có đúng một câu trả lời.
* `TestRengCuaMayKiem` — nuôi từng loại sai (tỉ lệ bịa tính sai, trọng tài chấm khác, chữ ký
  giả, regex đọc chuỗi công bố hỏng, mẫu trống) và buộc script phải tự báo LỆCH / trả mã thoát 1.
  Không có lớp này thì một script in số sai vẫn "chạy ngon" và đó là loại lỗi nguy hiểm nhất.
* `TestDinhNghiaCuaKit` — khoá định nghĩa mẫu số (`answered_rows`, `gold_rate`) đúng như
  `gate.stats()`: đổi định nghĩa là đổi số đã công bố, phải đỏ ở đây trước.

Không gọi Gemini/Ollama/model; chỉ đọc `data/loop/`. Mọi ghi file đi vào `tmp_path`.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

kit = importlib.import_module("tools.diag.council_kit")
fab = importlib.import_module("tools.diag.council_check_fabrication")
ref = importlib.import_module("tools.diag.council_check_referee")
gold = importlib.import_module("tools.diag.council_check_gold6")
from tools.loop import gate, verify  # noqa: E402


@pytest.fixture(scope="module")
def cau1():
    return fab.build()


@pytest.fixture(scope="module")
def cau2():
    return ref.build()


@pytest.fixture(scope="module")
def cau3():
    return gold.build()


def _bo_truong_thoi_gian(d):
    """Loại các trường đo thời gian ra khỏi JSON để so tất định."""
    if isinstance(d, dict):
        return {k: _bo_truong_thoi_gian(v) for k, v in d.items()
                if k not in ("giay", "tong_giay")}
    if isinstance(d, list):
        return [_bo_truong_thoi_gian(x) for x in d]
    return d


# ---------------------------------------------------------------- 1. câu hỏi "có bịa không"
class TestCau1ChepBia:
    def test_phu_dung_ba_round_dang_dong(self, cau1):
        t = cau1["tong_hop"]
        assert t["n_rounds"] == 10
        assert t["n_rows"] == 1000 and t["n_answered"] == 380
        assert t["n_with_unsupported"] == 7
        assert t["by_verdict"] == {
            "FAIL_FABRICATED": 7,
            "FAIL_CONFIRMED_FALSE_PREMISE": 6,
            "FAIL_HALLUCINATED_ON_UNANSWERABLE": 30,
        }
        assert t["n_severe"] == 43
        assert t["so_dong_lech"] == 0, "mọi tỉ lệ tính lại phải khớp round_summary đã công bố"

    def test_ba_ca_nang_goc_la_mot_item_lap_lai(self, cau1):
        """CA bịa (FAB) duy nhất là MỘT item, không phải 7 lỗi độc lập — nói rõ để không phóng đại."""
        ids = cau1["tong_hop"]["ids_by_verdict"]["FAIL_FABRICATED"]
        assert ids == ["S115028976296200"]
        assert cau1["tong_hop"]["n_distinct_severe_items"] < cau1["tong_hop"]["n_severe"]

    def test_diem_mu_cua_thuoc_duoc_ghi_nguyen(self, cau1):
        """36/43 ca 'nói sai chủ động' có unsupported rỗng => 'fabrication = 0' không nghĩa là 'không sai'."""
        assert cau1["tong_hop"]["n_severe_blind"] == 36
        assert any("unsupported" in line or "trái ngữ cảnh" in line for line in cau1["diem_mu"])
        by_round = {r["round"]: r for r in cau1["theo_round"]}
        assert by_round["r8"]["fabrication_rate_published"] == 0.0
        assert by_round["r8"]["n_severe"] == 16, "r8 phải hiện 16 ca nặng DÙ báo cáo 0,0"

    def test_ci_cong_bo_tai_lap_diem_goc(self, cau1):
        ci = {c["round"]: c for c in cau1["ci"]}
        assert set(ci) == {"r5", "r7"}
        assert ci["r7"]["n_metric"] == 38 and ci["r7"]["point"] == 0.0263
        assert ci["r7"]["ci95"] == [0.0, 0.0789]
        assert ci["r5"]["n_metric"] == 31 and ci["r5"]["point"] == 0.0323
        assert ci["r5"]["ci95"] == [0.0, 0.0968]
        assert all(c["khop_diem_goc_vs_summary"] for c in ci.values())

    def test_che_tai_production_mac_dinh_tat(self, cau1):
        g = cau1["che_tai_production"]
        assert g["guard_mac_dinh_production_TAT"] is True
        assert g["ANSWER_GUARD_MIN_SCORE_mac_dinh"] == 0.6
        assert g["ANSWER_GUARD_MAX_UNSUPPORTED_mac_dinh"] == 1
        assert set(g["SEVERE_VERDICTS_trong_gate"]) == set(kit.SEVERE_VERDICTS)

    def test_mo_t_verdict_khong_thieu_verdict_nang(self, cau1):
        assert {d["verdict"] for d in cau1["dinh_nghia"]} == set(kit.SEVERE_VERDICTS)
        assert all(d["dieu_kien"] for d in cau1["dinh_nghia"])

    def test_in_bang_la_va_ma_thoat_0(self, tmp_path, capsys):
        out = tmp_path / "fab.json"
        assert fab.main(["--json", str(out)]) == 0
        d = json.loads(out.read_text(encoding="utf-8"))
        assert d["tong_hop"]["so_dong_lech"] == 0
        printed = capsys.readouterr().out
        assert "CÂU HỎI 1" in printed and "Từng ca cụ thể" in printed


# ---------------------------------------------------------------- 2. câu hỏi "trọng tài đáng tin"
V1 = "9f1179ccab74"   # trọng tài đã chấm MỌI round đã đóng (snapshot tests/snapshots/referee_v1)
V2 = "2911c69f740d"   # trọng tài hiện hành sau PA-2+PA-20 (cây làm việc 25-10)


class TestCau2TrongTai:
    def test_chu_ky_va_so_round_khop(self, cau2):
        """B2: hai thời kỳ dụng cụ đo. Round đã đóng mang v1; cây chạy mang v2;
        ĐỒ NÀO CŨNG PHẢI THUỘC ĐĂNG KÝ PHIÊN BẢN — chữ ký vô danh mới là đỏ."""
        fp = cau2["chu_ky"]
        assert fp["dang_chay"] == V2
        assert fp["dang_chay"] == verify.referee_fingerprint()
        assert fp["tinh_lai_tu_file"] == V2
        assert fp["dang_chay_khop_file"] is True, "chữ ký hàm phải khớp băm file (chống nói dối)"
        assert V1 in fp["danh_bien"] and V2 in fp["danh_bien"]
        assert fp["n_round_kiem"] == 19
        assert fp["n_chu_ky_khac_nhau"] == 1
        assert fp["round_lech"] == {}, "mọi round phải mang chữ ký đã đăng ký"

    def test_cham_lai_1000_cau_khop_het(self, cau2):
        """Round v1 phải được chấm lại bằng ĐÚNG v1 (subprocess snapshot), không phải v2 đang chạy."""
        t = cau2["tat_dinh"]
        assert t["n_rows_rescored"] == 1000
        assert t["n_rows_khop"] == 1000
        assert t["n_rows_lech"] == 0
        assert len(cau2["theo_round"]) == 10
        assert all(r["khop"] == r["n"] for r in cau2["theo_round"])
        assert all(r["referee"] == V1 and r["cach"] == "snapshot" for r in cau2["theo_round"]), (
            "chấm lại round đã đóng bằng bản khác bản đã chấm là vô nghĩa — phải in rõ cach=snapshot"
        )

    def test_verdict_khong_doi_khi_env_bi_doi(self, cau2):
        e = cau2["doc_lap_env"]
        assert e["giong_nhau"] is True
        assert e["verdict_sach"] == e["verdict_duc"]
        assert e["so_dong_env_da_dat"] == 8

    def test_file_trong_tai_va_trang_thai_git_thuc(self, cau2):
        files = {f["file"]: f for f in cau2["file_dung_cu_do"]}
        assert set(files) == {"tools/loop/verify.py", "src/answer_guard.py", "src/text_utils.py"}
        assert files["src/text_utils.py"]["git"] == "tracked-sach"
        # PA-26: hai file dụng cụ đo CHƯA vào git => không thể nói "không đổi so với HEAD".
        assert files["tools/loop/verify.py"]["git"] == "chua-commit"
        assert files["src/answer_guard.py"]["git"] == "chua-commit"

    def test_cong_tu_choi_so_hai_round_khac_chu_ky(self, cau2):
        g = cau2["cong_khoa_chu_ky"]
        assert g["tu_choi_khi_chu_ky_khac"] is True
        assert "trọng tài khác phiên bản" in g["thong_bao"]
        assert g["gate_sha256_24"] == kit.sha256_of(ROOT / "tools" / "loop" / "gate.py")[:24]

    def test_do_nhay_luat_so_cong_bo_dung_artifact(self, cau2):
        s = cau2["do_nhay_luat_so"]
        by = {r["round"]: r for r in s["rounds"]}
        assert by["r5"] == {"round": "r5", "n_rows": 100, "n_covers_now": 28,
                            "n_flips": 6, "n_flips_of_pass_correct": 1}
        assert sum(r["n_flips"] for r in s["rounds"]) == 11
        assert s["fingerprint_trong_audit"] == "9f1179ccab74"

    def test_chua_co_nhan_nguoi_phai_in_CHUA(self, cau2):
        h = cau2["dong_thuan_nguoi"]
        assert h["n_worksheet_rows"] == 60 and h["n_filled"] == 0
        assert h["cohen_kappa"] is None and h["overall_accuracy"] is None
        assert h["ket_luan"] == "CHƯA có bằng chứng con người"
        assert any("CHƯA" in line for line in cau2["da_va_chua"]["CHUA_CO"])

    def test_bang_diem_mu_du_10_round(self, cau2):
        b = cau2["diem_mu"]
        assert len(b["per_round"]) == 10
        assert (b["tong_answered"], b["tong_grounding_1"]) == (380, 373)
        assert (b["tong_severe"], b["tong_severe_grounding_1"]) == (43, 36)

    def test_in_va_ma_thoat_0(self, tmp_path, capsys):
        out = tmp_path / "ref.json"
        assert ref.main(["--json", str(out)]) == 0
        printed = capsys.readouterr().out
        assert "9f1179ccab74" in printed and "1000/1000" in printed


# ---------------------------------------------------------------- 3. câu hỏi "gold@6 là gì"
class TestCau3Gold6:
    def test_mau_va_mau_so(self, cau3):
        m = cau3["mau"]
        assert m["n_items"] == 811
        assert m["n_gold_items"] == 700
        assert m["n_no_gold"] == 111
        by = {r["family"]: r for r in m["by_family"]}
        assert by["HUMAN"] == {"family": "HUMAN", "n": 97, "n_gold": 0, "n_khong_gold": 97}
        assert by["REFUSE_OOD"]["n_gold"] == 0 and by["REFUSE_MISSING_DOC"]["n_gold"] == 0
        assert by["CLOZE_OCR"]["n_gold"] == 206

    def test_r0_tai_lap_dung_0_5186(self, cau3):
        r0 = cau3["tinh_lai"]["r0"]
        assert (r0["n_gold_items"], r0["n_hit"], r0["n_miss"]) == (700, 363, 337)
        assert r0["gold_rate"] == 0.5186
        assert r0["top_k"] == 6 and r0["referee"] == "9f1179ccab74"
        assert r0["rank_dist"] == {"1": 202, "2": 65, "3": 53, "4": 24, "5": 12, "6": 7}

    def test_bang_cong_bo_gate_vs_khong_co_dong_lech(self, cau3):
        assert cau3["so_dong_lech"] == 0
        assert len(cau3["cong_bo"]) == 7
        assert all(p.get("khop") for p in cau3["cong_bo"])
        r01 = next(p for p in cau3["cong_bo"]
                   if p["baseline"] == "r0" and p["candidate"] == "r1")
        assert r01["cong_bo"] == "0.5186->0.7657 tren 700 item"

    def test_gold_cao_khong_phai_tra_loi_dung(self, cau3):
        y = cau3["y_nghia_khong_phai_dung"]
        assert (y["n_gold_items"], y["n_hit"], y["gold_rate"]) == (80, 64, 0.8)
        assert y["pass_correct"] == 14
        assert y["overrefusal"] == 36 and y["retrieval_fail"] == 17

    def test_tran_xep_hang_va_nut_that_recall(self, cau3):
        o = cau3["tran_xep_hang"]
        assert o["pool_size_ghi_duoc"] == 12
        assert (o["gold_trong_top6"], o["gold_trong_pool"], o["gold_khong_vao_pool"]) == (518, 575, 125)
        assert o["rate_top6"] == 0.74 and o["rate_pool"] == 0.8214

    def test_dieu_kien_index_do_va_khong_duoc_so(self, cau3):
        ix = cau3["dieu_kien_index"]
        assert ix["index_cu"]["n_chunks"] == 361
        assert ix["index_moi"]["n_chunks"] == 342
        assert (ix["n_mat_neo"], ix["n_item_kiem_duoc"]) == (389, 797)
        assert ix["ty_le_mat_neo"] == 0.4881 and ix["do"] is True
        assert "PA-17" in ix["ket_luan"]

    def test_round_tai_lap_giong_nhet_tung_item(self, cau3):
        pairs = cau3["tai_lap"]["pairs"]
        assert pairs["r11 r14_repro_off"]["giong_nhet_tung_item"] is True
        assert pairs["r12 r15_repro_on"]["giong_nhet_tung_item"] is True
        assert pairs["r11 r14_repro_off"]["n_item_a"] == 811
        assert cau3["tai_lap"]["env_ghim"]["ENABLE_RERANKER"] == "0"

    def test_in_va_ma_thoat_0(self, tmp_path, capsys):
        out = tmp_path / "gold.json"
        assert gold.main(["--json", str(out)]) == 0
        printed = capsys.readouterr().out
        assert "0,5186" in printed and "0,8214" in printed


# ---------------------------------------------------------------- 4. răng của máy kiểm
class TestRengCuaMayKiem:
    def test_M1_ti_le_bia_tinh_sai_phai_in_LECH(self, monkeypatch):
        """Đột biến: `fabrication_rate` trả số sai => per_round phải tự phát hiện và main() phải đỏ."""
        monkeypatch.setattr(kit, "fabrication_rate", lambda rows: 0.5)
        r = fab.per_round("r7")
        assert r["khop"] is False
        assert fab.main([]) == 1

    # M2 series: sau B2, round r7 (v1) được chấm lại bằng snapshot subprocess — monkeypatch
    # `verify.score_item` không còn chạm tới đường đó nữa. Răng của bộ SO KHỚP được kiểm
    # qua móc `scorer` (đúng hợp đồng 3 trường: verdict / gold_in_top_k / số khẳng định).
    @staticmethod
    def _gia_mao_scorer(pub, **sai):
        def scorer(item, result, top_k=6):
            p = pub[item["id"]]
            out = {"verdict": p["verdict"], "gold_in_top_k": p["gold_in_top_k"],
                   "unsupported": list(p["unsupported"])}
            out.update({k: (f(out) if callable(f) else f) for k, f in sai.items()})
            return out
        return scorer

    def test_M2a_trong_tai_sai_verdict_phai_lo(self):
        """Đột biến răng #1: score trả verdict SAI nhưng các trường khác vẫn đúng => vẫn phải bắt."""
        pub = {r["id"]: r for r in kit.load_round("r7", "full")}
        scorer = self._gia_mao_scorer(
            pub, verdict=lambda f: "FAIL_FABRICATED" if f["verdict"] != "FAIL_FABRICATED" else "PASS_CORRECT")
        r = ref.rescore_layer("r7", scorer=scorer)
        assert r["cach"] == "test-hook"
        assert r["khop"] == 0 and len(r["lech"]) == 100

    def test_M2b_trong_tai_sai_cot_gold_phai_lo(self):
        """Đột biến răng #2: chỉ lật cột `gold_in_top_k` (verdict đúng) => vẫn phải đỏ."""
        pub = {r["id"]: r for r in kit.load_round("r7", "full")}
        scorer = self._gia_mao_scorer(pub, gold_in_top_k=lambda f: not f["gold_in_top_k"])
        r = ref.rescore_layer("r7", scorer=scorer)
        assert r["khop"] == 0 and len(r["lech"]) == 100

    def test_M2c_trong_tai_sai_so_khang_dinh_phai_lo(self):
        """Đột biến răng #3: chỉ thêm một khẳng định trái ngữ cảnh => vẫn phải đỏ."""
        pub = {r["id"]: r for r in kit.load_round("r7", "full")}
        scorer = self._gia_mao_scorer(
            pub, unsupported=lambda f: list(f["unsupported"]) + [{"kind": "number", "text": "9"}])
        r = ref.rescore_layer("r7", scorer=scorer)
        assert r["khop"] == 0 and len(r["lech"]) == 100

    def test_M2d_trong_tai_cham_khac_hoan_toan_phai_lo_va_do_main(self, monkeypatch):
        """Đột biến răng #4: verdict + mọi cột đều sai => cả 100 câu lệch VÀ main() trả 1."""
        scorer = lambda item, result, top_k=6: {
            "verdict": "FAIL_FABRICATED", "gold_in_top_k": False,
            "unsupported": [{"kind": "number", "text": "1"}]}
        r = ref.rescore_layer("r7", scorer=scorer)
        assert r["khop"] == 0 and len(r["lech"]) == 100

        # Nối lệch -> đỏ cả script, trên ĐƯỜNG THẬT (snapshot): giả lập snapshot nhả
        # 100 dòng lệch riêng round r7, các round khác chấm thật.
        orig = kit.rescore_round_via_snapshot

        def fake(rnd, version, phase="full"):
            if rnd != "r7":
                return orig(rnd, version, phase)
            return {"n": 100, "khop": 0, "giay": 0.0,
                    "lech": [{"round": rnd, "id": p["id"], "cong_bo": p["verdict"],
                              "tinhsan": "FAIL_FABRICATED"}
                             for p in kit.load_round(rnd, "full")]}

        monkeypatch.setattr(kit, "rescore_round_via_snapshot", fake)
        assert ref.main([]) == 1

    def test_M3_chu_ky_noi_doi_phai_lo(self, monkeypatch):
        """Đột biến: `referee_fingerprint()` nói dối so với nội dung file.

        Trước B2, patch này làm mọi round "lệch chữ ký" và đỏ. Sau B2, round v1 đã có
        snapshot đăng ký — cái phải đỏ là VẾ TỰ THÂN: chữ ký hàm đưa ra không khớp phép
        băm file tính lại độc lập (`dang_chay_khop_file`), và main() phải trả 1.
        """
        monkeypatch.setattr(verify, "referee_fingerprint", lambda: "deadbeefcafe", raising=True)
        fp = ref.fingerprint_layer()
        assert fp["dang_chay"] == "deadbeefcafe"
        assert fp["dang_chay_khop_file"] is False, "băm lại từ file phải lộ chữ ký giả"
        assert fp["tinh_lai_tu_file"] == V2
        assert ref.main([]) == 1

    def test_M4_regex_doc_chuoi_cong_bo_hong_khong_duoc_trong_ket_qua(self, monkeypatch):
        """Đột biến: GOLD_RE không khớp nữa => từng dòng phải gắn `loi`, không được biến mất."""
        import re as _re
        monkeypatch.setattr(gold, "GOLD_RE", _re.compile(r"khong_bao_gio_khop (?P<b>\d+)"), raising=True)
        rows = gold.published_layer({})
        assert rows, "artifact gate_vs vẫn phải được liệt kê"
        assert all("loi" in r for r in rows)
        assert gold.main([]) == 1

    def test_M5_gold_rate_tinh_sai_phai_LECH(self, monkeypatch):
        """Đột biến: mẫu số/điểm sai (0,99) => đối chiếu gate_vs phải báo LỆCH."""
        monkeypatch.setattr(kit, "gold_rate", lambda rows: (700, 693, 0.99))
        calc = {r: gold.recompute(r) for r in ("r0", "r1")}
        rows = gold.published_layer(calc)
        assert rows and not any(r.get("khop") for r in rows)

    def test_M6_mau_rong_khong_duoc_tinh_la_dat(self):
        """Không có round trong calc (artifact thiếu) => published_layer không được cấp 'khớp'."""
        rows = gold.published_layer({})
        assert rows
        assert all(not r.get("khop") for r in rows)

    def test_M9_round_tai_lap_lech_phai_lo(self, monkeypatch):
        """Răng của lớp tái lập: nếu trỏ nhầm file (r14 đọc bằng dữ liệu r12) phải báo KHÔNG ĐẠT."""
        that = kit.verdicts_path

        def trao_nhem(rnd, phase):
            return that("r12" if rnd == "r14_repro_off" else rnd, phase)

        monkeypatch.setattr(kit, "verdicts_path", trao_nhem)
        calc = {r: gold.recompute(r) for r in ("r11", "r12", "r14_repro_off", "r15_repro_on")}
        rp = gold.repro_layer(calc)
        assert rp["pairs"]["r11 r14_repro_off"]["giong_nhet_tung_item"] is False
        assert rp["pairs"]["r11 r14_repro_off"]["so_item_lech"] > 0

    def test_M7_khong_gui_file_khi_khong_co_dan(self, monkeypatch):
        """Ba script là CHỈ-ĐỌC: không được ghi file nào nếu không truyền --json."""
        def boom(self, *a, **k):
            raise AssertionError(f"script chỉ-đọc đã cố ghi {self}")
        monkeypatch.setattr(Path, "write_text", boom)
        monkeypatch.setattr(Path, "mkdir", lambda *a, **k: None)
        assert fab.main([]) == 0
        assert gold.main([]) == 0

    def test_M8_build_tat_dinh(self, tmp_path):
        """Hai lần chạy cùng artifact phải ra cùng một JSON (sau khi bỏ trường đo thời gian)."""
        a = _bo_truong_thoi_gian(ref.build())
        b = _bo_truong_thoi_gian(ref.build())
        assert a == b
        assert _bo_truong_thoi_gian(gold.build()) == _bo_truong_thoi_gian(gold.build())


# ---------------------------------------------------------------- 5. định nghĩa trong kit
class TestDinhNghiaCuaKit:
    ROWS = [
        {"id": "A", "verdict": "PASS_CORRECT", "is_refusal": False, "answer_chars": 10,
         "unsupported": [], "has_gold_chunk": True, "gold_in_top_k": True, "gold_rank_in_sources": 2},
        {"id": "B", "verdict": "FAIL_FABRICATED", "is_refusal": False, "answer_chars": 12,
         "unsupported": [{"kind": "number", "text": "9"}], "has_gold_chunk": True,
         "gold_in_top_k": True, "gold_rank_in_sources": 1},
        # câu từ chối KHÔNG thuộc mẫu số fabrication, dù có chữ trong answer
        {"id": "C", "verdict": "PASS_REFUSAL", "is_refusal": True, "answer_chars": 40,
         "unsupported": [], "has_gold_chunk": False, "gold_in_top_k": False,
         "gold_rank_in_sources": None},
        # PENDING_GENERATION cũng bị loại khỏi mẫu số (gate.stats dùng `decided`).
        # `answer_chars` PHẢI > 0 ở dòng này: nếu để 0 thì bộ lọc PENDING bị test bỏ qua
        # một cách tình cờ (đột biến xoá bộ lọc sống sót) — đã vấp thật ở mutation check đợt 1.
        {"id": "D", "verdict": "PENDING_GENERATION", "is_refusal": False, "answer_chars": 5,
         "unsupported": [], "has_gold_chunk": True, "gold_in_top_k": False,
         "gold_rank_in_sources": None},
    ]

    def test_answered_loai_tu_choi_va_pending(self):
        assert [r["id"] for r in kit.answered_rows(self.ROWS)] == ["A", "B"]

    def test_fabrication_rate_dung_mau_so(self):
        assert kit.fabrication_rate(self.ROWS) == 0.5, "1/2 câu đã trả lời có khẳng định trái ngữ cảnh"

    def test_gold_rate_mau_so_chi_item_co_chunk_vang(self):
        assert kit.gold_rate(self.ROWS) == (3, 2, 0.6667)

    def test_rounds_with_khong_bao_gio_trong(self):
        assert "r7" in kit.rounds_with("full")
        assert "r0" in kit.rounds_with("retrieval")
        assert set(kit.rounds_with("full")) >= {"r0", "r5", "r7", "r10"}

    def test_fmt_theo_quy_uoc_viet_va_none(self):
        assert kit.fmt(0.0263) == "0,0263"
        assert kit.fmt(None) == "—"
        assert kit.fmt(1000) == "1.000"
        assert kit.pct(363, 700) == "51,86%"

    def test_khong_duoc_phep_sua_dung_cu_do(self):
        """Bất biến phạm vi hai thời kỳ (B2, PA-2+PA-20 25-10).

        Trước: ghim sha của đúng 4 file. Sau khi trọng tài đổi bản hợp lệ (đã duyệt),
        ghim một con số duy nhất sẽ hoặc chặn sửa đúng, hoặc phải nới tay — cả hai đều
        mất răng. Ở đây mỗi thứ có chỗ của nó: gate.py VẪN không đổi; verify/answer_guard
        chốt đúng bản v2 đã duyệt; v1 lịch sử chỉ còn là snapshot byte-exact — sửa snapshot
        là chữ ký round mất nguồn và máy kiểm phải đỏ.
        """
        assert kit.sha256_of(ROOT / "tools" / "loop" / "gate.py")[:24] == "bf4bda89d8a360abbba25742"
        assert kit.sha256_of(ROOT / "tools" / "loop" / "verify.py")[:12] == "137ee884af3c"
        assert kit.sha256_of(ROOT / "src" / "answer_guard.py")[:12] == "ab4a8a73292f"
        assert kit.sha256_of(ROOT / "src" / "text_utils.py")[:12] == "5f810aa52b6b"
        assert verify.referee_fingerprint() == V2
        snap = ROOT / "tests" / "snapshots" / "referee_v1"
        assert kit.sha256_of(snap / "tools" / "loop" / "verify.py")[:12] == "6cc636689a8e"
        assert kit.sha256_of(snap / "src" / "answer_guard.py")[:12] == "40946176bc78"
        assert kit.sha256_of(snap / "src" / "text_utils.py")[:12] == "5f810aa52b6b"
        assert kit.snapshot_fingerprint(snap) == V1

    def test_severe_verdicts_khop_gate(self):
        assert set(kit.SEVERE_VERDICTS) == set(gate.SEVERE_VERDICTS)
