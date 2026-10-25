"""T4b — KIỂM ĐỊNH dữ liệu SFT (CHỈ ĐỌC, không train, không gọi model, không sửa gì).

Vì sao có file này: dữ liệu SFT là thứ duy nhất trong repo có thể "dạy" model 1,5B/0,5B
làm sai mà không ai thấy — một dòng rò rỉ test, một dòng có đáp án nằm ngoài ngữ cảnh,
hay một ca "không có đáp án" bị dán nhãn trả lời đều làm điểm eval tăng giả. Unit test
(`tests/test_t4_sft_invariants.py`) gọi thẳng các hàm ở đây, và mục 1–5 của đề bài T4
được chạy thật trên artifact đã công bố `data/training/t4b_r5r8r9r10`.

Năm bất biến, đúng thứ tự đề bài:

1. **Bất biến 7** — mỗi dòng `sft_extractive` phải chứa THỰC THỂ VÀNG và TÊN NGUỒN trong
   phần ngữ cảnh của chính nó. Thực thể + nguồn là BẮT BUỘC (thiếu ⇒ đỏ). `gold_sentence`
   chỉ là thông tin (INFO): bộ sinh hiện hành dùng luật nới `len(covered) < min(2, len(frags))`
   nên có thể giữ dòng thiếu câu vàng nếu thực thể + nguồn đã phủ 2 mẩu — đo trên artifact
   là 5/13 dòng. Luật 2/N đó là khoảng trống đã ghi PA-28, KHÔNG phải chỗ để nới kiểm định.
2. **Chặn rò rỉ** — không item `split != "trainpool"` nào được xuất hiện trong train, theo
   **id** và theo **gold_sentence đã fold**. Phát hiện là DỪNG (`SftInvariantError`), không
   chỉ cảnh báo: rò rỉ làm mọi số đo sau đó vô nghĩa.
3. **Group split** — nguyên cả tài liệu về MỘT phía; kiểm thêm mức `(tài liệu, Điều)` khi
   nhận diện được số Điều (ưu tiên `item["article"]`, rồi `gold_sentence`, rồi nhãn
   `[Điều N.]` trong ngữ cảnh). Không nhận diện được thì ĐẾM là "không xác định", không
   im lặng coi là đạt.
4. **Nhãn từ chối** — ca `FAIL_HALLUCINATED_ON_UNANSWERABLE` / `FAIL_CONFIRMED_FALSE_PREMISE`
   chỉ được thành `sft_refusal` với assistant ĐÚNG `REFUSAL_TEXT`; không được thành
   `sft_extractive`, và dòng `sft_refusal` không được sinh từ verdict khác.
5. **Định dạng** — mọi dòng parse được (lỗi parse là DỪNG kèm số dòng), không dòng rỗng,
   không dòng trùng, và độ dài token ≤ `--max-length` (mặc định 768 — trần đã chốt cho GPU
   4 GB, xem `models/train_sft_lora.py` + D-10). Độ dài lấy từ tokenizer THẬT khi có
   `--tokenizer-path`, hoặc từ `manifest["token_lengths"]` của artifact, hoặc ước lượng
   ký tự/3,6 — mỗi đường đều ghi rõ nguồn trong báo cáo.

Nguyên tắc:
- CHỈ ĐỌC: không ghi vào `data/training/`, không chạm `src/`, không đụng trọng tài.
- Không tự chế thang đo thứ hai: thực thể/nguồn lấy đúng `triage.target_fragments` (gọi lại
  hàm đó), fold lấy từ `src.text_utils.fold`, `REFUSAL_TEXT` lấy từ `src.generator`.
- Mục 5 có thể ĐỎ trên dữ liệu thật (13/13 dòng train > 768 token) — báo ĐỎ, không cắt dòng
  (cắt = mất căn cứ) và không nâng trần (vượt VRAM 4 GB ⇒ xem PA-11/PA-12).

Chạy thật:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/check_sft_invariants.py
Tuỳ chọn: --artifact-root, --rounds r5 r8 r9 r10, --max-length 768,
          --tokenizer-path models/qwen25_05b_sft_adapter, --out <file.json>, --strict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generator import REFUSAL_TEXT  # noqa: E402 (hằng số đã công bố, không chép lại)
from src.text_utils import fold  # noqa: E402
from tools.loop.triage import target_fragments  # noqa: E402 (KHÔNG viết lại luật mẩu căn cứ)

DEFAULT_ARTIFACT = ROOT / "data" / "training" / "t4b_r5r8r9r10"
DEFAULT_ROUNDS = ("r5", "r8", "r9", "r10")
DEFAULT_MAX_LENGTH = 768
CHARS_PER_TOKEN = 3.6

UNANSWERABLE_VERDICTS = frozenset({"FAIL_HALLUCINATED_ON_UNANSWERABLE", "FAIL_CONFIRMED_FALSE_PREMISE"})
ANSWER_TASKS = frozenset({"sft_extractive"})
QUESTION_SEP = "\n\nCâu hỏi:"
_ARTICLE_RE = re.compile(r"Điều\s+(\d+)")


class SftInvariantError(AssertionError):
    """Vi phạm bất biến dữ liệu SFT — luôn có nghĩa 'DỪNG', không phải cảnh báo."""


# --------------------------------------------------------------------- nạp dữ liệu

def load_jsonl(path: Path) -> list[dict]:
    """Đọc JSONL; dòng hỏng là DỪNG kèm số dòng (mục 5: 'mọi dòng parse được')."""
    path = Path(path)
    rows: list[dict] = []
    if not path.exists():
        return rows
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SftInvariantError(f"{path.name} dòng {lineno} không parse được: {exc}") from exc
    return rows


def load_artifact(root: Path | str) -> dict:
    root = Path(root)
    manifest_path = root / "manifest.json"
    return {
        "root": str(root),
        "train": load_jsonl(root / "sft_train.jsonl"),
        "holdout": load_jsonl(root / "sft_holdout.jsonl"),
        "manifest": json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {},
    }


def read_round_items(
    rounds: Iterable[str], rounds_root: Path | str = ROOT / "data" / "loop" / "rounds"
) -> dict[str, dict]:
    """id -> item, cùng thứ tự ưu tiên như `build_sft_from_round.read_items`.

    `rounds=()` nghĩa là quét mọi round có trong `rounds_root` (test dùng fixture riêng).
    """
    rounds_root = Path(rounds_root)
    names = list(rounds) or sorted(p.name for p in rounds_root.iterdir() if p.is_dir())
    items: dict[str, dict] = {}
    for name in names:
        rdir = rounds_root / name
        for fname in ("verdicts_full.jsonl", "full.jsonl"):
            for row in load_jsonl(rdir / fname):
                item = row.get("item")
                if item and row["id"] not in items:
                    items[row["id"]] = item
    return items


# ------------------------------------------------------------------ trích ngữ cảnh dòng

def context_of(row: dict) -> str:
    """Phần NGỮ CẢNH của dòng (mọi thứ trước dấu phân cách câu hỏi), không gồm câu hỏi."""
    for msg in row.get("messages") or []:
        if msg.get("role") == "user":
            content = msg.get("content") or ""
            return content.split(QUESTION_SEP)[0]
    return ""


def question_of(row: dict) -> str:
    for msg in row.get("messages") or []:
        if msg.get("role") == "user":
            content = msg.get("content") or ""
            return content.split(QUESTION_SEP, 1)[1] if QUESTION_SEP in content else ""
    return ""


def answer_of(row: dict) -> str:
    for msg in row.get("messages") or []:
        if msg.get("role") == "assistant":
            return msg.get("content") or ""
    return ""


def _norm(text: str) -> str:
    return fold(re.sub(r"\s+", " ", str(text or "")).strip())


def mandatory_fragments(item: dict, source: str) -> list[str]:
    """Mẩu BẮT BUỘC: mọi thực thể vàng + tên nguồn (đề bài mục 1).

    Lấy từ `triage.target_fragments` rồi BỎ đúng câu vàng — để luật mẩu của bộ sinh và
    luật kiểm định không bao giờ lệch nhau ở phần thực thể/nguồn.
    """
    gold_sentence = _norm(item.get("gold_sentence") or "")
    out: list[str] = []
    for frag in target_fragments(item, source):
        if not frag or _norm(frag) == gold_sentence:
            continue
        key = _norm(frag)
        if key and key not in out:
            out.append(frag)
    return out


def informational_fragments(item: dict) -> list[str]:
    """Mẩu CHỈ ĐỂ BÁO CÁO: câu vàng (luật sinh hiện hành chỉ đòi 2/N — xem PA-28)."""
    sentence = str(item.get("gold_sentence") or "").strip()
    return [re.sub(r"\s+", " ", sentence)] if sentence else []


def article_of(item: dict, context: str = "") -> tuple[Optional[str], str]:
    """Số Điều của item + nguồn suy ra: 'item' | 'gold_sentence' | 'context' | ''."""
    for key in ("article", "gold_article"):
        value = item.get(key)
        if value:
            match = _ARTICLE_RE.search(str(value))
            return (match.group(1) if match else str(value)), "item"
    match = _ARTICLE_RE.search(str(item.get("gold_sentence") or ""))
    if match:
        return match.group(1), "gold_sentence"
    # Nhãn `[Điều N.]` do corpus chèn vào đầu chunk; chỉ dùng khối ĐẦU để tránh bắt
    # những Điều được trích dẫn phụ trong cùng ngữ cảnh.
    head = context.split("\n\n", 1)[0] if context else ""
    match = _ARTICLE_RE.search(head)
    if match:
        return match.group(1), "context"
    return None, ""


# ------------------------------------------------------------------------- 1. bất biến 7

def check_evidence_in_context(rows: list[dict], items: dict[str, dict]) -> dict:
    """Mỗi dòng sft_extractive: thực thể vàng + tên nguồn PHẢI nằm trong ngữ cảnh của nó."""
    report = {
        "n_rows": 0,
        "rows_missing_item": [],
        "rows_missing_mandatory": [],   # ĐỎ: thiếu thực thể/nguồn
        "rows_missing_gold_sentence": [],  # INFO: thiếu câu vàng (PA-28)
        "missing_by_kind": Counter(),
    }
    for row in rows:
        if row.get("task") != "sft_extractive":
            continue
        report["n_rows"] += 1
        item_id = (row.get("provenance") or {}).get("item_id")
        item = items.get(item_id)
        if not item:
            report["rows_missing_item"].append(item_id)
            continue
        context_folded = fold(context_of(row))
        source = str(item.get("source_document") or "")
        missing = [f for f in mandatory_fragments(item, source) if _norm(f) not in _norm(context_folded)]
        if missing:
            report["rows_missing_mandatory"].append({"item_id": item_id, "missing": missing})
            for frag in missing:
                kind = "source" if _norm(frag) == _norm(source) else "entity"
                report["missing_by_kind"][kind] += 1
        missing_sentence = [f for f in informational_fragments(item) if _norm(f) not in _norm(context_folded)]
        if missing_sentence:
            report["rows_missing_gold_sentence"].append(item_id)
    report["ok"] = not report["rows_missing_item"] and not report["rows_missing_mandatory"]
    report["missing_by_kind"] = dict(report["missing_by_kind"])
    return report


# ------------------------------------------------------------------------ 2. chặn rò rỉ

def test_ids_of(items: dict[str, dict]) -> set[str]:
    return {item_id for item_id, item in items.items() if item.get("split") != "trainpool"}


def check_no_leak(
    train_rows: list[dict],
    items: dict[str, dict],
    *,
    raise_on_leak: bool = True,
) -> dict:
    """Không item test nào lọt vào train: theo id và theo gold_sentence đã fold.

    `raise_on_leak=True` (mặc định) là hành vi 'bắt và dừng' của đề bài mục 2 — vi phạm
    thì mọi số đo sau đó vô nghĩa, không được phép chạy tiếp.
    """
    test_ids = test_ids_of(items)
    train_ids = {(row.get("provenance") or {}).get("item_id") for row in train_rows}
    id_leaks = sorted(test_ids & train_ids)
    train_text = _norm("\n".join(json.dumps(row, ensure_ascii=False) for row in train_rows))
    sentence_leaks = []
    for item_id in test_ids:
        for sentence in informational_fragments(items[item_id]):
            if _norm(sentence) and _norm(sentence) in train_text:
                sentence_leaks.append({"item_id": item_id, "gold_sentence": sentence})
    report = {
        "n_test_items": len(test_ids),
        "n_train_rows": len(train_rows),
        "id_leaks": id_leaks,
        "sentence_leaks": sentence_leaks,
        "ok": not id_leaks and not sentence_leaks,
    }
    if report["ok"] is False and raise_on_leak:
        detail = []
        if id_leaks:
            detail.append(f"id test trong train: {id_leaks[:5]}")
        if sentence_leaks:
            detail.append(f"gold_sentence test trong train: {[x['item_id'] for x in sentence_leaks[:5]]}")
        raise SftInvariantError("Rò rỉ test-set: " + "; ".join(detail))
    return report


# ------------------------------------------------------------------------ 3. group split

def check_group_split(
    train_rows: list[dict],
    holdout_rows: list[dict],
    items: dict[str, dict],
    *,
    raise_on_overlap: bool = True,
) -> dict:
    """Nguyên cả tài liệu về một phía; kiểm thêm mức (tài liệu, Điều)."""
    def doc_of(row: dict) -> str:
        return str(row.get("group_document") or "(không rõ nguồn)")

    train_docs = {doc_of(r) for r in train_rows}
    holdout_docs = {doc_of(r) for r in holdout_rows}
    doc_overlap = sorted(train_docs & holdout_docs)

    sides: dict[tuple[str, str], set[str]] = defaultdict(set)
    unidentified = 0
    for name, rows in (("train", train_rows), ("holdout", holdout_rows)):
        for row in rows:
            item = items.get((row.get("provenance") or {}).get("item_id")) or {}
            article, _how = article_of(item, context_of(row))
            if article is None:
                unidentified += 1
                continue
            sides[(doc_of(row), article)].add(name)
    article_overlap = sorted(k for k, v in sides.items() if len(v) > 1)

    report = {
        "n_train_rows": len(train_rows),
        "n_holdout_rows": len(holdout_rows),
        "train_documents": sorted(train_docs),
        "holdout_documents": sorted(holdout_docs),
        "document_overlap": doc_overlap,
        "n_document_article_groups": len(sides),
        "rows_without_article": unidentified,
        "article_overlap": [{"document": d, "article": a} for d, a in article_overlap],
        "ok": not doc_overlap and not article_overlap,
    }
    if report["ok"] is False and raise_on_overlap:
        raise SftInvariantError(
            f"Group split rò rỉ: tài liệu {doc_overlap[:5]}; (tài liệu, Điều) {article_overlap[:5]}"
        )
    return report


# ------------------------------------------------------------------------ 4. nhãn từ chối

def check_refusal_labels(rows: list[dict], items: dict[str, dict]) -> dict:
    """Ca 'không đáp án' phải là refusal đúng câu chuẩn; không được dán nhãn trả lời."""
    problems = []
    n_refusal = 0
    for row in rows:
        item_id = (row.get("provenance") or {}).get("item_id")
        verdict = (row.get("provenance") or {}).get("verdict")
        task = row.get("task")
        if task == "sft_refusal":
            n_refusal += 1
            if verdict not in UNANSWERABLE_VERDICTS:
                problems.append({"item_id": item_id, "kind": "refusal_from_answerable", "verdict": verdict})
            if answer_of(row).strip() != REFUSAL_TEXT:
                problems.append({"item_id": item_id, "kind": "refusal_text_differs", "answer": answer_of(row)[:80]})
        if verdict in UNANSWERABLE_VERDICTS and task in ANSWER_TASKS:
            problems.append({"item_id": item_id, "kind": "unanswerable_labeled_answer", "task": task})
        if verdict in UNANSWERABLE_VERDICTS:
            item = items.get(item_id)
            if item is not None and item.get("split") != "trainpool":
                problems.append({"item_id": item_id, "kind": "unanswerable_from_test_split"})
    kinds = Counter(p["kind"] for p in problems)
    return {
        "n_refusal_rows": n_refusal,
        "problems": problems,
        "by_kind": dict(kinds),
        "ok": not problems,
    }


# -------------------------------------------------------------------------- 5. định dạng

def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN)


def row_text(row: dict) -> str:
    return json.dumps(row.get("messages") or [], ensure_ascii=False)


def exact_tokens(row: dict, tokenizer: Any) -> int:
    """Đếm bằng tokenizer thật, đi đúng đường `tokenize=False` + encode.

    Đo 24-10: `apply_chat_template(..., tokenize=True)` trả 2 token cho dòng 3.424 ký tự
    (template hỏng trên đường đó) — hai script train/eval của repo đã tránh bằng
    tokenize=False, ở đây giữ nguyên cách đó.
    """
    text = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
    return len(tokenizer(text)["input_ids"])


def check_format(
    rows: list[dict],
    max_length: int = DEFAULT_MAX_LENGTH,
    *,
    tokenizer: Any = None,
    exact_lengths: Optional[dict[str, int]] = None,
) -> dict:
    """Parse/empty/dup + độ dài token ≤ trần. `exact_lengths` = item_id -> token (từ manifest)."""
    empty_rows, duplicate_rows, lengths = [], [], []
    seen: dict[tuple, int] = {}
    for idx, row in enumerate(rows):
        messages = row.get("messages") or []
        if not messages or any(not str(m.get("content") or "").strip() for m in messages):
            empty_rows.append(idx)
        key = tuple((m.get("role"), m.get("content")) for m in messages)
        if key in seen:
            duplicate_rows.append({"row": idx, "same_as": seen[key]})
        else:
            seen[key] = idx

        if tokenizer is not None:
            count, method = exact_tokens(row, tokenizer), "tokenizer"
        else:
            item_id = (row.get("provenance") or {}).get("item_id")
            if exact_lengths and item_id in exact_lengths:
                count, method = int(exact_lengths[item_id]), "manifest"
            else:
                count, method = estimate_tokens(row_text(row)), "estimate"
        lengths.append({"row": idx, "item_id": (row.get("provenance") or {}).get("item_id"),
                        "tokens": count, "method": method})

    over = [x for x in lengths if x["tokens"] > max_length]
    methods = Counter(x["method"] for x in lengths)
    return {
        "n_rows": len(rows),
        "empty_rows": empty_rows,
        "duplicate_rows": duplicate_rows,
        "max_length": max_length,
        "token_method": dict(methods),
        "tokens_min": min((x["tokens"] for x in lengths), default=0),
        "tokens_median": sorted(x["tokens"] for x in lengths)[len(lengths) // 2] if lengths else 0,
        "tokens_max": max((x["tokens"] for x in lengths), default=0),
        "rows_over_max_length": over,
        "per_row": lengths,
        "ok": not empty_rows and not duplicate_rows and not over,
    }


# --------------------------------------------------------------------------- toàn bộ

def _manifest_exact(manifest: dict, side: str) -> dict[str, int]:
    block = ((manifest or {}).get("token_lengths") or {}).get(side) or {}
    return {
        row["item_id"]: int(row["tokens"])
        for row in block.get("per_row") or []
        if row.get("item_id") is not None and row.get("tokens") is not None
    }


def check_artifact(
    artifact_root: Path | str = DEFAULT_ARTIFACT,
    rounds: Iterable[str] = DEFAULT_ROUNDS,
    *,
    rounds_root: Path | str = ROOT / "data" / "loop" / "rounds",
    max_length: int = DEFAULT_MAX_LENGTH,
    tokenizer: Any = None,
    raise_on_violation: bool = False,
) -> dict:
    """Chạy cả 5 bất biến trên một artifact. `raise_on_violation` dùng cho test 'bắt và dừng'."""
    artifact = load_artifact(artifact_root)
    train, holdout, manifest = artifact["train"], artifact["holdout"], artifact["manifest"]
    items = read_round_items(rounds, rounds_root)

    evidence = check_evidence_in_context(train, items)
    leak = check_no_leak(train, items, raise_on_leak=raise_on_violation)
    split = check_group_split(train, holdout, items, raise_on_overlap=raise_on_violation)
    refusal = check_refusal_labels(train + holdout, items)
    fmt = {
        "train": check_format(train, max_length, tokenizer=tokenizer,
                              exact_lengths=_manifest_exact(manifest, "train")),
        "holdout": check_format(holdout, max_length, tokenizer=tokenizer,
                                exact_lengths=_manifest_exact(manifest, "holdout")),
    }
    checks = {
        "1_evidence_in_context": evidence["ok"],
        "2_no_test_leak": leak["ok"],
        "3_group_split": split["ok"],
        "4_refusal_labels": refusal["ok"],
        "5_format_and_length": fmt["train"]["ok"] and fmt["holdout"]["ok"],
    }
    report = {
        "artifact_root": str(artifact_root),
        "rounds": list(rounds),
        "n_items": len(items),
        "n_train_rows": len(train),
        "n_holdout_rows": len(holdout),
        "1_evidence_in_context": evidence,
        "2_no_test_leak": leak,
        "3_group_split": split,
        "4_refusal_labels": refusal,
        "5_format": fmt,
        "checks": checks,
        "verdict": "XANH" if all(checks.values()) else "ĐỎ",
        "red_checks": [k for k, v in checks.items() if not v],
        "note_item5": (
            "ĐỎ ở mục 5 là ĐỎ của DỮ LIỆU, không phải của bộ kiểm: dòng > max_length bị "
            "train_sft_lora cắt cụt (mất căn cứ). Cách sửa không được phép tự làm: nâng "
            "trần vượt VRAM 4 GB (PA-11 4-bit / PA-12 đổi định dạng) hoặc sinh lại dòng ngắn hơn."
        ),
    }
    if raise_on_violation and report["verdict"] != "XANH":
        raise SftInvariantError(f"Artifact ĐỎ ở: {report['red_checks']}")
    return report


def _load_tokenizer(path: str) -> Any:
    from transformers import PreTrainedTokenizerFast

    return PreTrainedTokenizerFast.from_pretrained(path, local_files_only=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="T4b: kiểm 5 bất biến dữ liệu SFT (chỉ đọc).")
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT))
    parser.add_argument("--rounds", nargs="*", default=list(DEFAULT_ROUNDS))
    parser.add_argument("--rounds-root", default=str(ROOT / "data" / "loop" / "rounds"))
    parser.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument("--tokenizer-path", default="", help="nếu có: đếm token thật thay vì manifest/ước lượng")
    parser.add_argument("--out", default="", help="ghi báo cáo JSON (mặc định chỉ in)")
    parser.add_argument("--strict", action="store_true", help="exit 1 khi có mục ĐỎ")
    args = parser.parse_args()

    tokenizer = _load_tokenizer(args.tokenizer_path) if args.tokenizer_path.strip() else None
    report = check_artifact(
        args.artifact_root, args.rounds, rounds_root=args.rounds_root,
        max_length=args.max_length, tokenizer=tokenizer,
    )
    summary = {
        "artifact_root": report["artifact_root"],
        "n_train_rows": report["n_train_rows"],
        "n_holdout_rows": report["n_holdout_rows"],
        "checks": report["checks"],
        "verdict": report["verdict"],
        "red_checks": report["red_checks"],
        "1_evidence_in_context": {k: v for k, v in report["1_evidence_in_context"].items() if k != "rows_missing_gold_sentence"},
        "gold_sentence_missing_rows": report["1_evidence_in_context"]["rows_missing_gold_sentence"],
        "2_no_test_leak": {k: v for k, v in report["2_no_test_leak"].items() if k != "sentence_leaks"},
        "3_group_split": {k: v for k, v in report["3_group_split"].items() if k not in ("train_documents", "holdout_documents")},
        "4_refusal_labels": report["4_refusal_labels"],
        "5_format": {
            side: {k: v for k, v in block.items() if k != "per_row"}
            for side, block in report["5_format"].items()
        },
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[T4b] ghi báo cáo: {out_path}")
    if args.strict and report["verdict"] != "XANH":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
