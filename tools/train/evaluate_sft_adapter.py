"""Smoke test sinh văn bản cho adapter SFT đã train.

Chạy bằng `venv_train`. Mặc định thử 4 câu và in so sánh adapter vs base model.
"""

from __future__ import annotations

import argparse
import json
import os

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ADAPTER = os.path.join(BASE_DIR, "models", "qwen25_05b_sft_adapter")
DEFAULT_BASE = "Qwen/Qwen2.5-0.5B-Instruct"


def load_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def generate(model, tokenizer, prompt_messages, max_new_tokens: int) -> str:
    text = tokenizer.apply_chat_template(
        prompt_messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
    generated = output[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter-dir", default=DEFAULT_ADAPTER)
    parser.add_argument("--base-model", default=DEFAULT_BASE)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--max-new-tokens", type=int, default=120)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    rows = load_rows(os.path.join(BASE_DIR, "data", "training", "sft_val.jsonl"))[: args.limit]
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Loading base model...")
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        dtype=torch.bfloat16,
        device_map="cuda" if torch.cuda.is_available() else None,
    )
    print("Loading adapter...")
    adapter = PeftModel.from_pretrained(base, args.adapter_dir)
    adapter.eval()

    results = []
    for idx, row in enumerate(rows, 1):
        messages = row["messages"]
        expected = messages[-1]["content"]
        prompt = messages[:-1]
        query = prompt[-1]["content"] if prompt and prompt[-1]["role"] == "user" else ""
        print(f"\n[{idx}] {query[:180]}")
        print("EXPECTED:", expected[:240].replace("\n", " "))
        actual = generate(adapter, tokenizer, prompt, args.max_new_tokens)
        print("ADAPTER :", actual[:240].replace("\n", " "))
        results.append({"index": idx, "query": query, "expected": expected, "actual": actual})

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
