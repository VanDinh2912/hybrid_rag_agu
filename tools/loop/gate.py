"""Cổng duyệt của vòng lặp: một thay đổi chỉ được coi là CẢI TIẾN khi không làm
các chỉ số cốt lõi suy giảm. Không có cổng này, vòng lặp "tự chữa bệnh" sẽ dần
tối ưu theo hướng rẻ nhất: trả lời ít đi cho đỡ bị gọi là bịa.

So sánh trên GIAO của hai round (cùng tập item, cùng trọng tài) — không so
"90 item của round mới" với "800 item của round cũ" rồi kết luận tăng 5 điểm.

Bốn bất biến (env để siết/nới, mặc định là mức đồ án đã nghiệm thu):
1. fabrication_rate_on_answered  : candidate <= baseline + GATE_MAX_FABRICATION_DELTA (0)
2. hallucinated_on_unanswerable  : candidate <= baseline + GATE_MAX_MISSED_REFUSAL_DELTA (0)
   — câu ngoài phạm vi mà vẫn trả lời = bịa đặt, nghiêm trọng nhất.
3. pass_rate toàn cục & theo family (n>=GATE_MIN_FAMILY_N) : giảm không quá
   GATE_MAX_PASS_DROP (2 điểm %) toàn cục, GATE_MAX_FAMILY_DROP (10) theo family.
   Riêng neo NGƯỜI (HUMAN) dùng ngưỡng toàn cục vì nó là mặt trận thật.
4. refusal_rate (từ chối oan là cái giá của an toàn) : không vượt GATE_MAX_REFUSAL_RATE (0.35).

Thoát code 0 = ĐẠT, 1 = KHÔNG ĐẠT (dùng được trong script/CI).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.loop.verify import PASS_VERDICTS, load_jsonl  # noqa: E402

FABRICATION_VERDICTS = {
    "FAIL_FABRICATED",
    "FAIL_CONFIRMED_FALSE_PREMISE",
    "FAIL_HALLUCINATED_ON_UNANSWERABLE",
    "FAIL_OVERREFUSAL",  # không phải bịa, nhưng là mất khả năng trả lời -> gộp vào "lỗi"
}
SEVERE_VERDICTS = {"FAIL_FABRICATED", "FAIL_CONFIRMED_FALSE_PREMISE", "FAIL_HALLUCINATED_ON_UNANSWERABLE"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def verdicts_path(round_dir: Path, phase: str) -> Path:
    path = round_dir / f"verdicts_{phase}.jsonl"
    if not path.exists():
        raise SystemExit(
            f"Thiếu {path}. Hãy chạy `python tools/loop/run_round.py --round "
            f"{round_dir.name} --phase {phase}` trước khi mở cổng."
        )
    return path


def load_rows(round_dir: Path, phase: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for row in load_jsonl(verdicts_path(round_dir, phase)):
        if row.get("id"):
            rows[row["id"]] = row
    return rows


def metrics(rows: list[dict]) -> dict[str, Any]:
    """Tính bộ chỉ số trên ĐÚNG tập item được đưa vào so sánh."""
    n = len(rows)
    if n == 0:
        return {"n": 0}
    decided = [r for r in rows if r.get("verdict") != "PENDING_GENERATION"]
    pass_verdicts = [r for r in decided if r.get("verdict") in PASS_VERDICTS]
    answered = [r for r in decided if not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0]
    counts = Counter(r.get("verdict") for r in decided)
    grounding = [r.get("grounding_score") for r in answered if r.get("grounding_score") is not None]
    # --- Recall: mẫu số PHẢI là "item có chunk vàng", tính trên MỌI row ---
    # Row PENDING_GENERATION chính là các câu ĐÃ trúng chunk vàng, nên loại nó khỏi
    # mẫu số (như bản cũ) khiến gold_in_top_k_rate của pha truy xuất luôn bằng 0 và
    # cổng báo "ĐẠT" trên một con số vô nghĩa.
    flagged = [r for r in rows if "has_gold_chunk" in r]
    gold_rows = [r for r in flagged if r.get("has_gold_chunk")]
    gold_rate = (
        round(sum(1 for r in gold_rows if r.get("gold_in_top_k")) / len(gold_rows), 4)
        if gold_rows
        else None
    )
    # Pha truy xuất không có văn bản trả lời -> pass_rate/fabrication KHÔNG ÁP DỤNG,
    # thà để None còn hơn báo 0.0 rồi "ĐẠT" giả.
    has_answer = any((r.get("answer_chars") or 0) > 0 for r in rows)

    def _rate(group: list[dict]) -> dict[str, Any]:
        """Một ô family: hai thang đo độc lập, thang nào không đo được thì None."""
        g_decided = [r for r in group if r.get("verdict") != "PENDING_GENERATION"]
        g_answer = [r for r in g_decided if (r.get("answer_chars") or 0) > 0]
        g_gold = [r for r in group if r.get("has_gold_chunk")]
        # "Văn bản đúng có vào cửa sổ" — thang duy nhất đo được ở pha rẻ cho item neo
        # theo cả văn bản (HUMAN), vì chúng không có gold_chunk_id duy nhất.
        g_anchor = [r for r in group if r.get("expected_source_in_window") is not None]
        return {
            "n": len(group),
            "n_decided": len(g_decided),
            "pass_rate": (
                round(sum(1 for r in g_decided if r.get("verdict") in PASS_VERDICTS) / len(g_decided), 4)
                if g_decided and g_answer
                else None
            ),
            "gold_rate": (
                round(sum(1 for r in g_gold if r.get("gold_in_top_k")) / len(g_gold), 4)
                if g_gold
                else None
            ),
            "n_gold": len(g_gold),
            "anchor_rate": (
                round(sum(1 for r in g_anchor if r.get("expected_source_in_window")) / len(g_anchor), 4)
                if g_anchor
                else None
            ),
            "n_anchor": len(g_anchor),
            "fabricated": sum(1 for r in g_decided if r.get("verdict") in SEVERE_VERDICTS),
        }

    by_family = {family: _rate(group) for family, group in _group_by(rows, "family").items()}
    return {
        "n": n,
        "n_decided": len(decided),
        "has_answer_signal": has_answer,
        "n_gold_items": len(gold_rows),
        "pass_rate": (
            round(len(pass_verdicts) / len(decided), 4) if decided and has_answer else None
        ),
        "fabrication_rate_on_answered": (
            round(sum(1 for r in answered if r.get("unsupported")) / len(answered), 4) if answered else None
        ),
        "hallucinated_on_unanswerable": counts.get("FAIL_HALLUCINATED_ON_UNANSWERABLE", 0),
        "confirmed_false_premise": counts.get("FAIL_CONFIRMED_FALSE_PREMISE", 0),
        "overrefusal": counts.get("FAIL_OVERREFUSAL", 0),
        "retrieval_failures": counts.get("FAIL_RETRIEVAL", 0),
        "incomplete": counts.get("FAIL_INCOMPLETE", 0),
        "refusal_rate": round(sum(1 for r in decided if r.get("is_refusal")) / len(decided), 4) if decided else None,
        "mean_grounding_score": round(sum(grounding) / len(grounding), 4) if grounding else None,
        "gold_in_top_k_rate": gold_rate,
        "gold_flagged_rows": len(flagged),
        "verdict_counts": dict(counts),
        "by_family": by_family,
    }


def _group_by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out[r.get(key) or "?"].append(r)
    return out


def _delta(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old is None:
        return None
    return round(new - old, 4)


def compare(candidate: dict, baseline: dict, common_ids: list[str]) -> dict:
    checks: list[dict] = []
    drop_limit = _env_float("GATE_MAX_PASS_DROP", 0.02)
    family_drop_limit = _env_float("GATE_MAX_FAMILY_DROP", 0.10)
    fab_delta = _env_float("GATE_MAX_FABRICATION_DELTA", 0.0)
    missed_delta = _env_int("GATE_MAX_MISSED_REFUSAL_DELTA", 0)
    max_refusal = _env_float("GATE_MAX_REFUSAL_RATE", 0.35)
    min_family_n = _env_int("GATE_MIN_FAMILY_N", 8)

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"rule": name, "ok": bool(ok), "detail": detail})

    # 1. không được Bịa thêm
    cf, bf = candidate["fabrication_rate_on_answered"], baseline["fabrication_rate_on_answered"]
    if cf is not None and bf is not None:
        add(
            "fabrication_not_increased",
            cf <= bf + fab_delta,
            f"candidate={cf} baseline={bf} delta={_delta(cf, bf)} (ngưỡng +{fab_delta})",
        )
    else:
        add("fabrication_not_increased", True, "không đủ cặp câu đã trả lời để so")

    # 2. không được trả lời bừa câu ngoài phạm vi
    ch, bh = candidate["hallucinated_on_unanswerable"], baseline["hallucinated_on_unanswerable"]
    add(
        "no_new_hallucinated_refusal",
        ch <= bh + missed_delta,
        f"candidate={ch} baseline={bh} (ngưỡng +{missed_delta})",
    )

    # 3. pass_rate không rơi quá ngưỡng
    cp, bp = candidate["pass_rate"], baseline["pass_rate"]
    if cp is not None and bp is not None:
        add(
            "pass_rate_not_dropped",
            cp >= bp - drop_limit,
            f"candidate={cp} baseline={bp} delta={_delta(cp, bp)} (ngưỡng -{drop_limit})",
        )

    # 3b. theo từng family — chống 'cứu' chỗ này bằng cách phá chỗ khác.
    # Pha truy xuất không có pass_rate nên ô family dùng gold_rate: ngưởng vẫn là
    # GATE_MAX_FAMILY_DROP, chỉ khác thang đo — ý nghĩa "không family nào bị đem đánh
    # đổi" giữ nguyên.
    fam_lines: list[str] = []
    fam_problems: list[str] = []
    for family, cinfo in sorted(candidate["by_family"].items()):
        binfo = baseline["by_family"].get(family)
        if not binfo or cinfo["n"] < min_family_n or binfo["n"] < min_family_n:
            continue
        if cinfo.get("pass_rate") is not None and binfo.get("pass_rate") is not None:
            metric, cv, bv = "pass_rate", cinfo["pass_rate"], binfo["pass_rate"]
        elif cinfo.get("gold_rate") is not None and binfo.get("gold_rate") is not None:
            metric, cv, bv = "gold_rate", cinfo["gold_rate"], binfo["gold_rate"]
        else:
            continue
        delta = _delta(cv, bv)
        if delta is None:
            continue
        line = f"{family}: {metric} {bv}->{cv} ({delta:+.4f}, n={cinfo['n']})"
        if delta < -family_drop_limit:
            fam_problems.append((family, f"{line} giảm quá ngưỡng -{family_drop_limit}"))
        else:
            fam_lines.append(line)
    for family, problem in fam_problems:
        add(f"family_pass_rate[{family}]", False, problem)
    if not fam_problems:
        add(
            "family_pass_rate",
            True,
            f"không family nào (n>={min_family_n}) giảm quá {family_drop_limit} "
            f"trên {len(fam_lines)} family đo được",
        )

    # 3c. neo do NGƯỜI viết — ưu tiên 1, không được giảm TỶ ĐỐI trên 5%
    # Hai thang, tùy pha: `pass_rate` (pha có sinh văn bản) và `anchor_rate` = "đúng
    # văn bản được kéo vào cửa sổ" (pha rẻ). Bản cũ chỉ nhìn pass_rate nên ở pha
    # truy xuất cái neo quan trọng nhất KHÔNG ĐƯỢC ĐO — đúng chỗ lever router có thể
    # phá nó mà cổng vẫn mở.
    anchor_c = candidate["by_family"].get("HUMAN", {})
    anchor_b = baseline["by_family"].get("HUMAN", {})
    rel_limit = _env_float("GATE_MAX_HUMAN_REL_DROP", 0.05)
    if anchor_c.get("n") and anchor_b.get("n"):
        dc, db = anchor_c.get("pass_rate"), anchor_b.get("pass_rate")
        if dc is not None and db is not None and db > 0:
            rel = (dc - db) / db
            add(
                "human_anchor_not_degraded",
                rel >= -rel_limit,
                f"pass_rate HUMAN {db}->{dc} (tương đối {rel:+.2%}, ngưỡng -{rel_limit:.0%})",
            )
        ac, ab = anchor_c.get("anchor_rate"), anchor_b.get("anchor_rate")
        if ac is not None and ab is not None and ab > 0:
            rel = (ac - ab) / ab
            add(
                "human_anchor_source_not_degraded",
                rel >= -rel_limit,
                f"đúng-nguồn-vào-cửa-sổ HUMAN {ab}->{ac} (tương đối {rel:+.2%}, ngưỡng -{rel_limit:.0%}, "
                f"n={anchor_c.get('n_anchor')})",
            )
        elif anchor_c.get("n_anchor") or anchor_b.get("n_anchor"):
            add(
                "human_anchor_source_not_degraded",
                False,
                "KHÔNG ĐO ĐƯỢC neo HUMAN ở pha rẻ "
                f"(candidate anchor_rate={ac} n={anchor_c.get('n_anchor')}, "
                f"baseline anchor_rate={ab} n={anchor_b.get('n_anchor')}) — verdict bên "
                "thiếu là của verify.py cũ, chạy lại lệnh round của nó để chấm lại",
            )

    # 4. cái giá từ chối oan có trần
    cr = candidate["refusal_rate"]
    if cr is not None:
        add(
            "refusal_rate_bounded",
            cr <= max_refusal,
            f"candidate={cr} baseline={baseline['refusal_rate']} (trần {max_refusal})",
        )

    # 5. truy xuất không được tệ đi (chống 'sửa' bằng cách thu hẹp cửa sổ)
    cg, bg = candidate["gold_in_top_k_rate"], baseline["gold_in_top_k_rate"]
    recall_drop = _env_float("GATE_MAX_RECALL_DROP", 0.02)
    if cg is None or bg is None:
        # QUY TẮC KHÔNG ĐO ĐƯỢC = CẤM, không phải ĐẠT. Bản cũ bỏ qua rule này khi
        # thiếu số liệu, khiến cổng in "[ĐẠT] retrieval_not_degraded gold 0.0->0.0"
        # trên một mẫu số sai.
        add(
            "retrieval_not_degraded",
            False,
            "KHÔNG ĐO ĐƯỢC recall (candidate n_gold="
            f"{candidate.get('n_gold_items')}, baseline n_gold={baseline.get('n_gold_items')}) "
            "— nếu hai con số này bằng 0 thì verdict được ghi bởi verify.py cũ thiếu "
            "cờ has_gold_chunk: chạy lại lệnh round của cả hai round để chấm lại rồi mở cổng",
        )
    else:
        add(
            "retrieval_not_degraded",
            cg >= bg - recall_drop,
            f"gold@k {bg}->{cg} trên {candidate.get('n_gold_items')} item có chunk vàng "
            f"(ngưỡng -{recall_drop})",
        )

    regressions, improvements = _flips(candidate, baseline, common_ids)
    passed = all(c["ok"] for c in checks)
    return {
        "passed": passed,
        "n_common_items": len(common_ids),
        "thresholds": {
            "GATE_MAX_PASS_DROP": drop_limit,
            "GATE_MAX_FAMILY_DROP": family_drop_limit,
            "GATE_MAX_FABRICATION_DELTA": fab_delta,
            "GATE_MAX_MISSED_REFUSAL_DELTA": missed_delta,
            "GATE_MAX_REFUSAL_RATE": max_refusal,
            "GATE_MAX_RECALL_DROP": _env_float("GATE_MAX_RECALL_DROP", 0.02),
            "GATE_MIN_FAMILY_N": min_family_n,
        },
        "checks": checks,
        "family_deltas": fam_lines,
        "regressions": regressions,
        "improvements": improvements,
    }


def _flips(candidate: dict, baseline: dict, common_ids: list[str]) -> tuple[list[dict], list[dict]]:
    """Liệt kê item đổi chiều trên tập chung (minh chứng, không phải luật).

    Hai loại bằng chứng: đổi chiều verdict (chỉ có nghĩa khi hai round đều có văn bản)
    và đổi chiều `gold_in_top_k` — ở PHA TRUY XUẤT đây là thứ duy nhất đổi, và bản cũ
    chỉ nhìn verdict nên cổng in 'Cải thiện: 0' trong lúc 173 câu vừa vào cửa sổ.
    """
    rows_c = candidate["_rows"]
    rows_b = baseline["_rows"]
    regressions, improvements = [], []
    for item_id in common_ids:
        c, b = rows_c.get(item_id), rows_b.get(item_id)
        if not c or not b:
            continue
        if c.get("verdict") != b.get("verdict"):
            cp = c.get("verdict") in PASS_VERDICTS
            bp = b.get("verdict") in PASS_VERDICTS
            entry = {
                "id": item_id,
                "family": c.get("family"),
                "split": c.get("split"),
                "kind": "verdict",
                "from": b.get("verdict"),
                "to": c.get("verdict"),
                "raw_query": (c.get("raw_query") or "")[:120],
            }
            if bp and not cp:
                regressions.append(entry)
            elif cp and not bp:
                improvements.append(entry)
        if c.get("has_gold_chunk") and b.get("has_gold_chunk"):
            cg, bg = bool(c.get("gold_in_top_k")), bool(b.get("gold_in_top_k"))
            if cg != bg:
                entry = {
                    "id": item_id,
                    "family": c.get("family"),
                    "split": c.get("split"),
                    "kind": "recall",
                    "from": f"gold@k={bg}",
                    "to": f"gold@k={cg}",
                    "raw_query": (c.get("raw_query") or "")[:120],
                }
                (improvements if cg else regressions).append(entry)
        # Neo theo cả văn bản (HUMAN): bằng chứng là "đúng văn bản có còn trong cửa sổ".
        ca, ba = c.get("expected_source_in_window"), b.get("expected_source_in_window")
        if ca is not None and ba is not None and ca != ba:
            entry = {
                "id": item_id,
                "family": c.get("family"),
                "split": c.get("split"),
                "kind": "anchor",
                "from": f"nguon_trong_cua_so={ba}",
                "to": f"nguon_trong_cua_so={ca}",
                "source_document": c.get("expected_citation_source"),
                "raw_query": (c.get("raw_query") or "")[:120],
            }
            (improvements if ca else regressions).append(entry)
    return regressions, improvements


def round_settings(round_dir: Path, phase: str) -> dict:
    """Đọc `settings` đã ghi trong round_summary để biết hai round có so được nhau
    không. Thiếu file thì trả {} (cổng vẫn chạy nhưng cảnh báo)."""
    path = round_dir / f"round_summary_{phase}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("settings") or {}
    except json.JSONDecodeError:
        return {}


def compatibility(candidate: dict, baseline: dict) -> list[str]:
    """So cấu hình chạy hai round — trả về danh sách MÂU THUẪN (rỗng = so được)."""
    if not candidate or not baseline:
        # Round cũ (chạy trước khi có settings block) hoặc round bị gián đoạn trước
        # bước ghi summary: không xác nhận được gì, báo MỘT lần chứ không lặp theo số key.
        return ["thiếu round_summary — không xác nhận được hai round chạy chung cấu hình"]
    problems = []
    # Chữ ký trọng tài đi TRƯỚC các key khác vì nó là lỗi dễ sửa nhất mà hậu quả
    # nặng nhất: hai round chấm bằng hai phiên bản dụng cụ thì mọi chênh lệch số
    # đều vô nghĩa (r0 thật đã vấp đúng ca này).
    c_ref, b_ref = candidate.get("referee"), baseline.get("referee")
    if c_ref != b_ref:
        problems.append(
            "trọng tài khác phiên bản "
            f"(candidate={c_ref or 'không_ghi'}, baseline={b_ref or 'không_ghi'}) "
            "— chạy lại lệnh round của round cũ khi <phase>.jsonl đã đủ dòng để chấm lại, "
            "rồi mới mở cổng"
        )
    for key in ("testset", "top_k", "generator", "normalize_query", "enable_classifier"):
        c, b = candidate.get(key), baseline.get(key)
        if c is None and b is None:
            continue
        if str(c) != str(b):
            problems.append(f"{key} khác nhau: candidate={c} baseline={b}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="Cổng duyệt không suy giảm giữa hai round")
    parser.add_argument("--rounds-root", default=str(ROOT / "data" / "loop" / "rounds"))
    parser.add_argument("--candidate", required=True, help="nhãn round mới, ví dụ r1")
    parser.add_argument("--baseline", required=True, help="nhãn round chuẩn, ví dụ r0")
    parser.add_argument("--phase", default="full", choices=["full", "retrieval"])
    parser.add_argument("--out", default="", help="ghi báo cáo JSON (mặc định rounds/<candidate>/gate_vs_<baseline>.json)")
    args = parser.parse_args()

    rounds_root = Path(args.rounds_root)
    cand_dir, base_dir = rounds_root / args.candidate, rounds_root / args.baseline
    cand_rows = load_rows(cand_dir, args.phase)
    base_rows = load_rows(base_dir, args.phase)
    # Chỉ so trên giao — phần chưa chạy ở một trong hai round không được tính.
    common = sorted(set(cand_rows) & set(base_rows))
    if len(common) < _env_int("GATE_MIN_COMMON", 20):
        raise SystemExit(
            f"Chỉ có {len(common)} item chung giữa {args.candidate} và {args.baseline} "
            f"(pha {args.phase}) — chưa đủ để mở cổng."
        )
    candidate = metrics([cand_rows[i] for i in common])
    baseline = metrics([base_rows[i] for i in common])
    candidate["_rows"] = cand_rows
    baseline["_rows"] = base_rows

    result = compare(candidate, baseline, common)
    # Hai round phải chạy CÙNG thang đo; nếu không thì mọi so sánh đều vô nghĩa.
    mismatches = compatibility(
        round_settings(cand_dir, args.phase), round_settings(base_dir, args.phase)
    )
    if mismatches and os.getenv("GATE_ALLOW_CONFIG_MISMATCH", "0").strip().lower() in {"0", "false", "no"}:
        result["passed"] = False
    result["config_mismatches"] = mismatches
    result.update(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "candidate_round": args.candidate,
            "baseline_round": args.baseline,
            "phase": args.phase,
            "candidate_metrics": {k: v for k, v in candidate.items() if k != "_rows"},
            "baseline_metrics": {k: v for k, v in baseline.items() if k != "_rows"},
        }
    )

    out_path = Path(args.out) if args.out else cand_dir / f"gate_vs_{args.baseline}_{args.phase}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print(f"CỔNG VÒNG LẶP: {args.candidate} so với {args.baseline} (pha {args.phase}, {len(common)} item chung)")
    print("=" * 72)
    for check in result["checks"]:
        print(f"  [{'ĐẠT ' if check['ok'] else 'VI PHẠM'}] {check['rule']:34s} {check['detail']}")
    for mismatch in result.get("config_mismatches", []):
        print(f"  [CẤU HÌNH] {mismatch}")
    if result["family_deltas"]:
        print("\n  Biến động theo family:")
        for line in result["family_deltas"]:
            print(f"    - {line}")
    def _split_flips(entries: list[dict]) -> str:
        kinds = Counter(e.get("kind") for e in entries)
        return " + ".join(f"{k}:{kinds[k]}" for k in ("verdict", "recall", "anchor") if kinds.get(k)) or "0"

    print(
        f"\n  Hồi quy cụ thể: {_split_flips(result['regressions'])}"
        f" | Cải thiện: {_split_flips(result['improvements'])}"
        f" (trên {result['n_common_items']} item chung)"
    )
    print(f"  Kết luận: {'ĐẠT — được merge thay đổi' if result['passed'] else 'KHÔNG ĐẠT — giữ nguyên bản cũ, sửa rồi chấm lại'}")
    print(f"  Báo cáo: {out_path}")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
