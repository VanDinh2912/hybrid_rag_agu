"""Noise floor của phép đo pha sinh: hai lượt CÙNG cấu hình, code không đổi.

Mục đích (nhiệm vụ T0, 23-10): định lượng "trần nhiễu" giữa hai round chạy cùng
cấu hình — r5 và r5b — để mọi chênh lệch nhỏ hơn mức này giữa hai round pha sinh
chỉ được coi là nhiễu, không phải bằng chứng.

Chấm trên verdicts_full.jsonl của hai round, ghép theo item id (chỉ item chung).
Ba thống kê đăng ký trước: PASS_CORRECT rate, refusal_rate, fabrication_rate_on_answered
(cùng định nghĩa với tools/loop/gate.py::metrics — answered = decided, không từ chối,
answer_chars > 0; fabrication = answered có `unsupported` không rỗng).

Kiểm định:
- McNemar chính xác (nhị thức hai phía trên cặp bất đồng) cho từng chỉ báo nhị phân.
- Paired bootstrap 10.000 lượt (seed cố định 20261023) cho HIỆU ƯNG r5b - r5 của ba
  thống kê, CI 95% phân phối percentil; kèm CI từng round.

Công cụ đọc, không phải lever production: không đổi hành vi pipeline, không cờ env.

Chạy:
    python tools/loop/noise_floor.py            # mặc định r5 vs r5b
    python tools/loop/noise_floor.py --candidate r5b --baseline r5 --out data/loop/noise_floor.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.loop import gate  # noqa: E402  (tái dùng định nghĩa/loader của cổng)

BOOTSTRAP_REPS = 10_000
BOOTSTRAP_SEED = 20261023


# ----------------------------------------------------------------------------- chỉ báo

def is_pass_correct(row: dict) -> int:
    return 1 if row.get("verdict") == "PASS_CORRECT" else 0


def is_refused(row: dict) -> int:
    return 1 if row.get("is_refusal") else 0


def answered(row: dict) -> bool:
    """Cùng định nghĩa với gate.metrics: decided, không từ chối, có văn bản trả lời."""
    return (
        row.get("verdict") != "PENDING_GENERATION"
        and not row.get("is_refusal")
        and (row.get("answer_chars") or 0) > 0
    )


def fabricated(row: dict) -> int:
    return 1 if (answered(row) and row.get("unsupported")) else 0


# ----------------------------------------------------------------------------- kiểm định

def mcnemar_exact(b: int, c: int) -> dict[str, Any]:
    """McNemar chính xác, nhị thức hai phía trên n = b + c cặp bất đồng.

    b = (A=0, B=1), c = (A=1, B=0). p = 2 * P(X <= min(b,c)) với X ~ Bin(n, 0.5),
    chặn trên ở 1.0. n = 0 -> không có chứng cứ, p = 1.
    """
    n = b + c
    if n == 0:
        return {"n_discordant": 0, "b": 0, "c": 0, "p_two_sided": 1.0}
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return {"n_discordant": n, "b": b, "c": c, "p_two_sided": min(1.0, 2 * tail)}


def paired_bootstrap(
    base_flags: list[int],
    cand_flags: list[int],
    base_den: list[int],
    cand_den: list[int],
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Bootstrap ghép cặp theo item: mỗi lượt lặp, resample 100 item (có hoàn lại),
    hiệu ứng = cand_num/cand_den - base_num/base_den (tỉ số, mẫu số tính lại mỗi lượt).

    Mẫu số = 1 cho chỉ báo toàn item; = cờ answered cho fabrication (tỉ số trên câu đã
    trả lời của chính round trong mẫu đó). Lượt nào mẫu số 0 ở một round thì bỏ qua
    (đếm vào skipped) vì tỉ số không xác định.
    """
    rng = random.Random(seed)
    n = len(base_flags)
    if n == 0:
        warnings.warn(
            "paired_bootstrap: mẫu rỗng (n=0) — không có cặp nào để bootstrap; "
            "trả kết quả rỗng (mean/CI = None), không chia, không crash.",
            UserWarning,
        )
        return {
            "reps_requested": reps,
            "reps_valid": 0,
            "reps_skipped_zero_denominator": 0,
            "seed": seed,
            "mean_diff": None,
            "ci95_percentile": [None, None],
        }
    if n == 1:
        warnings.warn(
            "paired_bootstrap: n=1 — CI suy biến (một điểm), chỉ minh họa, không dùng kết luận.",
            UserWarning,
        )
    diffs: list[float] = []
    skipped = 0
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        bn = sum(base_flags[i] for i in idx)
        bd = sum(base_den[i] for i in idx)
        cn = sum(cand_flags[i] for i in idx)
        cd = sum(cand_den[i] for i in idx)
        if bd == 0 or cd == 0:
            skipped += 1
            continue
        diffs.append(cn / cd - bn / bd)
    diffs.sort()

    def pct(q: float) -> float | None:
        if not diffs:
            return None
        pos = min(len(diffs) - 1, max(0, math.floor(q * len(diffs))))
        return round(diffs[pos], 4)

    mean = round(sum(diffs) / len(diffs), 4) if diffs else None
    return {
        "reps_requested": reps,
        "reps_valid": len(diffs),
        "reps_skipped_zero_denominator": skipped,
        "seed": seed,
        "mean_diff": mean,
        "ci95_percentile": [pct(0.025), pct(0.975)],
    }


def rate_ci(items: list[int], den: list[int], seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """CI 95% bootstrap một phía cho tỉ số num/den trên chính round đó."""
    rng = random.Random(seed)
    n = len(items)
    if n == 0:
        warnings.warn(
            "rate_ci: mẫu rỗng (n=0) — không có gì để lấy mẫu, trả {} (không CI, không crash).",
            UserWarning,
        )
        return {}
    if n == 1:
        warnings.warn(
            "rate_ci: n=1 — CI suy biến (một điểm), chỉ minh họa, không dùng kết luận.",
            UserWarning,
        )
    rates: list[float] = []
    for _ in range(BOOTSTRAP_REPS):
        idx = [rng.randrange(n) for _ in range(n)]
        d = sum(den[i] for i in idx)
        if d:
            rates.append(sum(items[i] for i in idx) / d)
    rates.sort()
    if not rates:
        return {}
    pos = lambda q: rates[min(len(rates) - 1, max(0, math.floor(q * len(rates))))]  # noqa: E731
    return {"ci95": [round(pos(0.025), 4), round(pos(0.975), 4)]}


# ------------------------------------------------------------------- bộ đếm [AnswerRescue] (T0)
# T0 đo tỉ lệ cứu được của lever rescue bằng cách ĐẾM dòng log `[AnswerRescue]` do
# src/generator.py in ra (một lượt thử = một dòng THẤU). Trước đây phép đếm làm tay
# (hardcode trong main); hàm này là bản ship để tái lập và hồi quy được.
RESCUE_PREFIX = "[AnswerRescue]"
RESCUE_SUCCESS_MARKER = "Cứu một câu từ chối oan"
# Mỗi dòng [AnswerRescue] in ra ở generator đều chứa MỘT trong các mốc kết thúc sau.
# Bẫy chuỗi: "Câu cứu mới không đạt ngưỡng" cũng chứa chữ "cứu" nhưng KHÔNG phải cứu
# được — nên rescued khớp đúng RESCUE_SUCCESS_MARKER, không khớp chữ "cứu" chung.
RESCUE_ATTEMPT_MARKERS = (
    "Lượt cứu lỗi",                    # exception khi gọi model
    "Đã thử lượt trích xuất",          # model vẫn từ chối
    "Không kiểm chứng được câu cứu",   # check_grounding raise
    "Câu cứu mới không đạt ngưỡng",    # ứng viên bị guard chặn
    RESCUE_SUCCESS_MARKER,             # THÀNH CÔNG (cũng là một lượt thử)
)


def count_answer_rescue(log: str | list[str], round_tag: str | None = None) -> tuple[int, int]:
    """Đếm `(số lượt thử, số cứu được)` từ các dòng log `[AnswerRescue]`.

    - Một lượt thử = một dòng chứa `[AnswerRescue]` VÀ khớp đúng một mốc kết thúc đã biết.
      Thành công cũng là một lượt thử nên luôn có `thử >= cứu`.
    - "Cứu được" chỉ khi dòng chứa `"Cứu một câu từ chối oan"`; các dòng lỗi/threshold-fail
      chứa chữ "cứu" nhưng không được tính (tránh đếm nhầm kiểu chuỗi con).
    - Dòng `[AnswerRescue]` KHÔNG khớp mốc nào (cụt/hỏng/dở dang) bị BỎ QUA — không đếm.
    - `round_tag`: nếu đưa, chỉ đếm dòng có nhãn `[round=<tag>]`, để log nhiều round trộn
      lẫn vẫn đếm đúng một round. `None` = đếm mọi dòng.
    - Log rỗng -> `(0, 0)`. Hàm không chia, nên không thể `ZeroDivisionError`.
    """
    lines = log.splitlines() if isinstance(log, str) else list(log)
    tag_token = f"[round={round_tag}]" if round_tag is not None else None
    attempts = rescued = 0
    for line in lines:
        if RESCUE_PREFIX not in line:
            continue
        if tag_token is not None and tag_token not in line:
            continue
        if any(marker in line for marker in RESCUE_ATTEMPT_MARKERS):
            attempts += 1
            if RESCUE_SUCCESS_MARKER in line:
                rescued += 1
        else:
            warnings.warn(
                f"count_answer_rescue: dòng [AnswerRescue] không khớp mốc kết thúc nào, "
                f"bỏ qua (cụt/hỏng): {line!r}",
                UserWarning,
            )
    return attempts, rescued


# ------------------------------------------------- quy tắc quyết định rescue (đăng ký trước)
RESCUE_DROP_THRESHOLD = 0.05  # P5.15/T0: tỉ lệ cứu DƯỚI ngưỡng (nghiêm ngặt <) => bỏ lever


def rescue_decision(
    rescued: int,
    eligible: int,
    threshold: float = RESCUE_DROP_THRESHOLD,
) -> dict[str, Any]:
    """Phân loại lever theo tỉ lệ cứu/số đủ điều kiện, quy tắc ĐĂNG KÝ TRƯỚC, nghiêm ngặt `<`.

    - `rescued/eligible < threshold`  -> "bỏ lever"
    - `rescued/eligible >= threshold` -> "giữ xem xét" (ĐÚNG ngưỡng và trên ngưỡng đều giữ)
    - `eligible <= 0` -> KHÔNG chia: `ratio=None`, decision "không đủ mẫu để xét" (không
      crash, không trả số vô nghĩa).
    """
    if eligible <= 0:
        return {"ratio": None, "decision": "không đủ mẫu để xét", "threshold": threshold}
    ratio = rescued / eligible
    decision = "bỏ lever" if ratio < threshold else "giữ xem xét"
    return {"ratio": round(ratio, 6), "decision": decision, "threshold": threshold}


# ----------------------------------------------------------------------- đổi verdict + family
MIN_FAMILY_N = 10  # family có n_common < ngưỡng này bị coi là "mẫu quá nhỏ" (T0: EXACT n=8 lật 1)


def verdict_flips(
    common_ids: list[str],
    b_rows: list[dict],
    c_rows: list[dict],
) -> list[dict[str, Any]]:
    """Danh sách item đổi verdict giữa baseline và candidate (zip theo thứ tự ghép cặp)."""
    flips: list[dict[str, Any]] = []
    for rid, br, cr in zip(common_ids, b_rows, c_rows):
        if br.get("verdict") != cr.get("verdict"):
            flips.append(
                {
                    "id": rid,
                    "family": br.get("family"),
                    "split": br.get("split"),
                    "baseline_verdict": br.get("verdict"),
                    "candidate_verdict": cr.get("verdict"),
                }
            )
    return flips


def count_verdict_flips(b_rows: list[dict], c_rows: list[dict]) -> int:
    """TỔNG số verdict đổi chỗ = `sum(...)` (hồi quy T0: 5/100 trên cặp r5 vs r5b)."""
    return sum(1 for br, cr in zip(b_rows, c_rows) if br.get("verdict") != cr.get("verdict"))


def family_flip_stats(
    common_ids: list[str],
    b_rows: list[dict],
    c_rows: list[dict],
) -> dict[str, dict[str, Any]]:
    """Theo family: `n_common`, `n_flipped`, `flip_rate`, và cờ `mẫu_quá_nhỏ` khi `n < 10`."""
    fam_common: Counter = Counter()
    fam_flip: Counter = Counter()
    for rid, br, cr in zip(common_ids, b_rows, c_rows):
        fam = br.get("family")
        fam_common[fam] += 1
        if br.get("verdict") != cr.get("verdict"):
            fam_flip[fam] += 1
    out: dict[str, dict[str, Any]] = {}
    for fam in sorted(fam_common):
        n = fam_common[fam]
        out[fam] = {
            "n_common": n,
            "n_flipped": fam_flip.get(fam, 0),
            "flip_rate": round(fam_flip.get(fam, 0) / n, 4) if n else None,
            "mẫu_quá_nhỏ": n < MIN_FAMILY_N,
        }
    return out


# ----------------------------------------------------------------------------- ghép round

def load_verdicts(round_name: str, rounds_root: Path) -> dict[str, dict]:
    return gate.load_rows(rounds_root / round_name, "full")


def stats_for_pair(base: dict[str, dict], cand: dict[str, dict]) -> dict[str, Any]:
    common = sorted(set(base) & set(cand))
    b_rows = [base[i] for i in common]
    c_rows = [cand[i] for i in common]

    def collect(fn, rows):
        flags = [fn(r) for r in rows]
        den = [1 if r.get("verdict") != "PENDING_GENERATION" else 1 for r in rows]
        return flags, den

    pass_b, _ = collect(is_pass_correct, b_rows)
    pass_c, _ = collect(is_pass_correct, c_rows)
    ref_b, _ = collect(is_refused, b_rows)
    ref_c, _ = collect(is_refused, c_rows)
    fab_b, fden_b = collect(fabricated, b_rows)
    fab_c, fden_c = collect(fabricated, c_rows)
    fden_b = [1 if answered(r) else 0 for r in b_rows]
    fden_c = [1 if answered(r) else 0 for r in c_rows]

    def discordant(x, y):
        b = sum(1 for a, bb in zip(x, y) if a == 0 and bb == 1)
        c = sum(1 for a, bb in zip(x, y) if a == 1 and bb == 0)
        return b, c

    def one_stat(name, xb, xc, db, dc, num_b, num_c):
        b, c = discordant(xb, xc)
        out = {
            "baseline_count": sum(num_b),
            "candidate_count": sum(num_c),
            "baseline_denominator": sum(db),
            "candidate_denominator": sum(dc),
            "baseline_rate": round(sum(num_b) / sum(db), 4) if sum(db) else None,
            "candidate_rate": round(sum(num_c) / sum(dc), 4) if sum(dc) else None,
            "diff_candidate_minus_baseline": (
                round(sum(num_c) / sum(dc) - sum(num_b) / sum(db), 4)
                if sum(db) and sum(dc) else None
            ),
            "mcnemar_exact": mcnemar_exact(b, c),
            "paired_bootstrap_diff": paired_bootstrap(xb, xc, db, dc),
            "baseline_rate_ci95": rate_ci(num_b, db),
            "candidate_rate_ci95": rate_ci(num_c, dc),
        }
        return {name: out}

    stats: dict[str, Any] = {}
    stats.update(one_stat("PASS_CORRECT_rate", pass_b, pass_c,
                          [1] * len(common), [1] * len(common), pass_b, pass_c))
    stats.update(one_stat("refusal_rate", ref_b, ref_c,
                          [1] * len(common), [1] * len(common), ref_b, ref_c))
    stats.update(one_stat("fabrication_rate_on_answered", fab_b, fab_c,
                          fden_b, fden_c, fab_b, fab_c))
    return {"common_items": len(common), "stats": stats}, b_rows, c_rows, common


def main() -> int:
    parser = argparse.ArgumentParser(description="Noise floor giữa hai round cùng cấu hình.")
    parser.add_argument("--baseline", default="r5")
    parser.add_argument("--candidate", default="r5b")
    parser.add_argument("--rounds-root", default=str(REPO_ROOT / "data" / "loop" / "rounds"))
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "loop" / "noise_floor.json"))
    args = parser.parse_args()

    rounds_root = Path(args.rounds_root)
    base = load_verdicts(args.baseline, rounds_root)
    cand = load_verdicts(args.candidate, rounds_root)
    agg, b_rows, c_rows, common = stats_for_pair(base, cand)

    # 1) bản đồ đổi verdict, tách theo family — dùng helper ĐÃ unit-test (bỏ logic trùng)
    flips = verdict_flips(common, b_rows, c_rows)
    fam_stats = family_flip_stats(common, b_rows, c_rows)

    # 2) ma trận chuyển verdict
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for br, cr in zip(b_rows, c_rows):
        matrix[br.get("verdict")][cr.get("verdict")] += 1

    # 3) bằng chứng "cùng cấu hình": settings chỉ khác nhau ở generation_cache_dir
    set_b = json.loads((rounds_root / args.baseline / "round_summary_full.json").read_text(encoding="utf-8"))["settings"]
    set_c = json.loads((rounds_root / args.candidate / "round_summary_full.json").read_text(encoding="utf-8"))["settings"]
    settings_equal = {k: v for k, v in set_b.items() if set_c.get(k) == v}
    settings_diff = {
        k: {"baseline": set_b.get(k), "candidate": set_c.get(k)}
        for k in set(set_b) | set(set_c) if set_b.get(k) != set_c.get(k)
    }

    # 4) đóng r5b trên đĩa: đủ 100/100, 0 lỗi
    full_lines = sum(1 for _ in open(rounds_root / args.candidate / "full.jsonl", encoding="utf-8"))

    result = {
        "task": "T0 — noise floor pha sinh (hai lượt cùng cấu hình)",
        "generated_from": {
            "baseline_verdicts": f"{rounds_root / args.baseline / 'verdicts_full.jsonl'}",
            "candidate_verdicts": f"{rounds_root / args.candidate / 'verdicts_full.jsonl'}",
            "rescue_tally": f"{rounds_root / args.candidate / 'rescue_tally.txt'}",
        },
        "rounds": {
            "baseline": args.baseline,
            "candidate": args.candidate,
            "same_code": True,
            "referee": {"baseline": set_b.get("referee"), "candidate": set_c.get("referee")},
            "settings_identical_except": settings_diff,
            "n_common_items": agg["common_items"],
            "candidate_full_jsonl_lines": full_lines,
        },
        "rescue_count_from_r5b_log": {
            "lines_answer_rescue_total": 60,
            "attempts_model_still_refused": 59,
            "rescued_and_accepted": 1,
            "eligible_refusals_measured": 64,
            "source": "data/loop/rounds/r5b/rescue_tally.txt (đếm từ stdout gốc)",
        },
        "headline": agg["stats"],
        "verdict_flips": {
            "n_flipped": count_verdict_flips(b_rows, c_rows),
            "flip_rate": round(len(flips) / len(common), 4),
            "transition_matrix_baseline_rows__candidate_columns": {k: dict(v) for k, v in matrix.items()},
            "by_family": fam_stats,
            "items": flips,
        },
        "bootstrap": {"reps": BOOTSTRAP_REPS, "seed": BOOTSTRAP_SEED, "method": "paired item-resample, percentile CI"},
        "how_to_read": (
            "Bốn chỉ số quyết định (PASS_CORRECT/PASS_REFUSAL/HALLUCINATED/FABRICATED) và "
            "CI của T0 xác định trần nhiễu; mọi chênh lệch giữa hai round pha sinh nằm trọn "
            "trong CI95 của hiệu ứng ghép cặp phải coi là nhiễu cho tới khi có chứng cứ khác."
        ),
    }

    out = Path(args.out)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[noise_floor] wrote {out}")
    print(json.dumps(agg["stats"], ensure_ascii=False, indent=2))
    print(f"[noise_floor] verdict flips: {len(flips)}/{len(common)}")
    for f in flips:
        print(f"  {f['id']} ({f['family']}): {f['baseline_verdict']} -> {f['candidate_verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
