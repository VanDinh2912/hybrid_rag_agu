# -*- coding: utf-8 -*-
"""T4b — đo BỘ NHỚ THẬT cho câu hỏi "có train được trên đúng model triển khai không".

Đây là **probe chi phí**, không phải lượt train: một batch giả, một bước forward+backward,
không dataset, không checkpoint, không cập nhật trọng số nào được giữ lại. Mục tiêu là trả lời
bằng số (đã kiểm chứng trên chính card 4 GB này) thay bằng ước lượng:

* dòng SFT thật dài ~1.400 token (đo bằng tokenizer ở `tools/train/build_sft_from_round.py`,
  median 1.439) trong khi trần `max_length` đã chốt cho GPU 4 GB là 768 — vậy cần bao nhiêu VRAM
  khi nâng trần lên 1.768?
* bật/tắt gradient checkpointing tiết kiệm được bao nhiêu?
* 3B (model triển khai ứng viên của T4a) có chất nổi ở fp16 không, hay bắt buộc 4-bit
  (`bitsandbytes` — hiện CHƯA cài trong `venv_train`)?

Chạy bằng `venv_train`, SAU khi không còn round nào chiếm GPU:

    ./venv_train/Scripts/python.exe tools/diag/qlora_memory_probe.py \
        --lengths 768,1768 --out data/loop/diag/t4b_memory_probe.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
# LoRA target cùng bộ với lượt 0,5B đã train (models/train_sft_lora.py) để số so sánh được.
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj"]


def one_probe(model_id: str, length: int, grad_checkpointing: bool, seed: int = 20261024) -> dict:
    """Một điểm đo: nạp model fp16 + LoRA, chạy đúng một bước fwd/bwd, ghi lại đỉnh VRAM."""
    torch.manual_seed(seed)
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=torch.float16, device_map="cuda", local_files_only=True
    )
    model.config.use_cache = False
    if grad_checkpointing:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    peft_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32, lora_dropout=0.05, target_modules=LORA_TARGETS
    )
    model = get_peft_model(model, peft_cfg)
    trainable = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(trainable, lr=1e-4)

    input_ids = torch.randint(
        0, max(tok.vocab_size, 1), (1, length), dtype=torch.long, device="cuda"
    )
    labels = input_ids.clone()

    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    base_alloc = torch.cuda.memory_allocated()
    opt.zero_grad()
    loss = model(input_ids=input_ids, labels=labels).loss
    loss.backward()
    opt.step()
    torch.cuda.synchronize()

    row = {
        "model": model_id,
        "length_tokens": length,
        "grad_checkpointing": grad_checkpointing,
        "weights_plus_adapter_allocated_mib": round(base_alloc / 2**20, 1),
        "trainable_params": sum(p.numel() for p in trainable),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1),
        "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 1),
        "loss_at_first_step": float(loss.item()),
        "wall_seconds": round(time.perf_counter() - t0, 1),
        "gpu": torch.cuda.get_device_name(0),
        "gpu_total_mib": round(torch.cuda.get_device_properties(0).total_memory / 2**20, 1),
    }

    del model, opt, trainable, loss, input_ids, labels
    torch.cuda.empty_cache()
    return row


def note_3b(model_id: str) -> dict:
    """3B fp16 có nạp nổi không? (trọng số chưa tải về máy ⇒ đây cũng là một con số)"""
    try:
        AutoModelForCausalLM.from_pretrained(model_id, local_files_only=True)
        return {"model": model_id, "cached_locally": True}
    except Exception as exc:  # noqa: BLE001
        return {
            "model": model_id,
            "cached_locally": False,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "consequence": "muốn đo/train 3B phải tải trọng số HF trước (~6,2 GB fp16) — chưa làm, cần duyệt",
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="T4b: probe VRAM cho SFT/QLoRA trên GPU 4 GB.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--lengths", default="768,1768,2048")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "data", "loop", "diag", "t4b_memory_probe.json"))
    ap.add_argument("--skip-3b-check", action="store_true")
    args = ap.parse_args()

    if not torch.cuda.is_available():
        print(json.dumps({"error": "CUDA không khả dụng — probe này vô nghĩa nếu chạy trên CPU"}))
        return 2

    rows = []
    for raw in args.lengths.split(","):
        length = int(raw)
        for gc in (False, True):
            try:
                rows.append(one_probe(args.model, length, gc))
            except torch.cuda.OutOfMemoryError:
                rows.append({"model": args.model, "length_tokens": length, "grad_checkpointing": gc,
                             "oom": True})
                torch.cuda.empty_cache()
            except Exception as exc:  # noqa: BLE001
                rows.append({"model": args.model, "length_tokens": length, "grad_checkpointing": gc,
                             "error": f"{type(exc).__name__}: {str(exc)[:200]}"})

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "probe chi phí (1 bước fwd/bwd giả), KHÔNG phải lượt train",
        "bitsandbytes_installed": __import__("importlib.util", fromlist=["x"]).find_spec("bitsandbytes") is not None,
        "rows": rows,
        "deployment_check_3b": None if args.skip_3b_check else note_3b("Qwen/Qwen2.5-3B-Instruct"),
        "reading_rule": "so peak_allocated_mib với gpu_total_mib; số cho 3B là NGOẠI SUY từ tỉ trọng số, "
        "chưa kiểm chứng bằng lượt nạp 3B thật (trọng số chưa có trên máy)",
    }
    text = json.dumps(out, ensure_ascii=False, indent=2)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
