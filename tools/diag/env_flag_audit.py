"""Kiểm toán CHỈ-ĐỌC (nghiệm thu cuối, mục 3): mọi cờ env mới đều mặc định TẮT.

Ba tầng bằng chứng, không tầng nào thay tầng nào:

1. **Tĩnh** — quét `src/` + `tools/` + các script gốc, tìm mọi chỗ đọc từng cờ và ghi lại
   *literal mặc định* ngay trong code (`os.getenv(NAME, "<macro>")`, `_flag(NAME)`,
   `_env_flag(NAME, False)`…). Nếu một site nào đó mặc định `"1"` thì dòng đó đỏ, kể cả khi
   runtime đang TẮT — vì máy khác chỉ cần thiếu env là hành vi đổi.
2. **Động** — import module thật, **xoá** mọi tên cờ khỏi `os.environ` (nếu không xoá, kết luận
   sẽ phụ thuộc vào biến môi trường của máy người chạy), rồi gọi đúng hàm tra cờ của module.
   Đây là giá trị mà một bản clone mới thật sự nhìn thấy.
3. **Khai báo** — cờ có nằm trong `.env.example` không, và nếu có thì giá trị khai báo là gì.
   Thiếu trong `.env.example` **không** phải lỗi hành vi (env trống ⇒ code mặc định TẮT, đã
   chứng minh ở tầng 2) mà là khoảng trống **tài liệu**, nên phân loại riêng là `THU_TU`.

Ngoài ra báo cáo: mọi `os.environ.setdefault("NAME", …)` (nếu có tên cờ thì đó là "bật ngầm" ở
tầng import ⇒ LỖI), mặc định của các helper đọc env (`_flag`, `_env_flag`…), và mọi chuỗi
`chains/*.json` đặt cờ lên `1` (chuỗi đo chủ đích, không phải mặc định — ghi ra để không nhầm).

Chạy:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/env_flag_audit.py
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/env_flag_audit.py \
        --json tmp/env_flag_audit.json --md tmp/env_flag_audit_table.md
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: Giá trị được coi là "TẮT" khi đọc từ env/code.
OFF_LITERALS = {"", "0", "false", "no", "off", "none", "null"}

FlagRow = Dict[str, Any]

#: Danh sách CỜ ĐĂNG KÝ của chương vòng lặp P5 (T3/T4/T5/T7 + các lever đã bác).
#: `expect` = giá trị accessor phải trả khi env trống; `probe` = (module, hàm) đọc cờ đó.
LEVERS: List[FlagRow] = [
    dict(name="ENABLE_ANSWER_GUARD", group="lever", intro="T3 — guardrail sau sinh",
         expect=False, probe=("src.answer_guard", "answer_guard_enabled")),
    dict(name="ENABLE_DECOUPLED_REFUSAL", group="lever", intro="T3 — r8 từ chối tách đôi",
         expect=False, probe=("src.refusal_policy", "decoupled_refusal_enabled")),
    dict(name="ENABLE_EVIDENCE_SELECTION", group="lever", intro="T3 — r9 chọn câu căn cứ",
         expect=False, probe=("src.evidence_selection", "evidence_selection_enabled")),
    dict(name="ENABLE_RERANKER", group="lever", intro="T5a — r12 rerank cross-encoder",
         expect=False, probe=("src.reranker", "reranker_enabled")),
    dict(name="RERANKER_KEEP_CANDIDATES", group="lever", intro="T5a — trả nguyên pool 20",
         expect=False, probe=("src.reranker", "reranker_keep_candidates")),
    dict(name="RERANKER_FALLBACK", group="lever", intro="T5 — lùi RRF âm thầm (PA-18a)",
         expect=False, probe=("src.reranker", "reranker_fallback_enabled")),
    dict(name="ENABLE_CONTEXTUAL_HEADER", group="lever", intro="T5b — r13 header ngữ cảnh",
         expect=False, probe=("src.contextual_header", "contextual_header_enabled")),
    dict(name="ENABLE_ANSWER_RESCUE", group="lever", intro="r5b — giải cứu đáp án (đã BỊ BÁC)",
         expect=False, probe=("src.generator", "answer_rescue_enabled")),
    dict(name="NORMALIZE_SANITY_GUARD", group="lever", intro="r6 — guard lành mạnh chuẩn hoá",
         expect=False, probe=("src.query_normalizer", "normalize_sanity_guard_enabled")),
    dict(name="ROUTER_SOFT_FILTER", group="lever", intro="router — lọc mềm theo nguồn",
         expect=False, probe=("src.router", "router_soft_filter_enabled")),
    # Ngưỡng: chỉ có tác dụng khi cờ bật, nhưng vẫn phải có mặc định "không đổi hành vi cũ".
    dict(name="ROUTER_SOURCE_QUOTA", group="ngưỡng", intro="quota nguồn (0 = không áp trần)",
         expect=0, probe=("src.router", "router_source_quota")),
    dict(name="ROUTER_FILTER_RANK_BONUS", group="ngưỡng",
         intro="điểm cộng hạng bộ lọc (3 = đường production trước vòng lặp, không phải lever mới)",
         expect=3, probe=("src.router", "router_filter_rank_bonus")),
    dict(name="RESCUE_MIN_SCORE", group="ngưỡng",
         intro="ngưỡng giải cứu — không có accessor đơn, chỉ đọc khi rescue bật (kiểm tĩnh)",
         expect="0.8", probe=None),
]

READERS = ("getenv", r"environ\.get", r"environ\[", "_flag", "_env_flag", "_env_int",
           "_env_float", "_int_env", "_env_str")
READER_RE = re.compile(
    r"(?P<call>" + "|".join(READERS) + r")\(\s*[\"'](?P<name>[A-Z][A-Z0-9_]{3,})[\"']"
    r"\s*(?:,\s*(?P<default>[^)]*))?\)")
CONST_RE = re.compile(r"^(?P<const>[A-Z][A-Z0-9_]*_ENV)\s*=\s*[\"'](?P<name>[A-Z][A-Z0-9_]{3,})[\"']", re.M)
CONST_USE_RE = "(?:" + "|".join(r.lstrip("\\") for r in READERS) + r")"
SETDEFAULT_RE = re.compile(
    r"os\.environ\.setdefault\(\s*[\"'](?P<name>[A-Z][A-Z0-9_]{3,})[\"']\s*,\s*[\"'](?P<val>[^\"']*)[\"']")
HELPER_DEF_RE = re.compile(
    r"def\s+(?P<fn>_flag|_env_flag|_env_int|_env_float|_int_env|_env_str)\s*\([^)]*?"
    r"default(?:\s*:[^,=)]+)?\s*=\s*(?P<default>\"[^\"]*\"|\'[^\']*\'|False|True|[0-9.]+)"
    r"[^)]*\)[^:]*:", re.S)

SCAN_DIRS = ["src", "tools"]
SCAN_FILES = ["main.py", "demo_streamlit.py", "learn.py", "ingest.py", "evaluation.py"]


def _py_files() -> List[Path]:
    out: List[Path] = []
    for d in SCAN_DIRS:
        p = ROOT / d
        if p.is_dir():
            out += [f for f in p.rglob("*.py") if "__pycache__" not in f.parts]
    for f in SCAN_FILES:
        p = ROOT / f
        if p.is_file():
            out.append(p)
    return sorted(out)


def _is_off(literal: str) -> bool:
    return literal.strip().strip("\"'").lower() in OFF_LITERALS


def _matches(expect: Any, literal: str) -> bool:
    """Literal code có tương đương giá trị đã đăng ký không (chấp nhận 'False' == False)."""
    got = literal.strip().strip("\"'")
    if isinstance(expect, bool):
        return got.lower() in {"false", "0", "no", "off", ""} or got == repr(expect)
    return got == str(expect)


def _statement(text: str, start: int, max_lines: int = 4) -> str:
    """Lấy tối đa `max_lines` dòng kể từ vị trí match — đủ để thấy `or "0"` / `not in {...}`."""
    head = text.rfind("\n", 0, start) + 1
    pos, lines = head, 0
    while pos < len(text) and lines < max_lines:
        nl = text.find("\n", pos)
        if nl == -1:
            nl = len(text)
        step = text[pos:nl].strip()
        if lines and (not step or step.startswith(("return", "def ", "if ", "#", "@"))):
            break
        lines += 1
        pos = nl + 1
    return " ".join(text[head:pos].split())[:220]


def scan_static(names: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Mỗi tên cờ -> mọi site đọc nó (file, dòng, reader, literal mặc định nhìn thấy được)."""
    hits: Dict[str, List[Dict[str, Any]]] = {n: [] for n in names}
    named = set(names)
    for path in _py_files():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        # (a) tên cờ xuất bản thẳng trong lời gọi đọc env
        for m in re.finditer(READER_RE, text):
            if m.group("name") in named:
                hits[m.group("name")].append(dict(
                    file=rel, line=text[: m.start()].count("\n") + 1, reader=m.group("call"),
                    default=(m.group("default") or "").strip().rstrip(","), via_const=None,
                    snippet=_statement(text, m.start())))
        # (b) tên cờ đi qua hằng số module: `X_ENV = "ENABLE_X"` rồi `getenv(X_ENV)`
        consts = {m.group("const"): m.group("name") for m in re.finditer(CONST_RE, text)}
        for const_name, env_name in consts.items():
            if env_name not in named:
                continue
            pat = re.compile(
                rf"(?:{CONST_USE_RE})\s*\(\s*{re.escape(const_name)}\b\s*(?:,\s*(?P<default>[^)]*))?\)")
            for m in re.finditer(pat, text):
                hits[env_name].append(dict(
                    file=rel, line=text[: m.start()].count("\n") + 1,
                    reader=f"{m.group(0).split('(')[0].strip()}({const_name})",
                    default=(m.group("default") or "").strip().rstrip(","), via_const=const_name,
                    snippet=_statement(text, m.start())))
    return hits


def is_production(file: str) -> bool:
    """Đường production = `src/` hoặc script gốc; script đo trong `tools/` được phép đặt env
    cho chính lượt đo của nó, nên bị bật cờ ở đó chỉ là GHI CHÚ, không phải mặc định repo."""
    return file.startswith("src/") or "/" not in file


def scan_setdefault() -> List[Dict[str, Any]]:
    bad: List[Dict[str, Any]] = []
    named = {l["name"] for l in LEVERS}
    for path in _py_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(SETDEFAULT_RE, text):
            bad.append(dict(file=path.relative_to(ROOT).as_posix(),
                            line=text[: m.start()].count("\n") + 1,
                            name=m.group("name"), value=m.group("val"),
                            la_lever=m.group("name") in named))
    return bad


def scan_helper_defaults() -> List[Dict[str, str]]:
    """Mặc định của helper đọc env — `_flag(NAME)` không ghi literal nên phải kiểm ở định nghĩa."""
    out: List[Dict[str, str]] = []
    for path in _py_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(HELPER_DEF_RE, text):
            out.append(dict(file=path.relative_to(ROOT).as_posix(), fn=m.group("fn"),
                            default=m.group("default").strip()))
    return sorted(out, key=lambda r: (r["fn"], r["file"]))


def dotenv_example() -> Dict[str, str]:
    p = ROOT / ".env.example"
    out: Dict[str, str] = {}
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.split("#")[0].strip()
    return out


def runtime_value(probe: Tuple[str, str]) -> Any:
    mod = importlib.import_module(probe[0])
    fn: Optional[Callable[[], Any]] = getattr(mod, probe[1], None)
    if fn is None:
        return f"<{probe[0]} không có {probe[1]}>"
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - ghi lại, không làm chết audit
        return f"<lỗi {type(exc).__name__}: {exc}>"


def chains_with_lever_on() -> List[Dict[str, Any]]:
    """Các chuỗi đo chủ đích đặt cờ lên 1 — bắt buộc ghi ra để không đọc nhầm thành mặc định."""
    out: List[Dict[str, Any]] = []
    chains_dir = ROOT / "tools" / "loop" / "chains"
    if not chains_dir.is_dir():
        return out
    named = {l["name"] for l in LEVERS}
    for path in sorted(chains_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        envs: Dict[str, Any] = {}
        if isinstance(data, dict):
            envs.update({k: v for k, v in (data.get("env") or {}).items()})
            for rd in data.get("rounds") or []:
                envs.update({k: f"{v} (round {rd.get('id', '?')})" for k, v in (rd.get("env") or {}).items()})
        on = {k: v for k, v in envs.items()
              if k in named and str(v).strip().lower() not in OFF_LITERALS}
        if on:
            out.append(dict(chain=path.relative_to(ROOT).as_posix(), on=on))
    return out


def audit() -> Dict[str, Any]:
    names = [l["name"] for l in LEVERS]
    static = scan_static(names)
    example = dotenv_example()
    helpers = scan_helper_defaults()

    saved = {n: os.environ.pop(n) for n in names if n in os.environ}
    try:
        rows: List[Dict[str, Any]] = []
        for lever in LEVERS:
            name, expect = lever["name"], lever["expect"]
            sites = static.get(name, [])
            helper_map = {h["fn"]: h["default"] for h in helpers}
            # Site không ghi literal (đi qua helper hoặc `... or "0"`) -> suy ra từ định nghĩa
            # helper / từ biểu thức bao quanh, rồi mới phán quyết.
            effective: List[Dict[str, Any]] = []
            for s in sites:
                lit = s["default"]
                fn = s["reader"].split("(")[0].strip()
                if lit:
                    ok = _is_off(lit) or _matches(expect, lit)
                    note = ""
                elif fn in helper_map:
                    lit = helper_map[fn]
                    ok = _is_off(lit) or _matches(expect, lit)
                    note = f"(mặc định của helper `{fn}`)"
                else:
                    off_in_expr = re.search(r"or\s+[\"'](0|false|no|off)[\"']", s["snippet"]) \
                        or re.search(r"getenv\([^)]*\)\s*(?:\.strip\(\)\.lower\(\))?\s*(?:or|not in)", s["snippet"])
                    lit = s["snippet"][:120]
                    ok = bool(off_in_expr)
                    note = "(suy ra từ biểu thức)" if ok else "(KHÔNG XÁC ĐỊNH)"
                effective.append({**s, "effective_default": lit, "off_ok": ok, "note": note})
            bad = [s for s in effective if not s["off_ok"]]
            runtime = "(chỉ kiểm tĩnh)" if lever["probe"] is None else runtime_value(lever["probe"])
            dong_ok = lever["probe"] is None or (
                runtime is expect if isinstance(expect, bool) else str(runtime) == str(expect))
            khai_bao = example.get(name)
            verdict = "DAT"
            if not dong_ok:
                verdict = "LOI_RUNTIME"
            elif bad:
                verdict = "LOI_MAC_DINH"
            elif khai_bao is None:
                verdict = "THU_TU"
            elif not (_is_off(khai_bao) or _matches(expect, khai_bao)):
                verdict = "LOI_KHAI_BAO"
            rows.append(dict(
                name=name, group=lever["group"], intro=lever["intro"], expect=expect,
                probe=list(lever["probe"]) if lever["probe"] else None, runtime=runtime,
                dong_ok=dong_ok, static_sites=effective, static_bad=bad,
                dotenv_example=khai_bao if khai_bao is not None else "<không khai báo>",
                verdict=verdict))
    finally:
        os.environ.update(saved)

    all_setdefault = scan_setdefault()
    forced_on = [s for s in all_setdefault
                 if s["la_lever"] and not _is_off(s["value"]) and is_production(s["file"])]
    return dict(
        rows=rows,
        helper_defaults=helpers,
        setdefault_all=all_setdefault,
        setdefault_forced_on=forced_on,
        setdefault_chu_y=[s for s in all_setdefault if s not in forced_on
                          and s["la_lever"] and not _is_off(s["value"])],
        env_example_keys=sorted(example),
        env_example_on_preloop={k: v for k, v in example.items()
                                if k not in set(names) and v.strip().lower() in {"1", "true", "yes", "on"}},
        env_example_not_off={k: v for k, v in example.items()
                             if k in set(names) and not (_is_off(v) or any(_matches(l["expect"], v)
                                                                          for l in LEVERS if l["name"] == k))},
        chains_with_lever_on=chains_with_lever_on(),
        counts=dict(
            n_total=len(rows),
            duong=sum(1 for r in rows if r["verdict"] == "DAT"),
            thu_tu=sum(1 for r in rows if r["verdict"] == "THU_TU"),
            loi=sum(1 for r in rows if r["verdict"].startswith("LOI")),
        ),
    )


def md_table(result: Dict[str, Any]) -> str:
    lines = [
        "| Cờ env | Lever / ngưỡng | Mặc định code (tĩnh) | Giá trị khi env trống | `.env.example` | Phán quyết |",
        "|---|---|---|---|---|---|",
    ]
    for r in result["rows"]:
        sites = "; ".join(f"`{s['file']}:{s['line']}` → `{s['effective_default']}`"
                          for s in r["static_sites"][:3]) or "<không thấy site đọc>"
        if r["static_bad"]:
            sites += " ⚠"
        lines.append(f"| `{r['name']}` | {r['intro']} | {sites} | `{r['runtime']}` "
                     f"| `{r['dotenv_example']}` | {r['verdict']} |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Kiểm toán chỉ-đọc: cờ env mặc định TẮT (nghiệm thu cuối, mục 3).")
    ap.add_argument("--json", help="ghi kết quả JSON (nên trỏ tmp/).")
    ap.add_argument("--md", help="ghi bảng markdown (nên trỏ tmp/).")
    ap.add_argument("--task", help="chỉ in các dòng có tên chứa chuỗi này.")
    args = ap.parse_args(argv)

    result = audit()
    c = result["counts"]
    print(f"[env-audit] {c['n_total']} cờ đăng ký; ĐẠT {c['duong']}, "
          f"THƯ_TU {c['thu_tu']}, LỖI {c['loi']}")
    for r in result["rows"]:
        if args.task and args.task.lower() not in r["name"].lower():
            continue
        mark = "  " if r["verdict"] in ("DAT", "THU_TU") else "✗ "
        print(f"  {mark}{r['name']:28} expect={r['expect']!r:8} runtime={r['runtime']!s:22} "
              f"dotenv={r['dotenv_example']!s:18} {r['verdict']}")
    print(f"  helper mặc định: {[(h['fn'], h['default']) for h in result['helper_defaults']][:8]}")
    if result["setdefault_forced_on"]:
        print(f"  ✗ os.environ.setdefault BẬT cờ: {result['setdefault_forced_on']}")
    else:
        print("  os.environ.setdefault: không có site nào bật cờ")
    if result["chains_with_lever_on"]:
        print(f"  ghi chú: {len(result['chains_with_lever_on'])} chuỗi đo đặt cờ lên 1 (chủ đích)")
    thieu = [r["name"] for r in result["rows"] if r["dotenv_example"] == "<không khai báo>"]
    print(f"  .env.example khai báo {len(result['env_example_keys'])} key; "
          f"cờ đăng ký CÓ trong .env.example: {len(result['rows']) - len(thieu)}/{len(result['rows'])}")
    print(f"  .env.example bật sẵn (tính năng tiền-vòng-lặp, ghi nhận): {result['env_example_on_preloop']}")
    if thieu:
        print(f"  thiếu khai báo: {', '.join(thieu)}")
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                                   encoding="utf-8")
        print(f"[env-audit] ghi: {args.json}")
    if args.md:
        Path(args.md).write_text(md_table(result), encoding="utf-8")
        print(f"[env-audit] ghi bảng: {args.md}")
    return 1 if (c["loi"] or result["setdefault_forced_on"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
