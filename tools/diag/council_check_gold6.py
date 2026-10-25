#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Câu hỏi hội đồng #3 — **"`gold@6 = 0,5186` nghĩa là gì?"** (CHỈ-ĐỌC).

Script tái lập con số từ chính `verdicts_retrieval.jsonl` của từng round, đối chiếu với
chuỗi đã công bố trong các `gate_vs_*.json`, rồi nói rõ ba điều:

* mẫu số là gì (item CÓ chunk vàng — không phải toàn bộ 811 câu hỏi);
* một điểm vàng nghĩa là gì (đoạn văn bản chứa đáp án lọt vào 6 mảnh ngữ cảnh đưa cho model),
  và vì sao nó KHÔNG phải "trả lời đúng";
* điều kiện để hai con số gold@6 so được với nhau (cùng index, cùng chữ ký trọng tài).

Không gọi mạng/Gemini/Ollama. Lưu bằng chứng: `--json tmp/council_gold6.json`.

Mã thoát: 0 nếu MỌI con số công bố tái lập được; 1 nếu có dòng LỆCH.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
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

GOLD_RE = re.compile(
    r"gold@k (?P<b>\d+(?:[.,]\d+)?)->(?P<c>\d+(?:[.,]\d+)?) trên (?P<n>\d+) item có chunk vàng"
)
RETRIEVAL_ROUNDS = ("r0", "r1", "r2", "r4", "r11", "r12", "r13", "r14_repro_off", "r15_repro_on")


def sample_layer() -> dict[str, Any]:
    """Mẫu đo: 811 câu hỏi, bao nhiêu câu có chunk vàng để mà 'trúng'."""
    rows = kit.read_jsonl(ROOT / "data" / "loop" / "testset_v1.jsonl")
    by_family: dict[str, Counter] = {}
    for r in rows:
        c = by_family.setdefault(r.get("family") or "?", Counter())
        c["n"] += 1
        if r.get("gold_chunk_id") is not None:
            c["gold"] += 1
    table = [
        {"family": f, "n": c["n"], "n_gold": c["gold"], "n_khong_gold": c["n"] - c["gold"]}
        for f, c in sorted(by_family.items(), key=lambda kv: -kv[1]["n"])
    ]
    return {
        "n_items": len(rows),
        "n_gold_items": sum(1 for r in rows if r.get("gold_chunk_id") is not None),
        "n_no_gold": sum(1 for r in rows if r.get("gold_chunk_id") is None),
        "by_family": table,
        "nguồn": kit.rel(ROOT / "data" / "loop" / "testset_v1.jsonl"),
    }


def recompute(rnd: str, phase: str = "retrieval") -> dict[str, Any]:
    """gold@k tái lập từ verdicts của round + phân bố hạng của chunk vàng."""
    rows = kit.load_round(rnd, phase)
    n_gold, n_hit, rate = kit.gold_rate(rows)
    ranks = Counter(r.get("gold_rank_in_sources") for r in rows
                    if r.get("has_gold_chunk") and r.get("gold_in_top_k"))
    top_k = kit.settings_of(rnd, phase).get("top_k")
    return {
        "round": rnd,
        "phase": phase,
        "n_rows": len(rows),
        "n_gold_items": n_gold,
        "n_hit": n_hit,
        "n_miss": n_gold - n_hit,
        "gold_rate": rate,
        "top_k": top_k,
        "rank_dist": {str(k): v for k, v in sorted(ranks.items(), key=lambda kv: (kv[0] is None, kv[0]))},
        "referee": kit.settings_of(rnd, phase).get("referee"),
        "nguồn": kit.rel(kit.verdicts_path(rnd, phase)),
    }


def published_layer(calc: dict[str, dict]) -> list[dict[str, Any]]:
    """Mọi chuỗi 'gold@k X->Y' đã công bố trong gate_vs_*.json, đối chiếu số tính lại."""
    out = []
    for path in sorted((ROOT / "data" / "loop" / "rounds").glob("*/gate_vs_*retrieval.json")):
        d = kit.read_json(path)
        cand_round = path.parent.name
        for check in d.get("checks") or []:
            if check.get("rule") != "retrieval_not_degraded":
                continue
            m = GOLD_RE.search(check.get("detail") or "")
            if not m:
                out.append({"file": kit.rel(path), "round_cand": cand_round,
                            "detail": check.get("detail"), "loi": "khong doc duoc chuoi"})
                continue
            b, c = float(m.group("b")), float(m.group("c"))
            n_pub = int(m.group("n"))
            base_round = path.name.split("gate_vs_", 1)[1].removesuffix("_retrieval.json")
            cb = calc.get(base_round)
            cc = calc.get(cand_round)
            ok = (cb and cc and abs(cb["gold_rate"] - b) < 5e-5 and abs(cc["gold_rate"] - c) < 5e-5
                  and cb["n_gold_items"] == n_pub == cc["n_gold_items"])
            out.append({
                "file": kit.rel(path),
                "baseline": base_round, "candidate": cand_round,
                "cong_bo": f"{m.group('b')}->{m.group('c')} tren {n_pub} item",
                "tinh_lai": (f"{kit.fmt(cb['gold_rate'] if cb else None)}->"
                             f"{kit.fmt(cc['gold_rate'] if cc else None)} tren "
                             f"{cb['n_gold_items'] if cb else '—'} item"),
                "khop": bool(ok),
            })
    return out


def meaning_layer() -> dict[str, Any]:
    """gold@6 cao KHÔNG có nghĩa trả lời đúng — dẫn ngay từ round r7 (100 câu đã sinh chữ)."""
    rows = kit.load_round("r7", "full")
    n_gold, n_hit, rate = kit.gold_rate(rows)
    vc = Counter(r["verdict"] for r in rows)
    return {
        "round": "r7",
        "n_gold_items": n_gold,
        "n_hit": n_hit,
        "gold_rate": rate,
        "pass_correct": vc.get("PASS_CORRECT", 0),
        "overrefusal": vc.get("FAIL_OVERREFUSAL", 0),
        "retrieval_fail": vc.get("FAIL_RETRIEVAL", 0),
        "incomplete": vc.get("FAIL_INCOMPLETE", 0),
        "nguồn": kit.rel(kit.verdicts_path("r7", "full")),
    }


def oracle_layer(rnd: str = "r11") -> dict[str, Any]:
    """Trần của xếp hạng: chunk vàng có vào nổi POOL lớn hơn (12) hay không tồn tại trong index."""
    rows = kit.read_jsonl(ROOT / "data" / "loop" / "rounds" / rnd / "retrieval.jsonl")
    tot = hit6 = in_pool = 0
    ranks = Counter()
    for r in rows:
        item = r.get("item") or {}
        g = item.get("gold_chunk_id")
        if g is None:
            continue
        tot += 1
        rank = None
        for s in r.get("sources") or []:
            if s.get("chunk_id") == g:
                rank = s.get("rank")
                break
        ranks[rank] += 1
        if rank is not None:
            in_pool += 1
            if rank <= 6:
                hit6 += 1
    pool = max(len(r.get("sources") or []) for r in rows)
    return {
        "round": rnd,
        "n_gold_items": tot,
        "pool_size_ghi_duoc": pool,
        "gold_trong_top6": hit6,
        "gold_trong_pool": in_pool,
        "gold_khong_vao_pool": tot - in_pool,
        "rate_top6": round(hit6 / tot, 4),
        "rate_pool": round(in_pool / tot, 4),
        "rank_dist": {str(k): v for k, v in sorted(ranks.items(), key=lambda kv: (kv[0] is None, kv[0]))},
        "nguồn": kit.rel(ROOT / "data" / "loop" / "rounds" / rnd / "retrieval.jsonl"),
    }


def index_layer() -> dict[str, Any]:
    """Điều kiện so sánh: chunk vàng phải còn tồn tại trong index đang dùng."""
    p = ROOT / "data" / "loop" / "diag" / "corpus_check" / "corpus_check.json"
    d = kit.read_json(p)
    gc = d.get("gold_coverage") or {}
    return {
        "index_cu": d.get("index_signature_old"),
        "index_moi": d.get("index_signature_new"),
        "n_item_kiem_duoc": gc.get("n_checkable"),
        "n_mat_neo": gc.get("n_missing_gold"),
        "ty_le_mat_neo": gc.get("missing_rate"),
        "nguong_do": (gc.get("red_threshold")),
        "do": bool(gc.get("red")),
        "ket_luan": ("KHÔNG được so gold@6 giữa hai index cho tới khi PA-17 re-anchor xong"
                     if gc.get("red") else "so sánh được"),
        "nguồn": kit.rel(p),
    }


def repro_layer(calc: dict[str, dict]) -> dict[str, Any]:
    """Round tái lập (r14/r15) có cho từng item CÙNG cờ vàng như round gốc (r11/r12) không?"""
    out = {}
    for pair in (("r11", "r14_repro_off"), ("r12", "r15_repro_on")):
        a = kit.gold_flags(kit.load_round(pair[0], "retrieval"))
        b = kit.gold_flags(kit.load_round(pair[1], "retrieval"))
        so_lech = (sum(1 for k in a if a[k] != b.get(k))
                   + sum(1 for k in b if k not in a))
        out[" ".join(pair)] = {
            "n_item_a": len(a), "n_item_b": len(b),
            "giong_nhet_tung_item": a == b,
            "so_item_lech": so_lech,
            "rate_a": calc[pair[0]]["gold_rate"], "rate_b": calc[pair[1]]["gold_rate"],
        }
    m = ROOT / "data" / "loop" / "diag" / "chain_manifest_t7_repro_r0.json"
    manifest = kit.read_json(m) if m.exists() else {}
    return {"pairs": out, "manifest": kit.rel(m),
            "manifest_sha256": manifest.get("spec_sha256"),
            "env_ghim": (manifest.get("steps") or [{}])[0].get("env") if manifest else None}


def build() -> dict[str, Any]:
    calc = {r: recompute(r) for r in RETRIEVAL_ROUNDS if kit.verdicts_path(r, "retrieval").exists()}
    published = published_layer(calc)
    return {
        "cau_hoi": "`gold@6 = 0,5186` nghĩa là gì?",
        "dinh_nghia": [
            "chunk vàng = `item.gold_chunk_id` — đúng một chunk trong index chứa đoạn văn bản "
            "mà câu hỏi dẫn chứng (đăng ký sẵn trong testset_v1.jsonl).",
            "gold_in_top_k = chunk đó xuất hiện trong `sources[:top_k]` (top_k = 6) mà pipeline "
            "trả về cho bước sinh chữ.",
            "gold@k = (số item có chunk vàng lọt vào cửa sổ) / (số item CÓ chunk vàng) — "
            "mẫu số KHÔNG phải toàn bộ câu hỏi (gate.stats, tools/loop/gate.py).",
            "Đây là chỉ số PHA TRUY XUẤT: chưa sinh câu trả lời, nên không nói gì về văn bản cuối.",
        ],
        "mau": sample_layer(),
        "tinh_lai": calc,
        "cong_bo": published,
        "y_nghia_khong_phai_dung": meaning_layer(),
        "tran_xep_hang": oracle_layer(),
        "dieu_kien_index": index_layer(),
        "tai_lap": repro_layer(calc),
        "so_dong_lech": sum(1 for p in published if not p.get("khop", False)),
    }


def print_report(result: dict[str, Any]) -> None:
    kit.banner("CÂU HỎI 3 — `gold@6 = 0,5186` NGHĨA LÀ GÌ?", result["cau_hoi"])
    print("\n[1] Định nghĩa (nguyên văn từ dụng cụ đo):")
    for line in result["dinh_nghia"]:
        print(f"  · {line}")
    print(f"     {kit.src('tools/loop/verify.py')} (rank_of_gold/in_contexts) · "
          f"{kit.src('tools/loop/gate.py')} (gold_in_top_k_rate)")

    m = result["mau"]
    print("\n[2] Mẫu đo:")
    kit.kv("câu hỏi trong testset", m["n_items"], m["nguồn"])
    kit.kv("có chunk vàng (mẫu số của gold@6)", m["n_gold_items"])
    kit.kv("KHÔNG có chunk vàng (bị loại khỏi mẫu số)", m["n_no_gold"])
    print(kit.md_table(["family", "n", "có gold", "không gold"],
                       [[f["family"], f["n"], f["n_gold"], f["n_khong_gold"]]
                        for f in m["by_family"]]))
    print("     97 câu HUMAN + 14 câu REFUSE không có một chunk vàng duy nhất ⇒ gold@6 "
          "mù với 111 item; chúng dùng thang `expected_source_in_window` (anchor) thay thế.")

    print("\n[3] Tái lập gold@6 từng round (tính lại từ verdicts_retrieval.jsonl):")
    print(kit.md_table(
        ["round", "row", "item có gold", "trúng", "trượt", "gold@6", "phân bố hạng 1..6", "chữ ký"],
        [[c["round"], c["n_rows"], c["n_gold_items"], c["n_hit"], c["n_miss"], kit.fmt(c["gold_rate"]),
          " ".join(f"{k}:{v}" for k, v in c["rank_dist"].items() if k != "None"), c["referee"]]
         for c in result["tinh_lai"].values()]))

    print("\n[4] Đối chiếu số ĐÃ CÔNG BỐ trong gate_vs_*.json:")
    print(kit.md_table(["file", "baseline->candidate", "công bố", "tính lại", "khớp"],
                       [[p["file"], f'{p.get("baseline")}→{p.get("candidate")}',
                         p.get("cong_bo", "—"), p.get("tinh_lai", "—"),
                         "khớp" if p.get("khop") else "LỆCH"] for p in result["cong_bo"]]))
    kit.kv("số dòng LỆCH", result["so_dong_lech"])

    y = result["y_nghia_khong_phai_dung"]
    print("\n[5] gold@6 cao ≠ trả lời đúng (số của round r7, cùng index, 100 câu đã sinh chữ):")
    kit.kv(f'gold_in_top_k trên {y["n_gold_items"]} item có gold', f'{y["n_hit"]} = {kit.fmt(y["gold_rate"])}')
    kit.kv("PASS_CORRECT", y["pass_correct"])
    kit.kv("FAIL_OVERREFUSAL", y["overrefusal"])
    kit.kv("FAIL_RETRIEVAL", y["retrieval_fail"])
    kit.kv("FAIL_INCOMPLETE", y["incomplete"])
    print(f"     {kit.src(y['nguồn'])}")
    print("     ⇒ căn cứ đã nằm trước mặt model trong 80% ca, nhưng model chỉ trả lời đúng "
          "14% — gold@6 đo CỔNG ĐẦU, không đo chất lượng chữ.")

    o = result["tran_xep_hang"]
    print("\n[6] Trần của xếp hạng trên chính mẫu này (round r11):")
    kit.kv("cửa sổ ghi trong retrieval.jsonl", f'pool {o["pool_size_ghi_duoc"]} nguồn/item')
    kit.kv("chunk vàng vào top-6", f'{o["gold_trong_top6"]}/{o["n_gold_items"]} = {kit.fmt(o["rate_top6"])}')
    kit.kv("chunk vàng vào pool-12", f'{o["gold_trong_pool"]}/{o["n_gold_items"]} = {kit.fmt(o["rate_pool"])}')
    kit.kv("chunk vàng KHÔNG vào nổi pool", o["gold_khong_vao_pool"])
    print(f"     {kit.src(o['nguồn'])}")
    print(f"     ⇒ trần xếp hạng = {kit.fmt(o['rate_pool'])}; tối đa {o['gold_trong_pool'] - o['gold_trong_top6']} "
          "item chỉ có thể cứu bằng rerank, và "
          f"{o['gold_khong_vao_pool']} item là nút thắt RECALL (không phải thứ tự).")

    ix = result["dieu_kien_index"]
    print("\n[7] Điều kiện để hai con số so được với nhau:")
    kit.kv("index mà mọi round đang dùng", ix["index_cu"])
    kit.kv("index mới sau re-OCR", ix["index_moi"])
    kit.kv("mất neo vàng trên index mới",
           f'{ix["n_mat_neo"]}/{ix["n_item_kiem_duoc"]} = {kit.fmt(ix["ty_le_mat_neo"])} '
           f'(ngưỡng {kit.fmt(ix["nguong_do"], 2)}; '
           f'{"ĐỎ" if ix["do"] else "xanh"})')
    kit.kv("kết luận", ix["ket_luan"], ix["nguồn"])

    rp = result["tai_lap"]
    print("\n[8] Tái lập bằng một lệnh (T7):")
    for label, d in rp["pairs"].items():
        kit.kv(label, f'cờ vàng từng item giống nhau: {kit.dat(d["giong_nhet_tung_item"])} '
                      f'(gold@6 {kit.fmt(d["rate_a"])} vs {kit.fmt(d["rate_b"])}, {d["n_item_a"]} item)')
    kit.kv("manifest chuỗi tái lập", rp["manifest"], rp["manifest"])
    kit.kv("spec_sha256", rp["manifest_sha256"])
    if rp.get("env_ghim"):
        print("     env ghim trong manifest: " + ", ".join(f"{k}={v}" for k, v in rp["env_ghim"].items()))

    print("\n[9] Trả lời bằng một câu:")
    print(f"  · `gold@6 = {kit.fmt(result['tinh_lai']['r0']['gold_rate'])}` nghĩa là: trong 700 câu hỏi "
          f"CÓ sẵn đoạn văn bản chứa đáp án trong index, {result['tinh_lai']['r0']['n_hit']} câu "
          f"({kit.pct(result['tinh_lai']['r0']['n_hit'], result['tinh_lai']['r0']['n_gold_items'])}) "
          "dẫn đúng đoạn đó vào 6 mảnh ngữ cảnh đưa cho model ở cấu hình mặc định trước khi tối ưu.")
    print("  · Nó KHÔNG nói: câu trả lời cuối đúng hay sai; 111 câu không có chunk vàng; "
          "và cũng không so sánh được sang index khác khi chưa re-anchor (PA-17).")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", help="ghi bằng chứng ra tmp/<tên>.json (mặc định không ghi)")
    args = ap.parse_args(argv)
    result = build()
    print_report(result)
    kit.emit(result, args)
    return 1 if result["so_dong_lech"] else 0


if __name__ == "__main__":
    sys.exit(main())
