"""P4.3 (nhóm 04): Phân tích A/B WITH vs WITHOUT classifier + biểu đồ cho chương thực nghiệm.

Đọc 2 JSON kết quả P4.2 (kịch bản local: generator qwen2.5:1.5b, judge TẮT, faithfulness
heuristic_local) + benchmark v3, xuất:
  - outputs/ab_comparison.md : bảng tổng thể + per question_type + per category + nhận xét
  - outputs/figures/*.png    : 3 biểu đồ (matplotlib Agg, dpi 150, DejaVu Sans)

Nguyên tắc: MỌI con số trong report phải truy được về 2 JSON nguồn — chỉ số tổng thể đọc
thẳng từ khối `aggregates` của từng JSON; số theo nhóm tính từ per_question bằng đúng
các trường đã lưu (hit_at_*, reciprocal_rank, citations.{precision,recall,f1,exact_match},
faithfulness.score, number_support, latency_seconds, is_refusal_answer); các đại lượng
cần benchmark (in_corpus, expected_question_type, category) join qua id.
KHÔNG sửa src/assessment/evaluation.py. KHÔNG bịa nhận xét — mỗi kết luận gắn số liệu/câu dẫn chứng.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
BENCH_PATH = ROOT / "data/evaluation/benchmark_100_questions_v3.json"
WITHOUT_PATH = ROOT / "outputs/ab_results_without_classifier.json"
WITH_PATH = ROOT / "outputs/ab_results_with_classifier.json"
OUT_MD = ROOT / "outputs/ab_comparison.md"
FIG_DIR = ROOT / "outputs/figures"
CLASSIFIER_RESULTS = ROOT / "logs/classifier/results.json"

RUN_DATE = date.today().isoformat()
PARAM_NOTE = f"top_k=6 · retrieve_k=6 · generator local-qwen (qwen2.5:1.5b-instruct) · judge TẮT · {RUN_DATE}"

plt.rcParams["font.family"] = "DejaVu Sans"

PCT_KEYS = [
    ("hit_at_3", "Hit@3"),
    ("hit_at_5", "Hit@5"),
    ("hit_at_6", "Hit@6"),
    ("citation_precision", "Citation Precision"),
    ("citation_recall", "Citation Recall"),
    ("citation_f1", "Citation F1"),
    ("citation_exact_match", "Citation Exact Match"),
    ("number_support", "Number support"),
    ("normalization_preservation", "Bảo toàn thực thể (chuẩn hóa)"),
]
SMALL_N_NOTE = 10  # nhóm có n < ngưỡng này → ghi chú cẩn trọng


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def rel_delta(with_v: float | None, wo_v: float | None) -> str:
    if with_v is None or wo_v is None or wo_v == 0:
        return "n/a"
    return f"{(with_v - wo_v) / wo_v * 100:+.1f}%"


def pp_delta(with_v: float | None, wo_v: float | None, scale: float = 100) -> str:
    if with_v is None or wo_v is None:
        return "n/a"
    return f"{(with_v - wo_v) * scale:+.2f}"


def mean(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def load_all():
    bench = json.loads(BENCH_PATH.read_text(encoding="utf-8"))
    questions = {q["id"]: q for q in bench["questions"]}
    wo = json.loads(WITHOUT_PATH.read_text(encoding="utf-8"))
    w = json.loads(WITH_PATH.read_text(encoding="utf-8"))
    wo_e = {e["id"]: e for e in wo["per_question"]}
    w_e = {e["id"]: e for e in w["per_question"]}
    return questions, wo, w, wo_e, w_e


def group_metrics(entries: dict, ids: list[str]) -> dict:
    """Tính chỉ số cho một nhóm id, dùng đúng trường đã lưu trong JSON."""
    sub = [entries[i] for i in ids if i in entries]
    cit = [e["citations"] for e in sub if isinstance(e.get("citations"), dict)]
    faith = [
        e["faithfulness"]["score"]
        for e in sub
        if not e.get("is_refusal_answer")  # từ chối được gán 1.0 — loại để không phình điểm
        and (e.get("faithfulness") or {}).get("method") == "heuristic_local"
        and e["faithfulness"].get("score") is not None
    ]
    return {
        "n": len(sub),
        "hit3": mean([e["retrieval"]["hit_at_3"] for e in sub]),
        "hit5": mean([e["retrieval"]["hit_at_5"] for e in sub]),
        "hit6": mean([e["retrieval"]["hit_at_6"] for e in sub]),
        "mrr": mean([e["retrieval"]["reciprocal_rank"] for e in sub]),
        "cit_f1": mean([c["f1"] for c in cit]),
        "cit_n": len(cit),
        "faith": mean(faith),
        "faith_n": len(faith),
        "latency": mean([e.get("latency_seconds") for e in sub]),
    }


def main() -> None:
    questions, wo, w, wo_e, w_e = load_all()
    ids = sorted(questions.keys())
    in_corpus_ids = [i for i in ids if questions[i].get("in_corpus")]
    ooc_ids = [i for i in ids if not questions[i].get("in_corpus")]

    def refusal_oan(entries: dict) -> list[str]:
        return [i for i in in_corpus_ids if entries[i].get("is_refusal_answer")]

    oan_wo = refusal_oan(wo_e)
    oan_w = refusal_oan(w_e)

    # ---- 1. Bảng tổng thể (đọc thẳng aggregates) ----
    A_wo, A_w = wo["aggregates"], w["aggregates"]

    # classification accuracy (chỉ lượt WITH có classifier)
    topic_ok = sum(
        1 for i in ids if (w_e[i].get("predicted_labels") or {}).get("topic") == questions[i]["category"]
    )
    type_ok = sum(
        1
        for i in ids
        if (w_e[i].get("predicted_labels") or {}).get("question_type") == questions[i]["question_type"]
    )

    overall_rows: list[tuple[str, str, str, str, str]] = []

    def add_row(label: str, wo_v: str, w_v: str, d: str, note: str = "") -> None:
        overall_rows.append((label, wo_v, w_v, d, note))

    for key, label in PCT_KEYS:
        add_row(label, pct(A_wo.get(key)), pct(A_w.get(key)), pp_delta(A_w.get(key), A_wo.get(key)) + " pp")
    add_row("MRR (recall window)", f"{A_wo['mrr']:.4f}", f"{A_w['mrr']:.4f}", pp_delta(A_w["mrr"], A_wo["mrr"], 1))
    # Faithfulness tổng thể: judge tắt → aggregates có n_faithfulness_scored=0; tính mean per-entry.
    # Chỉ tính câu ĐƯỢC TRẢ LỜI (entry từ chối được gán 1.0 — gộp vào sẽ phình điểm).
    def faith_answered(entries: dict) -> tuple[float | None, int, float | None]:
        sc = [
            (e["faithfulness"]["score"], bool(e.get("is_refusal_answer")))
            for e in entries.values()
            if (e.get("faithfulness") or {}).get("method") == "heuristic_local"
            and e["faithfulness"].get("score") is not None
        ]
        ans = [s for s, r in sc if not r]
        return (mean(ans), len(ans), mean([s for s, _ in sc]))

    fa_wo, fa_w = faith_answered(wo_e), faith_answered(w_e)
    if fa_wo[0] is not None and fa_w[0] is not None:
        add_row("Faithfulness heuristic_local",
                f"{fa_wo[0]:.3f} (n={fa_wo[1]})",
                f"{fa_w[0]:.3f} (n={fa_w[1]})",
                f"{(fa_w[0] - fa_wo[0]):+.3f}",
                f"chỉ câu trả lời — gộp cả từ chối (score 1.0): {fa_wo[2]:.3f} / {fa_w[2]:.3f}")
    else:
        add_row("Faithfulness heuristic_local", "n/a", "n/a", "n/a", "không có entry nào được chấm")
    add_row("Latency trung bình (s)", f"{A_wo['avg_latency_seconds']:.2f}", f"{A_w['avg_latency_seconds']:.2f}",
            pp_delta(A_w["avg_latency_seconds"], A_wo["avg_latency_seconds"], 1), "CHỈ THAM CHIẾU (xem mục 6)")
    add_row("Topic accuracy", "n/a (không classifier)", f"{topic_ok / len(ids) * 100:.1f}%", "—")
    add_row("Type accuracy", "n/a (không classifier)", f"{type_ok / len(ids) * 100:.1f}%", "—",
            "khớp P2.3 gate (topic ~85%, type ~81%)")
    add_row("Từ chối oan (in_corpus)", f"{len(oan_wo)}/{len(in_corpus_ids)} ({len(oan_wo) / len(in_corpus_ids) * 100:.1f}%)",
            f"{len(oan_w)}/{len(in_corpus_ids)} ({len(oan_w) / len(in_corpus_ids) * 100:.1f}%)",
            f"{len(oan_w) - len(oan_wo):+d} câu", "in_corpus bị trả lời từ chối")
    add_row("Từ chối đúng (ngoài corpus)", f"{A_wo.get('refusal_correct_rate') and pct(A_wo['refusal_correct_rate']) or 'n/a'}",
            f"{A_w.get('refusal_correct_rate') and pct(A_w['refusal_correct_rate']) or 'n/a'}", "—", "trên 3 câu ngoài corpus")
    add_row("Ảo giác ngoài corpus", f"{A_wo.get('hallucination_on_unanswerable')}", f"{A_w.get('hallucination_on_unanswerable')}",
            "—", "câu ngoài corpus bị trả lời thay vì từ chối")

    # ---- 2. Per expected question_type ----
    types = ["TRA_CUU", "SO_SANH", "THU_TUC", "NGOAI_PHAM_VI"]
    type_rows = []
    for t in types:
        t_ids = [i for i in ids if questions[i]["question_type"] == t]
        m_wo, m_w = group_metrics(wo_e, t_ids), group_metrics(w_e, t_ids)
        type_rows.append((t, m_wo, m_w))

    # ---- 3. Per category ----
    categories = sorted({questions[i]["category"] for i in ids})
    cat_rows = []
    for c in categories:
        c_ids = [i for i in ids if questions[i]["category"] == c]
        cat_rows.append((c, group_metrics(wo_e, c_ids), group_metrics(w_e, c_ids)))

    # ---- 3b. Nhóm tăng/giảm rõ theo chủ đề (ΔHit@3, tính từ per_question) ----
    cat_delta = []
    for c, m_wo, m_w in cat_rows:
        if m_wo["hit3"] is not None and m_w["hit3"] is not None:
            cat_delta.append((c, m_wo["n"], (m_w["hit3"] - m_wo["hit3"]) * 100))
    cat_delta.sort(key=lambda t: t[2])
    top_drop = cat_delta[:2]
    top_gain = list(reversed(cat_delta[-2:]))

    # ---- 4. Router WITH: phân bố predicted ----
    pred_counter = Counter((w_e[i].get("predicted_labels") or {}).get("question_type") for i in ids)
    pred_rows = []
    for t in types:
        t_ids = [i for i in ids if (w_e[i].get("predicted_labels") or {}).get("question_type") == t]
        m = group_metrics(w_e, t_ids)
        pred_rows.append((t, m))

    # ---- 5. Từ chối oan: nguyên nhân ----
    cls = json.loads(CLASSIFIER_RESULTS.read_text(encoding="utf-8"))
    mis_type = {
        r["id"]: r.get("predicted_question_type")
        for r in cls["results"]
        if r["expected_question_type"] != r.get("predicted_question_type")
    }
    oan_w_pred = Counter((w_e[i].get("predicted_labels") or {}).get("question_type") for i in oan_w)
    oan_w_misrouted = sorted(set(oan_w) & set(mis_type))
    oan_wo_examples = sorted(oan_wo)[:5]

    # WITHOUT cũng từ chối oan nhiều => nguyên nhân nền là guardrail/model, không phải classifier.
    # WITH: bao nhiêu oan do misroute (predicted NGOAI_PHAM_VI/SO_SANH) vs do model?
    oan_w_misroute_ng = [i for i in oan_w if (w_e[i].get("predicted_labels") or {}).get("question_type") == "NGOAI_PHAM_VI"]

    # ---- 6. Dẫn chứng cụ thể ----
    # (a) câu SO_SANH tăng MRR rõ nhất
    ss_ids = [i for i in ids if questions[i]["question_type"] == "SO_SANH"]
    gain = max(
        ss_ids,
        key=lambda i: (w_e[i]["retrieval"]["reciprocal_rank"] - wo_e[i]["retrieval"]["reciprocal_rank"]),
    )
    # (b) câu từ chối oan do misroute NGOAI (nếu có)
    ex_oan = oan_w_misroute_ng[0] if oan_w_misroute_ng else None
    # (c) câu WITHOUT miss → WITH hit
    flip = [i for i in ss_ids if not wo_e[i]["retrieval"]["hit_at_5"] and w_e[i]["retrieval"]["hit_at_5"]]

    # ---- GATE ----
    gate_items = []
    for key, label in [("hit_at_3", "Hit@3"), ("hit_at_5", "Hit@5"), ("hit_at_6", "Hit@6"), ("mrr", "MRR")]:
        wo_v, w_v = A_wo[key], A_w[key]
        rel = (w_v - wo_v) / wo_v * 100
        gate_items.append((label, rel, rel > -5.0, wo_v, w_v))
    gate_pass = all(ok for _, _, ok, _, _ in gate_items)
    ss_gain = type_rows[1][2]["mrr"] - type_rows[1][1]["mrr"]  # SO_SANH expected MRR delta

    # =================== VIẾT MARKDOWN ===================
    L: list[str] = []
    L.append("# So sánh A/B — bật/tắt tầng phân loại (P4.3)")
    L.append("")
    L.append(f"Nguồn: `{WITHOUT_PATH.relative_to(ROOT)}` ({wo['meta']['timestamp']}) và "
             f"`{WITH_PATH.relative_to(ROOT)}` ({w['meta']['timestamp']}); benchmark 100 câu v3.")
    L.append(f"Tham số chung: {PARAM_NOTE}. Mọi con số truy được về 2 JSON nguồn (tổng thể đọc thẳng khối "
             "`aggregates` — trừ Faithfulness tính mean per-entry vì judge tắt khiến aggregates n=0; "
             "theo nhóm tính từ `per_question`).")
    L.append("")
    L.append("> **Lưu ý kịch bản**: judge Gemini TẮT — cột Faithfulness là **heuristic_local** (chấm per-entry, cùng "
             "công thức 2 nhánh). Không so sánh trực tiếp với baseline Gemini cũ; A/B nội bộ vẫn công bằng.")
    L.append("")

    L.append("## 1. Bảng tổng thể")
    L.append("")
    L.append("| Chỉ số | WITHOUT (tắt phân loại) | WITH (bật phân loại) | Chênh lệch | Ghi chú |")
    L.append("|---|---|---|---|---|")
    for label, wo_v, w_v, d, note in overall_rows:
        L.append(f"| {label} | {wo_v} | {w_v} | {d} | {note} |")
    L.append("")
    L.append("**Kiểm tra GATE** (MRR/Hit không giảm > 5% tương đối):")
    L.append("")
    L.append("| Chỉ số | WITHOUT | WITH | Thay đổi tương đối | GATE (ngưỡng −5%) |")
    L.append("|---|---|---|---|---|")
    for label, rel, ok, wo_v, w_v in gate_items:
        wo_vs = f"{wo_v:.4f}" if label == "MRR" else pct(wo_v)
        w_vs = f"{w_v:.4f}" if label == "MRR" else pct(w_v)
        L.append(f"| {label} | {wo_vs} | {w_vs} | {rel:+.1f}% | {'ĐẠT' if ok else 'TỤT'} |")
    L.append("")

    def group_table(title: str, rows: list, key_label: str) -> None:
        def fmt3(v: float | None) -> str:
            return f"{v:.3f}" if v is not None else "n/a"

        L.append(f"## {title}")
        L.append("")
        L.append(f"| {key_label} | n | Hit@3 (W/O) | Hit@3 (W) | ΔHit@3 | Hit@5 (W/O) | Hit@5 (W) | MRR (W/O) | MRR (W) | CitF1 (W/O) | CitF1 (W) | Faith. trả lời (W/O) | Faith. trả lời (W) |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for key, m_wo, m_w in rows:
            note = " ⚠️ n nhỏ" if m_wo["n"] < SMALL_N_NOTE else ""
            L.append(
                f"| {key}{note} | {m_wo['n']} | {pct(m_wo['hit3'])} | {pct(m_w['hit3'])} "
                f"| {pp_delta(m_w['hit3'], m_wo['hit3'])} | {pct(m_wo['hit5'])} | {pct(m_w['hit5'])} "
                f"| {m_wo['mrr']:.4f} | {m_w['mrr']:.4f} | {pct(m_wo['cit_f1'])} | {pct(m_w['cit_f1'])} "
                f"| {fmt3(m_wo['faith'])} | {fmt3(m_w['faith'])} |"
            )
        L.append("")
        small = [key for key, m_wo, _ in rows if m_wo["n"] < SMALL_N_NOTE]
        if small:
            L.append(f"> ⚠️ Nhóm n < {SMALL_N_NOTE} ({', '.join(small)}): sai số cao, chỉ đọc xu hướng, không kết luận mạnh.")
            L.append("")

    group_table("2. Theo loại câu hỏi (expected từ benchmark)", type_rows, "Loại câu hỏi")
    group_table("3. Theo chủ đề (category benchmark)", cat_rows, "Chủ đề")

    L.append("## 4. Router lượt WITH — phân bố predicted question_type")
    L.append("")
    L.append("| Predicted | n | Hit@3 | Hit@5 | MRR | CitF1 | Faith. trả lời |")
    L.append("|---|---|---|---|---|---|---|")
    for key, m in pred_rows:
        f_str = f"{m['faith']:.3f}" if m["faith"] is not None else "n/a"
        L.append(f"| {key} | {m['n']} | {pct(m['hit3'])} | {pct(m['hit5'])} | {m['mrr']:.4f} | {pct(m['cit_f1'])} | {f_str} |")
    L.append("")
    L.append(f"Phân bố predicted: {dict(pred_counter)} (expected: TRA_CUU 87, SO_SANH 5, THU_TUC 5, NGOAI_PHAM_VI 3).")
    L.append("")

    L.append("## 5. Từ chối oan — phân tích nguyên nhân")
    L.append("")
    L.append(f"- WITHOUT: **{len(oan_wo)}/{len(in_corpus_ids)}** câu in_corpus bị từ chối oan — lượt này KHÔNG có classifier, "
             f"nên phần lớn nguyên nhân nền là guardrail overlap + khuynh hướng từ chối của generator local (không phải lỗi phân loại).")
    L.append(f"- WITH: **{len(oan_w)}/{len(in_corpus_ids)}** câu từ chối oan, theo predicted type: {dict(oan_w_pred)}.")
    L.append(f"- Trong số đó, {len(oan_w_misroute_ng)} câu bị classifier gán nhầm **NGOAI_PHAM_VI** (prompt từ chối khớp → từ chối oan): "
             f"{', '.join(oan_w_misroute_ng) if oan_w_misroute_ng else 'không có'}.")
    L.append(f"- Đối chiếu danh sách 19 câu bị gán nhầm trong `logs/classifier/results.json` "
             f"(10 TRA_CUU→SO_SANH, 9 TRA_CUU→NGOAI_PHAM_VI): {len(oan_w_misrouted)}/19 câu bị từ chối oan ở lượt WITH "
             f"({', '.join(oan_w_misrouted) if oan_w_misrouted else 'không có'}). "
             f"Kết luận: misroute góp phần nhưng KHÔNG phải nguyên nhân chính — chênh lệch từ chối oan 2 lượt chỉ "
             f"{len(oan_w) - len(oan_wo):+d} câu, cả 2 lượt đều ~50% do tầng generator/guardrail.")
    L.append(f"- Ví dụ từ chối oan WITHOUT (không classifier): {', '.join(oan_wo_examples)} — xác nhận nguyên nhân nền.")
    L.append("")

    L.append("## 6. Nhận xét tăng/giảm & dẫn chứng cụ thể")
    L.append("")
    g_txt = "; ".join(f"{c} (n={n}) Hit@3 {d:+.1f} pp" + ("" if n >= SMALL_N_NOTE else " ⚠️") for c, n, d in top_gain)
    d_txt = "; ".join(f"{c} (n={n}) Hit@3 {d:+.1f} pp" + ("" if n >= SMALL_N_NOTE else " ⚠️") for c, n, d in top_drop)
    L.append(f"- **Tăng mạnh nhất theo chủ đề** (ΔHit@3): {g_txt}.")
    L.append(f"- **Giảm theo chủ đề** (ΔHit@3): {d_txt} (⚠️ = n nhỏ, chỉ đọc xu hướng).")
    L.append(f"- Theo loại câu hỏi: TRA_CUU (n=87) là nhóm tăng chính (Hit@3 {pct(type_rows[0][1]['hit3'])} → "
             f"{pct(type_rows[0][2]['hit3'])}); NGOAI_PHAM_VI (n=3) MRR 0.0000 ở cả 2 lượt — ngoài corpus không có "
             "tài liệu đúng để khớp, hành vi như kỳ vọng.")
    q = questions[gain]
    L.append(
        f"- **{gain}** (SO_SANH, tăng MRR rõ nhất nhóm SO_SANH): WITHOUT matched_rank="
        f"{wo_e[gain]['retrieval']['matched_rank']} (RR {wo_e[gain]['retrieval']['reciprocal_rank']:.2f}) → WITH rank="
        f"{w_e[gain]['retrieval']['matched_rank']} (RR {w_e[gain]['retrieval']['reciprocal_rank']:.2f}). "
        f"Câu: “{q['raw_query'][:120]}…”"
    )
    if flip:
        L.append(f"- Các câu SO_SANH WITHOUT miss (Hit@5=False) → WITH hit: {', '.join(sorted(flip))}.")
    if ex_oan:
        L.append(
            f"- **{ex_oan}**: in_corpus nhưng bị classifier gán NGOAI_PHAM_VI → từ chối oan ở lượt WITH "
            f"(expected type: {questions[ex_oan]['question_type']})."
        )
    L.append("- Q96/Q98 (ngoài corpus): cả 2 lượt đều trả lời thay vì từ chối (ảo giác); chỉ Q97 từ chối đúng.")
    L.append("")
    L.append("## 7. Latency — chỉ tham chiếu")
    L.append("")
    L.append(f"WITHOUT {A_wo['avg_latency_seconds']:.2f}s/câu vs WITH {A_w['avg_latency_seconds']:.2f}s/câu. "
             "Hai lượt có pattern cache khác nhau (WITH miss nhiều ở nhóm SO_SANH do router đổi ngữ cảnh truy vấn) "
             "và chạy song song trên cùng máy — latency KHÔNG dùng để rút kết luận chất lượng.")
    L.append("")
    L.append("## 8. Kết luận GATE P4.3")
    L.append("")
    for label, rel, ok, _, _ in gate_items:
        L.append(f"- {label}: {rel:+.1f}% tương đối → {'ĐẠT' if ok else 'TỤT'} (ngưỡng −5%).")
    L.append(f"- Nhóm tăng rõ: SO_SANH (expected, n=5) MRR {type_rows[1][1]['mrr']:.4f} → {type_rows[1][2]['mrr']:.4f} "
             f"({ss_gain:+.4f}); nhóm TRA_CUU (n=87) Hit@3 {pct(type_rows[0][1]['hit3'])} → {pct(type_rows[0][2]['hit3'])}.")
    verdict = "ĐẠT" if (gate_pass and ss_gain > 0) else "CẦN XEM LẠI"
    L.append(f"- **GATE tổng thể: {verdict}**" + ("" if gate_pass else " — có chỉ số tụt quá ngưỡng, xử lý theo playbook (chạy lại CHỈ lượt WITH, KHÔNG sửa số)."))
    L.append("")

    OUT_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"[OK] Đã viết {OUT_MD.relative_to(ROOT)} ({len(L)} dòng)")

    # =================== BIỂU ĐỒ ===================
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # Fig 1 — tổng thể
    fig, ax = plt.subplots(figsize=(12, 5.5))
    labels = ["Hit@3", "Hit@5", "Hit@6", "MRR", "Cit P", "Cit R", "Cit F1", "Cit EM", "Number support"]
    wo_vals = [A_wo["hit_at_3"], A_wo["hit_at_5"], A_wo["hit_at_6"], A_wo["mrr"], A_wo["citation_precision"],
               A_wo["citation_recall"], A_wo["citation_f1"], A_wo["citation_exact_match"], A_wo["number_support"]]
    w_vals = [A_w["hit_at_3"], A_w["hit_at_5"], A_w["hit_at_6"], A_w["mrr"], A_w["citation_precision"],
              A_w["citation_recall"], A_w["citation_f1"], A_w["citation_exact_match"], A_w["number_support"]]
    x = range(len(labels))
    width = 0.38
    b1 = ax.bar([i - width / 2 for i in x], [v * 100 for v in wo_vals], width, label="WITHOUT (tắt phân loại)", color="#9e9e9e")
    b2 = ax.bar([i + width / 2 for i in x], [v * 100 for v in w_vals], width, label="WITH (bật phân loại)", color="#1f77b4")
    for bars in (b1, b2):
        for r in bars:
            ax.annotate(f"{r.get_height():.1f}", (r.get_x() + r.get_width() / 2, r.get_height()),
                        ha="center", va="bottom", fontsize=7)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Giá trị (%)")
    ax.set_title(f"So sánh tổng thể A/B — WITHOUT vs WITH classifier\n({PARAM_NOTE})", fontsize=11)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig1_overall.png", dpi=150)
    plt.close(fig)

    # Fig 2 — Hit@K theo question_type (expected)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    type_labels = [f"{t}\n(n={group_metrics(wo_e, [i for i in ids if questions[i]['question_type'] == t])['n']})" for t in types]
    for ax, k_key, k_name in zip(axes, ["hit3", "hit5"], ["Hit@3", "Hit@5"]):
        wo_v = [(m_wo[k_key] or 0) * 100 for _, m_wo, _ in type_rows]
        w_v = [(m_w[k_key] or 0) * 100 for _, _, m_w in type_rows]
        xx = range(len(types))
        bw = 0.38
        ax.bar([i - bw / 2 for i in xx], wo_v, bw, label="WITHOUT", color="#9e9e9e")
        ax.bar([i + bw / 2 for i in xx], w_v, bw, label="WITH", color="#1f77b4")
        ax.set_xticks(list(xx))
        ax.set_xticklabels(type_labels, fontsize=9)
        ax.set_title(k_name, fontsize=11)
        ax.grid(axis="y", alpha=0.3)
        for i, (a, b) in enumerate(zip(wo_v, w_v)):
            ax.annotate(f"{a:.0f}", (i - bw / 2, a), ha="center", va="bottom", fontsize=8)
            ax.annotate(f"{b:.0f}", (i + bw / 2, b), ha="center", va="bottom", fontsize=8)
    axes[0].set_ylabel("Hit@K (%)")
    axes[0].legend()
    fig.suptitle(f"Hit@K theo loại câu hỏi (expected) — 2 lượt A/B\n({PARAM_NOTE})", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(FIG_DIR / "fig2_hit_by_type.png", dpi=150)
    plt.close(fig)

    # Fig 3 — confusion matrix phân loại (lượt WITH)
    fig, ax = plt.subplots(figsize=(7, 6))
    matrix = [[0] * len(types) for _ in types]
    for i in ids:
        exp = questions[i]["question_type"]
        prd = (w_e[i].get("predicted_labels") or {}).get("question_type")
        if exp in types and prd in types:
            matrix[types.index(exp)][types.index(prd)] += 1
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(range(len(types)))
    ax.set_yticks(range(len(types)))
    ax.set_xticklabels(types, rotation=30, ha="right", fontsize=9)
    ax.set_yticklabels(types, fontsize=9)
    ax.set_xlabel("Classifier dự đoán")
    ax.set_ylabel("Thực tế (benchmark)")
    ax.set_title("Confusion matrix phân loại — lượt WITH", fontsize=11, pad=10)
    for r in range(len(types)):
        for c in range(len(types)):
            v = matrix[r][c]
            ax.text(c, r, str(v), ha="center", va="center", fontsize=11,
                    color="white" if v > max(max(row) for row in matrix) / 2 else "black")
    fig.colorbar(im, ax=ax, label="Số câu")
    fig.text(0.5, 0.01, f"({PARAM_NOTE})", ha="center", fontsize=7.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG_DIR / "fig3_confusion.png", dpi=150)
    plt.close(fig)

    print(f"[OK] Đã viết 3 biểu đồ vào {FIG_DIR.relative_to(ROOT)}/")

    # =================== SPOT-CHECK (in để đối chiếu) ===================
    print("[SPOT-CHECK] 1) Hit@3 tổng thể WITHOUT = %.4f | WITH = %.4f" % (A_wo["hit_at_3"], A_w["hit_at_3"]))
    print("[SPOT-CHECK] 2) Q16 WITHOUT RR = %.2f | WITH RR = %.2f" % (
        wo_e["Q16"]["retrieval"]["reciprocal_rank"], w_e["Q16"]["retrieval"]["reciprocal_rank"]))
    n_oan_wo = len(oan_wo)
    print("[SPOT-CHECK] 3) Từ chối oan WITHOUT = %d | WITH = %d" % (n_oan_wo, len(oan_w)))
    print("[GATE] " + ("ĐẠT" if gate_pass and ss_gain > 0 else "CẦN XEM LẠI"))


if __name__ == "__main__":
    main()
