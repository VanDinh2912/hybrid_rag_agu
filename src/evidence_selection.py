"""T3 — đòn bẩy 3: `ENABLE_EVIDENCE_SELECTION` (extract-then-generate).

Vì sao tồn tại: số đo T1 (`docs/reports/T1.md`) cho thấy refusal của Qwen 2.5:1.5B TĂNG
đơn điệu khi cửa sổ sinh GIẢM (0,675 ở ~7k ký tự → 0,8625 ở 0,9–1,4k → 0,95 ở 150–300 ký
tự). Nghĩa là độ dư ngữ cảnh là hiệu ứng thật: model nhỏ lạc trong 8k ký tự và chọn đường
"an toàn". Đòn bẩy này không thêm thông tin mới — nó BỚT thông tin thừa: thay cửa sổ chunk
bằng 3–5 CÂU bằng chứng, vẫn giữ `chunk_id`/`source`/`tier` của chunk gốc nên trích dẫn và
hậu kiểm không đổi chỗ dựa.

Luật chọn câu (đăng ký trước, `data/loop/README.md` mục T3):
1. câu chứa THỰC THỂ phía câu hỏi (số, mã văn bản, ngày, tên riêng) — tier 3, mạnh nhất;
2. câu chia sẻ >= `EV_MIN_KEYWORD_HITS` TỪ KHÓA phía câu hỏi — tier 2;
3. câu trùng tên văn bản mà router gọi, hoặc chỉ có MỘT từ khóa — tier 1;
4. trong cùng tier, xếp theo điểm reranker (cross-encoder nếu tải được, nếu không thì
   bi-encoder dùng lại model nhúng đang chạy, và round phải GHI rõ đã dùng kind nào).

Cửa sổ mới lấy tối đa `EV_MAX_SENTENCES` câu; ưu tiên lấy từ nhóm tier >= 2. Nếu nhóm này
dưới `EV_MIN_SENTENCES` thì NỚI một bậc (tier >= 1) — vì với câu hỏi không có thực thể
("Sinh viên học lại tối đa bao nhiêu lần?"), tier 3 trống trơn và đòn bẩy sẽ không bao giờ
chạy; vẫn phải giữ nguyên window gốc (không tự chế thêm văn bản) khi nới rồi mà chưa đủ
`EV_MIN_SENTENCES` câu.

Không đủ `EV_MIN_SENTENCES` câu đạt chuẩn (tier >= 1) ⇒ GIỮ NGUYÊN cửa sổ gốc — module
không tự chế thêm văn bản và cũng không được vì ít câu mà cắt căn cứ của câu hỏi khó.

CHỐNG RÒ ĐÁP ÁN: "thực thể" lấy từ phía CÂU HỎI và từ tên nguồn router đưa ra; các trường
`gold_sentence`/`required_entities`/`primary_entity`/`gold_chunk_id` của testset không được
đọc ở đây (bất biến #6 của vòng lặp).

Luật chia câu PHẢI trùng luật mà testset dùng để tạo `gold_sentence`
(`tools/loop/testset.py::sentence_split` — tách sau `. ; :`, bỏ câu < 25 ký tự), nếu không
thì "câu bằng chứng" của module và "câu vàng" của trọng tài là hai đơn vị khác nhau và phép
đo mất nghĩa.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

from src.config import settings
from src.refusal_policy import query_entities
from src.text_utils import fold

DEFAULT_MIN_SENTENCES = 3
DEFAULT_MAX_SENTENCES = 5
DEFAULT_RERANKER = "bge-reranker-base"
FALLBACK_EMBEDDING_MODEL = "BAAI/bge-m3"

MIN_SENTENCE_CHARS = 25  # đúng ngưỡng của tools/loop/testset.py::sentence_split

SENTENCE_SPLIT = re.compile(r"(?<=[\.;:])\s+")
_TOKEN = re.compile(r"\w+", flags=re.UNICODE)


def evidence_selection_enabled() -> bool:
    """Cờ bật chọn câu bằng chứng. Mặc định TẮT (tắt = đưa nguyên cửa sổ chunk như cũ)."""
    return settings()._env_flag("ENABLE_EVIDENCE_SELECTION", "0")


def sentence_budget() -> tuple[int, int]:
    """(min, max) số câu; max luôn >= min kể cả khi env vô lý (kẹp về mặc định đã đăng ký)."""
    cfg = settings()
    lo = cfg._env_int("EV_MIN_SENTENCES", DEFAULT_MIN_SENTENCES, minimum=1)
    hi = cfg._env_int("EV_MAX_SENTENCES", DEFAULT_MAX_SENTENCES, minimum=1)
    if hi < lo:
        lo, hi = DEFAULT_MIN_SENTENCES, DEFAULT_MAX_SENTENCES
    return lo, hi


def split_sentences(text: str) -> list[str]:
    """Chia câu ĐÚNG LUẬT của testset — xem docstring module."""
    parts = SENTENCE_SPLIT.split(text or "")
    return [p.strip() for p in parts if p and len(p.strip()) >= MIN_SENTENCE_CHARS]


def source_name_keys(source_names: Iterable[str]) -> set[str]:
    """Token nhận diện tên văn bản mà router gọi tên (fold, đủ dài để không khớp loạn).

    `fold` GIỮ dấu gạch nối ("quy-che-dao-tai-1054-qd-dhag-2020-09-29.pdf"), nên cắt theo
    `\\w+` sẽ vỡ thành 'quy','che','dao','tai' (3 ký tự — quá mòn, cái gì cũng khớp). Vì vậy
    lấy cả hai lớp: token định danh (>=5 ký tự hoặc chuỗi số như '2021', '1054', 'con915')
    và cả tên đã bỏ phần mở rộng.
    """
    keys: set[str] = set()
    for name in source_names or []:
        folded = fold(str(name or ""))
        stem = re.sub(r"\.(pdf|docx?|xlsx?|txt)$", "", folded, flags=re.I)
        if len(stem) >= 5:
            keys.add(stem)
        for token in _TOKEN.findall(folded):
            if len(token) >= 5 or (token.isdigit() and len(token) >= 4):
                keys.add(token)
    keys.discard("")
    return keys


# ------------------------------------------------------------------ từ khóa phía câu hỏi
# `refusal_policy.content_tokens` dùng danh sách hư từ khá rộng (đúng cho luật "chunk này
# có trả lời được câu hỏi không"), nhưng để XẾP HẠNG TỪNG CÂU thì nó quá chặt: đo trên
# fixture, câu hỏi "Sinh viên học lại tối đa bao nhiêu lần mỗi học phần?" chỉ còn MỘT token
# ('phan') ⇒ mọi câu đều tier 0 và đòn bẩy vĩnh viễn không chạy. Danh sách dưới đây là hư
# từ thuần chức năng, giữ lại danh từ chung ('hoc', 'sin', 'viê'...).
_FUNCTION_WORDS_FOLDED = {
    "va", "hoac", "la", "hay", "cua", "cho", "voi", "tu", "den", "theo", "trong", "ngoai",
    "co", "khong", "duoc", "bi", "duoc", "thi", "ma", "nu", "ay", "do", "day", "kia",
    "nay", "no", "anh", "em", "ban", "minh", "chung", "bao", "nhieu", "muc", "dinh",
    "lam", "lai", "da", "dang", "se", "moi", "mua", "nam", "nau", "tinh", "truoc", "sau",
    "gio", "bay", "toi", "ve", "phia", "khuon", "kho", "gioi", "han", "the", "nao", "gi",
    "may", "song", "cung", "ken", "nhung", "cac", "mot", "hai", "ba", "bon", "nam", "sau",
    "bay", "tam", "chin", "muoi", "lan", "luot", "chiec", "ca", "con", "cau", "hoi",
}


def question_terms(question: str) -> set[str]:
    """Từ khóa phía CÂU HỎI: fold, dài >=3, bỏ hư từ chức năng. Không đụng đáp án."""
    tokens = _TOKEN.findall(fold(question or ""))
    return {t for t in tokens if len(t) >= 3 and t not in _FUNCTION_WORDS_FOLDED}


MIN_KEYWORD_HITS_DEFAULT = 2


def min_keyword_hits() -> int:
    return settings()._env_int("EV_MIN_KEYWORD_HITS", MIN_KEYWORD_HITS_DEFAULT, minimum=1)


TIER_ENTITY = 3
TIER_KEYWORDS = 2
TIER_SOURCE_NAME = 1
TIER_NONE = 0


@dataclass
class Candidate:
    """Một câu ứng viên kèm xuất xứ và các tín hiệu đã tính (để hậu kiểm, không log dài)."""

    sentence: str
    doc_index: int
    sent_index: int
    tier: int
    score: float = 0.0
    keyword_hits: int = 0
    entity_hits: int = 0

    @property
    def sort_key(self) -> tuple:
        # tier cao trước; cùng tier thì điểm cao trước; vẫn bằng nhau thì theo thứ tự
        # gốc (chunk hạng nhất, câu đứng trước) — quyết định PHẢI tái lập được.
        return (-self.tier, -round(self.score, 4), self.doc_index, self.sent_index)


@dataclass
class Reranker:
    """Hàm xếp hạng câu theo câu hỏi. `kind` được ghi vào manifest của round."""

    kind: str  # "cross_encoder" | "bi_encoder" | "none"
    model_name: str = ""
    _model: Any = None
    _notes: list[str] = field(default_factory=list)

    def scores(self, question: str, sentences: Sequence[str]) -> list[float]:
        if not sentences:
            return []
        if self.kind == "cross_encoder":
            try:
                raw = self._model.predict([(question, s) for s in sentences])
                return [float(x) for x in raw]
            except Exception as exc:  # noqa: BLE001
                self._notes.append(f"cross_encoder lỗi ({type(exc).__name__})")
                return [0.0] * len(sentences)
        if self.kind == "bi_encoder":
            try:
                qv = self._embed([question])[0]
                vs = self._embed(list(sentences))
                return [round(_cosine(qv, v), 4) for v in vs]
            except Exception as exc:  # noqa: BLE001
                self._notes.append(f"bi_encoder lỗi ({type(exc).__name__})")
                return [0.0] * len(sentences)
        return [0.0] * len(sentences)

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._model
        if hasattr(model, "embed_documents"):  # LangChain embedding function (đang chạy thật)
            return list(model.embed_documents(list(texts)))
        if hasattr(model, "encode"):  # SentenceTransformer trực tiếp
            return [list(v) for v in model.encode(list(texts))]
        raise AttributeError("reranker bi-encoder không có API nhúng nào")


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


_RERANKER: Optional[Reranker] = None


def get_reranker(embeddings: Any = None, *, force_reload: bool = False) -> Reranker:
    """Tải reranker MỘT lần cho cả process (model vài GB — không được tải lại mỗi câu).

    Thứ tự ưu tiên đã đăng ký: cross-encoder `EVIDENCE_RERANKER`; nếu môi trường không tải
    được (thiếu weight, không mạng) thì lùi về bi-encoder. `embeddings` là hàm nhúng mà
    pipeline ĐANG dùng (bge-m3) — dùng lại nó để không nhân đôi RAM/VRAM trên máy 4GB.
    Không có gì cả ⇒ kind "none": xếp hạng chỉ theo tier 1-2, vẫn deterministic.
    """
    global _RERANKER
    if _RERANKER is not None and not force_reload:
        return _RERANKER
    requested = settings().text_strip_or("EVIDENCE_RERANKER", DEFAULT_RERANKER)
    notes: list[str] = []
    try:
        from sentence_transformers import CrossEncoder  # import trễ: chỉ khi cờ BẬT

        model = CrossEncoder(requested)
        _RERANKER = Reranker("cross_encoder", requested, model, notes)
        print(f"[EvidenceSelection] Reranker = cross-encoder {requested}.")
        return _RERANKER
    except Exception as exc:  # noqa: BLE001
        notes.append(f"cross-encoder {requested} không tải được ({type(exc).__name__})")
    if embeddings is not None:
        _RERANKER = Reranker("bi_encoder", FALLBACK_EMBEDDING_MODEL, embeddings, notes)
        print(
            f"[EvidenceSelection] Reranker = bi-encoder {FALLBACK_EMBEDDING_MODEL} "
            "(dùng lại hàm nhúng của pipeline) — KHÔNG phải cross-encoder."
        )
        return _RERANKER
    notes.append("không có hàm nhúng để lùi về bi-encoder")
    _RERANKER = Reranker("none", "", None, notes)
    print("[EvidenceSelection] Reranker = none — chỉ xếp theo thực thể/tên nguồn.")
    return _RERANKER


def reranker_status() -> dict[str, Any]:
    """Trạng thái reranker để manifest ghi lại (đăng ký: round phải GHI rõ dùng kind nào)."""
    requested = settings().text_strip_or("EVIDENCE_RERANKER", DEFAULT_RERANKER)
    if _RERANKER is None:
        return {"requested": requested, "kind": "chưa_chạy", "notes": []}
    return {
        "requested": requested,
        "kind": _RERANKER.kind,
        "model": _RERANKER.model_name,
        "notes": list(_RERANKER._notes),
    }


def rank_candidates(
    question: str,
    docs: Sequence[Any],
    source_names: Sequence[str] = (),
    *,
    reranker: Optional[Reranker] = None,
) -> list[Candidate]:
    """Chấm điểm từng câu trong cửa sổ; KHÔNG cắt gì ở bước này.

    Bậc thang đã đăng ký (README mục T3, dòng 'EV_*'): thực thể phía câu hỏi > từ khóa phía
    câu hỏi (>= `EV_MIN_KEYWORD_HITS`, mặc định 2) > token tên nguồn mà router gọi > không gì
    hết. Cùng bậc thì reranker quyết; reranker lỗi/không có ⇒ 0.0 đều nhau, thứ tự gốc quyết
    (chunk hạng cao hơn, câu đứng trước).
    """
    keys = set(query_entities(question))
    terms = question_terms(question)
    name_keys = source_name_keys(source_names)
    need_terms = min_keyword_hits()
    ranker = reranker or Reranker("none")
    candidates: list[Candidate] = []
    for di, doc in enumerate(docs):
        content = getattr(doc, "page_content", None)
        if content is None:
            content = str(doc or "")
        sentences = split_sentences(content)
        if not sentences:
            continue
        scores = ranker.scores(question, sentences)
        for si, sentence in enumerate(sentences):
            hay = fold(sentence)
            entity_hits = sum(1 for k in keys if k and k in hay)
            keyword_hits = sum(1 for t in terms if t in hay)
            source_hit = any(k and k in hay for k in name_keys)
            if entity_hits:
                tier = TIER_ENTITY
            elif keyword_hits >= need_terms:
                tier = TIER_KEYWORDS
            elif source_hit or keyword_hits >= 1:
                tier = TIER_SOURCE_NAME
            else:
                tier = TIER_NONE
            candidates.append(
                Candidate(
                    sentence=sentence,
                    doc_index=di,
                    sent_index=si,
                    tier=tier,
                    score=float(scores[si]) if si < len(scores) else 0.0,
                    keyword_hits=keyword_hits,
                    entity_hits=entity_hits,
                )
            )
    candidates.sort(key=lambda c: c.sort_key)
    return candidates


def build_evidence_window(question: str, docs: Sequence[Any], chosen: Sequence[Candidate]) -> list[Any]:
    """Ghép câu đã chọn thành cửa sổ mới, theo thứ tự chunk gốc, metadata nguyên vẹn.

    Metadata được sao nên `chunk_id`/`source`/`tier` vẫn đúng — tầng trích dẫn
    (`inject_citations_from_metadata`) và hậu kiểm căn cứ không bị mất chỗ dựa.
    """
    by_doc: dict[int, list[Candidate]] = {}
    for cand in chosen:
        by_doc.setdefault(cand.doc_index, []).append(cand)
    out: list[Any] = []
    for di in sorted(by_doc):
        kept = sorted(by_doc[di], key=lambda c: c.sent_index)  # giữ mạch đọc của chunk
        new_doc = copy_like(docs[di], " ".join(c.sentence for c in kept))
        out.append(new_doc)
    return out


def copy_like(doc: Any, new_content: str) -> Any:
    """Bản sao Document/LangChain-compatible với `page_content` mới, metadata giữ nguyên."""
    try:
        from langchain_core.documents import Document

        metadata = dict(getattr(doc, "metadata", None) or {})
        return Document(page_content=new_content, metadata=metadata)
    except Exception:  # noqa: BLE001 - đồ vật giả trong test cũng phải đi được đường này
        class _Shallow:
            pass

        clone = _Shallow()
        clone.page_content = new_content
        clone.metadata = dict(getattr(doc, "metadata", None) or {})
        return clone


def select_evidence(
    question: str,
    docs: Sequence[Any],
    *,
    source_names: Sequence[str] = (),
    embeddings: Any = None,
    log=print,
) -> tuple[list[Any], dict[str, Any]]:
    """Cửa sổ generator ⇒ (docs mới hoặc gốc, thông tin quyết định để log/manifest).

    Trả về cửa sổ GỐC khi không đủ `EV_MIN_SENTENCES` câu đạt chuẩn — hành vi khi đó giống
    hệt trước đòn bẩy và `info["applied"] = False` nói rõ vì sao.
    """
    lo, hi = sentence_budget()
    reranker = get_reranker(embeddings)
    candidates = rank_candidates(question, docs, source_names, reranker=reranker)
    strong = [c for c in candidates if c.tier >= TIER_KEYWORDS]
    relaxed = [c for c in candidates if c.tier >= TIER_SOURCE_NAME]
    qualifying, relaxed_used = (strong, False) if len(strong) >= lo else (relaxed, True)
    info: dict[str, Any] = {
        "applied": False,
        "min_sentences": lo,
        "max_sentences": hi,
        "n_candidates": len(candidates),
        "n_strong": len(strong),
        "n_relaxed": len(relaxed),
        "reranker_kind": reranker.kind,
        "chars_before": sum(len(getattr(d, "page_content", "") or "") for d in docs),
    }
    if len(qualifying) < lo:
        info["reason"] = "not_enough_qualifying_sentences"
        log(
            f"[EvidenceSelection] Giữ nguyên cửa sổ: chỉ {len(qualifying)}/{lo} câu đạt chuẩn "
            f"(mạnh={len(strong)}, nới lỏng={len(relaxed)}, reranker={reranker.kind})."
        )
        return list(docs), info

    chosen = qualifying[:hi]
    window = build_evidence_window(question, docs, chosen)
    info.update(
        {
            "applied": True,
            "relaxed_to_source_name": relaxed_used,
            "n_sentences": len(chosen),
            "chars_after": sum(len(getattr(d, "page_content", "") or "") for d in window),
            "top_tiers": sorted({c.tier for c in chosen}, reverse=True),
        }
    )
    log(
        f"[EvidenceSelection] Cửa sổ còn {info['n_sentences']} câu "
        f"({info['chars_before']} → {info['chars_after']} ký tự, "
        f"nới_lỏng={int(relaxed_used)}, reranker={reranker.kind})."
    )
    return window, info
