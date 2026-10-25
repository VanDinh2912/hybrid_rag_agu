#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đồ dùng chung cho ba script trả lời **câu hỏi hội đồng** (CHỈ-ĐỌC).

Ba câu hỏi cần trả lời được bằng số, không bằng lời hứa:

1. *Hệ thống có bịa câu trả lời không?* — `council_check_fabrication.py`
2. *Trọng tài có đáng tin không?* — `council_check_referee.py`
3. *`gold@6 = 0,5186` nghĩa là gì?* — `council_check_gold6.py`

Nguyên tắc của kit này:

* không sửa file nào, không ghi vào `data/loop/rounds/`, không gọi mạng/Gemini/Ollama;
* mọi con số đều **tính lại** từ artifact đã đóng, và in kèm đường dẫn file nguồn;
* chỗ nào chưa có bằng chứng thì in `CHƯA` chứ không suy diễn (ví dụ nhãn tay của người);
* muốn lưu bằng chứng thì dùng `--json tmp/<tên>.json` (thư mục tmp, không phải artifact đóng).

Định dạng số theo qui ước Việt (dấu `,` thập phân) vì các con số này được trích nguyên
vào `docs/reports/test_final.md` và bảng "công bố | tính lại | khớp".
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "tools" / "loop"), str(ROOT / "tools" / "diag")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ROUNDS_DIR = ROOT / "data" / "loop" / "rounds"

# Thứ tự round cố định (không phụ thuộc sorted() chữ số — "r10" xếp trước "r2").
ROUND_ORDER = (
    "r0", "r0_pilot", "r1", "r2", "r3", "r4", "r5", "r5b", "r6", "r7",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14_repro_off", "r15_repro_on",
)

# Ba verdict mà trọng tài xếp vào nhóm "nói sai một cách chủ động" (gate.py: SEVERE_VERDICTS).
SEVERE_VERDICTS = (
    "FAIL_FABRICATED",
    "FAIL_CONFIRMED_FALSE_PREMISE",
    "FAIL_HALLUCINATED_ON_UNANSWERABLE",
)

NGHIA_SEVERE = {
    "FAIL_FABRICATED": (
        "chunk vàng ĐÃ ở trong cửa sổ sinh mà câu trả lời vẫn có ≥1 khẳng định "
        "(số/mã/tên riêng) không tìm thấy trong ngữ cảnh + câu hỏi + tên nguồn"
    ),
    "FAIL_HALLUCINATED_ON_UNANSWERABLE": (
        "câu ngoài phạm vi (REFUSE_OOD/REFUSE_MISSING_DOC, hoặc expected_answer_type="
        "'refuse') mà hệ thống KHÔNG từ chối — nhận diện sai đề, nặng nhất"
    ),
    "FAIL_CONFIRMED_FALSE_PREMISE": (
        "câu bẫy (TRAP/TRAP_OCR) mà hệ thống xác nhận luôn con số SAI có trong tiền đề"
    ),
}


def rel(path: Any) -> str:
    """Đường dẫn tương đối repo, thuậnslash, để in ra lệnh copy-paste được."""
    p = Path(path)
    if not p.is_absolute():
        # đường dẫn tương đối hiểu theo gốc repo, không theo thư mục hiện hành
        p = ROOT / p
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def src(path: Any) -> str:
    """Nhãn 'nguồn' thống nhất cho mọi bảng: `  ← data/loop/...`."""
    return f"← {rel(path)}"


def read_json(path: Any) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Any) -> list[dict]:
    out: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def rounds_with(phase: str) -> list[str]:
    """Các round có `verdicts_<phase>.jsonl`, theo thứ tự ROUND_ORDER."""
    suf = f"verdicts_{phase}.jsonl"
    return [r for r in ROUND_ORDER if (ROUNDS_DIR / r / suf).exists()]


def verdicts_path(rnd: str, phase: str) -> Path:
    return ROUNDS_DIR / rnd / f"verdicts_{phase}.jsonl"


def summary_path(rnd: str, phase: str) -> Path:
    return ROUNDS_DIR / rnd / f"round_summary_{phase}.json"


def full_path(rn: str) -> Path:
    return ROUNDS_DIR / rn / "full.jsonl"


def load_round(rnd: str, phase: str) -> list[dict]:
    return read_jsonl(verdicts_path(rnd, phase))


def settings_of(rnd: str, phase: str = "full") -> dict:
    p = summary_path(rnd, phase)
    if not p.exists():
        return {}
    return dict(read_json(p).get("settings") or {})


def answered_rows(rows: Iterable[dict]) -> list[dict]:
    """Định nghĩa 'đã trả lời' của gate.stats(): đã chấm, KHÔNG phải câu từ chối, có chữ.

    Phải dùng lại đúng định nghĩa này (chứ không phải 'mọi row có answer') thì số
    tái lập mới khớp `fabrication_rate_on_answered` đã công bố trong round_summary.
    """
    return [
        r for r in rows
        if r.get("verdict") != "PENDING_GENERATION"
        and not r.get("is_refusal")
        and (r.get("answer_chars") or 0) > 0
    ]


def fabrication_rate(rows: Iterable[dict]) -> Optional[float]:
    ans = answered_rows(rows)
    if not ans:
        return None
    return round(sum(1 for r in ans if r.get("unsupported")) / len(ans), 4)


def gold_flags(rows: Iterable[dict]) -> dict[str, tuple]:
    """id -> (has_gold_chunk, gold_in_top_k, gold_rank_in_sources) cho so item-level."""
    return {
        r["id"]: (r.get("has_gold_chunk"), r.get("gold_in_top_k"), r.get("gold_rank_in_sources"))
        for r in rows
    }


def gold_rate(rows: Iterable[dict]) -> tuple[int, int, Optional[float]]:
    """(n_item có gold, n_trúng trong top_k, tỉ lệ) — mẫu số là item CÓ chunk vàng."""
    g = [r for r in rows if r.get("has_gold_chunk")]
    hit = [r for r in g if r.get("gold_in_top_k")]
    return len(g), len(hit), (round(len(hit) / len(g), 4) if g else None)


def sha256_of(path: Any) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_state(path: Any) -> str:
    """'tracked-sach' | 'tracked-ban' | 'chua-commit' | 'khong-co-git'.

    Dùng cho câu hỏi 'dụng cụ đo có bị sửa để qua cổng không': nếu file chưa vào
    git thì KHÔNG THỂ nói 'không đổi so với HEAD' — đó là khoảng trống PA-26, phải
    in ra đúng như vậy.
    """
    p = Path(path)
    if not p.exists():
        return "thieu-file"
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel(p)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError:
        return "khong-co-git"
    if tracked.returncode != 0:
        return "chua-commit"
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", rel(p)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return "tracked-ban" if (dirty.stdout or "").strip() else "tracked-sach"


def fmt(value: Any, nd: int = 4) -> str:
    """Số theo kiểu Việt; None -> '—' (không in 'None' vào báo cáo)."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    return f"{value:.{nd}f}".replace(".", ",")


def pct(n: int, d: int, nd: int = 2) -> str:
    if not d:
        return "—"
    return f"{fmt(100.0 * n / d, nd)}%"


def md_table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join("---" for _ in headers) + "|"
    body = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
    return "\n".join([head, sep, body]) if body else "\n".join([head, sep, "| (trống) |"])


def dat(x: bool) -> str:
    return "ĐẠT" if x else "KHÔNG ĐẠT"


def emit(result: dict, args: argparse_ns) -> None:  # type: ignore[valid-type]
    """Ghi `--json` nếu được yêu cầu; mặc định KHÔNG ghi gì (script chỉ-đọc)."""
    out = getattr(args, "json", None)
    if not out:
        return
    path = Path(out)
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{src(path)}")


def banner(title: str, question: str) -> None:
    print(f"\n=== {title} ===")
    print(f"Câu hỏi hội đồng: {question}")


def kv(label: str, value: Any, source: Any = None) -> None:
    line = f"  {label}: {value}"
    if source is not None:
        line += f"   {src(source)}"
    print(line)
