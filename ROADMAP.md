# ROADMAP — Hướng làm lại đồ án

> Phiên bản 1.0 · Ngày 2026-10-20 · Trạng thái: **chờ người dùng duyệt** (cổng P0.1)
> Văn bản định hướng cho toàn bộ P0.2 → P5.4; chi tiết từng nhiệm vụ xem `prompts/README.md`.

## 1. Tên đề tài mới

**"Ứng dụng kiến trúc RAG phân loại câu hỏi và hỗ trợ truy xuất thông tin quy chế đào tạo sinh viên"**

Hướng làm lại kế thừa nguyên vẹn pipeline True Hybrid Search 4 tầng đang chạy ổn định, bổ sung **tầng phân loại câu hỏi 2 nhãn** (chủ đề + loại câu hỏi) và **router truy xuất theo lớp câu hỏi**, sau đó đánh giá A/B có/không có tầng phân loại trên cùng bộ 100 câu.

## 2. Mục tiêu & câu hỏi nghiên cứu

**Mục tiêu:** xây bộ phân loại gán đồng thời hai nhãn cho mỗi câu hỏi — `category` thuộc đúng 14 nhóm chủ đề của benchmark và `question_type` thuộc 4 nhãn cố định `TRA_CUU` / `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI`; dùng nhãn để chọn cấu hình truy xuất (router) và biến thể prompt sinh câu trả lời; đo chất lượng trên benchmark v3 (100 câu, 13 khóa = 12 khóa v2 + `question_type`) và so sánh A/B với baseline `ENABLE_CLASSIFIER=0`.

**Ba câu hỏi nghiên cứu:**

1. Bộ phân loại 2 nhãn (chủ đề + loại câu hỏi) đạt độ chính xác bao nhiêu trên 100 câu?
2. Router truy xuất theo lớp câu hỏi cải thiện Hit@K/MRR ở những nhóm câu nào so với cấu hình truy xuất chung?
3. Bật tầng phân loại có tốt hơn tắt trên tổng thể hay không, và có làm tụt chất lượng ở nhóm câu nào không?

## 3. Hiện trạng & mốc so sánh

### 3.1. Tài sản hiện có (tái sử dụng nguyên vẹn)

| Hạng mục | Hiện trạng | Nguồn |
|---|---|---|
| Corpus | 26 tài liệu (21 PDF + 5 DOCX) ở 3 tầng | `README.md` mục 8; kiểm tra `data/corpus/` ngày 2026-10-20 |
| Index sản xuất | 361 chunks, collection `agu_regulations` | `README.md` mục 5.1; `chroma_db/chroma.sqlite3` ngày 2026-10-20 |
| Truy xuất | BM25 + ChromaDB (bge-m3) hợp nhất bằng RRF, `c = 60`, trọng số 0.5/0.5 | `README.md` mục 1 |
| Generator | Gemini `gemini-2.5-flash` (temperature 0) + fallback Local Qwen + Soft Refusal | `README.md` mục 1, 5.2 |
| Bộ chỉ số | Hit@3/5/6, MRR, Citation Precision/Recall/F1/Exact Match, Faithfulness | `README.md` mục 5.5 |
| Unit test | 85 test offline | `pytest --collect-only` ngày 2026-10-20 |
| Benchmark hiện có | 100 câu v2, đúng 12 khóa, 14 nhóm chủ đề | `data/evaluation/benchmark_100_questions_v2.json` |

### 3.2. Chất lượng pipeline hiện tại

Lượt chạy ngày 2026-10-18 trên benchmark v2 (100 câu), generator Local Qwen, Top-K 6, giám khảo tắt:

| Chỉ số | Giá trị |
|---|---|
| Hit@3 / Hit@5 / Hit@6 | 59.8% / 63.9% / 65.0% |
| MRR (recall window) | 0.5076 |
| Citation F1 | 78.1% |
| Number support (không cần API) | 94.3% |
| Bảo toàn thực thể sau chuẩn hóa | 96.7% |
| Từ chối đúng (3 câu ngoài corpus) | 0.0% — cả 3 câu bị ảo giác *(chú thích 2026-10-21: số liệu đo sai do bug fold marker — phép so `REFUSAL_MARKER in fold(answer)` không bao giờ khớp vì marker còn dấu thanh; đã sửa 2026-10-21 trong P4.1, số thật sẽ có ở P4)* |

Nguồn: `outputs/evaluation_summary.md`, lượt 2026-10-18T08:34:35.

> Đây là mốc tham chiếu tạm thời: lượt chạy dùng generator Local Qwen và tắt giám khảo nên các chỉ số Citation/Faithfulness không đại diện cho pipeline Gemini. P0.2 sẽ ghim baseline chính thức (cùng generator, cùng Top-K, `ENABLE_CLASSIFIER=0`) trên benchmark v3 trước khi chạy A/B.

### 3.3. Đánh đổi giữa các chiến lược chunking

Lượt chạy ngày 2026-10-17 trên benchmark 50 câu, generator Local Qwen, Top-K 3, cửa sổ đo Hit@6 = 6:

| Chiến lược | Số chunk | Hit@3 | Hit@5 | Hit@6 | MRR | Citation F1 |
|---|---|---|---|---|---|---|
| fixed | 182 | 0.8800 | 0.9000 | 0.9000 | 0.6983 | 0.0000 |
| recursive | 189 | 0.7400 | 0.8800 | 0.9000 | 0.6687 | 0.0067 |
| structure | 378 | 0.7600 | 0.8800 | 0.9200 | 0.7160 | 0.0767 |

Nguồn: `logs/benchmark/summary_comparison_report.md`, lượt 2026-10-17 23:36:01.

> Citation F1 thấp do generator Local Qwen 1.5B — chỉ nên đọc bảng này để so sánh tương đối giữa ba chiến lược. Kết quả cho thấy mỗi cấu hình mạnh ở một nhóm chỉ số khác nhau (fixed mạnh Hit@3, structure mạnh MRR/Hit@6), là động lực để router chọn cấu hình truy xuất theo lớp câu thay vì dùng một cấu hình chung.

## 4. Phạm vi làm lại

| Hạng mục | Sản phẩm | Nội dung |
|---|---|---|
| Bộ phân loại 2 nhãn | `src/classifier.py` | Qwen few-shot trả `category` (14 nhóm) + `question_type` (4 nhãn cố định); guardrail 3 lớp; phân loại lỗi thì suy giảm mềm (nhãn dự phòng/cấu hình chung), không làm chết pipeline |
| Router truy xuất | `src/router.py` | Ánh xạ cặp nhãn → cấu hình truy xuất (số chunk, trọng số RRF, mở rộng truy vấn, bộ lọc tầng tài liệu…); cấu hình chung vẫn là đường lùi |
| Tách truy vấn con cho câu so sánh | Module/pipeline hiện có, chốt ở P3.3 | Tách câu `SO_SANH` thành các vế và truy xuất đủ ngữ cảnh cho từng vế trước khi tổng hợp |
| Prompt biến thể theo loại câu | `src/generator.py` | Prompt khác nhau cho 4 loại câu; `NGOAI_PHAM_VI` chỉ nhắc từ chối thêm, **không bỏ qua truy xuất** để tránh từ chối oan câu đúng |
| Đánh giá A/B + chỉ số phân loại | `src/evaluation.py` | Cờ `--with-classifier`; thống kê kết quả theo nhóm chủ đề/loại câu; đo accuracy, confusion matrix của bộ phân loại |
| Demo hiển thị nhãn | CLI, `ui/app.py`, `demo_streamlit.py` | Hiển thị 2 nhãn và cấu hình truy xuất đã chọn ở chế độ bật classifier |
| Công tắc an toàn | `ENABLE_CLASSIFIER` | `0` = giữ hành vi pipeline cũ nguyên vẹn 100%; `1` = bật classifier + router. Đề xuất mặc định `0`, P0.3 chốt khi khai báo |

Nguồn phạm vi: `prompts/P0_1_direction_doc.md` (mục "Phạm vi làm lại") và `prompts/README.md`; số liệu tái sử dụng lấy từ `README.md` và kiểm tra trực tiếp ngày 2026-10-20.

**Tái sử dụng nguyên vẹn, không làm lại:** corpus 26 tài liệu, index 361 chunks, hybrid search BM25 + Chroma, generator trích dẫn Điều/Khoản + Soft Refusal, bộ chỉ số Hit@K/MRR/Citation/Faithfulness, 85 unit test hiện có. Benchmark v2 được nâng thành v3 bằng cách thêm khóa `question_type`, không đổi câu hỏi và ground truth.

## 5. Ngoài phạm vi

- Không đổi model OCR, không xử lý lại chất lượng dấu thanh của corpus.
- Không train mới hoặc fine-tune embedding (giữ `BAAI/bge-m3`).
- Không đổi vector database (giữ ChromaDB).
- Không mở rộng corpus ra tài liệu ngoài quy chế học vụ AGU.

Mọi đề xuất vượt bốn mục trên cần người dùng duyệt riêng trước khi đưa vào kế hoạch.

## 6. Tiêu chí thành công định lượng

| Tiêu chí | Ngưỡng | Đo tại |
|---|---|---|
| Accuracy nhãn chủ đề | ≥ 85% trên 100 câu v3 | P2.3, log trong `logs/classifier/` |
| Accuracy nhãn loại câu hỏi | ≥ 80% trên 100 câu v3 | P2.3, log trong `logs/classifier/` |
| Recall lớp thiểu số | Mỗi lớp `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI` ≥ 50% — bổ sung 2026-10-20 vì TRA_CUU chiếm 85% khiến accuracy tổng không đủ chứng minh | P2.3, log trong `logs/classifier/` |
| A/B tổng thể | Hit@K và MRR không giảm quá **5% tương đối** so với baseline `ENABLE_CLASSIFIER=0`; ngưỡng chính thức chốt tại P4.3 | P4.3 |
| Nhóm câu cải thiện | Ít nhất 1–2 nhóm câu tăng rõ, báo cáo cả chênh lệch tuyệt đối và tương đối | P4.3 |
| Unit test | Toàn bộ test xanh, chạy offline hoàn toàn, không tốn quota | P2.2, P3.2, P4.1 |
| Bất biến tương thích | `ENABLE_CLASSIFIER=0` cho hành vi pipeline cũ nguyên vẹn 100% | P3.2, P5.4 |

Nguồn ngưỡng: `prompts/P0_1_direction_doc.md` và `prompts/README.md` (mục "Các điểm BẠN phải quyết"). Ngưỡng 5% tương đối là đề xuất, sẽ chốt cùng người dùng tại P4.3.

## 7. Kế hoạch 6 giai đoạn

| GĐ | Thời lượng | Nội dung chính | Sản phẩm / cổng |
|---|---|---|---|
| 0 — Chốt hướng & mốc so sánh | 2–3 ngày | Chốt ROADMAP, ghim baseline số liệu pipeline cũ, khai báo `ENABLE_CLASSIFIER` | ROADMAP (duyệt) · baseline snapshot · feature flag |
| 1 — Thiết kế bộ nhãn | 3–5 ngày | `TAXONOMY.md` (14 chủ đề + 4 loại + luật gán); gán nhãn 100 câu → benchmark v3; verify độc lập | TAXONOMY (duyệt) · bảng nhãn v3 (duyệt) · GATE verify 100% |
| 2 — Bộ phân loại v1 | 1–2 tuần | `src/classifier.py` Qwen few-shot + guardrail; unit test offline; đo accuracy 100 câu | GATE: chủ đề ≥ 85% và loại câu ≥ 80% |
| 3 — Router truy xuất theo lớp | 1–2 tuần | `src/router.py`, tích hợp qua feature flag, tách truy vấn con cho `SO_SANH`, prompt theo loại câu, hiển thị nhãn ở CLI/GUI | pytest + smoke 2 chế độ (bật/tắt) |
| 4 — Đánh giá A/B | 1 tuần | Cờ `--with-classifier`, chạy 2 lượt 100 câu trên v3, bảng so sánh + biểu đồ + nhận xét | P4.2 duyệt kế hoạch quota (~400 request, giảm nhờ cache) · GATE không tụt quá 5% tương đối |
| 5 — Demo & báo cáo | 1–2 tuần | Demo Streamlit hiển thị nhãn, `SYSTEM_ARCHITECTURE.md` 6 tầng, chương 3–4, README chốt | GATE cuối: smoke xanh |

## 7b. Giai đoạn P5 — Vòng lặp tự kiểm chứng & tự huấn luyện (thêm 2026-10-23)

Mục tiêu chuyển từ "đo điểm trung bình" sang "không được bịa": một bộ test khổng lồ
có đáp án **trích nguyên văn từ tài liệu**, một trọng tài deterministic, và một cổng
duyệt khiến mọi thay đổi phải chứng minh không làm tăng bịa đặt mới được giữ.

| Bước | Nội dung | Sản phẩm / cổng | Trạng thái 23-10 |
|---|---|---|---|
| P5.1 | Ngân hàng câu hỏi neo bằng chứng, chia theo văn bản, hai kho mẫu tách rời | `data/loop/testset_v1.jsonl` (811 item: 407 test / 404 trainpool), manifest + fingerprint corpus | XONG |
| P5.2 | Tầng kiểm chứng thực thể dùng chung cho guardrail và trọng tài | `src/answer_guard.py` + `ENABLE_ANSWER_GUARD` (mặc định TẮT), 45 unit test | XONG |
| P5.3 | Audit trọng tài trên dữ liệu cũ để chắc chắn nó không báo động giả | `tools/loop/audit_guard.py`; kết quả: 16→11/50 câu bị flag sau khi loại marker số thứ tự, 0 FABRICATED bị mất, 9/50 câu bịa thật (18%) | XONG |
| P5.4 | Runner 2 pha (retrieval rẻ / full đắt) + bản đồ lỗi theo tầng | `tools/loop/run_round.py`, `verify.py`, `triage.py` | XONG code; r0 đang chạy |
| P5.5 | Cổng duyệt không suy giảm, chỉ so trên item chung + kiểm tra cùng cấu hình | `tools/loop/gate.py`, exit 0/1, 20 unit test | XONG |
| P5.6 | Round r0 (đo hiện trạng) → triage → round r1 sửa ĐÚNG lever | `data/loop/rounds/r0/*`, `triage_report.md` | XONG cả hai pha + triage (811 truy xuất / 100 sinh) |
| P5.7 | Sửa lever truy xuất phát hiện từ r0: router lọc MỀM theo nguồn | `src/router.py::rescore_with_source_preference`, cờ `ROUTER_SOFT_FILTER` (mặc định TẮT), test router + pipeline | XONG code; **cổng r1 CHẶN** (xem P5.11) |
| P5.8 | Máy quy lỗi truy xuất theo tầng (để biết sửa gì trước) | `tools/loop/attribute.py` + `attribution_retrieval.json`, 18 unit test | XONG |
| P5.9 | Dụng cụ đo không tự lừa mình: chữ ký trọng tài, mẫu số recall, rule không đo được = CẤM | `verify.referee_fingerprint()`, `gate.metrics/compare`, `attribute --compare` | XONG |
| P5.10 | Ba lỗ do lường lộ ra khi số thật va nhau: id trùng, tập đo phình khi chạy lại, neo HUMAN vô hình ở pha rẻ | `testset.resolve_id_collisions`, `run_round.plan_subset`+`compact_rows`, `verify.expected_source_in_window` + luật `human_anchor_source_not_degraded` | XONG — 500 unit test |
| P5.11 | Cổng r1 chặn lever lọc mềm → dò lại trục bonus | round `r2` (811 item, `ROUTER_FILTER_RANK_BONUS=12`), hai cổng r2-vs-r0 và r2-vs-r1 | XONG 23-10: r2-vs-r0 **ĐẠT** (gold@6 51,86%→74,00%, neo HUMAN giữ 81,44%); r2-vs-r1 **KHÔNG ĐẠT** (mua neo bằng gold@6). Mặc định giữ bonus=3; lever kế tiếp = **hạn ngạch nguồn** |
| P5.12 | Truy thủ phạm over-refusal (lớp lỗi lớn nhất của pha sinh) + vá lỗ triage "không sinh dòng train" | `tmp/probe_overrefusal.py`, `tmp/probe_prompt_window.py`, `triage.lever_for`/`blocks_for_sft`/`target_fragments`, bất biến 7 | XONG — 16 test triage, 519 unit test toàn repo |
| P5.13 | Lever tầng sinh: cứu câu từ chối oan bằng lượt yêu cầu trích xuất, vẫn qua `check_grounding` | `src/generator.py::QwenGenerator._rescue_refusal` + `demands_specific_value`, cờ `ENABLE_ANSWER_RESCUE` (mặc định TẮT), `tests/test_answer_rescue.py` (16 test) | Code + test XONG; A/B 4 biến thể prompt XONG; điều kiện kích hoạt đo lại XONG (37/38, luật cũ 22/38); round `r3` **KHÔNG ĐẠT** — xem P5.15 để biết vì sao số đó chưa có giá trị |
| P5.14 | Lever truy xuất kế tiếp: **hạn ngạch nguồn** trong cửa sổ thay vì chỉnh con số bonus | `src/router.py::apply_source_quota` + cờ `ROUTER_SOURCE_QUOTA` (mặc định 0 = TẮT), `src/pipeline.py` nối vào nhánh lọc mềm, 6 test router + 1 test pipeline | Code + test XONG (528 unit test toàn repo); round `r4` (bonus 12 + quota 4) đã đo đủ 811 item: hai cổng ĐẠT nhưng gold@6 chỉ +0,29 (0,7400→0,7429), **giả thuyết cấu trúc bị bác** — chốt mặc định bonus 12, quota OFF, không thêm lever truy xuất (chi tiết P5.14) |
| P5.15 | Rescue v2: chỉ dẫn trích xuất mạnh hơn (ví dụ BỊA), ngưỡng nhận 0,8, và mọi lượt THỬ phải đếm được | `RESCUE_INSTRUCTION` mới, `rescue_min_score()` + cờ `RESCUE_MIN_SCORE` (mặc định 0,8), log `[AnswerRescue] Đã thử lượt trích xuất…`, `tests/test_answer_rescue.py` (20 test) | Code + test XONG; **bổ sung P5.15b**: điều kiện kích hoạt xét trên CẢ câu gốc (`raw_query` xuống generator) vì bản chuẩn hóa có thể là một câu khác; r5 (bonus 3, quota 0) **6/7 quy tắc cổng ĐẠT vs r1** — chỉ `refusal_rate_bounded` vi phạm, fabrication giảm, PASS_CORRECT 10→14, HALLUCINATED về 2; số lượt thử bị mất ở r5 (lệnh bọc `| tail -60`) đã **đo lại đủ trong `r5b`: 60 lượt thử, 1 câu cứu được (1,7%)** ⇒ quy tắc đăng ký trước áp dụng, **lever rescue BỊ BÁC vĩnh viễn**, giữ code + test làm bằng chứng, mặc định TẮT (chi tiết P5.15c) |
| P5.16 | Bản kiểm chứng đầu ra bộ chuẩn hóa câu hỏi: bắt hai mode hỏng đo thật (echo few-shot / tự trả lời) | `src/query_normalizer.py::normalized_output_rejection` + cờ `NORMALIZE_SANITY_GUARD` (mặc định TẮT), ngưỡng `NORMALIZE_MIN_CONTAINMENT` (0,3 chốt theo phân bố 300 lượt), `tests/test_query_normalizer_guard.py` (27 test) | Code + test XONG (**563 unit test toàn repo**); **round `r6` ĐÃ ĐO (một biến số, nền r1): 5/100 ca bị bác = đúng tần suất đăng ký trước, cả 5 item lấy lại chunk vàng vào cửa sổ, `PASS_CORRECT` 10→14, gold@k 0,6875→0,7875, fabrication giảm, refusal 0,72→0,64 ⇒ lever ĐƯỢC chứng minh** (chi tiết P5.16); bật làm mặc định production **chờ user duyệt** |
| P5.17 | Round tổ hợp r7: đường chốt truy xuất (bonus 12) + lever chuẩn hóa, không rescue | `tmp/r7_driver.sh`, `rounds/r7/`, `rounds/r7/combo_tally.txt` | **ĐO XONG 24-10**: 6/7 quy tắc ĐẠT cả hai cổng, chỉ veto vì trần refusal tuyệt đối; **chênh r7-vs-r6 nằm trong băng nhiễu ±3** ⇒ bonus 12 không xác nhận cũng không bác khi đã bật guard; guard tái lập **5/5 ca trùng khít với r6**; 2 ca `PASS_CORRECT` → từ chối oan vì bonus đẩy chunk cần thiết ra cửa sổ. Câu hỏi "bonus 3 hay 12" chuyển sang lặp lại/tăng cỡ mẫu (chi tiết P5.17) |
| P5.18 | T3 đòn bẩy 1+2: bỏ đường từ chối khỏi prompt, quyền từ chối chuyển xuống tầng ngoài deterministic (5 luật, ngưỡng đăng ký trước) | `src/refusal_policy.py` + `EXTRACT_ONLY_HEAD`/`effective_prompt_version()` trong `src/generator.py` + `_collect_leg_ranks`/luật trong `src/pipeline.py`, cờ `ENABLE_DECOUPLED_REFUSAL` (mặc định TẮT), `tests/test_decoupled_refusal.py` (24 hàm/29 case), round `r8` | **ĐO XONG 24-10 — KHÔNG ĐẠT** (`PASS_CORRECT` 19 < 25; fabrication 1→0 là vế duy nhất đạt): refusal **0,69→0,28** (dưới trần 0,35 lần đầu trong chuỗi r), `FAIL_OVERREFUSAL` **37→23**, +16 câu từ over-refusal thành đúng, nhưng **`PASS_REFUSAL` 17→2** ⇒ 12 câu ngoài phạm vi được trả lời sai + 4 ca tiền giả sai, `pass_rate` 0,31→0,21, cổng veto ở 5 quy tắc. **Năm luật chỉ hai luật bắt** (rank 25, refusal-marker 3); `no_evidence`/`off_topic_window`/`ungrounded` = 0 vì grounding ≡ 1,0 với prompt trích xuất ⇒ tầng ngoài mù với "có căn cứ nhưng lạc đề". Giữ cờ TẮT, code + test + round giữ làm bằng chứng (chi tiết P5.18) |
| P5.19 | T3 đòn bẩy 3: extract-then-generate — cửa sổ sinh là 3–5 CÂU bằng chứng thay vì ~7k ký tự | `src/evidence_selection.py` (bậc thang thực thể→keyword→tên nguồn→reranker, metadata sao nguyên vẹn) + móc trong `src/pipeline.py`, cờ `ENABLE_EVIDENCE_SELECTION` (mặc định TẮT), `tests/test_evidence_selection.py` (18 case), round `r9` | **ĐO XONG 24-10 — KẾT QUẢ ÂM**: phần pre giống hệt r8 (25 từ chối, gold@k 0,7125 không đổi ⇒ phép một biến đúng), nhưng 75/75 cửa sổ đều **đúng 5 câu** (6898→1022 ký tự) làm `model_still_refuses` **3→32**, refusal **0,28→0,57** (vượt trần), `FAIL_OVERREFUSAL` 23→35, CLOZE_OCR `PASS_CORRECT` **8→3**, p95 **19,93→33,27 s (+67%)**; `PASS_CORRECT` đi ngang 19 nhưng tập câu khác (giao nhau 11 id). Reranker lùi bi-encoder `bge-m3` (cross-encoder không tải được) — đã ghi trong `settings.evidence_reranker`. Không chỉnh ngưỡng `EV_*`; không đo lại trước khi corpus có dấu / model sinh mạnh hơn (chi tiết P5.19) |
| P5.20 | T4a: generator 3B trên đúng máy triển khai (một biến = model sinh) + T4b pipeline dữ liệu SFT/chi phí bộ nhớ | cờ `GENERATOR_OLLAMA_MODEL` (`src/generator.py`, `src/pipeline.py`), manifest `generator_status` (`tools/loop/run_round.py`), `tests/test_loop_generator_model_flag.py` (11 case), round `r10` (100 item, cache lạnh `tmp/loop_gen_cache_r10`), `tools/build_sft_from_round.py` + `data/training/t4b_r5r8r9r10/`, `tools/diag/{t4_stats,one_variable_check,qlora_memory_probe}.py` | **ĐO XONG 24-10 — 3B KHÔNG đạt ngưỡng đã đăng ký trước** (`PASS_CORRECT` 14→16 < 22; McNemar p = 0,804, CI delta [−0,06; +0,10] chứa 0) trong khi p95 **18,65→34,12 s (+83%)**, model 2,3 GB **100% GPU**, không offload; refusal 0,69→0,75, fabrication 0,0323→0,0. `one_variable_check`: 100/100 item giống nhau từng ký tự ở `contexts`/`sources`/`normalized_query`/`labels`/`retrieval_config`. ⇒ **giữ 1,5B, không mở round Qwen3-4B** (điều khoản: chỉ mở nếu 3B cải thiện). 4b: **trần train đo được của card 4 GB ≈ 1.000 token/dòng** (960 → 3.931,0 MiB; 1.024 → 4.156,9 MiB; gradient checkpointing không giúp) trong khi **13/13 dòng train ≥ 1.016 token** ⇒ cần duyệt PA-11 (4-bit) / PA-12 (đổi định dạng dữ liệu). Chi tiết: `docs/reports/T4.md` |
| P5.21 | T5a: reranker cross-encoder trên pool 20 RRF → top-6 (bge-reranker-v2-m3, GPU riêng `venv_gpu`) | `src/reranker.py` (`ENABLE_RERANKER`, `RERANKER_*`, mặc định TẮT), nối trong `src/pipeline.py`, `tests/test_reranker_flag.py` + `tests/test_t5_reranker_contract.py` (46 case), round `r12`, `tools/diag/reranker_cost_probe.py` | **ĐO XONG 25-10 — KẾT LUẬN ÂM, giữ cờ TẮT**: gold@6 **0,7400→0,6686** (delta −0,0714 CI [−0,1014; −0,0414], McNemar 83 mất/33 được **p = 3,9e−06**), EXACT **0,2115→0,0385**, TRAP→0, neo HUMAN 0,8144→0,7010, `FAIL_RETRIEVAL` 182→232, cổng **6/8 kiểm tra vi phạm**; round thật **≈66 phút** (median 4,74 s/item — vượt ngưỡng tự đặt 60 phút, đính chính ở T5.md §2.6). Nguyên nhân đo được: `score_pairs` chấm `fold(query)` với passage còn dấu (0/30 chunk vàng vào top-6 so với 28/30 khi dùng query nguyên văn) ⇒ **PA-25** chờ duyệt để bỏ fold + chạy r14. Trần oracle pool-20 = 0,8871. Chi tiết: `docs/reports/T5.md` |
| P5.22 | T5b: contextual chunk header `[tên file] - [Điều/Khoản]` trong ngữ cảnh sinh | `ENABLE_CONTEXTUAL_HEADER` (mặc định TẮT), metadata header dựng sẵn cho 253/361 chunk, `tests/test_t5_contextual_header.py`, round `r13` | **ĐO XONG 25-10 — KHÔNG CÓ TÍN HIỆU**: gold@6 **0,7371**, delta **−0,0028** CI [−0,0129; +0,0071] (chứa 0), McNemar **p = 0,79**, EXACT +1 item; cổng **6/6 kiểm tra ĐẠT**. Phạm vi can thiệp thật nhỏ vì header `[file] - [Điều]` đã có sẵn ở 253/361 chunk; phần còn lại là Chương/Khoản + 108 chunk fallback. Có **lệch thiết kế đã ghi** (chạy trên `chroma_db` cũ thay vì index header riêng — PA-21/PA-22). Chi tiết: `docs/reports/T5.md` §5 |
| P5.23 | T7: tái lập một chuỗi round bằng một lệnh + sổ quyết định + khóa chính sách trong cache sinh | `tools/loop/run_chain.{py,ps1,sh}` + `chains/*.json` (dry-run, manifest tất định, preflight, không ghi đè round), `tests/test_run_chain.py` (11 test), `src/cache_policy.py` + `tests/test_cache_policy.py` (26 test), `docs/DECISION_LOG.md`, mục README 5.10 + 8.1 | **XONG TRONG WORKING TREE 25-10**: `run_chain` chạy end-to-end chuỗi demo 2 round × 20 item + gate + attribute; mutation run_chain **6/6**, cache policy **10/10** bị bắt; toàn repo **1.004 passed**. Cache sinh chỉ thêm trường `policy` khi ngưỡng lệch mặc định ⇒ cờ TẮT giữ khóa cũ từng byte. **Chưa commit được**: 41 file nguồn/công cụ/test chưa tracked + 6 file sửa dở ⇒ **PA-26** (commit freeze) chờ duyệt |

### P5.12 — over-refusal đến từ tầng nào (23-10, 100 item pha sinh)

`FAIL_OVERREFUSAL` chiếm 38/100 câu ở r1 (và 35/100 ở r0) — lớn hơn hẳn lớp bịa đặt
(1 câu). Bốn phép đo nối tiếp nhau loại trừ dần, tất cả chạy trên dữ liệu đã lưu,
không gọi model:

| Probe | Kết quả | Suy ra |
|---|---|---|
| `check_grounding(câu vàng, đúng ngữ cảnh đã lưu)` | 37/38 ca câu vàng **đi qua** trọng tài | guardrail không buộc phải chặn |
| mô phỏng cắt block 1600 / tổng 10000 ký tự | 35/35 ca câu vàng còn nguyên trong prompt | không phải do prompt cắt mất căn cứ |
| nhãn classifier trên chính 38 ca | 34 ca `TRA_CUU`, giống hóm trả lời đúng | không phải do phân loại ngoài phạm vi |
| replay 38 ca với `ENABLE_ANSWER_GUARD=0` | **31 ca model tự nói "không đủ thông tin"**, 4 ca trả lời nhưng bản nháp lệch căn cứ, 3 ca lẽ ra được chấp nhận | thủ phạm chính là **tầng sinh** |

Vị trí căn cứ trong prompt: 13/35 ca nằm ngay block `[1]`, 26/35 trong ba block đầu —
tức model nhìn thấy đáp án nguyên văn mà vẫn từ chối. Ngược lại, toàn bộ câu *nên* từ
chối đều xử lý đúng: 6/6 câu "thiếu tài liệu", 8/8 câu bẫy (TRAP/TRAP_OCR), 5/7 câu
ngoài phạm vi. Hệ mất điểm vì overly an toàn, không vì bịa.

Lỗ vòng lặp lộ ra kèm theo: `triage.py` gộp mọi `FAIL_OVERREFUSAL` về lever
`guardrail` rồi `continue`, nên lớp lỗi lớn nhất **không sinh ra một dòng train nào**.
Nay `lever_for()` dùng bằng chứng `gold_in_top_k` để tách hai ca: thấy-căn cứ-mà-vẫn-
từ-chối → `generation` (có SFT row), chưa chứng minh được căn cứ → `guardrail` (chỉ ghi
báo cáo, vì dạy "từ chối" khi chưa thấy căn cứ là dạy sai). Số thật sau khi sửa:

| Round | `sft_extractive` | trong đó từ over-refusal | `overrefusal_threshold_only` | `skip_sft_target_not_in_context` |
|---|---|---|---|---|
| r0 | 16 | 12 | 1 | 6 |
| r1 | 15 | 12 | 3 | 4 |

Kèm theo là bất biến mới thứ bảy của vòng lặp: ngữ cảnh của một dòng SFT **phải chứa**
đáp án của chính nó (`blocks_for_sft` ưu tiên chunk vàng thay vì cắt `contexts[:4]` mù;
`target_fragments` bỏ dòng không đạt). Không có luật này thì vòng lặp tự sản xuất dữ
liệu dạy model bịa.


### P5.13 — A/B bốn biến thể prompt sinh (23-10, 13 id gọi model thật)

Replay đúng 10 ca `FAIL_OVERREFUSAL` có câu vàng nguyên văn trong prompt + 3 ca điều
khiển **bắt buộc vẫn phải từ chối** (`PASS_REFUSAL`), mỗi ca chạy 4 head prompt trên
`qwen2.5:1.5b-instruct`, temp 0.1, không dùng cache (52 lượt gọi, ~8 s/lượt). Chấm bằng
chính hàm của vòng lặp (`_answer_covers_gold`, `check_grounding`).

| Biến thể | còn từ chối (/10) | đúng vàng **và** qua guard | bản nháp bị guard bác | control vẫn từ chối (/3) |
|---|---|---|---|---|
| `V0` prompt hiện hành | 7 | 2 | 0 | 3 |
| `V1` bỏ câu mồi từ chối | 5 | 1 | 2 | 3 |
| `V2` chỉ đưa 3 block đầu | 8 | 1 | 1 | 3 |
| `V3` chỉ dẫn TRÍCH XUẤT + 1 ví dụ | **0** | **3** | 2 | 2 |

Hai chuyện phải nói thẳng trước khi tin bảng này:

- **Bản thân dụng cụ đo từng sai:** `refused` của probe so chuỗi *có dấu*
  "không đủ thông tin" với text đã `fold()`, nên không bao giờ khớp — 25/52 dòng bị gắn
  nhầm `refused=False` (model viết "Xin lỗi, tài liệu hiện có không đủ thông tin…").
  Bảng trên là số đã chấm lại với kim cũng được `fold()`. Production và trọng tài **không
  dính lỗi này** (`src/generator.py::looks_like_refusal` dùng kim không dấu;
  `verify.REFUSAL_MARKERS_FOLDED` likewise), nên verdict r0/r1/r2 vẫn nguyên giá trị.
- **`V3` có một ca nhiễm mồi:** ví dụ few-shot của nó lấy đúng văn bản là đáp án vàng của
  item `T24199159682252` ("1.169.000 đồng mỗi tín chỉ"), nên 1 trong 3 ca "đúng + qua
  guard" của `V3` có thể là do mồi chứ không phải do chỉ dẫn.

Đọc theo số: `V3` xóa sạch hiện tượng từ chối oan (7/10 → 0/10) nhưng chỉ đổi được **+1**
câu đúng thật sự ở n=10, và làm rơi 1/3 câu điều khiển (model trả lời "Không, không đúng"
cho một câu bẫy). Cái hay là **trọng tài bắt được cả hai bản nháp sai đó** (guard bác 2/10
ca `V3`) — đúng tình huống mà `_rescue_refusal` được thiết kế: chỉ nhận câu cứu khi
`check_grounding` đồng ý, nên câu mất từ chối ở control bị trả lại lời từ chối gốc.

Vì vậy quyết định là **không thay prompt hệ thống bằng `V3`** (lợi ích nằm trong nhiễu,
rủi ro mất khả năng từ chối), mà giữ `V3` làm *yêu cầu trích xuất một lượt sau khi đã từ
chối*, mặc định TẮT, và để round `r3` + cổng r3-vs-r1 quyết định bằng 100 item thật.

**Điều kiện kích hoạt của lever đã đo lại trên 100 item r1 (không gọi model):** luật chữ
`demands_specific_value` bản đầu chỉ phủ 22/38 ca over-refusal — nó bỏ sót đúng các mẫu
có sẵn trong test bank ("Điền giá trị còn thiếu…", "Cho biết…", "… có đúng theo quy
định", "nằm trong"). Nay danh sách kim viết không dấu (so qua `fold()`, cùng chiều với
`looks_like_refusal`) phủ:

| Nhóm item | n | đủ điều kiện cứu (luật mới) | (luật cũ) |
|---|---|---|---|
| `FAIL_OVERREFUSAL` | 38 | **37** | 22 |
| `PASS_REFUSAL` (từ chối ĐÚNG) | 19 | 16 | 1 |
| `FAIL_RETRIEVAL` | 23 | 23 | 13 |

Giá phải trả ghi thẳng vào thiết kế: 16/19 ca từ chối đúng cũng đủ điều kiện, nên lever
thêm ~16 lượt gọi model trên 100 câu và **chỉ an toàn vì ứng viên cứu phải qua
`check_grounding`**; ri ro thật là chuyển thành `FAIL_HALLUCINATED_ON_UNANSWERABLE`,
tức đúng cái cổng r3-vs-r1 canh. Ba ca TRAP "… là 1232000 phải không?" được COC Y để
ngoài danh sách (thêm "phải không" là kéo câu bẫy vào đường cứu). `tests/test_answer_rescue.py`
(16 test) ghim cả hai biên này.

**Tiêu chí cổng r3-vs-r1 đăng ký TRƯỚC khi chạy** (ghi ở đây để không tự biện minh sau
khi thấy số): `PASS_REFUSAL` không giảm; `FAIL_HALLUCINATED_ON_UNANSWERABLE` không tăng;
`FAIL_OVERREFUSAL` giảm; fabrication rate trên câu đã trả lời không tăng. Thiếu một trong
bốn điều kiện là lever BỊ từ chối, dù `PASS_CORRECT` có tăng.

**Kết quả r3 (23-10, 100 item pin từ r0, cache lạnh `tmp/loop_gen_cache_r3`, router giữ
đúng cấu hình r1 — chữ ký `9f1179ccab74`):** cổng `KHÔNG ĐẠT`, đúng hai điều kiện đã đăng
ký trước.

| Chỉ số | r1 | r3 | |
|---|---|---|---|
| `PASS_CORRECT` | 10 | **16** | ✓ |
| `FAIL_OVERREFUSAL` | 38 | **32** | ✓ |
| fabrication rate trên câu đã trả lời | 3,57% | **2,56%** | ✓ |
| `PASS_REFUSAL` | 19 | **15** | ✗ |
| `FAIL_HALLUCINATED_ON_UNANSWERABLE` | 2 | **3** | ✗ (ngưỡng +0) |
| `refusal_rate` | 0,72 | 0,61 | (check `refusal_rate_bounded` là trần tuyệt đối 0,35 — r1 cũng đã vi phạm, không phải do lever) |

Điều làm cả bốn con số trên chỉ có giá trị một nửa: **đọc log của lượt chạy**
(`[AnswerRescue]` = 9 dòng: 7 câu được nhận, 2 câu ứng viên vẫn bị `check_grounding` bác —
"score=0.9 — Khoản 5", "score=0.6667 — 1059, 2020, Khoản 5, Điều 14") trong khi 60/61 câu
từ chối ĐỦ ĐIỀU KIỆN được cứu. Đối chiếu latency (p50 câu từ chối 15,5 s, chỉ 5 câu vượt
19,5 s ≈ hai lượt gọi) xác nhận: **luật mới chỉ thật sự phát ~9/60 lần**. Lý do nằm ở
đường im lặng của `_rescue_refusal` — ứng viên vẫn là lời từ chối thì trả lại từ chối mà
không ghi log. Nói cách khác lever chưa được đo đủ, chứ không phải đã đo và thua.

Tách hai việc: (1) `check_grounding` từ chối 2/9 ứng viên — lớp an toàn hoạt động đúng;
(2) chỉ dẫn trích xuất *dán thêm vào prompt cũ* hầu như không đổi được ý model, khác với
đầu prompt viết lại hẳn của `V3` trong A/B. Bản sửa vì vậy nhắm vào (2): chỉ dẫn mạnh hơn
nhưng ví dụ phải **bịa sẵn** (số tổng hợp, tên file giả) — bài học từ ca `V3` nhiễm mồi,
ví dụ lấy từ corpus thật đã chép đúng đáp án vàng của một item. Kèm theo là ngưỡng nhận
chặt hơn ngưỡng sản xuất (`unsupported` rỗng **và** score ≥ 0,8 thay vì 0,6) vì chính một
ca `PASS_REFUSAL` bị cứu thành `FAIL_HALLUCINATED_ON_UNANSWERABLE`.


### P5.14 — hạn ngạch nguồn: sửa cấu trúc, không sửa con số (23-10)

r2 chứng minh một knob toàn cục chỉ ĐỔI chỉ số này lấy chỉ số khác, và probe 21/21 item
hồi quy trỏ vào cấu trúc: ở bonus=12, MỘT nguồn chiếm trọn cửa sổ. `apply_source_quota`
đổi luật thành "không nguồn nào quá `quota` suất trong danh sách ứng viên; phần hoãn nối
vào cuối theo thứ tự cũ" — mất ưu tiên, không mất suất (`ROUTER_SOURCE_QUOTA`, mặc định
0 = tắt hẳn, 6 test đơn vị + 1 test nối dây trong pipeline).

**Dự đoán đăng ký trước khi chạy r4** (bonus 12 + quota 4, cửa sổ 12 ô cho top_k 6):
neo HUMAN vẫn ≈ 81,44% vì luật đó đo "đúng nguồn *còn trong cửa sổ*", mà nguồn được ưu
tiên luôn giữ 4 suất đầu; gold@6 phải hồi phục về phía 76,57% của r1 vì 8 ô còn lại do
nguồn khác điền. Nếu r4 KHÔNG đạt cả hai cùng lúc thì giả thuyết cấu trúc sai — khi đó
mặc định được chốt bằng cổng r2-vs-r0 (bonus 12), không vẽ thêm lever.

**Bằng chứng lever thật sự chạy (đọc từ 236 dòng đầu của `r4/retrieval.jsonl`, lúc 21:35):**
phân bố "số suất tối đa của MỘT nguồn trong 12 ô cửa sổ" dồn ở giá trị 4 với r4 (128/236 item),
trong khi r2 chỉ 163/811 và **472/811 item có nguồn chiếm hơn 4 suất**; r4 chỉ còn **35**
item vượt ngưỡng. 35/35 đó đều có `source_filter` RỖNG — tức lever chỉ áp dụng ở nhánh router
chọn được nguồn (`src/pipeline.py:268` có `if config.source_filter:`), còn khi router không
gán nguồn thì RRF tự do và một file vẫn chiếm 5–6 ô (ví dụ `KH To chuc HK 261`, `367-QĐ-ĐU`).
Đây là lỗ HỞ CÓ THẬT, ghi lại để đọc đúng số r4: nếu neo HUMAN hồi phục mà gold@6 không hồi
phục về phía r1 thì nghi phạm số một là 92–229 item không có `source_filter`, không phải
giá trị quota. Chưa sửa code giữa chừng — đổi luật giữa một round đang chạy là tự hủy phép đo.

**Kịch bản rủi ro cho neo HUMAN, tính trên dữ liệu r2 TRƯỚC khi r4 xong (21:5x):** trong 97
item HUMAN ở r2 (bonus 12, chưa quota), có **8 item một nguồn chiếm trọn 12 ô** và 3 item
chiếm 10 ô; 13/97 item HUMAN không có `source_filter` (quota không áp dụng). Nghĩa là quota=4
sẽ cắt chính phần đuôi của nguồn đang chiếm cửa sổ — nếu văn bản vàng của neo nằm ở hạng 5–12
của nguồn đó thì nó RƠI, đúng chỗ r1 từng vấp. Cổng r4-vs-r2 vì vậy mới là phép thử thật của
giả thuyết "chia suất mà không mất suất", không phải con số gold@6.

**Kết quả r4 (811 item, pha truy xuất, chốt 23-10 22:02) — giả thuyết cấu trúc SAI:**

| chỉ số | r0 | r1 (bonus 3) | r2 (bonus 12) | r4 (bonus 12 + quota 4) |
|---|---|---|---|---|
| gold@6 | 0,5186 | **0,7657** | 0,7400 | 0,7429 |
| neo HUMAN đúng-nguồn-vào-cửa-sổ | — | mất neo (cổng CHẶN) | 0,8144 | 0,8144 |
| `FAIL_RETRIEVAL` | 337 | 164 | 182 | 180 |

Cả hai cổng đều ĐẠT: `r4-vs-r2` (gold@k 0,74→0,7429 trên 700 item có chunk vàng, ngưỡng −0,02;
neo 0,8144→0,8144 tức +0,00% tương đối, n=97; không family nào n≥8 giảm quá 0,10; hallucinated-refusal
0/0) và `r4-vs-r0` (gold@k 0,5186→0,7429). Tức quota **không làm hỏng gì** — đúng như thiết kế
"mất ưu tiên, không mất suất", neo giữ nguyên từng item.

Nhưng vế thứ hai của dự đoán không xảy ra: gold@6 chỉ nhích **+0,29 điểm** (0,7400→0,7429),
không hồi phục về phía 0,7657 của r1; cách biệt 2,28 điểm vẫn còn nguyên, và `FAIL_RETRIEVAL`
vẫn cao hơn r1 tới 16 item. Family cũng đúng kiểu "lấy chỉ số này đổi chỉ số khác" mà r2 đã
rút ra: `SOURCE_LOOKUP` 0,8529→0,8922 (+3,93) đổi lấy `CLOZE_OCR` 0,9709→0,9515 (−1,94),
4 family đứng yên. Máy quy lỗi `attribute.py --round r4 --compare r0` tiếp tục xác nhận hướng đã
biết (`filter_blocked_wrong_table` 65→20, `filter_blocked_wrong_topic` 179→60, "bị `source_filter`
cắt" còn 44,4% của `FAIL_RETRIEVAL`) nhưng phần còn lại tăng: `ranking_despite_filter` 35→42 (+7)
và `ranking_no_filter` 58→58 (+0) — hai nhóm này quota
không với tới (nhóm sau còn không có `source_filter` để áp dụng).

**Quy tắc đã đăng ký trước, áp dụng nguyên văn:** r4 đạt một vế (neo) nhưng không đạt vế kia
(gold hồi phục) ⇒ "giả thuyết cấu trúc sai — mặc định được chốt bằng cổng r2-vs-r0 (bonus 12),
không vẽ thêm lever". Chốt: **đường mặc định của tầng truy xuất là lọc mềm bonus 12, quota OFF
(0)**; `apply_source_quota` + `ROUTER_SOURCE_QUOTA` + 7 test được giữ lại như lever đã đo và đã
chứng minh vô hại, không bật. Ghi trung thực một ô chưa đo: tổ hợp *bonus 3 + quota 4* là tổ hợp
duy nhất còn trống mà dữ liệu r4 gợi ý (r1 gold cao hơn nhờ bonus yếu, mất neo ở đúng chỗ bonus
mạnh chữa được) — nhưng nó là **câu hỏi mở**, không biến thành một round đo thêm, vì chốt trên đã đóng
lever truy xuất. Một nghi phạm khác vẫn còn sống và thuộc tầng input, không phải tầng xếp hạng:
xem P5.16 (bản chuẩn hóa đôi khi là một câu khác, dính cả 5/23 ca `FAIL_RETRIEVAL` pha đắt của r1).


### P5.15 — rescue v2: sửa vì sao lever không chạy đủ (23-10)

r3 KHÔNG ĐẠT, nhưng đọc kỹ thì phần lớn 100 item **chưa hề được đo**: `_rescue_refusal`
có một đường im lặng (ứng viên vẫn là lời từ chối → trả lại từ chối, không log), nên
60/61 câu đủ điều kiện cứu chỉ để lại 9 dòng `[AnswerRescue]`, và đối chiếu latency (p50
câu từ chối 15,5 s trong khi 5 câu vượt 19,5 s ≈ hai lượt gọi) gợi ý ~9 lượt thử thật.
**Ghi chú hiệu chỉnh (đọc khối "bẫy đo lường" bên dưới):** chính suy luận latency đó về sau
KHÔNG đứng — lượt gọi thứ hai có thể rẻ vì KV prefix — nên "lever chưa được đo đủ" là giả
thuyết, chưa phải số đo; cái chắc chắn là v1 **không đếm được**.
Ba sửa đổi, tất cả vẫn sau cờ `ENABLE_ANSWER_RESCUE` mặc định TẮT:

- **Chỉ dẫn trích xuất viết lại theo hướng `V3` của A/B** (đổi nhiệm vụ từ "quyết định có
  đủ căn cứ không" sang "tìm và chép"), nhưng ví dụ mẫu dùng **số và tên file bịa**
  (`3.456.000`, `VD-quy-che-mau.pdf`) — bài học nhiễm mồi, và nhờ vậy model bắt chước mẫu
  là `check_grounding` tự chặn. Test `test_mẫu_trong_chỉ_dẫn_là_số_bịa…` ghim điều đó.
- **Ngưỡng nhận chặt hơn guardrail sản xuất**: không còn thực thể chưa căn cứ **và**
  điểm ≥ `max(ngưỡng guard, RESCUE_MIN_SCORE)` với mặc định 0,8, và `score is None` (câu
  không chứa khẳng định kiểm được) không còn được coi là "an toàn". Lý do đo được: ca
  `FAIL_HALLUCINATED_ON_UNANSWERABLE` thứ 3 của r3 là giá trị có thật trong ngữ cảnh nhưng
  sai đối tượng, lọt qua ngưỡng 0,60.
- **Mọi nhánh thất bại phải in dấu** để lần đo sau phân biệt được "lever thua" với
  "lever không chạy".

**Tiêu chí r5-vs-r1 đăng ký trước:** (1) số lượt THỬ đếm được từ log phải xấp xỉ số câu
từ chối đủ điều kiện — **68**, đo lại trên chính 100 item r1 với luật mới (xét `question`
HOẶC `raw_query`; 58 câu khớp cả hai, 7 chỉ câu gốc, 3 chỉ bản chuẩn hóa), không phải 9;
(2) `PASS_REFUSAL` không dưới 19; (3)
`FAIL_HALLUCINATED_ON_UNANSWERABLE` không vượt 2; (4) `FAIL_OVERREFUSAL` giảm so với 38;
(5) fabrication rate không tăng. Nếu (1) đạt mà (2) hoặc (3) hỏng thì lever bị **bỏ vĩnh
viên** — không đổ lỗi cho mẫu nữa.

Điều (1) còn có một bẫy đo lường phải ghi trước: 68 lượt thử nghĩa là thêm ~68 lần gọi
model trên 100 item, tức thời gian round dài ra gần hai lần và **đơn giá là tiền máy địa
phương, không phải quota Gemini**. Nếu số lượt thử thấp hơn nhiều mà `PASS_CORRECT` vẫn
tăng, phải nghi phép đo (cache ấm, đường im lặng còn sót) trước khi kết luận lever thắng.

**Bẫy đó vừa lộ ra trong 15 dòng đầu của r5 (23-10, lúc ~22:3x): latency KHÔNG phải dụng cụ
đếm lượt gọi.** 8/15 item là lời từ chối và **cả 8 đều đủ điều kiện cứu** (kiểm bằng
`demands_specific_value(raw hoặc normalized)` + `is_enough_evidence(contexts)` chạy trên
`src/generator.py`/`src/answer_guard.py` bản ship), nhưng latency chỉ 15,7–17,8 s — không có
cặp 2× (~30 s) nào. Cơ chế hợp lý nhất: prompt cứu = `prompt + RESCUE_INSTRUCTION`, tức là
**phần mở rộng đúng nghĩa của prompt vừa gửi**, nên Ollama tái dùng KV prefix và lượt thứ hai
chỉ tốn một phần decode (~1–2 s) thay vì prefill lại toàn bộ ngữ cảnh. Hệ quả phải nói cho thẳng:
**suy luận "r3 chỉ thử ~9/60 lượt" dựa trên latency là không đủ cơ sở** — con số 9 của r3 đến
từ số dòng log, mà bản v1 im lặng ở nhánh "model vẫn từ chối"; nếu lượt thứ hai rẻ thì phần
lớn 60 ứng viên CÓ THỂ đã được hỏi lại và bị từ chối ở đúng nhánh không log đó. Phép đếm
duy nhất được tin ở r5 là **số dòng `[AnswerRescue]`** (v2 bắt mọi nhánh in dấu), còn latency
chỉ còn giá trị tham chiếu. Sau r5 sẽ xác nhận cơ chế prefix-cache bằng `prompt_eval_count`
trong response Ollama (không đo chồng lên lúc round còn chạy, để tránh nhiễu GPU).

**P5.15b — vì sao 9/60, phần hai (23-10):** đọc lại `full.jsonl` của r3 bằng chính hàm
ship trong repo cho thấy con đường cứu còn bị chặn ở một chỗ nữa. `pipeline.run` truyền
`normalized_query` xuống generator (`src/pipeline.py:464`), và trên 61 câu từ chối của r3,
điều kiện "câu hỏi đòi một giá trị cụ thể" chỉ khớp **54/61** khi xét bản chuẩn hóa so với
**60/61** khi xét câu gốc — vì bản chuẩn hóa đôi khi KHÔNG CÒN LÀ CÂU HỎI ĐÓ (mục P5.16).
Sửa: `generate_answer(..., raw_query=None)` và `_rescue_refusal` xét điều kiện trên
`question` **hoặc** `raw_query`; prompt và cache key không đổi một ký tự nào (chỉ dùng để
quyết định có hỏi lại hay không). `GeminiGenerator` nhận cùng chữ ký cho giao diện
Generator nhất quán nhưng không dùng. Test: `TestXetDieuKienTrenCauHoiGoc` (3 test) +
`test_generator_nhan_ca_cau_hoi_goc_for_rescue` trong `tests/test_pipeline.py`.

**Cấu hình router cho r5 — sửa lại kế hoạch ghi ở task #20, vì kỷ luật một biến số (23-10):**
kế hoạch ban đầu nói "r5 chạy với router = quyết định chốt của r4 (bonus 12, quota OFF)". Làm
vậy sẽ đổi **hai** thứ một lúc so với baseline r1 (bonus 3→12 và rescue tắt→bật), và toàn bộ
tiêu chí đăng ký ở trên — 68 lượt thử, `PASS_REFUSAL ≥ 19`, `FAIL_OVERREFUSAL < 38` — vốn đo
lại trên đúng 100 item của **r1** với cửa sổ truy xuất bonus 3, sẽ mất nghĩa. r5 vì vậy chạy
`ROUTER_SOFT_FILTER=1 ROUTER_FILTER_RANK_BONUS=3` (giống r1 và r3 từng ký), không quota, và đổi
duy nhất `ENABLE_ANSWER_RESCUE` + `RESCUE_MIN_SCORE=0.8`. Nhờ đó có hai phép đọc một biến cùng
lúc: `r5-vs-r1` (lever tắt/bật) và `r5-vs-r3` (rescue v1/v2). Bonus 12 là mặc định truy xuất
được chốt riêng, đã qua cổng ở pha rẻ; đưa bonus 12 vào đường sinh là **round tổ hợp** sau khi
từng lever đứng một mình đã chốt — không phải việc của r5.

**Kết quả r5 (100 item pin từ r0, 23-10 22:4x, chữ ký `9f1179ccab74`, cache lạnh
`tmp/loop_gen_cache_r5`):**

| chỉ số | r1 (rescue OFF) | r3 (rescue v1) | r5 (rescue v2 + ngưỡng 0,8) |
|---|---|---|---|
| `PASS_CORRECT` | 10 | 16 | **14** |
| `PASS_REFUSAL` | 19 | 15 | **17** |
| `FAIL_OVERREFUSAL` | 38 | 32 | **37** |
| `FAIL_HALLUCINATED_ON_UNANSWERABLE` | 2 | 3 | **2** |
| `FAIL_FABRICATED` | 1 | 1 | **1** |
| refusal rate | 0,72 | 0,61 | **0,69** |
| số câu từ chối ĐỦ ĐIỀU KIỆN cứu (đo lại bằng hàm ship) | 68 | 56 | **64** |

Cổng `r5-vs-r1`: **6/7 quy tắc ĐẠT**, chỉ một quy tắc vi phạm — `refusal_rate_bounded`
(0,69 > trần tuyệt đối 0,35, mà chính baseline r1 cũng 0,72). Các quy tắc còn lại đều theo
chiều tốt hoặc trung tính: fabrication **giảm** 0,0357→0,0323, hallucinated-on-unanswerable
2/2, pass_rate 0,29→0,31, gold@k trong cửa sổ 0,6875→0,7375, neo HUMAN 0,4286→0,4286 (n=7),
không family nào giảm quá 0,10 (EXACT 0,00→0,25, NUMERIC 0,30→0,40, CLOZE +0,07). Cổng
`r5-vs-r3` vi phạm `fabrication_not_increased` 0,0256→0,0323 — **cùng đúng MỘT câu bịa**
(1/39 → 1/31), chỉ số tăng vì mẫu số câu đã trả lời nhỏ lại, không phải vì có thêm câu bịa.

**Ba điều phải nói thẳng, xếp theo mức độ quan trọng:**

1. **Lỗi dung cụ của chính người đo (tôi):** lệnh khởi động r5 được bọc trong `… | tail -60`,
   nên toàn bộ stdout per-item — trong đó có mọi dòng `[AnswerRescue]` — **đã bị ném đi**, không
   phải lever không in. Vì vậy **điều kiện (1) "đếm được ~68 lượt thử" chưa có số**, và quy tắc
   đã đăng ký trước ("nếu (1) đạt mà (2) hoặc (3) hỏng thì bỏ lever vĩnh viễn") **chưa được phép
   áp dụng**: chưa tách được "lever thua" khỏi "lever không chạy", tức đúng cái bẫy mà v2 sinh ra
   để tránh. r5b (bản chạy lại NGUYÊN VĂN cấu hình, cache `tmp/loop_gen_cache_r5b`, không bọc
   pipe) bù việc đếm đó và đồng thời đo **nhiễu của chính phép đo**: cùng một cấu hình hai lượt
   cho verdict lệch nhau bao nhiêu item trên 100 — con số đó quyết định chênh 2 câu `PASS_REFUSAL`
   (19→17) có ý nghĩa gì không.
2. **Điều kiện (2) hỏng đúng nghĩa đen** (17 < 19) nhưng (3) và (4) đạt (2 ≤ 2; 37 < 38). Với
   `PASS_CORRECT` 10→14 và `FAIL_HALLUCINATED_ON_UNANSWERABLE` của v1 (3) được kéo về 2, bức
   tranh hiện tại là *v2 an toàn hơn v1 và tốt hơn baseline về mọi quy tắc cổng trừ trần tuyệt đối*
   — chưa đủ để kết luận "lever vô dụng", cần số lượt thử từ r5b.
3. **`refusal_rate_bounded` là trần TUYỆT ĐỐI nên không round pha sinh nào vượt nổi** khi chính
   baseline 0,66–0,72: r0, r1, r3, r5 đều vi phạm cùng một dòng. Đây là lỗi thiết kế cổng chứ
   không phải kết luận về lever — sửa thành quy tắc **tương đối** ("không tăng so với baseline")
   và giữ trần tuyệt đối làm cảnh báo là thay đổi dụng cụ ra quyết định, nên **đang chờ người dùng
   duyệt**, chưa tự sửa.


#### P5.15c — r5b đóng số: lever rescue bị bác bằng đúng quy tắc đã đăng ký trước (23-10, 23:12)

`r5b` = chạy lại **nguyên văn cấu hình r5** (`tmp/r5b_driver.sh`, cache lạnh
`tmp/loop_gen_cache_r5b`, `PYTHONUNBUFFERED=1`, **không bọc pipe**) đúng 100 item pin từ r0,
exit 0, `n_scored=100`, 0 entry lỗi.

**Con số mà r5 nợ — đếm từ log, không suy luận nữa** (bản ghi: `data/loop/rounds/r5b/rescue_tally.txt`). Toàn bộ stdout có **60 dòng
`[AnswerRescue]`**, chia đúng thành hai nhánh:

| dòng log | số | nghĩa |
|---|---|---|
| `Đã thử lượt trích xuất, model vẫn từ chối` | **59** | có hỏi lại, mô hình lặp lại lời từ chối |
| `Cứu một câu từ chối oan bằng lượt yêu cầu trích xuất.` | **1** | hỏi lại và **được nhận** (`item C126485669658863`, item đầu tiên của lượt chạy) |
| `Lượt cứu lỗi` / `Không kiểm chứng được` / `không đạt ngưỡng` | **0** | không ứng viên nào tạo ra văn bản không-phải-từ-chối rồi fail ở tầng kiểm chứng |

⇒ **60 lượt thử thật / 64 câu đủ điều kiện** (chênh 4 vì điều kiện chạy thật còn cần
`is_enough_evidence(contexts)` của đúng cửa sổ lượt đó, còn luật đếm 64 chỉ dựa trên
question/raw_query) và **tỉ lệ cứu thành công 1/60 = 1,7%**. Lever không "chạy không đủ" như
giả thuyết cũ: nó chạy gần đủ và **thất bại ở chỗ mô hình 1,5B từ chối lần hai y như lần đầu**.

**Quy tắc đã đăng ký trước (P5.15) giờ mới đủ điều kiện áp dụng:** (1) đếm được số lượt thử —
ĐẠT (60); (2) `PASS_REFUSAL < 19` — HỎNG, và hỏng **ở cả hai lượt độc lập cùng cấu hình** (17/17).
⇒ **bỏ lever `ENABLE_ANSWER_RESCUE` vĩnh viễn**: giữ `QwenGenerator._rescue_refusal` + 23 test
`tests/test_answer_rescue.py` làm bằng chứng đã đo, mặc định TẮT, **không round cứu nào nữa**.
Đầu tư tầng sinh chuyển sang hai hướng đã ghi ở điều (4) dưới đây, không sang lượt hỏi lại.

**Nhiễu của chính phép đo (đây là lý do thứ hai khiến r5b tồn tại).** Hai lượt cùng một cấu hình:

| chỉ số | r5 | r5b | chênh |
|---|---|---|---|
| `PASS_CORRECT` | 14 | **14** | 0 |
| `PASS_REFUSAL` | 17 | **17** | 0 |
| `FAIL_HALLUCINATED_ON_UNANSWERABLE` | 2 | **2** | 0 |
| `FAIL_FABRICATED` | 1 | **1** | 0 |
| `FAIL_OVERREFUSAL` | 37 | **34** | −3 |
| `FAIL_RETRIEVAL` | 20 | **22** | +2 |
| `FAIL_INCOMPLETE` | 9 | **10** | +1 |
| refusal rate | 0,69 | **0,66** | −0,03 |
| fabrication trên câu đã trả lời | 0,0323 | **0,0294** | −0,0029 (vẫn là MỘT câu bịa, mẫu số 31 vs 39) |

Bốn chỉ số quyết định (PASS_CORRECT / PASS_REFUSAL / HALLUCINATED / FABRICATED) **ổn định tuyệt
đối** giữa hai lượt, còn các nhóm FAIL dao động ±3 item — đó là trần nhiễu của pha đắt n=100 ở
nhiệt độ 0,1. Hệ quả đọc số: chênh 19→17 của `PASS_REFUSAL` giữa r1 và r5/r5b **không tự nó có
nghĩa** (r1 chỉ chạy một lượt, chưa có bản lặp), và mọi khác biệt ≤3 item giữa hai round pha sinh
đều phải coi là nhiễu cho tới khi có chứng cứ khác.

**Lỗ thứ hai của dụng cụ cổng, lộ ra đúng như thiết kế của r5b.** Cổng `r5b-vs-r5` — hai lượt
**cùng một cấu hình**, tức lẽ ra phải trung tính — vẫn kết luận **KHÔNG ĐẠT**, vì hai lý do:
`family_pass_rate[EXACT] 0,25→0,125` (n=8: **một item lật** đã là −12,5 điểm %, vượt ngưỡng
−10) và `refusal_rate_bounded` (trần tuyệt đối). Bài học cho task chờ-duyệt #23: ngoài quy tắc
tương đối cho refusal, cần chặn kiểu veto "một item của family n=8" — hoặc nâng
`GATE_MIN_FAMILY_N`, hoặc yêu cầu chênh lệch **≥2 item** trước khi family được phủ quyết; nếu
không, vòng lặp sẽ tiếp tục từ chối những cải thiện thật vì nhiễu và chấp nhận những round trệch
vì cùng một lý do. **Chờ người dùng duyệt, chưa tự sửa `gate.py`.**

**Điều (4) — việc thay thế, đã ghi trong báo cáo tổng quan 23-10:** tầng sinh được xử lý bằng
*chọn bằng chứng* (evidence-selection theo thực thể vàng), SFT đúng lớp `FAIL_OVERREFUSAL`
(triage r5 đã xuất 12 dòng `sft_extractive_from_overrefusal`, tuân thủ bất biến 7), và re-OCR
corpus mất dấu thanh — ba hướng đó không đụng nhau và không cần thêm lượt hỏi lại.


#### T0 — đóng round r5b + noise floor chính thức (23-10, nhiệm vụ T0)

Báo cáo đầy đủ: `docs/reports/T0.md`. Số liệu dưới đây truy được về
`data/loop/noise_floor.json` (sinh bởi `tools/loop/noise_floor.py`, seed 20261023,
10.000 lượt bootstrap ghép cặp, chỉ đọc verdicts đã lưu — 0 lời gọi model).

**1. r5b đóng round, xác minh trên đĩa.** `rounds/r5b/full.jsonl` = 100/100 dòng;
`settings` của r5 và r5b **giống nhau từng key, chỉ khác `generation_cache_dir`**
(cache lạnh riêng, hành vi đo không đổi); chữ ký trọng tài `9f1179ccab74` cả hai.
Bằng chứng: `rounds/r5/round_summary_full.json`, `rounds/r5b/round_summary_full.json`,
đối chiếu tự động ghi trong `noise_floor.json → rounds.settings_identical_except`.

**2. Đếm rescue từ log gốc (không suy luận):** 60 dòng `[AnswerRescue]`
= 59 lượt thử model vẫn từ chối + 1 câu được cứu (`rounds/r5b/rescue_tally.txt`).

**3. Quy tắc đăng ký trước (P5.15) áp dụng bằng số học tường minh:**
tỉ lệ cứu = 1/64 = **1,6%** (trên 64 câu đủ điều kiện) hay 1/60 = **1,7%** (trên số
lượt thử thật) — **dưới ngưỡng 5%** ⇒ **BỎ LEVER `ENABLE_ANSWER_RESCUE` VĨNH VIỄN**.
Code `QwenGenerator._rescue_refusal` + 23 test `tests/test_answer_rescue.py` giữ làm
bằng chứng đã đo; cờ mặc định TẮT; không mở round rescue nào nữa. Phán quyết bỏ lever
đã được ghi ở khối r5b ngay trên (theo điều kiện (1)+(2) của quy tắc đăng ký trước);
T0 chỉ thêm phép tính <5% mà nhiệm vụ yêu cầu ghi tường minh.

**4. Noise floor đo bằng kiểm định ghép cặp (r5 vs r5b, 100 item chung):**

| Thống kê | r5 | r5b | Hiệu ứng ghép cặp + CI 95% | McNemar chính xác |
|---|---|---|---|---|
| `PASS_CORRECT` rate | 14/100 | 14/100 | diff 0,00, CI [−0,03; +0,03] | b=1 c=1, p=1,00 |
| `refusal_rate` | 0,69 | 0,66 | diff −0,03, CI [−0,07; +0,01] | b=1 c=4, p=0,375 |
| `fabrication_rate_on_answered` (định nghĩa gate.py) | 1/31 = 0,0323 | 1/34 = 0,0294 | diff −0,0028, CI [−0,0144; +0,0009] | 0 cặp bất đồng (CÙNG MỘT câu bịa) |

Verdict đổi chỗ giữa hai lượt **cùng cấu hình**: **5/100 item**, tách theo family:
HUMAN 2/7 (28,6%) · EXACT 1/8 · SOURCE_LOOKUP 1/13 · CLOZE 1/14 · các family còn lại 0
(bảng đầy đủ + transition matrix + danh sách item trong `noise_floor.json → verdict_flips`).

**Sửa một khẳng định cũ ghi quá mạnh (bất biến 1 — ghi cả bản cũ lẫn bản sửa):**
P5.15c viết "bốn chỉ số quyết định ổn định tuyệt đối giữa hai lượt". Với `PASS_CORRECT`
điều đó **chỉ đúng ở mức số đếm**: đúng MỘT item rớt khỏi PASS_CORRECT
(`T111158251954171`, EXACT) và đúng MỘT item mới vào (`S193409910201077`,
SOURCE_LOOKUP) nên 14 = 14 chỉ là trùng hợp về số đếm. Ba chỉ số còn lại
(`PASS_REFUSAL`/`HALLUCINATED_ON_UNANSWERABLE`/`FABRICATED`) mới thực sự ổn định
**ở mức item** (0 cặp bất đồng). Bản đúng của "ổn định tuyệt đối": *số đếm*, không phải
*tập hợp item*.

**Hệ quả cho dụng cụ cổng (bổ sung bằng chứng cho hai đề xuất đang chờ duyệt):**
(i) `refusal_rate` dao động ±3 điểm % là NHIỄU thuần (McNemar p=0,375; CI hiệu ứng
ghép cặp [−0,07; +0,01]) ⇒ quy tắc
tương đối cho `refusal_rate_bounded` là cần, và trần nhiễu để "không tăng" phải trừ ít
nhất khoảng CI này; (ii) đúng item lật của family EXACT (`T111158251954171`) chính là
nguồn veto `0,25→0,125` trong cổng r5b-vs-r5 — một item lật xảy ra ngay khi không đổi
một dòng code nào ⇒ đề xuất "family chỉ được phủ quyết khi chênh ≥2 item" (hoặc nâng
`GATE_MIN_FAMILY_N`) nay có số, vẫn **chờ người dùng duyệt, `gate.py` chưa sửa**.

**5. Sửa nhận định latency/KV-prefix bằng số đo trực tiếp (ĐÃ ĐO 23-10, hai lượt độc lập,
`tmp/probe_prefix_cache_result.json`; chi tiết trong `docs/reports/T0.md` mục 5):**
probe 3 lượt gọi Ollama cục bộ/item-pair, 0 Gemini. Số: lượt đầy đủ A
`prompt_eval_count=3542` · 1,21 s; lượt đuôi B = A + `RESCUE_INSTRUCTION`
`prompt_eval_count=3806` · **0,52 s**; đối chứng C (prompt item khác + cùng đuôi, 3351 tok)
· **0,95 s**. Kết luận hiệu chỉnh hai nhận định cũ:
(i) **`prompt_eval_count` không phải dụng cụ đếm tái dùng** — B khai TOÀN bộ token dù
phần lớn prefill được bỏ qua; ý định "xác nhận cơ chế prefix-cache bằng
`prompt_eval_count`" (P5.15) là KHÔNG khả thi, đã đo và bác ở mức dụng cụ;
(ii) **cơ chế tái dùng prefix CÓ THẬT, đo bằng thời gian**: B dài hơn C mà rẻ hơn ~2 lần
(0,52 s vs 0,95 s) ⇒ nhận định "lượt cứu thứ hai rẻ" ở P5.15 được xác nhận với độ chính
xác mới **~0,3–0,7 s**, tức ~4% tổng latency một câu — điều này đồng thời giải thích vì
sao r5 KHÔNG thấy cặp latency 2× và vì sao phép đếm duy nhất đáng tin là số dòng log
(60/64 ở r5b, không đổi). Giới hạn: n = 1 cặp prompt, 2 lượt chạy, cùng hướng.


### P5.16 — bộ chuẩn hóa câu hỏi thỉnh thoảng trả về một câu khác (23-10)

Ca bệnh ĐO từ dữ liệu vòng lặp, không phải suy đoán. `full.jsonl` của r0/r1/r3 lưu lại
300 cặp (câu gốc, `normalized_query`). Đếm số token nội dung của câu gốc còn sót trong bản
chuẩn hóa (`fold()`, bỏ token dài ≤2): median **1,00**, p10 **0,46** — nhưng có **16/300
lượt (5,3%)** rơi tự do, chia hai mode (bảng dưới ghi **cả ba khẳng định về tính tái lập từng
bị ghi quá mạnh — xem đoạn sửa ngay sau bảng**):

| Mode | Ca thật | output |
|---|---|---|
| **ECHO nguyên văn một dòng few-shot** | `N148008092394710`, `Y57173144541416`, `T224347701010571` (ba câu hỏi khác nhau) | "Sinh viên: Bị điểm rèn luyện loại yếu thì có bị đuổi học không ad?" — đúng dòng `FEW_SHOT_PROMPT` Ví dụ 1 |
| **TỰ TRẢ LỜI thay vì chuẩn hóa** (System Prompt cấm rõ: "không tự trả lời câu hỏi") | `N143662722487347` (hỏi mức phụ cấp nội quy) | "Mức độ hoàn thành: 9/10" |
| **CHÉP ví dụ khác** | `Y166453071308081` (hỏi Triết học 660.000 đúng không) | "Triết học có mã môn học là gì, bao nhiêu tín chỉ…" (Ví dụ 4) |

**Sửa lại một khẳng định đã ghi quá mạnh (đo 23-10, sau khi r4 chốt):** bản kiểm tra chéo
100 item trùng khớp giữa các round cho thấy **không thể nói "tái lập y hệt"**. Trên đúng tập
item pin từ r0: `normalized_query` của **r0 và r3 giống nhau 100/100**, còn **r1 lệch 18/100**
(cùng code, cùng model, cùng một phiên driver r0→r1, temp 0.0). Ba ca ECHO
nêu trên không xuất hiện nguyên văn ở cả ba round: `T224347701010571` bị echo ở r1 nhưng được
chuẩn hóa đúng ở r0 VÀ r3. Kết luận trung thực: **bản chuẩn hóa không tái lập ổn định giữa các
lượt chạy**, tỉ lệ hỏng là một **đặc tính tần suất** (5–6/100 mỗi lượt) chứ không phải một hàm
tất định; nguyên nhân gốc (vì sao cả một run lệch 18 câu trong khi hai run kia trùng khít)
**chưa xác định được** và cần một phép đo riêng (hai lượt liên tiếp trên cùng 10 câu, không
cache) — để ngỏ, không suy diễn. Hệ phương pháp: lever tầng sinh/sửa ở P5.15b không được thiết
kế dựa trên `normalized_query` của MỘT round, vì chính đầu vào đó dao động giữa các lượt chạy.

Vì sao nó liên quan tới chống bịa đặt: `pipeline.run` đưa `normalized_query` vào **CẢ truy
xuất lẫn sinh**. Item hỏng từ gốc thì không lever nào ở tầng sau cứu được — 5/23 ca
`FAIL_RETRIEVAL` của r1 ở pha đắt thuộc nhóm này, nghĩa là một phần "lỗi truy xuất" mà
máy quy lỗi đổ cho router/classifier thực ra là lỗi tầng input.

Phạm vi nhiễm, nói cho đúng để không đọc nhầm số cũ: **chỉ pha đắt** (`full` → `pipeline.run`)
mới chuẩn hóa; `run_retrieval_phase` mặc định giữ nguyên câu hỏi (`--normalize-query` là cờ
rõ ràng, chưa từng bật). Vậy gold@6/neo HUMAN của r0–r4 không dính lỗi này, còn toàn bộ verdict
sinh văn bản của r0/r1/r3 thì có — 5–6/100 item mỗi round.

Sửa theo đúng bài học P5.14 (không vẽ số): `normalized_output_rejection(raw, out)` trả lý
do bằng tiếng Việt khi (a) output rỗng, (b) `fold(out)` trùng một dòng few-shot đang thực
sự dùng để dựng prompt (lấy từ `BASE_EXAMPLES` + learning pairs, không có bản sao thứ hai),
hoặc (c) `token_containment(raw, out) < NORMALIZE_MIN_CONTAINMENT` — mặc định **0,3** chốt
theo phân bố ở trên, nằm dưới cả hai mode hỏng (0,12–0,27) và trên không một bản chuẩn hóa
hợp lệ nào trong 284 lượt còn lại. Gate bật bằng `NORMALIZE_SANITY_GUARD=1` (mặc định TẮT,
hành vi cũ giữ nguyên từng ký tự); khi bác thì in `[QueryNormalizer] Bác bản chuẩn hóa…`
và trả về câu gốc — đường an toàn, cũng chính là hành vi của hệ thống trước khi có bộ
chuẩn hóa. 27 test trong `tests/test_query_normalizer_guard.py`, gồm test "mặc định TẮT thì
echo vẫn được trả về như cũ" và test "path bác phải in log".

`query_normalizer.py` KHÔNG nằm trong `REFEREE_FILES`, nên thêm gate không đổi chữ ký trọng
tài; hai key mới (`normalize_sanity_guard`, `normalize_min_containment`) đã được ghi vào
`settings` của round.

**Tiêu chí r6 ĐĂNG KÝ TRƯỚC bằng phép đo trên dữ liệu đã lưu (23-10, `tmp/probe_guard_scope.py`,
0 lời gọi model):** chấm `normalized_output_rejection` bằng đúng hàm ship, với `learning_pairs`
đang tải thật (15 cặp → 24 dòng ví dụ), trên 100 item đã lưu của từng round ⇒ **r1: 6/100 bị bác**
(3 "chép nguyên văn một dòng few-shot" + 3 "mất nội dung", containment 0,12–0,27), **r3: 5/100**,
**r0: 5/100**; median containment 1,00 ở cả ba round. Vì r6 chạy trên cùng 100 item pin từ r0,
kỳ vọng thật là **5–6 dòng `[QueryNormalizer] Bác bản chuẩn hóa…`** — nếu log chỉ có 0–2 dòng thì
NGHI phép đo trước khi kết luận lever (đúng cái bẫy đã trả giá ở r3: lever không chạy bị đọc
nhầm thành lever thua). Hai điều kiện đạt: (1) cổng `r6-vs-r1` ở pha sinh ĐẠT (PASS_CORRECT
không giảm quá ngưỡng, `FAIL_HALLUCINATED_ON_UNANSWERABLE` không tăng, fabrication không tăng);
(2) ít nhất MỘT trong các item bị bác đổi verdict theo chiều tốt — vì bản chuẩn hóa của chúng vốn
là câu khác, nên cửa sổ truy xuất và prompt sinh đều đổi. Một biến số duy nhất: `NORMALIZE_SANITY_GUARD=1`
còn router giữ nguyên cấu hình đã chốt ở r5 (bonus 3 nếu r5 còn dùng r1 làm baseline — xem P5.15),
`ENABLE_ANSWER_RESCUE` giữ đúng trạng thái mà r5 chốt.

**Ghi chú đăng ký thêm TRƯỚC khi r6 chạy (23-10, sau khi r5b chốt):** r6 chạy trên **cache lạnh**
(`tmp/loop_gen_cache_r6`) còn r1 chạy trên cache đã ấm từ r0, nên mọi câu không bị bác chuẩn hóa
sẽ được **hỏi lại model** ở nhiệt độ 0,1 thay vì đọc lại câu cũ. Trần nhiễu của phép đó đã đo
xong ở r5b: cùng một cấu hình, hai lượt — `PASS_CORRECT`/`PASS_REFUSAL`/`HALLUCINATED`/`FABRICATED`
ổn định tuyệt đối, các nhóm FAIL dao động ±3 item, refusal −0,03. Vì vậy khi đọc cổng `r6-vs-r1`
chỉ những chênh lệch **đúng trên các item bị bác** (và chiều của tiêu chí (2)) mới là chứng cứ;
chênh ≤3 item ở các nhóm khác phải coi là nhiễu. Lưu ý về dụng cụ: `gate.compatibility()` chỉ so
sánh năm key (`testset/top_k/generator/normalize_query/enable_classifier`) + chữ ký trọng tài,
**không biết gì về `normalize_sanity_guard`** — cổng sẽ im lặng coi hai round là so được. Kỷ luật
một biến số vì thế thuộc việc của người chạy (driver `tmp/r6_driver.sh` ghi rõ env), không phải
được dụng cụ bảo vệ.

**Kết quả r6 (23-10, 23:5x, `rounds/r6/`, 100/100 item, exit 0, 0 entry lỗi) — lever ĐƯỢC chứng
minh, và đây là bằng chứng nhân quả sạch nhất của cả vòng lặp.** Bản ghi đếm được + bảng quy lỗi
cấp item: `rounds/r6/normalizer_guard_tally.txt` (probe `tmp/probe_r6_attribution.py`).

- **Lever chạy đúng tần suất đăng ký trước: 5/100 dòng `[QueryNormalizer] Bác bản chuẩn hóa…`**
  (kỳ vọng 5–6; nếu 0–2 thì phải nghi phép đo). Hai mode hỏng hiện ra nguyên văn: 3 ca "mất nội
  dung câu gốc" (containment 0,12–0,27) và 2 ca "chép nguyên văn một dòng few-shot".
- **Cả 5 item bị bác đều lấy lại chunk vàng vào cửa sổ 6** (`gold_in_top_k` False → True ở 4/5;
  ca thứ năm vốn đã có vàng vì nghẽn ở tầng sinh). Verdict: 1 thành `PASS_CORRECT`, 2 từ
  `FAIL_RETRIEVAL` lên `FAIL_OVERREFUSAL` (hết lỗi truy xuất, còn lỗi sinh), 1 lên
  `FAIL_INCOMPLETE`, **0 item đi xuống**. ⇒ **tiêu chí (2) đã đăng ký trước: ĐẠT.**
- Số tổng hợp cùng chiều: `PASS_CORRECT` 10→**14**, `FAIL_RETRIEVAL` 23→**18**,
  **gold@k trên 80 item có chunk vàng 0,6875→0,7875 (+10 điểm %)**, fabrication 0,0357→**0,0278**,
  hallucinated-on-unanswerable 2/2, refusal rate 0,72→**0,64** (GIẢM). Chiều ngược cũng có và
  phải ghi: `PASS_REFUSAL` 19→**17** (−2, cùng cỡ nhiễu r5b) và `FAIL_INCOMPLETE` 7→**11** (+4) —
  hai chỉ số này ở r1/r5/r5b chưa từng được lặp lại nên chưa tách được lever khỏi dao động.
- Cổng `r6-vs-r1`: **6/7 quy tắc ĐẠT**, `pass_rate` 0,29→0,31, không family nào giảm (EXACT
  0,00→0,25, NUMERIC 0,30→0,50), neo HUMAN giữ. Quy tắc duy nhất vi phạm là
  `refusal_rate_bounded` — vi phạm **dù r6 đã cải thiện chính chỉ số đó** (0,64 < 0,72 của
  baseline), vì trần 0,35 là tuyệt đối. Đây là round đầu tiên mà "KHÔNG ĐẠT" của cổng hoàn toàn
  không có nội dung khoa học; nó là chứng cứ trực tiếp cho task chờ-duyệt #23.
- Cổng tham chiếu `r6-vs-r5b` (khác hai thứ: rescue và cache) cũng 6/7 ĐẠT, cùng một lý do.
- **Phần dao động không thuộc lever:** 16/95 item không bị bác đổi verdict (8 lên, 8 xuống),
  tổng PASS 29→31 — đúng cỡ nhiễu đã đo ở r5b. Con số này là lý do phải quy lỗi cấp item chứ
  không đọc chỉ số tổng.
- **Đính chính phương pháp (quan trọng cho mọi phép đo sau):** chủ thể thật của phép chuẩn hóa là
  `item["raw_query"]`, không phải `item["question"]` — `tools/loop/run_round.py:95` chọn
  `raw_query` rồi đưa vào `pipeline.run`, và `src/pipeline.py:356,386` chuẩn hóa chính chuỗi đó.
  Chấm nhầm trên `question` sẽ làm một ca ECHO "khớp cả ba round" và dẫn tới diễn giải sai về
  tính tái lập (xem đoạn "Sửa lại một khẳng định đã ghi quá mạnh" ở trên).

**Việc còn treo (không tự làm):** bật `NORMALIZE_SANITY_GUARD=1` làm mặc định production là đổi
hành vi đường đang chạy, cần người dùng duyệt; và #23 (sửa hai lỗ của cổng) nên sửa **trước** khi
mở cổng cho các round tổ hợp tiếp theo, vì hiện mọi round pha sinh đều bị cổng kết luận
"KHÔNG ĐẠT" bất kể tiến bộ.



#### P5.17 — r7 tổ hợp (bonus 12 + guard): không có bằng chứng cộng hưởng, và hai ca trả giá (24-10)

Bản ghi đếm được + bảng quy lỗi cấp item: `rounds/r7/combo_tally.txt`. Cấu hình: r6 +
`ROUTER_FILTER_RANK_BONUS=12`, rescue TẮT, quota TẮT, cache lạnh, 100/100 item, exit 0,
0 entry lỗi. Một biến số so với r6 = con số bonus.

- **Guard tái lập đúng 5/5 ca với r6, trùng khít từng ký tự** (cùng ba containment 0,12–0,27,
  cùng hai ca ECHO). Đây là cặp đầu tiên trong chuỗi có tập ca hỏng giống hệt nhau — không
  được suy rộng thành "bộ chuẩn hóa deterministic", cỡ mẫu là 5 và các cặp r0/r1/r3 vẫn lệch
  18/100 như đã ghi ở P5.16.
- **Cả hai cổng 6/7 ĐẠT**, `config_mismatches=[]`. Vi phạm duy nhất vẫn là `refusal_rate_bounded`
  với candidate **0,62** — vi phạm *dù chỉ số đó đã giảm* so với cả hai baseline (0,64 và 0,72).
  Lần thứ hai liên tiếp "KHÔNG ĐẠT" của cổng không mang nội dung khoa học ⇒ chứng cứ cho #23.
- **Chênh r7-vs-r6 nằm trong băng nhiễu** đã đo ở r5b (±3 item cho nhóm FAIL): 9 lên / 4 xuống
  nhưng chỉ 3/2 là verdict; `PASS_CORRECT` 14→14, `pass_rate` 0,31→0,32, gold@k +1/80 item,
  HUMAN anchor 3→5/7. Kết luận trung thực: ở n=100 **không xác nhận được** rằng bonus 12 cộng thêm
  giá trị khi đã có guard; cũng không bác nó. Chuỗi tiến bộ r1→r6→r7 (`pass_rate` 0,29→0,31→0,32)
  chủ yếu do guard, không do con số bonus.
- **Chiều bất lợi có cơ chế, không phải ngẫu nhiên:** `N172171203676287#2` (NUMERIC) và
  `S193409910201077` (SOURCE_LOOKUP) đi từ `PASS_CORRECT` xuống `FAIL_OVERREFUSAL` — xếp thưởng
  theo nguồn đẩy chunk cần thiết ra khỏi cửa sổ 12 slot. `NUMERIC` 0,50→0,40 = **−0,1000 đúng
  bằng ngưỡng** `GATE_MAX_FAMILY_DROP=.10` (chỉ veto khi giảm *quá* 0,1): một item nữa là family
  rule veto. Ghi đây vì đây là một cổng mỏng trên mép dao: chênh đúng bằng ngưỡng thì được coi là
  an toàn, nhưng nó không có nghĩa là không rủi ro.
- **Sự cố ở dụng cụ đo (1 item):** `CUDA error: out of memory` làm một lần gọi chuẩn hóa thất bại →
  `query_normalizer` fallback về câu gốc (đường an toàn có sẵn, may là đã tồn tại) kèm một cảnh báo
  nhãn classifier không hợp lệ cùng khối. 0 item `err != None`; item đó đi qua vòng lặp với hành vi
  "guard bác", không giải thích được thay đổi verdict nào.
- **Không có round tổ hợp nào nữa để đo bonus.** Việc còn treo theo đúng thứ tự đáng làm:
  (1) **#23 sửa cổng** để pha sinh có thể ĐẠT; (2) **#28 duyệt bật guard làm mặc định production**;
  (3) quyết định bonus 3 hay 12 bằng **lặp lại / tăng cỡ mẫu**, không bằng một cổng n=100;
  (4) lever chọn bằng chứng (evidence selection) và SFT trên `sft_extractive_from_overrefusal`.
  ⇒ (4) đã được đo và bác ở P5.19; (1) vẫn chờ duyệt (#23), (2) vẫn chờ duyệt (#28).

---

#### P5.18 — r8: quyền từ chối chuyển xuống tầng ngoài, kết quả là một thoả thuận xấu (24-10)

Cấu hình: **đúng r5 từng ký tự** + `ENABLE_DECOUPLED_REFUSAL=1`, cache lạnh
`tmp/loop_gen_cache_r8`, 100/100 item, exit 0, **0 lượt Gemini**. Chữ ký trọng tài
`9f1179ccab74` khớp cả ba round ⇒ không round cũ nào phải chấm lại.
Bản ghi: `rounds/r8/round_summary_full.json`, `rounds/r8/attribution_vs_r5.txt`,
`rounds/r8/gate_vs_r5_full.json`, log `tmp/r8_run.log`, báo cáo `docs/reports/T3.md`.

**Vì sao lever chạy được về mặt cơ học.** `EXTRACT_ONLY_HEAD` (prompt `v2.0-extract-only`) bỏ mọi
đường "không đủ thông tin" khỏi chỉ dẫn, nên model chỉ còn một việc: trích câu trả lời từ ngữ cảnh.
`effective_prompt_version()` tách nhánh phiên bản nên cache `v1.3` của mọi round trước **không bị đụng và
không bị invalidate** — điều kiện để so sánh một biến. Luật ngoài đọc ba tín hiệu đã ghi trong
manifest (`dec_thresholds`), quyết định deterministic, và in `[DecoupledRefusal]` ra log.

**Cái được (số thật, `rounds/r8/`):** refusal **0,69 → 0,28** — lần đầu dưới trần 0,35 của cổng;
`FAIL_OVERREFUSAL` **37 → 23**; `PASS_CORRECT` **14 → 19**, trong đó **16 câu đi thẳng từ
`FAIL_OVERREFUSAL` lên `PASS_CORRECT`**; fabrication trên câu đã trả lời **1 → 0**. Chênh +5 item
vượt băng nhiễu ±3 đã đo ở T0 ⇒ không phải nhiễu.

**Cái giá (cũng số thật, và là lý do cổng veto):** `PASS_REFUSAL` **17 → 2**, `FAIL_HALLUCINATED_ON_UNANSWERABLE`
**2 → 12**, `FAIL_CONFIRMED_FALSE_PREMISE` **0 → 4**, `pass_rate` **0,31 → 0,21**. Quy lỗi cấp item
khép chặt cơ chế: 12 câu bịa-lạc-đề là **7 `REFUSE_OOD` + 5 `REFUSE_MISSING_DOC`, 10/12 trong số đó ở
r5 là `PASS_REFUSAL`**; 4/4 ca tiền giả sai từng là `PASS_REFUSAL`. Tức lever **không tự sinh câu bịa
mới** — nó phá lớp im lặng đúng, và trong miền văn bản hành chính thì "trả lời chắc chắn điều không có
trong văn bản" nguy hại hơn im lặng.

**Phát hiện quan trọng hơn cả verdict: bốn trong năm luật là giấy.** Đếm từ log: `no_evidence` 0,
`off_topic_window` 0, `weak_retrieval_rank` **25**, `ungrounded` 0, `model_still_refuses` 3. Lý do đo
được từng cái: `overlap` min **0,333** > ngưỡng 0,20 mà luật 2 là HOẶC ⇒ không còn đường kích hoạt;
`grounding_score` **≡ 1,0 trên cả 72 câu đã sinh** vì prompt chỉ-trích-xuất sao nguyên văn căn cứ ⇒
luật 4 bị vô hiệu **cấu trúc**, nó không bắt được lớp "có căn cứ nhưng lạc đề" — chính là lớp vừa phình
ra. Tầng ngoài thực tế chỉ còn một tín hiệu phân biệt là **hạng truy xuất**, và hạng truy xuất không thể
phát hiện "corpus này không trả lời được câu hỏi" (TRAP/REFUSE vẫn `rrf_norm` cao vì có văn bản cùng chủ đề).
`rrf_norm` p25 = 0,930 trong khi ngưỡng 0,90 ⇒ **25 ca từ chối phần lớn nằm sát mép**, và
**20/28 item bị từ chối có chunk vàng trong cửa sổ**, trong đó **10 item r5 đã trả lời đúng**
(14 câu đúng của r5 chỉ giữ được 2). Đây là mô tả hậu nghiệm, **không** phải kết quả của một lần chỉnh ngưỡng.

**Không suy rộng được:** r8 là MỘT lever gồm hai thay đổi đi cùng nhau (prompt + tầng ngoài) theo đúng
đăng ký, nên không tách được đóng góp riêng của prompt; mẫu n=100 phân tầng (family nhỏ nhất n=1);
hành vi production không đổi vì cờ mặc định TẮT.

#### P5.19 — r9: 5 câu bằng chứng làm model 1,5B bỏ cuộc (24-10, kết quả âm)

Cấu hình: **đúng r8** + `ENABLE_EVIDENCE_SELECTION=1`, cache lạnh `tmp/loop_gen_cache_r9`,
100/100 item, exit 0, 0 lượt Gemini. Bản ghi: `rounds/r9/round_summary_full.json`,
`rounds/r9/attribution_vs_r8.txt`, `rounds/r9/attribution_vs_r5.txt`,
`rounds/r9/gate_vs_r8_full.json`, `rounds/r9/gate_vs_r5_full.json`, log `tmp/r9_run.log`.

**Phép một biến được giữ đúng:** luật 1–3 vẫn đo trên cửa sổ chunk **gốc**, chọn câu chạy SAU ba luật
đó ⇒ phần pre của r9 **trùng khít r8** (25 từ chối `weak_retrieval_rank`), và `sources` (retrieve_k)
không bị động vào nên gold@k **0,7125 = 0,7125**. Mọi khác biệt vì thế nằm ở phía model đã đọc gì.

**Kết quả:** `model_still_refuses` **3 → 32** (gấp ~11 lần), refusal **0,28 → 0,57** (vượt trần 0,35),
`FAIL_OVERREFUSAL` **23 → 35** với **29/35 có chunk vàng trong cửa sổ**, `PASS_CORRECT` **đi ngang 19**
nhưng là tập câu khác (giao nhau **11 id**; 7 id chỉ r8 đúng, 7 id chỉ r9 đúng, 1 id đúng ở cả ba round).
Đổi lại, lớp an toàn quay về: `PASS_REFUSAL` 2 → 14, `FAIL_HALLUCINATED_ON_UNANSWERABLE` 12 → 3,
`pass_rate` 0,21 → 0,33. Family nói rõ cơ chế: **CLOZE_OCR `PASS_CORRECT` 8 → 3** và từ chối 1 → 7 —
đúng family dễ tổn thương nhất khi mất ngữ cảnh (văn bản OCR gần như không dấu, một câu đơn lẻ thường
mất nhãn đi kèm con số); CLOZE 2→4, SOURCE_LOOKUP 1→3, YESNO_FACT 4→5 được cải thiện.

**Chi phí:** median **14,95 → 25,25 s**, p95 **19,93 → 33,27 s (+67%)** — chưa tách được phần nào là
CPU chọn câu, phần nào là sinh; muốn tách phải đo riêng, chưa làm.

**Hai sự thật dụng cụ phải đọc kèm số:** (i) reranker **không phải cross-encoder** — `bge-reranker-base`
không tải được (`RepositoryNotFoundError`), module lùi về bi-encoder `BAAI/bge-m3` và đã ghi vào
`settings.evidence_reranker` của manifest đúng yêu cầu đăng ký ⇒ số r9 phải đọc là "chọn câu theo
bi-encoder"; (ii) **75/75 cửa sổ đều đúng 5 câu** (`EV_MAX_SENTENCES`), không lần nào chọn 3–4 và không
lần nào phải nới lỏng bậc thang, trung bình **6898 → 1022 ký tự (còn 15%)** — tức lever đang hoạt động
như "cắt còn 5 câu", chưa phải "chọn 3–5 câu"; nguyên nhân chưa đo, có probe đề xuất ở `docs/reports/T3.md` §6.

**Xử lý theo điều khoản đã ký:** tiêu chí `PASS_CORRECT ≥ 25` không đạt ở cả hai round ⇒ **không mở
lever thứ ba, không chỉnh ngưỡng `DEC_*`/`EV_*` theo số**. Hai cờ giữ mặc định TẮT; module + 47 test
+ artifact round giữ làm bằng chứng (tiền lệ `rescue` ở P5.15c). Hướng điều tra tiếp theo (đều cần duyệt,
chưa tự làm) nằm ở `docs/PENDING_APPROVAL.md` PA-9/PA-10.


#### P5.20 — T4: 3B trên máy triển khai không mua được gì, và SFT bị chặn bởi 1.000 token (24-10)

Báo cáo đầy đủ: `docs/reports/T4.md`. Cấu hình r10 = **đúng r5** chỉ đổi
`GENERATOR_OLLAMA_MODEL=qwen2.5:3b-instruct` (Q4, `num_ctx` 8192, prompt `v1.3`, temperature 0,1),
100/100 item, cache lạnh `tmp/loop_gen_cache_r10`, exit 0, **0 lượt Gemini**; log `tmp/r10_run.log`.

**Một biến đã chứng minh chứ không tuyên bố:** `tools/diag/one_variable_check.py --candidate r10
--baseline r5` so SHA-1 từng trường trên 100 item chung ⇒ `contexts`, `sources`, `normalized_query`,
`labels`, `retrieval_config` **identical 100/100**, chỉ `answer` khác (50/100). `FAIL_RETRIEVAL` và
gold@6 của r10 do đó bằng đúng r5, như tiên đề.

**Số (trọng tài `9f1179ccab74`, bootstrap 10.000 seed 20261023 — `rounds/r10/t4_stats.json`):**

| Chỉ số | r5 (1,5B) | r10 (3B) | Ghép cặp |
|---|---|---|---|
| `PASS_CORRECT` | 14 [0,07; 0,21] | **16 [0,09; 0,24]** | delta +0,0203 CI [−0,06; +0,10], McNemar 9/7 **p = 0,804** |
| `refusal_rate` | 0,69 | **0,75** | +0,06 CI [−0,03; +0,16] (chứa 0) |
| fabrication trên câu đã trả lời | 0,0323 | **0,0** | −0,0322 CI [−0,1111; 0,0] |
| median / p95 / max giây | 16,16 / 18,65 / 21,43 | **26,71 / 34,12 / 45,16** | p95 **+83%** |

Quy tắc đăng ký trước ("3B = có tín hiệu nếu `PASS_CORRECT ≥ 22/100` **và** fabrication không tăng")
⇒ **không có tín hiệu** (16 < 22). Điều khoản kèm theo — "Qwen3-4B chỉ chạy như round riêng nếu 3B
cho cải thiện nhưng chưa đạt mục tiêu" — **không kích hoạt**, vì delta CI chứa 0. Hai cổng
(`r10-vs-r5`, `r10-vs-r9`) đều KHÔNG ĐẠT; ở cổng r10-vs-r5 phần vi phạm family chỉ là 1–2 item trên
n=8/n=10 (đúng lỗ #23 đã chờ duyệt), còn `refusal_rate_bounded` vi phạm trần tuyệt đối độc lập.
`ollama ps` trong phiên: `qwen2.5:3b-instruct 2,3 GB 100% GPU 8192` — không offload nên phép so
latency hợp lệ trực tiếp; snapshot thành tệp của chính khoảnh khắc đó chưa có (lần thử lại bị model
1,5B của classifier chiếm GPU), đã ghi là "bằng chứng chờ" trong `docs/reports/T4.md` §5.4.

**4b — hai bằng chứng chặn đường SFT, không phải thiếu script.** (1) Dữ liệu:
`data/training/t4b_r5r8r9r10/manifest.json` = 23 dòng SFT (khử trùng theo item id) trên 9 tài liệu,
group-split theo tài liệu train 13 / holdout 10 (2 tài liệu holdout), ba assert chống rò rỉ đều
`true`, bị chặn `blocked_test_leak` 134 · `skip_sft_target_not_in_context` 20 ·
`overrefusal_threshold_only` 17 · trùng id cross-round 38. Tokenizer thật
(`models/qwen25_05b_sft_adapter`) đo: **train min 1.016 / median 1.439 / max 1.707**, **13/13 vượt
trần 768**. (2) Bộ nhớ: `data/loop/diag/t4b_memory_probe{,_len}.json` — LoRA fp16 của 0,5B trên card
4.095,5 MiB hết chỗ từ **1.024 token** (peak 4.156,9; 960 token còn 3.931,0; 1.768 token cần 6.437,9),
độ dốc ≈ **3 MiB/token** và `gradient_checkpointing` **không giảm** (6.451,0 so với 6.437,9) ⇒ bộ nhớ
bị chiếm bởi logits của LM head, phần checkpointing không chạm tới. Cộng lại: **mọi dòng train thật
đều dài hơn trần bộ nhớ của máy** ⇒ hoặc đổi định dạng dữ liệu (PA-12, đụng bất biến #7 nếu cắt
nhầm căn cứ) hoặc đổi phần cứng/4-bit (PA-11, cần `bitsandbytes` + trọng số HF 3B, cả hai chưa có).
Theo đặc tả của user, phiên này **chỉ dựng pipeline + báo cáo chi phí**, không train, nên tiêu chí
"chứng minh bằng `PASS_CORRECT` trên test group tách rời" vẫn **chưa** được thỏa.


#### P5.21 — T5a: reranker cross-encoder là kết luận âm, và nguyên nhân là một quy ước chấm (25-10)

Cấu hình r12 = **đúng r11** (811 item, retrieval-only, bonus 12, quota 0) chỉ thêm
`ENABLE_RERANKER=1 RERANKER_KEEP_CANDIDATES=1 RERANKER_DEVICE=cuda` — pool 20 RRF → cross-encoder
`bge-reranker-v2-m3` → top-6. Round chạy **02:53 → 03:58 = ≈66 phút** (tổng `latency_seconds` 811 dòng
= 3.855,5 s; median 4,74 s/item, p95 5,09 — nguồn `data/loop/rounds/r12/round_summary_retrieval.json`),
0 lượt Gemini. **Vượt ngưỡng tự đặt 60 phút**, ghi lại thay vì che.

| Chỉ số | r11 (nền) | r12 (rerank) | Ghép cặp |
|---|---:|---:|---|
| gold@6 | **0,7400** [0,7071; 0,7729] | **0,6686** | delta −0,0714 CI [−0,1014; −0,0414], McNemar 83/33 **p = 3,9e−06** |
| EXACT | 0,2115 | **0,0385** | sụp gần hết |
| TRAP | — | **0** | mất toàn bộ |
| neo HUMAN | 0,8144 | 0,7010 | giảm |
| `FAIL_RETRIEVAL` | 182 | **232** | +50 |

Cổng r12-vs-r11: **6/8 kiểm tra vi phạm** (EXACT, SOURCE_LOOKUP, TRAP, YESNO_FACT, neo HUMAN,
`retrieval_not_degraded`). Trần oracle pool-20 = **0,8871** (EXACT 0,6154) — tức vấn đề không phải
"model yếu" mà là "chấm sai cặp". Probe 30 item r11-có-vàng-nhưng-r12-mất (`tmp/probe_r12_fold.json`):
RRF gốc 27/30, `fold(query)` **0/30**, query nguyên văn **28/30 (đa số hạng 1)** ⇒ thủ phạm là
`score_pairs` chấm query mất dấu với passage còn dấu. Sửa fold + chạy r14 = **PA-25** (chờ duyệt).

#### P5.22 — T5b: header `[file] - [Điều]` không có tín hiệu vì phần lớn đã có sẵn (25-10)

r13 = **đúng r11** + `ENABLE_CONTEXTUAL_HEADER=1`, 811 item. gold@6 **0,7400 → 0,7371** (delta −0,0028,
CI [−0,0129; +0,0071] chứa 0, McNemar **p = 0,79**), EXACT **+1 item**, cổng **6/6 ĐẠT**.
Không kết luận "header vô dụng" chung chung: đo trên đĩa cho thấy **253/361 chunk đã có header dạng
`[tên file] - [Điều]`**, nên lever chỉ còn tác dụng trên Chương/Khoản + 108 chunk fallback — đúng
phạm vi nhỏ, delta nằm trong băng nhiễu ±3 item. Có **lệch thiết kế** (chạy trên `chroma_db` cũ thay vì
index header riêng vì neo `gold_chunk_id` không ánh xạ — PA-21/PA-22); đã ghi ở T5.md §5, không sửa
số. Nguồn: `data/loop/rounds/r13/round_summary_retrieval.json`.

#### P5.23 — T7: chuỗi round tái lập bằng một lệnh, và cache sinh không trộn hai thể chế (25-10)

Ba phần, đều có test phá được (mutation) chứ không chỉ "chạy được":

1. **`tools/loop/run_chain.py`** (+ wrapper `.ps1`/`.sh`, spec JSON trong `chains/`): thay các driver
   `.sh` viết tay bằng spec + manifest tất định (`spec_sha256`, đường dẫn tương đối, không timestamp).
   Preflight env trước bước đầu; từ chối thư mục round đã có dữ liệu (trừ `--resume`); cổng trả mã 1
   **vẫn đi tiếp sang attribute** (kết quả âm phải được quy lỗi), chỉ dừng khi không tạo được báo cáo;
   `--set` chặn biến bí mật. `tests/test_run_chain.py` 11 test, mutation **6/6** bắt
   (`tmp/mutation_check_t7.py`). Đã chạy end-to-end chuỗi demo 2×20 item + gate "ĐẠT" + attribute.
2. **`src/cache_policy.py`**: khóa cache của `GeminiGenerator`/`QwenGenerator` mang thêm trường `policy`
   **khi và chỉ khi** ngưỡng cứu/từ chối/guard/chọn câu bằng chứng/chuẩn hóa lệch mốc
   `DEFAULT_CACHE_TOKEN = d0b4c6a65f83`. Thể chế mặc định giữ **đúng công thức cũ 4 trường** (bất biến
   #2, 351+ entry cache còn dùng); đổi một ngưỡng là tách không gian cache. `tests/test_cache_policy.py`
   26 test, mutation **10/10** bắt (`tmp/mutation_check_cache_policy.py`, phục hồi byte-identical).
   Đánh đổi đã ghi: đổi ngưỡng hậu xử lý buộc sinh lại — thà tốn lượt hơn trộn hai thể chế.
3. **Sổ quyết định `docs/DECISION_LOG.md`** (20 quyết định D-01…D-20, mỗi dòng ngày/giả thuyết/số
   đo/file nguồn/trạng thái) + README mục 5.10 (cách chạy) và 8.1 ("Giới hạn thật lòng").

Toàn repo **1.004 passed**. **Chưa commit** được vì HEAD thiếu 41 file nguồn/công cụ/test và 6 file
đang sửa dở của phiên T3–T5 ⇒ **PA-26** (ba phương án commit freeze; đề xuất (ii): commit mã + tổng
hợp round, không commit `models/`, `chroma_*`, `full.jsonl`).

### P5.6 — số đo hiện trạng (round r0, pha truy xuất, 811 item, 23-10)

| Chỉ số | Giá trị |
|---|---|
| gold@6 toàn bộ (item có chunk vàng, 700/811) | **51,86%** (363/700) |
| `FAIL_RETRIEVAL` | 337/811 = **41,6%** |
| Trong đó chunk vàng bị `source_filter` cắt khỏi cửa sổ | 244/337 = **72,4%** |
| &nbsp;&nbsp;• do nhãn chủ đề SAI (lever classifier) | 179 |
| &nbsp;&nbsp;• do bảng `TOPIC_SOURCE_FILTER` quá hẹp (lever router) | 65 |
| Lỗi xếp hạng khi không lọc / dù đã lọc đúng nguồn | 58 / 35 |
| Family yếu nhất | EXACT 8/52 = 15,4%; TRAP_OCR 17,6%; TRAP 21,7%; NUMERIC 26,8% |
| Family mạnh nhất | CLOZE_OCR 176/206 = 85,4% |
| Nhầm chủ đề đắt nhất | hành chính sinh viên → học phí (37 item), hành chính sinh viên → quy chế CT SV (27) |

Kết luận dẫn tới hành động: **kẻ phá recall lớn nhất không phải mô hình nhúng mà là
chính bộ định tuyến** — nó phạt sai lầm của classifier bằng cách XÓA toàn bộ nguồn
khỏi cửa sổ truy xuất thay vì chỉ ưu tiên nguồn đúng. Văn bản bị chặn nhiều nhất
là `KH To chuc HK 261 - 20260612.pdf` (73 item). P5.7 đổi phép cắt cứng thành cộng
ưu tiên hạng (`ROUTER_FILTER_RANK_BONUS`, mặc định 3) và round r1 đo lại đúng một
biến số đó trên cùng 811 item.

Số ở bảng trên là số sau khi **chấm lại** bằng `verify.py` hiện hành. Bản verdict ghi
trong lần chạy đầu bị hỏng bởi chính bug của trọng tài (`has_gold_chunk` chưa được kiểm
tra) khiến 97 item không có chunk vàng bị đếm nhầm thành `FAIL_RETRIEVAL` (434 thay vì
337). Bài học: sửa trọng tài là phải chấm lại các round cũ — runner tự làm được việc đó
vì `<phase>.jsonl` đã đủ dòng thì nó bỏ qua pha gọi model, chỉ chấm lại.

### P5.11 — cổng r1 nói gì (23-10, 811 item chung)

| Chỉ số | r0 (cắt cứng) | r1 (lọc mềm, bonus 3) |
|---|---|---|
| gold@6 trên 700 item có chunk vàng | 51,86% | **76,57%** (+24,7 điểm) |
| `FAIL_RETRIEVAL` | 337 | 164 |
| Chunk vàng bị `source_filter` cắt khỏi cửa sổ | 244 (72,4%) | **0** |
| Hồi quy / cải thiện theo item | — | recall: 9 mất + 182 vào cửa sổ |
| **Neo HUMAN: đúng văn bản còn trong top-6** | **81,44%** | **77,32%** (-5,06% tương đối) |
| Kết luận cổng | — | `KHÔNG ĐẠT` (exit 1) — luật `human_anchor_source_not_degraded` |

Lọc mềm đúng như dự đoán về recall (đòn bẩy cắt cứng biến mất hoàn toàn, 182 chunk
vàng vào lại cửa sổ) nhưng cái giá nằm ở 97 câu do **người** viết: khi nhãn router
ĐÚNG, phép cắt cũ bảo đảm cửa sổ toàn văn bản đúng; bỏ cắt thì văn bản đúng bị các
nguồn khác tràn chỗ. Probe 14 item trên trục bonus (cùng pipeline, cùng vector store):

| Cấu hình | 6 câu neo (nhãn đúng) còn đúng nguồn trong top-6 | 8 item r0 trượt do cắt (nhãn sai) kéo được gold |
|---|---|---|
| cắt cứng (r0) | 6/6 | 1/8 |
| mềm, bonus 0 | 0/6 | 8/8 |
| mềm, bonus 3 (r1) | 2/6 | 8/8 |
| mềm, bonus 12 | **6/6** | **7/8** |

`bonus ≥ cỡ cửa sổ` = "ưu tiên tuyệt đối nhưng không xóa ứng viên": chunk đúng nguồn
xếp trước, phần còn lại của cửa sổ do nguồn khác điền — giữ được cả hai phía. Round
`r2` đo lại toàn bộ 811 item đúng một biến số đó; cổng mở hai lần (r2 vs r0 = cả đòn
bẩy, r2 vs r1 = riêng knob bonus) trước khi quyết định đổi mặc định.

**Số của r2 (23-10, 811 item, `ROUTER_FILTER_RANK_BONUS=12`, chữ ký trọng tài
`342d42bf3ea4` — giống hệt r0/r1 nên ba cổng so được nhau):**

| Cổng | Kết quả | Vì sao |
|---|---|---|
| r2 vs r0 (cả đòn bẩy) | **ĐẠT** (exit 0) | gold@6 51,86% → **74,00%**; `FAIL_RETRIEVAL` 337 → 182; neo HUMAN **81,44% → 81,44%** (không mất, đúng cái r1 vấp); 161 recall + 188 anchor cải thiện |
| r2 vs r1 (riêng knob bonus) | **KHÔNG ĐẠT** (exit 1) | gold@6 76,57% → 74,00% (vượt ngưỡng -0,02); neo HUMAN 77,32% → **81,44%** (+5,33%) |

Hai cổng nói hai điều khác nhau và đều đúng: so với cắt cứng thì lọc mềm thắng mọi mặt;
so với nhau thì bonus 12 **mua neo HUMAN bằng gold@6**. Probe cơ chế trên 21 item hồi
quy (`tmp/probe_bonus_regressions.py`, chấm từ dữ liệu đã lưu, không gọi model) cho thấy
**cả 21/21 item có chunk vàng nằm NGOÀI `source_filter`** của router: ở bonus=12 cửa sổ
bị nguồn được ưu tiên chiếm gần hết nên chunk vàng của nguồn khác bị đẩy ra, còn bonus=3
vẫn chừa chỗ cho nguồn khác. Family thiệt hại vì thế tập trung ở `SOURCE_LOOKUP`
(-0,0883) và `CLOZE` (-0,0392).

Kết luận kỹ thuật: con số bonus **không phải** chỗ sửa đúng. Lỗi thật là "một nguồn được
ưu tiên có thể chiếm TOÀN bộ cửa sổ" — kể cả khi router chọn sai nguồn (47,2%
`FAIL_RETRIEVAL` của r2 vẫn do filter, xem `attribution_retrieval.json`:
`filter_blocked_wrong_topic` 66 + `filter_blocked_wrong_table` 20). Lever tiếp theo vì
vậy là **hạn ngạch nguồn** (mỗi nguồn nhiều nhất ⌈k/2⌉ ô trong cửa sổ) thay vì chỉnh
constant; còn **mặc định production chưa chốt**: theo luật merge (so với baseline đã
duyệt = r0) thì ứng viên hợp lệ duy nhất hiện nay là r2/bonus=12, nhưng round r1/bonus=3
bị chính luật đó chặn vì neo HUMAN. Vì vậy các round đo tiếp vẫn chạy **đúng cấu hình
truy xuất của r1 (bonus=3)** để cô lập một biến số, còn mặc định sẽ chốt sau round hạn
ngạch nguồn — nếu hạn ngạch thắng cả hai cổng thì đó là cấu hình được merge.

Bài học vận hành round (đã ghi vào runner): pha nào cũng phải chạy cùng
`ENABLE_CLASSIFIER`, và `GENERATION_CACHE_DIR` phải trỏ vào cache **lạnh** dùng chung
cho mọi round — để cache cũ thì hầu hết câu là cache-hit, `ENABLE_ANSWER_GUARD` không
bao giờ chạy và vòng lặp đo sai lever sinh.

Quy tắc cứng của giai đoạn này (chi tiết trong `data/loop/README.md`): đáp án test
không do AI viết; item split=test không bao giờ thành dữ liệu train; mọi vòng lặp chấm
bằng code vì quota Gemini ~14 request/ngày; lỗi được quy về đúng tầng trước khi retrain.

Nguồn: `prompts/README.md` (bảng nhiệm vụ, thời lượng từng giai đoạn và các cổng kiểm tra).

---

Mọi số liệu trong văn bản này được chép nguyên từ nguồn ghi dưới từng bảng; không có số liệu ước lượng.
