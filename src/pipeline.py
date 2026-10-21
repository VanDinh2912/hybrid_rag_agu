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

from src.classifier import classify_query
from src.query_normalizer import normalize_user_query
from src.retrieval import SYNONYM_DICTIONARY, expand_query_with_synonyms, split_comparison_query
from src.router import RetrievalConfig, base_config_from_env, get_retrieval_config
from src.text_utils import fold
from src.vector_db import (
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
                for r in sub_retrievers:
                    if hasattr(r, "k"):
                        r.k = k
                    elif hasattr(r, "search_kwargs") and isinstance(r.search_kwargs, dict):
                        r.search_kwargs["k"] = k
                        # Filter metadata `source` cho nhánh Chroma (API hỗ trợ chính
                        # thức qua search_kwargs). Xóa filter khi không còn để đường
                        # cũ không bị vướng trạng thái từ lượt trước.
                        if config is not None and config.source_filter:
                            r.search_kwargs["filter"] = {
                                "source": {"$in": list(config.source_filter)}
                            }
                        else:
                            r.search_kwargs.pop("filter", None)

                # Tài liệu Tầng 1 mất dấu thanh vì OCR nên vector bge-m3 của chunk không còn dấu:
                # query PHẢI được fold trước khi nhúng cho Chroma leg (BM25 không bị ảnh hưởng
                # vì bm25_tokenize đã nhân đôi cả hai dạng token khi dựng chỉ mục).
                # Thực nghiệm 15-10: cùng index, query có dấu → 6 chunk sai nguồn;
                # query đã fold → chunk đúng lên hạng 1.
                docs = self.ensemble_retriever.invoke(fold(query))

                # Fallback Query: chạy song song với câu hỏi gốc nếu được cung cấp
                if fallback_query and fallback_query != query:
                    try:
                        fallback_docs = self.ensemble_retriever.invoke(fold(fallback_query))
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
                    if filtered_docs:
                        docs = filtered_docs
                    else:
                        print(
                            "[Router] Cảnh báo: source_filter loại bỏ hết kết quả "
                            f"({config.source_filter}) — giữ nguyên kết quả chưa lọc."
                        )

                # Lọc lấy Top-k chunks tốt nhất (Best-First Search / Beam Filter)
                return docs[:k]
            except Exception as exc:
                print(f"[HybridSearch] Lỗi truy xuất qua EnsembleRetriever ({exc}), lùi về similarity_search.")

        # 2. Fallback tương thích ngược: ChromaDB similarity_search (sử dụng query đã fold để khớp tài liệu OCR mất dấu)
        vector_query = fold(query)
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
        answer = self.generator.generate_answer(
            query=normalized_query, retrieved_docs=gen_docs, question_type=question_type
        )

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
        }


