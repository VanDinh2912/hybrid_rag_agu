# -*- coding: utf-8 -*-
"""Preflight tái lập — **CHỈ-ĐỌC**, không mở Chroma client, không gọi mạng/model.

Vì sao có tệp này: ngày 31-10 phát hiện **hai hư hỏng âm thầm** đều nằm ở artifact *không được git
theo dõi* nên không cổng nào bắt được:

1. `chroma_db/` bị ingest lại thành **443 chunk** (thay vì 361) — mọi số neo đo trên 361 thành
   không tái lập;
2. `data/training/` (gitignore, ngoài `ARTIFACT_MANIFEST.json`) bị **tái sinh** — 1.635 → 2.089 dòng.

Công cụ này so cây hiện tại với `docs/repro_pins_20261031.json` (các con số + sha256 đã chốt) và báo
`ĐẠT / CẢNH BÁO / HỎNG`. Nó **không sửa gì**, không `import chromadb` (Chroma tự tái ghi byte khi mở —
xem PA-60), chỉ đọc sqlite bằng `mode=ro&immutable=1`.

Dùng:

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/repro_preflight.py
    ... --json tmp/preflight.json          # máy đọc
    ... --skip-env                          # bỏ phép kiểm lever `.env`

Mã thoát: 0 = không có HỎNG (cảnh báo vẫn rc 0, là kết quả chứ không phải lỗi); 1 = có HỎNG;
2 = không đọc được pin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PINS = "docs/repro_pins_20261031.json"
OK, WARN, FAIL = "ĐẠT", "CẢNH BÁO", "HỎNG"
SKIP = object()          # `--skip-env`: khác hẳn "đã kiểm và regime sạch"


# ------------------------------------------------------------------ phép đọc thuần (test được)
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_chroma_facts(sqlite_path: Path) -> dict:
    """Đọc số chunk/nguồn/tầng bằng sqlite thuần — KHÔNG dùng chromadb."""
    con = sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        chunks = con.execute("SELECT count(*) FROM embeddings").fetchone()[0]
        sources = con.execute(
            "SELECT count(DISTINCT string_value) FROM embedding_metadata WHERE key='source'"
        ).fetchone()[0]
        tiers = dict(
            con.execute(
                "SELECT string_value, count(*) FROM embedding_metadata WHERE key='tier' GROUP BY 1"
            ).fetchall()
        )
    finally:
        con.close()
    return {"chunks": chunks, "sources": sources, "tiers": tiers}


def count_corpus(corpus_dir: Path) -> dict:
    ext: dict[str, int] = {}
    for p in corpus_dir.rglob("*"):
        if p.is_file():
            ext[p.suffix.lower()] = ext.get(p.suffix.lower(), 0) + 1
    return {"files": sum(ext.values()), "ext": ext}


def count_training(training_dir: Path) -> dict:
    """Khoá theo **đường dẫn tương đối** — tên tệp trần bị trùng giữa các thư mục con (`t4b_*`)."""
    files = sorted(p for p in training_dir.rglob("*") if p.is_file())
    rows = {
        p.relative_to(training_dir).as_posix(): sum(1 for _ in p.open("rb"))
        for p in files
        if p.suffix.lower() == ".jsonl"
    }
    return {
        "files": len(files),
        "rows": rows,
        "total_rows": sum(rows.values()),
        "sha256": {p.relative_to(training_dir).as_posix(): sha256_file(p) for p in files},
    }


def env_regime_deviation() -> str | None:
    """Token thể chế cache khi `.env` của máy bật lever; None = regime chuẩn."""
    from dotenv import load_dotenv  # noqa: PLC0415 — chỉ nạp trong phép kiểm này

    load_dotenv()
    if str(ROOT) not in sys.path:      # chạy trực tiếp bằng `python tools/diag/...`
        sys.path.insert(0, str(ROOT))
    from src.core.cache_policy import cache_policy_deviation

    return cache_policy_deviation()


# ------------------------------------------------------------------ so khớp
def evaluate(pins: dict, chroma: dict, corpus: dict, training: dict,
             chroma_sha: dict, env_dev: str | None) -> list[tuple[str, str]]:
    """Trả về [(mức, thông điệp)] — thuần, không đọc đĩa."""
    out: list[tuple[str, str]] = []
    pc = pins.get("chroma_db", {})

    if chroma["chunks"] != pc.get("chunks"):
        out.append((FAIL, f"`chroma_db` có {chroma['chunks']} chunk, pin {pc.get('chunks')} "
                          "— index sản xuất đã bị dựng lại (hệ quả: mọi số neo 361 mất hiệu lực)"))
    else:
        out.append((OK, f"`chroma_db` = {chroma['chunks']} chunk"))
    if chroma["sources"] != pc.get("sources"):
        out.append((FAIL, f"`chroma_db` có {chroma['sources']} nguồn, pin {pc.get('sources')}"))
    else:
        out.append((OK, f"`chroma_db` = {chroma['sources']} tệp nguồn"))
    if pc.get("tiers") and chroma["tiers"] != pc["tiers"]:
        out.append((FAIL, f"phân bố tầng đổi: {chroma['tiers']} ≠ pin {pc['tiers']}"))
    else:
        out.append((OK, f"phân bố tầng khớp {chroma['tiers']}"))

    changed = [name for name, sha in (pc.get("sha256") or {}).items() if chroma_sha.get(name) != sha]
    if changed:
        out.append((WARN, "byte index đổi so với pin (Chroma tái ghi khi mở — PA-60): "
                          + ", ".join(sorted(changed))))
    else:
        out.append((OK, "byte index khớp pin"))

    pcorp = pins.get("corpus", {})
    if corpus["files"] > int(pcorp.get("files", 0)):
        out.append((WARN, f"`data/corpus/` có {corpus['files']} tệp nhưng pin {pcorp.get('files')} "
                          f"và index {chroma['sources']} nguồn — chạy `ingest.py` bây giờ sẽ sinh "
                          f"nhiều chunk hơn index sản xuất (xem `docs/REPRODUCE.md` §1)"))
    elif corpus["files"] < int(pcorp.get("files", 0)):
        out.append((WARN, f"`data/corpus/` chỉ còn {corpus['files']} tệp, pin {pcorp.get('files')}"))
    else:
        out.append((OK, f"`data/corpus/` = {corpus['files']} tệp"))

    ptr = pins.get("data_training", {})
    if training["files"] != ptr.get("files"):
        out.append((FAIL, f"`data/training/` có {training['files']} tệp, pin {ptr.get('files')}"))
    else:
        out.append((OK, f"`data/training/` = {training['files']} tệp"))
    if training["total_rows"] != ptr.get("total_rows"):
        out.append((FAIL, f"`data/training/` {training['total_rows']} dòng, pin {ptr.get('total_rows')} "
                          "— bộ train đã bị tái sinh"))
    else:
        out.append((OK, f"`data/training/` = {training['total_rows']} dòng"))
    bad = [k for k, v in (ptr.get("rows") or {}).items() if training["rows"].get(k) != v]
    if bad:
        out.append((FAIL, "số dòng lệch ở: " + ", ".join(sorted(bad))))
    bad_sha = [k for k, v in (ptr.get("sha256") or {}).items() if training["sha256"].get(k) != v]
    if bad_sha:
        out.append((FAIL, "byte lệch ở: " + ", ".join(sorted(bad_sha))
                          + " — nếu cố ý rebuild, phải cập nhật pin bằng một quyết định có ghi lý do"))

    if env_dev is SKIP:
        out.append((OK, "regime chuẩn hoá: BỎ QUA theo `--skip-env` (chưa kiểm)"))
    elif env_dev is None:
        out.append((OK, "regime chuẩn hoá = mặc định (cache_policy_deviation = None)"))
    else:
        out.append((WARN, f"`.env` máy đang bật lever: `cache_policy_deviation()` = {env_dev} "
                          "— mọi phép đo trong tiến trình này mang regime lạ"))
    return out


# ------------------------------------------------------------------ CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Preflight tái lập (chỉ đọc).")
    ap.add_argument("--pins", default=str(ROOT / DEFAULT_PINS))
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--skip-env", action="store_true")
    ap.add_argument("--json", default=None, help="ghi báo cáo JSON ra tên mới")
    args = ap.parse_args(argv)

    root = Path(args.root)
    pins_path = Path(args.pins)
    if not pins_path.exists():
        print(f"[preflight] không thấy pin: {pins_path}", file=sys.stderr)
        return 2
    pins = json.loads(pins_path.read_text(encoding="utf-8"))

    sqlite_path = root / "chroma_db" / "chroma.sqlite3"
    if not sqlite_path.exists():
        print(f"[preflight] không thấy index sản xuất: {sqlite_path}", file=sys.stderr)
        return 2
    chroma = read_chroma_facts(sqlite_path)
    chroma_sha = {
        str(p.relative_to(root)).replace("\\", "/"): sha256_file(p)
        for p in sorted((root / "chroma_db").rglob("*"))
        if p.is_file()
    }
    corpus = count_corpus(root / "data" / "corpus")
    training = count_training(root / "data" / "training")
    env_dev = SKIP if args.skip_env else env_regime_deviation()

    rows = evaluate(pins, chroma, corpus, training, chroma_sha, env_dev)
    width = max(len(m) for _, m in rows)
    for level, msg in rows:
        print(f"[preflight] {level:<9} {msg}")
    n_fail = sum(1 for level, _ in rows if level == FAIL)
    print(f"[preflight] KẾT LUẬN: {'HỎNG' if n_fail else 'ĐẠT'} "
          f"({n_fail} hỏng / {sum(1 for l, _ in rows if l == WARN)} cảnh báo; pin {pins_path.name})")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"pins": str(pins_path), "rows": rows, "fails": n_fail},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
