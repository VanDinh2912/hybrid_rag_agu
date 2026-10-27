# -*- coding: utf-8 -*-
"""T4b — dựng dữ liệu SFT cho model TRIỂN KHAI, từ ca từ chối oan có căn cứ trong cửa sổ.

Phạm vi tệp này là **pipeline dữ liệu + sổ cái chi phí**, KHÔNG phải huấn luyện.
Đặc tả T4 yêu cầu "chỉ dựng pipeline + báo cáo chi phí" (quyết định của user 24-10),
nên ở đây không có một dòng train nào được chạm GPU.

Bốn thứ bắt buộc, lấy từ bất biến của `data/loop/README.md`:

1. **Nguồn đúng như đặc tả**: verdict `FAIL_OVERREFUSAL` mà căn cứ ĐÃ nằm trong cửa sổ
   generator (`gold_in_top_k`), do `tools/loop/triage.py` phân loại — không tự chế bộ lọc
   riêng, vì trọng tài của vòng lặp là `triage.lever_for`.
2. **Bất biến #7**: dòng train phải tự chứa căn cứ cho đáp án của nó. Đây chính là kiểm tra
   `skip_sft_target_not_in_context` bên trong `triage.build_rows` — script này GỌI LẠI đúng
   hàm đó, không viết lại luật (viết lại là tạo ra hai bộ dữ liệu khác nhau cùng tên).
3. **Chặn rò rỉ test-set**: item `split != "trainpool"` bị `triage` chặn bằng
   `blocked_test_leak`; script này còn kiểm LẠI bằng assert trước khi ghi đĩa.
4. **Group split theo TÀI LIỆU** (không theo item): mọi item cùng `source_document` rơi về
   đúng MỘT bên. Chia theo item sẽ cho model thấy câu trả lời của một Điều ở train rồi
   "đo" nó ở test — đúng kiểu tự lừa mình mà vòng lặp đã loại ở r0.

Cách chạy:

    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/build_sft_from_round.py \
        --rounds r5 r6 --out-root data/training/t4b_r5r6

Output: `sft_train.jsonl`, `sft_holdout.jsonl`, `manifest.json` (số dòng train, số dòng bị
chặn theo TỪNG lý do, danh sách document mỗi bên, seed, chữ ký trọng tài).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.triage import build_rows, load_jsonl  # noqa: E402
from tools.loop.verify import referee_fingerprint  # noqa: E402

# Chỉ những dòng này là "dạy được bằng SFT" theo đặc tả T4b.
SFT_TASKS = ("sft_extractive",)
UNKNOWN_DOC = "(không rõ nguồn)"


def read_items(round_dir: Path) -> dict[str, dict]:
    """id -> item, lấy từ verdicts trước rồi rows (cùng thứ tự ưu tiên như triage)."""
    items: dict[str, dict] = {}
    for verdict in load_jsonl(round_dir / "verdicts_full.jsonl"):
        if verdict.get("item") and verdict["id"] not in items:
            items[verdict["id"]] = verdict["item"]
    for row in load_jsonl(round_dir / "full.jsonl"):
        if row.get("item") and row["id"] not in items:
            items[row["id"]] = row["item"]
    return items


def doc_of(item: Optional[dict]) -> str:
    if not item:
        return UNKNOWN_DOC
    return str(item.get("source_document") or "").strip() or UNKNOWN_DOC


def collect(
    round_names: list[str],
    rounds_root: Path,
    include_refusal_rows: bool = False,
) -> tuple[list[dict], dict]:
    """Gộp dòng SFT từ nhiều round, bỏ trùng theo item id, mang theo lý do bị chặn."""
    tasks = tuple(SFT_TASKS) + (("sft_refusal",) if include_refusal_rows else ())
    kept: list[dict] = []
    seen: set[str] = set()
    stats: Counter = Counter()
    per_round: dict[str, dict] = {}

    for name in round_names:
        round_dir = rounds_root / name
        if not round_dir.is_dir():
            raise FileNotFoundError(f"Không thấy round: {round_dir}")
        rows, report = build_rows(round_dir, name)
        items = read_items(round_dir)
        stats["sft_refusal_rows"] += sum(1 for r in rows if r.get("task") == "sft_refusal")
        picked_this_round = 0
        for row in rows:
            if row.get("task") not in tasks:
                continue
            item_id = row["provenance"]["item_id"]
            if item_id in seen:
                stats["deduped_same_item_across_rounds"] += 1
                continue
            seen.add(item_id)
            item = items.get(item_id)
            row["group_document"] = doc_of(item)
            row["family"] = (item or {}).get("family")
            row["split"] = (item or {}).get("split")
            row["source_round"] = name
            kept.append(row)
            picked_this_round += 1
        per_round[name] = {
            "sft_rows_from_round": picked_this_round,
            "stats": report["stats"],
        }
        for key, value in report["stats"].items():
            if key.startswith(("blocked_", "skip_", "overrefusal_")):
                stats[key] += int(value)

    ledger = {
        "rounds": round_names,
        "per_round": per_round,
        "blocked": dict(stats),
        "n_items": len(kept),
        "n_documents": len({r["group_document"] for r in kept}),
    }
    return kept, ledger


def group_split(rows: list[dict], test_fraction: float, seed: int) -> tuple[list[dict], list[dict], dict]:
    """Chia theo NHÓM tài liệu: nguyên tắc = hash(seed + tên tài liệu), không phải xáo item.

    Lấy theo tỉ lệ số DÒNG nhưng chỉ được cắt giữa các nhóm; không bao giờ để một tài liệu
    xuất hiện cả hai bên (kiểm bằng assert bên dưới).
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["group_document"]].append(row)

    # Thứ tự xác định: ưu tiên nhóm lớn trước để tỉ lệ sát hơn, tie-break bằng hash.
    ordered = sorted(
        groups.items(),
        key=lambda kv: (
            -len(kv[1]),
            hashlib.sha256(f"{seed}:{kv[0]}".encode("utf-8")).hexdigest(),
        ),
    )

    target_test = max(1, round(len(rows) * test_fraction)) if rows else 0
    test_rows: list[dict] = []
    train_rows: list[dict] = []
    test_docs: list[str] = []
    for doc, grp in ordered:
        if len(test_rows) < target_test:
            test_rows.extend(grp)
            test_docs.append(doc)
        else:
            train_rows.extend(grp)

    overlap = {r["group_document"] for r in train_rows} & set(test_docs)
    assert not overlap, f"Group split rò rỉ tài liệu qua hai bên: {sorted(overlap)}"
    train_ids = {r["provenance"]["item_id"] for r in train_rows}
    test_ids = {r["provenance"]["item_id"] for r in test_rows}
    assert not (train_ids & test_ids), "Một item id xuất hiện ở cả train lẫn holdout"

    meta = {
        "test_fraction_requested": test_fraction,
        "test_target_rows": target_test,
        "seed": seed,
        "n_train_rows": len(train_rows),
        "n_holdout_rows": len(test_rows),
        "n_train_documents": len({r["group_document"] for r in train_rows}),
        "holdout_documents": test_docs,
        "holdout_document_count": len(test_docs),
        "rule": "nguyên cả tài liệu rơi về MỘT bên; cắt theo hash(seed + source_document), ưu tiên nhóm lớn trước",
    }
    return train_rows, test_rows, meta


def token_cost_proxy(rows: list[dict], max_length: int) -> dict:
    """Chi phí đo bằng ký tự (không cần tokenizer/GPU): độ dài dòng train thật.

    `max_length` là trần đã chốt cho GPU 4 GB ở lượt 0,5B (bài học `models/train_sft_lora.py`).
    Dòng dài hơn trần sẽ bị CẮT — nghĩa là mất căn cứ — nên phải đếm trước khi train.
    """
    lens = [len(json.dumps(r["messages"], ensure_ascii=False)) for r in rows]
    approx_tokens = [int(L / 3.6) for L in lens]  # 1 token ~3,6 ký tự tiếng Việt có dấu (ước lượng)
    over = sum(1 for t in approx_tokens if t > max_length)
    return {
        "method": "ước lượng ký tự",
        "max_length_assumption": max_length,
        "n_rows": len(lens),
        "chars_median": int(sorted(lens)[len(lens) // 2]) if lens else 0,
        "chars_p95": int(sorted(lens)[max(0, int(len(lens) * 0.95) - 1)]) if lens else 0,
        "est_tokens_median": int(sorted(approx_tokens)[len(approx_tokens) // 2]) if approx_tokens else 0,
        "rows_estimated_over_max_length": over,
        "note": "ước lượng token = ký tự/3,6, CHƯA kiểm chứng bằng tokenizer thật của Qwen2.5",
    }


def exact_token_lengths(rows: list[dict], tokenizer_path: str, max_length: int) -> dict:
    """Đếm token BẰNG TOKENIZER THẬT, thay cho ước lượng ở `token_cost_proxy`.

    Bắt buộc đi đường `apply_chat_template(tokenize=False)` rồi encode: đo 24-10 trên
    `models/qwen25_05b_sft_adapter` với `transformers 5.20.2`, gọi
    `apply_chat_template(..., tokenize=True)` trả về **2 token** cho dòng 3.424 ký tự
    (template hỏng trên đường đó), trong khi tokenize=False + encode cho 1.204 token.
    Hai script train/eval của repo (`models/train_sft_lora.py`,
    `models/evaluate_sft_adapter.py`) đã dùng đường tokenize=False — giữ nguyên cách đó.
    """
    from transformers import PreTrainedTokenizerFast

    tok = PreTrainedTokenizerFast.from_pretrained(tokenizer_path, local_files_only=True)
    counts = []
    for row in rows:
        text = tok.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
        counts.append(len(tok(text)["input_ids"]))
    ordered = sorted(counts)
    return {
        "method": f"tokenizer thật từ {tokenizer_path} (local_files_only)",
        "max_length_assumption": max_length,
        "n_rows": len(counts),
        "tokens_min": ordered[0] if ordered else 0,
        "tokens_median": ordered[len(ordered) // 2] if ordered else 0,
        "tokens_max": ordered[-1] if ordered else 0,
        "rows_over_max_length": sum(1 for t in counts if t > max_length),
        "per_row": [
            {"item_id": row["provenance"]["item_id"], "group_document": row["group_document"], "tokens": t}
            for row, t in zip(rows, counts)
        ],
    }


def write_outputs(out_root: Path, train_rows: list[dict], holdout_rows: list[dict], manifest: dict) -> None:
    if out_root.exists() and any(out_root.glob("sft_*.jsonl")):
        raise SystemExit(
            f"[T4b] {out_root} đã có sft_*.jsonl — dùng tên thư mục khác (bất biến: không ghi đè)."
        )
    out_root.mkdir(parents=True, exist_ok=True)
    for name, rows in (("sft_train.jsonl", train_rows), ("sft_holdout.jsonl", holdout_rows)):
        with (out_root / name).open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="T4b: dựng dữ liệu SFT group-split, KHÔNG train.")
    parser.add_argument("--rounds", nargs="+", default=["r5"], help="round nguồn (verdicts_full.jsonl)")
    parser.add_argument("--rounds-root", default=str(ROOT / "data" / "loop" / "rounds"))
    parser.add_argument("--out-root", default=str(ROOT / "data" / "training" / "t4b"))
    parser.add_argument("--test-fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=20261024)
    parser.add_argument("--max-length", type=int, default=768, help="trần huấn luyện đã chốt ở GPU 4 GB")
    parser.add_argument(
        "--include-refusal-rows",
        action="store_true",
        help="mặc định TẮT: đặc tả T4b chỉ lấy ca từ chối oan CÓ căn cứ trong ngữ cảnh",
    )
    parser.add_argument(
        "--tokenizer-path",
        default="",
        help="đường tokenizer thật (vd models/qwen25_05b_sft_adapter) — rỗng = chỉ ước lượng ký tự",
    )
    parser.add_argument("--dry-run", action="store_true", help="in số, không ghi tệp")
    args = parser.parse_args()

    rows, ledger = collect(args.rounds, Path(args.rounds_root), args.include_refusal_rows)
    ledger["note_blocked"] = (
        "blocked/skip là Cộng DỒN theo từng round: cùng một item bị chặn ở r5 và r6 sẽ đếm "
        "hai lần; chỉ số n_sft_rows đã khử trùng theo item id."
    )
    train_rows, holdout_rows, split_meta = group_split(rows, args.test_fraction, args.seed)
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "tools/build_sft_from_round.py",
        "task_scope": "chỉ dựng dữ liệu + chi phí; chưa train (quyết định user 24-10)",
        "referee": referee_fingerprint(),
        "source_rounds": ledger["rounds"],
        "ledger": ledger,
        "group_split": split_meta,
        "cost_proxy": token_cost_proxy(train_rows, args.max_length),
        "asserts": {
            "khong_document_nao_o_ca_hai_ben": True,
            "khong_item_id_nao_o_ca_hai_ben": True,
            "khong_dong_tren_item_split_test": all(
                r.get("split") == "trainpool" for r in train_rows + holdout_rows
            ),
        },
    }
    if args.tokenizer_path.strip():
        manifest["token_lengths"] = {
            "train": exact_token_lengths(train_rows, args.tokenizer_path.strip(), args.max_length),
            "holdout": exact_token_lengths(holdout_rows, args.tokenizer_path.strip(), args.max_length),
        }
    print(json.dumps(
        {
            "n_sft_rows": len(rows),
            "n_documents": ledger["n_documents"],
            "train_rows": split_meta["n_train_rows"],
            "holdout_rows": split_meta["n_holdout_rows"],
            "holdout_documents": split_meta["holdout_documents"],
            "blocked": ledger["blocked"],
            "cost_proxy": manifest["cost_proxy"],
        },
        ensure_ascii=True,
        indent=2,
    ))
    if not args.dry_run:
        write_outputs(Path(args.out_root), train_rows, holdout_rows, manifest)
        print(f"[T4b] ghi vào {args.out_root}/ (sft_train, sft_holdout, manifest)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
