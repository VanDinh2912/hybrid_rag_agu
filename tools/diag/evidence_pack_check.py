# -*- coding: utf-8 -*-
"""C3 — gói bằng chứng: mỗi dòng của `docs/EXPERIMENTS.md` → tệp nguồn + SHA-256.

Vì sao có tệp này: bảng EXPERIMENTS trích số từ artifact nằm rải trong `data/loop/`, `docs/` và
`tmp/`; phần lớn KHÔNG nằm trong git (PA-33). Muốn trả lời "số này đọc từ tệp nào, tệp còn đúng
bản đã công bố không" cần một danh sách máy đọc được kèm băm byte thô. Tệp này KHÔNG chép artifact
vào git — nó chỉ ghim `(path, bytes, sha256)` và kiểm lại được bằng một lệnh.

Ba chế độ, mặc định chỉ đọc:

    venv/Scripts/python.exe tools/diag/evidence_pack_check.py            # in tóm tắt JSON đã ghim
    venv/Scripts/python.exe tools/diag/evidence_pack_check.py --check    # băm lại; lệch ⇒ mã 1
    venv/Scripts/python.exe tools/diag/evidence_pack_check.py --write    # sinh lại JSON + bảng MD

`--check` báo bốn loại lệch: tệp THIẾU, tệp ĐỔI byte/hash, JSON không khớp danh sách D-row hiện
hành (spec đổi mà chưa `--write`), và bảng trong `docs/EVIDENCE_PACK.md` không khớp JSON. So sánh
bỏ qua `generated_at`. Băm trên BYTE THÔ (không chuẩn hoá EOL) — cùng luật với chữ ký trọng tài.

Quy ước cột: `chinh` = đúng tệp ở cột "Tệp nguồn" của EXPERIMENTS.md; `phu` = tệp cần để đọc/đối
chiếu số trong cùng dòng (baseline, gate, nhật ký đếm). `anchors` = neo đóng băng không thuộc
D-row (round r11, golden env, manifest artifact, dụng cụ chấm lại).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:  # D-36: console Windows cp1258 không in được chữ có dấu ⇒ tự đặt UTF-8 ngay lúc import
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = ROOT / "docs" / "evidence_pack.json"
MD_PATH = ROOT / "docs" / "EVIDENCE_PACK.md"
START = "<!-- evidence-table:start -->"
END = "<!-- evidence-table:end -->"
CHUNK = 1024 * 1024

#: D-row → (tệp chính, tệp phụ). Thứ tự cố định theo EXPERIMENTS.md.
ROWS: dict[str, tuple[list[str], list[str]]] = {
    "D-01": (
        ["data/loop/rounds/r1/round_summary_retrieval.json"],
        # baseline r0 (51,86%) + cổng so r1↔r0
        ["data/loop/rounds/r0/round_summary_retrieval.json",
         "data/loop/rounds/r1/gate_vs_r0_retrieval.json"],
    ),
    "D-02": (
        ["data/loop/rounds/r4/round_summary_retrieval.json"],
        # mốc so sánh là r2 (74,00%) + cổng so r4↔r2
        ["data/loop/rounds/r2/round_summary_retrieval.json",
         "data/loop/rounds/r4/gate_vs_r2_retrieval.json"],
    ),
    "D-03": (
        ["data/loop/rounds/r5b/rescue_tally.txt"],
        ["data/loop/rounds/r5b/round_summary_full.json",
         "data/loop/rounds/r5b/gate_vs_r5_full.json"],
    ),
    "D-04": (
        ["data/loop/rounds/r6/round_summary_full.json"],
        ["data/loop/rounds/r6/normalizer_guard_tally.txt",
         "data/loop/rounds/r6/gate_vs_r5b_full.json"],
    ),
    "D-05": (
        ["data/loop/rounds/r7/gate_vs_r6_full.json"],
        ["data/loop/rounds/r7/round_summary_full.json",
         "data/loop/rounds/r7/combo_tally.txt"],
    ),
    "D-06": (
        ["data/loop/diag/bonus_paired.json"],
        ["data/loop/diag/bonus_paired_r1_r2.json"],
    ),
    "D-07": (
        ["data/loop/rounds/r8/round_summary_full.json"],
        ["data/loop/rounds/r8/gate_vs_r5_full.json",
         "data/loop/rounds/r8/attribution_vs_r5.txt"],
    ),
    "D-08": (
        ["data/loop/rounds/r9/round_summary_full.json"],
        ["data/loop/rounds/r9/gate_vs_r8_full.json",
         "data/loop/rounds/r9/attribution_vs_r8.txt"],
    ),
    "D-09": (
        ["data/loop/rounds/r10/t4_stats.json"],
        ["data/loop/rounds/r10/round_summary_full.json",
         "data/loop/diag/one_variable_check.json",
         "data/loop/diag/t4_latency_20q.json"],
    ),
    "D-10": (
        ["data/loop/diag/t4b_memory_probe_len.json"],
        ["data/loop/diag/t4b_memory_probe.json"],
    ),
    "D-11": (
        ["data/loop/diag/reranker_paired_r11_r12.json"],
        # probe fold(query) 0/30 → lỗi build, không phải năng lực model
        ["tmp/probe_r12_fold.json",
         "data/loop/rounds/r12/round_summary_retrieval.json"],
    ),
    "D-12": (
        ["data/loop/diag/header_paired_r11_r13.json"],
        ["data/loop/diag/header_index_old_build.json",
         "data/loop/rounds/r13/round_summary_retrieval.json"],
    ),
    "D-13": (
        ["data/loop/diag/corpus_diagnostics/index_after.json"],
        # trước/sau rebuild + bằng chứng dấu theo từng tệp + mẫu đọc tay
        ["data/loop/diag/corpus_diagnostics/index_before.json",
         "data/loop/diag/corpus_diagnostics/quality_vie.json",
         "data/loop/diag/corpus_diagnostics/easyocr_trial.json",
         "data/loop/diag/corpus_diagnostics/manual_20_segments.txt",
         "data/loop/diag/corpus_diagnostics/per_file.json"],
    ),
    "D-14": (
        ["data/loop/diag/b_gemini_top6/bootstrap_ci_25.json"],
        ["data/loop/diag/b_gemini_top6/summary.json",
         "data/loop/diag/b_gemini_top6/id_status.json",
         "data/loop/diag/b_gemini_top6/rows.jsonl",
         "data/loop/diag/b_gemini_top6/settings.json"],
    ),
    "D-16": (
        ["docs/bao_cao/danh_gia_tong_quan_2026-10-23.md"],
        # dòng D-16 trích số từ chính tài liệu (5 điểm thành phần), không có artifact đo riêng
        [],
    ),
    "D-20": (
        ["data/loop/rounds/r12/round_summary_retrieval.json"],
        ["data/loop/diag/reranker_cost_gpu.json",
         "data/loop/diag/reranker_cost.json"],
    ),
    "D-22": (
        ["tools/loop/chains/t5a_reranker.json"],
        ["tools/loop/chains/t7_repro_r0.json",
         "tools/loop/chains/demo_dryrun.json"],
    ),
    "D-30": (
        ["tmp/compare_r0_repro.json"],
        ["data/loop/diag/chain_manifest_t7_repro_r0.json",
         "tools/loop/chains/t7_repro_r0.json"],
    ),
    "D-33": (
        ["docs/archive/reports/test_final.md"],
        # số 126/126 được đếm lại từ 13 log; bảng nguồn nằm trong chính báo cáo
        [],
    ),
    "D-37": (
        ["data/loop/rounds_v2/r16/gate_vs_r11_retrieval.json"],
        ["data/loop/diag/reranker_paired_r11_r16.json",
         "tmp/probe_r12_fold.json",
         "data/loop/rounds_v2/r16/round_summary_retrieval.json"],
    ),
    "D-38": (
        ["data/loop/diag/answerability_probe_r5.json"],
        ["data/loop/diag/answerability_labelset_r5.jsonl",
         "data/loop/diag/answerability_probe_r5_buildonly.json",
         "data/loop/diag/answerability_probe_r11_retrieval.json",
         "data/loop/diag/answerability_probe_r12_retrieval.json"],
    ),
    "D-39": (
        ["data/loop/diag/answer_token_logits_probe_real_fraction.json"],
        ["data/loop/diag/answer_token_logits_probe.json",
         "data/loop/diag/answer_token_logits_probe_oom_bound.json",
         "data/loop/diag/b5_answer_fraction.json",
         "data/loop/diag/b5_wddm_oversubscription.json"],
    ),
    "D-40": (
        ["data/loop/diag/b1_cprime/analysis.json"],
        ["data/loop/diag/b1_cprime/mapping.json",
         "data/loop/diag/b1_cprime/settings.json"],
    ),
    "D-41": (
        ["data/loop/rounds_v2/compare_v1_v2.json"],
        # bản chấm lại 10 round bằng v2 là đầu vào của phép so; không lặp từng round
        [],
    ),
    "D-42": (
        ["tmp/final_number_audit_b_shift.json"],
        ["tmp/final_number_audit.json",
         "tmp/final_number_audit_table.md"],
    ),
}

#: Neo đóng băng (không thuộc D-row) — dùng cho §6 của CLEANUP_ANCHORS.md và cổng sau mỗi bước.
ANCHORS: list[str] = [
    "docs/CLEANUP_ANCHORS.md",
    "tools/loop/verify.py",
    "tools/diag/rescore_retrieval_round_v2.py",
    "data/loop/rounds/r11/verdicts_retrieval.jsonl",
    "data/loop/rounds/r11/round_summary_retrieval.json",
    "tmp/anchor_r11_rescore_v2.json",
    "tmp/b0_golden_env_off.txt",
    "tmp/b0_anchor_numbers.py",
    "ARTIFACT_MANIFEST.json",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _tracked_set() -> set[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True,
            stdin=subprocess.DEVNULL, check=True,
        ).stdout
    except Exception:
        return set()
    return {p.decode("utf-8", "replace") for p in out.split(b"\0") if p}


def _all_files() -> list[str]:
    """Danh sách tệp duy nhất, giữ thứ tự xuất hiện; thiếu tệp là lỗi cứng."""
    seen: list[str] = []
    for chinh, phu in ROWS.values():
        for p in chinh + phu:
            if p not in seen:
                seen.append(p)
    for p in ANCHORS:
        if p not in seen:
            seen.append(p)
    missing = [p for p in seen if not (ROOT / p).is_file()]
    if missing:
        raise FileNotFoundError("thiếu tệp nguồn: " + ", ".join(missing))
    return seen


def build() -> dict:
    tracked = _tracked_set()
    files = []
    for rel in _all_files():
        p = ROOT / rel
        files.append(
            {
                "path": rel,
                "bytes": p.stat().st_size,
                "sha256": _sha256(p),
                "tracked": rel in tracked,
            }
        )
    rows = [{"id": k, "chinh": list(v[0]), "phu": list(v[1])} for k, v in ROWS.items()]
    return {
        "schema": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "algorithm": "sha256",
        "root": ".",
        "note": "sha256 trên byte thô, không chuẩn hoá EOL; artifact nặng không commit",
        "rows": rows,
        "anchors": list(ANCHORS),
        "files": files,
        "summary": {
            "rows": len(rows),
            "files": len(files),
            "total_bytes": sum(f["bytes"] for f in files),
        },
    }


def render_table(data: dict) -> str:
    """Bảng Markdown sinh từ JSON — `--check` so đúng chuỗi này với khối trong tài liệu."""
    files = {f["path"]: f for f in data["files"]}
    lines = [
        "| D | Vai trò | Tệp | byte | sha256 (12 đầu) | git |",
        "|---|---|---|---:|---|---|",
    ]

    def row(d_id: str, role: str, rel: str) -> str:
        f = files[rel]
        git = "tracked" if f["tracked"] else "chưa"
        return f"| {d_id} | {role} | `{rel}` | {f['bytes']} | `{f['sha256'][:12]}` | {git} |"

    for item in data["rows"]:
        for rel in item["chinh"]:
            lines.append(row(item["id"], "chính", rel))
        for rel in item["phu"]:
            lines.append(row(item["id"], "phụ", rel))
    for rel in data["anchors"]:
        lines.append(row("neo", "neo", rel))
    return "\n".join(lines) + "\n"


def _replace_block(md: str, table: str) -> str:
    i = md.index(START)
    j = md.index(END)
    eol = "\r\n" if "\r\n" in md else "\n"
    body = table.replace("\n", eol)
    return md[: i + len(START)] + eol + eol + body + eol + md[j:]


def write_pack() -> int:
    data = build()
    JSON_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    md = MD_PATH.read_bytes().decode("utf-8")
    new = _replace_block(md, render_table(data))
    MD_PATH.write_bytes(new.encode("utf-8"))
    print(f"[evidence] đã ghi {JSON_PATH.relative_to(ROOT)} ({data['summary']['files']} tệp, "
          f"{data['summary']['total_bytes']} B)")
    print(f"[evidence] đã cập nhật bảng trong {MD_PATH.relative_to(ROOT)}")
    return 0


def check() -> int:
    if not JSON_PATH.is_file():
        print(f"[evidence] THIẾU {JSON_PATH.relative_to(ROOT)} — chạy --write")
        return 1
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    entries = {f["path"]: f for f in data.get("files", [])}

    missing = sorted(p for p in entries if not (ROOT / p).is_file())
    changed = []
    for p, f in entries.items():
        if p in missing:
            continue
        path = ROOT / p
        if path.stat().st_size != int(f["bytes"]) or _sha256(path) != f["sha256"]:
            changed.append(p)

    spec = sorted(_all_files())
    extra = sorted(set(entries) - set(spec))
    not_pinned = sorted(set(spec) - set(entries))

    table_ok, table_msg = True, ""
    if MD_PATH.is_file():
        md = MD_PATH.read_bytes().decode("utf-8")
        if START in md and END in md:
            block = md.split(START, 1)[1].split(END, 1)[0].replace("\r\n", "\n").strip()
            if block != render_table(data).strip():
                table_ok, table_msg = False, "bảng trong EVIDENCE_PACK.md không khớp JSON"
        else:
            table_ok, table_msg = False, "không thấy hai mốc bảng trong EVIDENCE_PACK.md"
    else:
        table_ok, table_msg = False, "THIẾU docs/EVIDENCE_PACK.md"

    print(f"[evidence] {JSON_PATH.relative_to(ROOT)}: {len(entries)} tệp / "
          f"{sum(int(f['bytes']) for f in entries.values())} B")
    print(f"[evidence] D-row: {len(ROWS)} · neo: {len(ANCHORS)}")
    for label, items in (
        ("THIẾU", missing),
        ("ĐỔI", changed),
        ("JSON THỪA (ngoài spec)", extra),
        ("JSON THIẾU (spec chưa ghim)", not_pinned),
    ):
        if items:
            print(f"  {label} ({len(items)}):")
            for p in items[:20]:
                print("    -", p)
    if not table_ok:
        print(f"  BẢNG: {table_msg}")
    if missing or changed or extra or not_pinned or not table_ok:
        print("[evidence] KẾT LUẬN: LỆCH — artifact hoặc tài liệu đã đổi so với gói bằng chứng.")
        return 1
    print("[evidence] KẾT LUẬN: KHỚP — mọi tệp đúng byte, JSON và bảng MD nhất quán.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Gói bằng chứng EXPERIMENTS.md: ghim (path, bytes, sha256), kiểm lại chỉ-đọc."
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="sinh lại docs/evidence_pack.json + bảng MD")
    g.add_argument("--check", action="store_true", help="băm lại và so; lệch ⇒ mã 1")
    ap.add_argument("--json", action="store_true", help="in JSON đầy đủ ra stdout")
    args = ap.parse_args(argv)

    if args.write:
        try:
            return write_pack()
        except FileNotFoundError as exc:
            print(f"[evidence] {exc}")
            return 1
    if args.check:
        try:
            return check()
        except FileNotFoundError as exc:
            print(f"[evidence] {exc}")
            return 1

    try:
        data = build()
    except FileNotFoundError as exc:
        print(f"[evidence] {exc}")
        return 1
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        s = data["summary"]
        print(f"[evidence] spec: {s['rows']} D-row, {s['files']} tệp, {s['total_bytes']} B")
        tracked = sum(1 for f in data["files"] if f["tracked"])
        print(f"[evidence] tracked {tracked} / chưa-tracked {s['files'] - tracked}")
        print(f"[evidence] dùng --check để so với {JSON_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
