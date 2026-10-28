# -*- coding: utf-8 -*-
"""Unit test cho bản kiểm chứng đầu ra bộ chuẩn hóa câu hỏi (P5.16).

Ca bệnh ĐO THẬT, không phải tưởng tượng. Vòng lặp P5 lưu `normalized_query` của 300 lượt
sinh (100 item x 3 round r0/r1/r3). 16/300 bản chuẩn hóa mất hơn 70% token câu gốc, chia
làm hai mode:

  (a) ECHO NGUYÊN VĂN một dòng few-shot. Item `N148008092394710` (hỏi "từ ngày ra thông
      báo đến áp dụng từ thời điểm nào?"), `Y57173144541416` (hỏi mua BHYT 2026) và
      `T224347701010571` (hỏi hình thức trực tuyến) — ba câu hỏi KHÁC nhau — cùng nhận
      một output "Sinh viên: Bị điểm rèn luyện loại yếu thì có bị đuổi học không ad?",
      Y HỆT nhau qua cả ba round (nhiệt độ 0.0, không phải nhiễu).
  (b) TỰ TRẢ LỜI thay vì chuẩn hóa. Item `N143662722487347` (hỏi mức phụ cấp nội quy)
      nhận output "Mức độ hoàn thành: 9/10" — đúng cái mà System Prompt cấm
      ("không tự trả lời câu hỏi").

Vì `src/core/pipeline.py` đưa `normalized_query` vào CẢ truy xuất lẫn sinh, item hỏng từ gốc
thì không lever nào cứu được: 5/23 ca `FAIL_RETRIEVAL` của r1 ở pha đắt thuộc nhóm này.

Test khóa ba chuyện: mặt nạ TẮT-mặc-định (hành vi cũ từng ký tự), hai mode hỏng bị bắt,
và bản chuẩn hóa HỢP LỆ (được phép đổi chữ) không bị chặn oan.
"""

from __future__ import annotations

import pytest

from src.core.query_normalizer import (
    BASE_EXAMPLES,
    DEFAULT_NORMALIZE_MIN_CONTAINMENT,
    content_tokens,
    normalized_output_rejection,
    normalize_min_containment,
    normalize_sanity_guard_enabled,
    normalize_user_query,
    prompt_example_lines,
    token_containment,
)
from src.text_utils import fold

ECHOED_EXAMPLE = "Sinh viên: Bị điểm rèn luyện loại yếu thì có bị đuổi học không ad?"
ANSWER_INSTEAD = "Mức độ hoàn thành: 9/10"

RAW_NUMERIC_QUESTION = "Mức thực tập chap hanh nội quy là bao nhiêu?"
GOOD_REWRITE = "Mức độ hoàn thành nội quy được tính bao nhiêu?"


class FakeClient:
    """Giả lập LocalSLM: chỉ cần .generate(prompt, temperature=...)."""

    def __init__(self, output: str):
        self.output = output
        self.calls = []

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        self.calls.append(prompt)
        return self.output


# --- hợp đồng env -----------------------------------------------------------


class TestCaiThat:
    def test_mac_dinh_tat_va_nguong_mac_dinh(self, monkeypatch):
        monkeypatch.delenv("NORMALIZE_SANITY_GUARD", raising=False)
        monkeypatch.delenv("NORMALIZE_MIN_CONTAINMENT", raising=False)
        assert normalize_sanity_guard_enabled() is False
        assert normalize_min_containment() == DEFAULT_NORMALIZE_MIN_CONTAINMENT == 0.3

    @pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
    def test_bat(self, monkeypatch, value):
        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", value)
        assert normalize_sanity_guard_enabled() is True

    @pytest.mark.parametrize("value", ["0", "", "false", "off"])
    def test_tat(self, monkeypatch, value):
        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", value)
        assert normalize_sanity_guard_enabled() is False

    @pytest.mark.parametrize(
        "raw,expected",
        [("0.5", 0.5), ("5", 1.0), ("-1", 0.0), ("ranh", DEFAULT_NORMALIZE_MIN_CONTAINMENT)],
    )
    def test_nguong_clamp_va_chap_gia_tri_hong(self, monkeypatch, raw, expected):
        monkeypatch.setenv("NORMALIZE_MIN_CONTAINMENT", raw)
        assert normalize_min_containment() == expected


# --- hình phạt deterministic -------------------------------------------------


class TestDoLuong:
    def test_ban_chuan_hoa_tot_giu_du_token(self):
        # content_tokens đã fold nên "Mức" -> "muc": so không dấu, cùng chiều phần còn lại.
        assert "muc" in content_tokens(RAW_NUMERIC_QUESTION)
        assert token_containment(RAW_NUMERIC_QUESTION, GOOD_REWRITE) >= 0.5
        assert normalized_output_rejection(RAW_NUMERIC_QUESTION, GOOD_REWRITE) == ""

    def test_echo_dong_few_shot_bi_bat_khong_can_nguong(self):
        why = normalized_output_rejection(RAW_NUMERIC_QUESTION, ECHOED_EXAMPLE)
        assert "few-shot" in why

    def test_model_tu_tra_loi_bi_bat(self):
        assert "mất nội dung" in normalized_output_rejection(RAW_NUMERIC_QUESTION, ANSWER_INSTEAD)

    def test_output_rong_bi_bac(self):
        assert normalized_output_rejection(RAW_NUMERIC_QUESTION, "   ") == "output rỗng"

    def test_danh_sach_cam_lay_tu_chinh_BASE_EXAMPLES_khong_co_ban_sao(self):
        """Sửa few-shot thì gate tự theo — không có bản sao thứ hai để lệch âm."""
        lines = prompt_example_lines()
        for ex in BASE_EXAMPLES:
            assert fold(ex["raw"]) in lines
            assert fold(ex["normalized"]) in lines
            assert fold(f"Sinh viên: {ex['raw']}") in lines
        assert len(lines) == 3 * len(BASE_EXAMPLES)

    def test_ba_ca_benh_that_trong_vong_lap_deu_bi_bac(self):
        """Chấm lại đúng các ca đã lưu ở r0/r1/r3 (không gọi model)."""
        cases = [
            ("Tu ngay ra thong bao den ap dung tu thoi diem nao?", ECHOED_EXAMPLE),
            ("phải mua BHYT năm học là 2026, thông tin này có đúng không?", ECHOED_EXAMPLE),
            (RAW_NUMERIC_QUESTION, ANSWER_INSTEAD),
            (
                "Triết học là 660.000, thông tin này có đúng theo quy định không?",
                "Triết học có mã môn học là gì, bao nhiêu tín chỉ và có môn học trước là môn nào?",
            ),
        ]
        for raw, norm in cases:
            assert normalized_output_rejection(raw, norm), f"lọt: {raw[:30]!r} -> {norm[:30]!r}"


# --- nối dây vào normalize_user_query ---------------------------------------


class TestHanhViKhiTatKhongDoi:
    def test_tat_gate_thi_echo_van_duoc_tra_ve_dung_nhu_cu(self, monkeypatch):
        """Mặc định TẮT = không đổi một ký tự hành vi đã nghiệm thu."""
        monkeypatch.delenv("NORMALIZE_SANITY_GUARD", raising=False)
        client = FakeClient(ECHOED_EXAMPLE)
        assert normalize_user_query(client, RAW_NUMERIC_QUESTION) == ECHOED_EXAMPLE
        assert len(client.calls) == 1


class TestHanhViKhiBat:
    def test_echo_few_shot_bat_ve_cau_goc(self, monkeypatch):
        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", "1")
        client = FakeClient(ECHOED_EXAMPLE)
        assert normalize_user_query(client, RAW_NUMERIC_QUESTION) == RAW_NUMERIC_QUESTION

    def test_model_tu_tra_loi_bat_ve_cau_goc(self, monkeypatch):
        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", "1")
        client = FakeClient(ANSWER_INSTEAD)
        assert normalize_user_query(client, RAW_NUMERIC_QUESTION) == RAW_NUMERIC_QUESTION

    def test_ban_chuan_hoa_hop_le_giuyen_nguyen_tra_ve(self, monkeypatch):
        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", "1")
        client = FakeClient(GOOD_REWRITE)
        assert normalize_user_query(client, RAW_NUMERIC_QUESTION) == GOOD_REWRITE

    def test_nhan_label_dau_dong_van_duoc_nhan_dien_la_hop_le(self, monkeypatch):
        """`clean_normalized_text` đã bóc nhãn 'Chuẩn hóa:' trước gate — gate không bóc lại."""
        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", "1")
        client = FakeClient(f"Chuẩn hóa: {GOOD_REWRITE}")
        assert normalize_user_query(client, RAW_NUMERIC_QUESTION) == GOOD_REWRITE

    def test_mo_tat_phai_in_ra_log(self, monkeypatch, capsys):
        """Bất biến vòng lặp: rule không đo được thì không tồn tại. Path từ chối phải đếm được."""
        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", "1")
        normalize_user_query(FakeClient(ECHOED_EXAMPLE), RAW_NUMERIC_QUESTION)
        out = capsys.readouterr().out
        assert "[QueryNormalizer]" in out and "Bác bản chuẩn hóa" in out

    def test_khi_bat_gate_that_bai_van_giu_nguyen_duong_fallback(self, monkeypatch):
        """Model trả về chuỗi rỗng -> fallback câu gốc (hành vi cũ), gate không lên tiếng."""
        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", "1")
        client = FakeClient("")
        assert normalize_user_query(client, RAW_NUMERIC_QUESTION) == RAW_NUMERIC_QUESTION

    def test_ham_goi_loi_khong_bi_gate_bien_doi(self, monkeypatch):
        """Client raise -> vẫn fallback câu gốc như cũ, không nhân đôi lỗi."""

        class Boom:
            def generate(self, prompt, temperature=0.0):
                raise RuntimeError("ollama khong chay")

        monkeypatch.setenv("NORMALIZE_SANITY_GUARD", "1")
        assert normalize_user_query(Boom(), RAW_NUMERIC_QUESTION) == RAW_NUMERIC_QUESTION
