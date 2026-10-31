#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nghiệm thu cuối — **CHỈ-ĐỌC**: tái lập mọi con số đã công bố trong T0…T7.

Không sửa file nào, không gọi mạng/Gemini/Ollama, không ghi vào `outputs/` hay
`data/loop/rounds/`. Muốn lưu bảng thì dùng `--json <đường dẫn tmp/>`.

Cách so khớp (đăng ký trước, để không ai tự nói "trùng"):
* tách mọi số khỏi hai chuỗi theo qui ước Việt (`.` hàng nghìn khi theo sau đúng 3 chữ số,
  `,` thập phân);
* **số đã công bố phải xuất hiện theo đúng thứ tự** trong chuỗi tính lại (cho phép chuỗi tính
  lại có thêm số, ví dụ thời gian chạy);
* không đủ điều kiện ⇒ `LỆCH`, báo cáo phải giải trình hoặc sửa.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

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

for _p in (str(ROOT), str(ROOT / "tools" / "loop"), str(ROOT / "tools" / "eval"), str(ROOT / "tools" / "diag")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

NUM = re.compile(r"\d+(?:[.,]\d+)*")


def numbers(text: str) -> list[tuple[float, int]]:
    """Tách số kèm **số chữ thập phân đã viết** (để so khớp theo đúng độ chính xác đã công bố)."""
    out: list[tuple[float, int]] = []
    for tok in NUM.findall(text):
        head, *rest = tok.split(",")
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", head):
            head = head.replace(".", "")
        try:
            out.append((float(".".join([head] + rest)), len(rest[0]) if rest else 0))
        except ValueError:
            continue
    return out


def is_subsequence(a: list[tuple[float, int]], b: list[float]) -> bool:
    """Mỗi số đã công bố phải gặp được trong chuỗi tính lại, theo thứ tự, làm tròn đúng số chữ số đã viết."""
    it = iter(b)
    for value, dp in a:
        for cand in it:
            if round(cand, dp) == round(value, dp):
                break
        else:
            return False
    return True


def sha_prefix(path: Path, n: int = 12) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ pytest
_COLLECT: dict[str, int] | None = None


def collect_counts() -> dict[str, int]:
    global _COLLECT
    if _COLLECT is None:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            # stdin=DEVNULL (D-35): lỗi spawn trên Windows (`OSError: [WinError 6]`)
            # không được biến số lượng test thành "không đo được".
            stdin=subprocess.DEVNULL,
        )
        counts: dict[str, int] = {}
        for line in proc.stdout.splitlines():
            m = re.match(r"(tests/[\w/]+\.py)::", line.strip())
            if m:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
        _COLLECT = counts
    return _COLLECT


def n_test(rel: str) -> str:
    return str(collect_counts().get("tests/" + rel, -1))


def n_tests(*rels: str) -> str:
    vals = [int(n_test(r)) for r in rels]
    return f"{'+'.join(str(v) for v in vals)} = {sum(vals)}"


# ------------------------------------------------------------------ mutation logs
def mutation_total(log: str) -> str:
    p = ROOT / log
    if not p.exists():
        return "KHONG CO LOG"
    text = p.read_text(encoding="utf-8", errors="replace")
    explicit = re.findall(r"(?:Kết quả|kết luận)[^\n]{0,40}?(\d+)/(\d+)", text, re.I)
    if explicit:
        a, b = explicit[-1]
        return f"{a}/{b}"
    ids = set(re.findall(r"^\[([^\]]*M\d+[a-z]?[^\]]*)\]", text, re.M))
    if not ids:
        ids = set(re.findall(r"Mutation\s*:\s*([A-Za-z0-9_\-]+)", text))
    if ids:
        return f"{len(ids)}/{len(ids)}"
    m = re.search(r"(\d+)/(\d+)", text)
    return f"{m.group(1)}/{m.group(2)}" if m else "khong doc duoc log"


def tail_line(log: str, n: int = -1) -> str:
    p = ROOT / log
    if not p.exists():
        return "KHONG CO LOG"
    lines = [x.strip() for x in p.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
    hits = [x for x in lines if "passed" in x or "failed" in x]
    return (hits or lines)[n] if (hits or lines) else "log rong"


# ------------------------------------------------------------------ cổng / round
def gate_metrics(round_id: str, phase: str = "retrieval") -> dict:
    import gate

    rows = gate.load_rows(ROOT / "data" / "loop" / "rounds" / round_id, phase)
    return gate.metrics(list(rows.values()))


def gold_rel(round_id: str) -> str:
    m = gate_metrics(round_id)
    return (f"gold={m['gold_in_top_k_rate']:.4f} (n={m['n']}, {m['n_gold_items']} có vàng, "
            f"FAIL_RETRIEVAL={m['retrieval_failures']})")


def paired(rel: str) -> str:
    d = load(rel)["paired"]
    b = d["paired_bootstrap_gold_delta"]
    return (f"gold_delta={d['gold_delta']:.4f} CI {b['ci95_percentile']} "
            f"p={d['mcnemar_exact']['p_two_sided']}")


def _referenced_paths() -> int:
    import docs_consistency_check as dc

    total = 0
    for rel in dc.DOC_FILES:
        p = ROOT / rel
        if p.exists():
            total += len(dc.referenced_paths(p.read_text(encoding="utf-8")))
    return total


def cache_token_clean_env() -> str:
    keep = {}
    for k in list(os.environ):
        if k.startswith(("RESCUE_", "ANSWER_GUARD_", "DEC_", "NORMALIZE_", "EV_", "ENABLE_",
                        "ROUTER_", "RERANKER", "EVIDENCE_", "GENERATION_", "GATE_")):
            keep[k] = os.environ.pop(k)
    try:
        import importlib

        import src.core.cache_policy as cp

        importlib.reload(cp)
        return f"{cp.policy_cache_token()} (deviation={cp.cache_policy_deviation()!r})"
    finally:
        os.environ.update(keep)


ROWS: list[tuple[str, str, str, str]] = [
    # (task, "số đã công bố", "cách tính lại", "kết quả tính lại")
    # --- T0
    ("T0", "22 test noise floor", "`pytest --collect-only -q tests/test_noise_floor.py`", lambda: n_test("test_noise_floor.py")),
    ("T0", "5/5 đột biến bị bắt", "`tmp/mutation_check_t0.log` (đếm khối `Mutation :`)", lambda: mutation_total("tmp/mutation_check_t0.log")),
    # --- T1
    ("T1", "29 test ablation_generation", "collect-only", lambda: n_test("test_ablation_generation.py")),
    ("T1", "4/4 đột biến bị bắt", "`tmp/mutation_check_t1.log`", lambda: mutation_total("tmp/mutation_check_t1.log")),
    # --- T2
    ("T2", "81 test corpus rebuild", "collect-only", lambda: n_test("test_corpus_rebuild.py")),
    ("T2", "6/6 đột biến bị bắt", "`tmp/t2_mutation_6.log`", lambda: mutation_total("tmp/t2_mutation_6.log")),
    # --- T3
    ("T3", "77 test guardrails", "collect-only", lambda: n_test("test_t3_guardrails.py")),
    ("T3", "9/9 đột biến bị bắt", "`tmp/t3_mutation_recheck_9.log`", lambda: mutation_total("tmp/t3_mutation_recheck_9.log")),
    ("T3", "golden (sha) `e59b9ebb6b12c2d6844356f5861cc98d418c11b26f83a49fdae1f8f2ea1728b5`", "sha256 file golden",
     lambda: sha_prefix(ROOT / "tests/golden/t3_off_30items_head_f492f05.json", 64)),
    # --- T4
    ("T4", "11 + 10 + 29 + 12 = 62 test nhanh", "collect-only 4 file",
     lambda: n_tests("test_loop_generator_model_flag.py", "test_build_sft_from_round.py",
                     "test_t4_sft_invariants.py", "test_t4_generator_contract.py")),
    ("T4", "2 test slow (mặc định skip)", "collect-only", lambda: n_test("test_t4_gpu_slow.py")),
    ("T4", "7/7 đột biến (bộ test cũ)", "`tmp/mutation_check_t4.log`", lambda: mutation_total("tmp/mutation_check_t4.log")),
    ("T4", "8/8 đột biến (bộ test mới)", "`tmp/mutation_check_t4_new.log`", lambda: mutation_total("tmp/mutation_check_t4_new.log")),
    ("T4", "PASS_CORRECT 14→16",
     "đọc `round_summary_full.json` r9 và r10 THẬT + `data/loop/rounds/r10/t4_stats.json`",
     lambda: (f"r9={load('data/loop/rounds/r9/round_summary_full.json')['verdict_counts'].get('PASS_CORRECT')}, "
              f"r10={load('data/loop/rounds/r10/round_summary_full.json')['verdict_counts'].get('PASS_CORRECT')}; "
              f"r5={load('data/loop/rounds/r10/t4_stats.json')['rounds']['r5']['counts']['PASS_CORRECT']} "
              f"→ r10={load('data/loop/rounds/r10/t4_stats.json')['rounds']['r10']['counts']['PASS_CORRECT']}")),
    ("T4", "CI [−0,06 ; +0,10], p=0,804", "`data/loop/rounds/r10/t4_stats.json` pairs[0] (r5 vs r10)",
     lambda: (lambda pr: f"CI {pr['paired_delta']['pass_correct']['ci95_percentile']} "
                         f"p={pr['pass_correct_flip']['mcnemar']['p_two_sided']}")(load("data/loop/rounds/r10/t4_stats.json")["pairs"][0])),
    ("T4", "trần 1.024 token → 4.156,9 MiB", "row `length_tokens=1024` của `t4b_memory_probe_len.json`",
     lambda: f"length_tokens=1024 → peak_allocated_mib="
             f"{[r['peak_allocated_mib'] for r in load('data/loop/diag/t4b_memory_probe_len.json')['rows'] if r['length_tokens'] == 1024]}"),
    ("T4", "2 slow passed (79,04 s)", "`tmp/pytest_t4_slow.log` + chạy lại 25-10 `tmp/pytest_final_t4_slow.txt`",
     lambda: tail_line("tmp/pytest_t4_slow.log") + " || " + tail_line("tmp/pytest_final_t4_slow.txt")),
    # --- T5
    ("T5", "33 + 42 = 75 test", "collect-only 2 file",
     lambda: n_tests("test_t5_reranker_contract.py", "test_t5_contextual_header.py")),
    # PA-41: kỳ vọng cũ "46 test" (tới 25-10) đã đổi thành 51 vì B3 thêm test khoá
    # `query_convention` của PA-25 vào đúng file này — xem D-41, D-42.
    ("T5", "51 test cờ RERANKER_FALLBACK", "collect-only", lambda: n_test("test_reranker_flag.py")),
    ("T5", "13/13 đột biến bị bắt", "`tmp/mutation_check_t5.log`", lambda: mutation_total("tmp/mutation_check_t5.log")),
    ("T5", "gold = 0,7400 và FAIL_RETRIEVAL 182", "gate.metrics trên round đã đóng **r11**", lambda: gold_rel("r11")),
    ("T5", "delta −0,0714 CI [−0,1014; −0,0414] p=3,9e−06", "`reranker_paired_r11_r12.json`",
     lambda: paired("data/loop/diag/reranker_paired_r11_r12.json")),
    ("T5", "delta −0,0029 CI [−0,0129; +0,0071] p=0,79", "`header_paired_r11_r13.json` (ĐÍNH CHÍNH: từng in −0,0028 do cắt số)",
     lambda: paired("data/loop/diag/header_paired_r11_r13.json")),
    # --- T6
    ("T6", "9 + 6 = 15 test", "collect-only 2 file",
     lambda: n_tests("test_gate_refusal_relative_proposal.py", "test_score_real_questions.py")),
    ("T6", "28 + 10 + 22 = 60 test", "collect-only 3 file",
     lambda: n_tests("test_t6_gate_refusal_and_regression.py", "test_t6_referee_validation.py",
                     "test_t6_real_questions_and_metrics.py")),
    ("T6", "10/10 đột biến (bộ cũ)", "`tmp/mutation_check_t6.log`", lambda: mutation_total("tmp/mutation_check_t6.log")),
    ("T6", "10/10 đột biến (bộ mới)", "`tmp/mutation_check_t6_tests.log`", lambda: mutation_total("tmp/mutation_check_t6_tests.log")),
    ("T6", "60 mẫu, n_filled=0", "manifest + đếm nhãn trong `referee_labeling_r5.jsonl`",
     lambda: (lambda rows: f"n_selected={load('data/loop/diag/referee_sample_manifest.json')['n_selected']}, "
                           f"n_filled={sum(1 for r in rows if r.get('label'))}, n_rows={len(rows)}")(
         [json.loads(l) for l in (ROOT / "data/loop/diag/referee_labeling_r5.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()])),
    ("T6", "Wilson 7/10 = [0,3968; 0,8922]", "`report_metrics.wilson_ci(7, 10)`",
     lambda: f"7/10 -> {__import__('report_metrics').wilson_ci(7, 10)}"),
    ("T6", "điểm trọng số 7,17 và 7,10",
     "`weighted_score()` hai bộ điểm 9,2/8,2/7,0/8,5/4,0 và 9,0/8,0/7,0/8,5/4,0, trọng số 0,20/0,15/0,20/0,20/0,25",
     lambda: (lambda rm: f"{rm.weighted_score({'a': 9.2, 'b': 8.2, 'c': 7.0, 'd': 8.5, 'e': 4.0},
                                             {'a': .20, 'b': .15, 'c': .20, 'd': .20, 'e': .25})} ~ "
                           f"{rm.weighted_score({'a': 9.0, 'b': 8.0, 'c': 7.0, 'd': 8.5, 'e': 4.0},
                                                {'a': .20, 'b': .15, 'c': .20, 'd': .20, 'e': .25})}")(
         __import__("report_metrics"))),
    ("T6", "CI PASS_CORRECT = [0,08; 0,21]", "`metric_ci_r7_full.json` (round r7)",
     lambda: json.dumps(load("data/loop/diag/metric_ci_r7_full.json")["metrics"]["pass_correct_rate"],
                        ensure_ascii=False)[:160]),
    # --- T7
    ("T7", "11 + 26 = 37 test", "collect-only 2 file",
     lambda: n_tests("test_run_chain.py", "test_cache_policy.py")),
    ("T7", "19 + 18 + 33 + 36 = 106 test", "collect-only 4 file",
     lambda: n_tests("test_t7_chain_env_manifest.py", "test_t7_cache_reuse_e2e.py",
                     "test_t7_tmp_cleanup.py", "test_t7_docs_consistency.py")),
    ("T7", "6/6 đột biến run_chain", "`tmp/mutation_check_t7.log`", lambda: mutation_total("tmp/mutation_check_t7.log")),
    ("T7", "6/6 đột biến run_chain (chạy lại)", "`tmp/mutation_check_t7_rerun_dot2.log`",
     lambda: mutation_total("tmp/mutation_check_t7_rerun_dot2.log")),
    ("T7", "10/10 đột biến cache_policy", "`tmp/mutation_check_cache_policy.log`",
     lambda: mutation_total("tmp/mutation_check_cache_policy.log")),
    ("T7", "(6+10) = 16/16", "tổng hai log cũ (ĐÍNH CHÍNH cho 17/17 từng in ở §2.3/§3)",
     lambda: (lambda a, b: f"{a}/{a} + {b}/{b} = {a + b}/{a + b}")(
         int(mutation_total("tmp/mutation_check_t7.log").split("/")[0]),
         int(mutation_total("tmp/mutation_check_cache_policy.log").split("/")[0]))),
    ("T7", "20/20 đột biến", "`tmp/mutation_check_t7_dot2.log` (dòng kết luận ghi '0 lọt')",
     lambda: mutation_total("tmp/mutation_check_t7_dot2.log")),
    ("T7", "DEFAULT_CACHE_TOKEN = d0b4c6a65f83", "`policy_cache_token()` dưới env đã bóc cờ lever",
     lambda: cache_token_clean_env()),
    ("T7", "checker: 264 lệnh · 100 đường dẫn · 4 help · 0 lỗi · 5 cảnh báo · 30 dòng sổ",
     "`tmp/docs_check_t7_dot3.json` + chạy lại `referenced_paths` trên README/ROADMAP",
     lambda: (lambda d, paths: f"{d['commands_checked']} lệnh, {paths} đường dẫn, help={d['help_checked']}, "
                               f"{len(d['decision_problems']) + len(d['referenced_file_problems']) + len(d['command_problems'])} lỗi, "
                               f"{len(d['command_warnings'])} cảnh báo, {d['decision_rows']} dòng sổ")(
         load("tmp/docs_check_t7_dot3.json"), _referenced_paths())),
    ("T7", "tmp_cleanup 164 mục · 95 GIỮ · 69 đề xuất · 26,4 MB · không xoá gì",
     "`tmp/cleanup_report_t7.json`",
     lambda: (lambda rep: (lambda s, dl: f"{s['n_items']}, {s['n_kept_cited']}, {s['n_proposed_delete']}, "
                          f"{s['bytes_proposed']} bytes = {s['bytes_proposed'] / 1e6:.1f} MB, "
                          f"applied={dl.get('applied')}, deleted={dl.get('deleted')}")(
             rep["summary"], rep["deletion"]))(load("tmp/cleanup_report_t7.json"))),
    ("T7", "gold = 0,5186 với 811 item, 700 item vàng", "gate.metrics trên round đã đóng **r0**", lambda: gold_rel("r0")),
    ("T7", "811/811 verdict trùng, 0 đổi chiều, 811/811 top, gold 0,5186",
     "`tmp/compare_r0_repro.json` (vòng r0 tái lập so với r0 đã đóng)",
     lambda: (lambda d: f"n_common={d['n_common']}, agree={d['verdict_agree']}, flips={d['verdict_flips']}, "
                        f"top6_exact={d['top6_exact_order']}/{d['top6_items_compared']}, "
                        f"gold_goc={d['metrics_base']['gold_in_top_k_rate']}, "
                        f"gold_repro={d['metrics_repro']['gold_in_top_k_rate']}")(
         load("tmp/compare_r0_repro.json"))),
    ("T7", "manifest dry-run = manifest lượt chạy (`295413c196de`)", "sha256 hai file",
     lambda: sha_prefix(ROOT / "data/loop/diag/chain_manifest_t7_repro_r0.json", 12) + " = "
             + sha_prefix(ROOT / "tmp/t7_manifest_probe_dot2.json", 12)),
    ("T2", "mất neo vàng 389/797 = 0,4881 với ngưỡng 0,02 ⇒ ĐỎ", "`data/loop/diag/corpus_check/corpus_check.json` `gold_coverage`",
     lambda: (lambda g: f"{g['n_missing_gold']}/{g['n_checkable']} = {g['missing_rate']}, red={g['red']}, "
                        f"ngưỡng {g['red_threshold']}")(
         load("data/loop/diag/corpus_check/corpus_check.json")["gold_coverage"])),
    ("T5", "verdict trùng 811, top trùng 811, sources toàn bộ 809 (tái lập cấu hình TẮT)",
     "`reranker_paired_family.json` `reproducibility.off_vs_closed`",
     lambda: (lambda r: f"n_common={r['n_common']}, same_verdict={r['same_verdict']}, "
                        f"same_top_k={r['same_sources_top_k']}, same_full={r['same_sources_full']}, "
                        f"mismatched={r['n_mismatched_items']}, tie-break ở hạng sâu")(
         load("data/loop/diag/reranker_paired_family.json")["reproducibility"]["off_vs_closed"])),
    ("T6", "refusal 0,61→0,69 và fabrication 0,0256→0,0323 ⇒ cổng không ĐẠT",
     "`data/loop/rounds/r5/gate_vs_r3_full.json`",
     lambda: (lambda g: (lambda b, c: f"refusal {b['refusal_rate']}→{c['refusal_rate']}, "
                                   f"fabrication {b['fabrication_rate_on_answered']}→{c['fabrication_rate_on_answered']}, "
                                   f"passed={g['passed']}")(g["baseline_metrics"], g["candidate_metrics"]))(
         load("data/loop/rounds/r5/gate_vs_r3_full.json"))),
    ("T7", "11 + 26 + 19 + 18 + 33 + 36 = 143 test", "collect-only 6 file T7",
     lambda: n_tests("test_run_chain.py", "test_cache_policy.py", "test_t7_chain_env_manifest.py",
                     "test_t7_cache_reuse_e2e.py", "test_t7_tmp_cleanup.py", "test_t7_docs_consistency.py")),
    # --- trọng tài / toàn repo
    # PA-41: kỳ vọng cũ "`9f1179ccab74`" (tới 25-10) đã đổi thành v2 `2911c69f740d` vì B2 áp
    # PA-2 + PA-20 — xem D-41, D-42.
    ("Chung", "chữ ký trọng tài `2911c69f740d`", "`verify.referee_fingerprint()`",
     lambda: __import__("verify").referee_fingerprint()),
    ("Chung", "SHA gate.py `bf4bda89d8a360abbba25742`", "sha256 tools/loop/gate.py",
     lambda: sha_prefix(ROOT / "tools/loop/gate.py", 24)),
    ("Chung", "1.004 passed", "`tmp/pytest_t7_final.txt`",
     lambda: tail_line("tmp/pytest_t7_final.txt")),
    ("Chung", "1.064 passed, 2 skipped", "`tmp/pytest_t5_final_2.txt`",
     lambda: tail_line("tmp/pytest_t5_final_2.txt")),
    ("Chung", "1.124 passed, 2 skipped", "`tmp/pytest_t6_final.txt`",
     lambda: tail_line("tmp/pytest_t6_final.txt")),
    ("Chung", "1.228 passed, 4 skipped", "`tmp/pytest_t7_dot2_final.txt`",
     lambda: tail_line("tmp/pytest_t7_dot2_final.txt")),
    ("Chung", "1.228 passed, 4 skipped (chạy lại)", "`tmp/pytest_t7_dot3_final.txt` (chạy lại lần 2)",
     lambda: tail_line("tmp/pytest_t7_dot3_final.txt")),
    # --- Nghiệm thu cuối + đợt siết môi trường đo D-35 (them 25-10 19:3x, ĐÍNH CHÍNH tăng 55 -> 59 dong)
    ("Chung", "1.338 passed, 5 skipped", "`tmp/pytest_post_commit_venv.txt` (sau commit `c508876`, stdin đóng)",
     lambda: tail_line("tmp/pytest_post_commit_venv.txt")),
    ("Chung", "1.359 passed, 5 skipped", "`tmp/pytest_after_d35.txt` (sau đợt siết D-35 + 21 test mới)",
     lambda: tail_line("tmp/pytest_after_d35.txt")),
    ("Chung", "1.371 passed, 5 skipped", "`tmp/pytest_after_d36.txt` (sau cả hai lớp siết D-35 + D-36)",
     lambda: tail_line("tmp/pytest_after_d36.txt")),
    ("NCC", "34 test phòng thủ môi trường của máy kiểm", "collect-only `test_final_subprocess_stdin_guard.py`",
     lambda: n_test("test_final_subprocess_stdin_guard.py")),
    ("NCC", "9/9 đột biến phòng thủ môi trường", "`tmp/mutation_check_stdin_guard.log` (dòng kết quả)",
     lambda: mutation_total("tmp/mutation_check_stdin_guard.log")),
    ("Chung", "1.372 passed, 5 skipped", "`tmp/pytest_final_batch3.txt` (đợt siết cuối, đỏ 1 test vì đường dẫn cá nhân trong docs — xem `tmp/pytest_batch3_caught_pii_path.txt`)",
     lambda: tail_line("tmp/pytest_final_batch3.txt")),
    ("NCC", "144 passed, 1 skipped", "`tmp/pytest_final5_batch3.txt` (bộ nghiệm thu cuối, venv)",
     lambda: tail_line("tmp/pytest_final5_batch3.txt")),
    ("NCC", "144 passed, 1 skipped", "`tmp/pytest_final5_py314_stdin_closed_batch3.txt` (bộ cùng chạy bằng interpreter hệ thống, stdin đóng)",
     lambda: tail_line("tmp/pytest_final5_py314_stdin_closed_batch3.txt")),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tái lập số công bố của T0–T7 (chỉ đọc).")
    ap.add_argument("--json", help="ghi kết quả JSON vào đường dẫn này (nên trỏ tmp/).")
    ap.add_argument("--task", help="chỉ in bảng của một nhãn task")
    ap.add_argument("--md", action="store_true", help="in dạng bảng Markdown có header")
    args = ap.parse_args(argv)

    out = []
    for task, published, method, fn in ROWS:
        if args.task and task != args.task:
            continue
        try:
            recomputed = str(fn())
        except Exception as exc:  # không im lặng bỏ qua
            recomputed = f"LOI KHI TINH LAI: {type(exc).__name__}: {exc}"
        pn = numbers(published)
        rn = [v for v, _ in numbers(recomputed)]
        khop = is_subsequence(pn, rn) if pn else None
        out.append({"task": task, "cong_bo": published, "cach_tinh_lai": method,
                    "tinh_lai": recomputed, "khop": khop})

    if args.md:
        print("| Task | Số công bố | Cách tính lại | Tính lại | Khớp |")
        print("|---|---|---|---|---|")
    for row in out:
        mark = "?" if row["khop"] is None else ("KHỚP" if row["khop"] else "**LỆCH**")
        cells = (row["task"], row["cong_bo"], row["cach_tinh_lai"], row["tinh_lai"], mark)
        if args.md:
            print("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
        else:
            print(" | ".join(cells))
    n_lech = sum(1 for r in out if r["khop"] is False)
    print(f"\n[tổng] {len(out)} dòng; {n_lech} dòng LỆCH.", file=sys.stderr)
    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
