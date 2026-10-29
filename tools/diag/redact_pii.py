# -*- coding: utf-8 -*-
"""PA-31 — xuất BẢN REDACTED (chỉ đọc nguồn) cho các tệp có cảnh báo nhân thân.

Vì sao là tool MỚI chứ không sửa `tools/diag/secret_scan.py`: máy quét là dụng cụ đo đã công bố
(`0 secret / 0 đường dẫn / 89 PII / 8 file`) — sửa nó là đổi thước. Tool này **nhập** đúng
`PATTERNS` và `DOMAIN_ALLOW_HINT` của máy quét để không phát minh khuôn mới, rồi chỉ làm một việc
chưa ai làm: **ghi ra bản đã che**.

Nguyên tắc:
* **Không sửa tệp gốc** (mở chỉ-đọc). Bản che ghi sang `--out` (mặc định `data/loop/diag_redacted/`).
* **Giữ nguyên số dòng** và **giữ nguyên kiểu xuống dòng** (đọc/ghi `newline=""`): tệp `.jsonl` vẫn
  đúng số bản ghi, `.json` vẫn parse được — có kiểm ngay trong lượt chạy.
* **Che tất định**: cùng một giá trị trong một tệp ⇒ cùng một token (`[EMAIL_1]`, `[PHONE_2]`,
  `[ID_1]`…), đánh số theo lần xuất hiện đầu. Token không chứa `@`, `"`, `\\`, xuống dòng ⇒ không
  làm hỏng JSON/CSV.
* **Báo số trước/sau**: số dòng có cảnh báo và số lần khớp TRƯỚC khi che, và số lần khớp CÒN LẠI
  trên chính bản che (phải = 0). Không sửa số đã công bố của máy quét.

Chạy:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/redact_pii.py
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/redact_pii.py --dry
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "diag"))

import secret_scan  # noqa: E402  — dùng CHUNG khuôn với máy quét đã công bố

DEFAULT_OUT = ROOT / "data" / "loop" / "diag_redacted"

#: 8 tệp trong hồ sơ PA-31 (25-10) — đúng danh sách đã công bố, không thêm không bớt.
PA31_FILES: List[str] = [
    "data/loop/diag/referee_labeling_r5.jsonl",
    "data/loop/diag/referee_labeling_r5.md",
    "data/loop/diag/b_gemini_top6/rows.jsonl",
    "data/loop/diag/a_oracle_qwen/rows.jsonl",
    "data/loop/diag/c_gold_window_qwen/rows.jsonl",
    "outputs/ab_results_without_classifier.json",
    "outputs/ab_results_with_classifier.json",
    "data/loop/diag/corpus_diagnostics/manual_20_segments.txt",
]

#: Chỉ che lớp dữ liệu cá nhân; KHÔNG che SECRET_COTHAT (máy quét khai 0 ca) hay BI_MAU.
PII_PATTERNS: List[Tuple[str, str, re.Pattern]] = [
    (kind, name, rx) for kind, name, rx in secret_scan.PATTERNS if kind == "DU_CAO_NHAN_HOC"
]
TOKEN_FOR = {"Email tổ chức/cá nhân": "EMAIL",
             "Số điện thoại VN (0xxxxxxxxx / +84…)": "PHONE",
             "Căn cước/MSSV/định danh dài (chỉ khi dòng có từ khoá định danh)": "ID"}

#: Lượt che THỨ HAI — khuôn RỘNG cho số điện thoại VN có dấu phân cách (dấu chấm, khoảng trắng
#: từng nhóm). Khuôn đã công bố chỉ cho MỘT dấu phân cách tuỳ chọn nên bỏ sót dạng nhóm kiểu
#: `09xx xxx xxx`, `0xxx.xxx.xxx`. Đây là lớp BỔ SUNG của tool mới: KHÔNG đổi `secret_scan.PATTERNS`,
#: KHÔNG đổi số đã công bố (89), và báo riêng để người đọc thấy phần nào do khuôn cũ bỏ sót.
#: Chốt chống dương tính giả: ứng viên phải có **đúng** 10 hoặc 11 chữ số — nhờ vậy chuỗi số dài và
#: số thực (`0.<10 chữ số>`) không bị cắt làm đôi.
BROAD_PHONE_RE = re.compile(r"(?<![\d.])0[\d.\-\s]{8,16}(?![\d])")
#: Tiền tố hợp lệ: di động 03/05/07/08/09 (10 số), cố định 02x (11 số). `000 988.400` là số tiền.
MOBILE_HEADS = ("03", "05", "07", "08", "09")


def phone_ok(candidate: str) -> bool:
    """Ứng viên có phải số điện thoại VN trọn vẹn (đúng 10/11 chữ số, tiền tố hợp lệ)?"""
    d = re.sub(r"[\s.\-]", "", candidate)
    if not d.isdigit():
        return False
    if re.fullmatch(r"0\.\d+", candidate):
        # `0.987654321` là số THỰC (10 chữ số, đầu 09 ⇒ nếu chỉ đếm chữ số sẽ bị che nhầm).
        # Số điện thoại viết có dấu chấm luôn có ≥2 dấu (dạng `0xxx.xxx.xxx`), khác dạng này.
        # Đo trước khi thêm luật: 0 ca trong 8 tệp PA-31 ⇒ luật này không đổi một con số đã báo.
        return False
    if len(d) == 10:
        return d[:2] in MOBILE_HEADS
    if len(d) == 11:
        return d[:2] == "02"
    return False


def mask_broad_phone(line: str, seen: Dict[str, str]) -> Tuple[str, int]:
    """Che số điện thoại VN có dấu phân cách; trả (dòng mới, số lần che)."""
    n = 0
    out = []
    pos = 0
    for m in BROAD_PHONE_RE.finditer(line):
        cand = m.group(0).rstrip(" .-")
        if not phone_ok(cand):
            continue
        key = "BP:" + re.sub(r"[\s.\-]", "", cand)
        if key not in seen:
            seen[key] = f"[PHONE_B_{sum(1 for v in seen.values() if v.startswith('[PHONE_B_')) + 1}]"
        out.append(line[pos:m.start()])
        out.append(seen[key])
        pos = m.start() + len(cand)
        n += 1
    out.append(line[pos:])
    return "".join(out), n


def out_path_for(rel: str, out_dir: Path) -> Path:
    """Giữ cấu trúc, chỉ bỏ tiền tố `data/loop/` cho gọn (tránh data/loop/diag_redacted/data/loop/…)."""
    r = Path(rel)
    parts = r.parts
    if parts[:2] == ("data", "loop"):
        return out_dir.joinpath(*parts[2:])
    return out_dir / r


def mask_line(line: str, start_index: Dict[str, int], seen: Dict[str, str], json_mode: bool = False):
    """Che MỌI khớp PII trên một dòng; trả (dòng mới, số khớp).

    `json_mode`: chuỗi JSON có escape `\\n`, `\\t`… nên một khớp có thể BẮT ĐẦU giữa escape
    (ví dụ dấu `-` + escape `\\n` + email viết liền ⇒ khuôn email khớp từ chữ `n` của `\\n`), và
    thay bằng `[EMAIL_1]` sẽ tạo `\\[` = escape KHÔNG hợp lệ. Sau khi che, mọi `\\` đứng ngay trước
    token được nhân đôi (`\\\\`) để JSON vẫn hợp lệ; chuỗi gốc parse được nên `\\[` chỉ có thể do ta
    sinh.
    """
    n = 0
    for kind, name, rx in PII_PATTERNS:
        prefix = TOKEN_FOR[name]

        def repl(m: "re.Match") -> str:
            nonlocal n
            value = m.group(1) if prefix == "ID" else m.group(0)
            if name.startswith("Email") and any(
                    d in value.lower() for d in secret_scan.DOMAIN_ALLOW_HINT):
                return m.group(0)  # email ví dụ/allowlist: máy quét cũng bỏ qua
            key = f"{prefix}:{value}"
            if key not in seen:
                start_index[prefix] = start_index.get(prefix, 0) + 1
                seen[key] = f"[{prefix}_{start_index[prefix]}]"
            n += 1
            tok = seen[key]
            if prefix == "ID":
                whole = m.group(0)
                return whole.replace(value, tok)
            return tok

        line = rx.sub(repl, line)
    if json_mode:
        line = re.sub(r"\\(\[(?:EMAIL|PHONE|ID)_\d+\])",
                      lambda m: "\\\\" + m.group(1), line)
    return line, n


def count_hits(text: str) -> Tuple[int, int]:
    """(số dòng có ít nhất 1 khớp, tổng số khớp PII) — cùng luật bỏ qua với máy quét."""
    dong = 0
    tong = 0
    for line in text.splitlines():
        c = 0
        for kind, name, rx in PII_PATTERNS:
            for m in rx.finditer(line):
                if name.startswith("Email") and any(
                        d in m.group(0).lower() for d in secret_scan.DOMAIN_ALLOW_HINT):
                    continue
                c += 1
        if c:
            dong += 1
            tong += c
    return dong, tong


def count_broad(text: str) -> int:
    """Số chuỗi còn thoả khuôn RỘNG (số điện thoại VN có dấu phân cách) trong `text`.

    Dùng CÙNG chốt `phone_ok` như `mask_broad_phone` — nếu hai bên lệch luật thì cổng
    "broad_phone_after = 0" sẽ hoặc báo đỏ giả hoặc bỏ lọt.
    """
    n = 0
    for line in text.splitlines():
        for m in BROAD_PHONE_RE.finditer(line):
            if phone_ok(m.group(0).rstrip(" .-")):
                n += 1
    return n


def redact_file(rel: str, out_dir: Path, dry: bool) -> Dict:
    src = ROOT / rel
    if not src.is_file():
        return {"path": rel, "error": "THIẾU tệp nguồn"}
    raw = src.read_text(encoding="utf-8", errors="replace", newline="")
    lines = raw.splitlines(keepends=True)
    start_index: Dict[str, int] = {}
    seen: Dict[str, str] = {}
    new_lines: List[str] = []
    hits = 0
    broad_hits = 0
    json_mode = rel.endswith(".json") or rel.endswith(".jsonl")
    for line in lines:
        body = line.rstrip("\r\n")
        eol = line[len(body):]
        masked, n = mask_line(body, start_index, seen, json_mode=False)
        masked, nb = mask_broad_phone(masked, seen)
        hits += n
        broad_hits += nb
        if json_mode:
            masked = re.sub(r"\\(\[(?:EMAIL|PHONE|ID)_\d+\])",
                            lambda m: "\\\\" + m.group(1), masked)
        new_lines.append(masked + eol)
    out_text = "".join(new_lines)

    before_dong, before_tong = count_hits(raw)
    after_dong, after_tong = count_hits(out_text)
    broad_before = count_broad(raw)
    broad_after = count_broad(out_text)

    # Kiểm cấu trúc: số dòng và tính hợp lệ JSON
    json_ok = None
    if rel.endswith(".jsonl"):
        try:
            [json.loads(x) for x in out_text.splitlines() if x.strip()]
            json_ok = True
        except Exception:
            json_ok = False
    elif rel.endswith(".json"):
        try:
            json.loads(out_text)
            json_ok = True
        except Exception:
            json_ok = False

    rec = {"path": rel, "out": str(out_path_for(rel, out_dir).relative_to(ROOT).as_posix()),
           "lines_before": len(raw.splitlines()), "lines_after": len(out_text.splitlines()),
           "pii_lines_before": before_dong, "pii_hits_before": before_tong,
           "masked_here": hits, "pii_lines_after": after_dong, "pii_hits_after": after_tong,
           "broad_phone_before": broad_before, "broad_phone_masked_here": broad_hits,
           "broad_phone_after": broad_after,
           "bytes_before": len(raw.encode("utf-8")), "bytes_after": len(out_text.encode("utf-8")),
           "json_valid_after": json_ok, "tokens": len(seen)}
    if not dry:
        dst = out_path_for(rel, out_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(out_text, encoding="utf-8", newline="")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description="PA-31 — xuất bản redacted (chỉ đọc nguồn).")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry", action="store_true", help="chỉ đo, không ghi bản che")
    args = ap.parse_args()

    out_dir = Path(args.out)
    recs = [redact_file(rel, out_dir, args.dry) for rel in PA31_FILES]

    print(f"{'tệp':60s} {'dòng':>6} {'PII dòng':>8} {'khớp':>5} {'còn':>4} "
          f"{'SĐT rộng':>9} {'còn':>4} {'JSON':>5}")
    for r in recs:
        if "error" in r:
            print(f"{r['path']:60s} {r['error']}")
            continue
        print(f"{r['path']:60s} {r['lines_before']:>6} {r['pii_lines_before']:>8} "
              f"{r['pii_hits_before']:>5} {r['pii_hits_after']:>4} "
              f"{r['broad_phone_before']:>9} {r['broad_phone_after']:>4} "
              f"{str(r['json_valid_after']):>5}")

    ok = [r for r in recs if "error" not in r]
    print("\nTỔNG: %d tệp · khuôn đã công bố: %d lần khớp trước / %d còn lại · "
          "khuôn RỘNG (bổ sung): %d trước / %d còn lại"
          % (len(ok), sum(r["pii_hits_before"] for r in ok), sum(r["pii_hits_after"] for r in ok),
             sum(r["broad_phone_before"] for r in ok), sum(r["broad_phone_after"] for r in ok)))
    print("      · dòng PII (khuôn công bố) trước khi che: %d"
          % sum(r["pii_lines_before"] for r in ok))
    dong_ok = all(r["lines_before"] == r["lines_after"] for r in ok)
    json_ok = all(r["json_valid_after"] in (True, None) for r in ok)
    clean = all(r["pii_hits_after"] == 0 and r["broad_phone_after"] == 0 for r in ok)
    print(f"cổng: số dòng giữ nguyên={dong_ok} · JSON hợp lệ={json_ok} · PII còn lại=0 → {clean}")
    if not args.dry:
        rep = {"schema": "pa31-redaction/v1", "files": recs,
               "gate": {"lines_kept": dong_ok, "json_valid": json_ok, "pii_zero_after": clean},
               "note": "Bản gốc KHÔNG bị sửa; đây là bản sao đã che."}
        (out_dir / "REDACTION_REPORT.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"ghi báo cáo: {out_dir / 'REDACTION_REPORT.json'}")
    return 0 if (dong_ok and json_ok and clean) else 1


if __name__ == "__main__":
    raise SystemExit(main())
