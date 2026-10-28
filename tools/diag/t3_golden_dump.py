"""T3-test — máy chụp GOLDEN cho bất biến "cờ TẮT = hành vi cũ từng ký tự".

Vì sao cần file này
-------------------
Bất biến #2 của vòng lặp P5 nói: mọi lever nằm sau cờ, và **tắt cờ thì pipeline phải
trả lại đúng hành vi đã nghiệm thu**. T3 nối hai cờ vào `src/core/pipeline.py`
(`ENABLE_DECOUPLED_REFUSAL`, `ENABLE_EVIDENCE_SELECTION`) ngay trên đường sinh, nên
nghĩa vụ kiểm chứng nặng nhất là: 30 lượt `pipeline.run` cố định, hai cờ TẮT, phải cho
đầu ra **byte-identical** với bản code CHƯA có đường nối đó.

Cách làm (không tự lừa):
- `git archive HEAD` dựng bản cây **trước khi wiring T3 landing** (tại HEAD,
  `src/core/pipeline.py` không có dòng `decoupled_refusal_enabled()` nào — đã kiểm).
- Chính file này được copy vào bản cây đó và chạy ở cả hai nơi. Nó chỉ dùng API có thật
  ở CẢ HAI cây: `HybridRAGPipeline(...).run(question, top_k)`, `QwenGenerator._build_prompt`
  và `QwenGenerator._cache_key`.
- Output chia hai khối:
  * `core`  = mặt chung (answer/contexts/sources/query các loại/labels/retrieval_config +
              số lượt generator + docs generator NHẬN + prompt Qwen + **cache key**).
              Đây là khối so byte giữa hai cây.
  * `t3`    = hai khóa MỚI của pipeline (`refusal_decision`, `evidence_selection`) — khối
              này đương nhiên không tồn tại ở cây baseline, nên không được đưa vào `core`;
              test riêng assertion chúng phải là None khi cờ TẮT.
- Stub generator trả chuỗi cố định; KHÔNG gọi Ollama/ChromaDB/Gemini.

Chạy:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/t3_golden_dump.py --out tests/golden/t3_off_30items_head.json
    # baseline: copy file này vào tmp/t3_baseline_head/tools/diag/ rồi chạy với --root cây đó
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ fixture 30 item (cố định)
# Văn bản tự dựng, NGẪU NHIÊN-THIỆT (chọn tay một lần rồi ghim): không lấy từ corpus thật
# để golden không đổi khi corpus đổi.
SENT_FACTS = [
    "Điều 15, Khoản 2: Sinh viên được phép đăng ký học lại tối đa 2 lần cho mỗi học phần không đạt.",
    "Học phí học kỳ chính quy là 7.400.000 đồng, nộp trước ngày 15 tháng 10 hàng năm.",
    "Sinh viên hệ vừa học vừa làm được miễn 30 % học phí nếu thuộc diện chính sách.",
    "Điều 22: Xét tốt nghiệp gồm 4 tiêu chí, trong đó điểm trung bình tích lũy đạt từ 2,0 trở lên.",
    "Thư viện mở cửa từ 7 giờ đến 19 giờ các ngày trong tuần, riêng thứ Bảy đến 11 giờ 30 phút.",
    "Điều 8: Sinh viên được chuyển ngành sau tối thiểu 2 học kỳ và không quá 1 lần.",
    "Mỗi tín chỉ lý thuyết tương đương 15 tiết, thực hành tương đương 30 tiết theo Quy chế 40/2017.",
    "Học bổng khuyến khích học loại Giỏi là 1.200.000 đồng mỗi tháng, xét theo 10 lớp.",
]
SENT_NOISE = [
    "Giáo trình in tại xưởng in nội bộ, khổ A4, đóng gáy keo nhiệt trong ba ngày.",
    "Máy photocopy tầng hai do phòng Hành chính quản lý, liên hệ số nội bộ 108 để được hướng dẫn.",
    "Cây xanh khu B được cắt tỉa định kỳ vào thứ Năm hằng tuần bởi đơn vị dịch vụ thuê ngoài.",
    "Biên bản họp hội đồng sư phạm ngày 12 tháng 3 ghi nhận 27 đại biểu tham dự đủ điều kiện.",
]
QUESTIONS = [
    "Sinh viên học lại tối đa bao nhiêu lần mỗi học phần?",
    "Học phí học kỳ chính quy là bao nhiêu và nộp trước ngày nào?",
    "Tỉ lệ miễn học phí cho diện chính sách là bao nhiêu phần trăm?",
    "Điểm trung bình tích lũy để xét tốt nghiệp là bao nhiêu?",
    "Thư viện mở cửa đến mấy giờ vào thứ Bảy?",
    "Sinh viên được chuyển ngành mấy lần và sau bao nhiêu học kỳ?",
    "Một tín chỉ lý thuyết tương đương bao nhiêu tiết?",
    "Mức học bổng khuyến khích loại Giỏi mỗi tháng là bao nhiêu?",
    "Thời gian in giáo trình A4 mất bao nhiêu ngày?",
    "Ai quản lý máy photocopy tầng hai và số nội bộ là gì?",
]


def _doc(i: int, which: int) -> dict[str, Any]:
    fact = SENT_FACTS[(i * 3 + which) % len(SENT_FACTS)]
    noise = SENT_NOISE[(i + which * 2) % len(SENT_NOISE)]
    other = SENT_FACTS[(i + which * 5 + 2) % len(SENT_FACTS)]
    return {
        "content": f"{fact} {noise} {other}",
        "metadata": {
            "source": f"qw-golden-{i % 7}-{which}.pdf",
            "tier": 1 + (i + which) % 3,
            "chunk_id": 1000 * i + which,
        },
    }


def build_items(n: int = 30) -> list[dict[str, Any]]:
    """30 item cố định: câu hỏi i -> cửa sổ 2 chunk (1 liên quan, 1 nhiễu trộn lẫn)."""
    items = []
    for i in range(n):
        items.append({
            "id": f"g{i:02d}",
            "question": QUESTIONS[i % len(QUESTIONS)],
            "docs": [_doc(i, 0), _doc(i, 1)],
            # Chuỗi trả về CỐ ĐỊNH theo vòng lặp — generator thật bị thay bằng stub.
            "stub_answer": (
                f"Trả lời cố định {i % 5}: theo Điều {(i % 9) + 1}, Khoản {(i % 3) + 1} "
                f"thì giới hạn là {(i % 7) + 1} lần."
            ),
        })
    return items


# ------------------------------------------------------------------ đồ giả cho các tầng dưới
class FakeDoc:
    def __init__(self, page_content: str, metadata: dict[str, Any]):
        self.page_content = page_content
        self.metadata = metadata


class FakeLeg:
    def __init__(self, docs: list[FakeDoc]):
        self.docs = docs
        self.calls = 0

    def invoke(self, query):
        self.calls += 1
        return self.docs


class FakeEnsemble:
    def __init__(self, legs: list[FakeLeg], fused: list[FakeDoc]):
        self.retrievers = legs
        self.weights = [1.0, 1.0]
        self.fused = fused
        self.calls = 0

    def invoke(self, query):
        self.calls += 1
        return self.fused


class FakeLocalSLM:
    """Bộ 'chuẩn hóa' giả: trả về đúng câu hỏi đã lowercase khoảng trắng — không model."""

    def __init__(self, normalized: str):
        self._normalized = normalized

    def generate(self, prompt, temperature: float = 0.0):
        return self._normalized


class StubGenerator:
    """Generator cố định: ghi lại những gì nhận, trả chuỗi đã định sẵn, đếm lượt gọi."""

    def __init__(self, answer: str):
        self.answer = answer
        self.calls = 0
        self.received_query: Optional[str] = None
        self.received_docs: list[dict[str, Any]] = []

    def generate_answer(self, query: str, retrieved_docs: list[Any], **kwargs: Any) -> str:
        self.calls += 1
        self.received_query = query
        self.received_docs = [
            {
                "page_content": getattr(d, "page_content", str(d)),
                "metadata": dict(getattr(d, "metadata", {}) or {}),
            }
            for d in retrieved_docs
        ]
        return self.answer


# ------------------------------------------------------------------ môi trường ghim cứng
OFF_ENV = {
    # Hai cờ T3 — ca đang test.
    "ENABLE_DECOUPLED_REFUSAL": "0",
    "ENABLE_EVIDENCE_SELECTION": "0",
    # Các lever khác phải TẮT để golden chỉ đo một thứ.
    "ENABLE_CLASSIFIER": "0",
    "ENABLE_ANSWER_RESCUE": "0",
    "ENABLE_ANSWER_GUARD": "0",
    "ENABLE_RERANKER": "0",
    "ENABLE_HYBRID_SEARCH": "1",
    "ENABLE_QUERY_EXPANSION": "1",
    "GENERATION_CACHE": "0",
    # Ghim tham số để hai cây tính ra cùng một chuỗi.
    "OLLAMA_MODEL": "t3-golden-model",
    "OLLAMA_HOST": "http://127.0.0.1:1",  # không có ai nghe — và sẽ không bao giờ được gọi
    "BM25_WEIGHT": "0.5",
    "CHROMA_WEIGHT": "0.5",
}
CLEAR_ENV = (
    "DEC_MIN_ENTITY_COVERAGE", "DEC_MIN_TOKEN_OVERLAP", "DEC_MIN_RRF_NORM",
    "DEC_MIN_GROUNDING", "DEC_MAX_UNSUPPORTED", "EV_MIN_SENTENCES", "EV_MAX_SENTENCES",
    "EV_MIN_KEYWORD_HITS", "EVIDENCE_RERANKER", "GENERATION_CACHE_DIR",
    "GENERATOR_OLLAMA_MODEL",
)


def pin_env() -> None:
    for k, v in OFF_ENV.items():
        os.environ[k] = v
    for k in CLEAR_ENV:
        os.environ.pop(k, None)


# ------------------------------------------------------------------ chạy một item
def run_item(item: dict[str, Any]) -> dict[str, Any]:
    from src.generator import QwenGenerator
    from src.core.pipeline import HybridRAGPipeline

    docs = [FakeDoc(d["content"], dict(d["metadata"])) for d in item["docs"]]
    ensemble = FakeEnsemble([FakeLeg(docs), FakeLeg(docs)], docs)
    gen = StubGenerator(item["stub_answer"])
    pipeline = HybridRAGPipeline(
        vector_db=None,
        local_slm=FakeLocalSLM(item["question"]),
        generator=gen,
        retriever=ensemble,
    )
    result = pipeline.run(item["question"], top_k=2)

    # Cache key Qwen tính trên đúng cửa sổ item này — mặt phải bất biến khi cờ TẮT.
    qwen = QwenGenerator(ollama_model="t3-golden-model", use_cache=False, temperature=0.1)
    dict_docs = [
        {"source": d["metadata"]["source"], "tier": str(d["metadata"]["tier"]),
         "content": d["content"]}
        for d in item["docs"]
    ]
    prompt = qwen._build_prompt(item["question"], dict_docs)
    cache_key = qwen._cache_key(prompt, 0.1)

    core: dict[str, Any] = {
        "id": item["id"],
        "question": item["question"],
        "raw_query": result["raw_query"],
        "normalized_query": result["normalized_query"],
        "expanded_query": result["expanded_query"],
        "retrieval_query": result["retrieval_query"],
        "sub_queries": result["sub_queries"],
        "contexts": result["contexts"],
        "sources": result["sources"],
        "answer": result["answer"],
        "labels": result["labels"],
        "retrieval_config": result["retrieval_config"],
        "gen_calls": gen.calls,
        "gen_query": gen.received_query,
        "gen_docs": gen.received_docs,
        "qwen_prompt_sha1": hashlib.sha1(prompt.encode("utf-8")).hexdigest(),
        "qwen_cache_key": cache_key,
        "ensemble_calls": ensemble.calls,
        "leg_calls": [leg.calls for leg in ensemble.retrievers],
    }
    t3_fields = {
        "refusal_decision": result.get("refusal_decision", "<khong_ton_tai_o_baseline>"),
        "evidence_selection": result.get("evidence_selection", "<khong_ton_tai_o_baseline>"),
    }
    return {"core": core, "t3": t3_fields}


def dump(out_path: Path) -> dict[str, Any]:
    pin_env()
    items = build_items()
    rows = [run_item(it) for it in items]
    payload = {
        "meta": {
            "root": str(ROOT),
            "pipeline_has_t3_fields": rows[0]["t3"]["refusal_decision"] != "<khong_ton_tai_o_baseline>",
            "env": {k: os.environ.get(k) for k in sorted(OFF_ENV)},
        },
        "core": [r["core"] for r in rows],
        "t3": [r["t3"] for r in rows],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    core_only = json.dumps(payload["core"], ensure_ascii=False, indent=2, sort_keys=True)
    return {
        "out": str(out_path),
        "n_items": len(rows),
        "core_sha256": hashlib.sha256(core_only.encode("utf-8")).hexdigest(),
        "bytes": len(text.encode("utf-8")),
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Chụp golden pipeline.run 30 item với hai cờ T3 TẮT.")
    ap.add_argument("--out", required=True, help="Đường dẫn JSON ghi kết quả.")
    args = ap.parse_args(argv)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    info = dump(Path(args.out))
    print(f"[golden] {info['n_items']} item -> {info['out']} ({info['bytes']} byte)")
    print(f"[golden] core_sha256 = {info['core_sha256']}")
    print(f"[golden] root = {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
