# -*- coding: utf-8 -*-
"""B5 (đêm 25-10) — probe VRAM của SFT khi chỉ tính logits trên TOKEN ĐÁP ÁN.

Đây là **probe chi phí**, không phải lượt train: một batch giả, đúng một bước forward+backward,
không dataset, không checkpoint, không trọng số nào được giữ lại (đề bài: "Không train").

Vì sao phép đo này đáng làm
--------------------------
T4b (`tools/diag/qlora_memory_probe.py`, 24-10) kết luận LoRA fp16 hết chỗ từ ~1.024 token
(≈3 MiB/token) và gradient checkpointing KHÔNG giúp. Nhưng con số 3 MiB/token đó gần như đúng
bằng kích thước logits: mỗi vị trí sinh ra một vector `vocab` (Qwen2.5 = 151.936) giữ lại cho
backward ⇒ 151.936 × 2 byte ≈ 297 KiB/vị trí, nhân lên vài lần cho graph. Nếu đúng như vậy thì
nút thắt KHÔNG phải "độ dài ngữ cảnh" mà là "tính lm_head ở mọi vị trí" — trong khi loss SFT chỉ
cần logits ở các vị trí dự đoán token đáp án (prompt đã bị `-100`).

Probe này đo trực tiếp hai chế độ trên CÙNG một batch:

* `full`    : `model(input_ids, labels)` — logits [1, L, V] (đường HF chuẩn, chính là what T4b đo);
* `answer_only`: thân transformer ra `hidden_state` [1, L, H], chỉ áp `lm_head` cho `n_ans` vị trí
  có nhãn ⇒ logits [n_ans, V], phần còn lại không bao giờ được materialise.

Kết luận có sức nặng nhất là HIỆU số peak giữa hai chế độ ở cùng L. Nếu `answer_only` vẫn OOM ở
1.024 token thì giả thuyết "logits là nút thắt" bị bác, và PA-11 (4-bit) / PA-12 (đổi định dạng
dữ liệu) vẫn là hai đường duy nhất.

Chạy bằng `venv_train`, SAU khi không còn round nào chiếm GPU:

    ./venv_train/Scripts/python.exe tools/diag/answer_token_logits_probe.py \
        --lengths 768,1024,1500 --answer-fraction 0.15 \
        --out data/loop/diag/answer_token_logits_probe.json

Mặc định `--answer-fraction 0.15` lấy theo phân bố thật đã đo: dòng SFT extractive có phần đáp án
ngắn hơn prompt rất nhiều (xem `docs/reports/T4.md`). Đổi tỷ lệ là đổi đối tượng đo, nên nó là
tham số tường minh chứ không phải hằng số ẩn.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from typing import Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
# Cùng bộ target với lượt train 0,5B đã deploy (models/train_sft_lora.py) để số so sánh được.
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj"]
SEED = 20261025


# ------------------------------------------------------------------ phần thuần, đo được không cần GPU
def vocab_logit_bytes_per_position(vocab_size: int, dtype_bytes: int = 2) -> int:
    """Bytes của MỘT dòng logits (một vị trí) — thước dự đoán trước khi bấm máy."""
    return vocab_size * dtype_bytes


def predicted_saving_bytes(length: int, n_answer: int, vocab_size: int, dtype_bytes: int = 2) -> int:
    """Chỗ tiết kiệm LÝ THUYẾT của chế độ answer_only so với full (phần logits thuần)."""
    return max(0, length - n_answer) * vocab_logit_bytes_per_position(vocab_size, dtype_bytes)


def answer_positions(length: int, answer_fraction: float) -> tuple[int, int]:
    """(prompt_len, n_answer) cho một batch giả: prompt chiếm phần còn lại.

    `answer_fraction` là tỷ lệ vị trí CÓ NHÃN (không phải -100). Tối thiểu 1 vị trí và tối đa
    `length - 1` — ca "dạy cả prompt" không tồn tại trong SFT và sẽ làm phép đo mất nghĩa.
    """
    if not (0.0 < answer_fraction <= 1.0):
        raise ValueError(f"answer_fraction phải trong (0; 1], nhận {answer_fraction!r}")
    n_answer = max(1, int(round(length * answer_fraction)))
    n_answer = min(n_answer, length - 1)
    return length - n_answer, n_answer


def build_batch(length: int, answer_fraction: float, vocab_size: int, seed: int = SEED):
    """input_ids [1,L] + labels [1,L] theo ĐÚNG qui ước HF: `labels[i] = input_ids[i]` ở các vị trí
    đáp án (n_slot CUỐI), `-100` ở prompt; HF tự dịch một trái khi tính loss.

    Tất định theo seed. Đây là cùng qui ước với `models/train_sft_lora.py` (mask prompt bằng -100),
    nên `loss_full` là đường cơ sở trung thực và `loss_answer_only` phải cho CÙNG một giá trị
    (test số trên model tiny khẳng định điều đó — tiết kiệm bộ nhớ mà không đổi hàm mất mát).
    """
    import torch

    g = torch.Generator(device="cpu").manual_seed(seed)
    input_ids = torch.randint(0, vocab_size, (1, length), generator=g, dtype=torch.long)
    prompt_len, n_answer = answer_positions(length, answer_fraction)
    labels = torch.full_like(input_ids, -100)
    labels[0, prompt_len:length] = input_ids[0, prompt_len:length]
    return {"input_ids": input_ids, "labels": labels, "prompt_len": prompt_len, "n_answer": n_answer}


# ------------------------------------------------------------------ hai chế độ tính loss
def loss_full(model: Any, batch: dict) -> Any:
    """Đường HF chuẩn: logits [1, L, V] được materialise cho MỌI vị trí."""
    import torch

    input_ids = batch["input_ids"]
    attention_mask = torch.ones_like(input_ids)
    return model(input_ids=input_ids, attention_mask=attention_mask,
                 labels=batch["labels"]).loss


def loss_answer_only(model: Any, batch: dict) -> Any:
    """Chỉ áp lm_head trên các vị trí có nhãn. Phần prompt không bao giờ sinh logits.

    `model` có thể là CausalLM gốc hoặc PeftModel; cả hai đều exposes `.model` (thân
    transformer) và `.lm_head`. Không dùng `model(..., logits_to_keep=)`: tham số đó chỉ giữ
    logits CUỐI CÙNG (cuối chuỗi), không giữ theo tập vị trí tùy ý.

    Đổi cả `hidden` lẫn `logits` từ hàng `[1, L, H]`/`[1, L, V]` xuống `[n_answer, H]`/
    `[n_answer, V]` — đúng số hàng mà `loss_full` (HF shift một trái) cần tới.
    """
    import torch
    import torch.nn.functional as F

    base = getattr(model, "get_base_model", None)
    core = base() if callable(base) else model
    body = core.model
    head = core.lm_head

    input_ids = batch["input_ids"]
    attention_mask = torch.ones_like(input_ids)
    hidden = body(input_ids=input_ids, attention_mask=attention_mask, use_cache=False).last_hidden_state

    labels = batch["labels"]
    keep = labels != -100                      # [1, L] — vị trí DỰ ĐOÁN
    h = hidden[:, :-1, :][keep[:, 1:]]         # dịch một bước: hidden tại i dự đoán token i+1
    target = labels[keep]
    logits = head(h)                           # [n_answer, V] — chỗ tiết kiệm nằm ở đây
    return F.cross_entropy(logits, target)


# ------------------------------------------------------------------ một điểm đo
def one_probe(model_id: str, length: int, answer_fraction: float, mode: str,
              grad_checkpointing: bool, local_files_only: bool = True) -> dict:
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM

    t0 = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        model_id, dtype=torch.float16, device_map="cuda",
        local_files_only=local_files_only,
    )
    model.config.use_cache = False
    if grad_checkpointing:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    peft_cfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32,
                          lora_dropout=0.05, target_modules=LORA_TARGETS)
    model = get_peft_model(model, peft_cfg)
    trainable = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(trainable, lr=1e-4)

    vocab = int(getattr(model.config, "vocab_size", 0) or 0)
    batch = build_batch(length, answer_fraction, vocab)
    input_ids = batch["input_ids"].to("cuda")
    labels = batch["labels"].to("cuda")
    batch_gpu = {"input_ids": input_ids, "labels": labels,
                 "prompt_len": batch["prompt_len"], "n_answer": batch["n_answer"]}

    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    base_alloc = torch.cuda.memory_allocated()
    opt.zero_grad()
    if mode == "full":
        loss = loss_full(model, batch_gpu)
    elif mode == "answer_only":
        loss = loss_answer_only(model, batch_gpu)
    else:
        raise ValueError(f"mode không biết: {mode!r}")
    loss.backward()
    opt.step()
    torch.cuda.synchronize()

    peak_alloc = torch.cuda.max_memory_allocated()
    row = {
        "model": model_id,
        "mode": mode,
        "length_tokens": length,
        "answer_tokens": batch_gpu["n_answer"],
        "prompt_tokens": batch_gpu["prompt_len"],
        "grad_checkpointing": grad_checkpointing,
        "vocab_size": vocab,
        "weights_plus_adapter_allocated_mib": round(base_alloc / 2**20, 1),
        "peak_allocated_mib": round(peak_alloc / 2**20, 1),
        "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 1),
        "loss_at_first_step": float(loss.item()),
        "logits_rows_full": length,
        "logits_rows_answer_only": batch_gpu["n_answer"],
        "predicted_logit_saving_mib": round(
            predicted_saving_bytes(length, batch_gpu["n_answer"], vocab) / 2**20, 1),
        "wall_seconds": round(time.perf_counter() - t0, 1),
        "gpu": torch.cuda.get_device_name(0),
        "gpu_total_mib": round(torch.cuda.get_device_properties(0).total_memory / 2**20, 1),
    }

    del model, opt, trainable, loss, batch, batch_gpu, input_ids, labels
    torch.cuda.empty_cache()
    return row


def probe_safe(model_id: str, length: int, answer_fraction: float, mode: str, gc: bool,
               offline: bool = True) -> dict:
    """Bắt OOM thành một dòng dữ liệu thay vì làm sập cả lượt đo."""
    import torch
    try:
        return one_probe(model_id, length, answer_fraction, mode, gc, local_files_only=offline)
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        return {"model": model_id, "mode": mode, "length_tokens": length,
                "answer_fraction": answer_fraction, "grad_checkpointing": gc, "oom": True,
                "peak_allocated_mib": None}
    except Exception as exc:  # noqa: BLE001
        torch.cuda.empty_cache()
        return {"model": model_id, "mode": mode, "length_tokens": length,
                "answer_fraction": answer_fraction, "grad_checkpointing": gc,
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "peak_allocated_mib": None}


# ------------------------------------------------------------------ kết luận
def compare(rows: list[dict]) -> list[dict]:
    """Hiệu số peak giữa hai chế độ, theo từng (length, grad_checkpointing) có đủ cả hai ca đo."""
    keyed = {(r["length_tokens"], bool(r.get("grad_checkpointing")), r["mode"]): r for r in rows}
    out = []
    for length, gc in sorted({(r["length_tokens"], bool(r.get("grad_checkpointing"))) for r in rows}):
        full = keyed.get((length, gc, "full"))
        ans = keyed.get((length, gc, "answer_only"))
        if not full or not ans:
            continue
        f, a = full.get("peak_allocated_mib"), ans.get("peak_allocated_mib")
        out.append({
            "length_tokens": length, "grad_checkpointing": gc,
            "peak_full_mib": f, "peak_answer_only_mib": a,
            "delta_mib": round(f - a, 1) if f is not None and a is not None else None,
            "oom_full": bool(full.get("oom")), "oom_answer_only": bool(ans.get("oom")),
            "answer_only_thoat_khi_full_OOM": bool(full.get("oom")) and not bool(ans.get("oom")),
        })
    return out


def ket_luan(rows: list[dict], deltas: list[dict], gpu_total_mib: Optional[float]) -> dict:
    """Kết luận theo SỐ, không theo kỳ vọng; kỳ vọng sai thì đính chính, không nắn số."""
    max_len_ok = {}
    for mode in ("full", "answer_only"):
        ok = [r["length_tokens"] for r in rows if r.get("mode") == mode and not r.get("oom")
              and r.get("peak_allocated_mib") is not None]
        max_len_ok[mode] = max(ok) if ok else 0
    best = max((d["delta_mib"] for d in deltas if d.get("delta_mib") is not None), default=None)
    giải_phóng = any(d["answer_only_thoat_khi_full_OOM"] for d in deltas)
    return {
        "max_length_full": max_len_ok["full"],
        "max_length_answer_only": max_len_ok["answer_only"],
        "delta_peak_lớn_nhất_mib": best,
        "answer_only_cứu_được_ca_OOM": giải_phóng,
        "verdict": (
            "LOGITS_LA_NUT_THAT: answer_only mở thêm trần độ dài" if giải_phóng else
            "CO_HIEU_LUC_NHUNG_KHONG_MOI_THÊM_TRẦN" if (best or 0) > 0 else
            "KHONG_DO_DUOC"
        ),
        "gpu_total_mib": gpu_total_mib,
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="B5: probe VRAM khi logits chỉ tính trên token đáp án.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--lengths", default="768,1024,1500")
    ap.add_argument("--answer-fraction", type=float, default=0.15,
                    help="tỷ lệ vị trí có nhãn (đáp án) — đổi nó là đổi đối tượng đo")
    ap.add_argument("--modes", default="full,answer_only")
    ap.add_argument("--grad-checkpointing", default="0", choices=["0", "1", "both"])
    ap.add_argument("--allow-download", action="store_true",
                    help="MẶC ĐỊNH KHÔNG tải từ mạng: weights phải có sẵn trên đĩa")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "data", "loop", "diag",
                                                  "answer_token_logits_probe.json"))
    args = ap.parse_args(argv)

    import torch

    if not torch.cuda.is_available():
        print(json.dumps({"error": "CUDA không khả dụng — probe VRAM vô nghĩa trên CPU"},
                         ensure_ascii=False))
        return 2

    gcs: list[bool]
    if args.grad_checkpointing == "both":
        gcs = [False, True]
    else:
        gcs = [args.grad_checkpointing == "1"]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]

    rows: list[dict] = []
    for length in lengths:
        for mode in modes:
            for gc in gcs:
                print(f"[probe] L={length} mode={mode} gc={gc} ...", flush=True)
                r = probe_safe(args.model, length, args.answer_fraction, mode, gc,
                               offline=not args.allow_download)
                rows.append(r)
                print("   " + json.dumps({k: r.get(k) for k in
                                         ("peak_allocated_mib", "peak_reserved_mib", "oom",
                                          "error", "wall_seconds")}, ensure_ascii=False), flush=True)

    deltas = compare(rows)
    gpu_total = next((r.get("gpu_total_mib") for r in rows if r.get("gpu_total_mib")), None)
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "probe chi phí (1 bước fwd/bwd giả), KHÔNG phải lượt train",
        "answer_fraction": args.answer_fraction,
        "rows": rows,
        "delta_theo_length": deltas,
        "ket_luan": ket_luan(rows, deltas, gpu_total),
        "baseline_t4b": {
            "nguồn": "data/loop/diag/t4b_memory_probe.json (24-10, đường `full`, gc both)",
            "peak_mib": {"768": 3339.8, "1768": 6437.9},
            "ước_ly_trên_mỗi_token": 3.0,
        },
        "reading_rule": "SO SÁNH peak_allocated_mib GIỮA hai mode ở cùng length; OOM của `full` "
                        "KHÔNG được tính là 'không train được' nếu `answer_only` vẫn chạy — "
                        "vì đó chính là giả thuyết đang được kiểm tra.",
    }
    text = json.dumps(out, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"[out] {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # D-36
    raise SystemExit(main())
