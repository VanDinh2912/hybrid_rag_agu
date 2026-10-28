# -*- coding: utf-8 -*-
"""T7 (mục 5–6 đề bài) — kiểm tài liệu bằng dụng cụ, không bằng mắt.

Hai việc phải tự trả lời được mỗi khi tài liệu đổi:

**Mục 5 — Sổ quyết định (`docs/DECISION_LOG.md`).** Mỗi dòng `| D-xx |` phải đủ sáu cột
(ID, Ngày, Giả thuyết, Số đo quyết định, Nguồn, Trạng thái), giả thuyết và số đo không rỗng, số đo
chứa ít nhất một con số (quyết định phải dựa trên số, không dựa trên cảm giác), và **mọi đường dẫn
nguồn phải tồn tại trên đĩa**. Đường dẫn được chuẩn hoá trước khi kiểm: bỏ chú thích `::tên_hàm`,
`:số_dòng`, ` §mục`, mở rộng kiểu `{a,b}`, bỏ dấu `/…` và `*` — tức là cùng quy ước mà chính cái
snippet cuối `DECISION_LOG.md` đã dùng, nhưng lần này có test.

**Mục 6 — Tài liệu chạy được.** (a) Mỗi *file* được README/ROADMAP nhắc bằng đường dẫn repo
(`src/…`, `tools/…`, `scripts/…`, `tests/…`, `data/…`, `docs/…`, `models/…`, `outputs/…`) phải tồn tại;
(b) mỗi *lệnh* trong block code trỏ tới một script của repo phải có thật, và nếu script đó dùng
`argparse` thì `--help` phải chạy với mã 0 (đó là chế độ "in hướng dẫn, không làm gì"). Script
không có `argparse` (vd. `ingest.py`, `scripts/learn.py`) được xếp vào nhóm **cảnh báo** chứ không phải lỗi:
đề bài yêu cầu "--help hoặc dry-run", nhưng thêm CLI vào các script đó là việc cần duyệt, không phải
việc của bộ kiểm thử.

Chỉ-đọc tuyệt đối: module không ghi file nào trừ khi người chạy truyền `--json`.

Dùng:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/docs_consistency_check.py
    ... --scope log|files|commands|all  --run-help  --json tmp/docs_check.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DECISION_LOG = "docs/DECISION_LOG.md"
DOC_FILES = ("README.md", "docs/planning/ROADMAP.md")

# Tiền tố đường dẫn repo — chỉ những cái này mới bị kiểm tồn tại.
REPO_TOP = ("src/", "tools/", "tests/", "data/", "docs/", "ui/", "models/", "outputs/", "logs/", "scripts/",
            "chroma_db", ".ocr_cache", "tmp/")

# Nhưng **chỉ** nhóm được commit/quản lý có kỳ vọng tồn tại. `logs/`, `tmp/`, `chroma_db*`,
# `.ocr_cache`, `.generation_cache` là thư mục **sinh ra lúc chạy** — bắt tồn tại trong bản clone
# mới là đòi hỏi sai (và sẽ đỏ ngay trên máy chưa chạy lần nào).
CHECK_TOP = ("src/", "tools/", "tests/", "data/", "docs/", "ui/", "models/", "outputs/", "scripts/")
CHECK_EXACT = {"README.md", "docs/planning/ROADMAP.md", "docs/spec/TAXONOMY.md", "requirements.txt", ".env.example"}

# Hai file `data/…` mà GUI/`scripts/learn.py` **tự sinh khi người dùng bấm "Sai"/"Học ngay"** — README mô tả
# luồng đó nên bắt buộc nhắc đường dẫn, kể cả khi chưa ai bấm. `docs/giang_day/04` đã ghi rõ
# "không tồn tại". Đây là nhóm "thư mục sinh lúc chạy" nhưng nằm trong `data/` nên CHECK_TOP không loại
# được; ghi thành danh sách trắng CÓ LÝ DO để lần sau thêm file không tồn tại thật vẫn bị bắt.
RUNTIME_GENERATED = {
    "data/normalization_pairs.json",
    "data/corpus/ghi_chu_hoc_them.txt",
}

STATUS_WORDS = ("GIỮ", "GIU", "BÁC", "BAC", "CHỜ DUYỆT", "CHO DUYET", "MỞ", "MO", "ĐẠT", "DAT")

DATE_RE = re.compile(r"^\d{2}-\d{2}(?:→\d{2}-\d{2})?$|^\d{2}→\d{2}-\d{2}$|^\d{2}-\d{2}→\d{2}-\d{2}$")
ID_RE = re.compile(r"^D-\d{2,3}$")

CELL_SPLIT = re.compile(r"\s\|\s")


def _clean_token(tok: str) -> str:
    """Chuẩn hoá một chuỗi đường dẫn trong tài liệu về dạng có thể `exists()`."""
    t = tok.strip().strip(".,;:)]\"'`")
    t = t.split("::")[0]                      # src/generator.py::ham
    t = re.sub(r"\.(py|json|jsonl|md|txt|log|csv|sh|ps1)[: ]\d.*$", r".\1", t)  # path.py:95
    t = re.sub(r"\.(py|json|jsonl|md|txt|log|csv|sh|ps1),\d.*$", r".\1", t)      # path.py:356,386
    t = t.split(" §")[0].split("#")[0]         # docs/reports/T5.md §2.7
    if t not in ("tests/", "docs/", "tools/"):
        t = t.rstrip("*").rstrip("/")
    return t.strip()


def looks_like_pattern(tok: str) -> bool:
    """`logs/benchmark/chroma_<strategy>/`, `src/a|b.py`, `tools/loop/*` — mô tả, không phải một file."""
    return any(ch in tok for ch in "<>*|…") or " " in tok.strip()


def expand_braces(tok: str) -> list[str]:
    """`a/{b,c}.json` -> ['a/b.json', 'a/c.json']; `probe{,_len}.json` -> cả hai nhánh."""
    m = re.match(r"^(.*)\{([^{}]*)\}(.*)$", tok)
    if not m:
        return [tok]
    pre, inner, post = m.groups()
    out: list[str] = []
    for part in inner.split(","):
        out.extend(expand_braces(f"{pre}{part.strip()}{post}"))
    return out


def path_candidates(cell: str) -> list[str]:
    """Mọi chuỗi trông như đường dẫn file/thư mục repo trong một ô bảng."""
    raw = re.findall(r"`([^`]+)`|\b((?:src|tools|tests|data|docs|ui|models|outputs|logs)/[^\s,|]+)", cell)
    out: list[str] = []
    for group in raw:
        tok = (group[0] or group[1]).strip()
        if not tok:
            continue
        for cand in (_clean_token(c) for c in expand_braces(tok)):
            if not cand or cand.startswith(("http", "#", "mailto")):
                continue
            if looks_like_pattern(cand):
                continue
            if cand.startswith(REPO_TOP) or "/" in cand:
                out.append(cand)
    return sorted(set(out))


def decision_rows(text: str) -> list[dict]:
    """Bảng tổng của sổ quyết định: mỗi dòng `| D-xx |` một mục."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("| D-"):
            continue
        cells = [c.strip() for c in CELL_SPLIT.split(line.strip().strip("|"))]
        rows.append({
            "line": line,
            "id": cells[0] if cells else "",
            "date": cells[1] if len(cells) > 1 else "",
            "hypothesis": cells[2] if len(cells) > 2 else "",
            "measurement": cells[3] if len(cells) > 3 else "",
            "source": cells[4] if len(cells) > 4 else "",
            "status": cells[5] if len(cells) > 5 else "",
            "n_cells": len(cells),
        })
    return rows


def check_decision_log(rows: list[dict]) -> list[str]:
    """Mục 5(a): mỗi mục phải có đủ ngày – giả thuyết – số đo – nguồn – trạng thái."""
    problems: list[str] = []
    for r in rows:
        rid = r["id"] or "?"
        if r["n_cells"] != 6:
            problems.append(f"{rid}: bảng phải có 6 cột, nhận {r['n_cells']}")
            continue
        if not ID_RE.match(rid):
            problems.append(f"{rid}: ID không đúng dạng D-xx")
        if not DATE_RE.match(r["date"]):
            problems.append(f"{rid}: ngày '{r['date']}' không đúng dạng dd-mm (hoặc dd→dd-mm)")
        if len(r["hypothesis"]) < 10:
            problems.append(f"{rid}: giả thuyết rỗng/quá ngắn")
        if not re.search(r"\d", r["measurement"]):
            problems.append(f"{rid}: số đo quyết định không chứa con số nào")
        if not r["source"]:
            problems.append(f"{rid}: thiếu cột nguồn")
        if not any(w in r["status"] for w in STATUS_WORDS):
            problems.append(f"{rid}: trạng thái '{r['status']}' không thuộc tập quy ước")
    ids = [r["id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    for d in sorted(dup):
        problems.append(f"{d}: ID bị lặp trong bảng tổng")
    return problems


def check_source_paths(root: Path, rows: list[dict]) -> list[str]:
    """Mục 5(b): mọi đường dẫn nguồn trong sổ phải tồn tại (kể cả artefact chưa tracked)."""
    problems: list[str] = []
    for r in rows:
        for cand in path_candidates(r["source"]):
            p = root / cand
            if p.exists():
                continue
            if cand.endswith("*"):  # dẫn cả thư mục bằng wildcard -> kiểm thư mục cha
                if (root / cand.rstrip("*/")).exists():
                    continue
            # tên trần (không có '/') -> tìm trong repo, ví dụ `round_summary_full.json`
            if "/" not in cand and list(root.glob(f"**/{cand}")):
                continue
            problems.append(f"{r['id']}: nguồn không tồn tại trên đĩa — `{cand}`")
    return problems


def referenced_paths(text: str, *, include_runtime: bool = False) -> list[str]:
    """Mục 6(a): đường dẫn repo được nhắc trong README/ROADMAP (inline code + link markdown).

    Chỉ trả về những đường dẫn **có kỳ vọng tồn tại trong bản clone mới** (`CHECK_TOP` +
    `CHECK_EXACT`). Thư mục sinh ra lúc chạy (`logs/`, `tmp/`, `chroma_db*`, `.ocr_cache`) và hai
    file tự sinh của GUI (`RUNTIME_GENERATED`) bị loại ngay từ đây: bắt chúng tồn tại trên máy chưa
    chạy lần nào là đòi hỏi sai.
    """
    spans = re.findall(r"`([^`\n]{2,200})`", text) + re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", text)
    out: set[str] = set()
    for s in spans:
        tok = s.strip().split()[0] if s.strip() else ""
        if not tok or tok.startswith(("http", "#", "mailto")):
            continue
        if not (tok.startswith(CHECK_TOP) or tok in CHECK_EXACT):
            continue
        if looks_like_pattern(tok):
            continue
        for cand in expand_braces(_clean_token(tok)):
            if "*" in cand or looks_like_pattern(cand):      # mô tả nhóm file, không phải một file
                continue
            cand = cand.rstrip("/")
            if not include_runtime and cand in RUNTIME_GENERATED:
                continue
            if cand.startswith(CHECK_TOP) or cand in CHECK_EXACT:
                out.add(cand)
    return sorted(out)


def runtime_generated_mentioned(text: str) -> list[str]:
    """Đường dẫn nhóm `RUNTIME_GENERATED` mà tài liệu nhắc tới (để in ra, không tính là lỗi)."""
    return [p for p in RUNTIME_GENERATED if p in text]


def check_referenced_files(root: Path, docs: tuple[str, ...] = DOC_FILES) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    checked = 0
    runtime: list[str] = []
    for name in docs:
        path = root / name
        if not path.exists():
            problems.append(f"{name}: file tài liệu không tồn tại")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        runtime.extend(p for p in runtime_generated_mentioned(text) if p not in runtime)
        for cand in referenced_paths(text):
            checked += 1
            if not (root / cand).exists():
                problems.append(f"{name}: nhắc `{cand}` nhưng không có trên đĩa")
    notes = [f"đã kiểm {checked} đường dẫn"]
    if runtime:
        notes.append("bỏ qua (file tự sinh lúc chạy): " + ", ".join(f"`{p}`" for p in runtime))
    return problems, notes


CODE_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)
INLINE_CMD = re.compile(r"`((?:PYTHONIOENCODING=[^\s]+\s+)?[^\n`]*?\.py[^\n`]*)`")
PY_LINE = re.compile(r"\bpython(?:\.exe)?\b|venv[/\\]Scripts[/\\]python\.exe|\bvenv\\Scripts\\python\b")
SCRIPT_RE = re.compile(r"([\w./\\-]+\.py)")


def command_lines(text: str) -> list[str]:
    """Mọi dòng lệnh trong block code (bash/text/console) + inline code có `.py`."""
    out: list[str] = []
    for _lang, body in CODE_FENCE.findall(text):
        for raw in body.splitlines():
            s = raw.strip()
            if not s or s.startswith(("#", "$", ">")) or s.endswith(("\\", "|")):
                continue
            out.append(s)
    out.extend(m.group(1).strip() for m in INLINE_CMD.finditer(text))
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def classify_command(root: Path, line: str) -> dict:
    """Phân loại một dòng lệnh: có trỏ script repo không, script đó có argparse không."""
    info = {"line": line, "kind": "khac", "script": "", "has_argparse": False}
    low = line.lower()
    if low.startswith(("pip", "conda", "npm", "git ", "cd ", "ls ", "rm ", "mkdir", "echo",
                       "source ", "streamlit", "ollama", "copy-item", "setx", "sha256sum", "for ",
                       "PYTHONIOENCODING=utf-8 for", "python -m venv", "python -m pip",
                       "python -m pytest", "pytest")):
        info["kind"] = "hal-tang" if low.startswith(("pip", "python -m venv", "source ", "copy-item", "cp ")) \
            else "pytest" if "pytest" in low else "lenh-shell"
        return info
    if not PY_LINE.search(line):
        info["kind"] = "khong-phai-python"
        return info
    m = SCRIPT_RE.search(line)
    if not m:
        info["kind"] = "python-khong-kenh-script"   # vd `python -m tools.loop.gate`
        mod = re.search(r"-m\s+([\w.]+)", line)
        if mod:
            info["script"] = mod.group(1).replace(".", "/") + ".py"
            info["kind"] = "repo-script"
        return info
    script = m.group(1).replace("\\", "/")
    info.update(kind="repo-script", script=script)
    path = root / script
    if path.exists():
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
            # "ArgumentParser(" cụ thể hơn "argparse": một file chỉ *nhắc* tới argparse
            # (comment/docstring) sẽ không bị xử oan là có --help.
            info["has_argparse"] = "ArgumentParser(" in body
        except OSError:
            info["has_argparse"] = False
    return info


def commands_from_docs(root: Path, docs: tuple[str, ...] = DOC_FILES) -> list[dict]:
    out = []
    for name in docs:
        p = root / name
        if not p.exists():
            continue
        for line in command_lines(p.read_text(encoding="utf-8", errors="replace")):
            info = classify_command(root, line)
            info["doc"] = name
            out.append(info)
    return out


def check_command_scripts(root: Path, cmds: list[dict]) -> tuple[list[str], list[str]]:
    """Lỗi: lệnh trỏ script repo mà file không tồn tại. Cảnh báo: script không có --help."""
    problems: list[str] = []
    warnings: list[str] = []
    for c in cmds:
        if c["kind"] != "repo-script" or not c["script"]:
            continue
        if not (root / c["script"]).exists():
            problems.append(f"{c['doc']}: lệnh gọi `{c['script']}` nhưng không có file — `{c['line'][:70]}`")
        elif not c["has_argparse"]:
            warnings.append(f"{c['doc']}: `{c['script']}` không có argparse ⇒ không có chế độ --help/dry-run")
    return problems, sorted(set(warnings))


def run_help(root: Path, scripts: list[str], timeout: int = 90) -> list[dict]:
    """Chạy `<python> <script> --help` cho từng script có argparse (mã 0 = đạt)."""
    py = root / "venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)
    results = []
    for script in sorted(set(scripts)):
        argv = [str(py), script, "--help"]
        try:
            proc = subprocess.run(argv, cwd=str(root), capture_output=True, text=True,
                                  timeout=timeout, encoding="utf-8", errors="replace",
                                  stdin=subprocess.DEVNULL)
            rc, err = proc.returncode, (proc.stderr or "")
        except subprocess.TimeoutExpired:
            rc, err = 124, "timeout"
        except OSError as exc:
            rc, err = 127, str(exc)
        results.append({"script": script, "rc": rc, "stderr_tail": err.strip().splitlines()[-1][:160] if err else ""})
    return results


def check_all(root: Path, *, run_help_checks: bool = False) -> dict:
    log_path = root / DECISION_LOG
    rows = decision_rows(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    log_problems = check_decision_log(rows) + check_source_paths(root, rows)
    files_problems, notes = check_referenced_files(root)
    cmds = commands_from_docs(root)
    cmd_problems, cmd_warnings = check_command_scripts(root, cmds)
    help_results: list[dict] = []
    help_problems: list[str] = []
    if run_help_checks:
        scripts = [c["script"] for c in cmds if c["kind"] == "repo-script" and c["has_argparse"]
                   and (root / c["script"]).exists()]
        help_results = run_help(root, scripts)
        for h in help_results:
            if h["rc"] != 0:
                help_problems.append(f"--help lỗi (rc={h['rc']}): {h['script']} — {h['stderr_tail']}")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision_rows": len(rows),
        "decision_problems": log_problems,
        "referenced_file_problems": files_problems,
        "commands_checked": len(cmds),
        "repo_scripts": len({c["script"] for c in cmds if c["kind"] == "repo-script" and c["script"]}),
        "command_problems": cmd_problems,
        "command_warnings": cmd_warnings,
        "help_checked": len(help_results),
        "help_results": help_results,
        "help_problems": help_problems,
        "notes": notes,
    }


SCOPE_KEYS = {
    "log": ("decision_problems",),
    "files": ("referenced_file_problems",),
    "commands": ("command_problems", "command_warnings", "help_problems"),
    "all": ("decision_problems", "referenced_file_problems", "command_problems",
            "command_warnings", "help_problems"),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--scope", default="all", choices=sorted(SCOPE_KEYS),
                    help="chỉ in và đếm lỗi của một nhóm kiểm (mặc định: all).")
    ap.add_argument("--run-help", action="store_true",
                    help="chạy --help trên từng script repo có argparse (mất ~1 phút)")
    ap.add_argument("--json", default="", help="ghi kết quả JSON (mặc định chỉ in)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    result = check_all(root, run_help_checks=args.run_help)
    problems: list[str] = []
    for key in SCOPE_KEYS[args.scope]:
        for line in result.get(key) or []:
            tag = "CẢNH BÁO" if key == "command_warnings" else "LỖI"
            problems.append(f"[{tag}] {line}")
    errors = [p for p in problems if p.startswith("[LỖI]")]
    print(f"[T7-docs] scope={args.scope}; sổ quyết định: {result['decision_rows']} mục; "
          f"lệnh đã phân loại: {result['commands_checked']} (script repo {result['repo_scripts']}); "
          f"--help: {result['help_checked']}")
    for line in problems:
        print(f"  {line}")
    for line in result["notes"]:
        print(f"  ghi chu: {line}")
    print(f"[T7-docs] kết luận: {'CÒN ' + str(len(errors)) + ' lỗi' if errors else 'SẠCH LỖI'}"
          f" — cảnh báo {len(result['command_warnings'])}")
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[T7-docs] ghi: {out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
