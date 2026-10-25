"""Test cho `tools/diag/answer_token_logits_probe.py` (B5) — chạy trên CPU, model tiny tự sinh.

Test quan trọng nhất là `loss_answer_only == loss_full`: phép đo chỉ có nghĩa nếu chế độ tiết kiệm
bộ nhớ tính ĐÚNG CÙNG hàm mất mát với đường HF chuẩn. Nếu nó tính khác (sai chiều dịch nhãn, thiếu
một vị trí, hay quên mất hàng cuối) thì mọi con số VRAM trong báo cáo B5 là rác. Vì vậy ngoài so
sánh giá trị loss, test còn so gradient của `lm_head.weight` và hình dạng tensor đi vào `lm_head`.
"""

import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from tools.diag import answer_token_logits_probe as bp


def tiny_model(vocab_size: int = 53, hidden_size: int = 16):
    from transformers import LlamaConfig, LlamaForCausalLM

    cfg = LlamaConfig(
        vocab_size=vocab_size, hidden_size=hidden_size, intermediate_size=32,
        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2,
        max_position_embeddings=256, tie_word_embeddings=False,
    )
    torch.manual_seed(0)
    model = LlamaForCausalLM(cfg).to(torch.float32).eval()
    model.config.use_cache = False
    return model, vocab_size


# ------------------------------------------------------------------ chia prompt/đáp án
class TestAnswerPositions:
    @pytest.mark.parametrize("length,fraction,expected", [
        (768, 0.15, 115),   # round(115.2)
        (1024, 0.15, 154),
        (1500, 0.15, 225),
        (10, 1.0, 9),       # bị chặn ở length-1: không có ca "dạy cả prompt"
        (10, 0.01, 1),      # tối thiểu 1 vị trí
    ])
    def test_số_vị_trí_đáp_án(self, length, fraction, expected):
        prompt_len, n_answer = bp.answer_positions(length, fraction)
        assert n_answer == expected
        assert prompt_len + n_answer == length

    @pytest.mark.parametrize("bad", [0.0, -0.5, 1.5])
    def test_fraction_hợp_lệ_thì_ném_lỗi_thay_vì_lặng_lẽ_đo_sai(self, bad):
        with pytest.raises(ValueError):
            bp.answer_positions(100, bad)

    def test_ước_lượng_bytes_theo_vocab_không_phụ_thuộc_chiều_dài_đáp_án(self):
        assert bp.vocab_logit_bytes_per_position(151936) == 151936 * 2
        assert bp.predicted_saving_bytes(1500, 225, 151936) == (1500 - 225) * 151936 * 2


class TestBuildBatch:
    def test_đúng_n_slot_cuối_mang_nhãn_theo_qui_ước_HF(self):
        b = bp.build_batch(20, 0.25, 53)
        labels, ids = b["labels"], b["input_ids"]
        assert labels.shape == ids.shape == (1, 20)
        n = b["n_answer"]
        assert int((labels != -100).sum()) == n
        # qui ước HF: labels[i] = input_ids[i] ở slot đáp án (HF tự dịch khi tính loss)
        assert torch.equal(labels[0, -n:], ids[0, -n:])
        assert int((labels[0, :-n] != -100).sum()) == 0

    def test_tất_định_theo_seed(self):
        first = bp.build_batch(64, 0.2, 53)
        second = bp.build_batch(64, 0.2, 53)
        assert torch.equal(first["input_ids"], second["input_ids"])
        assert torch.equal(first["labels"], second["labels"])

    def test_thay_seed_thì_dữ_liệu_khác_nhưng_cấu_trúc_giữ_nguyên(self):
        a = bp.build_batch(64, 0.2, 53, seed=1)
        b = bp.build_batch(64, 0.2, 53, seed=2)
        assert not torch.equal(a["input_ids"], b["input_ids"])
        assert (a["prompt_len"], a["n_answer"]) == (b["prompt_len"], b["n_answer"])


# ------------------------------------------------------------------ BẤT BIẾN SỐ MỘT (CPU)
class TestLossEquality:
    def test_loss_answer_only_bằng_loss_full(self):
        model, vocab = tiny_model()
        batch = bp.build_batch(24, 0.25, vocab)
        full = bp.loss_full(model, batch).item()
        sparse = bp.loss_answer_only(model, batch).item()
        assert full == pytest.approx(sparse, abs=1e-5)

    def test_mất_mát_không_đổi_khi_dịch_tập_trung_đáp_án(self):
        """Cà vào chỗ dịch nhãn: nếu `answer_only` lấy sai hàng (lệch 1 vị trí) loss sẽ đổi."""
        model, vocab = tiny_model()
        for fraction in (0.05, 0.15, 0.5, 0.9):
            batch = bp.build_batch(30, fraction, vocab)
            assert bp.loss_answer_only(model, batch).item() == pytest.approx(
                bp.loss_full(model, batch).item(), abs=1e-5), f"fraction={fraction}"

    def test_gradient_của_lm_head_weight_nhau_hai_chế_độ(self):
        """Loss bằng nhau chưa chắc graph bằng nhau; gradient là bằng chứng mạnh hơn."""
        model, vocab = tiny_model()
        batch = bp.build_batch(20, 0.3, vocab)
        grads = {}
        for mode, fn in (("full", bp.loss_full), ("answer_only", bp.loss_answer_only)):
            model.zero_grad(set_to_none=True)
            fn(model, batch).backward()
            grads[mode] = model.lm_head.weight.grad.detach().clone()
        assert torch.allclose(grads["full"], grads["answer_only"], atol=1e-5)

    def test_answer_only_chỉ_đưa_n_answer_hàng_vào_lm_head(self):
        """Nếu mã vẫn âm thầm đưa đủ L hàng thì 'tiết kiệm' là giả — test này chặn đứng.

        Spy được gắn ngay tại `model.lm_head`, nên cả hai đường (kể cả `loss_full` đi qua
        forward nội bộ của HF) đều bị ghi hình: full phải thấy [1, L, H], answer_only phải
        thấy đúng [n_answer, H].
        """
        model, vocab = tiny_model()
        batch = bp.build_batch(20, 0.3, vocab)
        seen = []
        real_head = model.lm_head

        class Spy(torch.nn.Module):
            def __init__(self, inner):
                super().__init__()
                self.inner = inner

            def forward(self, x):
                seen.append(tuple(x.shape))
                return self.inner(x)

        model.lm_head = Spy(real_head)
        try:
            bp.loss_answer_only(model, batch)
            shapes_sparse = list(seen)
            seen.clear()
            bp.loss_full(model, batch)
            shapes_full = list(seen)
        finally:
            model.lm_head = real_head
        assert shapes_sparse == [(batch["n_answer"], 16)]
        assert shapes_full and shapes_full[0] == (1, 20, 16)
        assert shapes_full[0][1] > shapes_sparse[0][0]  # full vật hoá nhiều hàng hơn hẳn

    def test_không_dùng_logits_to_keep_thay_cho_answer_only(self):
        """`logits_to_keep` chỉ giữ hàng CUỐI cùng của chuỗi; tập đáp án nằm giữa thì nó bất lực.

        Test chốt bằng HÌNH DẠNG logits trả về, vì đó là lý do `loss_answer_only` phải tự slicing
        `hidden` thay vì đi đường tắt của HF.
        """
        model, vocab = tiny_model()
        batch = bp.build_batch(20, 0.3, vocab)  # n_answer = 6, nhưng đáp án KHÔNG nằm ở vị trí 0
        out = model(input_ids=batch["input_ids"], logits_to_keep=2)
        assert out.logits.shape[1] == 2 < batch["n_answer"]


# ------------------------------------------------------------------ bảng kết luận
def _row(mode, length, peak=None, oom=False, gc=False):
    return {"mode": mode, "length_tokens": length, "grad_checkpointing": gc,
            "peak_allocated_mib": peak, "oom": oom}


class TestCompareKetLuan:
    def test_delta_tính_trên_cùng_length_và_cùng_gc(self):
        rows = [_row("full", 1024, 3300.0), _row("answer_only", 1024, 1200.0)]
        d = bp.compare(rows)
        assert len(d) == 1
        assert d[0]["delta_mib"] == 2100.0
        assert d[0]["answer_only_thoat_khi_full_OOM"] is False

    def test_không_ghép_chéo_grad_checkpointing(self):
        rows = [_row("full", 1024, 3300.0, gc=False),
                _row("answer_only", 1024, 1200.0, gc=True)]
        assert bp.compare(rows) == []

    def test_oom_đủ_đôi_nên_vẫn_ghép_được_delta_None(self):
        rows = [_row("full", 1500, oom=True), _row("answer_only", 1500, 2100.0)]
        d = bp.compare(rows)
        assert d[0]["delta_mib"] is None
        assert d[0]["answer_only_thoat_khi_full_OOM"] is True

    def test_verdict_logits_la_nut_that_khi_answer_only_cứu_ca_oom(self):
        rows = [_row("full", 1024, oom=True), _row("answer_only", 1024, 2000.0)]
        kl = bp.ket_luan(rows, bp.compare(rows), 4095.5)
        assert kl["verdict"].startswith("LOGITS_LA_NUT_THAT")
        assert kl["max_length_full"] == 0 and kl["max_length_answer_only"] == 1024

    def test_verdict_không_mở_trần_khi_cả_hai_đều_chạy_nhưng_hiệu_số_dương(self):
        rows = [_row("full", 768, 3300.0), _row("answer_only", 768, 3000.0)]
        kl = bp.ket_luan(rows, bp.compare(rows), 4095.5)
        assert kl["verdict"] == "CO_HIEU_LUC_NHUNG_KHONG_MOI_THÊM_TRẦN"
        assert kl["delta_peak_lớn_nhất_mib"] == 300.0

    def test_không_có_dữ_liệu_thì_thẳng_thắn_KHONG_DO_DUOC(self):
        """Chế độ "không đo được" phải có chữ, không được trả verdict đẹp."""
        kl = bp.ket_luan([], [], None)
        assert kl["verdict"] == "KHONG_DO_DUOC"

    def test_max_length_lấy_cao_nhất_trong_cac_ca_thành(self):
        rows = [_row("full", 768, 3300.0), _row("full", 1024, oom=True), _row("full", 1500, oom=True),
                _row("answer_only", 1500, 2100.0), _row("answer_only", 1024, 1800.0)]
        kl = bp.ket_luan(rows, bp.compare(rows), 4095.5)
        assert kl["max_length_full"] == 768
        assert kl["max_length_answer_only"] == 1500


# ------------------------------------------------------------------ CLI
class TestMain:
    def test_không_có_cuda_thì_dừng_với_rc_2(self, monkeypatch, tmp_path):
        def no_cuda():
            return False

        monkeypatch.setattr(torch.cuda, "is_available", no_cuda)
        out = tmp_path / "probe.json"
        rc = bp.main(["--lengths", "768", "--out", str(out)])
        assert rc == 2
        assert not out.exists()

    def test_mặc_định_là_ba_mức_độ_dài_của_đề_bài(self, monkeypatch, tmp_path):
        """768/1024/1500 là chữ trong đề bài B5; để nó trôi đi thì phép đo không còn trả lời câu hỏi."""
        seen_lengths, seen_modes = [], []
        monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

        def fake_probe(model_id, length, fraction, mode, gc, offline=True):
            seen_lengths.append(length)
            seen_modes.append(mode)
            return _row(mode, length, 1000.0, gc=gc)

        monkeypatch.setattr(bp, "probe_safe", fake_probe)
        rc = bp.main(["--out", str(tmp_path / "probe.json")])
        assert rc == 0
        assert sorted(set(seen_lengths)) == [768, 1024, 1500]
        assert sorted(set(seen_modes)) == ["answer_only", "full"]

    def test_one_probe_được_gọi_đúng_b_ma_trận_length_x_mode_x_gc(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

        def fake_probe(model_id, length, fraction, mode, gc, offline=True):
            calls.append((length, mode, gc))
            return _row(mode, length, 1000.0, gc=gc)

        monkeypatch.setattr(bp, "probe_safe", fake_probe)
        out = tmp_path / "probe.json"
        rc = bp.main(["--lengths", "768,1024", "--modes", "full,answer_only",
                      "--grad-checkpointing", "both", "--out", str(out)])
        assert rc == 0
        assert len(calls) == 2 * 2 * 2
        result = json.loads(out.read_text(encoding="utf-8"))
        assert len(result["rows"]) == 8
        assert result["kind"].startswith("probe chi phí")

    def test_báo_cáo_không_ghi_đè_artifact_t4b_đã_công_bố(self):
        """B5 là phép đo MỚI; artifact 24-10 (`t4b_memory_probe.json`) phải còn nguyên."""
        src = Path(bp.__file__).read_text(encoding="utf-8")
        assert "answer_token_logits_probe.json" in src      # đích ghi của B5
        assert "t4b_memory_probe.json" in src               # chỉ là nguồn THAM CHIẾU trong báo cáo
        assert not src.count('os.path.join(BASE_DIR, "data", "loop", "diag", "t4b')  # không ghi vào đó
