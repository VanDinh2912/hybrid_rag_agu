"""Hiệu chỉnh `src/answer_guard.check_grounding` trên dữ liệu A/B đã có.

Mục đích: đo tỉ lệ câu trả lời chứa khẳng định không căn cứ BẰNG LỖ CŨ (không
tốn một request API nào), đồng thời soi manual để chắc chắn trọng tài không báo
động giả (số trong bảng, tên file, định dạng markdown).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.answer_guard import check_grounding, extract_entities  # noqa: E402


def main(paths: list[str]) -> None:
    for path in paths:
        data = json.loads((ROOT / path).read_text(encoding="utf-8"))
        entries = data.get("per_question", [])
        counter: Counter = Counter()
        examples: dict[str, list] = {}
        for e in entries:
            answer = e.get("answer") or ""
            contexts = e.get("contexts") or []
            question = e.get("raw_query") or ""
            if not answer or e.get("error"):
                counter["skip_no_answer"] += 1
                continue
            if e.get("is_refusal_answer"):
                counter["refusal"] += 1
                continue
            if not contexts:
                counter["skip_no_contexts"] += 1
                continue
            rep = check_grounding(answer, contexts, question)
            counter["scored"] += 1
            if rep.unsupported:
                counter["has_unsupported"] += 1
                for ent in rep.unsupported:
                    key = f"{ent.kind}"
                    counter[f"unsupported_kind:{key}"] += 1
                    examples.setdefault(key, []).append(
                        (e.get("id"), ent.text, answer[:150])
                    )
            else:
                counter["clean"] += 1
            scores = getattr(main, "_scores", None)
            if scores is None:
                scores = main._scores = []
            if rep.grounding_score is not None:
                scores.append(rep.grounding_score)

        print(f"\n=== {path} ===")
        for k, v in counter.most_common():
            print(f"  {k}: {v}")
        scores = getattr(main, "_scores", [])
        if scores:
            scores.sort()
            print(
                f"  grounding_score trung bình={sum(scores)/len(scores):.3f} "
                f"p10={scores[max(0,len(scores)//10)]:.3f} median={scores[len(scores)//2]:.3f}"
            )
        for kind, items in examples.items():
            print(f"  --- mẫu không căn cứ loại {kind} ---")
            for qid, ent, snippet in items[:8]:
                print(f"    [{qid}] '{ent}' | {snippet}")
        main._scores = []


if __name__ == "__main__":
    main(sys.argv[1:] or ["outputs/ab_results_with_classifier.json"])
