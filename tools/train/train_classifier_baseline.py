"""Train baseline classifier 2 đầu ra cho dataset phân loại câu hỏi.

Mô hình: TF-IDF (word + char) + Logistic Regression. Mục tiêu là có một baseline
chạy được trên CPU trong 16 GB RAM và dùng để so sánh với Qwen/API.

Kết quả:
- `topic_pipeline.joblib`
- `question_type_pipeline.joblib`
- `training_report.json`
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import joblib
import scipy.sparse as sp
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRAIN_PATH = os.path.join(BASE_DIR, "data", "training", "classifier_train.jsonl")
SEED_PATH = os.path.join(BASE_DIR, "data", "training", "classifier_benchmark_seed.jsonl")
OUT_DIR = os.path.join(BASE_DIR, "models", "classifier_baseline")
RANDOM_STATE = 42


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class TextFeatures(BaseEstimator, TransformerMixin):
    """Hợp nhất word n-gram và char n-gram; char_wb chịu tốt tiếng Việt dính dấu câu."""

    def __init__(self) -> None:
        self.word = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b\w+\b",
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=80_000,
        )
        self.char = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            sublinear_tf=True,
            max_features=120_000,
        )

    def fit(self, X, y=None):
        self.word.fit(X, y)
        self.char.fit(X, y)
        return self

    def transform(self, X):
        return sp.hstack([self.word.transform(X), self.char.transform(X)], format="csr")

    def get_feature_names_out(self):
        import numpy as np

        return np.asarray(["features"], dtype=object)


def make_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("features", TextFeatures()),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", C=4.0)),
        ]
    )


def normalize_topic(value: str | None) -> str:
    return value or "none"


def metrics_payload(y_true, y_pred) -> dict[str, Any]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "classification_report": classification_report(
            y_true, y_pred, output_dict=True, zero_division=0
        ),
    }


def cv_predict(model: Pipeline, X: list[str], y: list[str]) -> list[str]:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    return cross_val_predict(model, X, y, cv=skf, method="predict", n_jobs=1)


def main() -> None:
    train_rows = load_jsonl(TRAIN_PATH)
    seed_rows = load_jsonl(SEED_PATH)

    X_train = [row["text"] for row in train_rows]
    X_seed = [row["text"] for row in seed_rows]
    topic_train = [normalize_topic(row["labels"].get("topic")) for row in train_rows]
    topic_seed = [normalize_topic(row["labels"].get("topic")) for row in seed_rows]
    type_train = [row["labels"].get("question_type") or "UNKNOWN" for row in train_rows]
    type_seed = [row["labels"].get("question_type") or "UNKNOWN" for row in seed_rows]

    print(f"Train: {len(X_train)} mẫu · Seed/gold: {len(X_seed)} mẫu")

    topic_cv_pred = cv_predict(make_pipeline(), X_train, topic_train)
    type_cv_pred = cv_predict(make_pipeline(), X_train, type_train)
    print("Đã xong internal CV; đang train full và đánh giá seed...")

    topic_model = make_pipeline().fit(X_train, topic_train)
    type_model = make_pipeline().fit(X_train, type_train)

    topic_seed_pred = topic_model.predict(X_seed)
    type_seed_pred = type_model.predict(X_seed)

    joblib.dump(topic_model, os.path.join(OUT_DIR, "topic_pipeline.joblib"))
    joblib.dump(type_model, os.path.join(OUT_DIR, "question_type_pipeline.joblib"))

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": "TF-IDF(word+char_wb) + LogisticRegression",
        "random_state": RANDOM_STATE,
        "train_file": os.path.relpath(TRAIN_PATH, BASE_DIR),
        "gold_eval_file": os.path.relpath(SEED_PATH, BASE_DIR),
        "n_train": len(X_train),
        "n_gold_eval": len(X_seed),
        "topic": {
            "internal_cv": metrics_payload(topic_train, topic_cv_pred),
            "gold_holdout": metrics_payload(topic_seed, topic_seed_pred),
        },
        "question_type": {
            "internal_cv": metrics_payload(type_train, type_cv_pred),
            "gold_holdout": metrics_payload(type_seed, type_seed_pred),
        },
    }

    with open(os.path.join(OUT_DIR, "training_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    for task in ("topic", "question_type"):
        cv = report[task]["internal_cv"]
        gold = report[task]["gold_holdout"]
        print(
            f"{task:13s} | internal CV acc={cv['accuracy']:.3f} macroF1={cv['macro_f1']:.3f} "
            f"| gold acc={gold['accuracy']:.3f} macroF1={gold['macro_f1']:.3f}"
        )


if __name__ == "__main__":
    main()
