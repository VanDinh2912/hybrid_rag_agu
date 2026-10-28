"""Module gộp luồng Hybrid RAG (Local SLM phối hợp Gemini API).

Luồng xử lý (True Hybrid Search):
1. Nhận câu hỏi thô của sinh viên.
2. Local SLM (Qwen/Ollama) chuẩn hóa câu hỏi thành văn phong học vụ.
3. Bỏ dấu thanh câu chuẩn hóa (fold) rồi truy vấn kết hợp (True Hybrid Search):
   - BM25 Retriever: tìm kiếm từ khóa chính xác (Điều, Khoản, thuật ngữ viết tắt).
   - ChromaDB Retriever (bge-m3): tìm kiếm ngữ nghĩa theo vector tương đồng.
   - EnsembleRetriever (RRF - Reciprocal Rank Fusion): gộp và xếp hạng lại tài liệu.
4. Gemini API sinh câu trả lời cuối cùng dựa trên ngữ cảnh đã truy xuất.

Chiến lược oversampling (retrieve_k ≥ top_k):
- Bộ truy xuất trả về `retrieve_k` ứng viên để tính Hit@K chính xác trong evaluation
  (recall window rộng hơn cửa sổ ngữ cảnh generator).
- Chỉ `top_k` chunk đứng đầu (theo RRF ranking) được đưa vào generator —
  giữ nguyên chất lượng câu trả lời, không mở rộng context window không cần thiết.
- `sources` trả về TOÀN BỘ retrieve_k chunk để evaluation đo Hit@retrieve_k,
  `gen_docs` chỉ là top_k đầu để generator dùng.

Tương thích ngược:
- Nếu use_hybrid=False hoặc ChromaDB không hỗ trợ BM25, pipeline tự động lùi về
  `vector_db.similarity_search` thuần vector ban đầu.
"""

import os
from dataclasses import asdict
from typing import Any, Optional

from langchain_core.documents import Document

from src.core.classifier import classify_query
from src.core.config import settings
from src.generation.evidence_selection import evidence_selection_enabled, select_evidence
from src.core.query_normalizer import normalize_user_query
from src.generation.refusal_policy import (
    decoupled_refusal_enabled,
    decide_post_generation,
    decide_pre_generation,
    log_decision,
)
from src.retrieval.retrieval import SYNONYM_DICTIONARY, expand_query_with_synonyms, split_comparison_query
from src.retrieval.reranker import (
    RerankerUnavailable,
    last_call,
    reranker_candidate_pool,
    reranker_enabled,
    reranker_fallback_enabled,
    reranker_keep_candidates,
    rerank_documents,
)
from src.retrieval.router import (
    RetrievalConfig,
    apply_source_quota,
    base_config_from_env,
    get_retrieval_config,
    rescore_with_source_preference,
    router_filter_rank_bonus,
    router_source_quota,
    router_soft_filter_enabled,
)
from src.text_utils import fold
from src.retrieval.vector_db import (
    DEFAULT_BM25_WEIGHT,
    DEFAULT_VECTOR_WEIGHT,
    DEFAULT_RRF_C,
    extract_documents_from_chroma,
    bm25_tokenize,
)

try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:
    try:
        from langchain_classic.retrievers.ensemble import EnsembleRetriever
    except ImportError:
        from langchain_community.retrievers import EnsembleRetriever

from langchain_community.retrievers import BM25Retriever

DEFAULT_OVERSAMPLE_FACTOR = 2


def dense_original_query_enabled() -> bool:
    """V1/PA-48a: chỉ nhánh dense (Chroma) nhận query NGUYÊN VĂN; BM25 vẫn `fold`.

    Cờ TẮT (mặc định) giữ nguyên đường cũ — đúng một lời gọi `ensemble.invoke(fold(query))`
    cho cả hai nhánh, nên byte đầu ra không đổi và khóa cache sinh không bị ảnh hưởng
    (cờ này không nằm trong `cache_policy`).
    """
    return settings()._flag("ENABLE_DENSE_ORIGINAL_QUERY", "0")


def _preview(text: str, limit: int = 160) -> str:
    """Một dòng xem trước của chunk, dùng khi liệt kê nguồn trích dẫn."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def describe_document(doc: Any, index: int) -> dict:
    """Trích metadata của một chunk LangChain Document thành dict hiển thị được."""
    metadata = getattr(doc, "metadata", None) or {}
    content = getattr(doc, "page_content", "") or ""
    return {
        "rank": index + 1,
        "source": str(metadata.get("source") or "không rõ nguồn"),
        "tier": str(metadata.get("tier") or "Khác"),
        "chunk_id": metadata.get("chunk_id", index),
        "preview": _preview(content),
        "chars": len(content),
    }


class HybridRAGPipeline:
    """Điều phối toàn bộ luồng True Hybrid RAG."""

    def __init__(
        self,
        vector_db: Any,
        local_slm: Any,
        generator: Any,
        oversample_factor: int = DEFAULT_OVERSAMPLE_FACTOR,
        use_hybrid: bool = True,
        bm25_weight: float = DEFAULT_BM25_WEIGHT,
        vector_weight: float = DEFAULT_VECTOR_WEIGHT,
        retriever: Optional[Any] = None,
        expand_query: bool = True,
    ):
        self.vector_db = vector_db
        self.local_slm = local_slm
        self.generator = generator
        self.oversample_factor = max(1, int(oversample_factor))
        self.use_hybrid = use_hybrid and os.getenv("ENABLE_HYBRID_SEARCH", "1").lower() not in {"0", "false", "no"}
        self.bm25_weight = float(os.getenv("BM25_WEIGHT", str(bm25_weight)))
        self.vector_weight = float(os.getenv("CHROMA_WEIGHT", str(vector_weight)))
        self.expand_query = expand_query and os.getenv("ENABLE_QUERY_EXPANSION", "1").lower() not in {"0", "false", "no"}
        # Tầng phân loại + router (P3.2): chỉ bật khi ENABLE_CLASSIFIER=1; tắt thì
        # đường chạy giữ nguyên y như trước (không gọi classifier, không đổi cấu hình).
        self.enable_classifier = os.getenv("ENABLE_CLASSIFIER", "0").strip().lower() not in {"0", "false", "no"}

        # Nếu người dùng truyền thẳng retriever tùy chỉnh vào
        self.custom_retriever = retriever

        # T3: hạng THÔ của từng chunk trong từng nhánh (BM25, vector) của lượt truy xuất
        # gần nhất. CHỈ được điền khi `ENABLE_DECOUPLED_REFUSAL=1`; cờ TẮT thì thuộc tính
        # này luôn None và không code T3 nào chạy (bất biến #2).
        self.last_leg_ranks: Optional[dict] = None

        # T5a: số liệu lượt rerank gần nhất (đếm ứng viên, giây, điểm cao/thấp nhất).
        # Cờ `ENABLE_RERANKER` TẮT thì thuộc tính này luôn None.
        self.last_rerank_call: Optional[dict] = None

        # Khởi tạo EnsembleRetriever (BM25 + Chroma) nếu được bật
        self.ensemble_retriever: Optional[Any] = None
        if self.custom_retriever is not None:
            self.ensemble_retriever = self.custom_retriever
        elif self.use_hybrid:
            self._init_hybrid_retriever()

    def _init_hybrid_retriever(self) -> None:
        """Tự động thiết lập BM25 và kết hợp với ChromaDB qua EnsembleRetriever (RRF)."""
        try:
            # Nếu vector_db vốn đã là một retriever có phương thức invoke
            if hasattr(self.vector_db, "invoke") and not hasattr(self.vector_db, "get"):
                self.ensemble_retriever = self.vector_db
                return

            if not hasattr(self.vector_db, "get"):
                return

            docs = extract_documents_from_chroma(self.vector_db)
            if not docs:
                return

            bm25 = BM25Retriever.from_documents(docs, preprocess_func=bm25_tokenize)
            bm25.k = 12  # Oversampling: truy xuất 12 ứng viên để tăng Recall/Hit@K

            chroma_ret = self.vector_db.as_retriever(search_kwargs={"k": 12})  # Đồng bộ với BM25

            weights = [self.bm25_weight, self.vector_weight]
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[bm25, chroma_ret],
                weights=weights,
                c=DEFAULT_RRF_C,
                id_key="chunk_id",
            )
            print(
                f"[HybridSearch] Đã kích hoạt True Hybrid Search (BM25={weights[0]:.2f} + Chroma={weights[1]:.2f}, c={DEFAULT_RRF_C})."
            )
        except Exception as exc:
            print(f"[HybridSearch] Cảnh báo: không thể khởi tạo BM25 ({exc}) — tự động lùi về Chroma vector search.")
            self.ensemble_retriever = None

    # ------------------------------------------------------------------ T3: đo hạng từng nhánh
    def _collect_leg_ranks(
        self, folded_query: str, dense_query: Optional[str] = None
    ) -> None:
        """Lấy hạng THÔ của từng chunk trong TỪNG nhánh (BM25, vector) — chỉ cho luật 3.

        Vì sao phải đo riêng: `EnsembleRetriever` trả về danh sách ĐÃ trộn theo RRF nên
        thứ hạng sau fusion không còn cho biết chunk đó đứng đâu trong từng nhánh — mà
        "điểm truy xuất" theo định nghĩa đã đăng ký (`DEC_MIN_RRF_NORM`) là hàm của hai
        hạng thô đó. Gọi lại từng nhánh là thao tác ĐỌC: `docs` trả về cho tầng sinh vẫn
        do đúng một lần `ensemble_retriever.invoke(...)` sinh ra, nên bật cờ không đổi
        đầu vào của generator. Giá phải trả là chi phí đo (thêm một lượt nhúng + một lượt
        BM25 mỗi câu) — tính vào p95 latency của r8 và ghi rõ trong báo cáo.
        """
        ranks = dict(self.last_leg_ranks or {})
        legs = list(getattr(self.ensemble_retriever, "retrievers", []) or [])
        if len(legs) != 2:
            # Không đoán mò thứ tự nhánh: không đo được thì ghi nhận không đo được
            # (quyết định đã đăng ký — `rrf_unavailable`, KHÔNG âm thầm coi là đạt).
            self.last_leg_ranks = ranks or None
            return
        for pos, leg in enumerate(legs):  # 0 = BM25, 1 = Chroma (đúng thứ tự weights)
            # V1/PA-48a: khi cờ bật, nhánh dense phải đo bằng ĐÚNG query mà nó nhận
            # lúc truy xuất (nguyên văn); BM25 vẫn đo bằng `fold` như trước.
            leg_query = dense_query if (pos == 1 and dense_query is not None) else folded_query
            try:
                hits = leg.invoke(leg_query)
            except Exception as exc:  # noqa: BLE001
                print(
                    "[DecoupledRefusal] Cảnh báo: không đo được hạng nhánh "
                    f"{pos} ({type(exc).__name__}: {exc}) — luật 3 bỏ qua lượt này."
                )
                continue
            for i, doc in enumerate(hits or [], start=1):
                cid = str((getattr(doc, "metadata", None) or {}).get("chunk_id"))
                pair = list(ranks.get(cid, [None, None]))
                if pair[pos] is None:
                    pair[pos] = i
                    ranks[cid] = (pair[0], pair[1])
        self.last_leg_ranks = ranks or None

    def _aligned_leg_ranks(self, docs: list) -> Optional[list]:
        """Ánh danh sách chunk cửa sổ generator sang `(rank_bm25, rank_vector)`.

        Chunk không có mặt ở cả hai lượt đo (vd. chỉ vào được nhờ fallback query) thành
        None — `decide_pre_generation` xử lý bằng `rrf_unavailable`, không coi là đạt.
        """
        if not self.last_leg_ranks:
            return None
        aligned = []
        for doc in docs:
            cid = str((getattr(doc, "metadata", None) or {}).get("chunk_id"))
            aligned.append(self.last_leg_ranks.get(cid))
        return aligned

    def _fusion_weights(self, config: Optional[RetrievalConfig]) -> tuple:
        """Trọng số RRF thực sự dùng cho lượt này (router ghi đè theo câu, P3.2)."""
        if config is not None:
            return float(config.bm25_weight), float(config.chroma_weight)
        return float(self.bm25_weight), float(self.vector_weight)

    def _invoke_hybrid(self, query: str) -> list[Document]:
        """Một lượt truy xuất hybrid — giữ đúng công thức RRF của `EnsembleRetriever`.

        Cờ `ENABLE_DENSE_ORIGINAL_QUERY` TẮT (mặc định): đúng một lời gọi
        `invoke(fold(query))` như trước — đường cũ từng byte.

        Cờ BẬT (V1/PA-48a): hai nhánh được gọi riêng để **chỉ dense** nhận query
        nguyên văn — BM25 nhận `fold(query)` vì chỉ mục BM25 đã nhân đôi token
        có/không dấu, còn bge-m3 nhận nguyên văn vì index cũ vẫn còn từ có dấu. Hợp
        nhất bằng chính `weighted_reciprocal_rank` của ensemble (cùng `weights`, `c`,
        `id_key`, cùng thứ tự nhánh) nên không đổi công thức RRF. Nếu ensemble không
        có đúng 2 nhánh hoặc không phải `EnsembleRetriever` thật (retriever tùy biến),
        lùi về đường cũ thay vì đoán thứ tự nhánh.
        """
        if not dense_original_query_enabled():
            return self.ensemble_retriever.invoke(fold(query))
        legs = list(getattr(self.ensemble_retriever, "retrievers", []) or [])
        fuse = getattr(self.ensemble_retriever, "weighted_reciprocal_rank", None)
        if len(legs) != 2 or fuse is None:
            return self.ensemble_retriever.invoke(fold(query))
        bm25_docs = legs[0].invoke(fold(query))
        dense_docs = legs[1].invoke(query)
        return fuse([bm25_docs, dense_docs])

    def retrieve(
        self,
        query: str,
        k: int = 6,
        fallback_query: Optional[str] = None,
        config: Optional[RetrievalConfig] = None,
    ) -> list[Document]:
        """Truy xuất tài liệu: True Hybrid Search (BM25 + Vector RRF) hoặc Vector Search thuần túy.

        Với oversampling, trả về đúng k chunks tốt nhất (Best-First Search / Beam Filter).
        Đảm bảo trả về danh sách Document giữ nguyên vẹn metadata (chunk_id, source, tier).

        Args:
            query: Câu hỏi truy xuất chính (thường là normalized_query)
            k: Số chunk cần trả về
            fallback_query: Câu hỏi dự phòng (thường là original_user_query) để chạy song song
            config: Cấu hình từ router (P3.2), None = đường cũ (không điều chỉnh gì).
                    Khi có: áp trọng số BM25/Chroma per-query (EnsembleRetriever đọc
                    `weights` lúc invoke nên gán thuộc tính là đủ), áp filter metadata
                    `source` cho nhánh Chroma và lọc hậu kiểm cho toàn bộ kết quả
                    (nhánh BM25 không hỗ trợ filter — lọc theo metadata sau merge).
        """
        k = max(1, int(k))

        # 1. Trường hợp sử dụng True Hybrid Search (EnsembleRetriever)
        if self.use_hybrid and self.ensemble_retriever is not None:
            try:
                # Trọng số RRF per-query của router (P3.2). EnsembleRetriever dùng
                # `self.weights` ngay lúc rank_fusion nên đổi thuộc tính trước invoke
                # là áp được theo từng câu hỏi, không cần dựng lại retriever.
                if hasattr(self.ensemble_retriever, "weights"):
                    if config is not None:
                        self.ensemble_retriever.weights = [
                            config.bm25_weight,
                            config.chroma_weight,
                        ]
                    else:
                        # Đường cũ (hoặc phục hồi sau một lượt có classifier): trả về
                        # đúng trọng số khởi tạo từ env như trước P3.2.
                        self.ensemble_retriever.weights = [
                            self.bm25_weight,
                            self.vector_weight,
                        ]

                # Đồng bộ tham số k cho các sub-retrievers bên trong
                sub_retrievers = getattr(self.ensemble_retriever, "retrievers", [])
                soft_filter = bool(
                    config is not None
                    and config.source_filter
                    and router_soft_filter_enabled()
                )
                # T5a: khi bật reranker, mỗi nhánh phải QUÉT SÂU hơn cửa sổ để pool 20
                # ứng viên tồn tại thật. Cờ TẮT -> leg_k == k -> từng ký tự như cũ.
                leg_k = max(k, reranker_candidate_pool()) if reranker_enabled() else k
                for r in sub_retrievers:
                    if hasattr(r, "k"):
                        r.k = leg_k
                    elif hasattr(r, "search_kwargs") and isinstance(r.search_kwargs, dict):
                        r.search_kwargs["k"] = leg_k
                        # Filter metadata `source` cho nhánh Chroma (API hỗ trợ chính
                        # thức qua search_kwargs). Xóa filter khi không còn để đường
                        # cũ không bị vướng trạng thái từ lượt trước. Ở chế độ LỌC MỀM
                        # (P5.2) nhánh này phải quét toàn corpus — nếu cắt ngay lúc tìm
                        # thì chunk ngoài nguồn được ưu tiên sẽ không bao giờ vào ứng
                        # viên, và "mềm" chỉ còn trên danh nghĩa.
                        if (
                            config is not None
                            and config.source_filter
                            and not soft_filter
                        ):
                            r.search_kwargs["filter"] = {
                                "source": {"$in": list(config.source_filter)}
                            }
                        else:
                            r.search_kwargs.pop("filter", None)

                # V1 (27-10): query **nguyên văn** cho nhánh dense thắng `fold` trên đúng
                # index cũ (474/700 vs 202/700, p=5,27e−55) vì fold xoá dấu câu hỏi trong
                # khi 18,6% từ trong index vẫn có dấu — ghi chú 15-10 ("6 chunk sai nguồn")
                # là quan sát 1 câu, không tái lập được trên 700 item. Vì vậy đường cũ
                # (TẮT cờ) giữ nguyên từng byte, còn cờ BẬT chỉ đổi query của nhánh dense;
                # BM25 vẫn nhận `fold` (bm25_tokenize đã nhân đôi token khi dựng chỉ mục).
                docs = self._invoke_hybrid(query)
                # T3: hạng thô từng nhánh cho luật 3 của tầng từ chối ngoài. Đặt SAU
                # `invoke` chính để không ảnh hưởng `docs` (cờ TẮT thì không gọi gì).
                if decoupled_refusal_enabled():
                    self._collect_leg_ranks(
                        fold(query),
                        query if dense_original_query_enabled() else None,
                    )

                # Fallback Query: chạy song song với câu hỏi gốc nếu được cung cấp
                if fallback_query and fallback_query != query:
                    try:
                        fallback_docs = self._invoke_hybrid(fallback_query)
                        # Gộp và khử trùng lặp theo chunk_id
                        seen_chunk_ids = set()
                        merged_docs = []

                        # Thêm docs từ query chính
                        for doc in docs:
                            chunk_id = doc.metadata.get("chunk_id")
                            if chunk_id not in seen_chunk_ids:
                                seen_chunk_ids.add(chunk_id)
                                merged_docs.append(doc)

                        # Thêm docs từ fallback query nếu chưa có
                        for doc in fallback_docs:
                            chunk_id = doc.metadata.get("chunk_id")
                            if chunk_id not in seen_chunk_ids:
                                seen_chunk_ids.add(chunk_id)
                                merged_docs.append(doc)

                        docs = merged_docs
                        print(f"[FallbackQuery] Đã gộp {len(docs)} chunk từ 2 query (normalized + original)")
                    except Exception as exc:
                        print(f"[FallbackQuery] Lỗi khi chạy fallback query ({exc}), chỉ dùng kết quả chính.")

                # Lọc hậu kiểm theo nguồn của router (P3.2): BM25 không filter được
                # lúc truy xuất nên lọc theo metadata sau merge; đồng thời đây là lớp
                # an toàn nếu nhánh Chroma bỏ qua filter. So khớp không dấu (fold) vì
                # một số tên file metadata còn dấu tiếng Việt.
                if config is not None and config.source_filter:
                    allowed_sources = {fold(source) for source in config.source_filter}
                    filtered_docs = [
                        doc
                        for doc in docs
                        if fold(str(doc.metadata.get("source", ""))) in allowed_sources
                    ]
                    if soft_filter:
                        # Chế độ mềm: không cắt, chỉ cộng ưu tiên hạng cho nguồn đúng
                        # để cửa sổ vẫn còn suất cho phần còn lại của corpus.
                        docs = rescore_with_source_preference(
                            docs,
                            config.source_filter,
                            rank_bonus=router_filter_rank_bonus(),
                        )
                        # P5.14: ưu tiên không đồng nghĩa "chiếm hết cửa sổ". Số liệu r2
                        # cho thấy chính lúc bonus >= cỡ cửa sổ là lúc chunk vàng của
                        # nguồn khác bị đẩy ra (21/21 item hồi quy).
                        docs = apply_source_quota(docs, router_source_quota())
                    elif filtered_docs:
                        docs = filtered_docs
                    else:
                        print(
                            "[Router] Cảnh báo: source_filter loại bỏ hết kết quả "
                            f"({config.source_filter}) — giữ nguyên kết quả chưa lọc."
                        )

                # T5a: xếp lại bằng cross-encoder TRÊN POOL đã có (sau bonus + quota, vì
                # đó đúng thứ tự mà đường cũ giao cho cửa sổ). Cờ TẮT thì không gọi gì.
                if reranker_enabled():
                    docs = rerank_documents(
                        query,
                        docs,
                        top_n=None if reranker_keep_candidates() else k,
                    )
                    self.last_rerank_call = last_call.as_dict()

                # Lọc lấy Top-k chunks tốt nhất (Best-First Search / Beam Filter)
                if reranker_enabled() and reranker_keep_candidates():
                    return docs
                return docs[:k]
            except RerankerUnavailable as exc:
                # Mặc định (RERANKER_FALLBACK=0) vẫn dừng loudly: không để reranker rơi
                # vào nhánh lùi về similarity_search ở dưới, vì một round đo nhầm lever
                # còn tệ hơn một round dừng tường minh.
                if not reranker_fallback_enabled():
                    raise
                # RERANKER_FALLBACK=1 (mục 5 đề bài T5, PA-18a): lùi về ĐÚNG thứ tự
                # RRF+bonus trước rerank, cảnh báo rõ, và ghi manifest để hậu kiểm.
                print(
                    f"[Reranker] Cảnh báo: {exc} — lùi về thứ tự RRF trước rerank "
                    "(RERANKER_FALLBACK=1)."
                )
                self.last_rerank_call = {
                    "fallback_used": True,
                    "error": str(exc),
                    "pool": reranker_candidate_pool(),
                }
                return docs[:k]
            except Exception as exc:
                print(f"[HybridSearch] Lỗi truy xuất qua EnsembleRetriever ({exc}), lùi về similarity_search.")

        # 2. Fallback tương thích ngược: ChromaDB similarity_search thuần vector. Đây là
        #    nhánh dense duy nhất, nên cờ V1/PA-48a áp dụng y như nhánh Chroma trong RRF.
        vector_query = query if dense_original_query_enabled() else fold(query)
        return self.vector_db.similarity_search(vector_query, k=k)

    def _merge_subquery_branches(
        self, branches: list[list[Document]], k: int
    ) -> list[Document]:
        """Gộp kết quả truy xuất của các truy vấn con SO_SANH (P3.3).

        Điểm của mỗi chunk = thứ hạng tốt nhất (vị trí nhỏ nhất) của nó xuyên suốt
        các nhánh — RRF fusion đã xảy ra bên trong từng nhánh nên thứ hạng trong
        nhánh chính là điểm số khả dụng. Khử trùng theo `chunk_id`, cắt đúng cửa
        sổ `k` (retrieve_k) để context của generator không bị phình.
        """
        best: dict[Any, tuple[int, int, Document]] = {}
        for branch_idx, docs in enumerate(branches):
            for pos, doc in enumerate(docs):
                metadata = getattr(doc, "metadata", None) or {}
                key = metadata.get("chunk_id", id(doc))
                rank = pos  # nhỏ hơn = tốt hơn
                current = best.get(key)
                if current is None or (rank, branch_idx) < (current[0], current[1]):
                    best[key] = (rank, branch_idx, doc)
        merged = sorted(best.values(), key=lambda item: (item[0], item[1]))
        total = sum(len(branch) for branch in branches)
        print(
            f"[SubQuery] Gộp {total} chunk từ {len(branches)} nhánh truy vấn con thành "
            f"{len(merged)} chunk duy nhất (cửa sổ {max(1, int(k))})."
        )
        return [doc for _, _, doc in merged[: max(1, int(k))]]

    def run(self, question: str, top_k: int = 4) -> dict:
        """Xử lý một câu hỏi với True Hybrid Search và oversampling.

        Tham số:
            question: câu hỏi thô của sinh viên.
            top_k: số chunk đưa vào generator (và đo Hit@top_k nếu evaluation
                   không tự đặt retrieve_k riêng).

        Trả về dict gồm:
            raw_query, normalized_query, retrieval_query,
            contexts: nội dung top_k chunk đầu (cho generator),
            sources:  metadata TẤT CẢ retrieve_k chunk (cho Hit@K evaluation),
            gen_docs: top_k LangChain Document đầu (dùng nội bộ, không in ra),
            answer:   câu trả lời Gemini.
            labels:           nhãn classifier (dict) hoặc None khi ENABLE_CLASSIFIER=0/lỗi.
            retrieval_config: cấu hình router đã áp (dict) hoặc None — để UI/evaluation dùng.
            sub_queries:      truy vấn con đã tách (P3.3) hoặc None khi không áp dụng —
                              tầng tách có guardrail, tách dở tự lùi về đường đơn.

        Tầng phân loại + router (P3.2): chỉ chạy khi ENABLE_CLASSIFIER=1. Mọi sự
        cố của classifier/router đều log cảnh báo và lùi về cấu hình gốc — lượt
        hỏi không bao giờ chết vì tầng này.
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Câu hỏi phải là chuỗi không rỗng.")
        raw_query = question.strip()
        top_k = max(1, int(top_k))

        # --- Tầng phân loại + router (bỏ qua hoàn toàn khi ENABLE_CLASSIFIER=0) ---
        labels: Optional[dict] = None
        retrieval_config: Optional[RetrievalConfig] = None
        effective_top_k = top_k
        if self.enable_classifier:
            try:
                labels = classify_query(raw_query)
                base_config = base_config_from_env()
                # top_k nền lấy theo lượt hỏi (tham số của caller) để router điều
                # chỉnh từ đúng điểm xuất phát; trọng số/lọc vẫn từ env.
                base_config.top_k = top_k
                retrieval_config = get_retrieval_config(labels, base_config)
                effective_top_k = max(1, retrieval_config.top_k)
            except Exception as exc:
                print(
                    "[Classifier] Cảnh báo: tầng phân loại/router lỗi "
                    f"({type(exc).__name__}: {exc}) — lùi về cấu hình truy xuất gốc."
                )
                labels = None
                retrieval_config = None
                effective_top_k = top_k

        # --- Oversampling: lấy nhiều ứng viên hơn, chỉ cho generator top_k đầu ---
        # Với oversample_factor=2 và top_k=6, retrieve_k=12 để tăng Recall/Hit@K
        retrieve_k = effective_top_k * self.oversample_factor

        # Bước 1: Chuẩn hóa câu hỏi bằng Qwen (normalize_user_query)
        normalized_query = normalize_user_query(self.local_slm, raw_query)

        # Bước 2: Mở rộng từ khóa (Query Expansion) bằng từ điển đồng nghĩa pháp lý
        expanded_query = (
            expand_query_with_synonyms(normalized_query)
            if self.expand_query
            else normalized_query
        )

        # retrieval_query (dạng đã fold) chỉ dùng để log/debug: bản thân retrieve() tự fold
        # trước khi gọi EnsembleRetriever cho khớp tài liệu OCR mất dấu.
        retrieval_query = fold(expanded_query)

        # --- Tách truy vấn con cho SO_SANH (P3.3) — chỉ khi router bật subquery ---
        # Guardrail của split_comparison_query tự suy giảm về [query] khi tách dở;
        # pipeline chỉ đi đường đa nhánh khi thực sự tách được >= 2 truy vấn con,
        # còn lại chạy y hệt đường đơn (kèm fallback_query) — câu TRA_CUU bị gán
        # nhầm SO_SANH vì thế luôn an toàn tuyệt đối.
        sub_queries: Optional[list[str]] = None
        if (
            retrieval_config is not None
            and retrieval_config.enable_subquery
            and labels is not None
            and fold(str(labels.get("question_type") or "")).strip().lower() == "so_sanh"
        ):
            try:
                # Tách trên câu CHUẨN HÓA (chưa mở rộng từ đồng nghĩa): cụm từ
                # đồng nghĩa ghép ở cuối chuỗi làm Qwen 1.5B parrot/echo (đo thực
                # nghiệm P3.3). Mỗi truy vấn con vẫn được mở rộng từ đồng nghĩa
                # riêng trước khi truy xuất ở nhánh bên dưới — recall không đổi.
                candidate_subs = split_comparison_query(
                    normalized_query, llm_client=self.local_slm
                )
                if len(candidate_subs) >= 2:
                    sub_queries = candidate_subs
            except Exception as exc:
                print(
                    "[SubQuery] Cảnh báo: tách truy vấn con lỗi "
                    f"({type(exc).__name__}: {exc}) — lùi về truy xuất đơn."
                )
                sub_queries = None

        # --- T3 (mặc định TẮT): chuẩn bị đo hạng cho tầng từ chối ngoài ---
        decoupled = decoupled_refusal_enabled()
        if decoupled:
            self.last_leg_ranks = None

        if sub_queries:
            # Truy xuất TỪNG sub-query với retrieve_k như thường, tái dùng
            # index/Ensemble hiện có (không dựng lại BM25). Mỗi sub-query cũng
            # được mở rộng từ đồng nghĩa cho đồng nhất với đường đơn.
            branches: list[list[Document]] = []
            for sub in sub_queries:
                sub_expanded = (
                    expand_query_with_synonyms(sub) if self.expand_query else sub
                )
                branches.append(
                    self.retrieve(sub_expanded, k=retrieve_k, config=retrieval_config)
                )
            all_docs = self._merge_subquery_branches(branches, k=retrieve_k)
        else:
            # Truy xuất True Hybrid — query CÓ DẤU (đã mở rộng từ đồng nghĩa); retrieve() sẽ fold
            # nội bộ cho Chroma leg. Đồng thời truyền câu hỏi gốc (raw_query) làm fallback_query
            # để đảm bảo không mất chunk nếu chuẩn hóa làm mất từ khóa.
            all_docs = self.retrieve(
                expanded_query,
                k=retrieve_k,
                fallback_query=raw_query,
                config=retrieval_config,
            )

        # Generator chỉ nhận top_k đầu — recall window rộng hơn mà context không phình.
        gen_docs = all_docs[:effective_top_k]
        contexts = [doc.page_content for doc in gen_docs]

        # sources chứa TOÀN BỘ retrieve_k để evaluation đo Hit@retrieve_k.
        sources = [describe_document(doc, i) for i, doc in enumerate(all_docs)]

        # P3.4: truyền question_type xuống generator để chọn biến thể prompt
        # (bảng cho SO_SANH, bước đánh số cho THU_TUC, dòng từ chối cho
        # NGOAI_PHAM_VI). labels là None khi ENABLE_CLASSIFIER=0 → question_type
        # None → prompt gốc giống hệt từng ký tự, cache cũ vẫn trúng.
        question_type = labels.get("question_type") if labels else None

        answer: Optional[str] = None
        pre_features: Optional[dict] = None
        refusal_decision: Optional[dict] = None
        if decoupled:
            # Luật 1-3: tầng ngoài CÓ quyền từ chối mà không tốn một lượt sinh.
            # Luật 1-3 luôn đo trên cửa sổ CHUNK GỐC (không phải cửa sổ đã cắt câu):
            # phán quyết "có căn cứ không" là phán quyết về CHẤT LƯỢNG TRUY XUẤT — r8 và
            # r9 phải cùng một phép đo ở đây thì hai round mới chỉ khác nhau MỘT biến là
            # những gì model được đọc.
            from src.generator import REFUSAL_TEXT  # import trễ: cờ TẮT không nạp module

            bm25_w, vec_w = self._fusion_weights(retrieval_config)
            pre = decide_pre_generation(
                question=normalized_query,
                contexts=contexts,
                leg_ranks=self._aligned_leg_ranks(gen_docs),
                bm25_weight=bm25_w,
                vector_weight=vec_w,
            )
            log_decision("pre", pre, question=normalized_query)
            refusal_decision = {"stage": "pre", **pre.to_dict()}
            if pre.refuse:
                answer = REFUSAL_TEXT
            else:
                pre_features = pre.features

        # --- T3 đòn bẩy 3: extract-then-generate (mặc định TẮT) ---
        # Cửa sổ generator được thay bằng 3–5 CÂU bằng chứng; `sources` (toàn bộ
        # retrieve_k) KHÔNG đổi nên gold@k của round vẫn đo đúng tầng truy xuất.
        # `contexts` trong kết quả LÀ CÁI MODEL ĐÃ ĐỌC — trọng tài chấm grounding trên
        # đúng căn cứ đó, không được privileged hơn model.
        evidence_info: Optional[dict] = None
        if answer is None and evidence_selection_enabled():
            source_names = [
                str((getattr(d, "metadata", None) or {}).get("source") or "") for d in gen_docs
            ]
            if retrieval_config is not None:
                source_names += [str(s) for s in (retrieval_config.source_filter or [])]
            window, evidence_info = select_evidence(
                normalized_query,
                gen_docs,
                source_names=source_names,
                embeddings=getattr(self.vector_db, "embeddings", None),
            )
            gen_docs = window
            contexts = [doc.page_content for doc in gen_docs]

        if answer is None:
            answer = self.generator.generate_answer(
                query=normalized_query,
                retrieved_docs=gen_docs,
                question_type=question_type,
                # P5.12b: truyền cả câu gốc để lớp cứu từ chối oan (`ENABLE_ANSWER_RESCUE`)
                # xét điều kiện trên câu HỎI thật, chứ không trên bản chuẩn hóa đôi khi
                # bị bộ chuẩn hóa viết thành câu khác (đo: 16/300 lượt sinh).
                raw_query=raw_query,
            )

        if pre_features is not None:
            # Luật 4-5: câu vừa sinh phải đứng được trên căn cứ, nếu không tầng ngoài
            # thay nó bằng câu từ chối chuẩn. Chỉ chạy khi luật 1-3 đã CHO SINH
            # (`pre_features` không None), vì thế cờ TẮT không bao giờ tới đây.
            post = decide_post_generation(
                question=normalized_query,
                contexts=contexts,
                answer=answer,
                source_names=[str((getattr(d, "metadata", None) or {}).get("source") or "") for d in gen_docs],
                pre_features=pre_features,
            )
            log_decision("post", post, question=normalized_query)
            refusal_decision = {"stage": "post", **post.to_dict()}
            if post.refuse:
                answer = REFUSAL_TEXT  # đã nạp ở nhánh `decoupled` phía trên

        return {
            "raw_query": raw_query,
            "normalized_query": normalized_query,
            "expanded_query": expanded_query,
            "retrieval_query": retrieval_query,
            "sub_queries": sub_queries,
            "contexts": contexts,
            "sources": sources,
            "answer": answer,
            "labels": labels,
            "retrieval_config": asdict(retrieval_config) if retrieval_config is not None else None,
            # T3: phán quyết của tầng từ chối ngoài (None khi cờ TẮT). Không vào schema
            # `.jsonl` của round — `run_round` chỉ đọc các khóa nó cần — mà để UI và
            # hậu kiểm đếm được lý do từ chối mà không parse log.
            "refusal_decision": refusal_decision,
            "evidence_selection": evidence_info,
        }


