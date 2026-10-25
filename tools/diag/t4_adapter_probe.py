# -*- coding: utf-8 -*-
"""T4a (mục 9) — chứng minh adapter LoRA THẬT SỰ được áp, và nạp hỏng thì LỖI RÕ.

Vì sao có file này: `models/qwen25_05b_sft_adapter` là một thư mục trọng số; nếu nó không
khớp base model, hoặc `PeftModel.from_pretrained` bị bọc trong try/except trả về model gốc,
thì mọi tuyên bố "đã SFT" đều là niềm tin chứ không phải sự thật. Script này đo hai điều,
bằng đúng một prompt, greedy (không lấy mẫu) để sai khác chỉ có thể đến từ trọng số adapter:

1. **Adapter được áp**: đầu ra của `base + adapter` KHÁC đầu ra của `base` trên ≥1 mẫu.
2. **Nạp hỏng không âm thầm lùi về base**: trỏ `PeftModel.from_pretrained` vào một thư mục
   rỗng phải NÉM LỖI; script ghi lại loại lỗi + thông điệp và trả mã khác 0 nếu không ném.

Không train, không sửa trọng số, không ghi gì ngoài file JSON đầu ra.

Chạy bằng môi trường CÓ torch/peft (app `venv/` không cài torch):

    PYTHONIOENCODING=utf-8 ./venv_train/Scripts/python.exe tools/diag/t4_adapter_probe.py \
        --out data/loop/diag/t4_adapter_probe.json
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ADAPTER = ROOT / "models" / "qwen25_05b_sft_adapter"

PROMPT = (
    "Bạn là trợ lý học vụ của Trường Đại học An Giang. Chỉ trả lời dựa trên ngữ cảnh.\n\n"
    "Ngữ cảnh:\nquy-che-dao-tao.pdf: Điều 12. Sinh viên được học lại tối đa 8 lần đối với "
    "mỗi học phần và phải đóng học phí cho lần học lại đó.\n\n"
    "Câu hỏi: Sinh viên được học lại tối đa bao nhiêu lần một học phần?\n\nTrả lời:"
)


def _generate(model, tokenizer, prompt: str, device: str, max_new_tokens: int) -> str:
    import torch

    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,          # greedy: sai khác không thể do ngẫu nhiên
            temperature=None,
            top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = out[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def run(adapter_dir: Path, max_new_tokens: int) -> dict:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    config = json.loads((adapter_dir / "adapter_config.json").read_text(encoding="utf-8"))
    base_name = config["base_model_name_or_path"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

    tokenizer = AutoTokenizer.from_pretrained(adapter_dir, local_files_only=True)
    started = time.time()
    base = AutoModelForCausalLM.from_pretrained(
        base_name, local_files_only=True, torch_dtype=dtype,
    ).to(device)
    base.eval()
    load_base_s = round(time.time() - started, 2)

    started = time.time()
    base_text = _generate(base, tokenizer, PROMPT, device, max_new_tokens)
    gen_base_s = round(time.time() - started, 2)
    vram_base = torch.cuda.max_memory_allocated() if device == "cuda" else 0

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    started = time.time()
    # KHÔNG bọc try/except: nạp hỏng phải nổi lên thành lỗi, không lùi về base.
    model = PeftModel.from_pretrained(base, str(adapter_dir))
    model.eval()
    load_adapter_s = round(time.time() - started, 2)

    started = time.time()
    adapter_text = _generate(model, tokenizer, PROMPT, device, max_new_tokens)
    gen_adapter_s = round(time.time() - started, 2)
    vram_adapter = torch.cuda.max_memory_allocated() if device == "cuda" else 0

    report = {
        "adapter_dir": str(adapter_dir),
        "base_model": base_name,
        "device": device,
        "dtype": str(dtype),
        "greedy": True,
        "max_new_tokens": max_new_tokens,
        "base_text": base_text,
        "adapter_text": adapter_text,
        "outputs_differ": base_text != adapter_text,
        "vram_peak_base_mib": round(vram_base / 2**20, 1),
        "vram_peak_adapter_mib": round(vram_adapter / 2**20, 1),
        "seconds": {"load_base": load_base_s, "gen_base": gen_base_s,
                    "load_adapter": load_adapter_s, "gen_adapter": gen_adapter_s},
    }

    # --- nạp hỏng phải lỗi rõ -------------------------------------------------
    with tempfile.TemporaryDirectory() as empty_dir:
        try:
            PeftModel.from_pretrained(base, empty_dir)
        except Exception as exc:  # noqa: BLE001 — đang ĐO hành vi lỗi, không xử lý
            report["failure_probe"] = {
                "raised": True,
                "type": type(exc).__name__,
                "message": str(exc)[:400],
                "note": "không có nhánh fallback nào được chạy; lỗi nổi lên nguyên vẹn",
            }
        else:
            report["failure_probe"] = {
                "raised": False,
                "note": "NGUY HIỂM: nạp adapter hỏng mà không ném lỗi ⇒ có thể đang âm thầm dùng base",
            }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="T4a: kiểm adapter LoRA được áp + nạp hỏng báo lỗi.")
    parser.add_argument("--adapter-dir", default=str(DEFAULT_ADAPTER))
    parser.add_argument("--max-new-tokens", type=int, default=48)
    parser.add_argument("--out", default="", help="file JSON; rỗng = chỉ in ra stdout")
    args = parser.parse_args()

    report = run(Path(args.adapter_dir), args.max_new_tokens)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[T4a] ghi: {out}")

    ok = report["outputs_differ"] and report["failure_probe"]["raised"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
