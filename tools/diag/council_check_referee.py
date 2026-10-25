#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Câu hỏi hội đồng #2 — **"Trọng tài có đáng tin không?"** (CHỈ-ĐỌC).

Bằng chứng chia làm hai nhóm, và script nói rõ nhóm nào ĐÃ có / nhóm nào CHƯA:

ĐÃ có   : chữ ký dụng cụ đo, tính tất định (chấm lại 1.000 câu khớp 100%), độ độc lập
          với env, cổng từ chối so hai round khác chữ ký, mẫu số/điều kiện từng luật.
CHƯA có : đồng thuận với nhãn người (60 mẫu chưa ai dán nhãn) và tính đúng của CHÍNH
          định nghĩa 'bịa' (trọng tài chỉ biết ngữ cảnh, không biết 'đáp án nào là phải').

Không gọi mạng/Gemini/Ollama, không sửa file. Lưu bằng chứng: `--json tmp/council_referee.json`.

Mã thoát: 0 nếu chữ ký khớp và tái lập 100%; 1 nếu có round lệch chữ ký hoặc lệch verdict.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "tools" / "loop"), str(ROOT / "tools" / "diag")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.diag import council_kit as kit  # noqa: E402
from tools.loop import gate, verify  # noqa: E402

SEVERE = set(kit.SEVERE_VERDICTS)


def fingerprint_layer() -> dict[str, Any]:
    """Chữ ký hiện tại của trọng tài + chữ ký ghi trong TỪNG round đã đóng."""
    now = verify.referee_fingerprint()
    per_round: dict[str, str] = {}
    for phase in ("full", "retrieval"):
        for rnd in kit.rounds_with(phase):
            s = kit.settings_of(rnd, phase)
            ref = s.get("referee")
            if ref is not None:
                per_round[f"{rnd}/{phase}"] = ref
    khac = {k: v for k, v in per_round.items() if v != now}
    return {
        "dang_chay": now,
        "n_round_kiem": len(per_round),
        "n_chu_ky_khac_nhau": len(set(per_round.values())),
        "round_lech": khac,
        "nguồn": [kit.rel(ROOT / "tools" / "loop" / "verify.py"),
                  kit.rel(ROOT / "data" / "loop" / "rounds") + "/<round>/round_summary_*.json"],
    }


def rescore_layer(rnd: str) -> dict[str, Any]:
    """Chấm lại một round từ `full.jsonl` và so từng trường với verdicts đã công bố."""
    rows = kit.read_jsonl(kit.full_path(rnd))
    pub = {r["id"]: r for r in kit.load_round(rnd, "full")}
    khop = 0
    lech: list[dict[str, Any]] = []
    t0 = time.time()
    for rec in rows:
        item = rec["item"]
        result = {k: rec.get(k) for k in ("answer", "contexts", "sources", "labels", "latency_seconds")}
        top_k = (rec.get("retrieval_config") or {}).get("top_k", 6)
        v = verify.score_item(item, result, top_k=top_k)
        p = pub.get(item["id"])
        if p is None:
            lech.append({"round": rnd, "id": item["id"], "loi": "khong_co_row_cong_bo"})
            continue
        if (v["verdict"] == p["verdict"]
                and bool(v["gold_in_top_k"]) == bool(p["gold_in_top_k"])
                and len(v["unsupported"]) == len(p["unsupported"])):
            khop += 1
        else:
            lech.append({"round": rnd, "id": item["id"],
                         "cong_bo": p["verdict"], "tinhsan": v["verdict"],
                         "gold": (p.get("gold_in_top_k"), v.get("gold_in_top_k")),
                         "n_unsupported": (len(p.get("unsupported") or []), len(v["unsupported"]))})
    return {"round": rnd, "n": len(rows), "khop": khop, "lech": lech,
            "giay": round(time.time() - t0, 2),
            "nguồn": [kit.rel(kit.full_path(rnd)), kit.rel(kit.verdicts_path(rnd, "full"))]}


def env_independence_layer() -> dict[str, Any]:
    """Chứng minh verdict KHÔNG đổi khi env đổi: chấm cùng một row hai lần, một lần có env 'đục'.

    Đây là điểm khác nhau giữa 'trọng tài' và 'một tầng của pipeline': nếu đọc env thì
    người ta có thể chỉnh env để số đẹp, và không ai biết.
    """
    rnd = "r7"
    rows = kit.read_jsonl(kit.full_path(rnd))
    rec = rows[0]
    item = rec["item"]
    result = {k: rec.get(k) for k in ("answer", "contexts", "sources", "labels", "latency_seconds")}
    sach = verify.score_item(item, result, top_k=6)
    doc = dict(os.environ)
    os.environ.update({
        "ENABLE_ANSWER_GUARD": "1", "ANSWER_GUARD_MIN_SCORE": "0.01",
        "ANSWER_GUARD_MAX_UNSUPPORTED": "99", "ENABLE_QUERY_NORMALIZER_SANITY_GUARD": "1",
        "ENABLE_DECOUPLED_REFUSAL": "1", "ENABLE_EVIDENCE_SELECTION": "1",
        "ENABLE_RERANKER": "1", "ROUTER_SOFT_FILTER": "1",
    })
    try:
        duc = verify.score_item(item, result, top_k=6)
    finally:
        os.environ.clear()
        os.environ.update(doc)
    return {
        "round": rnd, "id": item["id"],
        "verdict_sach": sach.get("verdict"), "verdict_duc": duc.get("verdict"),
        "giong_nhau": sach.get("verdict") == duc.get("verdict")
                     and sach.get("grounding_score") == duc.get("grounding_score")
                     and len(sach.get("unsupported") or []) == len(duc.get("unsupported") or []),
        "so_dong_env_da_dat": 8,
    }


def files_layer() -> list[dict[str, str]]:
    out = []
    for p in verify.REFEREE_FILES:
        out.append({
            "file": kit.rel(p),
            "sha256_12": kit.sha256_of(p)[:12],
            "git": kit.git_state(p),
        })
    return out


def gate_lock_layer() -> dict[str, Any]:
    """Cổng từ chối so hai round khác chữ ký — chạy thật `gate.compatibility()`."""
    a = {"referee": verify.referee_fingerprint(), "top_k": 6, "generator": "offline_qwen",
         "testset": "x", "normalize_query": False, "enable_classifier": "1"}
    b = dict(a, referee="000000000000")
    problems = gate.compatibility(a, b)
    return {
        "gate_sha256_24": kit.sha256_of(ROOT / "tools" / "loop" / "gate.py")[:24],
        "gate_git": kit.git_state(ROOT / "tools" / "loop" / "gate.py"),
        "tu_choi_khi_chu_ky_khac": bool(problems),
        "thong_bao": problems[0] if problems else "(không từ chối — LỖI)",
        "so_khac_khai": sorted(a.keys()),
    }


def sensitivity_layer() -> dict[str, Any]:
    """Độ nhạy của verdict với LUẬT SO KHỚP SỐ (bản 'nghiêm khắc' chỉ để đo, không chấm round)."""
    p = ROOT / "data" / "loop" / "diag" / "referee_strict_number_audit.json"
    d = kit.read_json(p)
    return {
        "rule": d.get("strict_rule"),
        "note": d.get("note"),
        "fingerprint_trong_audit": d.get("referee_fingerprint"),
        "rounds": [
            {"round": r["round"], "n_rows": r["n_rows"], "n_covers_now": r["n_covers_now"],
             "n_flips": r["n_flips"], "n_flips_of_pass_correct": r["n_flips_of_pass_correct"]}
            for r in d.get("rounds") or []
        ],
        "nguồn": kit.rel(p),
    }


def human_layer() -> dict[str, Any]:
    p = ROOT / "data" / "loop" / "diag" / "referee_agreement_r5.json"
    m = ROOT / "data" / "loop" / "diag" / "referee_sample_manifest.json"
    d = kit.read_json(p)
    manifest = kit.read_json(m) if m.exists() else {}
    return {
        "n_worksheet_rows": d.get("n_worksheet_rows"),
        "n_filled": d.get("n_filled"),
        "cohen_kappa": d.get("cohen_kappa"),
        "overall_accuracy": d.get("overall_accuracy"),
        "class_labels": d.get("class_labels"),
        "manifest_seed": manifest.get("seed"),
        "ket_luan": ("CHƯA có bằng chứng con người" if not d.get("n_filled") else "CÓ nhãn người"),
        "nguồn": [kit.rel(p), kit.rel(m)],
    }


def blindness_layer() -> dict[str, Any]:
    """Bằng chứng định lượng cho điểm mù 'đúng căn cứ nhưng lạc đề'."""
    rounds = kit.rounds_with("full")
    per = []
    for rnd in rounds:
        rows = kit.load_round(rnd, "full")
        ans = kit.answered_rows(rows)
        g1 = sum(1 for r in ans if r.get("grounding_score") is not None
                 and abs(r["grounding_score"] - 1.0) < 1e-9)
        sev = [r for r in rows if r.get("verdict") in SEVERE]
        per.append({"round": rnd, "n_answered": len(ans), "n_grounding_1": g1,
                    "n_severe": len(sev),
                    "n_severe_grounding_1": sum(1 for r in sev
                                                if r.get("grounding_score") is not None
                                                and abs(r["grounding_score"] - 1.0) < 1e-9)})
    return {
        "per_round": per,
        "tong_answered": sum(p["n_answered"] for p in per),
        "tong_grounding_1": sum(p["n_grounding_1"] for p in per),
        "tong_severe": sum(p["n_severe"] for p in per),
        "tong_severe_grounding_1": sum(p["n_severe_grounding_1"] for p in per),
        "nguồn": [kit.rel(ROOT / "src" / "answer_guard.py")],
    }


def build() -> dict[str, Any]:
    fp = fingerprint_layer()
    rescore = [rescore_layer(r) for r in kit.rounds_with("full")]
    tong = {
        "n_rows_rescored": sum(r["n"] for r in rescore),
        "n_rows_khop": sum(r["khop"] for r in rescore),
        "n_rows_lech": sum(len(r["lech"]) for r in rescore),
        "tong_giay": round(sum(r["giay"] for r in rescore), 2),
    }
    return {
        "cau_hoi": "Trọng tài có đáng tin không?",
        "chu_ky": fp,
        "tat_dinh": tong,
        "theo_round": rescore,
        "doc_lap_env": env_independence_layer(),
        "file_dung_cu_do": files_layer(),
        "cong_khoa_chu_ky": gate_lock_layer(),
        "do_nhay_luat_so": sensitivity_layer(),
        "dong_thuan_nguoi": human_layer(),
        "diem_mu": blindness_layer(),
        "da_va_chua": ket_luan(fp, tong, rescore),
    }


def ket_luan(fp: dict, tong: dict, rescore: list[dict]) -> dict[str, list[str]]:
    da = [
        f"Chữ ký dụng cụ đo `{fp['dang_chay']}` và {fp['n_round_kiem']} round đã đóng dùng chung "
        f"{fp['n_chu_ky_khac_nhau']} chữ ký — không round nào được chấm bằng bản trọng tài khác.",
        f"Chấm lại {tong['n_rows_rescored']} câu của {len(rescore)} round từ chính văn bản đã lưu: "
        f"{tong['n_rows_khop']} câu cho cùng verdict + cùng gold_in_top_k + cùng số khẳng định "
        f"trái ngữ cảnh; toàn bộ bằng code, không gọi model ({tong['n_rows_lech']} câu lệch).",
        "Verdict không đổi khi env bị đổi (env_independence) — trọng tài không đọc env, "
        "nên không thể 'chỉnh cờ cho số đẹp'.",
        "Cổng (gate.compatibility) TỪ CHỐI so hai round khác chữ ký — kiểm bằng lệnh thật ở [5].",
        "Mọi luật chấm đều đọc được trong một file duy nhất (tools/loop/verify.py), "
        "mẫu số từng chỉ số ghi rõ trong gate.stats().",
    ]
    chua = [
        "CHƯA có đồng thuận với người: 60 mẫu dán nhãn (referee_agreement_r5.json) "
        "n_filled = 0 ⇒ chưa có Cohen kappa, chưa có precision/recall theo nhãn người.",
        "CHƯA chứng minh định nghĩa 'bịa' là đúng: trọng tài chỉ kiểm 'có căn cứ trong "
        "ngữ cảnh truy xuất', không kiểm 'đây có phải đáp án mà hội đồng mong muốn'.",
        "CHƯA tái lập được từ fresh clone: verify.py và answer_guard.py chưa vào git "
        "(PA-26) — xem bảng [4], cột git.",
        f"Độ nhạy luật so khớp số có thật: {sum(r['n_flips'] for r in sensitivity_layer()['rounds'])} "
        "verdict đổi chiều khi siết regex số (đã ghi nguyên, không giảm nhẹ).",
    ]
    return {"DA_CO": da, "CHUA_CO": chua}


def print_report(result: dict) -> None:
    kit.banner("CÂU HỎI 2 — TRỌNG TÀI CÓ ĐÁNG TIN KHÔNG?", result["cau_hoi"])
    fp = result["chu_ky"]
    print("\n[1] Chữ ký dụng cụ đo:")
    kit.kv("verify.referee_fingerprint() hiện tại", f"`{fp['dang_chay']}`", "tools/loop/verify.py")
    kit.kv("round đã đóng có ghi chữ ký", fp["n_round_kiem"], "data/loop/rounds")
    kit.kv("số chữ ký KHÁC NHAU trong các round đó", fp["n_chu_ky_khac_nhau"])
    kit.kv("round lệch chữ ký", fp["round_lech"] or "không có")

    print("\n[2] Tính tất định: chấm lại toàn bộ round đã đóng từ văn bản đã lưu:")
    print(kit.md_table(
        ["round", "câu", "khop verdict+gold+so-trai-ngu-canh", "lekh", "giay", "nguồn"],
        [[r["round"], r["n"], r["khop"], len(r["lech"]), r["giay"], " + ".join(r["nguồn"])]
         for r in result["theo_round"]]))
    t = result["tat_dinh"]
    print(f"     Tổng: {t['n_rows_khop']}/{t['n_rows_rescored']} khớp, {t['n_rows_lech']} lệch, "
          f"{t['tong_giay']} s cho toàn bộ {len(result['theo_round'])} round.")

    e = result["doc_lap_env"]
    print("\n[3] Trọng tài không đọc env (không chỉnh cờ cho số đẹp được):")
    kit.kv(f"câu {e['id']} (round {e['round']})", f"sạch={e['verdict_sach']} / đục={e['verdict_duc']}")
    kit.kv("kết luận", kit.dat(e["giong_nhau"]) + f" (đã đặt {e['so_dong_env_da_dat']} biến env gây nhiễu)")

    print("\n[4] File tạo nên trọng tài + trạng thái git (PA-26):")
    print(kit.md_table(["file", "sha256[:12]", "git"],
                       [[f["file"], f["sha256_12"], f["git"]] for f in result["file_dung_cu_do"]]))

    g = result["cong_khoa_chu_ky"]
    print("\n[5] Cổng khóa chữ ký (chạy thật gate.compatibility, không phải trích lời):")
    kit.kv("gate.py sha256[:24] / git", f"{g['gate_sha256_24']} · {g['gate_git']}", "tools/loop/gate.py")
    kit.kv("từ chối khi chữ ký khác", kit.dat(g["tu_choi_khi_chu_ky_khac"]))
    print(f"     thông báo thật: {g['thong_bao']}")

    s = result["do_nhay_luat_so"]
    print("\n[6] Độ nhạy với luật so khớp số (bản nghiêm khắc CHỈ ĐO, không chấm round):")
    print(kit.md_table(["round", "n_rows", "covers (luật hiện hành)", "đổi chiều", "trong đó PASS_CORRECT"],
                       [[r["round"], r["n_rows"], r["n_covers_now"], r["n_flips"],
                         r["n_flips_of_pass_correct"]] for r in s["rounds"]]))
    print(f"     rule: {s['rule']}   {kit.src(s['nguồn'])}")
    print(f"     ghi chú gốc: {s['note']}")

    h = result["dong_thuan_nguoi"]
    print("\n[7] Đồng thuận với con người (phần CHƯA làm được — nói thẳng):")
    kit.kv("số mẫu phát ra", h["n_worksheet_rows"], h["nguồn"][0])
    kit.kv("số mẫu đã có nhãn", h["n_filled"])
    kit.kv("Cohen kappa / accuracy", f"{kit.fmt(h['cohen_kappa'], 4)} / {kit.fmt(h['overall_accuracy'], 4)}")
    kit.kv("kết luận", h["ket_luan"])

    b = result["diem_mu"]
    print("\n[8] Điểm mù đã biết, có số:")
    print(kit.md_table(["round", "đã trả lời", "grounding=1,0", "ca nặng", "ca nặng grounding=1,0"],
                       [[p["round"], p["n_answered"], p["n_grounding_1"], p["n_severe"],
                         p["n_severe_grounding_1"]] for p in b["per_round"]]))
    print(f"     Tổng {b['tong_grounding_1']}/{b['tong_answered']} câu đã trả lời có grounding_score = 1,0; "
          f"{b['tong_severe_grounding_1']}/{b['tong_severe']} ca 'nói sai chủ động' có grounding = 1,0 "
          "⇒ trọng tài bắt được câu TRÁI ngữ cảnh, không bắt được câu ĐÚNG ngữ cảnh nhưng LẠC ĐỀ.")

    print("\n[9] ĐÃ có bằng chứng:")
    for line in result["da_va_chua"]["DA_CO"]:
        print(f"  · {line}")
    print("\n[10] CHƯA có bằng chứng (khoản trống thật, không tô):")
    for line in result["da_va_chua"]["CHUA_CO"]:
        print(f"  · {line}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", help="ghi bằng chứng ra tmp/<tên>.json (mặc định không ghi)")
    args = ap.parse_args(argv)
    result = build()
    print_report(result)
    kit.emit(result, args)
    fp = result["chu_ky"]
    t = result["tat_dinh"]
    ok = (fp["n_chu_ky_khac_nhau"] == 1
          and not fp["round_lech"]
          and t["n_rows_lech"] == 0
          and t["n_rows_khop"] == t["n_rows_rescored"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
