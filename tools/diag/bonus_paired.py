"""So sánh GHÉP CẶP hai round truy xuất trên toàn bộ 811 item — công cụ trả lời câu
"bonus lọc mềm 3 hay 12?" (nhiệm vụ T5, 24-10).

Bối cảnh: `ROADMAP.md` P5.16 ghi r1 (bonus 3) có gold@6 76,57% CAO HƠN r2 (bonus 12)
74,00%, nhưng r2 được chọn làm mặc định vì cổng r2-vs-r1 đổi chiều: bonus 12 "mua neo
HUMAN bằng gold@6". Lý do cơ chế trong ROADMAP chỉ mới đứng trên một probe 21 item
(`tmp/probe_bonus_regressions.py`). Script này kiểm lại lý do đó trên TOÀN BỘ cặp bất
đồng của 811 item, bằng đúng dữ liệu đã lưu trên đĩa — không gọi model, không sửa code
sản xuất, không đổi trọng tài.

Ba thống kê đăng ký trong script (định nghĩa lấy nguyên văn từ `tools/loop/gate.py`):
- gold@6 = trung bình `gold_in_top_k` trên item có `has_gold_chunk` (mẫu số gate dùng).
- anchor = trung bình `expected_source_in_window` trên item có trường đó (toàn cục và
  riêng family HUMAN).
- McNemar chính xác trên cặp bất đồng + paired bootstrap 10.000 lượt (seed 20261023)
  cho hiệu ứng — cùng helper với `tools/loop/noise_floor.py`.

Chạy:
    PYTHONIOENCODING=utf-8 python tools/diag/bonus_paired.py \
        --baseline r1 --candidate r2 --third r4 \
        --out data/loop/diag/bonus_paired.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.loop.noise_floor import (  # noqa: E402
    mcnemar_exact,
    paired_bootstrap,
    rate_ci,
)
from tools.loop.attribute import source_blocks_gold  # noqa: E402  (tái dùng luật quy lỗi)

WINDOW = 6  # cửa sổ generator (top_k) của mọi round P5


# ------------------------------------------------------------------ đọc dữ liệu round
def load_round(rounds_root: Path, round_name: str, phase: str = "retrieval") -> dict[str, Any]:
    """Nạp verdicts + rows của một round pha truy xuất, khóa theo item id."""
    base = rounds_root / round_name
    verdicts_path = base / f"verdicts_{phase}.jsonl"
    rows_path = base / f"{phase}.jsonl"
    for path in (verdicts_path, rows_path):
        if not path.exists():
            raise SystemExit(f"Thiếu {path} — round {round_name} chưa có pha {phase}.")

    verdicts = {}
    for line in verdicts_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            verdicts[row["id"]] = row
    rows = {}
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = row
    return {
        "round": round_name,
        "phase": phase,
        "paths": {
            "verdicts": str(verdicts_path.relative_to(REPO_ROOT)),
            "rows": str(rows_path.relative_to(REPO_ROOT)),
            "summary": str((base / f"round_summary_{phase}.json").relative_to(REPO_ROOT))
            if (base / f"round_summary_{phase}.json").exists()
            else None,
        },
        "verdicts": verdicts,
        "rows": rows,
    }


def settings_of(rounds_root: Path, round_name: str, phase: str) -> dict[str, Any]:
    path = rounds_root / round_name / f"round_summary_{phase}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("settings") or {}


# ------------------------------------------------------------------ chỉ số từng round
def gold_ids(data: dict) -> list[str]:
    return [i for i, v in data["verdicts"].items() if v.get("has_gold_chunk")]


def gold_flags(data: dict, ids: list[str]) -> list[int]:
    return [1 if data["verdicts"][i].get("gold_in_top_k") else 0 for i in ids]


def anchor_flags(data: dict) -> tuple[list[str], list[int]]:
    ids = [i for i, v in data["verdicts"].items() if v.get("expected_source_in_window") is not None]
    return ids, [1 if data["verdicts"][i].get("expected_source_in_window") else 0 for i in ids]


def round_block(data: dict, rounds_root: Path) -> dict[str, Any]:
    verdicts = data["verdicts"]
    ids = gold_ids(data)
    flags = gold_flags(data, ids)
    out: dict[str, Any] = {
        "n_items": len(verdicts),
        "n_gold_items": len(ids),
        "gold_at_k": round(sum(flags) / len(ids), 4) if ids else None,
        "gold_ci95": rate_ci(flags, [1] * len(flags)) if ids else None,
        "settings": settings_of(rounds_root, data["round"], data["phase"]),
    }
    anc_ids, anc = anchor_flags(data)
    out["anchor_rate_all"] = round(sum(anc) / len(anc), 4) if anc else None
    human = [i for i in anc_ids if verdicts[i].get("family") == "HUMAN"]
    human_flags = [1 if verdicts[i].get("expected_source_in_window") else 0 for i in human]
    out["anchor_rate_human"] = round(sum(human_flags) / len(human_flags), 4) if human_flags else None
    out["n_anchor_human"] = len(human_flags)

    by_family: dict[str, dict[str, Any]] = {}
    for family in sorted({verdicts[i].get("family") or "?" for i in verdicts}):
        fam_ids = [i for i in ids if verdicts[i].get("family") == family]
        if not fam_ids:
            continue
        fam_flags = gold_flags(data, fam_ids)
        by_family[family] = {
            "n_gold": len(fam_ids),
            "gold_at_k": round(sum(fam_flags) / len(fam_ids), 4),
            "ci95": rate_ci(fam_flags, [1] * len(fam_flags)),
        }
    out["gold_by_family"] = by_family

    by_split: dict[str, dict[str, Any]] = {}
    for split in sorted({verdicts[i].get("split") or "?" for i in ids}):
        s_ids = [i for i in ids if (verdicts[i].get("split") or "?") == split]
        s_flags = gold_flags(data, s_ids)
        by_split[split] = {"n_gold": len(s_ids), "gold_at_k": round(sum(s_flags) / len(s_ids), 4)}
    out["gold_by_split"] = by_split

    # Độ tập trung nguồn trong cửa sổ: bao nhiêu item mà MỘT nguồn chiếm >= 4/6 suất?
    conc = []
    for i, row in data["rows"].items():
        srcs = (row.get("sources") or [])[:WINDOW]
        names = [str(s.get("source") or "") for s in srcs]
        if not names:
            continue
        modal = Counter(names).most_common(1)[0][1]
        conc.append(modal)
    out["window_concentration"] = {
        "mean_modal_source_share": round(sum(conc) / len(conc) / WINDOW, 4) if conc else None,
        "n_items_window_full_by_one_source": sum(1 for c in conc if c >= WINDOW),
        "n_items_modal_ge_4": sum(1 for c in conc if c >= 4),
        "n_measured": len(conc),
    }

    # Lỗ hổng ghi dữ liệu: round cũ không lưu `retrieval_config` -> attribute.py vô hiệu.
    missing = sum(1 for row in data["rows"].values() if not row.get("retrieval_config"))
    out["rows_without_retrieval_config"] = missing
    out["attribution_usable"] = missing == 0

    # Trần của MỌI đòn bẩy chỉ XẾP LẠI thứ tự (reranker): chunk vàng có mặt trong danh
    # sách ứng viên hay không tồn tại ở đó. `rerankable_by_pool` = hạng WINDOW+1..2*WINDOW
    # (nằm ngay ngoài cửa sổ, reranker với pool 2*WINDOW với tới được).
    ceiling: dict[str, dict[str, int]] = {}
    for i, v in verdicts.items():
        if not v.get("has_gold_chunk"):
            continue
        fam = v.get("family") or "?"
        rank = v.get("gold_rank_in_sources")
        blk = ceiling.setdefault(fam, {"n_gold": 0, "in_window": 0, "outside_window_in_list": 0, "absent_from_list": 0})
        blk["n_gold"] += 1
        if rank is None:
            blk["absent_from_list"] += 1
        elif rank <= WINDOW:
            blk["in_window"] += 1
        else:
            blk["outside_window_in_list"] += 1
    for fam, blk in ceiling.items():
        blk["gold_at_k"] = round(blk["in_window"] / blk["n_gold"], 4)
        blk["ceiling_if_all_outside_ranks_7_to_12_recovered"] = round(
            (blk["in_window"] + blk["outside_window_in_list"]) / blk["n_gold"], 4
        )
    out["gold_rank_ceiling"] = ceiling
    return out


# ------------------------------------------------------------------ so sánh ghép cặp
def paired_block(base: dict, cand: dict, third: dict | None = None) -> dict[str, Any]:
    common = sorted(set(base["verdicts"]) & set(cand["verdicts"]))
    gold_common = [i for i in common if base["verdicts"][i].get("has_gold_chunk") and cand["verdicts"][i].get("has_gold_chunk")]
    bf = gold_flags(base, gold_common)
    cf = gold_flags(cand, gold_common)
    n = len(gold_common)
    # Quy ước mcnemar_exact(b, c): b = cặp "chỉ CANDIDATE đúng", c = cặp "chỉ BASELINE đúng".
    only_base = sum(1 for x, y in zip(bf, cf) if x and not y)
    only_cand = sum(1 for x, y in zip(bf, cf) if y and not x)
    both = sum(1 for x, y in zip(bf, cf) if x and y)
    neither = sum(1 for x, y in zip(bf, cf) if not x and not y)

    out: dict[str, Any] = {
        "n_common_items": len(common),
        "n_common_gold_items": n,
        "baseline": base["round"],
        "candidate": cand["round"],
        "gold_flags": {"both_hit": both, "only_baseline": only_base, "only_candidate": only_cand, "both_miss": neither},
        "mcnemar_exact": mcnemar_exact(only_cand, only_base),
        "paired_bootstrap_gold_delta": paired_bootstrap(bf, cf, [1] * n, [1] * n),
        "gold_delta": round(sum(cf) / n - sum(bf) / n, 4) if n else None,
    }

    # Cùng phép nhưng trên family EXACT và TRAP* (tiêu chí T5 nói đích danh EXACT).
    per_family: dict[str, Any] = {}
    for family in ("EXACT", "TRAP", "TRAP_OCR"):
        ids = [i for i in gold_common if (base["verdicts"][i].get("family") or cand["verdicts"][i].get("family")) == family]
        if not ids:
            continue
        f_b = gold_flags(base, ids)
        f_c = gold_flags(cand, ids)
        m = len(ids)
        per_family[family] = {
            "n_gold": m,
            "baseline_rate": round(sum(f_b) / m, 4),
            "candidate_rate": round(sum(f_c) / m, 4),
            "delta": round((sum(f_c) - sum(f_b)) / m, 4),
            "mcnemar": mcnemar_exact(
                sum(1 for x, y in zip(f_b, f_c) if y and not x),
                sum(1 for x, y in zip(f_b, f_c) if x and not y),
            ),
        }
    out["by_family"] = per_family

    # neo HUMAN ghép cặp
    anc_common = [
        i
        for i in common
        if base["verdicts"][i].get("expected_source_in_window") is not None
        and cand["verdicts"][i].get("expected_source_in_window") is not None
    ]
    a_b = [1 if base["verdicts"][i].get("expected_source_in_window") else 0 for i in anc_common]
    a_c = [1 if cand["verdicts"][i].get("expected_source_in_window") else 0 for i in anc_common]
    human_common = [i for i in anc_common if base["verdicts"][i].get("family") == "HUMAN"]
    h_b = [1 if base["verdicts"][i].get("expected_source_in_window") else 0 for i in human_common]
    h_c = [1 if cand["verdicts"][i].get("expected_source_in_window") else 0 for i in human_common]
    m = len(anc_common)
    out["anchor"] = {
        "n": m,
        "baseline_rate": round(sum(a_b) / m, 4) if m else None,
        "candidate_rate": round(sum(a_c) / m, 4) if m else None,
        "delta": round((sum(a_c) - sum(a_b)) / m, 4) if m else None,
        "paired_bootstrap": paired_bootstrap(a_b, a_c, [1] * m, [1] * m) if m else None,
        "human": {
            "n": len(human_common),
            "baseline_rate": round(sum(h_b) / len(human_common), 4) if human_common else None,
            "candidate_rate": round(sum(h_c) / len(human_common), 4) if human_common else None,
            "delta": round((sum(h_c) - sum(h_b)) / len(human_common), 4) if human_common else None,
            "mcnemar": mcnemar_exact(
                sum(1 for x, y in zip(h_b, h_c) if y and not x),
                sum(1 for x, y in zip(h_b, h_c) if x and not y),
            )
            if human_common
            else None,
        },
    }

    # ---- CƠ CHẾ: mất ở round nào thì mất vì gì?
    out["mechanism"] = {
        "lost_in_candidate": discordant_detail(base, cand, direction="hit_to_miss"),
        "gained_in_candidate": discordant_detail(base, cand, direction="miss_to_hit"),
    }
    if third is not None:
        t_common = [i for i in gold_common if i in third["verdicts"] and third["verdicts"][i].get("has_gold_chunk")]
        t_f = gold_flags(third, t_common)
        b_f2 = gold_flags(base, t_common)
        c_f2 = gold_flags(cand, t_common)
        m2 = len(t_common)
        out["third_round"] = {
            "round": third["round"],
            "n": m2,
            "gold_at_k": round(sum(t_f) / m2, 4) if m2 else None,
            "vs_baseline": {"delta": round((sum(t_f) - sum(b_f2)) / m2, 4) if m2 else None},
            "vs_candidate": {
                "delta": round((sum(t_f) - sum(c_f2)) / m2, 4) if m2 else None,
                "mcnemar": mcnemar_exact(
                    sum(1 for x, y in zip(c_f2, t_f) if y and not x),
                    sum(1 for x, y in zip(c_f2, t_f) if x and not y),
                ),
            },
            "recovered_items_of_candidate_losses": sum(
                1
                for i in t_common
                if base["verdicts"][i].get("gold_in_top_k")
                and not cand["verdicts"][i].get("gold_in_top_k")
                and third["verdicts"][i].get("gold_in_top_k")
            ),
        }
    return out


def window_sources(data: dict, item_id: str) -> list[dict]:
    return (data["rows"].get(item_id, {}).get("sources") or [])[:WINDOW]


def discordant_detail(base: dict, cand: dict, *, direction: str) -> dict[str, Any]:
    """Liệt kê + phân loại từng item đổi chiều gold@6 giữa hai round.

    Nguyên nhân luôn xét ở ROUND THUA (round không đưa được chunk vàng vào cửa sổ),
    vì đó mới là chỗ cần giải thích:
    - "hit_to_miss" (baseline trúng, candidate trượt) ->loser = candidate;
    - "miss_to_hit" (ngược lại) -> loser = baseline.
    Luật phân loại lấy từ `tools/loop/attribute.py::classify_failure`: chunk vàng bị
    `source_filter` cắt khỏi danh sách ứng viên, hay chỉ XẾP HẠNG ngoài cửa sổ.
    """
    items: list[dict[str, Any]] = []
    for i in sorted(set(base["verdicts"]) & set(cand["verdicts"])):
        bv, cv = base["verdicts"][i], cand["verdicts"][i]
        if not (bv.get("has_gold_chunk") and cv.get("has_gold_chunk")):
            continue
        hit_b, hit_c = bool(bv.get("gold_in_top_k")), bool(cv.get("gold_in_top_k"))
        if direction == "hit_to_miss" and not (hit_b and not hit_c):
            continue
        if direction == "miss_to_hit" and not (hit_c and not hit_b):
            continue
        loser, winner = (cand, base) if direction == "hit_to_miss" else (base, cand)
        loser_v, winner_v = (cv, bv) if direction == "hit_to_miss" else (bv, cv)
        item = (cand["rows"].get(i) or base["rows"].get(i) or {}).get("item") or {}
        l_row = loser["rows"].get(i) or {}
        w_row = winner["rows"].get(i) or {}
        l_filter = (l_row.get("retrieval_config") or {}).get("source_filter")
        w_filter = (w_row.get("retrieval_config") or {}).get("source_filter")
        l_srcs = window_sources(loser, i)
        w_srcs = window_sources(winner, i)
        l_names = [str(s.get("source") or "") for s in l_srcs]
        gold_source = str(item.get("source_document") or "")
        l_rank = loser_v.get("gold_rank_in_sources")
        w_rank = winner_v.get("gold_rank_in_sources")
        modal_l = Counter(l_names).most_common(1)[0][1] if l_names else 0
        modal_w = Counter([str(s.get("source") or "") for s in w_srcs]).most_common(1)[0][1] if w_srcs else 0
        if not (l_row.get("retrieval_config") or {}):
            cause = "loser_config_not_recorded"  # chỉ ảnh hưởng nhãn cơ chế, không ảnh hưởng gold@6
        elif source_blocks_gold(l_filter, gold_source):
            cause = "filter_blocks_gold"
        elif l_rank is not None and l_rank > WINDOW:
            cause = "ranking_outside_window"
        elif l_rank is None:
            cause = "gold_not_in_loser_list"
        else:
            cause = "unclassified"
        items.append(
            {
                "id": i,
                "family": cv.get("family"),
                "split": cv.get("split"),
                "gold_source": gold_source,
                "loser_round": loser["round"],
                "winner_round": winner["round"],
                "cause": cause,
                "loser_gold_rank": l_rank,
                "winner_gold_rank": w_rank,
                "loser_filter": l_filter,
                "winner_filter": w_filter,
                "loser_modal_source_share": modal_l,
                "winner_modal_source_share": modal_w,
                "loser_top6_sources": l_names,
            }
        )
    groups = Counter(x["cause"] for x in items)
    families = Counter(x["family"] or "?" for x in items)
    splits = Counter(x["split"] or "?" for x in items)
    just_outside = sum(
        1 for x in items if isinstance(x["loser_gold_rank"], int) and WINDOW < x["loser_gold_rank"] <= 2 * WINDOW
    )
    window_taken = sum(1 for x in items if x["loser_modal_source_share"] >= WINDOW)
    return {
        "n": len(items),
        "loser_round": items[0]["loser_round"] if items else None,
        "by_cause": dict(groups),
        "by_family": dict(families),
        "by_split": dict(splits),
        "n_gold_just_outside_window_7_to_12": just_outside,
        "n_window_taken_by_one_source": window_taken,
        "loser_rank_distribution": {str(k): v for k, v in Counter(x["loser_gold_rank"] for x in items).most_common()},
        "winner_rank_distribution": {str(k): v for k, v in Counter(x["winner_gold_rank"] for x in items).most_common()},
        "loser_filter_recorded": sum(1 for x in items if x["loser_filter"] is not None),
        "winner_filter_recorded": sum(1 for x in items if x["winner_filter"] is not None),
        "reading_note": (
            "Hai round cùng chạy classifier + bảng TOPIC_SOURCE_FILTER như nhau (settings giống "
            "hệt nhau ngoại trừ con số bonus), nên `filter_blocks_gold` ở đây KHÔNG có nghĩa là "
            "bộ lọc CẮT chunk vàng (chế độ mềm không cắt) — mà là: chunk vàng nằm NGOÀI danh sách "
            "nguồn được ưu tiên, và bonus đủ lớn (>= cỡ cửa sổ) kéo MỌI chunk trong danh sách lên "
            "trước nó, đúng bao nhiêu hạng bằng đúng mức bonus."
        ),
        "mean_loser_modal_share": round(
            sum(x["loser_modal_source_share"] for x in items) / len(items), 2
        )
        if items
        else None,
        "mean_winner_modal_share": round(
            sum(x["winner_modal_source_share"] for x in items) / len(items), 2
        )
        if items
        else None,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="r1", help="round bonus 3")
    parser.add_argument("--candidate", default="r2", help="round bonus 12")
    parser.add_argument("--third", default="r4", help="round bonus 12 + quota (đặt rỗng để bỏ)")
    parser.add_argument("--phase", default="retrieval")
    parser.add_argument("--rounds-root", default=str(REPO_ROOT / "data" / "loop" / "rounds"))
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "loop" / "diag" / "bonus_paired.json"))
    args = parser.parse_args()

    rounds_root = Path(args.rounds_root)
    base = load_round(rounds_root, args.baseline, args.phase)
    cand = load_round(rounds_root, args.candidate, args.phase)
    third = load_round(rounds_root, args.third, args.phase) if args.third else None

    report = {
        "purpose": "Kiểm lại lý do bonus 12 thấp gold@6 hơn bonus 3 trên TOÀN BỘ cặp bất đồng 811 item (ROADMAP P5.16 mới có probe 21 item).",
        "definitions": {
            "gold_at_k": "trung bình gold_in_top_k trên item has_gold_chunk — same as tools/loop/gate.py",
            "anchor": "trung bình expected_source_in_window (toàn cục + family HUMAN)",
            "tests": "mcnemar_exact + paired_bootstrap 10.000 lượt seed 20261023 (tools/loop/noise_floor.py)",
            "window": WINDOW,
        },
        "rounds": {
            args.baseline: round_block(base, rounds_root),
            args.candidate: round_block(cand, rounds_root),
        },
        "paired": paired_block(base, cand, third),
    }
    if third is not None:
        report["rounds"][args.third] = round_block(third, rounds_root)

    # Audit "một biến số": liệt kê MỌI khóa settings khác nhau giữa hai round. Ở pha
    # truy xuất, cờ chỉ ảnh hưởng tầng sinh (answer guard, rescue) không đổi gold@6 —
    # nhưng phải nhìn thấy được, không được suy ra từ trí nhớ.
    sb = report["rounds"][args.baseline]["settings"]
    sc = report["rounds"][args.candidate]["settings"]
    report["settings_diff"] = {
        k: {args.baseline: sb.get(k), args.candidate: sc.get(k)}
        for k in sorted(set(sb) | set(sc))
        if sb.get(k) != sc.get(k)
    }
    report["settings_diff_retrieval_relevant"] = {
        k: v
        for k, v in report["settings_diff"].items()
        if k in {"router_soft_filter", "router_filter_rank_bonus", "router_source_quota", "top_k", "enable_classifier", "normalize_query", "oversample_factor", "testset", "referee"}
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    p = report["paired"]
    print(f"=== GHÉP CẶP {args.baseline} (bonus {report['rounds'][args.baseline]['settings'].get('router_filter_rank_bonus')}) "
          f"vs {args.candidate} (bonus {report['rounds'][args.candidate]['settings'].get('router_filter_rank_bonus')}) ===")
    print(f"item chung: {p['n_common_items']} | có chunk vàng: {p['n_common_gold_items']}")
    print(f"  settings khác nhau giữa hai round: {json.dumps(report['settings_diff'], ensure_ascii=False)}")
    print(f"  ... trong đó liên quan pha truy xuất: {json.dumps(report['settings_diff_retrieval_relevant'], ensure_ascii=False)}")
    for r in (args.baseline, args.candidate):
        blk = report["rounds"][r]
        print(
            f"  {r:3s} gold@{WINDOW} = {blk['gold_at_k']} CI {blk['gold_ci95']} (n={blk['n_gold_items']}) | "
            f"neo toàn bộ {blk['anchor_rate_all']} | neo HUMAN {blk['anchor_rate_human']} (n={blk['n_anchor_human']}) | "
            f"thiếu retrieval_config {blk['rows_without_retrieval_config']}/{blk['n_items']}"
        )
    print(f"  cặp bất đồng: chỉ {args.baseline}={p['gold_flags']['only_baseline']}, chỉ {args.candidate}={p['gold_flags']['only_candidate']}")
    print(f"  McNemar p={p['mcnemar_exact']['p_two_sided']} | bootstrap delta={p['paired_bootstrap_gold_delta']['mean_diff']} "
          f"CI {p['paired_bootstrap_gold_delta']['ci95_percentile']}")
    for fam, d in p["by_family"].items():
        print(f"  {fam:8s} {d['baseline_rate']} -> {d['candidate_rate']} (delta {d['delta']:+.4f}, n={d['n_gold']}, McNemar p={d['mcnemar']['p_two_sided']})")
    for key, label in (("lost_in_candidate", f"mất ở {args.candidate}"), ("gained_in_candidate", f"được ở {args.candidate}")):
        mech = p["mechanism"][key]
        print(f"  {label}: n={mech['n']} nguyên nhân {mech['by_cause']} | cửa sổ 1-nguồn-chiếm-trọn {mech['n_window_taken_by_one_source']} | "
              f"vàng rơi hạng 7-12: {mech['n_gold_just_outside_window_7_to_12']}")
    if "third_round" in p and p["third_round"]:
        t = p["third_round"]
        print(f"  {t['round']}: gold@{WINDOW} {t['gold_at_k']} (vs {args.candidate} {t['vs_candidate']['delta']:+.4f}, "
              f"McNemar p={t['vs_candidate']['mcnemar']['p_two_sided']}), cứu lại {t['recovered_items_of_candidate_losses']} item mất ở {args.candidate}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
