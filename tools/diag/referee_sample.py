# -*- coding: utf-8 -*-
"""T6b — trích mẫu phân tầng để KIỂM ĐỊNH TRỌNG TÀI bằng nhãn tay.

Trọng tài (`tools/loop/verify.py`) tự động gắn verdict cho mỗi câu trả lời. Trước khi
dám kết luận "hệ thống đạt / không đạt" dựa trên verdict của nó, phải chứng minh bản
thân trọng tài đáng tin: nó phán đúng bao nhiêu phần trăm so với người đọc thật.

Script này lấy một mẫu PHÂN TẦM theo verdict của trọng tài — nhưng khi xuất ra file gán
nhãn thì ĂN hết mọi dấu vết của verdict và mọi trường vàng của testset
(`gold_chunk_id`, `gold_sentence`, `required_entities`, `grounding_score`, `severity`,
`is_refusal`, `detail`). Người đọc CHỈ thấy: câu hỏi, bằng chứng đã đưa cho model, và
câu trả lời model sinh ra. Nhờ vậy nhãn tay là phán quyết ĐỘC LẬP, không bị neo.

Bốn lớp ánh xạ verdict -> nhãn cho người đọc (mỗi verdict text của trọng tài rơi vào
đúng một lớp; `FAIL_RETRIEVAL` xếp vào "sai" vì từ phía người học, đáp án thiếu căn cứ
vẫn là đáp án không dùng được):

    dung         <- PASS_CORRECT, PASS_CORRECTED_TRAP
    tu_boi_dung  <- PASS_REFUSAL
    tu_boi_oan   <- FAIL_OVERREFUSAL
    sai          <- FAIL_FABRICATED, FAIL_CONFIRMED_FALSE_PREMISE,
                    FAIL_HALLUCINATED_ON_UNANSWERABLE, FAIL_INCOMPLETE, FAIL_RETRIEVAL

Ba file sinh ra (KHÔNG đè round đã đóng; chỉ ghi vào data/loop/diag):
    referee_labeling_<round>.jsonl   — phiếu gán nhãn máy đọc (có trường `nhan_tay` trống)
    referee_labeling_<round>.md      — phiếu con người đọc (bảng để điền tay)
    referee_sample_manifest.json     — ĐARES FOR SCORING: id -> verdict trọng tài + tầng.
                                       Người gán nhãn KHÔNG cần mở file này.

Dùng:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/referee_sample.py --round r5
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ROUNDS = ROOT / "data" / "loop" / "rounds"
DIAG = ROOT / "data" / "loop" / "diag"

# verdict -> lớp ánh xạ cho người đọc.
VERDICT_TO_STRATUM = {
    "PASS_CORRECT": "dung",
    "PASS_CORRECTED_TRAP": "dung",
    "PASS_REFUSAL": "tu_boi_dung",
    "FAIL_OVERREFUSAL": "tu_boi_oan",
    "FAIL_FABRICATED": "sai",
    "FAIL_CONFIRMED_FALSE_PREMISE": "sai",
    "FAIL_HALLUCINATED_ON_UNANSWERABLE": "sai",
    "FAIL_INCOMPLETE": "sai",
    "FAIL_RETRIEVAL": "sai",
}

STRATA = ("dung", "tu_boi_dung", "tu_boi_oan", "sai")

# Hướng dẫn ngắn cho người đọc; in ở đầu cả .md và .jsonl "_huong_dan".
HUONG_DAN = (
    "Đọc CẨN THẬN câu hỏi + bằng chứng + câu trả lời rồi chọn MỘT nhãn:\n"
    "  dung        = đáp án ĐÚNG và có căn cứ trong phần bằng chứng bên dưới\n"
    "  sai         = đáp án SAI, BỊA, hoặc KHÔNG có căn cứ trong bằng chứng\n"
    "  tu_boi_dung = model từ chối và việc từ chối là ĐÚNG (bằng chứng không đủ/trả lời được)\n"
    "  tu_boi_oan  = model từ chối nhưng ĐÁNG RA đã trả lời được (bằng chứng CÓ đủ)\n"
    "  khong_ro    = không đủ thông tin để phán (hiếm; dùng thận trọng)\n"
    "Không suy đoán kết luận của hệ thống. Chỉ dựa vào 3 mục: hỏi gì, bằng chứng gì, trả lời gì."
)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def pick_verdicts_path(round_dir: Path) -> Path:
    for phase in ("full", "retrieval"):
        p = round_dir / f"verdicts_{phase}.jsonl"
        if p.exists():
            return p
    raise SystemExit(f"Không tìm thấy verdicts_*.jsonl trong {round_dir}")


def load_records(round_name: str) -> list[dict]:
    """Hợp nhất full.jsonl (answer/contexts/raw_query) với verdict (chỉ để chọn tầng).

    Trả về bản ghi CHỈ chứa trường hiển thị cho người + verdict trọng tài (để lưu ở
    manifest riêng). Không chứa bất kỳ trường vàng nào của testset.
    """
    rdir = ROUNDS / round_name
    full = {r["id"]: r for r in read_jsonl(rdir / "full.jsonl")}
    verdicts = {}
    for v in read_jsonl(pick_verdicts_path(rdir)):
        verdicts[v["id"]] = v["verdict"]

    records = []
    for rid, vtext in verdicts.items():
        row = full.get(rid)
        if row is None:
            continue
        stratum = VERDICT_TO_STRATUM.get(vtext)
        if stratum is None:
            continue  # verdict không nằm trong ánh xạ -> bỏ, ghi cảnh báo
        item = row.get("item", {})
        contexts = [c if isinstance(c, str) else str(c) for c in (row.get("contexts") or [])]
        records.append(
            {
                "id": rid,
                "stratum": stratum,
                "referee_verdict": vtext,
                "question": (item.get("raw_query") or row.get("normalized_query") or "").strip(),
                "answer": (row.get("answer") or "").strip(),
                "evidence": contexts[:6],
                "error": row.get("error"),
            }
        )
    return records


def stratified_sample(records: list[dict], targets: dict[str, int], seed: int) -> list[dict]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict]] = {s: [] for s in STRATA}
    for r in records:
        buckets[r["stratum"]].append(r)
    for s in STRATA:
        rng.shuffle(buckets[s])

    chosen: list[dict] = []
    leftover_pools: dict[str, list[dict]] = {s: list(buckets[s]) for s in STRATA}
    # 1) lấy theo target từng tầng (không quá số khả dụng).
    for s in STRATA:
        take = min(targets.get(s, 0), len(leftover_pools[s]))
        for _ in range(take):
            chosen.append(leftover_pools[s].pop())

    # 2) nếu chưa đủ tổng (target nhỏ hơn khả dụng ở tầng khan hiếm), bù từ tầng dư nhiều nhất.
    want = sum(targets.values())
    while len(chosen) < want:
        cand = [s for s in STRATA if leftover_pools[s]]
        if not cand:
            break
        cand.sort(key=lambda s: len(leftover_pools[s]), reverse=True)
        chosen.append(leftover_pools[cand[0]].pop())

    # 3) xáo toàn bộ để người đọc không suy ra tầng từ thứ tự.
    rng.shuffle(chosen)
    for i, r in enumerate(chosen, start=1):
        r["sample_index"] = i
    return chosen


def default_targets(n: int) -> dict[str, int]:
    """Phân bổ mặc định cho bộ 4 tầng, tổng = n."""
    dung = round(n * 0.24)
    tbd = round(n * 0.25)
    toa = round(n * 0.25)
    sai = n - dung - tbd - toa
    return {"dung": dung, "tu_boi_dung": tbd, "tu_boi_oan": toa, "sai": sai}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …[cắt]"


def write_markdown(path: Path, chosen: list[dict], round_name: str, ctx_clip: int, answer_clip: int) -> None:
    lines = [
        f"# Phiếu gán nhãn kiểm định trọng tài ({len(chosen)} mẫu)",
        "",
        f"Round nguồn: `{round_name}` — sinh lúc {datetime.now().isoformat(timespec='seconds')}.",
        "",
        HUONG_DAN,
        "",
        "> Kết quả của hệ thống (verdict) đã bị ẨN khỏi phiếu này. Điền `nhan_tay` vào ô",
        "> `___` ở mỗi mục (một trong: dung / sai / tu_boi_dung / tu_boi_oan / khong_ro).",
        "",
        "---",
        "",
    ]
    for r in chosen:
        lines.append(f"## Mẫu {r['sample_index']}")
        lines.append("")
        lines.append(f"**Câu hỏi:** {r['question'] or '(trống)'}")
        lines.append("")
        ans = r["answer"] or ""
        if not ans:
            lines.append("**Câu trả lời của hệ thống:** (không có văn bản — có thể là từ chối/lỗi)")
            if r.get("error"):
                lines.append(f"_Ghi chú lỗi: {clip(str(r['error']), 200)}_")
        else:
            lines.append("**Câu trả lời của hệ thống:**")
            lines.append("")
            lines.append("```")
            lines.append(clip(ans, answer_clip))
            lines.append("```")
        lines.append("")
        lines.append("**Bằng chứng đã đưa cho hệ thống:**")
        lines.append("")
        if not r["evidence"]:
            lines.append("_(không có bằng chứng)_")
        for i, c in enumerate(r["evidence"], 1):
            lines.append(f"{i}. {clip(c, ctx_clip)}")
        lines.append("")
        lines.append("`nhan_tay: ___    ghi_chu: ___`")
        lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--round", default="r5")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20261024)
    ap.add_argument("--ctx-clip", type=int, default=1400, help="số ký tự tối đa mỗi đoạn bằng chứng trong .md")
    ap.add_argument("--answer-clip", type=int, default=1200)
    ap.add_argument(
        "--targets",
        default="",
        help='JSON overrides, vd \'{"dung":14,"tu_boi_dung":15,"tu_boi_oan":15,"sai":16}\'',
    )
    args = ap.parse_args()

    targets = json.loads(args.targets) if args.targets else default_targets(args.n)

    records = load_records(args.round)
    available = {s: sum(1 for r in records if r["stratum"] == s) for s in STRATA}
    chosen = stratified_sample(records, targets, args.seed)

    DIAG.mkdir(parents=True, exist_ok=True)

    # PHIẾU GÁN NHÃN (ẩn verdict): chỉ trường hiển thị + nhan_tay trống.
    label_rows = []
    for r in chosen:
        label_rows.append(
            {
                "_huong_dan": HUONG_DAN,
                "sample_index": r["sample_index"],
                "id": r["id"],
                "question": r["question"],
                "answer": r["answer"],
                "evidence": r["evidence"],
                "nhan_tay": "",
                "ghi_chu": "",
            }
        )
    jsonl_path = DIAG / f"referee_labeling_{args.round}.jsonl"
    write_jsonl(jsonl_path, label_rows)

    md_path = DIAG / f"referee_labeling_{args.round}.md"
    write_markdown(md_path, chosen, args.round, args.ctx_clip, args.answer_clip)

    # MANIFEST cho scoring (giữ verdict + tầng; người gán nhãn không cần đọc).
    manifest = {
        "round": args.round,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "targets": targets,
        "available_by_stratum": available,
        "n_selected": len(chosen),
        "selected_by_stratum": {s: sum(1 for r in chosen if r["stratum"] == s) for s in STRATA},
        "samples": [
            {
                "sample_index": r["sample_index"],
                "id": r["id"],
                "stratum": r["stratum"],
                "referee_verdict": r["referee_verdict"],
            }
            for r in chosen
        ],
    }
    manifest_path = DIAG / "referee_sample_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[T6b] round={args.round} khã_dung={available}")
    print(f"[T6b] chon={len(chosen)} theo={manifest['selected_by_stratum']}")
    print(f"[T6b] phieu: {jsonl_path}")
    print(f"[T6b] md   : {md_path}")
    print(f"[T6b] key  : {manifest_path}")


if __name__ == "__main__":
    main()
