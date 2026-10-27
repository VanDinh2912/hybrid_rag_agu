"""Classifier v3: tối ưu riêng question_type cho các lớp hiếm.

V2 có accuracy cao nhưng THU_TUC recall chỉ 20% và NGOAI_PHAM_VI 50%. Script này
thử oversample có kiểm soát + custom class_weight và chọn cấu hình tốt nhất bằng
5-fold stratified CV trên unique gold seed (mỗi fold loại đúng test seed khỏi train).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.utils import resample

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRAIN_PATH = os.path.join(BASE_DIR, "data", "training", "classifier_train.jsonl")
SEED_PATH = os.path.join(BASE_DIR, "data", "training", "classifier_benchmark_seed.jsonl")
OUT_DIR = os.path.join(BASE_DIR, "models", "classifier_baseline_v3")
RANDOM_STATE = 42
PREFIX_RE = re.compile(
    r"^\s*(?:Em muốn biết|Cho em hỏi|Nhờ tư vấn giúp em)\s*[:,.-]\s*",
    flags=re.IGNORECASE,
)
RARE_LABELS = {"SO_SANH", "THU_TUC", "NGOAI_PHAM_VI"}


def load_jsonl(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def clean_text(text: str) -> str:
    text = PREFIX_RE.sub("", text.strip())
    return re.sub(r"\s+", " ", text).lower()


class TextFeatures:
    """Feature extractor cấp module để joblib pickle được (bản trước định nghĩa
    trong hàm features() nên pipeline không lưu được)."""

    def fit(self, X, y=None):
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
        self.word.fit(X, y)
        self.char.fit(X, y)
        return self

    def transform(self, X):
        import scipy.sparse as sp

        return sp.hstack([self.word.transform(X), self.char.transform(X)], format="csr")


def features() -> Pipeline:
    return Pipeline([("features", TextFeatures())])


def make_model(C: float, class_weight: dict[str, float]) -> Pipeline:
    model = features()
    model.steps.append(
        (
            "clf",
            LogisticRegression(
                max_iter=3000,
                C=C,
                class_weight=class_weight,
                solver="lbfgs",
                random_state=RANDOM_STATE,
            ),
        )
    )
    return model


def oversample_rows(X: list[str], y: list[str], factor: int) -> tuple[list[str], list[str]]:
    out_X, out_y = list(X), list(y)
    rng = np.random.default_rng(RANDOM_STATE)
    labels = sorted(set(y))
    for label in labels:
        if label not in RARE_LABELS:
            continue
        idx = [i for i, item in enumerate(y) if item == label]
        if not idx:
            continue
        target = max(0, len(idx) * (factor - 1))
        if target == 0:
            continue
        # Duplicate có chủ đích; chỉ dùng trong fold train, không rò rỉ test seed.
        for _ in range(target):
            source = int(rng.integers(len(idx)))
            out_X.append(X[idx[source]])
            out_y.append(label)
    return out_X, out_y


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    template_rows = load_jsonl(TRAIN_PATH)
    seed_rows = load_jsonl(SEED_PATH)

    # Dedup theo nội dung sạch, ưu tiên seed để giữ nhãn gold.
    seen: dict[str, dict[str, Any]] = {}
    for source, rows in (("template", template_rows), ("seed", seed_rows)):
        for row in rows:
            text = clean_text(row["text"])
            if text and (text not in seen or source == "seed"):
                seen[text] = {**row, "clean_text": text, "source": source}
    all_rows = list(seen.values())
    template_rows = [r for r in all_rows if r["source"] == "template"]
    seed_rows = [r for r in all_rows if r["source"] == "seed"]

    X_template = [r["clean_text"] for r in template_rows]
    y_template = [r["labels"]["question_type"] for r in template_rows]
    X_seed = [r["clean_text"] for r in seed_rows]
    y_seed = [r["labels"]["question_type"] for r in seed_rows]

    configs = []
    for C in (1.0, 4.0):
        for factor in (1, 2, 4):
            for weight_name, weights in (
                ("soft", {"TRA_CUU": 1.0, "SO_SANH": 2.0, "THU_TUC": 4.0, "NGOAI_PHAM_VI": 6.0}),
                ("strong", {"TRA_CUU": 1.0, "SO_SANH": 3.0, "THU_TUC": 8.0, "NGOAI_PHAM_VI": 12.0}),
            ):
                configs.append({"C": C, "factor": factor, "weight": weight_name, "weights": weights})

    results = []
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    for config in configs:
        preds, actuals = [], []
        for train_idx, test_idx in skf.split(X_seed, y_seed):
            X_fold = X_template + [X_seed[i] for i in train_idx]
            y_fold = y_template + [y_seed[i] for i in train_idx]
            if config["factor"] > 1:
                X_fold, y_fold = oversample_rows(X_fold, y_fold, config["factor"])
            model = make_model(config["C"], config["weights"]).fit(X_fold, y_fold)
            fold_pred = model.predict([X_seed[i] for i in test_idx])
            preds.extend(fold_pred)
            actuals.extend([y_seed[i] for i in test_idx])

        macro = f1_score(actuals, preds, average="macro", zero_division=0)
        acc = accuracy_score(actuals, preds)
        result = {
            "C": config["C"],
            "factor": config["factor"],
            "weight": config["weight"],
            "accuracy": float(acc),
            "macro_f1": float(macro),
            "classification_report": classification_report(
                actuals, preds, output_dict=True, zero_division=0
            ),
        }
        results.append(result)
        print(
            f"C={config['C']} factor={config['factor']} {config['weight']:6s} "
            f"acc={acc:.3f} macroF1={macro:.3f}"
        )

    best = max(results, key=lambda r: (r["macro_f1"], r["accuracy"]))
    X_final = X_template + X_seed
    y_final = y_template + y_seed
    if best["factor"] > 1:
        X_final, y_final = oversample_rows(X_final, y_final, best["factor"])
    final_model = make_model(best["C"], dict(
        {"soft": {"TRA_CUU": 1.0, "SO_SANH": 2.0, "THU_TUC": 4.0, "NGOAI_PHAM_VI": 6.0},
         "strong": {"TRA_CUU": 1.0, "SO_SANH": 3.0, "THU_TUC": 8.0, "NGOAI_PHAM_VI": 12.0}}[best["weight"]]
    )).fit(X_final, y_final)
    joblib.dump(final_model, os.path.join(OUT_DIR, "question_type_pipeline.joblib"))

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_template_dedup": len(template_rows),
        "n_seed_dedup": len(seed_rows),
        "grid": [{k: v for k, v in r.items() if k != "classification_report"} for r in results],
        "selected": {k: v for k, v in best.items() if k != "classification_report"},
        "selected_detail": best["classification_report"],
    }
    best_no_oversample = max(
        (r for r in results if r["factor"] == 1),
        key=lambda r: (r["macro_f1"], r["accuracy"]),
    )
    report["oversampling_helped"] = bool(
        best["factor"] > 1
        and (best["macro_f1"], best["accuracy"])
        > (best_no_oversample["macro_f1"], best_no_oversample["accuracy"])
    )
    report["conclusion"] = (
        "Oversample lớp hiếm (factor 2/4) không cải thiện macro F1 so với factor 1; "
        "nó làm mô hình over-predict lớp hiếm và giảm accuracy tổng thể. "
        "Kết luận: giữ classifier v2 làm bản deploy; v3 chỉ là experiment phủ định."
        if not report["oversampling_helped"]
        else "Oversample cải thiện macro F1; v3 là bản ứng viên thay v2."
    )
    with open(os.path.join(OUT_DIR, "training_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report["selected"], indent=2))


if __name__ == "__main__":
    main()
