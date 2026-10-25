#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Con chạy của trọng tài snapshot: chấm lại các dòng đã lưu bằng đúng phiên bản trọng tài
đã chấm round đó (ví dụ v1 `9f1179ccab74` sau khi cây làm việc chuyển sang v2 — PA-2+PA-20).

Vì sao subprocess: `tools/loop/verify.py` import `src.answer_guard` theo tên tuyệt đối, nên
một process không thể nạp hai phiên bản cùng lúc một cách đáng tin cậy. Thụ thể tách biệt
mới là cách duy nhất để "chấm lại bằng bản cũ" không bị bản mới lẫn vào.

CHỈ ĐỌC. Input là một JSON (đường dẫn qua `--input`):

    {
      "expected_fingerprint": "9f1179ccab74",
      "rows": [{"id": ..., "top_k": 6, "item": {...}, "result": {...}}],
      "pub":  {"<id>": {"verdict": ..., "gold_in_top_k": ..., "unsupported": [...]}}
    }

Output (stdout, JSON): `{"fingerprint": ..., "n": ..., "khop": ..., "lech": [...]}`.
Logic so khớp PHẢI đồng nhất với `council_check_referee.rescore_layer`: cùng verdict,
cùng `bool(gold_in_top_k)`, cùng số khẳng định trái ngữ cảnh.

Lỗi chữ ký (snapshot bị sửa) -> exit 2, không chấm. D-35: mọi spawn từ kit đều
`stdin=DEVNULL`; D-36: stdout/stderr ép UTF-8.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _dong in (sys.stdout, sys.stderr):
    try:
        _dong.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", required=True,
                    help="thư mục gốc của cây snapshot (chứa tools/loop/verify.py + src/)")
    ap.add_argument("--input", required=True, help="đường dẫn JSON payload (xem docstring)")
    args = ap.parse_args(argv)

    snap = Path(args.snapshot).resolve()
    ver = snap / "tools" / "loop"
    sys.path.insert(0, str(ver))
    import verify  # noqa: E402  (bản snapshot — KHÔNG bản đang chạy)

    fp = verify.referee_fingerprint()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    expected = payload.get("expected_fingerprint")
    if expected is not None and fp != expected:
        print(json.dumps({"error": "chu_ky_snapshot_lech", "snapshot": str(snap),
                          "dang_chay": fp, "mong_doi": expected}, ensure_ascii=False))
        return 2

    pub = payload.get("pub") or {}
    khop = 0
    lech: list[dict] = []
    for rec in payload.get("rows") or []:
        item = rec["item"]
        v = verify.score_item(item, rec["result"], top_k=rec.get("top_k", 6))
        p = pub.get(item["id"])
        if p is None:
            lech.append({"round": None, "id": item["id"], "loi": "khong_co_row_cong_bo"})
            continue
        if (v["verdict"] == p["verdict"]
                and bool(v["gold_in_top_k"]) == bool(p["gold_in_top_k"])
                and len(v["unsupported"]) == len(p["unsupported"])):
            khop += 1
        else:
            lech.append({"round": None, "id": item["id"],
                         "cong_bo": p["verdict"], "tinhsan": v["verdict"],
                         "gold": (p.get("gold_in_top_k"), v.get("gold_in_top_k")),
                         "n_unsupported": (len(p.get("unsupported") or []),
                                           len(v["unsupported"]))})
    print(json.dumps({"fingerprint": fp, "n": len(payload.get("rows") or []),
                      "khop": khop, "lech": lech}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
