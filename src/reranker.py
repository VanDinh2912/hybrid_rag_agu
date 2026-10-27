"""Reranker cross-encoder cho tầng truy xuất (nhiệm vụ T5a, 24-10).

Vì sao cần một tầng này
-----------------------
`tools/loop/attribute.py` quy lỗi FAIL_RETRIEVAL và `tools/diag/bonus_paired.py`
(`data/loop/diag/bonus_paired_r1_r2.json`) đếm được rằng ở round r2 (đường mặc định,
bonus 12) có **57/700 item chunk vàng ĐÃ nằm trong danh sách ứng viên nhưng bị xếp ở
hạng 7-12**, tức là ngoài cửa sổ 6 ô của generator. Lever nguồn (bonus, quota) không
với tới nhóm này một cách miễn phí: mỗi lần nới ưu tiên nguồn là lại đẩy một chunk
ngoài nguồn ra khỏi cửa sổ (21 item hồi quy r1->r2, McNemar p=0,00028). Xếp hạng lại
bằng cross-encoder là đòn bẩy ĐÚNG chỗ: nó chỉ đổi thứ tự, không đổi tập ứng viên.

Tách module riêng (không sửa `src/evidence_selection.py`): cái đó chọn CÂU bằng chứng
cho tầng sinh (T3, đã bác), còn cái này xếp hạng CHUNK cho tầng truy xuất.

Thiết kế đã đăng ký trước trong `data/loop/README.md` (mục T5)
--------------------------------------------------------------
| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `ENABLE_RERANKER` | `0` (TẮT) | bật toàn bộ đường rerank; TẮT thì pipeline không import model, không đổi thứ tự, không đổi gì trên đĩa |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | id cross-encoder. BẮT BUỘC có tiền tố `org/` (hoặc là đường dẫn cục bộ): bài học r9 là `bge-reranker-base` không prefix -> `RepositoryNotFoundError` -> âm thầm lùi về bi-encoder |
| `RERANKER_DEVICE` | `cpu` | `venv` của app cài torch CPU-only (`torch.cuda.is_available() == False`), nên CPU là thiết bị ĐO, không phải phương án lùi |
| `RERANKER_CANDIDATE_POOL` | `20` | số ứng viên lấy từ RRF rồi mới rerank xuống cửa sổ |
| `RERANKER_KEEP_CANDIDATES` | `0` (TẮT) | khi BẬT, `retrieve()` trả về TOÀN BỘ pool đã rerank (hạng tới 20) thay vì cắt `[:k]`, để round đo được trần của pool 20. `contexts`/cửa sổ 6 ô không đổi |
| `RERANKER_MAX_LENGTH` | `512` | trần token mỗi cặp (query, passage) — chunk Tầng 1 dài ~1.300 ký tự nên bắt buộc phải khai trần |
| `RERANKER_BATCH_SIZE` | `4` | batch CPU, chọn thấp để giữ RAM |
| `RERANKER_FALLBACK` | `0` (TẮT) | khi BẬT, lỗi/timeout được **báo cảnh báo** rồi lùi về đúng thứ tự RRF+bonus trước rerank thay vì dừng; vẫn KHÔNG rơi xuống `similarity_search` |

KHÔNG CÓ PHƯƠNG ÁN LÙI THẦM: model không tải được hoặc chấm điểm lỗi ->
`RerankerUnavailable` (kế thừa `RuntimeError`) và `src/pipeline.py` NÉM THẲNG lên
trên, không rơi vào nhánh `except Exception` vốn đã lùi về `similarity_search`. Một
round đo nhầm lever còn tệ hơn một round dừng lại tường minh. Lùi **tường minh** (có
log cảnh báo + manifest `fallback_used=true`) chỉ xảy ra khi bật `RERANKER_FALLBACK=1`
— yêu cầu mục 5 của đề bài kiểm thử T5, và là phương án (a) trong PA-18; mặc định vẫn
là dừng loudly.

Qui ước chấm điểm (ĐÃ ĐÍNH CHÍNH 25-10 theo PA-25 — anh Le Van Dinh duyệt)
-----------------------------------------------------------------------
- query đưa vào cross-encoder là **NGUYÊN VĂN** (chỉ `.strip()`), KHÔNG còn `fold`:
  bản gốc fold(query) vì reasons của nhánh Chroma (`src/pipeline.py`: corpus Tầng 1 mất
  dấu thanh vì OCR), nhưng reranker chấm query × passage và passage giữ nguyên văn còn
  dấu ⇒ cặp lệch dấu làm `bge-reranker-v2-m3` gần như mất tín hiệu. Bằng chứng:
  r12 gold@6 0,7400 → 0,6686 và probe 30 item 0/30 → 28/30 (`tmp/probe_r12_fold.json`),
  sai số học r12 ở `docs/reports/T5.md` §2.7 + `docs/DECISION_LOG.md` D-11;
- passage giữ NGUYÊN VĂN `page_content` (không fold) để phần văn bản còn dấu
  (Tầng 2, `.docx`) không bị bỏ tín hiệu;
- sắp xếp ổn định theo `(-điểm, thứ tự RRF+bonus gốc)` — hai chunk bằng điểm thì
  giữ hạng cũ, nên kết quả tái lập được và không phụ thuộc thứ tự batch.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

# PA-25: `fold` KHÔNG còn được dùng ở đây — score_pairs chấm query nguyên văn. Import
# bỏ đi để ai thêm lại fold phải sửa cả docstring Qui ước chấm điểm, không trượt âm thầm.

ENABLE_RERANKER_ENV = "ENABLE_RERANKER"
RERANKER_MODEL_ENV = "RERANKER_MODEL"
RERANKER_DEVICE_ENV = "RERANKER_DEVICE"
RERANKER_POOL_ENV = "RERANKER_CANDIDATE_POOL"
RERANKER_KEEP_ENV = "RERANKER_KEEP_CANDIDATES"
RERANKER_MAX_LENGTH_ENV = "RERANKER_MAX_LENGTH"
RERANKER_BATCH_SIZE_ENV = "RERANKER_BATCH_SIZE"
RERANKER_FALLBACK_ENV = "RERANKER_FALLBACK"

DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_DEVICE = "cpu"
DEFAULT_CANDIDATE_POOL = 20
DEFAULT_MAX_LENGTH = 512
DEFAULT_BATCH_SIZE = 4

#: Tập giá trị BẬT tường minh (như `router_soft_filter_enabled`) — một giá trị rác
#: trong env không được vô tình bật lever.
_ON_VALUES = {"1", "true", "yes", "on"}


class RerankerUnavailable(RuntimeError):
    """Reranker BẬT nhưng không chạy được. Ném lên trên để round CHẾT loudly."""


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in _ON_VALUES


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(float(raw)))
    except ValueError:
        return default


def reranker_enabled() -> bool:
    """Cờ bật rerank. Mặc định TẮT = hành vi truy xuất cũ từng ký tự."""
    return _flag(ENABLE_RERANKER_ENV)


def reranker_model_id() -> str:
    """Model id đã được chặn lỗi r9 (thiếu tiền tố `org/`)."""
    raw = os.getenv(RERANKER_MODEL_ENV, "").strip() or DEFAULT_RERANKER_MODEL
    if "/" not in raw and not os.path.isdir(raw):
        raise RerankerUnavailable(
            f"RERANKER_MODEL={raw!r} thiếu tiền tố tổ chức. HF Hub cần id dạng "
            f"'BAAI/{raw}' — chính cái tên không prefix này làm r9 lỗi "
            "RepositoryNotFoundError rồi âm thầm lùi về bi-encoder."
        )
    return raw


def reranker_device() -> str:
    return os.getenv(RERANKER_DEVICE_ENV, "").strip() or DEFAULT_DEVICE


def reranker_candidate_pool() -> int:
    return _int_env(RERANKER_POOL_ENV, DEFAULT_CANDIDATE_POOL)


def reranker_keep_candidates() -> bool:
    return _flag(RERANKER_KEEP_ENV)


def reranker_fallback_enabled() -> bool:
    """Lỗi/timeout -> cảnh báo + lùi về thứ tự RRF trước rerank (mục 5 đề bài T5).

    Mặc định TẮT để giữ thiết kế đã đăng ký: round đo dừng loudly thay vì lặng lẽ đo
    một cấu hình khác. Bật cờ này là quyết định tường minh (PA-18a), không phải mặc định.
    """
    return _flag(RERANKER_FALLBACK_ENV)


def reranker_max_length() -> int:
    return _int_env(RERANKER_MAX_LENGTH_ENV, DEFAULT_MAX_LENGTH)


def reranker_batch_size() -> int:
    return _int_env(RERANKER_BATCH_SIZE_ENV, DEFAULT_BATCH_SIZE)


@dataclass
class LastCall:
    """Số liệu lượt rerank gần nhất — round ghi vào `rerank_last_call` để hậu kiểm."""

    n_candidates: int = 0
    n_scored: int = 0
    seconds: float = 0.0
    model: str = ""
    device: str = ""
    pool: int = 0
    top_score: Optional[float] = None
    bottom_score: Optional[float] = None
    order_changed: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_candidates": self.n_candidates,
            "n_scored": self.n_scored,
            "seconds": round(self.seconds, 4),
            "model": self.model,
            "device": self.device,
            "pool": self.pool,
            "top_score": self.top_score,
            "bottom_score": self.bottom_score,
            "order_changed": self.order_changed,
            "notes": list(self.notes),
        }

    def record(self, **values: Any) -> "LastCall":
        """Ghi đè TOÀN BỘ trường cho một lượt rerank.

        Bất buộc mutate tại chỗ (không rebinding tên toàn cục) vì `src/pipeline.py`
        import đối tượng này bằng `from ... import last_call` — rebinding sẽ để lại
        cho pipeline một tham chiếu cũ.
        """
        fresh = LastCall()
        for key in fresh.__dataclass_fields__:
            setattr(self, key, values.get(key, getattr(fresh, key)))
        return self


last_call = LastCall()

_MODEL: Any = None
_LOAD_NOTES: list[str] = []
_LOAD_SECONDS: Optional[float] = None


def get_reranker(*, force_reload: bool = False) -> Any:
    """Tải CrossEncoder MỘT lần cho cả process (2,3 GB — không tải lại mỗi câu).

    Không có phương án lùi: thất bại là `RerankerUnavailable` kèm nguyên văn lỗi.
    """
    global _MODEL, _LOAD_NOTES, _LOAD_SECONDS
    if _MODEL is not None and not force_reload:
        return _MODEL
    model_id = reranker_model_id()
    device = reranker_device()
    max_length = reranker_max_length()
    try:
        from sentence_transformers import CrossEncoder  # import trễ: chỉ khi cờ BẬT
    except Exception as exc:  # noqa: BLE001
        raise RerankerUnavailable(
            f"Không import được sentence_transformers ({type(exc).__name__}: {exc}) "
            "trong khi ENABLE_RERANKER=1."
        ) from exc
    started = time.perf_counter()
    try:
        model = CrossEncoder(model_id, device=device, max_length=max_length)
    except RerankerUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RerankerUnavailable(
            f"Không tải được reranker {model_id!r} trên {device!r}: {type(exc).__name__}: {exc}"
        ) from exc
    _LOAD_SECONDS = round(time.perf_counter() - started, 2)
    _LOAD_NOTES = [f"loaded {model_id} on {device} in {_LOAD_SECONDS}s, max_length={max_length}"]
    _MODEL = model
    return _MODEL


def reset_reranker_cache() -> None:
    """Cho test: bỏ model đã tải khỏi đơn vị trạng thái toàn cục."""
    global _MODEL, _LOAD_NOTES, _LOAD_SECONDS
    _MODEL = None
    _LOAD_NOTES = []
    _LOAD_SECONDS = None


def reranker_status() -> dict[str, Any]:
    """Trạng thái để manifest round ghi lại (đăng ký: round phải tự ký bằng số này)."""
    try:
        requested = reranker_model_id()
        model_error = None
    except RerankerUnavailable as exc:
        requested = os.getenv(RERANKER_MODEL_ENV, "").strip()
        model_error = str(exc)
    return {
        "enabled": reranker_enabled(),
        "requested_model": requested,
        "loaded_model": _LOAD_NOTES[0] if _MODEL is not None and _LOAD_NOTES else None,
        "loaded": _MODEL is not None,
        "load_seconds": _LOAD_SECONDS,
        "device": reranker_device(),
        "candidate_pool": reranker_candidate_pool(),
        "keep_candidates": reranker_keep_candidates(),
        "fallback": reranker_fallback_enabled(),
        "max_length": reranker_max_length(),
        "batch_size": reranker_batch_size(),
        "query_convention": "query NGUYEN VAN (chi strip) vs page_content nguyen van, "
                            "sap xep on dinh theo (-diem, hang RRF+bonus) [PA-25]",
        "model_error": model_error,
        "last_call": last_call.as_dict(),
    }


def score_pairs(model: Any, query: str, passages: Sequence[str]) -> list[float]:
    """Điểm relevance cho từng cặp (query, passage) — API của CrossEncoder."""
    # PA-25: chấm query NGUYÊN VĂN với passage nguyên văn. fold(query) từng làm r12 sụp
    # (gold@6 0,74->0,6686, EXACT 0,2115->0,0385) vì cặp lệch dấu thanh với model đa ngôn ngữ.
    # Bằng chứng: tmp/probe_r12_fold.json (0/30 -> 28/30 chunk vàng vào top-6).
    q = (query or "").strip()
    pairs = [(q, p or "") for p in passages]
    raw = model.predict(pairs, batch_size=reranker_batch_size(), convert_to_numpy=True)
    return [float(x) for x in raw]


def rerank_documents(
    query: str,
    docs: Sequence[Any],
    *,
    pool: Optional[int] = None,
    top_n: Optional[int] = None,
    model: Any = None,
) -> list[Any]:
    """Lấy `pool` ứng viên đầu (theo thứ tự RRF+bonus đang có) rồi xếp lại bằng cross-encoder.

    Trả về danh sách ĐÃ SẮP XẾP theo điểm giảm dần (hạng bằng nhau -> giữ thứ tự cũ).
    `top_n` (thường = cửa sổ k) chỉ là giới hạn cắt; để NGUYÊN nếu muốn giữ cả pool.
    """
    candidates = list(docs or [])
    if not candidates:
        return []
    pool_size = reranker_candidate_pool() if pool is None else max(1, int(pool))
    window = candidates[:pool_size]
    tail = candidates[pool_size:]

    active_model = model if model is not None else get_reranker()
    started = time.perf_counter()
    try:
        scores = score_pairs(active_model, query, [getattr(d, "page_content", "") or "" for d in window])
    except RerankerUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RerankerUnavailable(f"Reranker chấm điểm thất bại: {type(exc).__name__}: {exc}") from exc
    if len(scores) != len(window):
        raise RerankerUnavailable(
            f"Reranker trả {len(scores)} điểm cho {len(window)} ứng viên — lệch số lượng, không đoán tiếp."
        )

    keyed = [(-scores[i], i, window[i]) for i in range(len(window))]
    keyed.sort(key=lambda item: (item[0], item[1]))
    ranked = [doc for _, _, doc in keyed]

    last_call.record(
        n_candidates=len(candidates),
        n_scored=len(window),
        seconds=time.perf_counter() - started,
        model=os.getenv(RERANKER_MODEL_ENV, "").strip() or DEFAULT_RERANKER_MODEL,
        device=reranker_device(),
        pool=pool_size,
        top_score=round(max(scores), 4),
        bottom_score=round(min(scores), 4),
        order_changed=[id(d) for d in ranked] != [id(d) for d in window],
        notes=list(_LOAD_NOTES),
    )

    ordered = ranked + tail
    if top_n is not None:
        return ordered[: max(0, int(top_n))]
    return ordered
