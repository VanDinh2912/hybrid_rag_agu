#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Câu hỏi hội đồng #1 — **"Hệ thống có bịa câu trả lời không?"** (CHỈ-ĐỌC).

In ra: định nghĩa 'bịa' của trọng tài (3 verdict), số recalculated theo từng round đã
đóng, khoảng tin cậy 95% đã công bố, danh sách TỪNG CA cụ thể kèm câu trả lời mẫu, và
điểm mù của thước đo (ca sai nhưng thước không thấy). Không có mục nào cần Gemini/mạng.

Lệnh: `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/council_check_fabrication.py`
(thêm `--json tmp/council_fabrication.json` để lưu bằng chứng).

Mã thoát: 0 nếu MỌI tỉ lệ tính lại khớp `round_summary_full.json` đã công bố và không có
bất thường; 1 nếu có ít nhất một dòng lệch (report phải giải trình, không được im).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
# Console Windows mặc định cp1252: in tiếng Việt có dấu sẽ văng UnicodeEncodeError và exit code 1,
# người tái lập đọc nhầm thành "máy kiểm KHÔNG ĐẠT" (D-36 — máy kiểm phải báo lỗi đúng nguyên nhân).
# Đặt lại stdout/stderr sang UTF-8 ngay lúc import; bọc try/except để bước này không bao giờ
# làm hỏng phép đo (kể cả khi chạy dưới pytest capsys).
for _dong in (sys.stdout, sys.stderr):
    try:
        _dong.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover - chỉ khi mang console không phải TextIOWrapper
        pass

for _p in (str(ROOT), str(ROOT / "tools" / "loop"), str(ROOT / "tools" / "diag")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.diag import council_kit as kit  # noqa: E402
from tools.loop import gate  # noqa: E402

SEVERE = kit.SEVERE_VERDICTS


def per_round(rnd: str) -> dict[str, Any]:
    """Một dòng bảng: số tái lập từ verdicts_full.jsonl + số đã công bố trong summary."""
    rows = kit.load_round(rnd, "full")
    summary = kit.read_json(kit.summary_path(rnd, "full"))
    ans = kit.answered_rows(rows)
    with_uns = [r for r in ans if r.get("unsupported")]
    counts = {v: sum(1 for r in rows if r.get("verdict") == v) for v in SEVERE}
    severe_rows = [r for r in rows if r.get("verdict") in SEVERE]
    recomputed = kit.fabrication_rate(rows)
    published = summary.get("fabrication_rate_on_answered")
    gs = [r.get("grounding_score") for r in ans if r.get("grounding_score") is not None]
    return {
        "round": rnd,
        "n_rows": len(rows),
        "n_answered": len(ans),
        "n_with_unsupported": len(with_uns),
        "fabrication_rate_recomputed": recomputed,
        "fabrication_rate_published": published,
        "khop": recomputed == published,
        "verdict_counts": counts,
        "n_severe": len(severe_rows),
        "n_severe_without_unsupported": sum(1 for r in severe_rows if not r.get("unsupported")),
        "n_answered_grounding_1": sum(1 for g in gs if abs(g - 1.0) < 1e-9),
        "mean_grounding": round(sum(gs) / len(gs), 4) if gs else None,
        "guard_flag_in_round": kit.settings_of(rnd).get("enable_answer_guard"),
        "nguồn_verdicts": kit.rel(kit.verdicts_path(rnd, "full")),
        "nguồn_summary": kit.rel(kit.summary_path(rnd, "full")),
    }


def severe_cases(rnd: str) -> list[dict[str, Any]]:
    """Mọi ca 'nói sai chủ động' của một round, kèm ngữ cảnh để hội đồng đọc trực tiếp."""
    out = []
    for r in kit.load_round(rnd, "full"):
        if r.get("verdict") not in SEVERE:
            continue
        uns = r.get("unsupported") or []
        out.append({
            "round": rnd,
            "id": r.get("id"),
            "family": r.get("family"),
            "split": r.get("split"),
            "verdict": r.get("verdict"),
            "gold_in_top_k": r.get("gold_in_top_k"),
            "n_unsupported": len(uns),
            "unsupported_texts": [f"{u.get('kind')}:{u.get('text')}" for u in uns][:6],
            "grounding_score": r.get("grounding_score"),
            "cau_hoi": (r.get("raw_query") or "")[:90],
            "tra_loi": (r.get("answer_preview") or "")[:140],
        })
    return out


def ci_rows() -> list[dict[str, Any]]:
    """CI 95% đã công bố cho fabrication rate (bootstrap 10.000 lượt, seed cố định)."""
    out = []
    for rnd in ("r5", "r7"):
        p = ROOT / "data" / "loop" / "diag" / f"metric_ci_{rnd}_full.json"
        d = kit.read_json(p)
        m = d["metrics"]["fabrication_rate_on_answered"]
        out.append({
            "round": rnd,
            "n_metric": m["n_metric"],
            "point": m["point_estimate"],
            "ci95": m["ci95"],
            "method": d["method"],
            "khop_diem_goc_vs_summary": m["point_estimate"] == kit.fabrication_rate(kit.load_round(rnd, "full")),
            "nguồn": kit.rel(p),
        })
    return out


def def_layers() -> list[dict[str, str]]:
    """Định nghĩa 'bịa': verdict -> điều kiện, lấy nguyên từ mã trọng tài đang chạy."""
    return [
        {"verdict": v, "dieu_kien": kit.NGHIA_SEVERE[v]} for v in SEVERE
    ]


def production_guard() -> dict[str, Any]:
    """Chế tài ở đường production (khác vòng đo): guard mặc định TẮT, ngưỡng đọc từ env."""
    saved = {k: os.environ.pop(k, None) for k in
             ("ENABLE_ANSWER_GUARD", "ANSWER_GUARD_MIN_SCORE", "ANSWER_GUARD_MAX_UNSUPPORTED")}
    try:
        import src.answer_guard as ag

        enabled = ag.answer_guard_enabled()
        min_score, max_unsupported = ag.refusal_thresholds()
        files = {
            "answer_guard": kit.rel(ROOT / "src" / "answer_guard.py"),
            "verify": kit.rel(ROOT / "tools" / "loop" / "verify.py"),
            "gate": kit.rel(ROOT / "tools" / "loop" / "gate.py"),
        }
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    return {
        "guard_mac_dinh_production_TAT": not enabled,
        "ANSWER_GUARD_MIN_SCORE_mac_dinh": min_score,
        "ANSWER_GUARD_MAX_UNSUPPORTED_mac_dinh": max_unsupported,
        "SEVERE_VERDICTS_trong_gate": sorted(gate.SEVERE_VERDICTS),
        "files": files,
    }


def build() -> dict[str, Any]:
    rounds = [per_round(r) for r in kit.rounds_with("full")]
    cases = [c for r in kit.rounds_with("full") for c in severe_cases(r)]
    tot = {
        "n_rounds": len(rounds),
        "n_rows": sum(r["n_rows"] for r in rounds),
        "n_answered": sum(r["n_answered"] for r in rounds),
        "n_with_unsupported": sum(r["n_with_unsupported"] for r in rounds),
        "n_severe": sum(r["n_severe"] for r in rounds),
        "n_severe_blind": sum(r["n_severe_without_unsupported"] for r in rounds),
        "by_verdict": {v: sum(r["verdict_counts"][v] for r in rounds) for v in SEVERE},
        # Cùng một item lặp qua nhiều round KHÔNG phải nhiều ca bịa khác nhau.
        "ids_by_verdict": {
            v: sorted({c["id"] for c in cases if c["verdict"] == v}) for v in SEVERE
        },
        "n_distinct_severe_items": len({c["id"] for c in cases}),
        "so_dong_lech": sum(1 for r in rounds if not r["khop"]),
    }
    return {
        "cau_hoi": "Hệ thống có bịa câu trả lời không?",
        "dinh_nghia": def_layers(),
        "tong_hop": tot,
        "theo_round": rounds,
        "cac_ca": cases,
        "ci": ci_rows(),
        "che_tai_production": production_guard(),
        "ket_luan": verdict_text(tot, rounds),
        "diem_mu": diem_mu(tot, rounds),
    }


def verdict_text(tot: dict, rounds: list[dict]) -> list[str]:
    b = tot["by_verdict"]
    fab_ids = tot["ids_by_verdict"]["FAIL_FABRICATED"]
    hou_ids = tot["ids_by_verdict"]["FAIL_HALLUCINATED_ON_UNANSWERABLE"]
    return [
        f"CÓ bịa, nhưng hiếm và đo được: {b['FAIL_FABRICATED']}/{tot['n_rows']} câu "
        f"({kit.pct(b['FAIL_FABRICATED'], tot['n_rows'], 2)}) rơi vào FAIL_FABRICATED theo định nghĩa chặt; "
        f"nhưng đó chỉ là {len(fab_ids)} item khác nhau ({', '.join(fab_ids)}) lặp lại ở nhiều round, "
        f"không phải {b['FAIL_FABRICATED']} lỗi độc lập.",
        f"Lớp sai nguy hiểm hơn là trả lời câu ngoài phạm vi: "
        f"{b['FAIL_HALLUCINATED_ON_UNANSWERABLE']} lượt / {len(hou_ids)} item khác nhau, và "
        f"{b['FAIL_CONFIRMED_FALSE_PREMISE']} lượt xác nhận tiền đề sai của câu bẫy.",
        f"Tổng {tot['n_severe']} lượt nặng nhưng chỉ {tot['n_distinct_severe_items']} item "
        "khác nhau — round dùng chung một mẫu 100 câu nên ca lặp là bình thường; "
        "con số để trình hội đồng là SỐ ITEM, không phải số lượt.",
        "Số tuyệt đối nhỏ vì phần lớn round có refusal rate cao — hệ thống thà từ chối; "
        "đó là lý do phải đọc cả refusal rate chứ không đọc riêng fabrication.",
        "Chế tài guardrail (src/answer_guard.py) ĐANG BẬT trong mọi round đo "
        "(settings.enable_answer_guard = 1) nhưng mặc định production là TẮT "
        "=> con số bịa đặt ĐO ĐƯỢC là con số của cấu hình có guard, không phải cấu hình mặc định.",
    ]


def diem_mu(tot: dict, rounds: list[dict]) -> list[str]:
    return [
        f"{tot['n_severe_blind']}/{tot['n_severe']} ca 'nói sai chủ động' có `unsupported` RỖNG "
        f"=> thước `fabrication_rate_on_answered` KHÔNG thấy chúng.",
        "Vì vậy 'fabrication = 0,0' ở r8/r9/r10 chỉ có nghĩa là 'không có khẳng định nào "
        "trái ngữ cảnh', KHÔNG có nghĩa là 'không trả lời sai câu ngoài phạm vi' "
        "(r8 vẫn có 12 câu loại đó).",
        "grounding_score ≈ 1,0 trên gần như mọi câu đã trả lời "
        f"({sum(r['n_answered_grounding_1'] for r in rounds)}/{tot['n_answered']}) "
        "=> mù với lớp 'đúng căn cứ nhưng lạc đề' (đã ghi ở DECISION_LOG T3).",
        "Chưa có nhãn tay của con người trên mẫu 60 câu (referee_agreement_r5.json "
        "n_filled = 0) => 'bịa' hiện là định nghĩa của code, chưa được con người xác nhận.",
    ]


def print_report(result: dict) -> None:
    kit.banner("CÂU HỎI 1 — HỆ THỐNG CÓ BỊA CÂU TRẢ LỜI KHÔNG?", result["cau_hoi"])
    print("\n[1] 'Bịa' là gì (định nghĩa đang chạy trong trọng tài):")
    print(kit.md_table(["verdict", "điều kiện"],
                       [[d["verdict"], d["dieu_kien"]] for d in result["dinh_nghia"]]))
    print(f"     {kit.src('tools/loop/verify.py')} (score_item) · "
          f"{kit.src('src/answer_guard.py')} (check_grounding) · "
          f"{kit.src('tools/loop/gate.py')} (SEVERE_VERDICTS)")

    print("\n[2] Số theo từng round đã đóng (tính lại từ verdicts, đối chiếu summary):")
    rows = []
    for r in result["theo_round"]:
        rows.append([
            r["round"], r["n_rows"], r["n_answered"], r["n_with_unsupported"],
            kit.fmt(r["fabrication_rate_recomputed"]), kit.fmt(r["fabrication_rate_published"]),
            "khớp" if r["khop"] else "LỆCH",
            f'{r["verdict_counts"]["FAIL_FABRICATED"]}/'
            f'{r["verdict_counts"]["FAIL_CONFIRMED_FALSE_PREMISE"]}/'
            f'{r["verdict_counts"]["FAIL_HALLUCINATED_ON_UNANSWERABLE"]}',
            r["n_severe"], r["n_severe_without_unsupported"],
            kit.fmt(r["mean_grounding"]), f'guard={r["guard_flag_in_round"]}',
        ])
    print(kit.md_table(
        ["round", "row", "đã-trả-lời", "có-khẳng-định-trái-ngữ-cảnh", "tỉ lệ (tái lập)",
         "tỉ lệ (công bố)", "đối chiếu", "FAB/CFP/HOU", "nặng", "nặng-mù", "grounding", "guard"],
        rows))
    t = result["tong_hop"]
    print(f"     Tổng: {t['n_rounds']} round · {t['n_rows']} dòng · {t['n_answered']} câu đã trả lời · "
          f"{t['n_with_unsupported']} câu có khẳng định trái ngữ cảnh · "
          f"nặng {t['n_severe']} (FAB {t['by_verdict']['FAIL_FABRICATED']} / "
          f"CFP {t['by_verdict']['FAIL_CONFIRMED_FALSE_PREMISE']} / "
          f"HOU {t['by_verdict']['FAIL_HALLUCINATED_ON_UNANSWERABLE']}) · "
          f"số dòng LỆCH = {t['so_dong_lech']}")
    print(f"     {kit.src('data/loop/rounds/<round>/verdicts_full.jsonl')} + "
          f"{kit.src('data/loop/rounds/<round>/round_summary_full.json')}")

    print("\n[3] Khoảng tin cậy 95% (bootstrap có cặp, 10.000 lượt, seed 20261023):")
    print(kit.md_table(
        ["round", "n mẫu số", "điểm", "CI 95%", "khớp summary", "nguồn"],
        [[c["round"], c["n_metric"], kit.fmt(c["point"]),
          f'[{kit.fmt(c["ci95"][0])}; {kit.fmt(c["ci95"][1])}]',
          "khớp" if c["khop_diem_goc_vs_summary"] else "LỆCH", c["nguồn"]] for c in result["ci"]]))

    print("\n[4] Từng ca cụ thể (đọc được tại chỗ, không cần chạy lại round):")
    print(kit.md_table(
        ["round", "id", "family", "verdict", "gold trong cửa sổ", "trái ngữ cảnh", "khẳng định"],
        [[c["round"], c["id"], c["family"], c["verdict"], kit.fmt(1 if c["gold_in_top_k"] else 0, 0),
          c["n_unsupported"], ", ".join(c["unsupported_texts"]) or "(không nêu từng khẳng định)"]
         for c in result["cac_ca"]]))
    print("     Ngữ cảnh từng ca: `tra_loi`/`cau_hoi` có trong --json; "
          f"{kit.src('data/loop/rounds/<round>/full.jsonl')}")
    ids = result["tong_hop"]["ids_by_verdict"]
    for v in SEVERE:
        print(f"     {v}: {len(ids[v])} item khác nhau"
              + (f" — {', '.join(ids[v])}" if ids[v] else ""))

    g = result["che_tai_production"]
    print("\n[5] Chế tài (guardrail production) — khác với chế tài ĐO:")
    kit.kv("mặc định production TẮT (ENABLE_ANSWER_GUARD=0)", g["guard_mac_dinh_production_TAT"],
           "src/answer_guard.py")
    kit.kv("ANSWER_GUARD_MIN_SCORE mặc định", g["ANSWER_GUARD_MIN_SCORE_mac_dinh"])
    kit.kv("ANSWER_GUARD_MAX_UNSUPPORTED mặc định", g["ANSWER_GUARD_MAX_UNSUPPORTED_mac_dinh"])
    kit.kv("SEVERE_VERDICTS trong gate", ", ".join(g["SEVERE_VERDICTS_trong_gate"]), "tools/loop/gate.py")

    print("\n[6] Điểm mù của thước (phải nói trước hội đồng, không giấu):")
    for line in result["diem_mu"]:
        print(f"  · {line}")

    print("\n[7] Trả lời:")
    for line in result["ket_luan"]:
        print(f"  · {line}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", help="ghi bằng chứng ra tmp/<tên>.json (mặc định không ghi)")
    args = ap.parse_args(argv)
    result = build()
    print_report(result)
    kit.emit(result, args)
    return 1 if result["tong_hop"]["so_dong_lech"] else 0


if __name__ == "__main__":
    sys.exit(main())
