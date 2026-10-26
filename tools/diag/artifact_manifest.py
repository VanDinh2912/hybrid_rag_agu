# -*- coding: utf-8 -*-
"""T7/B3 — chụp manifest (đường dẫn, byte, sha256) cho các vùng artifact lớn.

Vì sao có file này: `models/`, `outputs/`, `logs/`, `chroma_db*`, `.ocr_cache*` chứa hàng trăm MB
sản phẩm sinh ra lúc chạy. Đợt dọn repo B3 KHÔNG xoá artifact nào; thay vào đó `.gitignore` giữ
chúng ngoài git và file manifest này ghi lại **tên + kích thước + SHA-256** để (a) biết bản đang
dùng là bản nào, (b) phát hiện artifact bị sửa/mất sau này mà không cần mở từng file.

Hai chế độ, mặc định chỉ đọc:

    venv/Scripts/python.exe tools/diag/artifact_manifest.py              # in tóm tắt
    venv/Scripts/python.exe tools/diag/artifact_manifest.py --write      # ghi ARTIFACT_MANIFEST.json
    venv/Scripts/python.exe tools/diag/artifact_manifest.py --check      # so với manifest đã ghi

`--check` trả mã 1 khi có file thiếu/thừa/đổi byte, 0 khi khớp. So sánh bỏ qua `generated_at` và
cờ `tracked` (hai thứ hợp lệ để đổi mà không phải sửa artifact).

Phạm vi (đúng B3): adapter SFT trong `models/`, toàn bộ `outputs/`, `logs/`, các thư mục
`chroma_db*`, `.ocr_cache*`. Artifact classifier/retrieval trong `models/` cũng được ghi để manifest
đủ bộ — chúng chưa nằm trong phạm vi ignore của B3 (xem PA-33).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "ARTIFACT_MANIFEST.json"
CHUNK = 1024 * 1024
SKIP_DIRS = {"__pycache__", ".ipynb_checkpoints"}
SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _scope_dirs() -> list[tuple[str, Path]]:
    """(tên scope, thư mục) — thứ tự cố định để manifest tái lập."""
    scopes: list[tuple[str, Path]] = [
        ("models_adapter", ROOT / "models" / "qwen25_05b_sft_adapter"),
        ("models_adapter_smoke", ROOT / "models" / "qwen25_05b_sft_smoke"),
        ("models_classifier_baseline", ROOT / "models" / "classifier_baseline"),
        ("models_classifier_v2", ROOT / "models" / "classifier_baseline_v2"),
        ("models_classifier_v3", ROOT / "models" / "classifier_baseline_v3"),
        ("models_retrieval_baseline", ROOT / "models" / "retrieval_baseline"),
        ("outputs", ROOT / "outputs"),
        ("logs", ROOT / "logs"),
    ]
    for p in sorted(ROOT.glob("chroma_db*")):
        if p.is_dir():
            scopes.append(("chroma", p))
    for p in sorted(ROOT.glob(".ocr_cache*")):
        if p.is_dir():
            scopes.append(("ocr_cache", p))
    return scopes


def _tracked_set() -> set[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True,
            stdin=subprocess.DEVNULL, check=True,
        ).stdout
    except Exception:
        return set()
    return {p.decode("utf-8", "replace") for p in out.split(b"\0") if p}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def build_manifest() -> dict:
    tracked = _tracked_set()
    scopes = []
    seen: set[str] = set()
    for name, d in _scope_dirs():
        files = []
        for f in sorted(d.rglob("*")):
            if not f.is_file():
                continue
            if any(part in SKIP_DIRS for part in f.parts):
                continue
            if f.name in SKIP_NAMES or f.name.startswith("~$"):
                continue
            rel = f.relative_to(ROOT).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            files.append(
                {
                    "path": rel,
                    "bytes": f.stat().st_size,
                    "sha256": _sha256(f),
                    "tracked": rel in tracked,
                }
            )
        scopes.append(
            {
                "name": name,
                "dir": d.relative_to(ROOT).as_posix(),
                "file_count": len(files),
                "total_bytes": sum(x["bytes"] for x in files),
                "files": files,
            }
        )
    return {
        "schema": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": ".",
        "algorithm": "sha256",
        "scopes": scopes,
        "summary": {
            "file_count": sum(s["file_count"] for s in scopes),
            "total_bytes": sum(s["total_bytes"] for s in scopes),
        },
    }


def _pairs(manifest: dict) -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    for scope in manifest.get("scopes", []):
        for f in scope.get("files", []):
            out[f["path"]] = (int(f["bytes"]), str(f["sha256"]))
    return out


def check(manifest_path: Path) -> int:
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    new = build_manifest()
    a, b = _pairs(old), _pairs(new)
    missing = sorted(set(a) - set(b))
    extra = sorted(set(b) - set(a))
    changed = sorted(p for p in set(a) & set(b) if a[p] != b[p])
    print(f"[manifest] {manifest_path}")
    print(f"  cũ: {len(a)} file / {sum(v[0] for v in a.values())} B")
    print(f"  nay: {len(b)} file / {sum(v[0] for v in b.values())} B")
    for label, items in (("THIẾU", missing), ("THỪA", extra), ("ĐỔI", changed)):
        if items:
            print(f"  {label} ({len(items)}):")
            for p in items[:20]:
                print("    -", p)
    if missing or extra or changed:
        print("[manifest] KẾT LUẬN: LỆCH — artifact đã đổi so với manifest.")
        return 1
    print("[manifest] KẾT LUẬN: KHỚP — không file nào đổi byte.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Manifest name/size/sha256 cho artifact lớn (chỉ đọc).")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="ghi manifest (mặc định ARTIFACT_MANIFEST.json)")
    g.add_argument("--check", action="store_true", help="so manifest đã ghi với đĩa; lệch ⇒ mã 1")
    ap.add_argument("--path", type=Path, default=DEFAULT_MANIFEST, help="đường dẫn manifest")
    ap.add_argument("--json", action="store_true", help="in JSON đầy đủ ra stdout")
    args = ap.parse_args(argv)

    if args.check:
        return check(args.path)

    man = build_manifest()
    if args.write:
        args.path.write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"[manifest] đã ghi {args.path} ({man['summary']['file_count']} file, "
              f"{man['summary']['total_bytes']} B)")
    if args.json:
        print(json.dumps(man, ensure_ascii=False, indent=1))
    else:
        for s in man["scopes"]:
            print(f"  {s['name']:<28} {s['file_count']:>4} file  {s['total_bytes']:>12} B  {s['dir']}")
        print(f"  {'TỔNG':<28} {man['summary']['file_count']:>4} file  "
              f"{man['summary']['total_bytes']:>12} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
