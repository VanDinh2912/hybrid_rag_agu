# -*- coding: utf-8 -*-
"""Unit test lớp "cứu câu từ chối oan" (P5.12, ENABLE_ANSWER_RESCUE).

Bằng chứng đo thật từ vòng lặp P5 (round r1, 100 item pha sinh): 38 ca FAIL_OVERREFUSAL,
35 ca có câu trả lời NGUYÊN VĂN trong prompt; áp `check_grounding` lên chính câu vàng thì
37/38 ca đi qua (guard không buộc phải chặn); replay 38 ca với guard TẮT cho 31 ca model
tự từ chối, 4 ca model trả lời nhưng bản nháp lệch căn cứ, 3 ca đáng lẽ được chấp nhận.

Test này KHÔNG đánh giá hiệu nghiệm của lớp cứu — việc đó thuộc round r3 và cổng gate.
Nó chỉ khóa hợp đồng an toàn: lời cứu được nhận khi và chỉ khi nó đi qua đúng
`check_grounding` của guardrail, để lớp này không bao giờ đổi "không biết" thành
"biết sai" — thà mất một câu trả lời còn hơn có một câu bịa.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from src.generator import (
    REFUSAL_TEXT,
    RESCUE_INSTRUCTION,
    QwenGenerator,
    answer_rescue_enabled,
    demands_specific_value,
    looks_like_refusal,
    rescue_min_score,
)

DOC = {
    "content": "Điều 14. Mức đóng bảo hiểm y tế: sinh viên đóng 546.480đ/12 tháng/SV.",
    "source": "05-tb-ctsv-bhyt.pdf",
    "tier": "1",
    "chunk_id": 11,
}
QUESTION = "Mức đóng bảo hiểm y tế của sinh viên là bao nhiêu?"


def make_generator() -> QwenGenerator:
    return QwenGenerator(use_cache=False)


def call_rescue(
    *,
    text,
    generate_fn,
    question=QUESTION,
    docs=None,
    question_type=None,
    prompt="PROMPT: ",
    raw_query=None,
):
    gen = make_generator()
    return gen._rescue_refusal(
        text=text,
        question=question,
        docs=docs if docs is not None else [DOC],
        prompt=prompt,
        generate_fn=generate_fn,
        question_type=question_type,
        raw_query=raw_query,
    )


class TestCauTruc:
    def test_mac_dinh_tat(self, monkeypatch):
        monkeypatch.delenv("ENABLE_ANSWER_RESCUE", raising=False)
        assert answer_rescue_enabled() is False

    def test_loi_tu_choi_nhan_duoc_ca_bien_the_mat_dau(self):
        assert looks_like_refusal(REFUSAL_TEXT)
        assert looks_like_refusal("Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời.")
        assert looks_like_refusal("Tôi không tìm thấy thông tin này trong tài liệu.")
        assert looks_like_refusal("")
        assert not looks_like_refusal("Sinh viên đóng 546.480đ/12 tháng (Điều 14).")

    def test_cau_hoi_xin_gia_tri_cu_the_moi_la_doi_tuong_cuu(self):
        assert demands_specific_value(QUESTION)
        assert demands_specific_value("Lễ bế giảng tổ chức vào ngày nào?")
        assert not demands_specific_value("Chúc mừng năm mới")

    def test_me_cau_hoi_dan_xuat_cua_bo_test_cung_du_dieu_kien_cuu(self):
        """Đo trên r1: danh sách cũ chỉ bắt 22/38 ca over-refusal; thêm các mẫu có sẵn
        trong test bank (CLOZE/NUMERIC/REVERSE_LEGAL) nâng lên 37/38."""
        assert demands_specific_value(
            "Điền giá trị còn thiếu cho đoạn trích từ Bản mô tả chương trình đào tạo."
        )
        assert demands_specific_value("Cho biết mức thu thường xuyên hiện hành.")
        # OCR mất dấu vẫn khớp vì so sánh bằng fold() — cùng chiều với looks_like_refusal.
        assert demands_specific_value("Tu ngay ra thong bao den ap dung tu thoi diem nao?")

    def test_cau_bay_phai_khong_dung_ngoai_duong_cuu(self):
        """CA COC Y: thêm "phải không" vào danh sách sẽ kéo cả 3 ca TRAP "… là 1232000
        phải không?" (đang từ chối ĐÚNG ở r1) vào đường cứu."""
        assert not demands_specific_value("Quản trị kinh doanh là 1232000 phải không?")
        assert not demands_specific_value("trình đào tạo là 7480202 phải không?")


class TestXetDieuKienTrenCauHoiGoc:
    """P5.12b: vì sao r3 chỉ thử 9/60 lần.

    `pipeline.run` truyền `normalized_query` xuống generator, mà bộ chuẩn hóa (Local
    SLM) đôi khi trả về MỘT CÂU KHÁC — đo trên 300 lượt sinh: 16/300 bản chuẩn hóa mất
    hơn 70% token câu gốc, trong đó 7 ca chép nguyên văn một dòng few-shot ("Sinh viên:
    Bị điểm rèn luyện loại yếu thì có bị đuổi học không ad?") và 1 ca TỰ TRẢ LỜI thay
    vì chuẩn hóa ("Mức độ hoàn thành: 9/10"). Trên 61 câu từ chối của r3: 60/61 đủ điều kiện
    nếu xét câu gốc, nhưng chỉ 54/61 nếu xét bản chuẩn hóa.
    """

    def test_ban_chuan_hoa_lech_van_duoc_cuu_nho_cau_goc(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        calls = []
        out = call_rescue(
            text=REFUSAL_TEXT,
            generate_fn=lambda p: calls.append(p) or REFUSAL_TEXT,
            question="Sinh viên có kết quả xếp loại rèn luyện Yếu có bị buộc thôi học không?",
            raw_query="Mức đóng bảo hiểm y tế của sinh viên là bao nhiêu?",
        )
        assert len(calls) == 1  # câu gốc đòi một giá trị cụ thể -> phải thử một lượt
        assert out == REFUSAL_TEXT  # và vẫn từ chối vì lượt cứu không cứu được gì

    def test_ca_goc_lan_chuan_hoa_khong_doi_gi_thi_khong_goi_model(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        calls = []
        out = call_rescue(
            text=REFUSAL_TEXT,
            generate_fn=lambda p: calls.append(p) or "x",
            question="Chúc mừng năm mới",
            raw_query="Chúc mừng năm mới",
        )
        assert calls == []
        assert out == REFUSAL_TEXT

    def test_hai_generator_cung_chu_ky_raw_query(self):
        """Giao diện Generator phải nhất quán: pipeline gọi một kiểu cho cả hai lớp."""
        import inspect

        from src.generator import GeminiGenerator

        for cls in (QwenGenerator, GeminiGenerator):
            params = inspect.signature(cls.generate_answer).parameters
            assert "raw_query" in params, f"{cls.__name__}.generate_answer thiếu raw_query"


class TestKhiTatKhongDoiHanhVi:
    def test_cot_tat_khong_goi_model_them_lan_nao(self, monkeypatch):
        monkeypatch.delenv("ENABLE_ANSWER_RESCUE", raising=False)
        calls = []
        out = call_rescue(text=REFUSAL_TEXT, generate_fn=lambda p: calls.append(p) or "x")
        assert out == REFUSAL_TEXT
        assert calls == []

    def test_khong_phi_cau_tra_loi_dung(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        dung = "Sinh viên đóng 546.480đ/12 tháng/SV (Điều 14 — 05-tb-ctsv-bhyt.pdf)."
        calls = []
        out = call_rescue(text=dung, generate_fn=lambda p: calls.append(p) or "x")
        assert out == dung
        assert calls == []  # không phải lời từ chối -> không cứu


class TestCuuDuoc:
    def test_loi_cuu_co_can_cu_duoc_nhan(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        rescued = "Mức đóng là 546.480đ/12 tháng/SV (Điều 14 — 05-tb-ctsv-bhyt.pdf)."
        seen = {}

        def gen(prompt: str) -> str:
            seen["prompt"] = prompt
            return rescued

        out = call_rescue(text=REFUSAL_TEXT, generate_fn=gen)
        assert out == rescued
        # lượt cứu phải là prompt cũ + chỉ dẫn trích xuất, không phải prompt khác
        assert seen["prompt"].startswith("PROMPT: ")
        assert "YÊU CẦU TRÍCH XUẤT" in seen["prompt"]

    def test_chi_mot_luot_goi_them(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        calls = []

        def gen(prompt: str) -> str:
            calls.append(prompt)
            return "Không có đoạn nào nói về mức đóng."

        call_rescue(text=REFUSAL_TEXT, generate_fn=gen)
        assert len(calls) == 1


class TestKhongDuocPheoBi:
    def test_loi_cuu_van_tu_choi_thi_gi_nguyen(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        out = call_rescue(text=REFUSAL_TEXT, generate_fn=lambda p: REFUSAL_TEXT)
        assert out == REFUSAL_TEXT

    def test_loi_cuu_giay_mu_hoa_thi_gi_nguyen_tu_choi(self, monkeypatch):
        """An toàn số một: câu "trả lời được" nhưng bịa thực thể phải bị trả lại.

        701.000đ không có trong ngữ cảnh -> `check_grounding` gọi là không căn cứ ->
        rescue trả về đúng lời từ chối ban đầu.
        """
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        fake = "Mức đóng bảo hiểm y tế là 701.000đ/12 tháng (Điều 99 — quyen-khong-co.pdf)."
        out = call_rescue(text=REFUSAL_TEXT, generate_fn=lambda p: fake)
        assert out == REFUSAL_TEXT

    def test_loi_cuu_chen_thuc_the_la_lenh_bi_chan(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        mixed = "Sinh viên đóng 546.480đ/12 tháng theo lớp DTA999999."
        out = call_rescue(text=REFUSAL_TEXT, generate_fn=lambda p: mixed)
        assert out == REFUSAL_TEXT

    def test_generate_fn_nem_lech_khong_lam_chet_luot_hoi(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")

        def boom(prompt: str) -> str:
            raise RuntimeError("ollama overloaded")

        assert call_rescue(text=REFUSAL_TEXT, generate_fn=boom) == REFUSAL_TEXT


class TestNghiPhepBoQua:
    def test_ngoai_pham_vi_khong_cuu(self, monkeypatch):
        """Câu ngoài phạm vi: từ chối là hành vi ĐÚNG, cứu sẽ phá lớp phòng vệ đó."""
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        calls = []
        out = call_rescue(
            text=REFUSAL_TEXT,
            generate_fn=lambda p: calls.append(p) or "546.480đ (Điều 14).",
            question_type="NGOAI_PHAM_VI",
        )
        assert out == REFUSAL_TEXT
        assert calls == []

    def test_khong_co_ngu_canh_thi_khong_cuu(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        calls = []
        out = call_rescue(
            text=REFUSAL_TEXT,
            generate_fn=lambda p: calls.append(p) or "x",
            docs=[{"content": "ngắn", "source": "a.pdf", "tier": "1", "chunk_id": 1}],
        )
        assert out == REFUSAL_TEXT
        assert calls == []

    def test_cau_hoi_khong_hoi_gia_tri_cu_the_khong_cuu(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        calls = []
        out = call_rescue(
            text=REFUSAL_TEXT,
            generate_fn=lambda p: calls.append(p) or "x",
            question="Em nên làm gì để cải thiện điểm rèn luyện",
        )
        assert out == REFUSAL_TEXT
        assert calls == []


class TestNgưỡngNhậnChặtHơnGuardrail:
    """r3 đổi 4 ca PASS_REFUSAL thành câu trả lời, trong đó 1 ca thành
    FAIL_HALLUCINATED_ON_UNANSWERABLE: giá trị model chép CÓ thật trong ngữ cảnh nhưng
    không phải giá trị được hỏi, nên ngưỡng 0,60 của guard (chỉ bắt thực thể thiếu căn
    cứ) vẫn cho qua. Luật mới: không còn thực thể chưa căn cứ VÀ điểm >=
    max(ngưỡng guard, RESCUE_MIN_SCORE=0,8) VÀ phải có điểm thật."""

    def test_ung_cu_con_thực_thể_thiếu_căn_cứ_bị_bỏ_dù_điểm_cao(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        monkeypatch.delenv("RESCUE_MIN_SCORE", raising=False)
        candidate = (
            "Sinh viên đóng 546.480đ/12 tháng (05-tb-ctsv-bhyt.pdf) theo Quyết Định Khẩn Cấp."
        )
        out = call_rescue(text=REFUSAL_TEXT, generate_fn=lambda p: candidate)
        assert out == REFUSAL_TEXT

    def test_ngưỡng_nhận_đọc_từ_env_và_dữ_dạng_không_làm_bật_lever(self, monkeypatch):
        monkeypatch.delenv("RESCUE_MIN_SCORE", raising=False)
        assert rescue_min_score() == 0.8
        monkeypatch.setenv("RESCUE_MIN_SCORE", "0.5")
        assert rescue_min_score() == 0.5  # co the nang/hat bang env, khong sua code
        monkeypatch.setenv("RESCUE_MIN_SCORE", "abc")
        assert rescue_min_score() == 0.8
        monkeypatch.setenv("RESCUE_MIN_SCORE", "5")
        assert rescue_min_score() == 1.0

    def test_lượt_thử_dù_thất_bại_vẫn_phải_đếm_được(self, monkeypatch, capsys):
        """r3 có 60/61 câu từ chối đủ điều kiện nhưng log chỉ 9 dòng -> không phân biệt
        được 'lever thua' với 'lever không chạy'. Mọi nhánh thất bại phải lại một dấu."""
        monkeypatch.setenv("ENABLE_ANSWER_RESCUE", "1")
        out = call_rescue(text=REFUSAL_TEXT, generate_fn=lambda p: "Tôi không tìm thấy thông tin.")
        assert out == REFUSAL_TEXT
        assert "Đã thử lượt trích xuất" in capsys.readouterr().out

    def test_mẫu_trong_chỉ_dẫn_là_số_bịa_không_thể_chép_nguyên_vào_bài_thi(self):
        """Bài học nhiễm mồi từ ca `V3` trong A/B: ví dụ few-shot lấy từ corpus THẬT đã
        chép đúng đáp án vàng của item `T24199159682252`, nên một phần thắng của `V3`
        là do mồi chứ không phải do chỉ dẫn.

        Số 3.456.000 và file `VD-quy-che-mau.pdf` không có trong test bank, do đó nếu
        model bắt chước mẫu thì `check_grounding` chắn chắc chặn (thực thể không căn cứ)
        — ví dụ tự kiểm soát, thay vì tự leak đáp án."""
        assert "3.456.000" in RESCUE_INSTRUCTION
        assert "VD-quy-che-mau.pdf" in RESCUE_INSTRUCTION
        testset = Path("data/loop/testset_v1.jsonl")
        if not testset.exists():  # bo test chua sinh (repo sạch) — khong co gi de leak
            return
        hay = testset.read_text(encoding="utf-8")
        assert "3.456.000" not in hay
        assert "VD-quy-che-mau.pdf" not in hay

