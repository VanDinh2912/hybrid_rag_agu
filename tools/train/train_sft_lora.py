"""SFT LoRA cho Qwen2.5-0.5B-Instruct bằng dataset `sft_train.jsonl`.

Script này dùng `venv_train`, không đụng `venv` của đồ án. Nó train trên GPU nếu
CUDA khả dụng, tự fallback về CPU. Mặc định chỉ chạy 1 epoch để kiểm chứng hạ tầng
trên RTX 3050 4GB; sau khi đạt có thể tăng epochs.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Iterable
from datetime import datetime

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


def load_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def conversation_to_row(row: dict, tokenizer, max_length: int) -> dict:
    messages = row["messages"]
    if not messages or messages[-1].get("role") != "assistant":
        return None

    prompt_text = tokenizer.apply_chat_template(
        messages[:-1], tokenize=False, add_generation_prompt=True
    )
    full_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)

    full = tokenizer(
        full_text,
        truncation=True,
        max_length=max_length,
        add_special_tokens=False,
    )
    prompt = tokenizer(
        prompt_text,
        truncation=True,
        max_length=max_length,
        add_special_tokens=False,
    )

    input_ids = full["input_ids"]
    labels = list(input_ids)
    prompt_len = min(len(prompt["input_ids"]), len(input_ids) - 1)
    for i in range(prompt_len):
        labels[i] = -100

    if not any(label != -100 for label in labels):
        return None

    return {
        "input_ids": input_ids,
        "attention_mask": full["attention_mask"],
        "labels": labels,
    }


def build_dataset(rows: Iterable[dict], tokenizer, max_length: int) -> Dataset:
    examples = []
    skipped = 0
    for row in rows:
        example = conversation_to_row(row, tokenizer, max_length)
        if example is None:
            skipped += 1
        else:
            examples.append(example)
    print(f"Tokenized examples: {len(examples)} · skipped: {skipped}")
    return Dataset.from_list(examples)


class PadCollator:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, features: list[dict]) -> dict[str, torch.Tensor]:
        max_len = max(len(f["input_ids"]) for f in features)

        def pad(seq: list[int], value: int) -> list[int]:
            return seq + [value] * (max_len - len(seq))

        batch = {
            "input_ids": torch.tensor(
                [pad(f["input_ids"], self.pad_token_id) for f in features], dtype=torch.long
            ),
            "attention_mask": torch.tensor(
                [pad(f["attention_mask"], 0) for f in features], dtype=torch.long
            ),
            "labels": torch.tensor(
                [pad(f["labels"], -100) for f in features], dtype=torch.long
            ),
        }
        return batch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số dòng để smoke test; 0 là toàn bộ.")
    parser.add_argument("--output-dir", default=os.path.join(BASE_DIR, "models", "qwen25_05b_sft_adapter"))
    args = parser.parse_args()

    train_path = os.path.join(BASE_DIR, "data", "training", "sft_train.jsonl")
    val_path = os.path.join(BASE_DIR, "data", "training", "sft_val.jsonl")
    train_rows = load_jsonl(train_path)
    val_rows = load_jsonl(val_path)
    if args.limit > 0:
        train_rows = train_rows[: args.limit]
        val_rows = val_rows[: max(1, args.limit // 4)]
    print(f"Train rows: {len(train_rows)} · Validation rows: {len(val_rows)}")

    cuda_available = torch.cuda.is_available()
    device_map = "cuda" if cuda_available else None
    torch_dtype = torch.bfloat16 if cuda_available else torch.float32
    if cuda_available:
        print(f"Using CUDA: {torch.cuda.get_device_name(0)}")
    else:
        print("CUDA unavailable; fallback CPU (chậm, chỉ dùng để smoke test)")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Preparing dataset (chat template + label masking)...")
    train_dataset = build_dataset(train_rows, tokenizer, args.max_length)
    val_dataset = build_dataset(val_rows, tokenizer, args.max_length)

    print(f"Loading {args.model} dtype={torch_dtype}...")
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        dtype=torch_dtype,
        device_map=device_map,
    )
    model.config.use_cache = False

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    use_bf16 = cuda_available and torch.cuda.is_bf16_supported()
    args_training = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_steps=5,
        weight_decay=0.01,
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch",
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        bf16=use_bf16,
        fp16=False,
        report_to=[],
        seed=42,
        dataloader_num_workers=0,
        gradient_checkpointing=cuda_available,
        gradient_checkpointing_kwargs={"use_reentrant": False} if cuda_available else None,
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=args_training,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=PadCollator(tokenizer.pad_token_id),
        processing_class=tokenizer,
    )

    print("Starting LoRA SFT...")
    t0 = time.time()
    result = trainer.train()
    elapsed = time.time() - t0

    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    metrics = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "cuda": cuda_available,
        "device": torch.cuda.get_device_name(0) if cuda_available else "cpu",
        "train_rows": len(train_dataset),
        "val_rows": len(val_dataset),
        "epochs": args.epochs,
        "max_length": args.max_length,
        "learning_rate": args.learning_rate,
        "elapsed_seconds": round(elapsed, 2),
        "train_loss": result.training_loss,
        "final_metrics": {
            k: float(v) if isinstance(v, (int, float)) else v
            for k, v in (result.metrics or {}).items()
        },
    }
    with open(os.path.join(args.output_dir, "training_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
