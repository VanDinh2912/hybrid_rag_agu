"""Train baseline retrieval có giám sát nhẹ từ `retrieval_pairs.jsonl`.

Pipeline gồm 3 kênh lexical:
- BM25 với tham số `k1`/`b` được chọn trên train split;
- TF-IDF word cosine;
- TF-IDF char_wb cosine.

Kênh 4 là logistic regression học trọng số tổ hợp 3 kênh từ positive/negative pairs.
Tất cả văn bản được `fold()` để mô phỏng đúng cách so khớp OCR-mất-dấu của đồ án.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from typing import Any

import joblib
import numpy as np
from rank_bm25 import BM25Okapi
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from src.text_utils import fold  # noqa: E402

DATA_PATH = os.path.join(BASE_DIR, "data", "training", "retrieval_pairs.jsonl")
OUT_DIR = os.path.join(BASE_DIR, "models", "retrieval_baseline")
RANDOM_STATE = 42
WORD_MAX = 80_000
CHAR_MAX = 120_000
TOKEN_RE = re.compile(r"(?u)\b\w+\b")


def load_rows() -> list[dict[str, Any]]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def build_index(rows: list[dict[str, Any]]):
    folded_to_id: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []

    def add(text: str, source: str | None = None, chunk_id: int | None = None) -> int:
        folded = fold(text)
        if folded in folded_to_id:
            return folded_to_id[folded]
        doc_id = len(candidates)
        folded_to_id[folded] = doc_id
        candidates.append(
            {
                "doc_id": doc_id,
                "text": text,
                "folded": folded,
                "source": source,
                "chunk_id": chunk_id,
                "sha1": sha1(folded),
            }
        )
        return doc_id

    queries = []
    for row in rows:
        pos_id = add(row["positive"], row.get("positive_source"), row.get("positive_chunk_id"))
        raw_neg_ids = [add(n) for n in row.get("negatives", [])]
        # Sau khi fold, một negative có thể trùng positive; loại để không gán nhãn mâu thuẫn.
        neg_ids = list(dict.fromkeys(n for n in raw_neg_ids if n != pos_id))
        queries.append(
            {
                "query": row["query"],
                "folded_query": fold(row["query"]),
                "positive_doc_id": pos_id,
                "negative_doc_ids": neg_ids,
                "quality": row.get("quality"),
                "folded": row.get("folded", False),
            }
        )
    return queries, candidates, folded_to_id


def metrics_from_scores(query_rows: list[dict[str, Any]], all_queries: list[dict[str, Any]], scores: np.ndarray) -> dict[str, float]:
    hits = {1: 0, 3: 0, 5: 0}
    rr = []
    for q_idx, q in enumerate(query_rows):
        target = all_queries[q["global_index"]]["positive_doc_id"]
        ranking = np.argsort(-scores[q_idx], kind="stable")
        rank = int(np.where(ranking == target)[0][0]) + 1
        for k in hits:
            if rank <= k:
                hits[k] += 1
        rr.append(1.0 / rank)
    n = max(1, len(query_rows))
    return {
        "hit@1": hits[1] / n,
        "hit@3": hits[3] / n,
        "hit@5": hits[5] / n,
        "mrr": float(np.mean(rr)),
    }


def bm25_score_matrices(query_tokens, corpus_tokens, grid):
    matrices: dict[tuple[float, float], np.ndarray] = {}
    for k1, b in grid:
        model = BM25Okapi(corpus_tokens, k1=k1, b=b)
        matrices[(k1, b)] = np.vstack(
            [np.asarray(model.get_scores(tokens), dtype=np.float32) for tokens in query_tokens]
        )
    return matrices


def normalize_rows(scores: np.ndarray) -> np.ndarray:
    max_scores = scores.max(axis=1, keepdims=True)
    return scores / np.maximum(max_scores, 1e-9)


def pair_features(query_idx: int, doc_indices: list[int], bm25_norm: np.ndarray, word_cos: np.ndarray, char_cos: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [
            bm25_norm[query_idx, doc_indices],
            word_cos[query_idx, doc_indices],
            char_cos[query_idx, doc_indices],
            np.log1p(bm25_norm[query_idx, doc_indices]),
        ]
    )


def top_document_ids(scores_row: np.ndarray, positive_doc_id: int, limit: int = 15) -> set[int]:
    ranking = np.argsort(-scores_row, kind="stable")[:limit]
    return {int(doc_id) for doc_id in ranking if int(doc_id) != positive_doc_id}


def fusion_scores(model: LogisticRegression, n_queries: int, n_candidates: int, bm25_norm: np.ndarray, word_cos: np.ndarray, char_cos: np.ndarray) -> np.ndarray:
    """Tính điểm fusion cho toàn bộ ma trận query × candidate đúng khuôn 4 feature."""
    doc_indices = list(range(n_candidates))
    all_scores = np.empty((n_queries, n_candidates), dtype=np.float32)
    for qi in range(n_queries):
        feats = pair_features(qi, doc_indices, bm25_norm, word_cos, char_cos)
        all_scores[qi] = model.decision_function(feats)
    return all_scores


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = load_rows()
    all_queries, candidates, folded_to_id = build_index(rows)
    for idx, q in enumerate(all_queries):
        q["global_index"] = idx

    # Dedup query-positive pairs by (folded query, positive doc).
    seen: set[tuple[str, int]] = set()
    queries = []
    for q in all_queries:
        key = (q["folded_query"], q["positive_doc_id"])
        if key in seen:
            continue
        seen.add(key)
        queries.append(q)

    print(f"Pairs: {len(rows)} → unique query/doc pairs: {len(queries)} · candidates: {len(candidates)}")

    corpus_texts = [c["folded"] for c in candidates]
    corpus_tokens = [tokenize(t) for t in corpus_texts]
    query_texts = [q["folded_query"] for q in queries]
    query_tokens = [tokenize(t) for t in query_texts]

    word_vectorizer = TfidfVectorizer(
        lowercase=True,
        token_pattern=r"(?u)\b\w+\b",
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=WORD_MAX,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        sublinear_tf=True,
        max_features=CHAR_MAX,
    )
    Xc_word = word_vectorizer.fit_transform(corpus_texts)
    Xq_word = word_vectorizer.transform(query_texts)
    Xc_char = char_vectorizer.fit_transform(corpus_texts)
    Xq_char = char_vectorizer.transform(query_texts)
    word_cos = cosine_similarity(Xq_word, Xc_word)
    char_cos = cosine_similarity(Xq_char, Xc_char)

    # Split by positive doc id để một chunk không xuất hiện cả train lẫn test.
    doc_ids = sorted({q["positive_doc_id"] for q in queries})
    rng = np.random.default_rng(RANDOM_STATE)
    shuffled = list(doc_ids)
    rng.shuffle(shuffled)
    test_doc_ids = set(shuffled[: max(1, int(len(shuffled) * 0.3))])

    train_queries = [q for q in queries if q["positive_doc_id"] not in test_doc_ids]
    test_queries = [q for q in queries if q["positive_doc_id"] in test_doc_ids]
    train_idx = {q["global_index"]: i for i, q in enumerate(queries)}
    test_idx = {q["global_index"]: i for i, q in enumerate(queries)}

    grid = [(1.2, 0.3), (1.2, 0.5), (1.2, 0.75), (1.5, 0.3), (1.5, 0.5), (1.5, 0.75), (2.0, 0.5), (2.0, 0.75)]
    bm25_matrices = bm25_score_matrices(query_tokens, corpus_tokens, grid)
    bm25_scores = []
    for (k1, b), scores in bm25_matrices.items():
        m = metrics_from_scores(train_queries, queries, scores[[train_idx[q['global_index']] for q in train_queries]])
        bm25_scores.append({"k1": k1, "b": b, **m})
    best_bm25 = max(bm25_scores, key=lambda item: (item["hit@3"], item["mrr"]))
    best_matrix = bm25_matrices[(best_bm25["k1"], best_bm25["b"])]
    best_norm = normalize_rows(best_matrix)

    # Baselines.
    train_rows_idx = [train_idx[q["global_index"]] for q in train_queries]
    test_rows_idx = [test_idx[q["global_index"]] for q in test_queries]
    baselines = {
        "bm25_train": metrics_from_scores(train_queries, queries, best_matrix[train_rows_idx]),
        "bm25_test": metrics_from_scores(test_queries, queries, best_matrix[test_rows_idx]),
        "word_train": metrics_from_scores(train_queries, queries, word_cos[train_rows_idx]),
        "word_test": metrics_from_scores(test_queries, queries, word_cos[test_rows_idx]),
        "char_train": metrics_from_scores(train_queries, queries, char_cos[train_rows_idx]),
        "char_test": metrics_from_scores(test_queries, queries, char_cos[test_rows_idx]),
    }

    # Hard-negative mining: dùng chính 3 kênh lexical để lấy ứng viên khó,
    # thay vì chỉ dùng 3 negative có sẵn (thường quá dễ phân biệt).
    X_rows, y_rows = [], []
    for q in train_queries:
        qi = train_idx[q["global_index"]]
        positive_id = q["positive_doc_id"]
        negatives = set(q["negative_doc_ids"])
        negatives.update(top_document_ids(best_matrix[qi], positive_id))
        negatives.update(top_document_ids(word_cos[qi], positive_id))
        negatives.update(top_document_ids(char_cos[qi], positive_id))
        negatives.discard(positive_id)
        docs = [positive_id] + sorted(negatives)
        X_rows.append(pair_features(qi, docs, best_norm, word_cos, char_cos))
        y_rows.extend([1] + [0] * len(negatives))
    X = np.vstack(X_rows)
    y = np.asarray(y_rows)

    fusion_metrics = []
    for C in (0.01, 0.1, 1.0, 10.0, 100.0):
        model = LogisticRegression(max_iter=3000, class_weight="balanced", C=C)
        model.fit(X, y)
        all_scores = fusion_scores(model, len(queries), len(candidates), best_norm, word_cos, char_cos)
        m = metrics_from_scores(train_queries, queries, all_scores[train_rows_idx])
        fusion_metrics.append({"C": C, **m})
    best_fusion = max(fusion_metrics, key=lambda item: (item["hit@3"], item["mrr"]))
    final_model = LogisticRegression(max_iter=3000, class_weight="balanced", C=best_fusion["C"])
    final_model.fit(X, y)

    all_scores = fusion_scores(final_model, len(queries), len(candidates), best_norm, word_cos, char_cos)
    train_final = metrics_from_scores(train_queries, queries, all_scores[train_rows_idx])
    test_final = metrics_from_scores(test_queries, queries, all_scores[test_rows_idx])

    joblib.dump(
        {
            "word_vectorizer": word_vectorizer,
            "char_vectorizer": char_vectorizer,
            "fusion_model": final_model,
            "bm25_k1": best_bm25["k1"],
            "bm25_b": best_bm25["b"],
            "candidates": candidates,
        },
        os.path.join(OUT_DIR, "retrieval_model.joblib"),
    )
    save_npz(os.path.join(OUT_DIR, "candidate_word_tfidf.npz"), Xc_word)
    save_npz(os.path.join(OUT_DIR, "candidate_char_tfidf.npz"), Xc_char)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": "BM25 + TF-IDF word + TF-IDF char_wb + learned logistic fusion",
        "n_pairs": len(queries),
        "n_candidates": len(candidates),
        "train_docs": len({q['positive_doc_id'] for q in train_queries}),
        "test_docs": len({q['positive_doc_id'] for q in test_queries}),
        "bm25_grid": bm25_scores,
        "selected_bm25": best_bm25,
        "baselines": baselines,
        "fusion_training_rows": int(X.shape[0]),
        "fusion_grid": fusion_metrics,
        "selected_fusion": best_fusion,
        "fusion_train": train_final,
        "fusion_test": test_final,
    }
    with open(os.path.join(OUT_DIR, "training_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("Selected BM25:", best_bm25)
    print("Baselines:", json.dumps(baselines, ensure_ascii=False, indent=2))
    print("Fusion train:", train_final)
    print("Fusion test:", test_final)


if __name__ == "__main__":
    main()
