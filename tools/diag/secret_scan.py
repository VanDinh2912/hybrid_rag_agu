"""Quét CHỈ-ĐỌC (nghiệm thu cuối, mục 5): secret / đường dẫn cá nhân / dữ liệu cá nhân.

Vì sao không dùng `grep` một lần rồi thôi: mỗi loại rủi ro cần cách xử lý khác nhau, và một
lệnh grep thô sẽ trộn "key mẫu" (`your_gemini_api_key_here`) với key thật, trộn email tổ chức
trong corpus pháp lý (dữ liệu nghiệp vụ, ĐÃ chủ đích commit) với email cá nhân của người dùng
máy này. Bộ quét phân loại:

* `SECRET_COTHAT` — chuỗi trông như credential thật (định dạng Google/AWS/GitHub/OpenAI/key
  dài kèm từ khoá). **Mọi ca là lỗi**, kể cả một file test, vì repo có thể bị chia sẻ.
* `BI_MAU` — đúng khuôn nhưng là placeholder/đã bị che (`your_...`, `***`, `os.environ[...]`).
  Không phải lỗi; ghi ra để người duyệt thấy khuôn nào được chấp nhận.
* `DUONG_DAN_CA_NHAN` — `C:\\Users\\<tên>`, `/home/<tên>`, `/Users/<tên>` trong file được theo
  dõi.dõi. Không lộ bí mật nhưng làm fresh-clone trục trặc và lộ tên tài khoản máy.
* `DU_CAO_NHAN_HOC` — email/điện thoại/SỐ_GIAY_TO trong file track. Trong corpus pháp lý đây
  là dữ liệu nghiệp vụ có chủ đích (đơn trường, danh sách cán bộ); báo cáo liệt kê theo file
  và số lượng để người duyệt quyết, **không** tự xoá (xoá là đổi dữ liệu đã công bố).

Mặc định quét **file đang được git theo dõi** (`git ls-files`) — đúng phạm vi "file đã commit".
`--scope worktree` quét cả file chưa track để báo sớm.

Chạy:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/secret_scan.py
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/secret_scan.py --json tmp/secret_scan.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


SKIPPED_PARTS = {"venv", "venv_gpu", "venv_train", "node_modules", "__pycache__", ".git",
                 "chroma_db", "chroma_db_vie", "chroma_db_headers_old", ".ocr_cache",
                 ".ocr_cache_vie", ".generation_cache", "models", "tmp"}
TEXT_EXT = {".py", ".md", ".json", ".jsonl", ".txt", ".csv", ".yaml", ".yml", ".toml",
            ".example", ".env", ".ini", ".cfg", ".tsv", ".html", ".sql", ".lock", ".sh", ".ps1"}

#: (mã loại, tên, regex, cách xử lý)
PATTERNS: List[Tuple[str, str, re.Pattern]] = [
    ("SECRET_COTHAT", "Google API key (AIza…)", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("SECRET_COTHAT", "AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("SECRET_COTHAT", "OpenAI/Anthropic style sk-…", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("SECRET_COTHAT", "GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("SECRET_COTHAT", "Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("SECRET_COTHAT", "Private key block",
     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("SECRET_COTHAT", "Bearer/JWT credential dài",
     re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]{32,}=*")),
    ("SECRET_COTHAT", "Giao assignment key/truncate token với giá trị dài",
     re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*"
                r"[\"'][^\"'\s][^\"']{11,}[\"']")),
    ("BI_MAU", "Placeholder đã biết",
     re.compile(r"(?i)(your[_-]?\w*[_-]?api[_-]?key|changeme|xxxxxxxx+|<[^>]{3,25}>|\*\*\*+|REDACTED)")),

    ("DUONG_DAN_CA_NHAN", "Đường dẫn Windows theo tên user",
     re.compile(r"[A-Za-z]:[\\/]{1,2}[Uu]sers[\\/]+([A-Za-z0-9._-]{2,})")),
    ("DUONG_DAN_CA_NHAN", "Đường dẫn Unix theo tên user",
     re.compile(r"(?<![\w.])/(?:home|Users)/([A-Za-z0-9._-]{2,})")),
    ("DU_CAO_NHAN_HOC", "Email tổ chức/cá nhân",
     re.compile(r"\b[A-Za-z0-9._%+-]{3,}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("DU_CAO_NHAN_HOC", "Số điện thoại VN (0xxxxxxxxx / +84…)",
     re.compile(r"(?<![\d])(?:0(?:3[2-9]|5[2-9]|7[0|6-9]|8[1-5|7-9]|9[0-4|6-9])[-\s]?\d{3}[-\s]?\d{4}|\+84\d{9,10})(?![\d])")),
    ("DU_CAO_NHAN_HOC", "Căn cước/MSSV/định danh dài (chỉ khi dòng có từ khoá định danh)",
     re.compile(r"(?i)(?:msnv|mssv|c[ăa]n\s*c[ướu]c|cccd|định\s*danh|employee|hotline|"
                r"so_dien_thoai|ma_the)[^\d]{0,24}(\d{8,12})")),
]

DOMAIN_ALLOW_HINT = {"example.com", "localhost", "test.com", "yourdomain"}

#: Giá trị dạng key nhưng mang tên fixture rõ ràng => chuỗi giả trong test, không phải credential.
FIXTURE_VALUE_RE = re.compile(
    r"(?i)(test|dummy|fake|mock|sample|example|placeholder|contract|changeme|your_|xxx)")


def tracked_files(scope: str) -> List[str]:
    if scope == "worktree":
        return sorted(str(p.relative_to(ROOT).as_posix()) for p in ROOT.rglob("*") if p.is_file())
    # `stdin=DEVNULL`: tránh Windows kế thừa handle stdin hỏng của process cha
    # (D-35) -> `OSError: [WinError 6]`; kết quả quét không được phụ thuộc cách chạy.
    out = subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True,
                         stdin=subprocess.DEVNULL)
    return sorted(x.decode("utf-8", "replace") for x in out.stdout.split(b"\x00") if x)


def skipped(rel: str) -> bool:
    parts = Path(rel).parts
    if any(p in SKIPPED_PARTS or p.startswith("venv") for p in parts):
        return True
    suf = Path(rel).suffix.lower()
    name = Path(rel).name.lower()
    if suf not in TEXT_EXT and not (suf == "" and (name.startswith(".env") or name == "LICENSE")):
        return True
    return False


def redact(text: str, limit: int = 46) -> str:
    """Không in nguyên mẫu bí mật: giữ 4 ký tự đầu + độ dài."""
    t = " ".join(text.split())
    if len(t) <= limit:
        head = t[:4]
        return f"{head}…({len(t)} ký tự)" if len(t) > 10 else t
    return f"{t[:4]}…({len(t)} ký tự)"


def scan(files: List[str]) -> Dict[str, Any]:
    hits: List[Dict[str, Any]] = []
    scanned = 0
    for rel in files:
        if skipped(rel):
            continue
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        scanned += 1
        lines = text.splitlines()
        for lineno, line in enumerate(lines, 1):
            for loai, ten, rx in PATTERNS:
                for m in rx.finditer(line):
                    value = m.group(0)
                    if loai == "DU_CAO_NHAN_HOC" and "Email" in ten:
                        low = value.lower()
                        if any(d in low for d in DOMAIN_ALLOW_HINT):
                            continue
                    if loai == "SECRET_COTHAT" and (
                            "assignment" in ten or FIXTURE_VALUE_RE.search(value)):
                        # (a) `API_KEY = os.environ[...]` / <placeholder> -> đọc từ env
                        # (b) giá trị mang tên fixture (test-key-…, dummy…)-> chuỗi giả trong test
                        if re.search(r"(?i)os\.environ|getenv|dotenv|<[^>]+>|your_|placeholder",
                                     line) or FIXTURE_VALUE_RE.search(value):
                            ten = ("Giá trị lấy từ env/placeholder (không hardcode)"
                                   if re.search(r"(?i)os\.environ|getenv|dotenv|<[^>]+>", line)
                                   else "Chuỗi fixture trong test (không phải credential)")
                            loai = "BI_MAU"
                            hits.append(dict(file=rel, line=lineno, loai=loai, pattern=ten,
                                             sample=redact(value), length=len(value)))
                            continue
                    hits.append(dict(file=rel, line=lineno, loai=loai, pattern=ten,
                                     sample=redact(value), length=len(value)))
    by_loai = Counter(h["loai"] for h in hits)
    by_file: Dict[str, Counter] = {}
    for h in hits:
        by_file.setdefault(h["file"], Counter())[h["loai"]] += 1
    return dict(
        scope_files=len(files), files_scanned=scanned, total_hits=len(hits),
        by_loai=dict(by_loai),
        by_pattern={ten: sum(1 for h in hits if h["pattern"] == ten)
                    for _, ten, _ in PATTERNS},
        files={f: dict(c) for f, c in sorted(by_file.items())},
        secret_hits=[h for h in hits if h["loai"] == "SECRET_COTHAT"],
        duongdan_hits=[h for h in hits if h["loai"] == "DUONG_DAN_CA_NHAN"],
        pii_by_file={f: c["DU_CAO_NHAN_HOC"] for f, c in sorted(by_file.items())
                     if "DU_CAO_NHAN_HOC" in c},
        hits=hits,
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Quét secret / đường dẫn cá nhân / PII (chỉ đọc).")
    ap.add_argument("--scope", choices=["tracked", "worktree"], default="tracked")
    ap.add_argument("--json", help="ghi kết quả JSON (nên trỏ tmp/).")
    ap.add_argument("--max-list", type=int, default=25, help="số dòng in mỗi bảng")
    args = ap.parse_args(argv)

    result = scan(tracked_files(args.scope))
    print(f"[secret-scan] scope={args.scope}: {result['scope_files']} file ứng viên, "
          f"đã đọc {result['files_scanned']} file văn bản")
    for loai, n in sorted(result["by_loai"].items(), key=lambda kv: -kv[1]):
        print(f"  {loai:20} {n}")
    print(f"  --- theo khuôn ---")
    for ten, n in sorted(result["by_pattern"].items(), key=lambda kv: -kv[1]):
        if n:
            print(f"    {ten:55} {n}")
    if result["secret_hits"]:
        print("  ✗ SECRET_COTHAT (phải = 0):")
        for h in result["secret_hits"][:args.max_list]:
            print(f"     {h['file']}:{h['line']}  {h['pattern']}  {h['sample']}")
    else:
        print("  ✓ SECRET_COTHAT = 0 — không thấy credential thật trong file đã track")
    if result["duongdan_hits"]:
        print(f"  đường dẫn cá nhân: {len(result['duongdan_hits'])} dòng, "
              f"{len({h['file'] for h in result['duongdan_hits']})} file")
        seen = set()
        for h in result["duongdan_hits"][:args.max_list]:
            key = (h["file"], h["sample"])
            if key in seen:
                continue
            seen.add(key)
            print(f"     {h['file']}:{h['line']}  {h['sample']}")
    pii = result["pii_by_file"]
    if pii:
        tong = sum(pii.values())
        print(f"  PII học thuật: {tong} dòng trong {len(pii)} file đã track (5 file đầu):")
        for f, n in sorted(pii.items(), key=lambda kv: -kv[1])[:5]:
            print(f"     {f}: {n}")
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"[secret-scan] ghi: {args.json}")
    return 1 if result["secret_hits"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
