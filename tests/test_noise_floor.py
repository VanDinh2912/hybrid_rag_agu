"""Unit test cho T0 — noise floor (`tools/loop/noise_floor.py`).

Phạm vi (Test Engineer, 24-10): kiểm phần THUẦN deterministic của T0 — McNemar chính
xác, paired bootstrap/rate_ci (tái lập theo seed, xử lý mẫu nhỏ), bộ đếm dòng
`[AnswerRescue]`, quy tắc quyết định <5% đăng ký trước, cờ "mẫu quá nhỏ" theo family,
và hồi quy số verdict đổi chỗ trên dữ liệu thật r5↔r5b (nếu có).

Deterministic (nguyên tắc #2): không gọi mạng/model; dữ liệu nhỏ dựng trong trí nhớ.
Hồi quy #6 dùng round thật ĐỌC TỪ DISK, không sinh model, nên không cần marker slow.
"""
from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.loop import noise_floor as nf  # noqa: E402


# ============================================================================ #1 McNemar
class TestMcNemarExact:
    def test_hai_vector_giong_het_khong_bat_dong_p1_ci_chua_0(self):
        # (a) hai véc-tơ giống hệt => 0 cặp bất đồng => p=1, và CI ghép cặp chứa 0.
        flags = [1, 0, 1, 1, 0, 0, 1, 0]
        b, c = _discordant(flags, flags)
        assert (b, c) == (0, 0)
        assert nf.mcnemar_exact(b, c)["p_two_sided"] == 1.0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            boot = nf.paired_bootstrap(flags, flags, [1] * len(flags), [1] * len(flags), reps=200, seed=1)
        lo, hi = boot["ci95_percentile"]
        assert boot["mean_diff"] == 0.0
        assert lo <= 0.0 <= hi  # CI chứa 0 => không có chênh

    def test_doi_cho_xung_gam_b_can_c_p_lon(self):
        # (b) đối xứng b == c => kiểm định không có hướng => p lớn (>= 0,5).
        for k in (1, 2, 5, 10):
            res = nf.mcnemar_exact(k, k)
            assert res["b"] == res["c"] == k
            assert res["p_two_sided"] >= 0.5, (k, res["p_two_sided"])

    def test_b20c2_p_nho_khop_tinh_tay_duoi_1e_minus_6(self):
        # (c) b=20, c=2 => p nhỏ; đối chiếu phép CHÍNH XÁC tính tay, sai số < 1e-6.
        n = 22
        k = 2
        tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
        hand = min(1.0, 2 * tail)
        script = nf.mcnemar_exact(20, 2)["p_two_sided"]
        assert script < 0.05  # "p nhỏ"
        assert abs(script - hand) < 1e-6


def _discordant(x, y):
    b = sum(1 for a, bb in zip(x, y) if a == 0 and bb == 1)
    c = sum(1 for a, bb in zip(x, y) if a == 1 and bb == 0)
    return b, c


# ============================================================================ #2 Bootstrap CI
class TestBootstrapReproducibility:
    def test_seed_co_dinh_re_lap_y_het(self):
        base = [1, 0, 1, 1, 0, 0, 1, 0, 1, 0]
        cand = [0, 0, 1, 1, 0, 1, 1, 0, 1, 1]
        den = [1] * len(base)
        a = nf.paired_bootstrap(base, cand, den, den, reps=500, seed=20261023)
        b = nf.paired_bootstrap(base, cand, den, den, reps=500, seed=20261023)
        assert a == b  # byte-identical khi cùng seed

    def test_doi_seed_chi_lech_nho(self):
        base = [1, 0, 1, 1, 0, 0, 1, 0, 1, 0]
        cand = [0, 0, 1, 1, 0, 1, 1, 0, 1, 1]
        den = [1] * len(base)
        a = nf.paired_bootstrap(base, cand, den, den, reps=2000, seed=1)["mean_diff"]
        b = nf.paired_bootstrap(base, cand, den, den, reps=2000, seed=999)["mean_diff"]
        assert abs(a - b) < 0.05  # đổi seed chỉ lệch nhỏ (nhiễu Monte-Carlo)

    def test_ci_luon_chua_uoc_luong_diem(self):
        base = [1, 1, 1, 1, 0, 0, 0, 0]
        cand = [1, 1, 1, 1, 1, 0, 0, 0]
        den = [1] * len(base)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = nf.paired_bootstrap(base, cand, den, den, reps=1000, seed=7)
        lo, hi = r["ci95_percentile"]
        assert lo <= r["mean_diff"] <= hi

    def test_ci_chua_uoc_luong_diem_giai_tich_khong_chi_trung_binh_bootstrap(self):
        # "Ước lượng điểm" phải là hiệu tỉ lệ TÍNH TỪ DỮ LIỆU (0,55 - 0,40 = 0,15),
        # không phải trung bình các lượt bootstrap (kiểm tra vòng tròn). CI 95% của
        # hiệu ứng ghép cặp phải chứa đúng 0,15; rate_ci mỗi round phải chứa tỉ lệ thô.
        base = [1] * 40 + [0] * 60
        cand = [1] * 55 + [0] * 45
        den = [1] * len(base)
        point = sum(cand) / len(cand) - sum(base) / len(base)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            diff = nf.paired_bootstrap(base, cand, den, den, reps=2000, seed=20261023)
            ci_base = nf.rate_ci(base, den, seed=20261023)["ci95"]
            ci_cand = nf.rate_ci(cand, den, seed=20261023)["ci95"]
        lo, hi = diff["ci95_percentile"]
        assert lo <= point <= hi, (point, lo, hi)
        assert ci_base[0] <= 0.40 <= ci_base[1], ci_base
        assert ci_cand[0] <= 0.55 <= ci_cand[1], ci_cand

    def test_n0_khong_crash_tra_ket_qua_rong_khong_so_vo_nghia(self):
        with pytest.warns(UserWarning):
            r = nf.paired_bootstrap([], [], [], [], reps=100, seed=1)
        assert r["mean_diff"] is None
        assert r["ci95_percentile"] == [None, None]
        with pytest.warns(UserWarning):
            c = nf.rate_ci([], [], seed=1)
        assert c == {}

    def test_n1_canh_bao_khong_crash_ci_suy_bien(self):
        with pytest.warns(UserWarning):
            r = nf.paired_bootstrap([1], [0], [1], [1], reps=50, seed=1)
        assert r["mean_diff"] == -1.0  # xác định, không phải số ngẫu nhiên vô nghĩa
        assert r["ci95_percentile"] == [-1.0, -1.0]
        with pytest.warns(UserWarning):
            c = nf.rate_ci([1], [1], seed=1)
        assert c["ci95"] == [1.0, 1.0]


# ============================================================================ #3 Bộ đếm [AnswerRescue]
class TestCountAnswerRescue:
    def _line(self, kind, round_tag=None):
        token = f"[round={round_tag}] " if round_tag else ""
        return (
            f"{token}[AnswerRescue] "
            + {
                "attempt": "Đã thử lượt trích xuất, model vẫn từ chối — giữ nguyên từ chối",
                "error": "Lượt cứu lỗi (Timeout) — giữ nguyên từ chối",
                "unverified": "Không kiểm chứng được câu cứu (ValueError) — giữ nguyên từ chối",
                "below": "Câu cứu mới không đạt ngưỡng 0.6 (score=0.3) — giữ nguyên từ chối",
                "rescued": "Cứu một câu từ chối oan bằng lượt yêu cầu trích xuất.",
            }[kind]
        )

    def test_5_dong_thu_2_cuu_duoc_tra_5_2(self):
        log = "\n".join(
            [self._line("attempt"), self._line("below"), self._line("rescued"),
             self._line("error"), self._line("rescued")]
        )
        assert nf.count_answer_rescue(log) == (5, 2)

    def test_log_rong_tra_0_0_khong_chia_0(self):
        assert nf.count_answer_rescue("") == (0, 0)
        # (0,0) đưa vào quy tắc quyết định cũng không được chia cho 0:
        assert nf.rescue_decision(0, 0)["decision"] == "không đủ mẫu để xét"

    def test_dong_ho_khong_duoc_dem(self):
        # Dòng [AnswerRescue] dở dang/không khớp mốc -> bỏ qua, không đếm (kèm cảnh báo).
        with pytest.warns(UserWarning):
            assert nf.count_answer_rescue("[AnswerRescue] Cứu một câu…") == (0, 0)
        # Dòng không có tiền tố [AnswerRescue] bị bỏ qua hoàn toàn (không cảnh báo).
        assert nf.count_answer_rescue("log thường không liên quan") == (0, 0)

    def test_ba_loi_chu_cuu_khong_phai_cuu_duoc(self):
        # "Câu cứu mới không đạt ngưỡng" chứa chữ "cứu" nhưng KHÔNG được tính là cứu.
        log = "\n".join([self._line("below"), self._line("below"), self._line("rescued")])
        assert nf.count_answer_rescue(log) == (3, 1)

    def test_nhieu_round_tron_lan_chi_dem_dung_round(self):
        log = "\n".join(
            [self._line("rescued", "r5b"), self._line("attempt", "r5b"),
             self._line("rescued", "r9"), self._line("rescued", "r9"), self._line("rescued", "r9")]
        )
        assert nf.count_answer_rescue(log, round_tag="r5b") == (2, 1)
        assert nf.count_answer_rescue(log, round_tag="r9") == (3, 3)
        assert nf.count_answer_rescue(log) == (5, 4)  # không lọc = đếm hết


# ============================================================================ #4 Quy tắc <5%
class TestRescueDecisionRule:
    def test_duoi_nguong_bo_lever(self):
        assert nf.rescue_decision(1, 64)["decision"] == "bỏ lever"   # 1,56% (T0)
        assert nf.rescue_decision(1, 21)["decision"] == "bỏ lever"   # 0,0476 < 0,05

    def test_dung_nguong_giu_xem_xet(self):
        # Điểm biên: đúng 0,05 phải là "giữ xem xét" (nghiêm ngặt `<`), KHÔNG phải "bỏ lever".
        r = nf.rescue_decision(1, 20)
        assert r["ratio"] == 0.05
        assert r["decision"] == "giữ xem xét"

    def test_tren_nguong_giu_xem_xet(self):
        assert nf.rescue_decision(2, 20)["decision"] == "giữ xem xét"  # 0,10
        assert nf.rescue_decision(3, 10)["decision"] == "giữ xem xét"  # 0,30


# ============================================================================ #5 Cờ mẫu quá nhỏ
class TestFamilyTooSmallFlag:
    def test_family_n_nho_mang_co_mau_qua_nho(self):
        ids = [str(i) for i in range(10)]
        rows = [
            {"verdict": "PASS_CORRECT", "family": ("SMALL" if i < 9 else "BIG")}
            for i in range(10)
        ]
        stats = nf.family_flip_stats(ids, rows, rows)  # candidate == baseline -> không lật
        assert stats["SMALL"]["n_common"] == 9
        assert stats["SMALL"]["mẫu_quá_nhỏ"] is True     # n<10
        assert stats["BIG"]["n_common"] == 1
        assert stats["BIG"]["mẫu_quá_nhỏ"] is True

    def test_family_du_nguong_khong_bi_co(self):
        # n == 10 (đúng ngưỡng) phải KHÔNG bị cờ -> bảo vệ phép so sánh `<` (không phải `<=`).
        ids = [str(i) for i in range(10)]
        rows = [{"verdict": "PASS_CORRECT", "family": "OK"} for _ in ids]
        stats = nf.family_flip_stats(ids, rows, rows)
        assert stats["OK"]["n_common"] == 10
        assert stats["OK"]["mẫu_quá_nhỏ"] is False

    def test_dem_flip_theo_family(self):
        ids = ["1", "2", "3"]
        base = [{"verdict": "PASS_CORRECT", "family": "F"} for _ in ids]
        cand = [
            {"verdict": "FAIL_OVERREFUSAL", "family": "F"},  # lật
            {"verdict": "PASS_CORRECT", "family": "F"},      # không
            {"verdict": "PASS_REFUSAL", "family": "F"},      # lật
        ]
        stats = nf.family_flip_stats(ids, base, cand)
        assert stats["F"]["n_common"] == 3
        assert stats["F"]["n_flipped"] == 2
        assert stats["F"]["flip_rate"] == round(2 / 3, 4)


# ============================================================================ #6 Hồi quy trên r5/r5b
def _flip_count_manual(b_rows, c_rows):
    """Cách tính ĐỘC LẬP bằng vòng for thô — đối chứng cho count_verdict_flips (sum)."""
    total = 0
    for br, cr in zip(b_rows, c_rows):
        if br.get("verdict") != cr.get("verdict"):
            total += 1
    return total


class TestRegressionRealRounds:
    def _pair(self):
        rounds_root = REPO_ROOT / "data" / "loop" / "rounds"
        if not (rounds_root / "r5" / "verdicts_full.jsonl").exists() or not (
            rounds_root / "r5b" / "verdicts_full.jsonl"
        ).exists():
            pytest.skip("chưa có dữ liệu round thật r5/r5b trên đĩa")
        base = nf.load_verdicts("r5", rounds_root)
        cand = nf.load_verdicts("r5b", rounds_root)
        _agg, b_rows, c_rows, common = nf.stats_for_pair(base, cand)
        return b_rows, c_rows, common

    def test_tong_verdict_doi_khop_script_doc_lap(self):
        b_rows, c_rows, common = self._pair()
        helper = nf.count_verdict_flips(b_rows, c_rows)            # sum(...)
        manual = _flip_count_manual(b_rows, c_rows)                # vòng for
        via_list = len(nf.verdict_flips(common, b_rows, c_rows))   # len(flips)
        assert helper == manual == via_list

    def test_flip_cua_stats_doi_chieu_duoc(self):
        # stats_for_pair trả common; đối chiếu số item chung và tỉ lệ lật <= 1.
        b_rows, c_rows, common = self._pair()
        flips = nf.verdict_flips(common, b_rows, c_rows)
        assert len(flips) <= len(common)
        assert all(f["baseline_verdict"] != f["candidate_verdict"] for f in flips)
        # Mỗi flip có id nằm trong tập chung và mang family của baseline.
        idset = set(common)
        for f in flips:
            assert f["id"] in idset
