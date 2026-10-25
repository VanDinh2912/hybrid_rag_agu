"""B4 (đêm 25-10) — cửa sổ có "trả lời được" không: dựng tập nhãn trên ĐĨA + đo một
cross-encoder nhỏ so với HẠNG TRUY XUẤT. Không gọi model sinh, 0 lượt Gemini.

Đề bài: "với cửa sổ của r5 và các cửa sổ 'bỏ chunk vàng', dựng tập nhãn trả-lời-được/không
(group split theo tài liệu) và đo một cross-encoder nhỏ phân biệt được bao nhiêu so với hạng
truy xuất. Nếu AUC < 0,75 thì dừng và ghi kết quả âm."

Vì sao cặp nhãn này trả lời được câu hỏi thật
--------------------------------------------
Lever T3 (`ENABLE_DECOUPLED_REFUSAL`) và r8 đều chết vì cùng một chỗ: tầng ngoài không biết
"ngữ cảnh đang có là đủ để đáp hay không", nên hoặc từ chối oan hoặc trả lời bừa. Một máy
đo answerability chạy trên cửa sổ 6 ô (không cần sinh) sẽ cắm được vào đúng chỗ đó. Probe này
đo TRƯỚC xem tín hiệu có tồn tại không, bằng cách so hai loại cửa sổ của CÙNG một câu:

* POS  = cửa sổ r5 thật (chunk vàng nằm trong 6 ô);
* NEG  = cửa sổ của chính câu đó nhưng RÚT chunk vàng ra và bù bằng ứng viên hạng kề tiếp
  (giữ đúng 6 ô, cùng độ dài ngữ cảnh, đổi duy nhất một biến: có/không căn cứ vàng).

Nhãn NEG là "giả định cấu trúc", không phải chân lý tuyệt đối: rút vàng vẫn có thể để lại
chunk khác chứa đáp án. Vì vậy mỗi cặp được gắn cờ `still_answerable` (đo bằng chữ, không đoán):
`gold_sentence` (fold) còn xuất hiện trong NEG, hoặc toàn bộ `required_entities` phủ được NEG.
Ca có cờ này là nhiễu nhãn đã biết — báo cáo cả hai phiên bản (kèm và bỏ cờ).

Tiêu chí ĐĂNG KÝ TRƯỚC (chốt trước khi chạy `--score`, không chỉnh sau khi thấy số)
---------------------------------------------------------------------------------
| Chỉ số | Định nghĩa | Ngưỡng |
|---|---|---|
| `auc_ce_max` (CHÍNH) | AUC Mann-Whitney của điểm cross-encoder CỰC ĐẠI trên ô, POS so với NEG, tính trên **partition eval** (tài liệu không giao nhau với train) | ≥ 0,75 ⇒ có tín hiệu, đề xuất; < 0,75 ⇒ DỪNG, ghi âm |
| `auc_rank_min` (MỐC) | AUC của mốc truy xuất `−(hạng nhỏ nhất trong cửa sổ)`, hạng tính theo VỊ TRÍ 1..k — cùng tập eval, cùng cặp nhãn | chỉ để so sánh, không phải ngưỡng. ĐÍNH CHÍNH THIẾT KẾ 25-10, ghi trước khi chạy `--score`: một cửa sổ 6 ô luôn bắt đầu ở hạng 1 ⇒ mốc này phẳng theo construction (AUC 0,5) và KHÔNG được diễn giải là "CE thắng/kém hạng"; dùng `neg_source_ranks` (hạng truy xuất gốc) nếu muốn thấy ô bù đến từ đâu, và `gold_rank_dist` cho tín hiệu hạng thật. Ngưỡng CHÍNH 0,75 giữ nguyên. |
| `auc_ce_max_pooled` | như `auc_ce_max` nhưng gộp mọi tài liệu | báo cáo phụ |
| `n_pairs_eval` | số cặp POS/NEG trên eval | `n < 30` ⇒ chỉ là ước lượng thô, ghi rõ, không kết luận |

Group split: hàm `md5(tên tài liệu)` quyết định partition, tất định và không đổi khi thêm dữ
liệu khác; in bảng phân bố để thấy tài liệu nào nằm ở đâu. Cross-encoder mặc định
`BAAI/bge-reranker-base` (278M — "nhỏ" theo đề bài); nếu weights không có trên đĩa và không
tải được, `--model BAAI/bge-reranker-v2-m3` là phương án dự phòng NHƯNG phải ghi rõ trong báo
cáo rằng nó không còn là model nhỏ (568M) và là đúng model của lever T5a đang đo.

ĐÃ KIỂM TRÊN ĐĨA (26-10, trước khi đo): `~/.cache/huggingface/hub` có `models--BAAI--bge-m3`,
`models--BAAI--bge-reranker-v2-m3`, `models--Qwen--Qwen2.5-0.5B-Instruct`,
`models--Qwen--Qwen2.5-3B-Instruct` nhưng KHÔNG có `bge-reranker-base` ⇒ đúng nhánh dự phòng ở
đoạn trên. Ngã rẽ bảo thủ: KHÔNG tải 1,1 GB weights mới trong ca trực, chạy bằng
`BAAI/bge-reranker-v2-m3` (568M) và báo cáo B4 phải nói thẳng đây KHÔNG còn là "cross-encoder
nhỏ" — phép đo trả lời "chính model reranker hiện tại có biết cửa sổ nào trả lời được không",
còn câu "một model NHỎ có làm được không" vẫn TRỐNG và cần tải weights (đề xuất riêng, chờ duyệt).

Cỡ mẫu ĐÃ KIỂM TRƯỚC KHI ĐO (26-10, đọc `data/loop/rounds/r5/full.jsonl` trên đĩa — chỉ đếm
cặp, chưa có bất kỳ AUC nào): r5 có 100 dòng, 59 dòng có chunk vàng trong cửa sổ 6 ô và cả 59
đều còn ứng viên hạng 7 để bù (0 cặp bị loại vì thiếu ô bù). Nhóm theo tài liệu: train 30 /
eval 29, và 13 dòng thiếu tên tài liệu KHÔNG nằm trong 59 cặp đó. Nghĩa là
**`n_pairs_eval = 29 < MIN_PAIRS_FOR_CONCLUSION = 30` ngay từ thiết kế**, tức phán quyết đúng
của mẫu đăng ký r5 gần như chắc chắn là `MAU_QUA_NHO` bất kể AUC ra sao. Ngưỡng 30 đã đăng ký
trước nên KHÔNG được hạ. Phương án đã ghi ở đây, trước khi thấy số: dựng thêm tập nhãn trên
`rounds/r11` và `rounds/r12` (811 dòng, pha retrieval, cùng cửa sổ 6 ô, cùng index) bằng
`--round r11 --phase retrieval`, báo cáo là **mẫu BỔ SUNG được ghi nhãn rõ ràng**; phán quyết
CHÍNH vẫn lấy từ mẫu r5 đã đăng ký, và nếu hai mẫu mâu thuẫn thì ghi cả hai chứ không chọn mẫu
đẹp. Khi đã có mẫu lớn hơn, AUC của mẫu r5 chỉ còn vai trò kiểm tra hướng (sign), không đủ sức
kết luận thông tin.

Chạy:
    # 1) chỉ dựng tập nhãn (đĩa, 0 model)
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/answerability_probe.py --build-only
    # 2) chấm cross-encoder (cần GPU/RAM nhàn rỗi)
    PYTHONIOENCODING=utf-8 venv_gpu/Scripts/python.exe tools/diag/answerability_probe.py \
        --model BAAI/bge-reranker-base --device cuda
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.text_utils import fold  # noqa: E402  (chỉ dùng cho cờ still_answerable)

ROUNDS = ROOT / "data" / "loop" / "rounds"
OUT_DEFAULT = ROOT / "data" / "loop" / "diag" / "answerability_probe.json"
DATASET_DEFAULT = ROOT / "data" / "loop" / "diag" / "answerability_labelset_r5.jsonl"

# Index mà r5 chạy thật (361 chunk). `chroma_db_vie` là bản re-OCR CHƯA kích hoạt —
# dùng nó sẽ so cửa sổ của một index khác với nhãn của r5.
INDEX_DEFAULT = "chroma_db"

WINDOW_K = 6
AUC_THRESHOLD = 0.75  # đăng ký trước, xem docstring
MIN_PAIRS_FOR_CONCLUSION = 30

_ENTITY_SPLIT = re.compile(r"[\s,;./–—(){}\[\]]+")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --------------------------------------------------------------------------- dựng tập nhãn
def split_of(document: str) -> str:
    """Partition theo TÀI LIỆU (không theo câu) — tất định, không phụ thuộc thứ tự dữ liệu.

    Item KHÔNG có tên tài liệu (13/100 dòng của r5, đã kiểm trên đĩa trước khi đo) trả
    `khong_ro_tai_lieu` thay vì bị md5('') nhét hết vào một partition: làm vậy tạo một ô
    "tài liệu" giả chứa toàn bộ ca thiếu nhãn nguồn, vừa rò rỉ (cùng một partition gom những
    câu không liên quan) vừa phồng mẫu. Những ca này vẫn được chấm và hiện trong `pooled_*`,
    nhưng KHÔNG được tính vào `eval` — phán quyết chính chỉ dựa trên tài liệu biết rõ.
    """
    doc = (document or "").strip()
    if not doc:
        return "khong_ro_tai_lieu"
    return "train" if int(hashlib.md5(doc.encode("utf-8")).hexdigest()[:8], 16) % 2 == 0 else "eval"


def _covers(neg_texts: Sequence[str], item: dict) -> str:
    """Cờ nhiễu nhãn: NEG vẫn còn đáp án không? Trả về '' nếu không, hoặc lý do nếu có."""
    joined = " ".join(fold(t or "") for t in neg_texts)
    gold = fold(item.get("gold_sentence") or "")
    if len(gold) >= 24 and gold in joined:
        return "gold_sentence_con_neg"
    ents = [e for e in (item.get("required_entities") or []) if str(e).strip()]
    if ents:
        toks = [fold(e).strip() for e in ents]
        if toks and all(t and t in joined for t in toks):
            return "required_entities_du_bo_trong_neg"
    return ""


def build_pairs(rows: Sequence[dict], *, k: int = WINDOW_K,
                texts: Optional["IndexTexts"] = None) -> tuple[list[dict], dict[str, int]]:
    """Mỗi dòng r5 có chunk vàng trong cửa sổ ⇒ một cặp POS/NEG.

    NEG = đúng cửa sổ đó nhưng ô vàng được THAY bằng ứng viên hạng kề tiếp (hạng k+1) —
    văn bản của ô bù đọc từ index trên đĩa (`IndexTexts`, 0 lượt sinh, 0 model). Không bù
    được (thiếu id/truy vấn index lỗi) ⇒ ĐẾM và loại cặp, không âm thầm chấm cửa sổ 5 ô.
    """
    pairs: list[dict] = []
    skip = Counter()
    for row in rows:
        item = row.get("item") or {}
        gold = item.get("gold_chunk_id")
        srcs = row.get("sources") or []
        if row.get("error"):
            skip["loi_tinh_nang"] += 1
            continue
        if gold is None:
            skip["khong_co_chunk_vang"] += 1
            continue
        window = srcs[:k]
        pos_rank = next((i for i, s in enumerate(window) if s.get("chunk_id") == gold), None)
        if pos_rank is None:
            skip["vang_ngoai_cua_so"] += 1
            continue
        pos_texts = list((row.get("contexts") or [])[:k])
        if len(pos_texts) != k:
            skip["thieu_text_trong_round_jsonl"] += 1
            continue
        filler = next((s for s in srcs[k:]), None)
        if filler is None:
            skip["khong_con_ung_vien_de_bu"] += 1
            continue
        filler_txt = texts.text_for(filler.get("chunk_id")) if texts is not None else ""
        if not (filler_txt or "").strip():
            skip["khong_doc_duoc_text_ung_vien_bu"] += 1
            continue
        neg_texts = pos_texts[:pos_rank] + pos_texts[pos_rank + 1:k] + [filler_txt]
        # `neg_ranks` là hạng VỊ TRÍ (1..k) chứ không phải hạng truy xuất gốc của từng ô còn lại.
        # Lý do (đính chính thiết kế, ghi trước khi chạy --score): nếu giữ hạng gốc thì NEG chỉ
        # mất hạng 1 khi chunk vàng đang chiếm hạng 1 ⇒ giá trị feature tiết lộ nhãn (leakage)
        # và AUC của mốc hạng thành trần "gian lận", không phải phép so sánh công bằng. Trong
        # triển khai thật một cửa sổ 6 ô LUÔN bắt đầu từ hạng 1, nên thông tin hạng thuần túy là
        # hằng số — đó chính là kết luận cần đo. Hạng gốc vẫn được giữ ở `neg_source_ranks`.
        pairs.append({
            "id": row["id"],
            "family": item.get("family"),
            "split_doc": split_of(item.get("source_document") or ""),
            "source_document": item.get("source_document"),
            "raw_query": item.get("raw_query"),
            "gold_chunk_id": gold,
            "gold_rank": window[pos_rank].get("rank", pos_rank + 1),
            "pos_chunks": pos_texts,
            "neg_chunks": neg_texts[:k],
            "pos_ranks": list(range(1, k + 1)),
            "neg_ranks": list(range(1, k + 1)),
            "neg_source_ranks": sorted(r for r in
                                       [window[i].get("rank", i + 1) for i in range(k) if i != pos_rank]
                                       + [filler.get("rank")] if r is not None),
            "filler_chunk_id": filler.get("chunk_id"),
            "still_answerable": _covers(neg_texts[:k], item),
        })
    return pairs, dict(skip)


class IndexTexts:
    """Đọc `page_content` của một `chunk_id` từ collection Chroma trên ĐĨA.

    `col.get(where={"chunk_id": n})` không nhúng vector nên không cần model nền; mở một lần,
    cache theo id. Fail-open: thiếu collection/lỗi ⇒ trả '' và để `build_pairs` ĐẾM ca thiếu
    (không được âm thầm đổi nhãn).
    """

    def __init__(self, persist_dir: Path, collection: str = "agu_regulations"):
        self.persist_dir = Path(persist_dir)
        self.collection = collection
        self._col = None
        self._cache: dict[Any, str] = {}
        self.error: Optional[str] = None
        self.n_reads = 0
        self.n_miss = 0

    def _open(self):
        if self._col is not None or self.error:
            return self._col
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._col = client.get_collection(self.collection)
        except Exception as exc:  # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"
        return self._col

    def text_for(self, chunk_id: Any) -> str:
        if chunk_id is None or chunk_id in ("", ()):
            return ""
        if chunk_id in self._cache:
            return self._cache[chunk_id]
        col = self._open()
        got = ""
        if col is not None:
            try:
                res = col.get(where={"chunk_id": chunk_id})
                docs = res.get("documents") or []
                got = (docs[0] or "") if docs else ""
                self.n_reads += 1
                if not got:
                    self.n_miss += 1
            except Exception as exc:  # noqa: BLE001
                self.error = f"get(chunk_id={chunk_id}) {type(exc).__name__}: {exc}"
        self._cache[chunk_id] = got
        return got

    def stats(self) -> dict[str, Any]:
        return {"persist_dir": self.persist_dir.name, "collection": self.collection,
                "n_reads": self.n_reads, "n_miss": self.n_miss, "error": self.error}


# --------------------------------------------------------------------------- điểm + AUC
def auc(pos_scores: Sequence[float], neg_scores: Sequence[float]) -> Optional[float]:
    """AUC Mann-Whitney (tie tính 0,5). Trả None nếu một trong hai nhóm rỗng."""
    if not pos_scores or not neg_scores:
        return None
    wins = 0.0
    for p in pos_scores:
        for n in neg_scores:
            wins += 1.0 if p > n else (0.5 if p == n else 0.0)
    return round(wins / (len(pos_scores) * len(neg_scores)), 4)


def rank_feature(pair: dict, which: str) -> float:
    """Mốc 'hạng truy xuất': điểm CÀNG CAO CÀNG tốt ⇒ dùng −hạng nhỏ nhất trong cửa sổ.

    ĐÍNH CHÍNH THIẾT KẾ 25-10 (ghi trước khi chạy `--score`). Hai sự thật về construction:
    (1) NEG chỉ khác POS ở MỘT ô; (2) trong triển khai thật, một cửa sổ 6 ô luôn có ô đầu ở
    hạng 1. Vì vậy `neg_ranks` được ghi theo hạng VỊ TRÍ (1..k) — nếu ghi hạng truy xuất gốc
    thì NEG chỉ mất hạng 1 khi chunk vàng chiếm hạng 1, tức feature tự tiết lộ nhãn và AUC của
    nó thành trần "gian lận" thay vì phép so sánh công bằng. Hệ quả: mốc này phẳng theo
    construction (AUC = 0,5), và `rank_min_phang` bật cờ True để không ai đọc 0,5 thành
    "CE thua hạng". Thông tin hạng thật sự có nghĩa nằm ở `gold_rank` (phân bố in trong báo
    cáo), không phải ở bản thân cửa sổ.
    """
    ranks = pair[f"{which}_ranks"]
    return -float(min(ranks)) if ranks else float("nan")


def aggregate_scores(scores: list[dict], pairs: list[dict]) -> dict[str, Any]:
    """Đo AUC theo từng cách gộp điểm cửa sổ: max / mean / top2-mean, trên eval + pooled."""
    by_id = {p["id"]: p for p in pairs}
    out: dict[str, Any] = {}
    for scope, keep in (("eval", lambda p: p["split_doc"] == "eval"),
                        ("pooled", lambda p: True)):
        use = [p for p in pairs if keep(p) and not p["still_answerable"]]
        use_all = [p for p in pairs if keep(p)]
        for name, dataset in (("clean", use), ("all", use_all)):
            got = [s for s in scores if s["id"] in {p["id"] for p in dataset}]
            if not got:
                continue
            feats = {}
            for label, key in (("ce_max", "ce_max"), ("ce_mean", "ce_mean"), ("ce_top2", "ce_top2")):
                feats[label] = auc([s[key]["pos"] for s in got], [s[key]["neg"] for s in got])
            pos_rank = [rank_feature(by_id[s["id"]], "pos") for s in got]
            neg_rank = [rank_feature(by_id[s["id"]], "neg") for s in got]
            feats["rank_min"] = auc(pos_rank, neg_rank)
            out[f"{scope}_{name}"] = {
                "n_pairs": len(got), "auc": feats,
                "mau_qua_nho": len(got) < MIN_PAIRS_FOR_CONCLUSION,
                # Mốc hạng chỉ có ý nghĩa khi phân bố của nó thay đổi; ghi thẳng số giá trị
                # riêng để người đọc biết AUC của nó có phải tín hiệu thật không.
                "rank_min_pos_distinct": sorted(set(pos_rank)),
                "rank_min_neg_distinct": sorted(set(neg_rank)),
                "rank_min_phang": len(set(pos_rank)) == 1 and len(set(neg_rank)) == 1,
                # Tín hiệu hạng thật sự có nghĩa: chunk vàng đứng hạng mấy trong cửa sổ POS.
                "gold_rank_dist": dict(sorted(Counter(p["gold_rank"] for p in dataset).items())),
            }
    return out


# --------------------------------------------------------------------------- chấm bằng model
def score_with_cross_encoder(pairs: list[dict], *, model_id: str, device: str,
                             max_length: int = 512) -> tuple[list[dict], dict[str, Any]]:
    from sentence_transformers import CrossEncoder  # import trễ: chỉ khi chạy --score

    started = datetime.now()
    model = CrossEncoder(model_id, device=device, max_length=max_length)
    scores: list[dict] = []
    n_pairs_scored = 0
    for p in pairs:
        # PA-25: query NGUYÊN VĂN (chỉ strip) chấm với passage nguyên văn — cùng qui ước với
        # `src/reranker.py` sau when sửa đã duyệt; `fold()` ở đây sẽ tái tạo đúng lỗi r12.
        q = (p["raw_query"] or "").strip()
        window = {}
        for which in ("pos", "neg"):
            texts = p[f"{which}_chunks"]
            vals = [float(x) for x in model.predict([(q, t or "") for t in texts],
                                                    convert_to_numpy=True)]
            n_pairs_scored += len(texts)
            ordered = sorted(vals, reverse=True)
            window[which] = {
                "max": max(vals),
                "mean": round(statistics.fmean(vals), 4),
                "top2": round(statistics.fmean(ordered[:2]), 4) if len(ordered) >= 2 else ordered[0],
                "per_chunk": [round(v, 4) for v in vals],
            }
        scores.append({"id": p["id"],
                       "ce_max": {"pos": window["pos"]["max"], "neg": window["neg"]["max"]},
                       "ce_mean": {"pos": window["pos"]["mean"], "neg": window["neg"]["mean"]},
                       "ce_top2": {"pos": window["pos"]["top2"], "neg": window["neg"]["top2"]},
                       "per_chunk": {k2: v2["per_chunk"] for k2, v2 in window.items()}})
    meta = {"mode": "scored", "model_id": model_id, "device": device, "max_length": max_length,
            "n_pairs_scored": n_pairs_scored,
            "seconds": round((datetime.now() - started).total_seconds(), 1)}
    return scores, meta


# --------------------------------------------------------------------------- kết luận
def ket_luan(agg: dict[str, Any], meta: dict[str, Any], skip: dict[str, int]) -> dict[str, Any]:
    primary = agg.get("eval_clean") or agg.get("eval_all") or {}
    a_ce = (primary.get("auc") or {}).get("ce_max")
    a_rank = (primary.get("auc") or {}).get("rank_min")
    n = primary.get("n_pairs", 0)
    if a_ce is None:
        verdict = "KHONG_DO_DUOC"
        why = ("không có cặp nào trên partition eval — xem `skipped` (thường là "
               "`khong_doc_duoc_text_ung_vien_bu` khi đọc index lỗi) và trường `index`")
    elif n < MIN_PAIRS_FOR_CONCLUSION:
        verdict = "MAU_QUA_NHO"
        why = f"n_pairs_eval={n} < {MIN_PAIRS_FOR_CONCLUSION} — chỉ là ước lượng thô"
    elif a_ce >= AUC_THRESHOLD:
        verdict = "CO_TIN_HIEU"
        why = f"auc_ce_max={a_ce} >= {AUC_THRESHOLD}"
    else:
        verdict = "AM_DUNG"
        why = f"auc_ce_max={a_ce} < {AUC_THRESHOLD} — theo đề bài: DỪNG, ghi kết quả âm"
    return {"verdict": verdict, "ly_do": why,
            "nguong_dang_ky": AUC_THRESHOLD, "auc_ce_max": a_ce, "auc_rank_min": a_rank,
            "n_pairs_eval": n, "so_cap_lo_do_thieu_text": skip.get("khong_doc_duoc_text_ung_vien_bu", 0),
            "model": meta, "so_khong_duoc_tinh": {k: v for k, v in skip.items() if v}}


def print_report(result: dict[str, Any]) -> None:
    print(f"[dataset] {result['dataset_path']} — {result['n_pairs']} cặp POS/NEG từ {result['round']}")
    print("  nguồn cặp:", result.get("pairs_source"))
    print("  index:", json.dumps(result.get("index", {}), ensure_ascii=False))
    print("  bỏ qua:", json.dumps(result["skipped"], ensure_ascii=False))
    print("  theo partition:", json.dumps(result["by_split"], ensure_ascii=False))
    print("  still_answerable (nhiễu nhãn đã biết):", result["n_still_answerable"])
    print("  số cặp đã chấm:", result.get("n_scored", 0), "| meta:", json.dumps(result.get("model_meta", {}), ensure_ascii=False))
    for scope, blk in result["aggregate"].items():
        print(f"  [{scope}] n={blk['n_pairs']}{' (mẫu quá nhỏ)' if blk['mau_qua_nho'] else ''}: "
              + " ".join(f"{k}={v}" for k, v in blk["auc"].items())
              + ("  (mốc hạng PHẲNG theo construction — xem docstring)" if blk.get("rank_min_phang") else ""))
    kl = result["ket_luan"]
    print(f"[KET LUAN] {kl['verdict']} — {kl['ly_do']}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Probe answerability của cửa sổ truy xuất (0 lượt sinh).")
    ap.add_argument("--round", default="r5")
    ap.add_argument("--phase", default="full", choices=["full", "retrieval"])
    ap.add_argument("--k", type=int, default=WINDOW_K)
    ap.add_argument("--dataset-out", default=str(DATASET_DEFAULT))
    ap.add_argument("--dataset-in", default="", help="đọc tập nhãn đã dựng sẵn thay vì dựng lại")
    ap.add_argument("--model", default="", help="rỗng = CHỈ dựng nhãn (--build-only); id HF hoặc đường dẫn")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-windows", type=int, default=0, help="giới hạn số cặp chấm (0 = tất cả)")
    ap.add_argument("--index-dir", default=INDEX_DEFAULT,
                    help="thư mục Chroma đọc text ô bù (mặc định = index mà round chạy thật)")
    ap.add_argument("--collection", default="agu_regulations")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args(argv)

    index_dir = Path(args.index_dir)
    if not index_dir.is_absolute():
        index_dir = ROOT / index_dir
    texts = IndexTexts(index_dir, collection=args.collection)

    if args.dataset_in:
        pairs = load_jsonl(Path(args.dataset_in))
        skip = {"doc_from_dataset": len(pairs)}
    else:
        rows_path = ROUNDS / args.round / f"{args.phase}.jsonl"
        if not rows_path.exists():
            raise SystemExit(f"[dataset] không có {rows_path}")
        pairs, skip = build_pairs(load_jsonl(rows_path), k=args.k, texts=texts)

    ds_path = Path(args.dataset_out)
    if not args.dataset_in:
        ds_path.parent.mkdir(parents=True, exist_ok=True)
        with ds_path.open("w", encoding="utf-8") as fh:
            for p in pairs:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")

    by_split = Counter(p["split_doc"] for p in pairs)
    docs = defaultdict(set)
    for p in pairs:
        docs[p["split_doc"]].add(p["source_document"] or "")

    result: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "purpose": "B4 — cửa sổ có căn cứ vàng vs cùng cửa sổ rút vàng: cross-encoder nhỏ "
                   "phân biệt tới đâu so với hạng truy xuất (0 lượt sinh)",
        "round": args.round, "k": args.k, "window_k_note": "NEG giữ đúng 6 ô, bù bằng hạng kề tiếp",
        "pairs_source": args.dataset_in or f"{args.round}/{args.phase}.jsonl + index {texts.persist_dir.name}",
        "index": texts.stats(),
        "dataset_path": str(ds_path.relative_to(ROOT)).replace("\\", "/") if ds_path.is_relative_to(ROOT) else str(ds_path),
        "n_pairs": len(pairs),
        "skipped": skip,
        "by_split": {s: {"pairs": n, "documents": len(docs[s])} for s, n in sorted(by_split.items())},
        "n_still_answerable": sum(1 for p in pairs if p["still_answerable"]),
        "preregistered": {"auc_threshold": AUC_THRESHOLD, "min_pairs": MIN_PAIRS_FOR_CONCLUSION,
                          "primary": "auc_ce_max trên eval_clean"},
    }

    scores: list[dict] = []
    scored = not args.build_only and bool(args.model)
    meta: dict[str, Any] = {"mode": "build_only" if not scored else "scored"}
    if scored:
        subset = pairs if not args.max_windows else pairs[: args.max_windows]
        scores, meta = score_with_cross_encoder(subset, model_id=args.model, device=args.device)
    result["n_scored"] = len(scores)
    result["model_meta"] = meta
    result["aggregate"] = aggregate_scores(scores, pairs) if scores else {}
    result["ket_luan"] = ket_luan(result["aggregate"], meta, skip)
    if scores:
        result["scores"] = scores

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(result)
    print(f"[out] {out_path}")
    # rc đỏ = dụng cụ đo hỏng, không phải kết quả âm. Kết luận AM_DUNG/MAU_QUA_NHO là những
    # câu trả lời hợp lệ theo tiêu chí đã đăng ký trước ⇒ rc 0. Hai tình huống hỏng:
    #   * 0 cặp nhãn dựng được (thường là đọc index thất bại — xem trường `index` + `skipped`);
    #   * đã chạy `--score` mà vẫn không đo được AUC (partition eval trống).
    verdict = result["ket_luan"]["verdict"]
    return 1 if (not pairs or (scored and verdict == "KHONG_DO_DUOC")) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # D-36
    raise SystemExit(main())
