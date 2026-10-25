# -*- coding: utf-8 -*-
"""T7 — kiểm kê và (tuỳ chọn, có duyệt) dọn `tmp/` một cách an toàn.

Vì sao có file này: `tmp/` là nơi chứa driver, log, cache lạnh của từng round, và **không nằm trong
git** (chưa từng được commit). Nghĩa là "xoá là mất hẳn" — không có `git checkout` để lùi. PA-24 từng
dừng ở bản kiểm kê + lệnh `rm -rf` viết tay vì chưa có duyệt. Script này biến việc đó thành **dụng cụ
có cổng an toàn**, với bốn lớp chặn:

1. **Mặc định là LiỆT KÊ (dry-run).** Không có `--yes` thì **không xoá gì cả**, dù mọi điều kiện khác
   hợp lệ. Báo cáo chỉ ra từng mục: đề xuất xoá / đang được dẫn chứng / bị chặn vì thuộc vùng bảo vệ.
2. **Vùng cho phép duy nhất là `<root>/tmp`.** Mọi đường dẫn khác — `outputs/`, `data/loop/rounds/`,
   `data/loop/diag/`, `chroma_db*`, `models/`, `data/training/`, `.git/`, `src/`, `docs/`, `tests/`,
   hoặc `../`/tuyệt đối — **bị từ chối kể cả khi có `--yes`**.
3. **Mục được trích dẫn trong tài liệu thì không xoá được.** Một mục tên `X` coi như "được dẫn" nếu
   chuỗi `tmp/X` xuất hiện trong `docs/**/*.md`, `ROADMAP.md`, `README.md` hoặc `data/loop/README.md`.
   Đây đúng là định nghĩa đã dùng ở PA-24, nên danh sách "GIỮ" của báo cáo và của dụng cụ không lệch nhau.
4. **Không đi theo symlink/junction ra ngoài `tmp/`.** Mọi mục là liên kết tượng trưng đều bị chặn
   (không cần biết nó trỏ vào đâu), vì `realpath` của nó có thể nằm ngoài repo.

Dùng:

    # liệt kê (mặc định, an toàn tuyệt đối)
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/tmp_cleanup.py

    # liệt kê kèm lý do từng mục, xuất JSON để đối chiếu với PA-24
    ... tools/diag/tmp_cleanup.py --json tmp/cleanup_report.json

    # xoá THẬT — chỉ sau khi user đã gạch tên; vẫn bị chặn nếu mục được dẫn/ outside tmp / symlink
    ... tools/diag/tmp_cleanup.py --yes --only envcheck.log --only gate_demo_rounds

`--root` chỉ tồn tại để test chạy trên cây tạm (xem `tests/test_t7_tmp_cleanup.py`); mặc định là repo.
Hoàn tác của chính script này: không ghi gì vào `tmp/` ngoài file `--json` nếu được yêu cầu.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Tên mục trong tmp/ được coi là "đang được dẫn chứng" — KHÔNG xoá, kể cả --yes.
DOC_GLOBS = ("docs/**/*.md", "ROADMAP.md", "README.md", "data/loop/README.md")

# Vùng bảo vệ: mọi đường dẫn tương đối với root, khớp theo tiền tố. Không nằm trong tmp/,
# nhưng khai báo ở đây để `check_target()` chặn cả trường hợp đi lạc (qua `..`, symlink, tuyệt đối).
PROTECTED_PREFIXES = (
    "outputs",
    "data/loop/rounds",
    "data/loop/diag",
    "data/training",
    "chroma_db",
    "chroma_db_vie",
    "models",
    ".git",
    ".venv",
    "venv",
    "venv_gpu",
    "venv_train",
    "src",
    "tools",
    "tests",
    "docs",
    "ui",
    ".env",
)

ALLOWED_SUBDIR = "tmp"


class CleanupRefusal(RuntimeError):
    """Đường dẫn bị từ chối — lý do luôn là chuỗi tiếng Việt đọc được, in ra hội đồng."""


def _norm(path: Path | str) -> str:
    return os.path.normcase(str(path))


def is_link(path: Path, allow: Path) -> bool:
    """True nếu `path` là symlink **hoặc** junction/ntfs reparse dẫn tới nơi khác.

    Windows: `Path.is_symlink()` trả về **False** với junction (`mklink /J`), nên chỉ dựa vào
    `is_symlink()` là lỗ hổng — junction vẫn làm `realpath` đổi chỗ. So `realpath` với vị trí
    danh nghĩa bên trong `tmp/` để bắt cả hai loại, không phụ thuộc quyền tạo symlink của test.
    """
    if path.is_symlink():
        return True
    nominal = _norm(Path(_norm(os.path.realpath(allow))) / path.name)
    return _norm(os.path.realpath(path)) != nominal


def _dir_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            p = Path(root) / f
            try:
                total += p.stat().st_size
            except OSError:
                pass
        # không tính dung lượng symlink để tránh "đếm hộ" file ngoài cây
        for d in dirs:
            p = Path(root) / d
            if p.is_symlink():
                dirs.remove(d)
    return total


def cited_names(root: Path) -> set[str]:
    """Tập tên mục `tmp/<ten>` được nhắc trong tài liệu (định nghĩa 'dẫn chứng' của PA-24)."""
    names: set[str] = set()
    for pattern in DOC_GLOBS:
        for doc in sorted(root.glob(pattern)):
            try:
                text = doc.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                # bắt cả `tmp/foo/` (thư mục) lẫn `tmp/foo.log` (file)
                for token in line.replace("`", " ").replace("*", " ").split():
                    token = token.strip(".,:;)][\"'")
                    if token.startswith("tmp/"):
                        rest = token[len("tmp/"):]
                        if rest and rest not in (".", ".."):
                            names.add(rest.split("/")[0])
    return names


def inventory(root: Path, keep: tuple[str, ...] = ()) -> list[dict]:
    """Kiểm kê `tmp/`: mỗi mục một dòng, kèm phân loại + lý do (KHÔNG sửa gì)."""
    allow = root / ALLOWED_SUBDIR
    if not allow.is_dir():
        return []
    cited = cited_names(root)
    rows = []
    for entry in sorted(allow.iterdir(), key=lambda p: p.name):
        link = is_link(entry, allow)
        if entry.name in keep:
            action, reason = "GIU", "người chạy gạch tên (--keep)"
        elif entry.name in cited:
            action, reason = "GIU", "được trích dẫn trong tài liệu (docs/README/ROADMAP)"
        elif link:
            action, reason = "CHAN", "là symlink/junction — chặn để không đi ra ngoài repo"
        else:
            action, reason = "XOÁ-ĐỀ-XUẤT", "không được dẫn ở đâu và không thuộc vùng bảo vệ"
        rows.append(
            {
                "name": entry.name,
                "kind": "dir" if entry.is_dir() and not link else "file",
                "bytes": 0 if link else _dir_bytes(entry),
                "is_symlink": link,
                "cited": entry.name in cited,
                "action": action,
                "reason": reason,
            }
        )
    return rows


def _rel_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return ""


def check_target(root: Path, name: str) -> Path:
    """Thẩm định MỘT tên mục. Trả về đường dẫn trong `tmp/`, hoặc ném `CleanupRefusal`.

    Đây là **chốt chặn duy nhất** mà hàm xoá phải đi qua — nên kể cả khi ai đó gọi hàm xoá trực tiếp
    với `../../outputs`, vẫn không có đường nào chạm tới file ngoài `tmp/`.
    """
    if not name or name in (".", ".."):
        raise CleanupRefusal("tên mục rỗng hoặc là thư mục cha — từ chối")
    if "/" in name or "\\" in name:
        raise CleanupRefusal(f"'{name}' chứa phân cấp đường dẫn — chỉ nhận một tên mục trong tmp/")
    if Path(name).is_absolute():
        raise CleanupRefusal(f"'{name}' là đường dẫn tuyệt đối — từ chối")

    allow = root / ALLOWED_SUBDIR
    target = allow / name

    # 1) không đi theo symlink/junction (kể cả khi trỏ vào đúng tmp/)
    if is_link(target, allow):
        raise CleanupRefusal(f"'{name}' là symlink/junction — chặn để không đi ra ngoài repo")

    resolved = target.resolve()
    # 2) realpath vẫn phải nằm trong tmp/
    try:
        resolved.relative_to(allow.resolve())
    except ValueError:
        raise CleanupRefusal(f"'{name}' giải ra ngoài tmp/ ({resolved}) — từ chối")

    # 3) realpath không được khớp vùng bảo vệ (chặn ca `..` lẫn cách viết khác của cùng ô đĩa)
    rel = _rel_to_root(root, resolved)
    for prefix in PROTECTED_PREFIXES:
        if rel == prefix or rel.startswith(prefix + "/"):
            raise CleanupRefusal(f"'{name}' rơi vào vùng bảo vệ '{prefix}/' — từ chối kể cả --yes")

    if not target.exists():
        raise CleanupRefusal(f"'{name}' không tồn tại trong tmp/ — không có gì để xoá")
    return target


def delete_targets(root: Path, names: list[str], *, apply: bool, cited: set[str] | None = None) -> dict:
    """Xoá theo danh sách tên, **chỉ khi `apply=True`**. Mọi mục bị chặn được ghi rõ lý do."""
    cited = cited_names(root) if cited is None else cited
    report = {
        "root": str(root),
        "applied": bool(apply),
        "mode": "XOÁ THẬT" if apply else "DRY-RUN (không xoá gì)",
        "deleted": [],
        "blocked": [],
        "would_delete": [],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    for name in names:
        try:
            target = check_target(root, name)
        except CleanupRefusal as exc:
            report["blocked"].append({"name": name, "reason": str(exc)})
            continue
        if name in cited:
            report["blocked"].append(
                {"name": name, "reason": "được trích dẫn trong tài liệu — cần bỏ dẫn chứng trước khi xoá"}
            )
            continue
        size = _dir_bytes(target)
        if not apply:
            report["would_delete"].append({"name": name, "bytes": size})
            continue
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        except OSError as exc:
            report["blocked"].append({"name": name, "reason": f"lỗi hệ thống: {exc}"})
            continue
        report["deleted"].append({"name": name, "bytes": size})
    return report


def summarize(rows: list[dict]) -> dict:
    out = {"n_items": len(rows), "n_proposed_delete": 0, "n_kept_cited": 0, "bytes_proposed": 0}
    for r in rows:
        if r["action"] == "XOÁ-ĐỀ-XUẤT":
            out["n_proposed_delete"] += 1
            out["bytes_proposed"] += r["bytes"]
        elif r["action"] == "GIU" and r["cited"]:
            out["n_kept_cited"] += 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(REPO_ROOT), help="gốc repo (mặc định: repo hiện tại)")
    ap.add_argument("--yes", action="store_true", help="XOÁ THẬT (mặc định chỉ liệt kê)")
    ap.add_argument("--only", action="append", default=[], metavar="TEN",
                    help="chỉ xét mục có tên này trong tmp/ (lặp lại được)")
    ap.add_argument("--keep", action="append", default=[], metavar="TEN",
                    help="đánh dấu GIỮ thêm mục này (lặp lại được)")
    ap.add_argument("--json", default="", help="ghi báo cáo JSON vào đường dẫn này")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    allow = root / ALLOWED_SUBDIR
    print(f"[T7-cleanup] root={root}")
    print(f"[T7-cleanup] che-do={'XOA THAT (--yes)' if args.yes else 'LIET KE (dry-run, mac dinh)'}")
    if not allow.is_dir():
        print(f"[T7-cleanup] khong co {ALLOWED_SUBDIR}/ — khong lam gi.")
        return 0

    rows = inventory(root, keep=tuple(args.keep))
    total = summarize(rows)
    print(f"[T7-cleanup] tmp/ co {total['n_items']} muc, "
          f"de xuat xoa {total['n_proposed_delete']} ({total['bytes_proposed']/1e6:.1f} MB), "
          f"giu vi duoc dan {total['n_kept_cited']}")
    for r in rows:
        print(f"  {r['action']:14}{r['name'][:42]:44}{r['bytes']/1e6:>8.2f} MB  {r['reason']}")

    names = args.only if args.only else [r["name"] for r in rows if r["action"] == "XOÁ-ĐỀ-XUẤT"]
    report = delete_targets(root, names, apply=args.yes)
    print(f"[T7-cleanup] mode={report['mode']} would_delete={len(report['would_delete'])} "
          f"deleted={len(report['deleted'])} blocked={len(report['blocked'])}")
    for b in report["blocked"]:
        print(f"  CHAN: {b['name']} — {b['reason']}")

    if args.json:
        payload = {"inventory": rows, "summary": total, "deletion": report}
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[T7-cleanup] ghi bao cao: {out}")
    if not args.yes:
        print("[T7-cleanup] DRY-RUN: khong xoa gi. Can --yes va ten da duoc duyet moi xoa that.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
