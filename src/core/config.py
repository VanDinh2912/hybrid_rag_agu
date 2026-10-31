"""Điểm ĐỌC biến môi trường duy nhất cho các module `src/` đã chuyển đổi (dọn repo B4).

Vì sao có file này
------------------
Trước B4 mỗi module tự gọi `os.getenv` với cách hiểu riêng, nên muốn biết "lượt chạy này
đang bật gì" phải grep 9 file. File này gom lại, nhưng tuyệt đối KHÔNG đổi giá trị mặc
định hay ngữ nghĩa parse của bất kỳ site cũ nào: mỗi accessor dưới đây là bản sao hành vi
từng ký tự của site gốc (kể cả chỗ coi chuỗi rỗng là TẮT, chỗ ném lỗi khi số hỏng, chỗ
kẹp ngưỡng về mặc định).

Ba nguyên tắc
-------------
1. KHÔNG gọi `load_dotenv()` ở đây. Module trước đây tự nạp dotenv (classifier) vẫn tự
   nạp; module không nạp (vector_db, loader…) vẫn không nạp. Gom cấu hình không được kéo
   theo thay đổi nguồn env.
2. KHÔNG đọc env lúc import. Test dùng ~198 lời gọi `monkeypatch.setenv` để đổi env giữa
   hai lượt gọi hàm, nên `settings()` cache theo **ảnh chụp** env: env đổi → dựng lại
   Settings; env yên → trả lại đúng instance cũ (một lượt đọc cả danh sách, không phải mỗi
   getter một lần `os.getenv`).
3. Tên `_flag` / `_env_flag` / `_env_int` / `_env_float` không phải sở thích: máy kiểm
   `tools/diag/env_flag_audit.py` chỉ nhận diện đúng các "reader" này khi quét tĩnh.
   Đổi tên accessor là làm máy kiểm mù site đọc cờ — xem `tests/test_final_env_flag_defaults.py`.

Phạm vi
-------
Chỉ 9 module đã chuyển: contextual_header, evidence_selection, refusal_policy, retrieval,
loader, vector_db, local_slm, classifier, chunking. CỐ Ý không chuyển:
`generator/pipeline/query_normalizer/router` (đóng băng PA-26), `answer_guard` (file trọng
tài — chữ ký `referee_fingerprint` băm byte), `evaluation` (runner đo), `reranker` (chưa
được track). Các file đó vẫn đọc env trực tiếp; việc gom nốt nằm ở PA-44. Hai ngoại lệ đã
đăng ký: `pipeline` đọc **một** cờ mới (`ENABLE_DENSE_ORIGINAL_QUERY`, PA-48a) qua
`settings()._flag(...)`; và REVIEW §3 (31-10) gom `RAG_TOP_K` về `top_k_from_env()` cho
`main`/`router` — các cờ cũ của hai module đó vẫn đọc trực tiếp như trước.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional

#: Số chunk ngữ cảnh mặc định cho MỌI entry point (REVIEW §3, 31-10).
#: Trước đây bốn nơi khai báo bốn giá trị (pipeline 4, router 4, main/evaluation 6,
#: GUI 6). Chọn 6 vì đó là cấu hình đã dùng cho các phép đo công bố (rounds truyền
#: top_k tường minh) và cho CLI/GUI/evaluation; đây là hằng số DUY NHẤT, mỗi entry
#: point vẫn được override qua tham số/`--top-k` như cũ.
DEFAULT_TOP_K = 6

#: Mọi biến mà 9 module đã chuyển có thể đọc. `settings()` chụp ĐÚNG danh sách này;
#: accessor gọi một tên ngoài danh sách sẽ `KeyError` ngay (fail-fast: thêm site đọc mà
#: quên khai báo thì không thể nhận giá trị cache cũ một cách âm thầm).
TRACKED_ENV: tuple[str, ...] = (
    # contextual header (T5b)
    "ENABLE_CONTEXTUAL_HEADER",
    # evidence selection (T3)
    "ENABLE_EVIDENCE_SELECTION",
    "EV_MIN_KEYWORD_HITS",
    "EV_MIN_SENTENCES",
    "EV_MAX_SENTENCES",
    "EVIDENCE_RERANKER",
    # decoupled refusal (T3)
    "ENABLE_DECOUPLED_REFUSAL",
    "DEC_MIN_ENTITY_COVERAGE",
    "DEC_MIN_TOKEN_OVERLAP",
    "DEC_MIN_RRF_NORM",
    "DEC_MIN_GROUNDING",
    "DEC_MAX_UNSUPPORTED",
    # Ollama (retrieval / local_slm / classifier)
    "OLLAMA_MODEL",
    "OLLAMA_HOST",
    "OLLAMA_TIMEOUT",
    # loader OCR
    "OCR_ENABLED",
    "OCR_DPI",
    "OCR_MIN_CHARS_PER_PAGE",
    "OCR_CACHE_DIR",
    # vector DB / trọng số RRF
    "CHROMA_PERSIST_DIR",
    "BM25_WEIGHT",
    "CHROMA_WEIGHT",
    # classifier
    "CLASSIFIER_TIMEOUT",
    "CLASSIFIER_MODEL",
    # chunking
    "EMBEDDING_MODEL",
    # pipeline (V1/PA-48a): chỉ nhánh dense dùng query nguyên văn thay vì fold
    "ENABLE_DENSE_ORIGINAL_QUERY",
    # top_k vận hành (REVIEW §3): một nguồn đọc chung cho main/router
    "RAG_TOP_K",
)

#: Giá trị được coi là BẬT khi dùng ngữ nghĩa `in _ON_VALUES` (contextual_header).
_ON_VALUES = {"1", "true", "yes", "on"}
#: Giá trị được coi là TẮT khi dùng ngữ nghĩa `not in _OFF_VALUES` (evidence/refusal/OCR).
_OFF_VALUES = {"", "0", "false", "no", "off"}


@dataclass(frozen=True)
class Settings:
    """Ảnh chụp env + accessor parse theo đúng ngữ nghĩa từng site cũ.

    `raw` phủ ĐÚNG `TRACKED_ENV` (biến chưa đặt ⇒ giá trị `None`). Không đọc lại
    `os.environ` bên trong accessor: mọi quyết định parse dựa trên ảnh chụp này, nên một
    lượt đọc env không thể bị "xé" giữa hai biến.
    """

    raw: Mapping[str, Optional[str]] = field(repr=False)

    # ------------------------------------------------------------- đọc thô
    def text(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """`os.getenv(name, default)` — KHÔNG strip (giữ nguyên site cũ)."""
        value = self.raw[name]
        return default if value is None else value

    def text_or(self, name: str, default: str) -> str:
        """`os.getenv(name) or default` — chuỗi rỗng cũng rơi về default."""
        return self.raw[name] or default

    def text_strip_or(self, name: str, default: str) -> str:
        """`os.getenv(name, default).strip() or default` (EVIDENCE_RERANKER)."""
        return self.text(name, default).strip() or default

    # ------------------------------------------------------------- cờ
    def _flag(self, name: str, default: str = "0") -> bool:
        """Ngữ nghĩa `in _ON_VALUES` (contextual_header): giá trị lạ ⇒ TẮT."""
        return self.text(name, default).strip().lower() in _ON_VALUES

    def _env_flag(self, name: str, default: str = "0") -> bool:
        """Ngữ nghĩa `not in _OFF_VALUES` (evidence/refusal/OCR): giá trị lạ ⇒ BẬT."""
        return self.text(name, default).strip().lower() not in _OFF_VALUES

    # ------------------------------------------------------------- số
    def _env_int(self, name: str, default: int, *, minimum: int = 1) -> int:
        """Rỗng/sai định dạng/dưới `minimum` ⇒ default (evidence: minimum=1, refusal: 0)."""
        raw = self.text(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value >= minimum else default

    def _env_float(
        self,
        name: str,
        default: float,
        *,
        lo: Optional[float] = None,
        hi: Optional[float] = None,
        gt: Optional[float] = None,
    ) -> float:
        """Rỗng/sai định dạng/ngoài khoảng ⇒ default.

        - refusal: `lo=0.0, hi=1.0` (đúng `0.0 <= value <= 1.0` cũ).
        - classifier: `gt=0.0` (đúng `timeout > 0` cũ).
        - local_slm: không bound (đúng `_env_float` cũ, nhận mọi số float được).
        """
        raw = self.text(name, "").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            return default
        if (lo is not None or hi is not None or gt is not None) and value != value:
            return default  # NaN: mọi so sánh khoảng cũ đều False ⇒ rơi về default
        if gt is not None and value <= gt:
            return default
        if lo is not None and value < lo:
            return default
        if hi is not None and value > hi:
            return default
        return value

    def int_required(self, name: str, default: int) -> int:
        """`int(os.getenv(name, default))` — GIỮ hành vi ném `ValueError` khi env hỏng."""
        return int(self.text(name, str(default)))

    def float_required(self, name: str, default: float) -> float:
        """`float(os.getenv(name, str(default)))` — GIỮ hành vi ném `ValueError` khi hỏng."""
        return float(self.text(name, str(default)))


#: Ảnh chụp gần nhất: `(snapshot, Settings)`. Gán tuple là thao tác nguyên tử trong
#: CPython; hai luồng đua nhau chỉ dựng thừa một Settings (vô hại), không trả giá trị sai.
_CACHE: Optional[tuple[tuple[tuple[str, Optional[str]], ...], Settings]] = None


def settings() -> Settings:
    """Settings cho ảnh chụp env HIỆN TẠI (đọc một lượt `TRACKED_ENV`, cache theo snapshot)."""
    global _CACHE
    snapshot = tuple((name, os.environ.get(name)) for name in TRACKED_ENV)
    cached = _CACHE
    if cached is not None and cached[0] == snapshot:
        return cached[1]
    current = Settings(raw=MappingProxyType(dict(snapshot)))
    _CACHE = (snapshot, current)
    return current


def top_k_from_env() -> int:
    """`RAG_TOP_K` cho `main`/`router` — giữ đúng ngữ nghĩa router cũ.

    Không đặt / rỗng / không phải số / ≤ 0 ⇒ `DEFAULT_TOP_K` (6). Ở mọi nơi khác,
    `DEFAULT_TOP_K` là mặc định của tham số; entry point vẫn override được qua
    `--top-k`/tham số như trước — review §3 chỉ gom *mặc định*, không đổi quyền ưu tiên.
    """
    return settings()._env_int("RAG_TOP_K", DEFAULT_TOP_K)
