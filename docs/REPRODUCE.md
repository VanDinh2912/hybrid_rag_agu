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

Cấu hình khuyến nghị: **`ENABLE_DENSE_ORIGINAL_QUERY=1`** và **`ENABLE_ANSWER_GUARD=1`** — chép từ
khối cuối `.env.example` (ở đó hai dòng đang **bị chú thích** để tệp mẫu không tự bật cờ nào; bỏ
dấu `#` rồi đặt vào `.env`). Đây là **khuyến nghị vận hành**, KHÔNG phải mặc định của mã: đọc
`src/core/config.py` / `src/answer_guard.py` sẽ thấy cả hai vẫn mặc định `"0"` (TẮT), và mọi artifact
đã công bố bên dưới đều được đo với **cờ TẮT** trừ khi dòng đăng ký của round nói khác.

| cờ | giá trị khuyến nghị | bằng chứng |
|---|---|---|
| `ENABLE_DENSE_ORIGINAL_QUERY` | `1` | r23 (29-10): dense truy vấn nguyên văn × guard, 300 id mới — `PASS_CORRECT` +21, McNemar p=0,0046, `FAIL_FABRICATED` 1/1, `HALLUCINATED` 0/0, CI cụm [0,0033; 0,16] ⇒ **XÁC NHẬN** |
| `ENABLE_ANSWER_GUARD` | `1` | cùng lượt r23 (guard là nửa còn lại của cặp được đo) |
| `ENABLE_RERANKER` | `0` — **GIỮ TẮT** | r22 (29-10): gold@6 581→612 (+31, p=3,12e−06) nhưng neo HUMAN 77→72 (−6,49%, ngưỡng −5%) ⇒ **BỊ BÁC VETO HUMAN** (D-37) |

Cái bẫy đã gặp: bật cờ bằng cách sửa giá trị mặc định trong `src/` sẽ làm mọi số neo trong
`docs/EXPERIMENTS.md` mất hiệu lực (chúng đo với cờ TẮT). Vì vậy khuyến nghị này chỉ được ghi ở
tầng cấu hình `.env`, không sửa mã; và trong `.env.example` nó nằm ở dạng chú thích để
`tools/diag/env_flag_audit.py` vẫn báo 0 `LOI_KHAI_BAO` (một cờ BẬT trong tệp mẫu = lỗi).

### Kiểm tra env trước khi đo (bắt buộc — phát hiện 31-10)

`src/core/classifier.py`, `src/retrieval/router.py` và `src/assessment/evaluation.py` gọi
`load_dotenv()` **ngay lúc import**. Hệ quả: mọi tiến trình có import pipeline — kể cả
`tools/loop/run_round.py` và `pytest` — đều **nhận cờ từ `.env` của máy**, không chỉ tiến trình
được chạy bằng tay. Cờ lạc sẽ đổi `cache_policy_deviation()` → đổi khóa cache sinh (`QwenGenerator._cache_key`)
và có thể làm lệch golden/neo. Trước khi chạy bất kỳ phép đo nào, kiểm tra:

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c "from src.core.cache_policy import cache_policy_deviation as d; print(d())"
```

Phải in `None` (regime chuẩn). Nếu in token lạ, `.env` máy đó đang bật lever — xử lý ở tầng `.env`
(không sửa mặc định trong `src/`), hoặc chạy phép đo với biến env đặt tường minh. Xem PA-56
(`docs/PA_TRIAGE.md`) về đề xuất bỏ `load_dotenv()` lúc import.

## 1. Dựng index

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe ingest.py
```

Cảnh báo (D-29): `ingest.py` **xoá collection** trong `CHROMA_PERSIST_DIR` (mặc định
`<gốc dự án>/chroma_db`; mẫu `.env` vẫn ghi `./chroma_db`) trước khi index. Đường dẫn tương đối
được hiểu theo gốc dự án (`src/core/paths.py`, REVIEW §4), không theo thư mục đang đứng. Muốn giữ
index đang chạy, đặt `CHROMA_PERSIST_DIR` sang thư mục mới trước khi chạy.
Index sản xuất hiện có 361 chunk (gốc repo, `./chroma_db`), dựng từ **26 tệp nguồn**;
`indexes/experimental/chroma_db_vie/` (342 chunk — đường dẫn cũ `chroma_db_vie/`, đổi 28-10)
là index re-OCR **chưa kích hoạt** (PA-17).

Cảnh báo tái lập (phát hiện 31-10): `data/corpus/` trên đĩa có **29 tệp (24 PDF + 5 DOCX)** — 3 PDF
thêm 28-10 (`dh24-ky`, `qd-1543-BGDDT`, `so-tay-sktt`) **chưa ingest**. Chạy `ingest.py` trên thư mục
hiện hành sinh **443 chunk, không phải 361**, và mọi số neo đo trên index 361 sẽ không tái lập được.
Muốn tái lập đúng artifact đã công bố: dựng index vào thư mục **khác** (`CHROMA_PERSIST_DIR=<thư mục mới>`)
rồi đối chiếu, hoặc tạm loại 3 tệp đó khỏi đầu vào — không ghi đè `./chroma_db`.

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
# (0) cổng tái lập: chỉ đọc, so trạng thái thật với pin 31-10 (rc=1 nếu HỎNG)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/repro_preflight.py

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

> **Ghi chú 01-11 (PA-41 + tài liệu đổi sau 25-10):** bảng trên giữ nguyên số đo 26-10. Chạy lại
> trên cây hiện tại: `docs_consistency_check` đếm **120 đường dẫn** (README 59 +
> `docs/planning/ROADMAP.md` 61 — tài liệu đổi bố cục/nội dung sau 25-10, trong đó PA-29 thêm 1
> đường dẫn `tools/diag/docs_consistency_check.py` ở §5.3), và
> `final_number_audit` còn **2 LỆCH thời điểm đó** (T5 `33 + 44 = 77` do PA-48 `ed0fc74` thêm 2 test;
> T7 `119 → 120` đường dẫn). Cả hai là kỳ vọng cũ đã được vá, không phải số đo hồi quy.

`rescore_retrieval_round_v2.py` cập nhật `generated_at` trong `round_summary_retrieval.json` của
round nguồn (cây `data/loop/rounds_v2/` chưa tracked) và từ chối chạy nếu trọng tài là v1.

**Đo lại 31-10 (nhánh `fix/audit-20261031`, cùng máy, venv, `NORMALIZE_SANITY_GUARD=0`):**

| Đại lượng | Giá trị | Ghi chú |
|---|---|---|
| `pytest tests -q` | **1.551 passed, 5 skipped** (107 s) | 1.556 test được collect; bộ test đã lớn hơn mốc 26-10 |
| `pytest` **không** ghim lever | 1.550 passed, **1 failed**, 5 skipped | đỏ duy nhất = `test_mo_truong_that_cua_repo_dang_khong_bat_lever_nao` — máy này `.env` bật `NORMALIZE_SANITY_GUARD=1`, test báo đúng (xem mục "Kiểm tra env") |
| `artifact_manifest.py --check` | **KHỚP 158 tệp / 390.961.924 B** | chạy sau toàn bộ máy kiểm: pytest **không** ghi vào `chroma_db` |
| `evidence_pack_check.py --check` | **KHỚP** (84 tệp / 4.041.992 B; 25 dòng D-, 9 neo) | |
| `docs_consistency_check.py` | **0 lỗi, 5 cảnh báo, 115 đường dẫn** | |
| `final_number_audit.py` | **63 dòng, 4 LỆCH, rc=0** | 4 dòng LỆCH đều là **kỳ vọng cũ** so với cây hiện tại (2 dòng đếm test T5 đo trước khi bộ test lớn lên; 1 dòng checker ghi 100 đường dẫn; 1 dòng chữ ký trọng tài v1 `9f1179ccab74`) — không phải số đo hồi quy |
| `referee_fingerprint()` | **`2911c69f740d`** | không đổi |
| `tools/diag/repro_preflight.py` | **ĐẠT** (0 hỏng; 1 cảnh báo = lever `.env` như dòng trên) | 361 chunk / 26 nguồn / phân bố tầng / sha256 index / 29 tệp corpus / 24 tệp + 10.672 dòng `data/training`; pin `docs/repro_pins_20261031.json` (PA-57) |

> **Ghi chú 01-11 (PA-41):** bản đo 31-10 giữ nguyên. Sau khi vá hai kỳ vọng `46 → 51` test và
> chữ ký `9f1179ccab74 → 2911c69f740d`, audit còn **2 LỆCH thời điểm đó**: T5 `33 + 42 = 75 → 33 + 44 = 77`
> (PA-48 `ed0fc74` thêm 2 test) và T7 `100 → 120 đường dẫn` (tài liệu đổi sau 25-10; PA-29 thêm 1
> đường dẫn so với mốc 119). Các thành phần còn lại của dòng checker (264 lệnh · 4 help · 0 lỗi ·
> 5 cảnh báo · 30 dòng sổ) không đổi.

**Thứ tự cổng (PA-60):** ngày 31-10 đã thấy byte 3 tệp mỗi index bị đổi ngay sau một chuỗi cổng dù
nội dung logic không đổi; **kiểm soát lại cùng ngày** (băm 10 tệp → chạy riêng
`final_number_audit.py` → băm lại) cho **0/10 tệp đổi**, nên bước gây tái ghi **chưa xác định**.
Phòng ngừa vẫn giữ: chạy `final_number_audit.py` **trước**, `artifact_manifest.py --check`
**sau cùng**; nếu LỆCH, phục hồi 6 tệp từ backup rồi kiểm lại. `repro_preflight.py` đọc index
bằng sqlite `mode=ro&immutable=1` nên không thể gây hiệu ứng này.

## 6. Hàng đợi phản hồi và đối chiếu corpus ↔ index (hardening 01-11)

Tab 3 mặc định **không** tự học (`LEARN_AUTO_APPLY=0`): mỗi phản hồi chỉ ghi
`logs/feedback/user_feedback.json` + một tệp trong `logs/feedback/queue/`. Ba tệp học
(`data/evaluation/benchmark_questions.json`, `data/learning/normalization_pairs.json`,
`data/corpus/ghi_chu_hoc_them.txt`) và `chroma_db/` giữ nguyên byte cho tới khi có người duyệt.

```bash
# xem kế hoạch, không ghi gì (mặc định là dry-run)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/feedback_promote.py
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/feedback_promote.py --json

# áp thật: ghi 3 tệp văn bản (có sao lưu), rebuild index vào thư mục MỚI, chạy cổng rồi hoán đổi
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/feedback_promote.py --apply --yes

# đối chiếu corpus ↔ index, chỉ đọc (chroma.sqlite3 mở mode=ro&immutable=1)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/corpus_index_manifest.py
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/corpus_index_manifest.py --check
```

`--apply` từ chối khi: hàng đợi có tệp JSON hỏng, thiếu `--yes` (mã 2), đích index nằm trong
vùng bảo vệ (`ensure_separate_index_target`), index mới thiếu `chroma.sqlite3`, chữ ký trọng tài
khác `2911c69f740d`, hoặc `corpus_index_manifest` báo lệch. Mọi lỗi sau khi đã sửa tệp văn bản
đều khôi phục từ bản sao; index cũ giữ ở `logs/feedback/promotions/<stamp>/chroma_db_before/`.
Tệp hàng đợi được **chuyển** sang `queue/applied/<stamp>/`, không xoá.

`corpus_index_manifest.py --check` đang trả **mã 1** vì 3 PDF thêm 28-10 chưa được ingest — đó là
hiện trạng đã biết (PA-17), không phải lỗi mới; dùng nó làm cổng sau mỗi lần rebuild để không bỏ
sót tệp mới.
