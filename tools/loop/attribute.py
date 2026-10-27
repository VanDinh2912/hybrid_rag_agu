"""Quy lỗi `FAIL_RETRIEVAL` theo tầng — công cụ hỗ trợ quyết định đòn bẩy (P5).

`triage.py` đã đủ để sinh dữ liệu train, nhưng để CHỌN sửa tầng nào thì cần một câu
hỏi khác: chunk vàng biến mất vì XẾP HẠNG kém hay vì bị `source_filter` của router
CẮT khỏi cửa sổ? Hai câu trả lời dẫn tới hai việc hoàn toàn khác nhau (train lại
classifier / nới bảng allowlist / sửa code retriever), nên tách thành tool riêng.

Chạy:
    python tools/loop/attribute.py --round r0
    python tools/loop/attribute.py --round r1 --compare r0

Đọc `retrieval.jsonl` (mỗi dòng có `item` + `retrieval_config` + `labels`), không
sinh văn bản, không gọi model. Kết quả ghi `attribution.json` cùng thư mục round.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.text_utils import fold  # noqa: E402
from tools.loop.verify import score_item  # noqa: E402


def _fold(value: Any) -> str:
    return fold(str(value or ""))


def source_blocks_gold(source_filter: Iterable[str] | None, gold_source: str | None) -> bool:
    """True nếu `source_filter` tồn tại mà KHÔNG thành phần nào khớp văn bản chứa
    (hoặc được chứa trong) tên văn bản của chunk vàng.

    So khớp hai chiều sau `fold()` vì tên file trong bảng allowlist và metadata
    Chroma không phải lúc nào cũng giống nhau từng ký tự (dấu cách, phần mở rộng).
    """
    sources = [s for s in (source_filter or []) if s]
    if not sources or not gold_source:
        return False
    gold = _fold(gold_source)
    for source in sources:
        allowed = _fold(source)
        if allowed == gold or allowed in gold or gold in allowed:
            return False
    return True


def classify_failure(row: dict, verdict: dict) -> str:
    """Một verdict FAIL_RETRIEVAL -> một trong ba nhóm nguyên nhân."""
    item = row.get("item") or {}
    config = row.get("retrieval_config") or {}
    if verdict.get("verdict") != "FAIL_RETRIEVAL":
        return "not_retrieval_failure"
    if source_blocks_gold(config.get("source_filter"), item.get("source_document")):
        # Còn phân nhánh: nhãn chủ đề sai (lever classifier) hay bảng allowlist hẹp
        # (lever router)?
        expected = _fold(item.get("topic"))
        predicted = _fold(verdict.get("predicted_topic"))
        if expected and predicted and expected == predicted:
            return "filter_blocked_wrong_table"
        return "filter_blocked_wrong_topic"
    if not config.get("source_filter"):
        return "ranking_no_filter"
    return "ranking_despite_filter"


def attribute_round(round_dir: Path, top_k: int = 6, phase: str = "retrieval") -> dict:
    path = round_dir / f"{phase}.jsonl"
    if not path.exists():
        raise SystemExit(f"Không có {path} — round này chưa chạy pha {phase}.")
    groups = collections.Counter()
    families = collections.defaultdict(collections.Counter)
    blocked_docs = collections.Counter()
    confusion = collections.Counter()
    total = 0
    retrieval_failures = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        total += 1
        verdict = score_item(row.get("item") or {}, row, top_k=top_k)
        if verdict.get("verdict") != "FAIL_RETRIEVAL":
            continue
        retrieval_failures += 1
        group = classify_failure(row, verdict)
        groups[group] += 1
        families[row["item"].get("family") or "?"][group] += 1
        if group.startswith("filter_blocked"):
            blocked_docs[row["item"].get("source_document") or "?"] += 1
        if group == "filter_blocked_wrong_topic":
            confusion[
                (
                    row["item"].get("topic") or "?",
                    (row.get("labels") or {}).get("topic") or "?",
                )
            ] += 1
    blocked = groups["filter_blocked_wrong_table"] + groups["filter_blocked_wrong_topic"]
    return {
        "round_dir": str(round_dir),
        "phase": phase,
        "n_items": total,
        "fail_retrieval": retrieval_failures,
        "groups": dict(groups),
        "share_blocked_by_filter": round(blocked / retrieval_failures, 4) if retrieval_failures else None,
        "by_family": {k: dict(v) for k, v in sorted(families.items())},
        "top_blocked_documents": blocked_docs.most_common(10),
        "topic_confusion_causing_blocks": [
            {"expected": e, "predicted": p, "n": n} for (e, p), n in confusion.most_common(10)
        ],
    }


def diff_rounds(base: dict, cand: dict) -> dict:
    """So phân bố nguyên nhân giữa hai round — cổng cho biết ĐẠT/HỎNG, còn đây cho
    biết đòn bẩy có tác dụng đúng chỗ nó nhắm vào không."""
    out = {}
    for group in sorted(set(base["groups"]) | set(cand["groups"])):
        out[group] = {
            "baseline": base["groups"].get(group, 0),
            "candidate": cand["groups"].get(group, 0),
            "delta": cand["groups"].get(group, 0) - base["groups"].get(group, 0),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", required=True)
    parser.add_argument("--compare", default=None, help="round gốc để so phân bố nguyên nhân")
    parser.add_argument("--phase", default="retrieval")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--rounds-root", default=str(ROOT / "data" / "loop" / "rounds"))
    args = parser.parse_args()

    rounds_root = Path(args.rounds_root)
    report = attribute_round(rounds_root / args.round, top_k=args.top_k, phase=args.phase)
    if args.compare:
        report["diff_vs_baseline"] = diff_rounds(
            attribute_round(rounds_root / args.compare, top_k=args.top_k, phase=args.phase),
            report,
        )
    out_path = rounds_root / args.round / f"attribution_{args.phase}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"--- QUY LỖI FAIL_RETRIEVAL round {args.round} ({args.phase}) ---")
    print(f"số item: {report['n_items']} | FAIL_RETRIEVAL: {report['fail_retrieval']}")
    for group, n in sorted(report["groups"].items(), key=lambda kv: -kv[1]):
        print(f"  {group:28s} {n:4d}")
    if report["share_blocked_by_filter"] is not None:
        print(f"  bị source_filter cắt = {report['share_blocked_by_filter']:.1%} của FAIL_RETRIEVAL")
    for row in report["topic_confusion_causing_blocks"][:5]:
        print(f"  nhầm chủ đề: {row['expected']} -> {row['predicted']} ({row['n']})")
    if "diff_vs_baseline" in report:
        print("  so voi round goc:")
        for group, d in report["diff_vs_baseline"].items():
            print(f"    {group:28s} {d['baseline']} -> {d['candidate']} ({d['delta']:+d})")
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
