# -*- coding: utf-8 -*-
"""T6c — khung benchmark "câu hỏi THẬT của sinh viên" + runner chấm điểm.

Vì SAO KHÁC benchmark 811 item: bộ auto-generated kiểm tra TRÍCH NIÊM (câu sinh từ chính
câu trong tài liệu), nên gold@k cao không chứng minh hệ thống trả lời hay cho câu hỏi đời
thật. Bộ này đo CÂU HỎI KHÔNG THEO KHUÔN. Kết quả chỉ là BẰNG CHỨNG ĐỊNH TÍNH ở cỡ mẫu nhỏ
(30–50): máy chấm `check_grounding` deterministic, còn "có giúp được không" do NGƯỜI ĐỌC điền
tay. Không suy thành tỉ lệ chính xác toàn hệ thống.

File vào : tools/eval/real_questions.jsonl        (câu hỏi + cột người đọc, do người dùng điền)
File ra  : tools/eval/real_questions_scored.jsonl  (KHÔNG ghi đè file vào; thêm cột máy chấm)

Chạy:
    # 1) kiểm khung + ĐẾM số lượt gọi model TRƯỚC khi tốn GPU (bất biến #8):
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/eval/score_real_questions.py --dry-run
    # 2) khi đã chắc chắn, chấm thật (mỗi câu 1 lượt pipeline):
    ... tools/eval/score_real_questions.py --limit 5      # thử 5 câu trước
    ... tools/eval/score_real_questions.py                # toàn bộ câu thật
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

EVAL_DIR = ROOT / "tools" / "eval"
IN_PATH = EVAL_DIR / "real_questions.jsonl"
OUT_PATH = EVAL_DIR / "real_questions_scored.jsonl"

HELP_SCORE = {"co": 1.0, "mot_phan": 0.5, "khong": 0.0}
HUMAN_COL = "co_giup_duoc_khong"
REQUIRED_FIELDS = ("id", "question", HUMAN_COL)
TESTSET_PATH = ROOT / "data" / "loop" / "testset_v1.jsonl"


def _norm_question(text: str) -> str:
    """Chuẩn hóa để phát hiện trùng nội dung: gộp khoảng trắng, không phân biệt hoa/thường."""
    return " ".join((text or "").split()).casefold()


def validate_questions(rows: list[dict], testset_questions=()) -> tuple[list[dict], dict]:
    """Kiểm schema + loại trùng + gắn cờ rò rỉ với testset.

    * BẮT BUỘC `id`, `question`, cột người chấm `co_giup_duoc_khong` (được để trống giá trị);
    * trùng `id` hoặc trùng nội dung câu (sau chuẩn hóa) => LOẠI dòng đến sau, ghi lý do;
    * câu giống hệt một câu trong `testset_v1` => GIỮ nhưng gắn `leak_testset_v1=True`
      (không tự xóa: người dùng cần biết mình đã dán câu từ benchmark vào).
    """
    accepted: list[dict] = []
    dropped: list[dict] = []
    flagged: list[str] = []
    seen_ids: set[str] = set()
    seen_questions: dict[str, str] = {}
    testset_norm = {_norm_question(q) for q in testset_questions if (q or "").strip()}

    for index, row in enumerate(rows):
        rid = str(row.get("id") or "").strip()
        question = str(row.get("question") or "").strip()
        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if not rid:
            missing.append("id(trống)")
        if not question:
            missing.append("question(trống)")
        if missing:
            dropped.append({"row_index": index, "id": rid, "reason": "thiếu_trường:" + ",".join(missing)})
            continue
        if rid in seen_ids:
            dropped.append({"row_index": index, "id": rid, "reason": "trùng_id"})
            continue
        norm = _norm_question(question)
        if norm in seen_questions:
            dropped.append(
                {"row_index": index, "id": rid, "reason": f"trùng_nội_dung_với:{seen_questions[norm]}"}
            )
            continue
        seen_ids.add(rid)
        seen_questions[norm] = rid
        out = dict(row)
        out["leak_testset_v1"] = norm in testset_norm
        accepted.append(out)
        if out["leak_testset_v1"]:
            flagged.append(rid)

    report = {
        "n_in": len(rows),
        "n_accepted": len(accepted),
        "n_dropped": len(dropped),
        "dropped": dropped,
        "flagged_leak_testset_v1": flagged,
    }
    return accepted, report


def load_testset_questions(path: Path = TESTSET_PATH) -> list[str]:
    if not path.exists():
        return []
    return [str(row.get("raw_query") or "") for row in read_jsonl(path)]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            if "_schema" in obj or "_cot_can_dien_tay" in obj:
                continue  # dòng mô tả schema, không phải câu hỏi
            rows.append(obj)
    return rows


def real_questions(rows: list[dict], include_examples: bool) -> list[dict]:
    out = []
    for r in rows:
        q = (r.get("question") or "").strip()
        if not q:
            continue
        if r.get("example") and not include_examples:
            continue
        out.append(r)
    return out


def score_one(pipeline, row: dict, top_k: int) -> dict:
    """Chạy pipeline thật một câu, chấm grounding + phát hiện từ chối."""
    from src.answer_guard import check_grounding
    from tools.loop.verify import is_refusal

    q = row["question"].strip()
    t0 = time.time()
    res = pipeline.run(q, top_k=top_k)
    latency = round(time.time() - t0, 2)
    answer = res.get("answer") or ""
    contexts = [c if isinstance(c, str) else str(c) for c in (res.get("contexts") or [])]
    sources = res.get("sources") or []
    src_names = [str(s.get("source") or "") for s in sources if isinstance(s, dict)]
    report = check_grounding(answer, contexts, q, extra_haystack=src_names)
    return {
        "id": row.get("id"),
        "question": q,
        "nguon": row.get("nguon", ""),
        "chu_de": row.get("chu_de", ""),
        "answer": answer,
        "is_refusal": is_refusal(answer),
        "grounding_score": report.grounding_score,
        "entities_total": report.entities_total,
        "n_supported": len(report.supported),
        "n_unsupported": len(report.unsupported),
        "unsupported": [e.text for e in report.unsupported][:10],
        "n_contexts": len(contexts),
        "latency_seconds": latency,
        # cột cho người đọc — GIỮ giá trị cũ nếu đã điền, không xoá công người label.
        "co_giup_duoc_khong": row.get("co_giup_duoc_khong", ""),
        "ghi_chu": row.get("ghi_chu", ""),
    }


def help_rate_ci(scores: list[float], seed: int = 20261024, reps: int = 10000) -> dict:
    """Bootstrap CI cho trung bình 'có giúp được' (co=1, mot_phan=0.5, khong=0)."""
    import random

    if not scores:
        return {"n": 0}
    rng = random.Random(seed)
    means: list[float] = []
    n = len(scores)
    for _ in range(reps):
        sample = [scores[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    last = len(means) - 1
    pos = lambda qq: means[min(last, max(0, int(qq * len(means))))]  # noqa: E731
    return {
        "n": n,
        "mean": round(sum(scores) / n, 4),
        "ci95": [round(pos(0.025), 4), round(pos(0.975), 4)],
        "note": "CI RỘNG do n nhỏ; đọc là bằng chứng ĐỊNH TÍNH, không phải tỉ lệ chính xác hệ thống.",
    }


def summarize(scored: list[dict]) -> dict:
    filled = [HELP_SCORE[s["co_giup_duoc_khong"]] for s in scored if s.get("co_giup_duoc_khong") in HELP_SCORE]
    refusals = sum(1 for s in scored if s["is_refusal"])
    grounded = [s["grounding_score"] for s in scored if s["grounding_score"] is not None]
    return {
        "n_scored": len(scored),
        "n_human_labeled": len(filled),
        "help_rating": help_rate_ci(filled) if filled else {"n": 0, "note": "chưa có nhãn tay — điền cột co_giup_duoc_khong"},
        "refusals": refusals,
        "refusal_rate": round(refusals / len(scored), 4) if scored else None,
        "mean_grounding_score": round(sum(grounded) / len(grounded), 4) if grounded else None,
        "n_fabricated_any": sum(1 for s in scored if s["n_unsupported"] > 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_path", default=str(IN_PATH))
    ap.add_argument("--out", dest="out_path", default=str(OUT_PATH))
    ap.add_argument("--limit", type=int, default=0, help="chỉ chấm N câu đầu (0 = tất cả câu thật)")
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--generator", default="ollama", help="ollama | gemini (khai rõ trước khi tốn quota)")
    ap.add_argument("--include-examples", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="chỉ đếm số câu thật + số lượt gọi, KHÔNG chạy model")
    ap.add_argument("--testset", default=str(TESTSET_PATH), help="testset_v1 để kiểm rò rỉ câu hỏi")
    args = ap.parse_args()

    rows_all = read_jsonl(Path(args.in_path))
    rows, validation = validate_questions(rows_all, load_testset_questions(Path(args.testset)))
    todo = real_questions(rows, args.include_examples)
    if args.limit:
        todo = todo[: args.limit]

    print(f"[T6c] schema: nhận {validation['n_accepted']}/{validation['n_in']} dòng, "
          f"loại {validation['n_dropped']}, gắn cờ rò rỉ {len(validation['flagged_leak_testset_v1'])}.")
    for item in validation["dropped"]:
        print(f"  [LOẠI] dòng {item['row_index']} id={item['id'] or '(trống)'} — {item['reason']}")
    if validation["flagged_leak_testset_v1"]:
        print(f"  [CỜ RÒ RỈ] câu trùng testset_v1: {', '.join(validation['flagged_leak_testset_v1'])}")
    print(f"[T6c] câu thật chờ chấm = {len(todo)} (đã loại dòng ví dụ/trống). "
          f"Số lượt pipeline dự kiến = {len(todo)} (generator={args.generator}).")
    if args.dry_run:
        print("[T6c] DRY-RUN: không gọi model. Điền câu thật vào real_questions.jsonl rồi chạy lại.")
        return
    if not todo:
        print("[T6c] Chưa có câu thật nào. Đây mới là KHUNG — cần >=30 câu từ sinh viên.")
        return

    from tools.loop.run_round import build_pipeline

    pipeline = build_pipeline(args.generator)
    scored = [score_one(pipeline, r, args.top_k) for r in todo]
    summary = summarize(scored)

    out_path = Path(args.out_path)
    out_path.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in scored) + "\n", encoding="utf-8")
    (EVAL_DIR / "real_questions_summary.json").write_text(
        json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "summary": summary},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("[T6c] ---- TÓM TẮT (định tính, n nhỏ) ----")
    print(f"  câu đã chấm        : {summary['n_scored']}")
    print(f"  nhãn tay đã điền   : {summary['n_human_labeled']}")
    print(f"  từ chối            : {summary['refusals']} ({summary['refusal_rate']})")
    print(f"  mean grounding     : {summary['mean_grounding_score']}")
    print(f"  có khẳng định bịa   : {summary['n_fabricated_any']}")
    print(f"  đánh giá 'giúp được': {summary['help_rating']}")
    print(f"[T6c] ghi: {out_path}")
    print("[T6c] NHẮC: điền cột `co_giup_duoc_khong` vào file scored rồi chạy lại để có CI 'giúp được'.")


if __name__ == "__main__":
    main()
