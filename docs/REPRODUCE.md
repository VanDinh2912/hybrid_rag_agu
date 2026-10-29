# Tái lập kết quả

Mọi lệnh dưới đây chạy từ gốc repo (`hybrid_rag_agu/`). Hai điều kiện bắt buộc:

1. **Dùng interpreter trong `venv/`**, không dùng `python` hệ thống: bản hệ thống thiếu
   `pypdfium2`/`streamlit` nên 4 tệp test lỗi collection (đo ở D-35/D-36).
2. **Đặt `PYTHONIOENCODING=utf-8`** trên Windows: console mặc định cp1258 làm một số máy kiểm
   hỏng ở khâu in (D-36). Các máy kiểm đã có guard, nhưng đặt biến vẫn là cách chắc nhất.

## 0. Môi trường

```bash
python -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt
venv/Scripts/python.exe -m pip install streamlit pandas     # chỉ cần cho demo Streamlit

ollama pull qwen2.5:1.5b-instruct
ollama serve                                                # terminal riêng, mở suốt lượt chạy

Copy-Item .env.example .env                                 # điền GEMINI_API_KEY nếu chạy Gemini
```

Chạy hoàn toàn offline (0 lượt Gemini): dùng `--use-qwen-generator --no-judge` cho đánh giá tĩnh;
vòng lặp `tools/loop/` không gọi Gemini trong bất kỳ round nào.

### Cấu hình khuyến nghị (r23, 29-10)

Cấu hình khuyến nghị: **`ENABLE_DENSE_ORIGINAL_QUERY=1`** và **`ENABLE_ANSWER_GUARD=1`** — khai trong
`.env` (mục cuối `.env.example`). Đây là **khuyến nghị vận hành**, KHÔNG phải mặc định của mã: đọc
`src/core/config.py` / `src/answer_guard.py` sẽ thấy cả hai vẫn mặc định `"0"` (TẮT), và mọi artifact
đã công bố bên dưới đều được đo với **cờ TẮT** trừ khi dòng đăng ký của round nói khác.

| cờ | giá trị khuyến nghị | bằng chứng |
|---|---|---|
| `ENABLE_DENSE_ORIGINAL_QUERY` | `1` | r23 (29-10): dense truy vấn nguyên văn × guard, 300 id mới — `PASS_CORRECT` +21, McNemar p=0,0046, `FAIL_FABRICATED` 1/1, `HALLUCINATED` 0/0, CI cụm [0,0033; 0,16] ⇒ **XÁC NHẬN** |
| `ENABLE_ANSWER_GUARD` | `1` | cùng lượt r23 (guard là nửa còn lại của cặp được đo) |
| `ENABLE_RERANKER` | `0` — **GIỮ TẮT** | r22 (29-10): gold@6 581→612 (+31, p=3,12e−06) nhưng neo HUMAN 77→72 (−6,49%, ngưỡng −5%) ⇒ **BỊ BÁC VETO HUMAN** (D-37) |

Cái bẫy đã gặp: bật cờ bằng cách sửa giá trị mặc định trong `src/` sẽ làm mọi số neo trong
`docs/EXPERIMENTS.md` mất hiệu lực (chúng đo với cờ TẮT). Vì vậy khuyến nghị này chỉ được ghi ở
tầng cấu hình `.env`, không sửa mã.

## 1. Dựng index

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe ingest.py
```

Cảnh báo (D-29): `ingest.py` **xoá collection** trong `CHROMA_PERSIST_DIR` (mặc định `./chroma_db`)
trước khi index. Muốn giữ index đang chạy, đặt `CHROMA_PERSIST_DIR` sang thư mục mới trước khi chạy.
Index sản xuất hiện có 361 chunk (gốc repo, `./chroma_db`);
`indexes/experimental/chroma_db_vie/` (342 chunk — đường dẫn cũ `chroma_db_vie/`, đổi 28-10)
là index re-OCR **chưa kích hoạt** (PA-17).

## 2. Chạy thử

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe main.py "Điều kiện xét tốt nghiệp?"
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe ui/app.py
```

## 3. Đánh giá tĩnh (benchmark có ground truth)

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe src/assessment/evaluation.py --use-qwen-generator --no-judge --limit 2
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe src/assessment/evaluate_classifier.py --limit 5
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe scripts/benchmark_chunking.py --generator qwen --limit 2
```

Bỏ `--limit` để chạy đủ bộ; ghi `--output`/`--summary-output` sang tên mới nếu không muốn ghi đè
kết quả đã công bố trong `outputs/` và `logs/`.

## 4. Vòng lặp đo một round (offline)

```bash
# chạy một round retrieval-only trên bộ 811 item — LUÔN dùng tên round mới
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/run_round.py \
    --round r_demo --phase retrieval --split all --top-k 6 --out-root data/loop/rounds

# chấm cổng so với round nền (exit 1 = KHÔNG ĐẠT, là kết quả chứ không phải lỗi)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/gate.py \
    --round r_demo --baseline r11 --phase retrieval

# quy lỗi theo tầng
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/attribute.py \
    --round r_demo --compare r11 --phase retrieval

# hoặc cả chuỗi có manifest tất định
tools/loop/run_chain.ps1 -Chain tools/loop/chains/t5a_reranker.json -DryRun
tools/loop/run_chain.ps1 -Chain tools/loop/chains/t5a_reranker.json
```

`run_round.py` bỏ qua id đã có nếu chạy tiếp cùng round; không chạy lại round đã đóng với cùng tên.

## 5. Máy kiểm và số neo

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/docs_consistency_check.py
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/final_number_audit.py
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c "from tools.loop.verify import referee_fingerprint as f; print(f())"

# chấm lại OFFLINE round neo r11 (chỉ đọc round, ghi báo cáo ra tên mới trong tmp/)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/rescore_retrieval_round_v2.py \
    --rounds r11 --phase retrieval --out tmp/repro_r11.json
```

| Đại lượng neo | Giá trị (đo 26-10) | Ghi chú |
|---|---|---|
| `pytest tests -q` | **1.495 passed, 5 skipped** (~90 s) | đợt dọn không thêm test |
| `referee_fingerprint()` | **`2911c69f740d`** | trọng tài v2 (PA-2 + PA-20) |
| Chấm lại r11, pha retrieval | **FAIL_RETRIEVAL=182, PENDING_GENERATION=629** | 811 dòng, 0 lệch, item drift 0 |
| `docs_consistency_check.py` | **0 lỗi, 5 cảnh báo, 100 đường dẫn** | cảnh báo = 5 script chưa có argparse |
| `final_number_audit.py` | **63 dòng, 2 LỆCH đã biết, rc=0** | hai kỳ vọng cũ chờ PA-41; phải chạy bằng venv |

`rescore_retrieval_round_v2.py` cập nhật `generated_at` trong `round_summary_retrieval.json` của
round nguồn (cây `data/loop/rounds_v2/` chưa tracked) và từ chối chạy nếu trọng tài là v1.
