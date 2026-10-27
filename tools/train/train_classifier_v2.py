"""Classifier v2: bỏ prefix lịch sự và đánh giá 5-fold trên riêng gold seed.

Cấu hình tốt nhất được chọn bằng cross-validation trên `classifier_benchmark_seed.jsonl`
(chỉ dùng template train làm dữ liệu nền cho từng fold), sau đó train model cuối trên
toàn bộ train + seed. Báo cáo ghi rõ seed được dùng trong quá trình chọn siêu tham số,
nên không được coi là held-out độc lập tuyệt đối.
"""

from __future__ import annotations

import json
import os
import re
import scipy.sparse as sp
from datetime import datetime
from typing import Any, Iterable

import joblib
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRAIN_PATH = os.path.join(BASE_DIR, "data", "training", "classifier_train.jsonl")
SEED_PATH = os.path.join(BASE_DIR, "data", "training", "classifier_benchmark_seed.jsonl")
OUT_DIR = os.path.join(BASE_DIR, "models", "classifier_baseline_v2")
RANDOM_STATE = 42

PREFIX_RE = re.compile(
    r"^\s*(?:Em muốn biết|Cho em hỏi|Nhờ tư vấn giúp em)\s*[:,.-]\s*",
    flags=re.IGNORECASE,
)


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def clean_text(text: str) -> str:
    text = PREFIX_RE.sub("", text.strip())
    return re.sub(r"\s+", " ", text).lower()


class TextFeatures(BaseEstimator, TransformerMixin):
    def __init__(self, word_max: int = 80_000, char_max: int = 120_000) -> None:
        self.word_max = word_max
        self.char_max = char_max
        self.word = None
        self.char = None

    def _build(self):
        self.word = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b\w+\b",
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=self.word_max,
        )
        self.char = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            sublinear_tf=True,
            max_features=self.char_max,
        )

    def fit(self, X, y=None):
        self._build()
        self.word.fit(X, y)
        self.char.fit(X, y)
        return self

    def transform(self, X):
        return sp.hstack([self.word.transform(X), self.char.transform(X)], format="csr")

    def get_feature_names_out(self):
        return np.asarray(["features"], dtype=object)


def make_model(C: float, class_weight: str | None) -> Pipeline:
    return Pipeline(
        [
            ("features", TextFeatures()),
            (
                "clf",
                LogisticRegression(
                    max_iter=2500,
                    C=C,
                    class_weight=class_weight,
                    solver="lbfgs",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def evaluate_seed_cv(
    label_name: str,
    template_rows: list[dict[str, Any]],
    seed_rows: list[dict[str, Any]],
    C: float,
    class_weight: str | None,
) -> dict[str, Any]:
    y_all = [row["labels"][label_name] or "none" for row in seed_rows]
    X_all = [clean_text(row["text"]) for row in seed_rows]
    X_template = [clean_text(row["text"]) for row in template_rows]
    y_template = [row["labels"][label_name] or "none" for row in template_rows]

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    predictions: list[str] = []
    actuals: list[str] = []
    for train_idx, test_idx in skf.split(X_all, y_all):
        X_fold = X_template + [X_all[i] for i in train_idx]
        y_fold = y_template + [y_all[i] for i in train_idx]
        model = make_model(C, class_weight).fit(X_fold, y_fold)
        predictions.extend(model.predict([X_all[i] for i in test_idx]))
        actuals.extend([y_all[i] for i in test_idx])

    return {
        "C": C,
        "class_weight": class_weight,
        "accuracy": float(accuracy_score(actuals, predictions)),
        "macro_f1": float(f1_score(actuals, predictions, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(actuals, predictions, average="weighted", zero_division=0)),
        "classification_report": classification_report(
            actuals, predictions, output_dict=True, zero_division=0
        ),
    }


def best_result(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return max(results, key=lambda item: (item["macro_f1"], item["accuracy"]))


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    template_rows = load_jsonl(TRAIN_PATH)
    seed_rows = load_jsonl(SEED_PATH)

    # Dedup theo (text đã clean, label), giữ bản đầu tiên.
    seen: set[tuple[str, str, str]] = set()
    all_rows = []
    for source, rows in (("template", template_rows), ("seed", seed_rows)):
        for row in rows:
            key = (
                clean_text(row["text"]),
                row["labels"].get("topic") or "none",
                row["labels"].get("question_type") or "UNKNOWN",
            )
            if key not in seen:
                seen.add(key)
                all_rows.append({**row, "source": source})

    print(f"Template: {len(template_rows)} · Seed: {len(seed_rows)} · Dedup: {len(all_rows)}")
    template_dedup = [row for row in all_rows if row["source"] == "template"]
    seed_dedup = [row for row in all_rows if row["source"] == "seed"]

    configs = [
        (1.0, None),
        (4.0, None),
        (1.0, "balanced"),
        (4.0, "balanced"),
    ]
    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": "stripped-prefix TF-IDF(word+char_wb) + LogisticRegression",
        "n_template_dedup": len(template_dedup),
        "n_seed_dedup": len(seed_dedup),
        "grid": {"topic": [], "question_type": []},
        "final": {},
    }

    for label_name in ("topic", "question_type"):
        results = []
        for C, class_weight in configs:
            print(f"CV {label_name}: C={C}, class_weight={class_weight}")
            result = evaluate_seed_cv(label_name, template_dedup, seed_dedup, C, class_weight)
            results.append(result)
            print(
                f"  acc={result['accuracy']:.3f} macroF1={result['macro_f1']:.3f}"
            )
        report["grid"][label_name] = results
        selected = best_result(results)
        report["final"][label_name] = {
            "selected_config": {"C": selected["C"], "class_weight": selected["class_weight"]},
            "seed_cv": {k: selected[k] for k in selected if k not in {"C", "class_weight"}},
        }

        X_final = [clean_text(row["text"]) for row in all_rows]
        y_final = [row["labels"][label_name] or "none" for row in all_rows]
        model = make_model(selected["C"], selected["class_weight"]).fit(X_final, y_final)
        artifact = os.path.join(OUT_DIR, f"{label_name}_pipeline.joblib")
        joblib.dump(model, artifact)
        report["final"][label_name]["artifact"] = os.path.relpath(artifact, BASE_DIR)

    with open(os.path.join(OUT_DIR, "training_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    for label_name in ("topic", "question_type"):
        cv = report["final"][label_name]["seed_cv"]
        print(
            f"{label_name:13s} | selected {report['final'][label_name]['selected_config']} "
            f"acc={cv['accuracy']:.3f} macroF1={cv['macro_f1']:.3f}"
        )


if __name__ == "__main__":
    main()
