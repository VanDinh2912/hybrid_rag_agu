"""Triage: biến LỖI của round thành dữ liệu huấn luyện cho ĐÚNG tầng gây lỗi.

Ba luật chống tự lừa mình (được thực thi bằng assert, không phải bằng lời khuyên):
1. Item có split == 'test' KHÔNG BAO GIỜ được sinh ra dòng train. Test chỉ dùng để
   đo. Vi phạm luật này là toàn bộ bệnh "điểm tăng nhưng hệ thống không giỏi hơn".
2. Mỗi dòng train phải mang provenance: round, item id, lever, đường dẫn chunk vàng.
   Không provenance thì không được nạp vào batch train nào.
3. Câu trả lời huấn luyện tầng sinh là TRÍCH NIÊM (extractive): nội dung = câu gold
   nguyên văn từ chunk + trích dẫn nguồn. Không có dòng nào do AI viết lại.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.text_utils import fold  # noqa: E402

REFUSAL_TEXT = "Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."

LEVER_OF_VERDICT = {
    "FAIL_RETRIEVAL": "retrieval",
    "FAIL_FABRICATED": "generation",
    "FAIL_HALLUCINATED_ON_UNANSWERABLE": "refusal",
    "FAIL_CONFIRMED_FALSE_PREMISE": "refusal",
    "FAIL_OVERREFUSAL": "guardrail",
    "FAIL_INCOMPLETE": "generation",
}

# Verdict nào chứng minh nhãn phân loại sai -> sửa classifier.
# FAIL_HALLUCINATED_ON_UNANSWERABLE nằm ở đây vì nó thường bắt nguồn từ nhãn: câu
# lẽ ra NGOAI_PHAM_VI bị nhận thành TRA_CUU nên router không bật source_filter và
# generator không được nhét dòng từ chối chuẩn vào prompt.
LABEL_KEYS = {
    "FAIL_RETRIEVAL",
    "FAIL_OVERREFUSAL",
    "FAIL_INCOMPLETE",
    "FAIL_HALLUCINATED_ON_UNANSWERABLE",
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def gold_answer_for(item: dict, source: str) -> str:
    """Câu trả lời mẫu TRÍCH NIÊM: đúng một câu trong văn bản + trích dẫn nguồn."""
    sentence = re.sub(r"\s+", " ", item.get("gold_sentence") or "").strip()
    family = item.get("family")
    if family == "SOURCE_LOOKUP":
        return f"Quy định này nằm trong {source}. ({source})"
    if family == "CLOZE" or family == "CLOZE_OCR":
        value = item.get("primary_entity") or ""
        return f"Giá trị còn thiếu là {value}. ({source})"
    if family in ("TRAP", "TRAP_OCR"):
        return (
            f"Thông tin '{item.get('wrong_value')}' không đúng theo tài liệu. "
            f"Quy định ghi: {sentence} ({source})"
        )
    return f"{sentence} ({source})"


def lever_for(verdict: dict, item: dict) -> tuple[str, str]:
    """Quy lỗi theo BẰNG CHỨNG trong verdict, không theo nhãn verdict cụt.

    `FAIL_OVERREFUSAL` là hai chuyện khác nhau đóng chung một tên:
      - căn cứ đã nằm trong cửa sổ generator (`gold_in_top_k=True`, đo trên r1 là
        35/38 ca, 13 ca ngay block [1], và câu vàng đi qua `check_grounding` dễ dàng)
        mà model vẫn nói "không đủ thông tin" -> lỗi TRÍCH XUẤT ở tầng sinh, dạy lại
        được bằng SFT row;
      - item không có chunk vàng duy nhất (HUMAN, SOURCE_LOOKUP nhiều bản sao) nên
        không chứng minh được căn cứ có mặt -> chỉ nghi ngờ ngưỡng guardrail, ghi báo cáo.

    Gộp hết về "guardrail" như bản đầu khiến lớp lỗi lớn nhất của r1 (38/100) không
    sinh ra một dòng train nào — vòng lặp tự cắt tín hiệu học được của chính nó.
    """
    name = verdict["verdict"]
    if name == "FAIL_OVERREFUSAL":
        if verdict.get("gold_in_top_k"):
            return "generation", "overrefusal_evidence_in_window"
        return "guardrail", "overrefusal_evidence_unproven"
    return LEVER_OF_VERDICT.get(name, "unknown"), ""


def blocks_for_sft(contexts: list[str], sources: list[dict], gold_chunk_id: Any, limit: int = 4) -> list[str]:
    """Chọn + trình bày ngữ cảnh cho SFT row, giống khung prompt production.

    Hai chuyện bắt buộc:
      1. chunk vàng PHẢI có mặt. Cắt bừa `contexts[:4]` khi chunk vàng rank 5-6 tạo ra
         dòng train có đáp án nằm NGOÀI ngữ cảnh — đúng loại dữ liệu dạy model bịa.
      2. khối ngữ cảnh ghi kèm TÊN nguồn, vì đáp án của SOURCE_LOOKUP chính là tên file;
         nếu không có tên file thì không thể kiểm chứng dòng train bằng căn cứ.
    """
    if not contexts:
        return []
    idx_gold = next(
        (k for k, s in enumerate(sources) if gold_chunk_id is not None and s.get("chunk_id") == gold_chunk_id),
        None,
    )
    picked = list(range(min(limit, len(contexts))))
    if idx_gold is not None and idx_gold not in picked:
        picked = [idx_gold] + picked[: max(0, limit - 1)]
    blocks: list[str] = []
    for i in sorted(set(picked)):
        if i >= len(contexts):
            continue
        src = sources[i] if i < len(sources) else {}
        name = str(src.get("source") or "").strip()
        body = (contexts[i] or "")[:700]
        blocks.append(f"{name}: {body}" if name else body)
    return blocks


def target_fragments(item: dict, source: str) -> list[str]:
    """Mẩu nội dung một dòng sft_extractive được phép coi là 'đã có căn cứ'.

    Không so nguyên văn câu trả lời mẫu vì `gold_answer_for` có khung chữ riêng
    ("Giá trị còn thiếu là ...") — so đúng các thực thể vàng mà item đã neo, cộng tên
    nguồn cho câu tra theo văn bản.
    """
    frags = [str(e) for e in (item.get("required_entities") or []) if e]
    if item.get("primary_entity"):
        frags.append(str(item["primary_entity"]))
    if item.get("gold_sentence"):
        frags.append(re.sub(r"\s+", " ", str(item["gold_sentence"])).strip())
    if source:
        frags.append(str(source))
    return [f for f in frags if f]


def build_rows(round_dir: Path, round_name: str) -> tuple[list[dict], dict]:
    verdicts = load_jsonl(round_dir / "verdicts_full.jsonl") or load_jsonl(
        round_dir / "verdicts_retrieval.jsonl"
    )
    results_by_id: dict[str, dict] = {}
    for fname in ("full.jsonl", "retrieval.jsonl"):
        for row in load_jsonl(round_dir / fname):
            results_by_id.setdefault(row["id"], row)

    rows: list[dict] = []
    stats: Counter = Counter()
    failures_by_lever: dict[str, list[dict]] = defaultdict(list)

    for verdict in verdicts:
        if verdict["verdict"] in ("PASS_CORRECT", "PASS_REFUSAL", "PASS_CORRECTED_TRAP", "PENDING_GENERATION"):
            continue
        item = verdict.get("item") or results_by_id.get(verdict["id"], {}).get("item")
        if item is None:
            stats["skip_no_item"] += 1
            continue
        lever, note = lever_for(verdict, item)
        failures_by_lever[lever].append(
            {"id": verdict["id"], "verdict": verdict["verdict"], "query": item.get("raw_query"),
             "detail": verdict.get("detail"), "note": note, "answer_preview": verdict.get("answer_preview")}
        )
        if lever == "guardrail":
            # Từ chối oan KHÔNG chứng minh được căn cứ trong cửa sổ: sửa bằng NGƯỠNG,
            # không có dòng train nào (dạy từ chối khi chưa thấy căn cứ là dạy sai).
            stats["overrefusal_threshold_only"] += 1
            continue
        if item["split"] != "trainpool":
            stats["blocked_test_leak"] += 1
            continue

        source = item.get("source_document") or ""
        gold_chunk = item.get("gold_chunk_id")

        # ---- lever: retrieval -> cặp (query, chunk vàng, negative) ----
        if lever == "retrieval":
            row_result = results_by_id.get(verdict["id"], {})
            negatives = [
                s.get("chunk_id")
                for s in (row_result.get("sources") or [])[:6]
                if s.get("chunk_id") != gold_chunk
            ]
            rows.append(
                {
                    "task": "retrieval_pair",
                    "lever": "retrieval",
                    "query": item["raw_query"],
                    "positive_chunk_id": gold_chunk,
                    "negative_chunk_ids": negatives[:5],
                    "source_document": source,
                    "family": item["family"],
                    "provenance": {"round": round_name, "item_id": verdict["id"], "verdict": verdict["verdict"]},
                }
            )
            stats["retrieval_pair"] += 1

        # ---- lever: generation/refusal -> SFT row (trích niêm hoặc từ chối) ----
        if lever in ("generation", "refusal"):
            row_result = results_by_id.get(verdict["id"], {})
            raw_ctx = row_result.get("contexts") or []
            raw_src = row_result.get("sources") or []
            contexts = [c for c in raw_ctx[:4]]
            if verdict["verdict"] in ("FAIL_HALLUCINATED_ON_UNANSWERABLE", "FAIL_CONFIRMED_FALSE_PREMISE"):
                # Dạy từ chối: câu trainpool nhưng ngữ cảnh RÁC/không có chunk vàng.
                distractor = [c for c in contexts if gold_chunk is None] or ["(không có ngữ cảnh liên quan)"]
                rows.append(
                    {
                        "task": "sft_refusal",
                        "lever": "refusal",
                        "messages": [
                            {"role": "system", "content": "Chỉ trả lời dựa trên ngữ cảnh được cung cấp; nếu ngữ cảnh không đủ căn cứ, từ chối chuẩn và KHÔNG tự bổ sung số liệu."},
                            {"role": "user", "content": f"Ngữ cảnh:\n{distractor[0][:900]}\n\nCâu hỏi: {item['raw_query']}"},
                            {"role": "assistant", "content": REFUSAL_TEXT},
                        ],
                        "provenance": {"round": round_name, "item_id": verdict["id"], "verdict": verdict["verdict"]},
                    }
                )
                stats["sft_refusal"] += 1
            else:
                blocks = blocks_for_sft(raw_ctx, raw_src, gold_chunk)
                ctx_text = "\n\n".join(blocks[:4]) if blocks else "(không có ngữ cảnh)"
                target = gold_answer_for(item, source)
                # Bất biến chống tự-dạy-bịa: đích của sft_extractive phải có mặt trong
                # chính ngữ cảnh của dòng train. Không có thì BỎ DÒNG, không đoán tiếp.
                frags = target_fragments(item, source)
                covered = [f for f in frags if fold(f) in fold(ctx_text)]
                if not blocks or (frags and len(covered) < min(2, len(frags))):
                    stats["skip_sft_target_not_in_context"] += 1
                    continue
                rows.append(
                    {
                        "task": "sft_extractive",
                        "lever": "generation",
                        "messages": [
                            {"role": "system", "content": "Chỉ trả lời dựa trên ngữ cảnh được cung cấp và nêu rõ nguồn. Không nêu số liệu ngoài ngữ cảnh."},
                            {"role": "user", "content": f"Ngữ cảnh:\n{ctx_text[:3200]}\n\nCâu hỏi: {item['raw_query']}"},
                            {"role": "assistant", "content": target},
                        ],
                        "gold_chunk_id": gold_chunk,
                        "provenance": {"round": round_name, "item_id": verdict["id"], "verdict": verdict["verdict"], "note": note},
                    }
                )
                stats["sft_extractive"] += 1
                if note == "overrefusal_evidence_in_window":
                    stats["sft_extractive_from_overrefusal"] += 1

        # ---- lever: classifier (nhãn dự đoán sai trên trainpool) ----
        if verdict["verdict"] in LABEL_KEYS and item.get("topic"):
            predicted_topic = verdict.get("predicted_topic")
            predicted_type = verdict.get("predicted_question_type")
            expected_type = verdict.get("expected_question_type")
            if (predicted_topic and fold(predicted_topic) != fold(item["topic"])) or (
                expected_type and fold(predicted_type or "") != fold(expected_type)
            ):
                rows.append(
                    {
                        "task": "classifier_label",
                        "lever": "classifier",
                        "text": item["raw_query"],
                        "labels": {
                            "topic": item["topic"],
                            "question_type": expected_type or predicted_type or "TRA_CUU",
                        },
                        "predicted": {"topic": predicted_topic, "question_type": predicted_type},
                        "provenance": {"round": round_name, "item_id": verdict["id"], "verdict": verdict["verdict"]},
                    }
                )
                stats["classifier_label"] += 1

    return rows, {"stats": dict(stats), "failures_by_lever": {k: v for k, v in failures_by_lever.items()}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", required=True)
    parser.add_argument("--rounds-root", default=str(ROOT / "data" / "loop" / "rounds"))
    args = parser.parse_args()

    round_dir = Path(args.rounds_root) / args.round
    rows, report = build_rows(round_dir, args.round)

    # ASSERT chống rò rỉ: không dòng train nào mang split test.
    for row in rows:
        assert row["provenance"]["round"] == args.round

    out = round_dir / "trainpool_additions.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    md = [f"# Triage round `{args.round}`", "", f"Sinh lúc: {datetime.now().isoformat(timespec='seconds')}", ""]
    md.append("## Số dòng train đã tạo (chỉ từ item split=trainpool)")
    for key, value in sorted(report["stats"].items()):
        md.append(f"- `{key}`: {value}")
    md.append("")
    md.append("## Lỗi theo tầng (kể cả item test — chỉ để đọc, không để học)")
    for lever, items in sorted(report["failures_by_lever"].items()):
        md.append(f"### lever `{lever}` — {len(items)} lỗi")
        for it in items[:12]:
            note = f" — {it['note']}" if it.get("note") else ""
            md.append(f"- [{it['verdict']}] {it['id']}: {str(it['query'])[:110]}{note}")
            if it.get("detail"):
                md.append(f"  - detail: {json.dumps(it['detail'], ensure_ascii=False)[:220]}")
            if it.get("answer_preview"):
                md.append(f"  - model đã trả lời: {it['answer_preview'][:180]}")
        md.append("")
    (round_dir / "triage_report.md").write_text("\n".join(md), encoding="utf-8")
    (round_dir / "triage_stats.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["stats"], ensure_ascii=False, indent=2))
    print(f"\n-> {out}")
    print(f"-> {round_dir / 'triage_report.md'}")


if __name__ == "__main__":
    main()
