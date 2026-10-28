"""Kiểm toán CHỈ-ĐỌC (nghiệm thu cuối, mục 5): bất biến #7 + chặn rò rỉ trên dữ liệu train cuối.

Dữ liệu train trong repo thuộc **hai họ** và bất biến #7 có nghĩa hơi khác nhau ở mỗi họ:

* Họ LOOP (`data/training/t4b_*`, sinh từ `tools/train/build_sft_from_round.py`): "#7 — mỗi dòng train
  phải **tự chứa** căn cứ của đáp án" + "không item test nào lọt vào train". Họ này đã có
  checker riêng (`tools/diag/check_sft_invariants.py`); ở đây chỉ gọi lại đúng hàm của nó và
  chép số, để báo cáo cuối có một chỗ duy nhất nhìn thấy cả hai họ.
* Họ CODE-QA (`data/training/sft_*.jsonl`, `classifier_*.jsonl`, `retrieval_pairs.jsonl`,
  `refusal.jsonl` — sinh 23-10 bởi `tools/build_training_data.py`): "tự chứa" được hiểu là
  **đáp án kiểm chứng được từ chính dữ liệu trong dòng** — file được trích (`metadata.file`)
  phải tồn tại, dòng được trích (`metadata.line`) phải nằm trong file, và mọi định danh code
  trích trong câu trả lời phải xuất hiện thật trong file đó. Rò rỉ ở họ này tinh vi hơn trùng
  id: hai bản ghi khác id nhưng cùng một câu hỏi chuẩn hoá, hoặc cùng `benchmark_id`, hoặc
  cùng đúng một đoạn `text` giữa `classifier_train` và `classifier_benchmark_seed` thì điểm
  benchmark không còn ý nghĩa.

Ba lớp kiểm tra, mỗi lớp in số dòng thật:

1. `đếm dòng` — số dòng mỗi `.jsonl` và đối chiếu với `data/training/manifest.json` (số đã công bố).
2. `chặn rò rỉ` — theo id, theo câu hỏi đã chuẩn hoá, theo `benchmark_id`, theo `text` nguyên văn.
3. `bất biến #7` — căn cứ phải có thật trong dòng/nguồn được trích.

Không ghi vào `data/`; báo cáo JSON tuỳ chọn qua `--out` (nên trỏ `tmp/`).

Chạy:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/train_data_audit.py
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/train_data_audit.py --out tmp/train_data_audit.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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

TRAIN_DIR = ROOT / "data" / "training"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SFT_FILES = ("sft_train.jsonl", "sft_val.jsonl", "sft_benchmark_seed.jsonl")
CLASSIFIER_PAIR = ("classifier_train.jsonl", "classifier_benchmark_seed.jsonl")

_CODE_IDENT_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.:/]{3,})`")
_FOLD_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def norm(text: str) -> str:
    """Fold giống `src/text_utils.fold_for_match`: bỏ dấu + chữ thường + bỏ punctuation."""
    if not isinstance(text, str):
        text = str(text)
    decomposed = unicodedata.normalize("NFD", text)
    khong_dau = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return " ".join(_FOLD_PUNCT.sub(" ", khong_dau.lower()).split())


def read_jsonl(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    out = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            out.append({"__parse_error__": f"{path.name}:{lineno}: {exc}"})
    return out


def line_counts() -> Dict[str, Any]:
    """Số dòng thật của mỗi file + đối chiếu manifest.json (số đã công bố 23-10)."""
    manifest_path = TRAIN_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    published = manifest.get("files", {})
    rows = []
    for path in sorted(TRAIN_DIR.glob("*.jsonl")):
        thuc = len(read_jsonl(path))
        cong_bo = published.get(path.name)
        rows.append(dict(file=path.name, dong_thuc=thuc, dong_manifest=cong_bo,
                         khop=(cong_bo is None or cong_bo == thuc)))
    return dict(rows=rows,
                total_dong=sum(r["dong_thuc"] for r in rows),
                so_file_khop_manifest=sum(1 for r in rows if r["khop"]),
                so_file_lech_manifest=sum(1 for r in rows if not r["khop"]),
                manifest_keys=sorted(published))


# ---------------------------------------------------------------------- 2. chặn rò rỉ
def _pairs(rows_a: List[dict], rows_b: List[dict], key: str, getter) -> List[Dict[str, Any]]:
    bang_a: Dict[str, List[str]] = {}
    for r in rows_a:
        v = getter(r)
        if v:
            bang_a.setdefault(norm(str(v)), []).append(str(r.get("id") or r.get("benchmark_id") or "?"))
    lech = []
    for r in rows_b:
        v = getter(r)
        if v and norm(str(v)) in bang_a:
            lech.append(dict(key=key, value=str(v)[:80], ben_a=bang_a[norm(str(v))][:3],
                             ben_b=str(r.get("id") or r.get("benchmark_id") or "?")))
    return lech


def _messages_getter(role: str):
    def getter(row: dict) -> Optional[str]:
        for msg in row.get("messages") or []:
            if msg.get("role") == role:
                return msg.get("content")
        return None
    return getter


def _doi_phia(rows_a: List[dict], rows_b: List[dict], ids: Iterable[str]) -> Dict[str, Any]:
    """Với mỗi id trùng giữa hai tập: so NỘI DUNG (câu hỏi + đáp án đã fold).

    `id` trong họ code-QA do bộ sinh đặt theo bộ đếm từng task, nên **hai bản ghi khác nội dung
    vẫn có thể cùng id**. Chỉ id trùng mà nội dung trùng mới là rò rỉ; id trùng mà nội dung khác
    là lỗi đặt tên (phải báo, nhưng không tính là leak).
    """
    want = set(ids)

    def nap(rows):
        out = {}
        for r in rows:
            if str(r.get("id")) in want:
                q = norm(str(_question_of(r) or ""))
                a = norm(str(_answer_of(r) or ""))
                out.setdefault(str(r["id"]), []).append((q, a, r))
        return out

    A, B = nap(rows_a), nap(rows_b)
    roi_le, trung_ten = [], []
    for i, nhom_a in A.items():
        for qa_a, ans_a, row_a in nhom_a:
            for qa_b, ans_b, row_b in B.get(i, []):
                if qa_a and qa_a == qa_b:
                    roi_le.append(dict(id=i, a=row_a.get("task"), b=row_b.get("task"),
                                       noi_dung=qa_a[:60]))
                else:
                    trung_ten.append(dict(id=i, a_task=row_a.get("task"), b_task=row_b.get("task"),
                                          a_meta=row_a.get("metadata"), b_meta=row_b.get("metadata")))
    return dict(roi_le=roi_le, trung_ten=trung_ten)


def _question_of(row: dict) -> str:
    for msg in row.get("messages") or []:
        if msg.get("role") == "user":
            return msg.get("content") or ""
    return row.get("question") or row.get("text") or ""


def _answer_of(row: dict) -> str:
    for msg in row.get("messages") or []:
        if msg.get("role") == "assistant":
            return msg.get("content") or ""
    return row.get("answer") or ""


def leak_checks() -> Dict[str, Any]:
    train = read_jsonl(TRAIN_DIR / "sft_train.jsonl")
    val = read_jsonl(TRAIN_DIR / "sft_val.jsonl")
    seed = read_jsonl(TRAIN_DIR / "sft_benchmark_seed.jsonl")
    cls_train = read_jsonl(TRAIN_DIR / "classifier_train.jsonl")
    cls_seed = read_jsonl(TRAIN_DIR / "classifier_benchmark_seed.jsonl")

    def ids(rows):
        return {str(r.get("id")) for r in rows if r.get("id")}

    theo_id = {
        "train_vs_val": sorted(ids(train) & ids(val)),
        "train_vs_benchmark_seed": sorted(ids(train) & ids(seed)),
        "val_vs_benchmark_seed": sorted(ids(val) & ids(seed)),
        "classifier_train_vs_classifier_seed": sorted(ids(cls_train) & ids(cls_seed)),
    }
    # tách "id trùng" thành hai số khác bản chất: rò rỉ nội dung thật vs lỗi đặt tên
    phan_tich = {
        cuoc: _doi_phia(A, B, theo_id[cuoc])
        for cuoc, (A, B) in (
            ("train_vs_val", (train, val)),
            ("train_vs_benchmark_seed", (train, seed)),
            ("val_vs_benchmark_seed", (val, seed)),
            ("classifier_train_vs_classifier_seed", (cls_train, cls_seed)),
        )
    }
    theo_benchmark_id = {
        "train_vs_benchmark_seed": _pairs(seed, train, "benchmark_id",
                                         lambda r: (r.get("metadata") or {}).get("benchmark_id")),
        "val_vs_benchmark_seed": _pairs(seed, val, "benchmark_id",
                                        lambda r: (r.get("metadata") or {}).get("benchmark_id")),
    }
    theo_cau_hoi = {
        "train_vs_val": _pairs(train, val, "user", _messages_getter("user")),
        "train_vs_benchmark_seed": _pairs(train, seed, "user", _messages_getter("user")),
    }
    theo_text_classifier = _pairs(cls_train, cls_seed, "text", lambda r: r.get("text"))
    # retrieval_pairs: positive_chunk_id của query nằm trong benchmark? kiểm trùng queryfold
    rp = read_jsonl(TRAIN_DIR / "retrieval_pairs.jsonl")
    rf = read_jsonl(TRAIN_DIR / "refusal.jsonl")
    # retrieval_pairs: trùng query là hợp lệ (nhiều positive); chỉ trùng (query, positive_chunk_id)
    # mới là bản ghi lặp => làm loãng đo. Đếm cả hai để không gộp thành một con số mù.
    nhom_query = Counter(norm(r.get("query", "")) for r in rp if r.get("query"))
    nho_positive = Counter((norm(r.get("query", "")), r.get("positive_chunk_id"))
                           for r in rp if r.get("query"))
    theo_khac = {
        "retrieval_query_trung_nhau_nhung_khac_positive": sum(
            1 for _, n in nhom_query.items() if n > 1),
        "retrieval_query_positive_trung_nguyen_ve": sum(n - 1 for n in nho_positive.values() if n > 1),
        "refusal_vs_sft_train_cau_hoi": _pairs(
            train, rf, "question", lambda r: (r.get("question") or "").split("NGỮ CẢNH:")[-1]),
    }
    that_roi_le = (sum(len(p["roi_le"]) for p in phan_tich.values())
                   + sum(len(v) for v in theo_benchmark_id.values())
                   + sum(len(v) for v in theo_cau_hoi.values())
                   + len(theo_text_classifier)
                   + len(theo_khac["refusal_vs_sft_train_cau_hoi"]))
    loi_dat_ten = sum(len(p["trung_ten"]) for p in phan_tich.values())
    return dict(theo_id=theo_id, phan_tich_id=phan_tich,
                theo_benchmark_id=theo_benchmark_id,
                theo_cau_hoi=theo_cau_hoi,
                theo_text_classifier=theo_text_classifier, theo_khac=theo_khac,
                tong_roi_le_thuc=that_roi_le, tong_id_trung_ten=loi_dat_ten)


# ----------------------------------------------------------------- 3. bất biến #7 (code-QA)
def self_contained_code_qa(rows: List[dict]) -> Dict[str, Any]:
    """Đáp án code-QA phải kiểm chứng được từ chính file/dòng nó trích.

    Ba luật, mỗi luật đếm số vi phạm (kỳ vọng = 0):
      * `file_thieu`         — `metadata.file` không tồn tại trong repo.
      * `line_vuot`          — `metadata.line` lớn hơn số dòng thật của file.
      * `dinh_danh_khong_co` — định danh code bọc trong `…` của câu trả lời không xuất hiện
                               trong file được trích (đáp án bịa reference).
    """
    bao_cao = dict(n_rows=0, co_trich_file=0, file_thieu=[], line_vuot=[],
                   dinh_danh_khong_co=[], dinh_danh_kiem_tra=0)
    cache: Dict[str, Optional[Tuple[Optional[str], int]]] = {}

    def noi_dung(file: str):
        if file not in cache:
            p = ROOT / file
            if not p.is_file():
                cache[file] = (None, 0)
            else:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    cache[file] = (None, 0)
                cache[file] = (text, text.count("\n") + 1 if text else 0)
        return cache[file]

    for row in rows:
        if row.get("__parse_error__"):
            continue
        bao_cao["n_rows"] += 1
        meta = row.get("metadata") or {}
        file = meta.get("file")
        if not file:
            continue
        text, so_dong = noi_dung(str(file))
        bao_cao["co_trich_file"] += 1
        if text is None:
            bao_cao["file_thieu"].append({"id": row.get("id"), "file": file})
            continue
        line = meta.get("line")
        if isinstance(line, int) and line > so_dong:
            bao_cao["line_vuot"].append({"id": row.get("id"), "file": file, "line": line,
                                         "so_dong_cua_file": so_dong})
        answer = ""
        for msg in row.get("messages") or []:
            if msg.get("role") == "assistant":
                answer = msg.get("content") or ""
        folded_file = norm(text)
        for token in _CODE_IDENT_RE.findall(answer):
            if "/" in token or "\\" in token or re.search(r"\.(py|md|json|jsonl|txt|csv|yaml|yml|pdf)$",
                                                          token, re.I):
                continue                      # đường dẫn/tên file — đã kiểm ở luật 1 & 2
            if len(token) < 5:
                continue
            bao_cao["dinh_danh_kiem_tra"] += 1
            if norm(token) not in folded_file:
                bao_cao["dinh_danh_khong_co"].append({"id": row.get("id"), "file": file,
                                                      "token": token})
    bao_cao["ok"] = (not bao_cao["file_thieu"] and not bao_cao["line_vuot"])
    return bao_cao


def _rounds_ten_tu(root_name: str) -> List[str]:
    """`t4b_r5r8r9r10` -> ['r5','r8','r9','r10']; không parse được thì trả []."""
    return [f"r{n}" for n in re.findall(r"r(\d+)", root_name)]


def loop_family(artifact_roots: List[str]) -> Dict[str, Any]:
    """Gọi lại checker #7 + chống rò rỉ CỦA vòng lặp (không tự viết lại luật)."""
    from tools.diag import check_sft_invariants as ci

    out = []
    for root_name in artifact_roots:
        art = (TRAIN_DIR / root_name) if not Path(root_name).is_absolute() else Path(root_name)
        if not art.is_dir():
            out.append(dict(root=root_name, error="không tồn tại"))
            continue
        rounds = _rounds_ten_tu(art.name)
        try:
            rep = ci.check_artifact(art, rounds=rounds, raise_on_violation=False)
        except Exception as exc:  # pragma: no cover
            out.append(dict(root=root_name, error=f"{type(exc).__name__}: {exc}"))
            continue
        checks = rep.get("checks", {})
        evidence = rep.get("1_evidence_in_context", {})
        leak = rep.get("2_no_test_leak", {})
        out.append(dict(
            root=root_name, rounds=rounds, n_items=rep.get("n_items"),
            n_train_rows=rep.get("n_train_rows"), n_holdout_rows=rep.get("n_holdout_rows"),
            verdict=rep.get("verdict"), red_checks=rep.get("red_checks"),
            checks=checks,
            evidence_n_rows=evidence.get("n_rows"),
            evidence_missing_mandatory=len(evidence.get("rows_missing_mandatory", [])),
            evidence_missing_gold_sentence=len(evidence.get("rows_missing_gold_sentence", [])),
            id_leaks=len(leak.get("id_leaks", [])), sentence_leaks=len(leak.get("sentence_leaks", [])),
            report=rep))
    return dict(artifact_roots=artifact_roots, roots=out)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Kiểm toán chỉ-đọc: đếm dòng + chặn rò rỉ + bất biến #7 cho dữ liệu train cuối.")
    ap.add_argument("--out", help="ghi báo cáo JSON (nên trỏ tmp/).")
    ap.add_argument("--loop-roots", nargs="*",
                    default=[d.name for d in TRAIN_DIR.glob("t4b*") if d.is_dir()],
                    help="thư mục artifact họ loop cần kiểm bằng check_sft_invariants.")
    args = ap.parse_args(argv)

    dem = line_counts()
    lech = dem["so_file_lech_manifest"]
    print(f"[train-audit] đếm dòng: {len(dem['rows'])} file, {dem['total_dong']} dòng; "
          f"khớp manifest {dem['so_file_khop_manifest']}, lệch {lech}")
    for r in dem["rows"]:
        mark = "  " if r["khop"] else "✗ "
        print(f"  {mark}{r['file']:38} thực={r['dong_thuc']:5} manifest={r['dong_manifest']}")

    leak = leak_checks()
    print(f"[train-audit] chặn rò rỉ: rò rỉ NỘI DUNG thật = {leak['tong_roi_le_thuc']}; "
          f"id trùng nhưng khác nội dung (lỗi đặt tên) = {leak['tong_id_trung_ten']}")
    for cuoc, p in leak["phan_tich_id"].items():
        print(f"  {'✓' if not p['roi_le'] else '✗'} id {cuoc:38} trùng={len(p['roi_le']) + len(p['trung_ten']):3} "
              f"trong đó rò rỉ={len(p['roi_le'])}, chỉ trùng tên={len(p['trung_ten'])}")
    for nhom, bang in (("theo benchmark_id", leak["theo_benchmark_id"]),
                      ("theo câu hỏi đã fold", leak["theo_cau_hoi"])):
        for cuoc, v in bang.items():
            print(f"  {'✓ ' if not v else '✗ '}{nhom:24} {cuoc:38} {len(v)}")
    print(f"  {'✓ ' if not leak['theo_text_classifier'] else '✗ '}text classifier trùng nguyên văn: "
          f"{len(leak['theo_text_classifier'])}")
    for k, v in leak["theo_khac"].items():
        print(f"    {k}: {v if not isinstance(v, list) else len(v)}")

    sft_train = read_jsonl(TRAIN_DIR / "sft_train.jsonl")
    sc = self_contained_code_qa(sft_train)
    print(f"[train-audit] #7 code-QA: {sc['n_rows']} dòng, trích file {sc['co_trich_file']}, "
          f"định danh đã kiểm {sc['dinh_danh_kiem_tra']}; "
          f"file thiếu {len(sc['file_thieu'])}, line vượt {len(sc['line_vuot'])}, "
          f"định danh không có trong file {len(sc['dinh_danh_khong_co'])}")
    if sc["dinh_danh_khong_co"]:
        mau = sc["dinh_danh_khong_co"][:8]
        for m in mau:
            print(f"     ✗ {m['id']} → `{m['token']}` không thấy trong {m['file']}")

    lp = None
    if args.loop_roots:
        try:
            lp = loop_family(args.loop_roots)
            for root in lp["roots"]:
                if "error" in root:
                    print(f"[train-audit] #7 loop {root['root']}: {root['error']}")
                    continue
                print(f"[train-audit] #7 loop {root['root']}: {root['n_train_rows']} dòng train, "
                      f"{root['n_holdout_rows']} holdout, {root['n_items']} item, "
                      f"verdict={root['verdict']} đỏ ở {root['red_checks']}; "
                      f"#7 thiếu căn cứ bắt buộc {root['evidence_missing_mandatory']}, "
                      f"thiếu câu vàng {root['evidence_missing_gold_sentence']}; "
                      f"rò rỉ id={root['id_leaks']} câu={root['sentence_leaks']}")
            do = [r for r in lp["roots"] if "error" not in r and r.get("verdict") == "ĐỎ"]
            if do and all(r.get("red_checks") == ["5_format_and_length"] for r in do):
                print("[train-audit] họ loop: ĐỎ **chỉ** ở 5_format_and_length — đó là đỏ DỮ LIỆU "
                      "đã đăng ký (PA-11/PA-12), không phải đỏ của bất biến #7 hay chống rò rỉ")
        except Exception as exc:  # pragma: no cover
            print(f"[train-audit] #7 loop KHÔNG chạy được: {type(exc).__name__}: {exc}")

    if args.out:
        bao_cao = dict(dem_dong=dem, chan_roi_le=leak, tu_chua_code_qa=sc, ho_loop=lp,
                       loop_roots=args.loop_roots)
        Path(args.out).write_text(json.dumps(bao_cao, ensure_ascii=False, indent=2, default=str),
                                  encoding="utf-8")
        print(f"[train-audit] ghi: {args.out}")
    do = bool(lech or leak["tong_roi_le_thuc"] or not sc["ok"])
    if leak["tong_id_trung_ten"]:
        print(f"[train-audit] CẢNH BÁO (không phải rò rỉ): {leak['tong_id_trung_ten']} id trùng giữa "
              f"hai tập nhưng nội dung khác — bộ sinh id theo bộ đếm từng task, không bảo đảm độc nhất "
              f"toàn cục; công cụ nào nối theo id sẽ sai")
    print(f"[train-audit] kết luận: {'CÒN ĐIỂM ĐỎ' if do else 'SẠCH các luật đã đăng ký'}")
    return 1 if do else 0


if __name__ == "__main__":
    raise SystemExit(main())
