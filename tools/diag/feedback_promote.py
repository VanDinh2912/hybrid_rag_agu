# -*- coding: utf-8 -*-
"""Duyệt phản hồi Tab 3: áp tệp học, dựng index MỚI, chạy cổng, rồi mới hoán đổi.

Vì sao có file này: từ hardening 01-11, GUI Tab 3 (`LEARN_AUTO_APPLY=0`) chỉ ghi
`logs/feedback/user_feedback.json` + một tệp trong `logs/feedback/queue/`; KHÔNG tự sửa
`benchmark_questions.json`, `normalization_pairs.json` hay corpus và KHÔNG rebuild index.
Công cụ này là bước "duyệt tay" — chạy mặc định là **dry-run**, không ghi gì:

    venv/Scripts/python.exe tools/diag/feedback_promote.py                 # xem kế hoạch
    venv/Scripts/python.exe tools/diag/feedback_promote.py --json          # kế hoạch cho máy
    venv/Scripts/python.exe tools/diag/feedback_promote.py --apply --yes   # áp thật

`--apply --yes` làm đúng thứ tự sau, hỏng ở bước nào thì trả phản hồi về như trước:

1. sao lưu 3 tệp đích (benchmark / pairs / ghi chú) vào thư mục làm việc,
2. áp phần đã xin duyệt của từng bản ghi (chỉ các mục `requested` = true),
3. nếu có mục `corpus_note`: dựng index vào thư mục MỚI (bảo vệ bởi
   `ensure_separate_index_target`), chạy cổng trên index mới:
   - fingerprint trọng tài đúng `2911c69f740d`,
   - `corpus_index_manifest` khớp (mọi tệp corpus đã nạp, không nguồn lạ/trùng tên),
4. chỉ khi cổng xanh mới hoán đổi `chroma_db` (index cũ được giữ trong thư mục sao lưu),
5. chuyển các tệp hàng đợi đã áp sang `logs/feedback/queue/applied/<stamp>/`.

KHÔNG tự ghi lại `ARTIFACT_MANIFEST.json`: hoán đổi index làm manifest lệch — người vận
hành chạy `tools/diag/artifact_manifest.py --write` sau khi kiểm tra (hoặc thêm
`--update-manifest` nếu chấp nhận ghi đè ngay). Không mở ChromaDB của index đang chạy
bằng client ở bất kỳ bước nào (PA-60); index mới do `ingest.py` dựng trong tiến trình con.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # chạy trực tiếp từ bất kỳ CWD nào
    sys.path.insert(0, str(ROOT))

from scripts.learn import append_note  # noqa: E402
from src.core.paths import CHROMA_DIR, CORPUS_DIR, EVALUATION_DIR, LEARNING_DIR, LOGS_DIR  # noqa: E402
from src.indexing.contextual_header import ensure_separate_index_target  # noqa: E402
from tools.diag.corpus_index_manifest import build_manifest  # noqa: E402
from tools.loop.verify import referee_fingerprint  # noqa: E402
from ui import feedback_controller as fc  # noqa: E402

#: Cổng trọng tài của đồ án (REPRODUCE.md). Index mới chỉ được hoán đổi khi trọng tài
#: vẫn đúng bản đã nghiệm thu — đổi trọng tài là một quyết định riêng, có round riêng.
EXPECTED_REFEREE_FINGERPRINT = "2911c69f740d"

DEFAULT_QUEUE_DIR = LOGS_DIR / "feedback" / "queue"
DEFAULT_PROMOTIONS_DIR = LOGS_DIR / "feedback" / "promotions"
DEFAULT_BENCHMARK = EVALUATION_DIR / "benchmark_questions.json"
DEFAULT_PAIRS = LEARNING_DIR / "normalization_pairs.json"
DEFAULT_NOTES = CORPUS_DIR / "ghi_chu_hoc_them.txt"

REQUEST_LABELS = {
    "benchmark": "benchmark_questions.json",
    "normalization_pair": "normalization_pairs.json",
    "corpus_note": "ghi_chu_hoc_them.txt + rebuild index",
}


class PromoteError(RuntimeError):
    """Không áp/không dựng/không hoán đổi được — caller phải báo, không coi là thành công."""


def load_queue(queue_dir: Path) -> tuple[list[tuple[Path, dict]], list[tuple[Path, str]]]:
    """Tách hàng đợi thành (bản ghi hợp lệ, tệp hỏng). Tệp hỏng KHÔNG bị bỏ qua."""
    valid: list[tuple[Path, dict]] = []
    broken: list[tuple[Path, str]] = []
    for path, record, error in fc.iter_queue(queue_dir):
        if record is None:
            broken.append((path, error))
        else:
            valid.append((path, record))
    return valid, broken


def plan(records: list[tuple[Path, dict]]) -> dict:
    """Kế hoạch dry-run: mỗi bản ghi xin duyệt mục nào, cần rebuild hay không."""
    items = []
    for path, record in records:
        requested = record["requested"]
        items.append({
            "file": path.name,
            "raw_query": record["raw_query"],
            "requested": {
                key: bool(requested.get(key, False))
                for key in fc.QUEUE_REQUEST_KEYS
            },
        })
    return {
        "records": len(records),
        "items": items,
        "targets": sorted({
            label
            for item in items
            for key, label in REQUEST_LABELS.items()
            if item["requested"][key]
        }),
        "needs_rebuild": any(item["requested"]["corpus_note"] for item in items),
    }


def _backup_text(targets: list[Path], backup_dir: Path) -> dict[str, str | None]:
    """Sao lưu tệp đích; tệp chưa có ⇒ ghi `None` để rollback biết phải xoá bản mới tạo."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str | None] = {}
    for target in targets:
        if target.exists():
            copy = backup_dir / target.name
            shutil.copy2(target, copy)
            saved[str(target)] = str(copy)
        else:
            saved[str(target)] = None
    return saved


def _restore_text(saved: dict[str, str | None]) -> None:
    """Trả 3 tệp đích về đúng trạng thái trước khi áp (kể cả xoá tệp vừa tạo)."""
    for original, copy in saved.items():
        path = Path(original)
        if copy is None:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copy, path)


def apply_records(
    records: list[tuple[Path, dict]],
    *,
    benchmark_path: Path,
    pairs_path: Path,
    notes_path: Path,
) -> list[str]:
    """Áp đúng các mục `requested`; trả danh sách lỗi (rỗng = xong hết)."""
    errors: list[str] = []
    for path, record in records:
        requested = record["requested"]
        if requested["benchmark"]:
            ok, error = fc.save_benchmark(
                benchmark_path,
                record,
                record["ground_truth"],
                record.get("citation", ""),
                record.get("source_doc", ""),
                record.get("normalized_truth", ""),
            )
            if not ok:
                errors.append(f"{path.name}: benchmark — {error}")
        if requested["normalization_pair"]:
            ok, error = fc.save_normalization_pair(
                pairs_path, record["raw_query"], record["normalized_truth"]
            )
            if not ok:
                errors.append(f"{path.name}: normalization_pairs — {error}")
        if requested["corpus_note"]:
            try:
                append_note(
                    record["raw_query"],
                    record.get("correct_answer") or "",
                    notes_path=str(notes_path),
                )
            except OSError as exc:
                errors.append(f"{path.name}: ghi chú học — {exc}")
    return errors


def rebuild_index(new_index: Path, log_path: Path) -> int:
    """`ingest.py` chạy trong tiến trình con, ghi vào `CHROMA_PERSIST_DIR` = thư mục MỚI."""
    env = os.environ.copy()
    env["CHROMA_PERSIST_DIR"] = str(new_index)
    env.pop("INGEST_ALLOW_RESET", None)  # thư mục mới: không cần và không được xoá gì
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "ingest.py"), "--yes"],
            cwd=str(ROOT),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return proc.returncode


def gate_new_index(new_index: Path, corpus_dir: Path) -> tuple[list[str], dict]:
    """Cổng trước hoán đổi: fingerprint trọng tài + corpus↔index. Trả (lỗi, báo cáo)."""
    problems: list[str] = []
    fingerprint = referee_fingerprint()
    if fingerprint != EXPECTED_REFEREE_FINGERPRINT:
        problems.append(
            f"fingerprint trọng tài {fingerprint} ≠ {EXPECTED_REFEREE_FINGERPRINT}"
        )
    manifest = build_manifest(corpus_dir, new_index)
    if not manifest["ok"]:
        problems.extend(manifest["reasons"])
    return problems, {"fingerprint": fingerprint, "manifest": manifest}


def swap_index(new_index: Path, target_index: Path, backup_dir: Path) -> Path:
    """Đổi chỗ index cũ ↔ index mới; hỏng giữa chừng thì trả index cũ về. Trả đường dẫn bản cũ."""
    if not (new_index / "chroma.sqlite3").is_file():
        raise PromoteError(f"index mới {new_index} không có chroma.sqlite3 — từ chối hoán đổi")
    backup = Path(backup_dir) / "chroma_db_before"
    if target_index.exists() and backup.exists():
        raise PromoteError(f"bản sao lưu {backup} đã tồn tại — chọn thư mục làm việc mới")
    moved_old = False
    try:
        if target_index.exists():
            shutil.move(str(target_index), str(backup))
            moved_old = True
        shutil.move(str(new_index), str(target_index))
    except OSError as exc:
        if moved_old and backup.exists() and not target_index.exists():
            shutil.move(str(backup), str(target_index))
        raise PromoteError(f"hoán đổi index hỏng, đã trả bản cũ về: {exc}") from exc
    return backup


def mark_applied(queue_dir: Path, paths: list[Path], stamp: str) -> Path:
    """Chuyển tệp hàng đợi đã áp sang `applied/<stamp>/` — giữ nguyên nội dung, không xoá."""
    applied = queue_dir / "applied" / stamp
    applied.mkdir(parents=True, exist_ok=True)
    for path in paths:
        shutil.move(str(path), str(applied / path.name))
    return applied


def print_plan(dry: dict, queue_dir: Path) -> None:
    print(f"Hàng đợi: {queue_dir} — {dry['records']} bản ghi chờ duyệt")
    for item in dry["items"]:
        pending = [label for key, label in REQUEST_LABELS.items() if item["requested"][key]]
        print(f"  - {item['file']}")
        print(f"      câu hỏi : {item['raw_query']}")
        print(f"      xin áp  : {', '.join(pending) if pending else 'không có mục nào'}")
    print()
    print("Tệp đích sẽ ghi: " + (", ".join(dry["targets"]) if dry["targets"] else "(không có)"))
    print("Rebuild index   : " + ("CÓ — dựng index mới rồi chạy cổng trước khi hoán đổi"
                                  if dry["needs_rebuild"] else "KHÔNG"))
    print("\n[DRY-RUN] Không ghi tệp nào, không dựng index, không gọi model.")
    print("Áp thật: thêm --apply --yes")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tools/diag/feedback_promote.py",
        description="Duyệt phản hồi Tab 3: áp tệp học + dựng/chạy cổng index mới + hoán đổi (mặc định dry-run).",
        epilog="--apply cần thêm --yes. Không bao giờ tự ghi ARTIFACT_MANIFEST.json trừ khi có --update-manifest.",
    )
    parser.add_argument("--apply", action="store_true", help="áp thật (mặc định chỉ in kế hoạch)")
    parser.add_argument("--yes", action="store_true", help="xác nhận hoán đổi index — bắt buộc với --apply")
    parser.add_argument("--queue-dir", default=str(DEFAULT_QUEUE_DIR), help="thư mục hàng đợi")
    parser.add_argument("--corpus", default=str(CORPUS_DIR), help="thư mục corpus để đối chiếu index mới")
    parser.add_argument("--target-index", default=str(CHROMA_DIR), help="index sẽ bị thay khi hoán đổi")
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK), help="tệp benchmark đích")
    parser.add_argument("--pairs", default=str(DEFAULT_PAIRS), help="tệp cặp chuẩn hóa đích")
    parser.add_argument("--notes", default=str(DEFAULT_NOTES), help="tệp ghi chú học thêm đích")
    parser.add_argument("--work-dir", default="",
                        help="thư mục làm việc (mặc định tmp/feedback_promote/<stamp>)")
    parser.add_argument("--update-manifest", action="store_true",
                        help="sau hoán đổi, ghi lại ARTIFACT_MANIFEST.json (mặc định chỉ nhắc lệnh)")
    parser.add_argument("--json", action="store_true", help="in kế hoạch/kết quả dạng JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    queue_dir = Path(args.queue_dir)
    records, broken = load_queue(queue_dir)
    dry = plan(records)

    if broken:
        print("[feedback_promote] HÀNG ĐỢI CÓ TỆP HỎNG — dừng, không áp gì:")
        for path, error in broken:
            print(f"  - {path.name}: {error}")
        return 1

    if not records:
        print(f"[feedback_promote] Hàng đợi {queue_dir} trống — không có gì để duyệt.")
        return 0

    if args.json and not args.apply:
        print(json.dumps(dry, ensure_ascii=False, indent=2))
    elif not args.json:
        print_plan(dry, queue_dir)

    if not args.apply:
        return 0
    if not args.yes:
        print("[feedback_promote] --apply cần --yes để xác nhận; chưa làm gì.")
        return 2

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    work_dir = Path(args.work_dir) if args.work_dir else ROOT / "tmp" / "feedback_promote" / stamp
    new_index = work_dir / "chroma_db"
    try:
        new_index = ensure_separate_index_target(new_index, repo_root=ROOT)
    except ValueError as exc:
        print(f"[feedback_promote] {exc}")
        return 1
    if new_index.exists():
        print(f"[feedback_promote] {new_index} đã tồn tại — chọn --work-dir mới.")
        return 1

    benchmark = Path(args.benchmark)
    pairs = Path(args.pairs)
    notes = Path(args.notes)
    saved = _backup_text([benchmark, pairs, notes], work_dir / "backup_text")
    print(f"[feedback_promote] Đã sao lưu 3 tệp đích vào {work_dir / 'backup_text'}")

    errors = apply_records(records, benchmark_path=benchmark, pairs_path=pairs, notes_path=notes)
    if errors:
        _restore_text(saved)
        print("[feedback_promote] Áp thất bại — đã trả 3 tệp về như trước:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"[feedback_promote] Đã áp {len(records)} bản ghi.")

    if dry["needs_rebuild"]:
        print(f"[feedback_promote] Dựng index mới tại {new_index} (ingest.py, tiến trình con)...")
        code = rebuild_index(new_index, work_dir / "ingest.log")
        if code != 0:
            _restore_text(saved)
            print(f"[feedback_promote] ingest.py trả mã {code} — đã trả tệp học về, KHÔNG hoán đổi.")
            print(f"  log: {work_dir / 'ingest.log'}")
            return 1
        problems, report = gate_new_index(new_index, Path(args.corpus))
        if problems:
            _restore_text(saved)
            print("[feedback_promote] CỔNG ĐỎ trên index mới — đã trả tệp học về, KHÔNG hoán đổi:")
            for problem in problems:
                print(f"  - {problem}")
            print(f"  index mới giữ lại để kiểm tra: {new_index}")
            return 1
        print(f"[feedback_promote] Cổng xanh: fingerprint {report['fingerprint']}, "
              f"{report['manifest']['chunk_total']} chunk, "
              f"{len(report['manifest']['files'])} tệp corpus.")
        backup = swap_index(new_index, Path(args.target_index), work_dir)
        print(f"[feedback_promote] Đã hoán đổi index; bản cũ: {backup}")

        if args.update_manifest:
            code = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "diag" / "artifact_manifest.py"), "--write"],
                cwd=str(ROOT), check=False,
            ).returncode
            print(f"[feedback_promote] artifact_manifest --write trả mã {code}.")
        else:
            print("  Bước tiếp: tools/diag/artifact_manifest.py --write (manifest đang lệch vì index đổi).")

    applied = mark_applied(queue_dir, [path for path, _record in records], stamp)
    print(f"[feedback_promote] Đã chuyển {len(records)} tệp hàng đợi sang {applied}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
