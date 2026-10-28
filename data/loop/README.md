# Vòng lặp tự kiểm chứng & tự huấn luyện (data/loop)

Mục tiêu cuối cùng của toàn bộ thư mục này: **con AI của đồ án trả lời đúng, và khi
không đủ căn cứ thì nói "không đủ thông tin" — tuyệt đối không bịa.** Vòng lặp không
tự nó làm AI giỏi hơn; nó chỉ ra *chính xác* chỗ nào AI sai và chỗ nào thuộc tầng nào
để sửa, rồi bắt mọi sửa đổi phải vượt qua một cổng đo được.

## Sơ đồ một vòng

```
data/corpus (tài liệu gốc)
   │  trích xuất nguyên văn (không do AI viết)
   ▼
testset_v1.jsonl  ──811 item──►  run_round.py --phase retrieval   (rẻ, ~3s/item)
   │                              │  FAIL_RETRIEVAL / PENDING_GENERATION
   │                              ▼
   │                        select_for_generation (stratified subset)
   │                              │
   │                              ▼
   │                        run_round.py --phase full  (pipeline thật, Qwen offline)
   │                              │
   ▼                              ▼
gate.py ◄── verify.py (trọng tài deterministic: PASS_*/FAIL_*)
   │  ĐẠT  ─► merge thay đổi, mở round tiếp theo
   │  KHÔNG ĐẠT ─► giữ bản cũ
   ▼
triage.py ─► trainpool_additions.jsonl (chỉ từ item split=trainpool)
   ▼
retrain ĐÚNG tầng gây lỗi (retrieval / generation / refusal / guardrail / classifier)
```

## Bảy bất biến chống tự lừa mình

1. **Gold không do AI viết.** Mọi đáp án trong test set được *trích nguyên văn* khỏi
   chunk trong ChromaDB (`tools/loop/testset.py` assert điều này: `gold` phải xuất
   hiện đúng chuỗi trong văn bản nguồn). Một bộ test do AI soạn = một vòng lặp tự
   khẳng định mình.
2. **Test không bao giờ thành dữ liệu train.** Chia theo C-level = theo **từng văn
   bản** (`hash(fold(source)) % 100 < 55 → test`), không chia theo câu hỏi: hai câu
   hỏi cùng một Điều mà một vào train một vào test thì train đã "nhìn thấy" đáp án.
   `triage.py` từ chối ghi dòng train nào có `split == "test"` và đếm `blocked_test_leak`.
3. **Hai kho mẫu câu tách rời.** `POOL_A` (sinh item trainpool) và `POOL_B` (sinh item
   test) không giao nhau — bài học từ classifier v1, khi mẫu train và mẫu đánh giá
   viết theo cùng một khuôn khiến điểm ảo cao.
4. **Một trọng tài duy nhất cho cả đo lẫn production.** `src/answer_guard.py` vừa là
   guardrail chặn câu trả lời trong `QwenGenerator.generate_answer` (khi
   `ENABLE_ANSWER_GUARD=1`), vừa là trọng tài của `verify.py`. Số đo và hành vi thật
   không thể lệch nhau.
5. **Mỗi round tự ký dụng cụ đo đã chấm nó.** Round ghi `settings.referee` =
   `verify.referee_fingerprint()` (SHA-256 của `verify.py` + `answer_guard.py` +
   `text_utils.py`); `gate.compatibility()` từ chối so hai round khác chữ ký. Lý do
   bằng máu: verdict r0 ghi bằng `verify.py` còn bug `has_gold_chunk` nên 97 item
   không có chunk vàng bị đếm nhầm thành `FAIL_RETRIEVAL` (434 thay vì 337) — và nếu
   không có chữ ký thì round r1 đã so với một cái thang bị gãy. Sửa trọng tài thì
   chạy lại lệnh round cũ khi `<phase>.jsonl` đã đủ dòng: runner bỏ qua pha gọi model,
   chỉ chấm lại.
6. **Một item một id, một round một tập đo cố định.** `testset.resolve_id_collisions()`
   hậu tố hóa id va chạm (`…#2`) và `main()` assert id độc nhất; `run_round.plan_subset()`
   chọn tập đo từ **toàn bộ** pool chứ không từ phần chưa chạy, và cuối run nén
   `<phase>.jsonl` về đúng tập đó (một dòng mỗi id). Hai lỗ này từng mở cùng lúc:
   id va chạm làm 6/811 item bị chấm bằng gold của item khác và 6 item không bao giờ
   được đo, còn `--limit` áp lên `todo` khiến mỗi lần chạy lại để chấm lại THÊM 100
   item mới (r0/full phình 100 → 178 → 181 dòng). Tập đo di dịch thì
   `--pin-subset-from` của round sau nuốt cả xác của round trước và cổng không còn so
   trên cùng một thang.
7. **Dòng train phải tự chứa căn cứ cho đáp án của nó.** `triage.blocks_for_sft()` ưu
   tiên chunk vàng (không cắt `contexts[:4]` mù) và `target_fragments()` bỏ dòng train
   nếu đáp án mẫu không xuất hiện trong chính ngữ cảnh của dòng đó
   (`skip_sft_target_not_in_context`: 4/6 dòng bị loại ở r1/r0). Lý do: sinh dữ liệu
   SFT từ ca lỗi mà ngữ cảnh không chứa đáp án là *tự tay dạy model bịa* — vòng lặp sẽ
   phá mục tiêu số một của đồ án thay vì sửa nó.

## Vì sao không dùng LLM judge / token-overlap

- **LLM judge**: quota Gemini ~14 request/ngày (đo thực tế) — không thể chấm hàng
  nghìn câu mỗi vòng, và điểm sẽ phụ thuộc model đang đổi.
- **Token-overlap** (`src/faithfulness_heuristic.py`): câu trả lời chép 90% chữ của
  context nhưng sửa đúng chỗ nguy hiểm nhất vẫn đạt điểm cao. Vụ có thật:
  `outputs/ab_results_with_classifier.json` Q01 trả lời mã lớp **CON515** trong khi
  tài liệu ghi **CON915** — metric cũ chấm ĐÚNG. `check_grounding` gọi nó là
  `FAIL_FABRICATED`.
- Trọng tài mới kiểm tra **từng thực thể**: số (450.000 / 2 tín chỉ), mã văn bản
  (1054-QĐ, CON915), Điều/Khoản/Mục, ngày, cụm tên riêng. Thực thể được coi là có
  căn cứ nếu xuất hiện trong contexts (so sau `fold`, chuẩn hóa nhóm nghìn) **hoặc**
  do chính người hỏi nêu trong câu hỏi.

## Tệp trong thư mục

| File | Vai trò |
|---|---|
| `testset_v1.jsonl` | 811 item đã neo bằng chứng (407 test / 404 trainpool) |
| `testset_v1_manifest.json` | sinh nhật test set, phân bố family, fingerprint corpus `0118b048ad790341`, số item bị loại vì mơ hồ (`dropped_ambiguous_query: 83`) |
| `rounds/<r>/retrieval.jsonl` | kết quả pha truy xuất (không sinh văn bản) |
| `rounds/<r>/full.jsonl` | kết quả pipeline thật (sinh văn bản) |
| `rounds/<r>/verdicts_<phase>.jsonl` | một dòng/item: verdict + tín hiệu triage |
| `rounds/<r>/round_summary_<phase>.json` | phân bố verdict, theo family/split, bản đồ lever |
| `rounds/<r>/gate_vs_<baseline>_<phase>.json` | báo cáo cổng duyệt |
| `rounds/<r>/trainpool_additions.jsonl` | dữ liệu train sinh ra từ lỗi (chỉ split trainpool) |
| `rounds/<r>/attribution_<phase>.json` | phân nhánh `FAIL_RETRIEVAL`: do router cắt nguồn (nhãn sai / bảng allowlist hẹp) hay do xếp hạng — `tools/loop/attribute.py`, có `--compare` để so hai round |

Family: `EXACT`, `NUMERIC`, `CLOZE`, `CLOZE_OCR`, `SOURCE_LOOKUP`, `YESNO_FACT`,
`REVERSE_LEGAL`, `TRAP`, `TRAP_OCR`, `REFUSE_OOD`, `REFUSE_MISSING_DOC`, `HUMAN`.
Nhóm `_OCR` kiểm chứng trên chunk mất dấu thanh (299/361 chunk chỉ còn ~0,10–0,22 tỉ
lệ dấu) — tức là kiểm cả giới hạn của corpus. `HUMAN` (97) là neo do người viết, có
cờ `contaminated_by_v2_classifier` vì đã dùng một phần để huấn luyện; nó chỉ dùng để
đo xu hướng, không dùng để "chứng minh" tổng quát hóa.

## Hiệu chỉnh trọng tài trước khi tin nó (`tools/loop/audit_guard.py`)

Một trọng tài chưa được audit sẽ retrain nhầm tầng. `audit_guard.py` chạy
`check_grounding` trên 50 câu đã trả lời của `outputs/ab_results_with_classifier.json`
(câu trả lời cũ, không tốn request nào) rồi gán NHÃN THỨ BA cho từng khẳng định bị
đánh dấu, bằng cách tìm nó trong TOÀN BỘ corpus:

| Nhãn | Nghĩa | Xử lý |
|---|---|---|
| `FABRICATED` | không tồn tại ở bất kỳ chunk nào | AI bịa — đưa vào SFT refusal/extractive |
| `UNSOURCED` | có trong corpus nhưng không nằm trong contexts đã truy xuất | lỗi truy xuất/attribution — sửa tầng retrieve |
| `LOOKS_LIKE_FORMATTING` | chỉ là marker định dạng hoặc cụm bị cắt sai ranh giới | **sửa trọng tài**, không sửa model |

Kết quả hiệu chỉnh trên dữ liệu thật (23/10):

- Trước: 16/50 câu bị flag. Sau khi bỏ quy tắc "số thứ tự ở đầu dòng" (42/45 thực thể
  loại number chỉ là marker `1.`, `12)` của danh sách markdown): còn 11/50, và
  **không mất một FABRICATED nào** (21 thực thể bịa vẫn bị bắt hết).
- 9/50 câu (18%) chứa ít nhất một khẳng định bịa thật — `CON515` (đúng là vụ Q01),
  `COS305/COS306`, `Khoản 5`… Đây chính là lỗ mà metric cũ (token-overlap, LLM judge)
  đã bỏ qua.
- `extra_haystack` được thêm vào `check_grounding` vì pipeline tự dán tên văn bản vào
  cuối câu trả lời; nếu không, mọi số trong tên file (`1059-qd-dhag-2020-09-28.pdf`)
  sẽ bị gọi là chữ bịa.

## Cách chạy một vòng

Hai quy tắc sống còn (r0 suýt cho số sai vì phạm phải):

- **Mọi round đều chạy cùng `ENABLE_CLASSIFIER=1`.** Pha truy xuất gọi classifier trực
  tiếp khi cờ bật; thiếu nó thì round "không có router" nhưng lại được so với round có
  router — cổng so hai pipeline khác nhau chứ không so một đòn bẩy.
- **`GENERATION_CACHE_DIR` phải trỏ cache LẠNH dùng chung cho mọi round** (`tmp/loop_gen_cache`).
  Để `./.generation_cache` (đã ấm từ thời prompt cũ) thì đa số câu là cache-hit,
  `ENABLE_ANSWER_GUARD` không bao giờ được chạy và vòng lặp đo sai lever sinh.
- **Chạy lại một round đã xong là hợp lệ, nhưng MỘT lúc chỉ MỘT runner cho một round.**
  `plan_subset()` chọn tập đo từ toàn bộ pool nên lần chạy lại sinh `lần này=0` rồi chấm
  lại ngay (đây là cách chính thức để áp dụng bản sửa của trọng tài), và cuối run file
  `<phase>.jsonl` bị nén về đúng tập đo. Hai runner cùng chạy trên một round thì
  ngược lại: cả hai cùng thấy "chưa chạy" và cùng sinh thêm item, số đo của round thành
  hai lát cắt của hai tập item khác nhau (đã xảy ra với r0/full: 100 → 178 dòng).

```bash
# 0) (đã chạy một lần) sinh bộ test
python tools/loop/testset.py

# 0b) hiệu chỉnh trọng tài trên dữ liệu cũ (làm LẠI mỗi khi sửa answer_guard.py)
python tools/loop/audit_guard.py outputs/ab_results_with_classifier.json

# 1) pha rẻ: chấm truy xuất cho TRỌNG bộ 811 item, không tốn Ollama (~38 phút)
ENABLE_CLASSIFIER=1 \
python tools/loop/run_round.py --round r0 --phase retrieval --split all --top-k 6

# 2) pha đắt: sinh văn bản trên subset cân bằng theo family (không ăn quota Gemini)
USE_QWEN_GENERATOR=1 ENABLE_ANSWER_GUARD=1 ENABLE_CLASSIFIER=1 \
GENERATION_CACHE_DIR=tmp/loop_gen_cache \
python tools/loop/run_round.py --round r0 --phase full --split all \
  --limit 100 --strategy stratified --only-retrieved

# 3) lỗi -> dữ liệu train (chỉ item trainpool)
python tools/loop/triage.py --round r0

# 4) sau khi sửa tầng gây lỗi, chạy round mới rồi MỞ CỔNG
#    --pin-subset-from giữ NGUYÊN tập item của r0 để hai round so sánh trên cùng
#    thang đo (không pin thì subset đổi theo kết quả truy xuất của chính round ->
#    phần giao teo lại, cổng mất ý nghĩa).
USE_QWEN_GENERATOR=1 ENABLE_ANSWER_GUARD=1 ENABLE_CLASSIFIER=1 \
GENERATION_CACHE_DIR=tmp/loop_gen_cache \
python tools/loop/run_round.py --round r1 --phase full --split all \
  --limit 100 --strategy stratified --only-retrieved --pin-subset-from r0
python tools/loop/gate.py --candidate r1 --baseline r0 --phase full   # exit 0 = ĐẠT

# 4b) nếu đòn bẩy là truy xuất, đo riêng bằng pha rẻ (toàn bộ 811 item, ~38 phút)
ENABLE_CLASSIFIER=1 ROUTER_SOFT_FILTER=1 \
python tools/loop/run_round.py --round r1 --phase retrieval --split all --top-k 6
python tools/loop/gate.py --candidate r1 --baseline r0 --phase retrieval
```

**Sửa trọng tài thì làm gì với round cũ:** `verify.referee_fingerprint()` chỉ băm
`tools/loop/verify.py` + `src/answer_guard.py` + `src/text_utils.py`; `gate.compatibility()`
từ chối mở cổng giữa hai chữ ký khác nhau. Cách chấm lại: chạy lại ĐÚNG lệnh round (kèm ĐÚNG
env của round đó) — khi `<phase>.jsonl` đã đủ dòng, runner bỏ qua pha gọi model và chỉ chấm
lại, rồi cập nhật chữ ký. Đã áp dụng sau vá `answer_guard` 23-10: cả 7 pha (r0 retrieval+full,
r1 retrieval+full, r2 retrieval, r3 full, r4 retrieval) mang chữ ký `9f1179ccab74`, verdict
không đổi, gate kết luận như cũ. CẤM sửa file trọng tài khi một round còn đang chạy.

## Đòn bẩy router (`src/router.py`)

| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `ROUTER_SOFT_FILTER` | `0` (TẮT) | `source_filter` thành **ưu tiên hạng** thay vì cắt cứng; nhánh Chroma cũng thôi lọc lúc tìm để ứng viên ngoài nguồn còn cơ hội vào cửa sổ |
| `ROUTER_FILTER_RANK_BONUS` | `3` | số hạng được cộng cho chunk thuộc nguồn router chọn (0 = không ưu tiên gì, chỉ ngừng cắt). **Giá trị 12 từng qua cổng ở tầng truy xuất sau r2/r4 (neo HUMAN 0,8144); đo lại ở r7 cùng guard chuẩn hóa: chênh với r6 nằm trong băng nhiễu ±3, `PASS_CORRECT` đi ngang, và 2 item `PASS_CORRECT` rơi xuống từ-chối-oan vì chunk cần thiết bị đẩy ra cửa sổ 12 slot ⇒ bonus 12 không được xác nhận là cộng thêm giá trị — chọn 3 hay 12 cần phép đo lặp lại/cỡ mẫu lớn hơn** — xem mục "r7" bên dưới và `ROADMAP.md` P5.17 |
| `ROUTER_SOURCE_QUOTA` | `0` (TẮT) | hạn ngạch suất trong cửa sổ ứng viên: không nguồn nào quá N suất, phần hoãn **nối vào cuối theo thứ tự cũ** (mất ưu tiên, không mất suất). Sinh ra từ probe 21/21 item hồi quy của r2 — xem `ROADMAP.md` P5.14. Đo ở r4: chạy thật, vô hại (gold@6 +0,29, neo không đổi) nhưng **không** hồi phục khoảng cách với r1 ⇒ giả thuyết cấu trúc bị bác, **giữ TẮT làm mặc định** |

## Đòn bẩy tầng sinh (`src/generator.py`)

| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `ENABLE_ANSWER_RESCUE` | `0` (TẮT) | khi model trả về lời từ chối mà chunk vàng đã nằm trong ngữ cảnh và câu hỏi đòi MỘT giá trị cụ thể (`demands_specific_value`, kim không dấu so qua `fold()`), hỏi lại MỘT lượt với chỉ dẫn trích xuất. **Đo xong và BỊ BÁC ở r5b: 60/64 lượt thử thật, cứu được 1 câu (1,7%) ⇒ không bật, không round cứu nào nữa** — xem mục "r5b" bên dưới và `ROADMAP.md` P5.15c |
| `RESCUE_MIN_SCORE` | `0.8` | ngưỡng chấp nhận câu được cứu, chặt hơn guardrail sản xuất (`ANSWER_GUARD_MIN_SCORE=0.6`); ứng viên còn phải có `unsupported` rỗng và `grounding_score is not None` |

Hai biên được test ghim (`tests/test_answer_rescue.py`, 23 test — 3 test `raw_query` của
P5.15b nằm trong đó): 37/38 ca
`FAIL_OVERREFUSAL` đủ điều kiện cứu, và 16/19 ca `PASS_REFUSAL` CŨNG đủ điều kiện — lever
an toàn chỉ vì ứng viên phải qua `check_grounding`, ri ro thật là chuyển thành
`FAIL_HALLUCINATED_ON_UNANSWERABLE`. Ba câu bẫy "… phải không?" cố ý đứng ngoài danh sách.

## Đòn bẩy tầng chuẩn hóa câu hỏi (`src/query_normalizer.py`)

| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `NORMALIZE_SANITY_GUARD` | `0` (TẮT) | bác bản chuẩn hóa nếu nó (a) trùng nguyên văn một dòng few-shot đang dùng để dựng prompt, (b) rỗng, hoặc (c) giữ dưới `NORMALIZE_MIN_CONTAINMENT` token của câu gốc → **dùng câu gốc** và in `[QueryNormalizer] Bác bản chuẩn hóa…`. **Đo ở r6: ĐẠT cả hai tiêu chí đăng ký trước ⇒ là lever duy nhất của pha sinh đã được chứng minh bằng quy lỗi cấp item; bật làm mặc định production đang chờ người dùng duyệt** — xem mục "r6" bên dưới và `ROADMAP.md` P5.16 |
| `NORMALIZE_MIN_CONTAINMENT` | `0.3` | ngưỡng (0..1, giá trị hỏng → mặc định). Chốt theo phân bố đo trên 300 lượt sinh: median 1,00, p10 0,46, hai mode hỏng nằm ở 0,12–0,27 |

Vì sao tầng này nằm trong vòng lặp chống bịa: `pipeline.run` đưa `normalized_query` vào
CẢ truy xuất lẫn sinh, nên khi bộ chuẩn hóa (Local SLM, temp 0.0) echo một dòng ví dụ
hoặc tự trả lời thay vì chuẩn hóa, item hỏng từ gốc — 16/300 lượt đo được, và 5/23 ca
`FAIL_RETRIEVAL` của r1 ở pha đắt thuộc nhóm này. Xem `ROADMAP.md` P5.16.

## Ablation tầng sinh T1 — điều kiện chạy cấu hình (b) ĐĂNG KÝ TRƯỚC (23-10, trước khi có số)

Script `tools/diag/ablation_generation.py` chạy ba cấu hình trên đúng 100 item pha sinh
của r5, chấm bằng trọng tài hiện tại. Cấu hình (b) (Gemini + top-6 của r5) **chỉ được
chạy nếu (a) thấp hoặc không kết luận được**; nếu (a) cao thì BỎ (b) và ghi lý do vào
báo cáo T1. Khi chạy, (b) tuân thủ nguyên tắc đã duyệt với người dùng:

- **n = 30**, mẫu từ các item `FAIL_OVERREFUSAL` của r5 **có chunk vàng trong cửa sổ**
  (tập "năng lực model" nghi phạm số một), phân tầng theo family, seed cố định;
- danh sách id chốt vào `data/loop/diag/b_gemini_top6/sample_ids.json` TRƯỚC khi gọi
  API đầu tiên;
- rải theo quota thực đo ~14 lượt/ngày, có checkpoint: item đã có dòng kết quả trong
  `rows.jsonl` KHÔNG được gọi lại;
- báo cáo phải ghi rõ "(b) = n=30 trên nhóm over-refusal" — **không ngoại suy** kết luận
  (b) ra toàn bộ 100 câu.

Ngân sách đăng ký: mỗi item đúng 1 lượt Gemini (cache lạnh riêng trong thư mục diag,
`QWEN_FALLBACK=0` ép tắt để lỗi không bị tráo thành Qwen). (a) và (c) là 80 lượt Ollama
cục bộ mỗi cấu hình, 0 Gemini (20 item HUMAN/REFUSE không có chunk vàng bị loại khỏi
(a)/(c) và ghi danh sách trong `settings.json`).

## T3 — Decoupled refusal + Evidence selection: ĐẶC TẢ + NGƯỠNG ĐĂNG KÝ TRƯỚC (24-10, VIẾT TRƯỚC KHI CHẠY r8/r9 — không chỉnh lại sau khi có số)

**Mục tiêu:** giảm from chối oan (r5: `refusal_rate` 0,69, `FAIL_OVERREFUSAL` 37/100) mà
KHÔNG tăng số câu bịa (r5: `fabrication_rate_on_answered` 0,0323 = 1/31;
`FAIL_HALLUCINATED_ON_UNANSWERABLE` 2). Tiêu chí xong đăng ký tại đây:
`PASS_CORRECT >= 25/100` **và** fabrication không tăng (gate delta 0). Nếu không đạt ⇒ ghi
kết quả **âm kèm phân tích**, KHÔNG thêm lever thứ ba để cứu số.

**Đòn bẩy (mặc định TẮT, module mới `src/refusal_policy.py` + `src/evidence_selection.py`;
KHÔNG sửa `src/answer_guard.py`/`tools/loop/verify.py`/`src/text_utils.py` — chỉ import):**

| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `ENABLE_DECOUPLED_REFUSAL` | `0` (TẮT) | (1) prompt Qwen MỚI không còn đường từ chối, `PROMPT_VERSION` tách nhánh `v2.0-extract-only` nên cache cũ (`v1.3`) không bị đụng và không bị.invalidate; (2) quyền từ chối chuyển xuống tầng ngoài, quyết định deterministic theo ba tín hiệu dưới đây |
| `ENABLE_EVIDENCE_SELECTION` | `0` (TẮT) | extract-then-generate: thay cửa sổ ~8k ký tự bằng 3–5 CÂU bằng chứng. Bậc thang xếp hạng (viết lại 05:5x 24-10, TRƯỚC khi chạy round nào): **tier 3** = câu chứa thực thể phía câu hỏi (số/mã/ngày/tên riêng); **tier 2** = câu chia sẻ ≥ `EV_MIN_KEYWORD_HITS` (2) từ khóa phía câu hỏi; **tier 1** = câu trùng tên nguồn router gọi hoặc chỉ một từ khóa; trong cùng tier → điểm reranker, rồi thứ tự gốc. Lấy tối đa `EV_MAX_SENTENCES` câu, ưu tiên nhóm tier ≥ 2; chưa đủ `EV_MIN_SENTENCES` thì nới xuống tier ≥ 1; vẫn chưa đủ ⇒ GIỮ NGUYÊN window. (Lý do có tier 2: câu hỏi không chứa thực thể — "Sinh viên học lại tối đa bao nhiêu lần?" — làm luật chỉ-dựa-thực-thể vĩnh viễn không kích hoạt.) |
| `DEC_MIN_ENTITY_COVERAGE` | `0.34` | ngưỡng ĐỘ PHỦ thực thể phía câu hỏi trong MỘT chunk (dưới 1/3 ⇒ chunk coi như không trả lời được câu hỏi) |
| `DEC_MIN_TOKEN_OVERLAP` | `0.20` | ngưỡng thay thế: tỉ lệ token nội dung (fold, dài ≥4, bỏ stopword pháp lý chung) của câu hỏi xuất hiện trong chunk |
| `DEC_MIN_RRF_NORM` | `0.90` | ngưỡng ĐIỂM TRUY XUẤT: điểm RRF chuẩn hóa của chunk đạt chuẩn liên quan tốt nhất, `rrf_norm = w_bm25/(c+rank_bm25) + w_vec/(c+rank_vec)` chia cho giá trị cực đại `1/(c+1)` với `c = src.pipeline.DEFAULT_RRF_C`. Quy đổi thực tế: 1,00 = hạng 1 cả hai nhánh; 0,90 ≈ không được rơi quá ~hạng 5-6 fusion. < ngưỡng ⇒ từ chối |
| `DEC_MIN_GROUNDING` | `0.60` | sau sinh: `check_grounding(...).grounding_score` phải ≥ ngưỡng (lấy đúng mức guardrail production `ANSWER_GUARD_MIN_SCORE`) |
| `DEC_MAX_UNSUPPORTED` | `1` | sau sinh: số khẳng định không căn cứ tối đa chấp nhận (1 là đủ để từ chối, cùng chuẩn với guardrail) | <!-- sửa 24-10: một ký tự CJK lạc trong ô "Ý nghĩa" của dòng này (viết "đồng口径") đã được thay bằng "cùng chuẩn"; KHÔNG đổi ngưỡng, không đổi ý nghĩa luật, và dòng này là mô tả chứ không phải tham số runtime --> |
| `EV_MIN_SENTENCES` / `EV_MAX_SENTENCES` | `3` / `5` | khung số câu bằng chứng; nếu cửa sổ không đủ 3 câu đạt chuẩn thì GIỮ NGUYÊN window (không tự chế thêm văn bản) |
| `EV_MIN_KEYWORD_HITS` | `2` | số TỪ KHÓA phía câu hỏi (fold, dài ≥3, trừ hư từ chức năng) mà một câu phải chia sẻ để được xếp tier 2 — bổ sung 05:5x 24-10 TRƯỚC khi chạy round nào, vì `extract_entities()` trên câu hỏi không chứa số/mã trả về rỗng nên luật chỉ-dựa-thực-thể sẽ vĩnh viễn không kích hoạt |
| `EVIDENCE_RERANKER` | `bge-reranker-base` | reranker cross-encoder; nếu môi trường không tải được thì lùi về `bge-m3` cosine (bi-encoder) và round phải GHI rõ trong `round_summary_full.json` — số của r9 khi đó đọc là "chọn câu theo bi-encoder", không phải cross-encoder |

**Luật từ chối (tầng ngoài, chỉ khi `ENABLE_DECOUPLED_REFUSAL=1`), chốt ở đây và không đổi:**
1. `not is_enough_evidence(contexts)` (import từ `src/answer_guard.py`) ⇒ `REFUSAL_TEXT`, lý do `no_evidence`.
2. KHÔNG chunk nào trong cửa sổ generator đạt `(coverage >= 0.34) hoặc (overlap >= 0.20)` ⇒ từ chối, lý do `off_topic_window`.
3. Chunk đạt chuẩn tốt nhất có `rrf_norm < 0.90` ⇒ từ chối, lý do `weak_retrieval_rank`.
4. Sau sinh: `grounding_score is None` (câu không chứa khẳng định kiểm chứng được) ⇒ **CHẤP NHẬN** (không có gì để bác); `fabricated` hoặc `unsupported > 1` hoặc `grounding_score < 0.60` ⇒ từ chối, lý do `ungrounded`.
5. Câu trả lời vẫn chứa marker từ chối (`looks_like_refusal`) ⇒ trả `REFUSAL_TEXT`, lý do `model_still_refuses`.
Mọi lý do in một dòng log `[DecoupledRefusal]` để đếm từ log round (không đổi schema `.jsonl`).

**Quy tắc chống rò đáp án (ràng buộc #6):** "thực thể vàng" trong luật 2 và trong mục xếp hạng
bằng chứng được hiểu là **thực thể phía CÂU HỎI** — `extract_entities()` của `src/answer_guard.py`
chạy trên `normalized_query`/`raw_query` + tên nguồn trong `source_filter` của router.
`required_entities`, `primary_entity`, `gold_sentence`, `gold_chunk_id` của testset **không** được
đọc ở runtime; chúng chỉ dùng trong trọng tài và trong phân tích SAU khi đã chốt ngưỡng.

**Quy tắc một biến:** r8 = cấu hình r5 từng ký tự (`classifier 1`, `guard 1`, `soft filter 1`,
`bonus 3`, `rescue 1`, `sanity guard 0`, `top_k 6`, `pin-subset-from r0`, cache lạnh
`tmp/loop_gen_cache_r8`) + `ENABLE_DECOUPLED_REFUSAL=1`. r9 = r8 + `ENABLE_EVIDENCE_SELECTION=1`
(cache lạnh `tmp/loop_gen_cache_r9`). Không round nào khác được đổi cờ.
**Thứ tự trong luồng (chốt trước khi chạy):** luật 1–3 luôn đo trên **cửa sổ chunk gốc** —
nó phán quyết chất lượng TRUY XUẤT, nên r8 và r9 phải dùng cùng một phép đo ở đây thì hai
round mới chỉ khác nhau đúng MỘT thứ: những gì model được đọc. Chọn câu bằng chứng chạy SAU
luật 1–3 và TRƯỚC khi sinh; `sources` (retrieve_k) không bị động vào nên gold@k của r9 so
được với r8. `contexts` ghi vào row là **cái model đã đọc**, để trọng tài không có căn cứ
"privileged" hơn model.
**CẤM tái dùng tên round** — r6/r7 đã đóng (guard chuẩn hóa / bonus 12), id mới luôn = số lớn
nhất đang có + 1. Gate: `r8 vs r5` và `r9 vs r8` (kèm `r9 vs r5` để đọc tổng biến), chênh lệch
dưới ±3 item nằm trong băng nhiễu T0 (`data/loop/noise_floor.json`) thì KHÔNG được gọi là cải thiện.

**Ngân sách:** 0 lượt Gemini — hai round chạy `offline_qwen` qua Ollama, ~100 lượt sinh/round
(r5 median 16,2 s ⇒ ước tính 30–60 phút/round). Reranker chạy CPU/local, không gọi API.

**→ ĐÃ CHẠY XONG (24-10) và KHÔNG ĐẠT TIÊU CHÍ** (`PASS_CORRECT` 19 < 25 ở cả r8 lẫn r9).
Số và phân tích nằm ở mục "Số đo đã có" (khối **r8 + r9**) và `docs/archive/reports/T3.md`. Toàn bộ ngưỡng
`DEC_*` / `EV_*` ở bảng trên **giữ nguyên như đã đăng ký trước khi chạy** — không có ô nào được sửa
sau khi thấy số. Hai cờ vẫn mặc định TẮT.

## T4 — Probe "năng lực model sinh" (4a) + pipeline SFT trên model triển khai (4b): ĐẶC TẢ + TIÊU CHÍ ĐĂNG KÝ TRƯỚC (24-10 ~09:25, VIẾT TRƯỚC KHI CHẠY r10 — không chỉnh lại sau khi có số)

**Điều kiện vào việc** (chữ T4: "chỉ làm nếu T1 chỉ ra năng lực model là nút thắt"). T1 đã chứng
minh tầng **sinh** là chỗ nghẽn (oracle MỘT chunk vàng vẫn 63/80 từ chối oan, trần `PASS_CORRECT`
8,75% — `data/loop/diag/a_oracle_qwen/summary.json`) và nghiêng về nghi-phạm "năng lực model"
(5/7 câu Qwen-từ-oan được Gemini trả đúng), nhưng **chưa chốt** vì cấu hình (b) mới 7/30 id.
Theo quyết định của user 24-10 (`docs/archive/AUTONOMY_LOG.md`): 4a chạy như phép **THĂM DÒ** song song với
việc resume (b) tới đủ 30 id; **cấm** viết câu "năng lực model là nút thắt" và **cấm** bắt đầu train
4b trước khi (b) đủ 30 id. Phán quyết cuối phải ghi rõ "n=30 trên nhóm over-refusal, không ngoại suy".

**Đòn bẩy mới — `GENERATOR_OLLAMA_MODEL` (mặc định rỗng = TẮT).** Lý do phải có cờ riêng chứ không
dùng `OLLAMA_MODEL`: biến đó hiện dẫn **năm** nơi — `src/generator.py:1050` (tầng sinh),
`src/local_slm.py:232`, `src/query_normalizer.py:419`, `src/classifier.py:553` (chỉ khi
`CLASSIFIER_MODEL` để trống), `src/retrieval.py:299` (splitter). Đổi `OLLAMA_MODEL` là đổi đồng
thời sinh + chuẩn hóa + phân loại + tách câu ⇒ trái quy tắc một biến. Cờ mới **chỉ** được đọc ở
`build_pipeline()` của `tools/loop/run_round.py` và chỉ truyền vào `QwenGenerator(ollama_model=...)`;
rỗng ⇒ `None` ⇒ đúng chuỗi fallback cũ, từng ký tự.

**Manifest bắt buộc ghi** `generator_ollama_model`, `generator_num_ctx`, `generator_temperature`,
`generator_gpu_placement`: `gate.compatibility()` chỉ so khóa `generator` (giá trị `"offline_qwen"`
KHÔNG đổi khi đổi slug model) nên cổng **không nhìn thấy** biến số đang đo — cùng dạng lỗ đã ghi ở
T3, và vì vậy round phải tự ký model đã dùng.

**Quy tắc một biến của r10** = r5 **từng ký tự** (`classifier 1`, `guard 1`, `soft filter 1`,
`bonus 3`, `quota 0`, `rescue 1`, `sanity guard 0`, `top_k 6`, `normalize_query false`,
`pin-subset-from r0`, 100 item) + `GENERATOR_OLLAMA_MODEL=qwen2.5:3b-instruct`, cache lạnh
`tmp/loop_gen_cache_r10`, thư mục round mới. Không đổi gì khác: `PROMPT_VERSION` vẫn `v1.3`
(hai cờ T3 giữ TẮT), `temperature` vẫn `0.1`, `num_ctx` vẫn `QWEN_FALLBACK_NUM_CTX = 8192`,
cửa sổ ngữ cảnh vẫn `QWEN_MAX_TOTAL_CHARS = 10000` / `QWEN_MAX_BLOCK_CHARS = 1600`.
Cache key đã chứa `model` (`src/generator.py:1179`) nên model mới tự miss, không đụng cache r5.

**"Round tốt nhất của T3" — tie-break chốt TRƯỚC khi chạy:** r8 và r9 hòa `PASS_CORRECT` 19/19,
chọn **r9** làm chuẩn vì tiêu chí an toàn im lặng áp đảo: `PASS_REFUSAL` 14 vs 2 và
`FAIL_HALLUCINATED_ON_UNANSWERABLE` 3 vs 12. Vì vậy gate **PHỤ** = `r10 vs r9` (đúng chữ đặc tả T4)
nhưng hai bên lệch nhau ba thứ (model + `ENABLE_DECOUPLED_REFUSAL` + `ENABLE_EVIDENCE_SELECTION`)
nên nó chỉ đọc được là "so với cấu hình T3 tốt nhất", KHÔNG phải one-variable. Gate **CHÍNH** =
`r10 vs r5` (khác đúng model). Chênh ≤ ±3 item = băng nhiễu T0 (`data/loop/noise_floor.json`) ⇒
không được gọi là cải thiện hay thoái hóa.

**Ngưỡng quyết định (đăng ký để báo cáo không biện hộ sau khi thấy số):**
- 3B = "có tín hiệu" nếu `PASS_CORRECT ≥ 22/100` (≥ r5 + 8, vượt nhiễu ±3) **và** fabrication trên
  câu đã trả lời không tăng so với r5 (0,0323).
- 3B "cải thiện nhưng chưa đạt" (22–24) ⇒ Qwen3-4B chỉ được đo ở round **riêng** r11, không chạy gộp.
- 3B "không cải thiện" (`PASS_CORRECT ≤ 17`) ⇒ đổi model không phải đường; 4b chỉ còn nghĩa nếu (b)
  đủ 30 id chốt được nghi phạm.
- `p95 latency`: nếu `ollama ps` cho thấy model KHÔNG nằm 100% trên GPU (có offload CPU) thì **cấm**
  so latency trực tiếp với baseline r5 (19,08 s) — chỉ báo số tuyệt đối kèm tình trạng offload.
- **Bổ sung 09:5x 24-10 (tại item 3/100, chưa có verdict nào) — confound đã đo được của metric
  latency:** `ollama ps` xác nhận 3B nằm **100% GPU** (2,3 GB, `num_ctx` 8192, không offload) nên điều
  cấm ở dòng trên **không kích hoạt**; nhưng một item của vòng lặp gọi `LocalSLM` (1,5B — chuẩn hóa +
  mở rộng truy vấn + splitter) RỒI `QwenGenerator`, tức hai slug khác nhau tranh nhau chỗ trên card
  4 GB ⇒ Ollama giải phóng và nạp lại model giữa các lượt. Cộng thêm chi phí này, mỗi item r10
  (~28,6 s) dài hơn r5 (~17,3 s) trên **cùng đúng 3 id đầu** — độ chênh KHÔNG thuần là "3B chậm hơn
  1,5B". Vì vậy số latency của r10 chỉ được dùng để (i) kết luận "có dùng được trên 4 GB hay không" và
  (ii) ước tính chi phí vận hành nếu đổi model thật; **cấm** đưa vào cổng duyệt như bằng chứng
  "model mới rẻ/đắt hơn". Không có cách nào né confound này mà vẫn giữ một biến (bắt normalizer dùng
  3B là đổi thêm tầng; `OLLAMA_KEEP_ALIVE=-1` nhét cả hai model vào 4 GB là gây offload nhân tạo).
- CI 95% bootstrap 10.000 lượt, seed `20261023` cho `refusal_rate` và `PASS_CORRECT` của r10 — cùng
  cách T1 đã dùng, để hai bảng đọc cạnh nhau được.

**4b (phiên này CHỈ dựng pipeline + báo cáo chi phí, không train):** nguồn dữ liệu = verdict
`FAIL_OVERREFUSAL ∩ has_gold_chunk` do `tools/loop/triage.py` xuất; bắt buộc tuân bất biến #7
(`triage.blocks_for_sft` ưu chunk vàng, `target_fragments()` bỏ dòng có đáp án mẫu không nằm trong
chính ngữ cảnh của dòng đó) và in đủ số dòng bị chặn theo TỪNG lý do (`blocked_test_leak`,
`skip_sft_target_not_in_context`, …). Chia train/test theo **document/Điều** (group split — mọi item
cùng một document rơi về đúng một bên), KHÔNG chia theo item. Bằng chứng bắt buộc là `PASS_CORRECT`
trên test group tách rời; **cấm** dùng `eval_loss` làm bằng chứng.

**Ngân sách:** 4a = **0 lượt Gemini** (~100 lượt Ollama; 1,5B mất 30–60 phút, 3B có offload có thể
dài hơn — đo và báo). Resume T1(b) = còn **23 id**, ngân sách hôm nay **≤14 lượt** (PerDay free tier,
window reset ~14:00 VN), checkpoint sau mỗi lượt, 429/timeout không tính quota, giữ nguyên
`sample_ids.json` (không thêm/bớt/đổi id sau khi đã thấy 7 kết quả đầu).

## T5 — Reranker cross-encoder (5a) + Contextual chunk header (5b): ĐẶC TẢ + NGƯỠNG ĐĂNG KÝ TRƯỚC (24-10 ~10:15, VIẾT TRƯỚC KHI CHẠY r11/r12 — không chỉnh lại sau khi có số)

**Mục tiêu:** nâng gold@6 vượt ~74% bằng đòn bẩy **xếp hạng**, nhắm đúng nhóm lỗi mà
`tools/loop/attribute.py` quy về `ranking_*` (lever nguồn không với tới). Module mới
`src/reranker.py`; sửa `src/pipeline.py` (KHÔNG phải file trọng tài) + `tools/loop/run_round.py`
chụp manifest. Chữ ký trọng tài sau khi sửa code vẫn là `9f1179ccab74` (đã đo lại 10:1x 24-10).

**Bằng chứng nền (đọc từ đĩa TRƯỚC khi chốt ngưỡng — `data/loop/diag/bonus_paired_r1_r2.json`,
sinh bởi `tools/diag/bonus_paired.py` trên `retrieval.jsonl`/`verdicts_retrieval.jsonl` của r1/r2/r4):**

| Số (r2 = đường mặc định, pool đang lưu = 12 ứng viên) | Giá trị |
|---|---|
| gold@6 toàn bộ | 0,74 (CI 95% [0,7071; 0,7729], n=700 item có chunk vàng) |
| chunk vàng **trong** cửa sổ 6 | 518/700 |
| chunk vàng có trong 12 ứng viên nhưng **hạng 7–12** (reranker với tới được) | 57/700 |
| chunk vàng **không có** trong 12 ứng viên (reranker không với tới — pool 20 sẽ đo lại) | 125/700 |
| Trần oracle của MỌI đòn bẩy chỉ xếp lại thứ tự ở pool 12 | 0,8214 (= +8,14 điểm) |
| EXACT | 11/52 trong cửa sổ (0,2115); 6 item hạng 7–12 ⇒ trần pool 12 = 0,3269; 35 item không có trong 12 |
| TRAP | 3/23 trong cửa sổ (0,1304); 1 hạng 7–12 ⇒ trần 0,1739; 19/23 không có trong 12 |
| r1 (bonus 3) → r2 (bonus 12) | 0,7657 → 0,74; delta ghép cặp −0,0257 CI [−0,04; −0,0129], McNemar p = 0,00028, 21 mất / 3 được |
| 21 ca mất | 21/21 chunk vàng nằm NGOÀI `source_filter` và rơi đúng hạng 7–12 (13 item hạng 7); cửa sổ "một nguồn chiếm trọn 6/6" tăng 105 → 209 item |
| r4 (bonus 12 + quota 4) | gold@6 0,7429 (vs r2 +0,0029, p = 0,77 = trong nhiễu), cứu 7/21 ca mất, **giữ nguyên neo HUMAN 0,8144**, cửa sổ 1-nguồn-chiếm-trọn giảm 209 → 24 |

⇒ **Tiêu chí "+10 điểm EXACT" nằm sát trần vật lý của pool 12** (0,3269): đạt được đòi hỏi kéo lại
≥5 trong 6 ca hạng 7–12, tức gần-oracle. round r12 chạy pool 20 + `RERANKER_KEEP_CANDIDATES=1`
chính là phép đo "pool 20 đưa thêm bao nhiêu chunk EXACT/TRAP vào ứng viên". Ghi trước điều này để
không ai được gọi kết quả là "bất ngờ".

**Cờ (mặc định TẤT cả TẮT; unit test `tests/test_reranker_flag.py` chứng minh tắt = không đổi hành
vi, tắt = không gọi `get_reranker`):**

| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `ENABLE_RERANKER` | `0` | bật rerank; TẮT thì không import model, `leg_k == k`, cửa sổ y như cũ từng ký tự |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | **bắt buộc có tiền tố tổ chức** — bài học r9: `bge-reranker-base` (không prefix) gây `RepositoryNotFoundError` rồi âm thầm lùi bi-encoder. Tên không prefix bị chặn bằng `RerankerUnavailable` NGAY KHI ĐỌC ENV |
| `RERANKER_DEVICE` | `cpu` | `venv` app cài torch **CPU-only** (`torch.cuda.is_available() == False`, đã đo 24-10) — CPU là thiết bị ĐO, không phải phương án lùi. Ghi "VRAM" của 5a = **0 MiB**, chi phí thật là RAM + giây CPU |
| `RERANKER_CANDIDATE_POOL` | `20` | số ứng viên lấy từ RRF rồi mới rerank xuống cửa sổ; cũng là độ sâu `k` của mỗi nhánh (BM25 + Chroma) khi cờ bật |
| `RERANKER_KEEP_CANDIDATES` | `0` | bật = `retrieve()` trả **toàn bộ pool đã rerank** (nguồn ghi `sources` tới hạng 20, để đo trần pool 20); `contexts`/cửa sổ 6 ô không đổi |
| `RERANKER_MAX_LENGTH` | `512` | trần token mỗi cặp (chunk Tầng 1 dài ~1.300 ký tự nên phải khai trần) |
| `RERANKER_BATCH_SIZE` | `4` | batch CPU, giữ RAM (máy 42 GB nhưng RAM rảnh chỉ ~3,8 GB lúc r10 đang chạy) |

**Thứ tự trong luồng (chốt trước khi chạy):** (1) hai nhánh lấy `leg_k = max(k, pool)`; (2) RRF
fusion; (3) gộp fallback-query (như cũ); (4) lọc mềm bonus + quota (như cũ, **không đổi**); (5) cắt
`pool` ứng viên đầu theo thứ tự RRF+bonus; (6) cross-encoder chấm `fold(query)` × `page_content`
nguyên văn, sắp **ổn định** theo `(-điểm, hạng cũ)`; (7) trả `docs[:k]` (hoặc nguyên pool khi
KEEP_CANDIDATES). Rerank chạy **sau** bonus nên không đối đầu lever nguồn; tie-break vẫn là hạng cũ
nên kết quả tái lập được. `sources`/`contexts` của row = thứ tự model thật sự đọc.

> **ĐÍNH CHÍNH ĐÃ DUYỆT 25-10 (PA-25) — bước (6) đổi thành query NGUYÊN VĂN × `page_content`
> nguyên văn.** Bản gốc ở đoạn trên ghi `fold(query)` và đã được dùng cho r12; r12 cho kết quả âm
> và nguyên nhân đo được là chính quy ước đó: cặp "query mất dấu × passage còn dấu" làm
> `bge-reranker-v2-m3` gần như mất tín hiệu — probe 30 item: `fold` **0/30** chunk vàng vào top-6,
> nguyên văn **28/30** (`tmp/probe_r12_fold.json`); round thật r12 gold@6 0,7400→0,6686, EXACT
> 0,2115→0,0385 (`docs/archive/reports/T5.md` §2.7). Round r16 (danh cho PA-25) chấm theo quy ước mới;
> `manifest` của mỗi round tự ký bằng `settings.retrieval_reranker.query_convention`, nên round cũ
> (fold) và round mới (nguyên văn) không đọc nhầm là cùng cấu hình. Các mục khác của thứ tự
> (1)–(7) giữ nguyên.

**Khác biệt có chủ đích so với T3:** KHÔNG có phương án lùi thầm. Model không tải được hoặc chấm
điểm lỗi ⇒ `RerankerUnavailable` (kế thừa `RuntimeError`) được `pipeline.retrieve` **ném thẳng lên**
(tránh cả nhánh `except Exception` vốn lùi về `similarity_search`) ⇒ `run_round` ghi `error` vào
dòng đó. Một round đo nhầm lever còn tệ hơn một round dừng tường minh.

**Chống rò đáp án (bất biến #6):** reranker chỉ thấy câu hỏi đã chuẩn hóa (từ PA-25: nguyên văn,
chỉ `.strip()`) + `page_content`; không đọc `gold_chunk_id`, `gold_sentence`, `required_entities`. (Khác `src/evidence_selection.py`:
cái đó chọn CÂU cho tầng sinh, đã bác ở T3.)

**Hai round, một biến (id luôn = số lớn nhất + 1; r10 đang chạy = 4a của T4):**

- **r11 = nền:** `--phase retrieval --split all --limit 811` (toàn bộ test bank),
  `ENABLE_CLASSIFIER=1 ROUTER_SOFT_FILTER=1 ROUTER_FILTER_RANK_BONUS=12 ROUTER_SOURCE_QUOTA=0`,
  MỌI cờ T3/T4/T5 TẮT. Hai nhiệm vụ: (i) tái lập đường mặc định trên code hôm nay để r12 có
  baseline ghép cặp đúng nghĩa một biến; (ii) `r11 vs r2` = **thước đo code drift** 22-10 → 24-10
  (không phải lever, không được tính là cải thiện).
- **r12 = r11 + `ENABLE_RERANKER=1 RERANKER_KEEP_CANDIDATES=1`.** KEEP_CANDIDATES chỉ thay đổi
  ĐỘ DÀI danh sách `sources` được lưu (hạng ghi tới 20, để đo trần pool 20); định nghĩa mọi chỉ số
  của gate (`sources[:6]`, `contexts`) không đổi. Gate: **r12 vs r11** (một biến) — cộng `attribute.py`
  trước/sau và `tools/diag/bonus_paired.py --baseline r11 --candidate r12`.

**Ngưỡng quyết định (đăng ký trước, không sửa sau khi thấy số):**

| Trường hợp | Tiêu chí |
|---|---|
| **ĐẠT 5a** | gold@6 family **EXACT** ≥ nền +10 điểm tuyệt đối, **HOẶC** delta gold@6 toàn bộ ≥ +1,5 điểm (≥ 11/700 item) **VÀ** McNemar p ≤ 0,05 theo hướng có lợi |
| **Âm rõ ràng** (chấp nhận được, vẫn là kết quả) | delta gold@6 nằm trong CI chứa 0 **và** chi phí đo được (giây/item, RAM) đã ghi đủ ⇒ giữ cờ TẮT, không chỉnh ngưỡng, không thêm lever thứ ba cứu số |
| Cấm gọi là cải thiện khi | \|delta\| < 11 item trên 700 **hoặc** CI bootstrap ghép cặp chứa 0 (tương đương băng nhiễu ±3 item của pha sinh n=100, quy theo cỡ mẫu) |
| Bắt buộc kèm theo | `gold_rank_ceiling` của round mới (pool 20) để nói được reranker **hết cửa** ở đâu; số FAIL_RETRIEVAL và phân bố `ranking_*` trước/sau; chi phí thật |

**Chi phí — phải đo TRƯỚC khi bấm r12 (mục 3 của nhiệm vụ):** `tools/diag/reranker_cost_probe.py` đo
giây tải model, giây/20-cặp, RAM tiến trình trên ~40 item thật lấy từ r11. **Nếu ngoại suy > 60 phút
cho 811 item thì DỪNG và báo**, không âm thầm đổi model (đổi model = đổi biến số).

**5b — Contextual chunk header:** gắn `tên văn bản + Chương/Điều/Khoản` vào **đầu `page_content`**
trước khi embed + BM25, build vào **thư mục index MỚI** (không ghi đè `chroma_db`/`chroma_db_vie`).
**Thứ tự phụ thuộc đã ghi trong đề bài: làm SAU T2.** T2 đã nộp nhưng corpus đích còn chờ duyệt
(PA-1: bật `chroma_db_vie` hay giữ `chroma_db`). Dựng header index trên corpus sắp bị thay = đo hai
lần, nên **code + script build được phép viết trước, round 5b CHƯA chạy cho tới khi corpus được chốt**.

**Ngân sách:** 0 lượt Gemini; r11 ~5 phút CPU (r2 chạy 811 item, median `latency_seconds` 0,28 s);
r12 = r11 + chi phí reranker đã đo ở trên. Retrieval-only **không đụng GPU** (bge-m3 chạy CPU, Ollama
chỉ phục vụ tầng sinh) nên chạy được song song với r10 — nhưng vẫn xếp sau r10 để tránh tranh RAM.

> **Sửa hai câu trên (đo lại 24-10 ~10:4x, giữ nguyên bản gốc vì đây là văn bản đã đăng ký):**
> (1) `latency_seconds` **median của r2 là 2,76 s/item** (p95 8,59 s) chứ không phải 0,28 s — tính
> từ 811 dòng `data/loop/rounds/r2/retrieval.jsonl`; r11 đo lại đúng lúc chạy: median 2,63 s.
> Toàn bộ 811 item vì thế mất **~40–60 phút**, không phải ~5 phút.
> (2) Pha truy xuất **CÓ chạm GPU** khi `ENABLE_CLASSIFIER=1`: `src/classifier.py:581` gọi
> `LocalSLM.generate()` = Ollama `qwen2.5:1.5b-instruct` cho **mỗi** câu hỏi (`raw_response` của
> 811/811 dòng r2 đều khác rỗng ⇒ không phải đường lùi). Câu "Ollama chỉ phục vụ tầng sinh" sai.
> Hệ quả vận hành: không được bấm probe/model khác trong lúc round truy xuất đang chạy — tranh
> GPU làm classifier timeout (`CLASSIFIER_TIMEOUT` 20 s) sẽ rơi về `topic=None` và **hỏng cả round**.
> Không đổi ngưỡng, không đổi thiết kế — chỉ ghi lại chi phí thật.


## Ngưỡng cổng (`tools/loop/gate.py`) — chỉ so trên item chung của hai round

| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `GATE_MAX_FABRICATION_DELTA` | `0.0` | tỉ lệ bịa đặt trên câu đã trả lời không được tăng |
| `GATE_MAX_MISSED_REFUSAL_DELTA` | `0` | không được trả lời bừa thêm câu ngoài phạm vi |
| `GATE_MAX_PASS_DROP` | `0.02` | pass_rate toàn cục giảm tối đa 2 điểm % |
| `GATE_MAX_FAMILY_DROP` | `0.10` | không family nào (n≥8) giảm quá 10 điểm % — chống "cứu" chỗ này bằng cách phá chỗ khác |
| `GATE_MAX_HUMAN_REL_DROP` | `0.05` | neo HUMAN không giảm quá 5% tương đối |
| `GATE_MAX_REFUSAL_RATE` | `0.35` | trần từ chối oan — chặn đường tắt "im lặng cho an toàn" |
| `GATE_MAX_RECALL_DROP` | `0.02` | tỉ lệ chunk vàng vào cửa sổ không giảm |
| `GATE_MIN_COMMON` | `20` | dưới 20 item chung thì từ chối mở cổng |

## Ngưỡng guardrail production (`src/answer_guard.py`)

| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `ENABLE_ANSWER_GUARD` | `0` (TẮT) | bật lớp chặn câu trả lời không căn cứ trong `QwenGenerator` |
| `ANSWER_GUARD_MIN_SCORE` | `0.6` | grounding score tối thiểu để được chấp nhận |
| `ANSWER_GUARD_MAX_UNSUPPORTED` | `1` | một khẳng định không căn cứ là đủ để không tin câu trả lời |

Khi bật: câu trả lời có thực thể không căn cứ → gửi lại prompt kèm khối
`CẢNH BÁO KIỂM CHỨNG` một lượt; vẫn sai → trả `REFUSAL_TEXT`. Guard chạy **trước**
khi ghi cache, nên câu bịa không bao giờ được lưu. Mặc định TẮT để không đổi hành vi
đã nghiệm thu (350 test hiện tại vẫn xanh cả khi tắt).

## Số đo đã có

**r0, pha truy xuất, 811 item, 23-10** (`router_soft_filter=0`, `enable_classifier=1`):

| Chỉ số | Giá trị |
|---|---|
| gold@6 (trên 700 item có chunk vàng; 111 item HUMAN/neo cả văn bản không có chunk vàng duy nhất) | **51,86%** (363/700) |
| `FAIL_RETRIEVAL` | 337/811 = 41,6% |
| — chunk vàng bị `source_filter` cắt khỏi cửa sổ | **244 = 72,4%** (179 do nhãn chủ đề sai, 65 do bảng allowlist hẹp) |
| — lỗi xếp hạng khi không lọc | 58 |
| — lỗi xếp hạng dù bộ lọc đúng nguồn | 35 |
| gold@6 theo family | CLOZE_OCR 85,4% · YESNO_FACT 56,2% · CLOZE 49,7% · SOURCE_LOOKUP 45,1% · REVERSE_LEGAL 33,3% · NUMERIC 26,8% · TRAP 21,7% · TRAP_OCR 17,6% · **EXACT 15,4%** |
| Nhầm chủ đề gây chặn nhiều nhất | hành chính sinh viên → học phí (37) · hành chính sinh viên → quy chế công tác sinh viên (27) · chương trình đào tạo → học phí (13) |

Chính bảng này sinh ra lever P5.7 (`ROUTER_SOFT_FILTER`): bộ định tuyến là kẻ phá recall
số một, không phải mô hình nhúng — nó phạt sai lầm của classifier bằng cách XÓA nguồn
thay vì ưu tiên nguồn. Văn bản bị chặn nhiều nhất: `KH To chuc HK 261 - 20260612.pdf`
(73 item). r1 chạy lại đúng 811 item với đúng MỘT biến số đó
(`python tools/loop/attribute.py --round r1 --compare r0`).

**r1, cùng 811 item, chỉ khác `router_soft_filter=1, rank_bonus=3` — cổng KHÔNG ĐẠT:**

| Chỉ số | r0 | r1 |
|---|---|---|
| gold@6 (700 item có chunk vàng) | 51,86% | **76,57%** |
| `FAIL_RETRIEVAL` | 337 | 164 |
| bị `source_filter` cắt (máy quy lỗi) | 244 (72,4%) | **0** |
| item đổi chiều trong cửa sổ | — | +182 vào, −9 ra |
| **Neo HUMAN: đúng văn bản còn trong top-6** | **81,44%** (79/97) | **77,32%** (75/97) = −5,06% tương đối |

Luật `human_anchor_source_not_degraded` (ngưỡng −5% tương đối) chặn round: 11 câu do
người viết mất văn bản cần thiết, 7 câu khác lấy lại được. Probe trên trục bonus cho
thấy bản chất đánh đổi — cắt cứng bảo đảm "cửa sổ chỉ chứa nguồn đúng" khi nhãn ĐÚNG,
còn lọc mềm với bonus nhỏ thì để nguồn khác tràn vào:

| bonus | 6 câu neo (nhãn đúng) còn đúng nguồn | 8 item nhãn sai kéo được gold |
|---|---|---|
| cắt cứng (0) | 6/6 | 1/8 |
| 0 (bỏ cắt, không ưu tiên) | 0/6 | 8/8 |
| 3 (r1) | 2/6 | 8/8 |
| 12 (= cỡ cửa sổ: ưu tiên tuyệt đối, không xóa) | **6/6** | **7/8** |

Vì `bonus ≥ cỡ cửa sổ` biến "lọc" thành "xếp trước" mà vẫn cho phép nguồn khác điền
phần còn lại, round `r2` đo lại toàn bộ 811 item với `ROUTER_FILTER_RANK_BONUS=12` và
mở hai cổng (r2-vs-r0 = cả đòn bẩy, r2-vs-r1 = riêng knob này).

**Kết quả r2 (23-10; chữ ký trọng tài lúc chạy là `342d42bf3ea4`, sau khi vá `answer_guard`
mục P5.13 thì r0/r1/r2 đều được chấm lại và mang `9f1179ccab74` như nhau nên cổng vẫn so
được — số không đổi):**

| Cổng | Kết luận | Số |
|---|---|---|
| r2 vs r0 | **ĐẠT** | gold@6 51,86% → **74,00%**; `FAIL_RETRIEVAL` 337 → 182; neo HUMAN 81,44% → **81,44%** (r1 từng tụt xuống 77,32%); 161 recall + 188 anchor cải thiện, 6 + 14 hồi quy |
| r2 vs r1 | **KHÔNG ĐẠT** | gold@6 76,57% → 74,00% (vượt ngưỡng -0,02); neo HUMAN 77,32% → 81,44% (+5,33%) |

Cơ chế của 21 item hồi quy khi tăng bonus 3 → 12 (probe từ dữ liệu đã lưu): **21/21 có
chunk vàng nằm NGOÀI `source_filter`** — cửa sổ bị nguồn được ưu tiên chiếm gần hết nên
chunk vàng của nguồn khác bị đẩy ra; vì thế thiệt hại tập trung ở `SOURCE_LOOKUP`
(-0,0883) và `CLOZE` (-0,0392). Bài học phương pháp: một knob toàn cục đổi chỉ số này lấy
chỉ số khác thì bằng chứng nghi ngờ **cấu trúc** ("một nguồn được phép chiếm hết cửa sổ"),
không phải giá trị của con số. Lever kế tiếp là hạn ngạch nguồn trong cửa sổ; mặc định
`ROUTER_FILTER_RANK_BONUS` chưa chốt cho tới khi lever đó có số.

**Pha sinh (100 item, cùng subset ở cả hai round, `--pin-subset-from r0`):**

| Chỉ số | r0 | r1 |
|---|---|---|
| `PASS_CORRECT` / `PASS_REFUSAL` | 12 / 18 | 10 / 19 |
| `FAIL_OVERREFUSAL` (từ chối oan khi căn cứ đã nằm trước mặt) | 35 | 38 |
| `FAIL_INCOMPLETE` | 11 | 7 |
| `FAIL_FABRICATED` (bịa số/mã không có trong ngữ cảnh) | 1 | 1 |
| fabrication rate trên câu đã trả lời | 2,94% | 3,57% |

Nút thắt lớn nhất của pha sinh không phải bịa đặt mà là **từ chối oan** (66–72% câu bị
đánh dấu refusal): `triage_report.md` của cả hai round phần lớn là `lever=guardrail`.

**r3 — đo lever `ENABLE_ANSWER_RESCUE` bản 1 (100 item pin từ r0, router giữ đúng cấu hình
r1, cache lạnh `tmp/loop_gen_cache_r3`): cổng `r3-vs-r1` KHÔNG ĐẠT.**

| Chỉ số | r1 | r3 | Tiêu chí đăng ký trước |
|---|---|---|---|
| `PASS_CORRECT` | 10 | **16** | ✓ |
| `FAIL_OVERREFUSAL` | 38 | **32** | ✓ |
| fabrication rate trên câu đã trả lời | 3,57% | **2,56%** | ✓ |
| `PASS_REFUSAL` | 19 | **15** | ✗ |
| `FAIL_HALLUCINATED_ON_UNANSWERABLE` | 2 | **3** | ✗ (ngưỡng +0) |
| `refusal_rate` | 0,72 | 0,61 | (trần tuyệt đối 0,35 — r1 đã vi phạm từ trước, không phải do lever) |

Bốn con số đầu chỉ có giá trị một nửa: log chỉ có **9** dòng `[AnswerRescue]` trong khi
**60/61** câu từ chối đủ điều kiện cứu. Cách đọc tại thời điểm đó (latency:
p50 câu từ chối 15,5 s, chỉ 5 câu vượt 19,5 s ≈ hai lượt gọi) là "lever chưa được đo đủ",
nhưng **phép đếm bằng latency đã bị bác ở r5**: lượt gọi thứ hai có thể chỉ tốn ~1–2 s vì
prompt cứu là phần mở rộng của prompt vừa gửi (Ollama tái dùng KV prefix), nên r5 phải đếm
bằng **số dòng log**, không bằng thời gian. Điều chắc chắn duy nhất về r3: v1 **không đếm
được** số lượt thử (nhánh "model vẫn từ chối" im lặng). Bản v2 (xem `ROADMAP.md` P5.15) sửa ba điểm:
chỉ dẫn "tìm và chép" với ví dụ **bịa sẵn** (nhiễm mồi là bài học từ A/B `V3`),
ngưỡng nhận `max(ngưỡng guard, RESCUE_MIN_SCORE=0.8)` + `unsupported` rỗng, và mọi nhánh
thất bại đều in dấu. Round `r5` là phép thử cuối: nếu đếm đủ ~68 lượt thử (đo lại trên đúng
100 item r1 bằng luật mới, xem `ROADMAP.md` P5.15) mà vẫn mất `PASS_REFUSAL` hoặc tăng
`FAIL_HALLUCINATED_ON_UNANSWERABLE` thì lever bị bỏ vĩnh viễn.

**r4 — đo lever `ROUTER_SOURCE_QUOTA=4` trên pha rẻ, 811 item, bonus giữ 12: hai cổng ĐẠT
nhưng giả thuyết bị bác.**

| Chỉ số | r0 | r1 (bonus 3) | r2 (bonus 12) | r4 (bonus 12 + quota 4) |
|---|---|---|---|---|
| `gold@6` | 0,5186 | 0,7657 | 0,7400 | **0,7429** |
| neo HUMAN đúng-nguồn-vào-cửa-sổ | — | mất neo | 0,8144 | **0,8144** |
| `FAIL_RETRIEVAL` | 337 | 164 | 182 | **180** |

`gate.py --candidate r4 --baseline r2 --phase retrieval` → ĐẠT (gold@k 0,74→0,7429, ngưỡng
−0,02; neo 0,8144→0,8144 n=97; family không có n≥8 nào giảm quá 0,10). `--baseline r0` → ĐẠT
(0,5186→0,7429). Lever chạy thật và **vô hại**: quota đã siết phân bố "suất tối đa của một
nguồn trong 12 ô" về đúng 4 (chỉ còn 35 item vượt ngưỡng, toàn bộ có `source_filter` rỗng),
neo giữ nguyên từng item. Nhưng dự đoán đăng ký trước ("gold@6 phải hồi phục về phía 0,7657
của r1") **không đạt** — chỉ +0,29 điểm, và family vẫn là kiểu đánh đổi: `SOURCE_LOOKUP`
+0,0393 lấy `CLOZE_OCR` −0,0194. Theo đúng quy tắc đã ghi trước khi chạy: giả thuyết cấu trúc
("một nguồn chiếm trọn cửa sổ" là nút thắt) **sai**, mặc định truy xuất chốt ở cổng r2-vs-r0
= **bonus 12, quota OFF**; `apply_source_quota` được giữ làm lever đã đo, không bật. Ghi lại
ô chưa đo để không ai tưởng là đã loại trừ: tổ hợp *bonus 3 + quota 4*; và nhóm lỗi quota với
tới không chạm — `attribute.py --round r4 --compare r0` cho `ranking_despite_filter` 35→42,
`ranking_no_filter` 58→58 (92–229 item không có `source_filter`).

**r5 — đo rescue v2 (`ENABLE_ANSWER_RESCUE=1 RESCUE_MIN_SCORE=0.8`, router giữ đúng cấu hình r1:
bonus 3, không quota, cache lạnh `tmp/loop_gen_cache_r5`): cổng `r5-vs-r1` chỉ vi phạm MỘT quy
tắc, và điều kiện đếm lượt thử KHÔNG đo được do lỗi dụng cụ ở phía người đo.**

| Chỉ số | r1 | r3 (v1) | r5 (v2) | Đủ điều kiện cứu (đo lại bằng hàm ship) |
|---|---|---|---|---|
| `PASS_CORRECT` | 10 | 16 | **14** | r1 68 · r3 56 · r5 **64** |
| `PASS_REFUSAL` | 19 | 15 | **17** | |
| `FAIL_OVERREFUSAL` | 38 | 32 | **37** | |
| `FAIL_HALLUCINATED_ON_UNANSWERABLE` | 2 | 3 | **2** | |
| `FAIL_FABRICATED` | 1 | 1 | **1** | |
| refusal rate | 0,72 | 0,61 | 0,69 | |

`gate.py --candidate r5 --baseline r1 --phase full` → 6/7 ĐẠT, chỉ `refusal_rate_bounded` vi phạm
(0,69 > 0,35 — mà baseline r1 cũng 0,72; fabrication **giảm** 0,0357→0,0323, hallucinated 2/2,
pass_rate 0,29→0,31, gold@k 0,6875→0,7375, neo 0,4286→0,4286 với n=7). `--baseline r3` vi phạm
`fabrication_not_increased` 0,0256→0,0323 nhưng **cùng đúng một câu bịa** (1/39 → 1/31): tỉ lệ
tăng vì mẫu số câu đã trả lời nhỏ lại, không vì có thêm câu bịa. Báo cáo:
`rounds/r5/gate_vs_r1_full.json`, `rounds/r5/gate_vs_r3_full.json`.

Vì sao **chưa được phép bỏ lever** dù `PASS_REFUSAL` 17 < 19 (điều kiện (2) đã đăng ký trước):
điều kiện (1) — đếm số lượt THỬ — thất bại ở phía người đo. Lệnh khởi động bị bọc `… | tail -60`
nên mọi dòng `[AnswerRescue]` đã bị ném đi (không phải lever không in — smoke test độc lập in
đàng hoàng). Latency cũng không cứu: 64 câu đủ điều kiện có p50 16,18 s còn nhóm khác 16,15 s,
không có dấu vết 2× — đúng như dự đoán "lượt thứ hai rẻ vì Ollama tái dùng KV prefix". Round
**r5b** (cấu hình y hệt, cache `tmp/loop_gen_cache_r5b`, không bọc pipe) trả lại con số đó và
đồng thời đo **nhiễu của chính phép đo**: cùng một cấu hình chạy hai lượt thì verdict lệch bao
nhiêu item/100 — nếu xấp xỉ 2 câu thì 19→17 không phải bằng chứng.

**r5b — lượt lặp lại NGUYÊN VĂN cấu hình r5, và nó đóng cả hai việc mà r5 để ngỏ (23-10,
`rounds/r5b/`, exit 0, 100/100 item, 0 entry lỗi).** Bản ghi đếm được (kèm đoạn stdout gốc và
cách tái lập) nằm ở `rounds/r5b/rescue_tally.txt` — giữ trong repo vì stdout của lượt chạy nằm ở
thư mục tạm của công cụ chạy nền và sẽ bị xoá.

Đếm từ stdout (không suy luận từ latency nữa): **60 dòng `[AnswerRescue]`** = 59 dòng
`Đã thử lượt trích xuất, model vẫn từ chối` + 1 dòng `Cứu một câu từ chối oan…` (item
`C126485669658863`). Zero dòng ở ba nhánh còn lại (`Lượt cứu lỗi`, `Không kiểm chứng được`,
`không đạt ngưỡng`) — tức mọi ứng viên thất bại **ngay tại mô hình**: bị hỏi lại bằng chỉ dẫn
trích xuất, `qwen2.5:1.5b-instruct` vẫn trả lời đúng một lời từ chối.

| | r5 | r5b |
|---|---|---|
| lượt THỬ cứu / câu đủ điều kiện | (mất log) | **60 / 64** |
| câu cứu được | — | **1 (1,7%)** |
| `PASS_CORRECT` | 14 | **14** |
| `PASS_REFUSAL` | 17 | **17** |
| `FAIL_HALLUCINATED_ON_UNANSWERABLE` | 2 | **2** |
| `FAIL_FABRICATED` | 1 | **1** |
| `FAIL_OVERREFUSAL` | 37 | **34** |
| `FAIL_RETRIEVAL` | 20 | **22** |
| `FAIL_INCOMPLETE` | 9 | **10** |
| refusal rate | 0,69 | **0,66** |

**Phán quyết, theo đúng quy tắc đã đăng ký trước ở P5.15:** điều kiện (1) giờ ĐẠT đo (60 lượt thử,
bằng 94% số ca đủ điều kiện — lever chạy phủ gần như toàn bộ số ca) và điều kiện (2) HỎNG ở **cả hai lượt độc
lập** (`PASS_REFUSAL` 17 < 19) ⇒ **bỏ lever `ENABLE_ANSWER_RESCUE` vĩnh viễn**. Code + 23 test ở
`tests/test_answer_rescue.py` giữ nguyên làm bằng chứng đã đo; mặc định TẮT; không mở round rescue
nào nữa, kể cả tổ hợp bonus 12 + rescue (một lever đã bị bác thì không "cứu" bằng cách đổi lever
khác).

**Nhiễu của chính phép đo (mục đích thứ hai của r5b) — chuẩn hóa cách đọc mọi cổng pha sinh:**
cùng một cấu hình chạy hai lượt, bốn chỉ số quyết định (PASS_CORRECT / PASS_REFUSAL / HALLUCINATED
/ FABRICATED) **không lệch một item nào**, trong khi các nhóm FAIL dao động ±3 item và refusal rate
−0,03. Trần nhiễu này là thứ phải trừ đi trước khi gọi bất kỳ chênh lệch nào là "bằng chứng"; riêng
chênh 19→17 của `PASS_REFUSAL` giữa r1 và r5/r5b **chưa được loại trừ nhiễu** vì r1 chỉ chạy một lượt.

*Ghi chú thiết kế cổng (đang chờ duyệt, chưa tự sửa):* `refusal_rate_bounded` là trần TUYỆT ĐỐI
nên không round pha sinh nào vượt nổi khi chính baseline ở 0,61–0,72 (r0 0,66 · r1 0,72 · r3 0,61
· r5 0,69 · r5b 0,66). Đề xuất đổi thành quy tắc tương đối "không tăng so với baseline", giữ trần
tuyệt đối làm cảnh báo không phủ quyết — vì đây là sửa dụng cụ RA QUYẾT ĐỊNH nên phải qua người dùng.
**Lỗ thứ hai, do r5b lộ ra:** cổng `r5b-vs-r5` (hai lượt cùng cấu hình) vẫn kết luận KHÔNG ĐẠT vì
`family_pass_rate[EXACT] 0,25→0,125` với n=8 — **một item lật đã vượt ngưỡng −0,10**. Nên sửa kèm:
nâng `GATE_MIN_FAMILY_N` hoặc yêu cầu chênh lệch ≥2 item để một family được phủ quyết; nếu không,
vòng lặp sẽ tiếp tục bác cải thiện thật và nhận round trệch vì cùng một lý do.

**r6 — đo lever `NORMALIZE_SANITY_GUARD=1` (một biến số trên nền r1: rescue TẮT, bonus 3, cache
lạnh `tmp/loop_gen_cache_r6`; 23-10, 100/100 item, exit 0). Đây là lever đầu tiên của pha sinh có
bằng chứng nhân quả ở cấp item.** Bản ghi: `rounds/r6/normalizer_guard_tally.txt`.

| Chỉ số | r1 | r6 | |
|---|---|---|---|
| dòng `Bác bản chuẩn hóa` | — (cờ tắt) | **5/100** | khớp kỳ vọng đăng ký trước 5–6 ⇒ phép đo có giá trị |
| item bị bác lấy lại được chunk vàng vào cửa sổ 6 | — | **5/5** | 4 ca `gold_in_top_k` False→True, 1 ca đã có vàng (nghẽn tầng sinh) |
| verdict của 5 item đó | `FAIL_RETRIEVAL` ×4, `FAIL_OVERREFUSAL` ×1 | **1 `PASS_CORRECT`**, 2 `FAIL_OVERREFUSAL`, 1 `FAIL_INCOMPLETE`, 1 giữ nguyên; **0 đi xuống** | tiêu chí (2) ĐẠT |
| `PASS_CORRECT` toàn round | 10 | **14** | |
| `FAIL_RETRIEVAL` | 23 | **18** | |
| gold@k (80 item có chunk vàng) | 0,6875 | **0,7875** | +10 điểm % — sửa tầng input là một thắng lợi TRUY XUẤT |
| fabrication trên câu đã trả lời | 0,0357 | **0,0278** | |
| `FAIL_HALLUCINATED_ON_UNANSWERABLE` | 2 | **2** | |
| refusal rate | 0,72 | **0,64** | giảm, nhưng vẫn vi phạm trần tuyệt đối 0,35 |
| `PASS_REFUSAL` / `FAIL_INCOMPLETE` | 19 / 7 | **17 / 11** | chiều ngược, chưa tách khỏi nhiễu (±3 ở r5b; r1 chưa chạy lặp) |

Cổng `r6-vs-r1`: **6/7 ĐẠT**; quy tắc duy nhất vi phạm là `refusal_rate_bounded` — vi phạm **dù
chỉ số đó đã tốt hơn baseline** (0,64 < 0,72), vì trần 0,35 là tuyệt đối. Không family nào giảm
(EXACT 0,00→0,25, NUMERIC 0,30→0,50), neo HUMAN giữ, pass_rate 0,29→0,31. Báo cáo:
`rounds/r6/gate_vs_r1_full.json`, `rounds/r6/gate_vs_r5b_full.json`. Triage: 15 `sft_extractive`
(13 từ over-refusal), `blocked_test_leak` 37, `skip_sft_target_not_in_context` 7.

**Đính chính chủ thể đo (áp dụng cho mọi phép đo chuẩn hóa sau này):** pipeline chuẩn hóa
`item["raw_query"]` chứ không phải `item["question"]` (`tools/loop/run_round.py:95` →
`src/pipeline.py:356,386`). Probe chấm trên `question` từng khiến một ca ECHO "khớp cả ba round"
và dẫn tới diễn giải sai về tính tái lập.

**r7 — round tổ hợp `ROUTER_FILTER_RANK_BONUS=12` + `NORMALIZE_SANITY_GUARD=1` (rescue TẮT, quota
TẮT, cache lạnh `tmp/loop_gen_cache_r7`; chạy 23-10 → 24-10, 100/100 item, exit 0). Một biến số so
với r6 = con số bonus.** Bản ghi: `rounds/r7/combo_tally.txt`.

| Chỉ số | r6 (bonus 3) | r7 (bonus 12) | r1 (không guard) |
|---|---|---|---|
| dòng `Bác bản chuẩn hóa` | 5/100 | **5/100 — trùng khít 5/5 ca với r6** | — |
| `PASS_CORRECT` | 14 | 14 | 10 |
| `pass_rate` | 0,31 | 0,32 | 0,29 |
| gold@k (80 item) | 0,7875 | 0,80 | 0,6875 |
| HUMAN đúng-nguồn-vào-cửa-sổ (n=7) | 0,4286 | **0,7143** | 0,4286 |
| refusal rate | 0,64 | 0,62 | 0,72 |
| fabrication | 0,0278 | 0,0263 | 0,0357 |

Cả hai cổng (`r7-vs-r6`, `r7-vs-r1`): **6/7 ĐẠT**, veto duy nhất vẫn là `refusal_rate_bounded` với
candidate 0,62 — vi phạm dù chỉ số đó đã giảm so với cả hai baseline. Chênh r7-vs-r6 là 9 lên/4 xuống
nhưng chỉ 3/2 là verdict, `PASS_CORRECT` đi ngang ⇒ **nằm trong băng nhiễu ±3 đã đo ở r5b: chưa xác
nhận được bonus 12 cộng thêm giá trị khi đã có guard, cũng chưa bác**. Giá phải trả có cơ chế và đã
quy lỗi được: `N172171203676287#2` và `S193409910201077` đi từ `PASS_CORRECT` xuống `FAIL_OVERREFUSAL`
vì xếp thưởng theo nguồn đẩy chunk cần thiết ra khỏi cửa sổ 12 slot; `NUMERIC` giảm đúng 0,1000 =
**bằng ngưỡng** `GATE_MAX_FAMILY_DROP` (chỉ veto khi giảm *quá* 0,1) — cổng mỏng trên mép dao.
Một lần gọi chuẩn hóa gặp `CUDA out of memory` → `query_normalizer` fallback về câu gốc (0 item
`err != None`). Kết luận vận hành: **không mở round tổ hợp nào nữa để đo bonus**; quyết định bonus
3 hay 12 cần lặp lại/tăng cỡ mẫu, không phải một cổng n=100.

**r8 + r9 — T3 (decoupled refusal, rồi cộng thêm evidence selection), 24-10, hai round MỘT BIẾN, cache lạnh
riêng, 0 lượt Gemini, 100/100 item mỗi round, exit 0.** Số ghi ở đây sau khi đã chốt; **không** chỉnh
ngưỡng `DEC_*`/`EV_*` theo kết quả (đúng điều khoản đã ký ở mục T3). Bản ghi:
`rounds/r8/round_summary_full.json` + `rounds/r8/attribution_vs_r5.txt` + `tmp/r8_run.log`,
`rounds/r9/round_summary_full.json` + `rounds/r9/attribution_vs_r8.txt` +
`rounds/r9/attribution_vs_r5.txt` + `tmp/r9_run.log`; cổng: `rounds/r8/gate_vs_r5_full.json`,
`rounds/r9/gate_vs_r8_full.json`, `rounds/r9/gate_vs_r5_full.json`. Báo cáo đầy đủ: `docs/archive/reports/T3.md`.

| Chỉ số | r5 | r8 | r9 |
|---|---|---|---|
| `PASS_CORRECT` (tiêu chí ≥25) | 14 | **19** | **19** |
| `PASS_REFUSAL` (im lặng đúng) | 17 | **2** | 14 |
| `FAIL_OVERREFUSAL` | 37 | 23 | 35 |
| `FAIL_HALLUCINATED_ON_UNANSWERABLE` | 2 | **12** | 3 |
| `FAIL_CONFIRMED_FALSE_PREMISE` | 0 | 4 | 2 |
| refusal rate | 0,69 | **0,28** | 0,57 |
| fabrication trên câu đã trả lời | 0,0323 | 0,0 | 0,0 |
| gold@k (80 item có chunk vàng) | 0,7375 | 0,7125 | 0,7125 |
| median / p95 latency (s) | 16,17 / 19,08 | 14,95 / 19,93 | 25,25 / 33,27 |
| cổng | nền | **KHÔNG ĐẠT** (5 vi phạm) | **KHÔNG ĐẠT vs r8** (2 vi phạm) |

Đọc bằng số: (i) quyền từ chối thật nằm ở phía model — bỏ đường từ chối khỏi prompt làm refusal
0,69→0,28 (dưới trần 0,35 lần đầu trong chuỗi r), +16 câu đi từ `FAIL_OVERREFUSAL` lên `PASS_CORRECT`,
chênh +5 item vượt băng nhiễu ±3; (ii) cái giá đo được là **lớp im lặng đúng biến mất** (17→2) và
chuyển thành 12 câu trả lời sai cho câu ngoài phạm vi + 4 câu tiền giả sai, nên `pass_rate` tụt
0,31→0,21 và cổng `no_new_hallucinated_refusal` veto đúng chỗ đó; (iii) trong năm luật **chỉ hai luật
bắt** (rank 25, refusal-marker), còn `no_evidence`/`off_topic_window`/`ungrounded` bằng 0 vì
overlap luôn ≥ 0,333 và extract-only làm `grounding_score` ≡ 1,0 — nghĩa là tầng ngoài **mù với lớp lỗi
"có căn cứ nhưng lạc đề"**, tức chính lớp vừa phình ra; (iv) r9 là kết quả âm: 75/75 cửa sổ đều đúng 5
câu (6898→1022 ký tự), `model_still_refuses` 3→32, refusal lên 0,57, CLOZE_OCR `PASS_CORRECT` 8→3,
p95 +67%, `PASS_CORRECT` đi ngang 19 nhưng là tập câu khác (giao nhau 11 id); reranker tụt về bi-encoder
`bge-m3` (cross-encoder không tải được) và đã ghi trong `settings.evidence_reranker` — số r9 đọc là
"chọn câu theo bi-encoder"; (v) **tiêu chí T3 không đạt ⇒ hai cờ giữ mặc định TẮT, không mở lever thứ
ba để cứu số.**

**Cảnh báo phương pháp (đã trả giá thật):** lần chạy đầu của r0 lưu verdict bằng
`verify.py` còn bug `has_gold_chunk`, nên 97 item không có chunk vàng bị đếm nhầm thành
`FAIL_RETRIEVAL` (434 thay vì 337). Vì trọng tài là một *dụng cụ đo*, sửa trọng tài thì
phải chấm lại các round cũ — chạy lại đúng lệnh round khi `<phase>.jsonl` đã đủ dòng,
runner sẽ bỏ qua pha gọi model và chỉ chấm lại. Số trong mục này là số sau khi chấm lại;
`round_summary_retrieval.json` có trường `_provenance` ghi rõ chuyện đó.

**Kiểm chứng bất biến 7 trên dữ liệu thật (23-10, round r3):** `triage.py --round r3` xuất
35 dòng (`sft_extractive` 13 · `retrieval_pair` 11 · `classifier_label` 11),
`blocked_test_leak=35`, `skip_sft_target_not_in_context=7`. Soi lại từng dòng `sft_extractive`
bằng `fold()`: **13/13 có đủ thực thể vàng và tên nguồn nằm trong chính khối ngữ cảnh của
dòng đó**, 0 dòng mang `split=test` vào train. Hai dòng (item `S128111294790282`,
`C151482102557130`) có `gold_sentence` KHÔNG nằm trọn trong ngữ cảnh — vì `blocks_for_sft`
cắt mỗi khối 700 ký tự mà gold_sentence của nó là một dòng bảng dài; luật `min(2, len(frags))`
cho phép, và soi thủ công thì **đáp án thật (thực thể + tên file) vẫn có mặt**, tức không phải
dạng dòng train dạy model bịa. Đây là điểm lỏng CÓ CHỦ ĐÍCH và đã được đo, không phải chưa đo.

`triage.py` xác minh chốt chống rò rỉ trên dữ liệu thật: trên pha sinh 100 item,
`blocked_test_leak=19` (r0) và `17` (r1) — từng ấy item `split=test` bị lỗi đã bị
**từ chối** đưa vào `trainpool_additions.jsonl`. (Pha truy xuất không được triage vì
verdict của nó chưa có văn bản để làm cặp huấn luyện: `triage.py` ưu tiên
`verdicts_full.jsonl`, chỉ quay về `verdicts_retrieval.jsonl` khi pha sinh chưa chạy.)

**r10 — T4a: đổi DUY NHẤT model sinh sang `qwen2.5:3b-instruct` (Q4_K_M, `num_ctx` 8192, 2,3 GB
100% GPU), 100/100 item, cache lạnh `tmp/loop_gen_cache_r10`, 0 lượt Gemini, 24-10. Cổng KHÔNG ĐẠT.**
Bản ghi: `rounds/r10/round_summary_full.json`, `rounds/r10/t4_stats.json` (10.000 lượt bootstrap,
seed 20261023), `rounds/r10/gate_vs_r5_full.json`, `rounds/r10/gate_vs_r9_full.json`,
`rounds/r10/triage_report.md`, log `tmp/r10_run.log`; kiểm "một biến":
`data/loop/diag/one_variable_check.json` (contexts/sources/normalized_query/labels/retrieval_config
**trùng 100/100** item). Báo cáo: `docs/archive/reports/T4.md`.

| Chỉ số | r5 = 1,5B | **r10 = 3B** |
|---|---|---|
| `PASS_CORRECT` (đăng ký trước: ≥22 ⇒ có tín hiệu) | 14 [0,07; 0,21] | **16 [0,09; 0,24]** |
| delta ghép cặp / McNemar | | **+0,0203, CI [−0,06; +0,10]** (chứa 0) / 9 được–7 mất, **p = 0,804** |
| `refusal_rate` | 0,69 | **0,75** (vượt trần 0,35) |
| fabrication trên câu đã trả lời | 0,0323 | **0,0** |
| `FAIL_OVERREFUSAL` / `FAIL_INCOMPLETE` | 37 / 9 | **39 / 4** |
| median / p95 / max latency (s) | 16,16 / 18,65 / 21,43 | **26,71 / 34,12 / 45,16** (+83% p95) |
| cổng | nền | **KHÔNG ĐẠT**: `family_pass_rate` EXACT 0,25→0,125 (n=8), NUMERIC 0,4→0,2 (n=10), refusal 0,75 > 0,35 |

Đọc bằng số: đường "tăng cỡ model" **không** vượt băng nhiễu mà p95 tăng 83% ⇒ **giữ
`qwen2.5:1.5b-instruct` làm model triển khai**, điều khoản chạy Qwen3-4B **không kích hoạt**. Không
được nói 3B "tệ hơn/tốt hơn" 1,5B về độ đúng: mọi chênh `PASS_CORRECT` đều có CI chứa 0.

**r11 — NỀN T5a/T5b: retrieval-only 811 item, `bonus=12`, `quota=0`, mọi cờ T3/T4/T5 TẮT, 25-10
02:1x–02:5x.** Đây là **baseline dùng chung** cho hai round sau; không có file cổng (nó là nền).
Bản ghi: `rounds/r11/{retrieval.jsonl,round_summary_retrieval.json,attribution_retrieval.json}`.
Số: gold@6 **0,7400** [0,7071; 0,7729] (700 item có chunk vàng) — **bằng đúng r2**, tức không drift
tổng; `FAIL_RETRIEVAL` **182**; median/p95 **2,78 / 3,87 s**; tổng latency 811 dòng 2.383 s ≈ 40 phút.
Quy lỗi: `ranking_no_filter` 57 · `ranking_despite_filter` 37 · `filter_blocked_wrong_topic` 68 ·
`filter_blocked_wrong_table` 20.

**r12 — T5a: r11 + `ENABLE_RERANKER=1 RERANKER_KEEP_CANDIDATES=1` (`bge-reranker-v2-m3`,
`max_length=512`, pool 20 → top-6, chạy trên `cuda` qua `venv_gpu` riêng), 811/811 item, **0 lỗi**,
25-10 02:53→03:58. Cổng KHÔNG ĐẠT — và là kết quả âm có nguyên nhân kiểm được.** Bản ghi:
`rounds/r12/{retrieval.jsonl,round_summary_retrieval.json,verdicts_retrieval.jsonl,
gate_vs_r11_retrieval.json,attribution_retrieval.json}`; ghép cặp:
`data/loop/diag/reranker_paired_r11_r12.json`; chi phí `data/loop/diag/reranker_cost_gpu.json`;
probe nguyên nhân `tmp/probe_r12_fold.json`; log `tmp/r12_run.log`, `tmp/vram_r12_run.log`.
Báo cáo: `docs/archive/reports/T5.md` §2.6–§2.7.

| Chỉ số (700 item, ghép cặp) | r11 | **r12** |
|---|---|---|
| gold@6 | 0,7400 | **0,6686** [0,6343; 0,7029] |
| delta / McNemar | | **−0,0714, CI [−0,1014; −0,0414]** / **83 mất–33 được, p = 3,9e−06** |
| `FAIL_RETRIEVAL` (811) | 182 | **232** |
| EXACT (n=52) / TRAP (n=23) | 0,2115 / 0,1304 | **0,0385** / **0,0000** |
| SOURCE_LOOKUP (n=102) / NUMERIC (n=112) | 0,8529 / 0,4375 | 0,6373 / **0,4821** |
| neo HUMAN đúng-nguồn (n=97) | 0,8144 | **0,7010** |
| cổng | nền | **KHÔNG ĐẠT — 6/8 kiểm tra vi phạm** (EXACT −0,173, SOURCE_LOOKUP −0,216, TRAP −0,130, YESNO_FACT −0,125, neo HUMAN −13,92% tương đối, `retrieval_not_degraded`) |
| median / p95 latency, tổng thời gian | 2,78 / 3,87 s | **4,74 / 5,09 s**, **≈66 phút** (tổng 3.855,5 s) |

Nguyên nhân (không phải suy đoán): `src/reranker.py:score_pairs` chấm **`fold(query)`** — query đã mất
dấu thanh — với passage còn dấu; trên 30 item bị r12 đẩy gold ra khỏi cửa sổ, rerank bằng query fold
cho **0/30** gold vào top-6, bằng query nguyên văn cho **28/30** (chi phí như nhau). ⇒ kết luận âm về
**bản build**, chưa phải về reranker; cờ **giữ TẮT**; sửa + chạy r14 nằm trong **PA-25**.
Trần oracle pool 20 = **0,8871** (EXACT 0,6154; SOURCE_LOOKUP/CLOZE 1,000) so với 0,8214 của pool 12
⇒ đòn bẩy xếp hạng còn **+14,7 điểm** nếu xếp đúng. Chi phí: nạp 8,3 s, VRAM **3.594/4.096 MiB**
dùng chung với Ollama 1.5B, RAM trống sau nạp 2.967 MiB.

**r13 — T5b: r11 + index header `chroma_db_headers_old`, 811/811 item, 0 `error`, 25-10 02:1x.
Cổng pha retrieval ĐẠT 6/6 nhưng là KHÔNG CÓ TÍN HIỆU.** Kiểm "một biến" bằng nội dung (manifest
không ghi thư mục index — PA-22): 4.866/4.866 context mang header mới. Bản ghi:
`rounds/r13/{retrieval.jsonl,round_summary_retrieval.json,gate_vs_r11_retrieval.json,
attribution_retrieval.json}`; ghép cặp `data/loop/diag/header_paired_r11_r13.json`.

| Chỉ số (700 item, ghép cặp) | r11 | **r13** |
|---|---|---|
| gold@6 | 0,7400 | 0,7371 [0,7043; 0,7700] |
| delta / McNemar | | **−0,0028, CI [−0,0129; +0,0071]** / 8 mất–6 được, **p = 0,79** |
| `FAIL_RETRIEVAL` (811) | 182 | 184 |
| EXACT / TRAP / TRAP_OCR | 0,2115 / 0,1304 / 0,4706 | 0,2308 (+1 item) / 0,1304 / 0,4706 |
| neo HUMAN đúng-nguồn | 0,8144 | 0,8144 |
| median / p95 latency | 2,78 / 3,87 s | 2,76 / 3,02 s |

|delta| = 2 item < băng nhiễu 11, CI chứa 0 ⇒ **cấm gọi là cải thiện**; "cổng ĐẠT" chỉ nghĩa là *không
làm hỏng*. `ENABLE_CONTEXTUAL_HEADER` **giữ TẮT**, `chroma_db_headers_old` **không kích hoạt**.
**Lệch thiết kế đã báo:** đặc tả T5 (mục T5 ở trên) ghi round 5b chưa chạy cho tới khi corpus được
chốt; r13 vẫn chạy trên **corpus cũ** ⇒ số này **không** thay cho phép đo trên corpus T2
(`chroma_db_vie`).

## Giới hạn thật lòng (đọc trước khi tin số)

- Vòng lặp **không chứng minh** AI không bao giờ bịa. Nó *đo* trên một tập câu có
  căn cứ xác thực, và *chặn* ở runtime những khẳng định không có trong ngữ cảnh. Một
  khẳng định hoàn toàn bằng chữ (không số, không mã, không Điều) mà ngữ cảnh không
  chứa thì thực thể-trích xuất không gọi được tên — đó là lúc `grounding_score` chỉ
  là xấp xỉ.
- Trần cứng nằm ở **chất lượng corpus**: 361 chunk nhưng chỉ 62 chunk còn đủ dấu thanh
  tiếng Việt; 3 tệp `.doc` và 1 PDF hỏng text. Không có loop nào bù được việc tài
  liệu chưa được số hóa đúng.
- Câu hỏi auto-generated kiểm tra tính *trích niêm*, không kiểm tra khả năng *suy
  luận tổng hợp* giữa nhiều văn bản; phần đó do `HUMAN` và `SO_SANH`/`THU_TUC` gánh.
- `--phase retrieval` không đi qua chuẩn hóa câu hỏi bằng Qwen, nên nó là **cận dưới**
  của recall production — dùng để xếp hạng lỗi, không để báo cáo Hit@K chính thức.
- Mọi số liệu ở đây offline (Qwen qua Ollama). Muốn kết luận cho đường Gemini phải
  chạy lại `--generator gemini` trong ngân sách quota, và cổng phải mở trên chính
  round đó.

## V1–V4 — chẩn đoán truy xuất 27-10: TIÊU CHÍ ĐĂNG KÝ TRƯỚC (viết TRƯỚC khi chạy V1/V3)

Mục đích: giải thích ba câu hỏi còn treo của tầng truy xuất mà chưa phép đo nào trả lời
dứt điểm — (V1) query dense nên fold hay nguyên văn, (V2) lớp router/soft-filter đang
cộng hay trừ giá trị, (V3) index `chroma_db_vie` còn đo được trên bao nhiêu item. Đây
là **chẩn đoán**, không phải lever: mọi cờ lever TẮT, không sinh văn bản, **0 lượt
Gemini**, không sửa `src/`, không đổi `k`/trọng số RRF mặc định. Mọi phép đo mở **bản
sao** index trong `tmp/diag_index_copies_20261027/`, không mở index thật.

**Số đã biết trước khi đăng ký (nguồn công bố, không phải số của phép đo mới):**
r0 363/700 · r1 536/700 · r2 518/700 · r4 520/700 · r11 518/700; probe all-off trên
700 item (mọi cờ TẮT) = 536/700 (`tmp/retriever_ranks_700.json`). Các số này **không**
được dùng để chỉnh tiêu chí bên dưới.

**Quy ước thống kê chốt trước (áp cho cả V1, V2, V3):**

- Đơn vị ghép cặp = **item**; chỉ item có `gold_chunk_id` (700) cho gold@6.
- McNemar **chính xác hai phía**: `p = min(1, 2·Σ_{k=0..min(b,c)} C(n,k)/2^n)` với
  `b,c` là hai chiều lật.
- Bootstrap **theo cụm tài liệu**: cụm = `source_document` nguyên văn; lấy mẫu lại
  cụm có hoàn lại đến đúng số cụm, giữ toàn bộ item của cụm được chọn (trùng cụm thì
  item lặp), 10.000 lượt, seed `20261027`, CI percentile 2,5–97,5 của **delta ghép
  cặp**. Báo kèm `n_clusters`; nếu < 20 cụm thì ghi "CI cụm không đáng tin" thay vì
  kết luận.
- **Chỉ gọi "có tín hiệu" khi đồng thời**: (a) McNemar `p ≤ 0,05` đúng chiều, (b) CI
  cụm **không chứa 0** cùng chiều, (c) `|delta| ≥ 11/700 ≈ 1,5 điểm %` — ngưỡng nhiễu
  đã dùng ở T5 cho cùng bộ 700 item. Thiếu bất kỳ điều kiện nào ⇒ ghi **"không kết
  luận"**, không suy diễn từ số tuyệt đối.
- Mọi số theo family là **thăm dò**; chỉ in `n` và delta, không tuyên bố ý nghĩa nếu
  `n < 8` hoặc CI chứa 0.

### V1 — dense leg: query nguyên văn vs `fold(query)`

**Hiện trạng code (đã kiểm, không sửa):** dense không nằm trong `src/retrieval.py`;
`src/retrieval.py` chỉ fold cho mở rộng từ đồng nghĩa và khử trùng truy vấn con.
Chỗ nhúng dense thật là `src/pipeline.py:319` — `docs = self.ensemble_retriever.invoke(fold(query))`
(và `:323` `_collect_leg_ranks(fold(query))`, fallback `:419` `vector_query = fold(query)`).
Vì vậy V1 đo đúng một biến: **query đưa vào nhánh Chroma** (BM25 giữ nguyên, không dùng
trong phép đo này).

- Đối chứng: `dense_rank` của `tmp/retriever_ranks_700.json` (query fold, k=12).
- Can thiệp: cùng bản sao index, `dense.invoke(raw_query)` **không fold**, k=12.
- Chỉ số chính: hit@6 của dense leg. Phụ: MRR@12, phân bố hạng 1–6 / 7–12 / ngoài 12.
- Quyết định đăng ký trước: nếu can thiệp **tốt hơn** theo đủ (a)(b)(c), đề xuất một
  PA thêm cờ `DENSE_QUERY_RAW` (mặc định 0) — **không tự sửa `src/`**. Nếu kém hơn
  hoặc không kết luận ⇒ giữ `fold`, ghi lý do bằng số. Kết quả ghi
  `tmp/dense_orig_query.json`.

### V2 — gold@6 dưới trọng tài v2 + hiệu ứng soft-filter

`data/loop/rounds_v2/compare_v1_v2.json` **không trả lời được câu này**: nó chỉ chứa
các round pha sinh (r0,r1,r3,r5,r5b,r6,r7,r8,r9,r10), 100 dòng/round, và không có
r2/r4/r11. Vì vậy gold@6 của r0/r1/r2/r4/r11 được **chấm lại offline** từ
`rounds/<r>/retrieval.jsonl` bằng `tools.loop.verify.score_item` hiện tại (chữ ký
`2911c69f740d`, `answer=None`) trên đúng 700 item có `gold_chunk_id`. Nếu số chấm lại
lệch `round_summary_retrieval.json` của chính round đó **quá 0 item**, dừng và báo
(xung đột dụng cụ đo, không tự chọn số nào).

- **all-off** = cùng bản sao index, mọi cờ = 0, gọi `pipeline.retrieve(raw_query, k=12,
  fallback_query=raw_query)`, cửa sổ = `sources[:6]`; chạy đủ **811 item** để đo cả neo
  HUMAN. Kiểm tương thích: 700 hạng RRF phải trùng `tmp/retriever_ranks_700.json`;
  lệch 1 item cũng dừng.
- **r1 vs all-off:** so **tập** top-6 theo item (không chỉ tổng số): số item trùng tập,
  số lật mỗi chiều, McNemar. Kết luận "trùng" chỉ được viết nếu tập trùng; nếu chỉ
  trùng tổng 536 thì phải ghi rõ là **trùng số, không trùng tập**. Phân rã theo
  `retrieval_config.source_filter` của r1: rỗng / trùng nguồn chứa gold / không trùng.
- **r0 thấp:** đếm item r0 trượt vì `source_filter` khác nguồn của gold (lọc cứng), so
  với all-off trên cùng item; đây là lời giải thích cơ chế, không phải lever mới.
- **Hiệu ứng soft-filter = r11 − all-off**, ghép cặp theo item, xuất theo family và
  theo **neo HUMAN** (`source_document` fold trùng một `source` trong `sources[:6]`;
  n=97). Bootstrap cụm như trên. Không được gọi là cải thiện/thoái hóa nếu thiếu
  (a)(b)(c).
- Kết quả ghi `tmp/v2_rescore.json` + `tmp/alloff_811.json`.

### V3 — `chroma_db_vie`: đo trên các item còn neo

- Bản sao `tmp/diag_index_copies_20261027/chroma_db_vie`, phải đúng **342 chunk**;
  lệch thì dừng.
- **"Còn neo" (định nghĩa chốt trước):** item có `gold_sentence` mà sau `fold` + gộp
  khoảng trắng là **chuỗi con** của ít nhất một chunk trong index mới **cùng
  `source_document`** (fold). Tập đích = **mọi** chunk thoả; hit@6 nếu bất kỳ chunk
  đích nào nằm trong top-6, hạng = hạng tốt nhất. Định nghĩa phụ (báo kèm, không dùng
  để kết luận): toàn bộ text chunk vàng cũ là chuỗi con của chunk mới cùng nguồn.
- Đo **BM25 và dense** (query fold, k=12 — giữ đúng quy ước đang chạy để V3 đo index,
  không đo lại V1) trên đúng tập còn neo: hit@6 từng nhánh, ma trận 2×2, theo family.
- Đối chứng ghép cặp: cùng item, hạng trong index cũ lấy từ
  `tmp/retriever_ranks_700.json`; delta + CI cụm. **Không** tuyên bố index nào tốt hơn
  nếu thiếu (a)(b)(c); V3 không phải cổng kích hoạt.
- **Đèn đỏ giữ nguyên:** nếu tỉ lệ còn neo < 90% thì `chroma_db_vie` vẫn **chưa** đủ
  điều kiện kích hoạt (PA-21/PA-1 vẫn mở), bất kể hit@6 trên tập còn neo cao đến đâu.
- Kết quả ghi `tmp/vie_anchored.json`.

### V4 — khung r17–r19 (chỉ kế hoạch, CHƯA chạy)

Ba round tương ứng ba câu hỏi trên, **mỗi round một biến**, baseline r11, mọi cờ khác
giữ như r11, 0 Gemini, `--phase retrieval --split all --top-k 6`. Chi tiết + ngưỡng
đầy đủ ở `docs/archive/PENDING_APPROVAL.md` (PA-48). Tóm tắt điều kiện mở round:

| Round | Một biến | Chỉ chạy khi | Ngưỡng ĐẠT (đăng ký trước) | Veto neo HUMAN |
|---|---|---|---|---|
| r17 | query dense nguyên văn (cờ mới, cần duyệt) | V1 đủ (a)(b)(c) theo hướng nguyên văn tốt hơn | gold@6 ≥ r11 + 11/700, McNemar p ≤ 0,05, CI cụm không chứa 0 | giảm > 5% tương đối (≈5 item / 97) ⇒ bác |
| r18 | `ENABLE_CLASSIFIER=0` (tắt cả lớp router; soft-filter/bonus ngủ) | V2 cho thấy r11 − all-off âm và đủ (a)(b)(c) | như trên | như trên |
| r19 | đổi index sang `chroma_db_vie` | V3 xong **và** PA-21 re-anchor đạt ≥90% neo **và** PA-1 được duyệt | trên tập còn neo: +5 điểm % tuyệt đối, p ≤ 0,05, CI cụm không chứa 0, không family n≥8 nào giảm > 0,10 | như trên |

Không round nào được chạy trong nhiệm vụ này; kết quả V1–V3 chỉ để quyết định có mở
round hay không. Nếu V1/V3 không kết luận được, ghi "không mở round" — không thay
lever khác để "cứu số".

## P3–P4 — ĐĂNG KÝ TRƯỚC r17 (27-10, viết TRƯỚC khi chạy round)

**Quan hệ với bảng V4 ở trên (ghi rõ để không đổi thước sau khi thấy số):** bảng V4
được viết khi r17 còn giả định "một biến so với r11". Sau khi V1–V2 chốt, biến duy
nhất của r17 là `ENABLE_DENSE_ORIGINAL_QUERY` — một cờ nằm *trong cùng đường all-off*
(không router, không reranker, không T3). Vì vậy **đối chứng đúng là all-off**, không
phải r11: so với r11 sẽ trộn hai biến (query dense + cả gói router/soft-filter) và
không quy được nguyên nhân. Mục này thay dòng r17 của bảng V4; hai dòng r18/r19 của
bảng V4 giữ nguyên. Ngưỡng dưới đây chốt trước khi chạy, không sửa sau khi thấy số.

**Một biến:** `ENABLE_DENSE_ORIGINAL_QUERY` (`0` = đối chứng, `1` = can thiệp). Mọi cờ
khác TẮT như all-off. Không sinh văn bản, 0 Gemini, không sửa `src/`, không đổi `k`
(12) / trọng số RRF (0,5/0,5, c=60) / tập 811 item.

**Dữ liệu & lời gọi (chốt trước):**

- Index: **bản sao** `tmp/diag_index_copies_20261027/chroma_db` (361 chunk); không mở
  `chroma_db` thật. Lệch số chunk ⇒ dừng.
- `pipeline.retrieve(raw_query, k=12, fallback_query=raw_query)`; cửa sổ đo =
  `sources[:6]`. `fallback_query == raw_query` nên nhánh fallback không chạy.
- Câu hỏi KHÔNG qua chuẩn hóa Qwen (đúng thang đo của `--phase retrieval`).

**Số đã biết trước khi đăng ký (không dùng để chỉnh ngưỡng):** all-off 536/700, neo
HUMAN 75/97 (`tmp/alloff_811.json`); V1 dense-raw 474/700 vs fold 202/700.

**Tiêu chí chính (quyết định):**

- Chỉ số: `gold@6` trên **700** item có `gold_chunk_id`, ghép cặp theo item,
  delta = can thiệp − đối chứng.
- **Có tín hiệu** khi đồng thời: (a) McNemar chính xác hai phía `p ≤ 0,05` đúng chiều
  dương; (b) bootstrap cụm theo `source_document` (10.000 lượt, seed `20261027`, CI
  percentile 2,5–97,5) **không chứa 0** và cùng chiều; (c) `|delta| ≥ 11/700`
  (≈1,57 điểm %, ngưỡng nhiễu đã dùng cho cùng bộ 700 item).
- **Veto neo HUMAN (97 item):** neo = có ít nhất một `source` trong top-6 fold-trùng
  `source_document` của item. Nếu can thiệp **thấp hơn** all-off (75/97) — dù chỉ 1
  item — thì **BÁC** cờ, bất kể gold@6. Không nới thành "−5%" như bảng V4 cũ vì người
  duyệt đã chốt "thấp hơn là bác".

**Kiểm tra trước khi diễn giải (fail-fast, không tự chọn số):**

1. Lượt đối chứng phải tái lập **từng item** `tmp/alloff_811.json`: hạng gold của 700
   item và neo HUMAN của 97 item trùng khít; lệch 1 item ⇒ dừng, không đo can thiệp.
2. **Stress test "mọi query đã fold"** (đăng ký trước, không phải kết quả): đặt
   `q' = fold(raw_query)` rồi chạy cả hai cấu hình trên đủ 811 item. Vì `q'` không còn
   dấu, `fold(q') = q'` (kiểm idempotence cho cả 811 câu) nên hai cấu hình phải cho
   **cùng tập top-6 và cùng thứ tự** ở 811/811 item. Khác dù 1 item ⇒ lỗi triển khai
   ⇒ dừng, kết luận "không kết luận", không diễn giải số chính.

**Thăm dò (không dùng để kết luận):** chia theo `family` và theo **tỉ lệ từ có dấu
của chunk vàng** (hàm `word_diacritic_ratio` của `tools/diag/corpus_diacritics.py`,
chốt 3 khoảng từ trước: `< 5%`, `5–20%`, `≥ 20%`); in `n`, delta, McNemar; bootstrap
cụm cho nhóm `n ≥ 8`. Không tuyên bố ý nghĩa nếu `n < 8`, cụm < 20, hoặc CI chứa 0.

**Kết quả & phán quyết:**

- ĐẠT (đủ (a)(b)(c) và không veto) ⇒ đề xuất một PA bật cờ làm mặc định; **không tự
  bật** trong phiên này.
- KHÔNG ĐẠT ⇒ cờ giữ TẮT; ghi delta + CI + p, không "cứu số" bằng lever khác.
- Thiếu bất kỳ điều kiện nào ⇒ "không kết luận".
- Ghi `tmp/r17_dense_orig_2026-10-27.json` + log cùng tên; tên mới, không ghi đè
  artifact đã công bố (D-27).

## P5 — ĐĂNG KÝ TRƯỚC r18 (viết 27-10 **sau** r17, TRƯỚC khi chạy r18)

**Quan hệ với các bảng trước (ghi rõ để không đổi thước sau khi thấy số):** mục P3–P4 ở
trên hứa "hai dòng r18/r19 của bảng V4 giữ nguyên". Nay dòng r18 được **viết lại** theo
đúng nhiệm vụ P5 ("viết lại thiết kế r18 theo kết quả [r17]") và theo kết quả ma trận
nhánh. Lý do đổi là **số của r17 và ma trận nhánh P5**, không phải số của r18 (r18 chưa chạy,
chưa có số):
(i) `rrf_fold` 536 thua **BM25 một mình** 568 (Δ=−32, McNemar p=9,4e−7) và thua union
hai nhánh 574 (Δ=−38, p=7,5e−11) — chế độ dense-**fold** đã bị chế độ dense-**nguyên
văn** áp đảo; (ii) vì vậy đo lớp router trên nền fold (dòng r18 cũ: "r11 +
`ENABLE_CLASSIFIER=0`") sẽ trả lời một câu hỏi về hệ thống **không còn là ứng viên
mặc định**. Phép đối chứng (lớp router bật vs tắt) **giữ nguyên**; chỉ đổi chế độ query
sang nguyên văn — nơi r17 đã chứng minh là cấu hình tốt hơn. Ngưỡng (a)(b)(c) và veto
HUMAN không đổi.

**Một lớp, bốn cờ (không phải một cờ):** lớp router của r11 là một **khối**:
`ENABLE_CLASSIFIER=1` + `ROUTER_SOFT_FILTER=1` + `ROUTER_FILTER_RANK_BONUS=12` +
`ROUTER_SOURCE_QUOTA=0`. Classifier sinh `source_filter`; ba cờ còn lại chỉ tiêu thụ
`source_filter` đó, nên tách lẻ sẽ đo một hệ thống chưa từng tồn tại. V2/r11 đã đo đúng
khối này; r18 đo lại khối đó trên nền mới. Hệ quả phải ghi: **không quy được công/thủ
cho từng cờ con**; muốn tách phải thêm round riêng, không tự thêm.

**Nền đối chứng (r17-T, đã đo):** all-off + `ENABLE_DENSE_ORIGINAL_QUERY=1` = 581/700,
neo HUMAN 77/97 (`tmp/r17_dense_orig_2026-10-27.json`). Mọi cờ khác TẮT y như r17-T.
Không đổi `k` (12), trọng số RRF (0,5/0,5, c=60), index (bản sao 361 chunk), tập 811.

**Can thiệp:** lớp router BẬT (bốn cờ ở trên) trên cùng nền. 0 Gemini, không sửa `src/`.

**Tiêu chí chính (quyết định) — r18 vs r17-T:**

- `gold@6` trên 700 item có `gold_chunk_id`, ghép cặp theo item; cùng bộ (a)(b)(c) của
  r17 (McNemar chính xác hai phía p ≤ 0,05 đúng chiều; bootstrap cụm `source_document`
  10.000 lượt seed `20261027` không chứa 0; |Δ| ≥ 11/700). Hai phía vì V2 dự đoán âm.
- **Luật quyết định chốt trước:** r18 **thấp hơn** r17-T có tín hiệu ⇒ đóng câu hỏi
  router: đề xuất (PA riêng) để router TẮT trong mặc định ứng viên, không tự tắt.
  r18 **cao hơn** có tín hiệu ⇒ đề xuất bật khối router (PA riêng), không tự bật.
  Không đủ (a)(b)(c) ⇒ "không kết luận", **giữ mặc định hiện hành** (router BẬT).
- **Veto neo HUMAN:** r18 phải không thấp hơn **77/97** — "thấp hơn là bác", đúng luật
  đã duyệt ở r17, không nới thành −5%.

**Sao lặp bắt buộc (không phải quyết định, nhưng chặn PA bật mặc định):** r18 vs **r11
đã công bố** (dùng lại `data/loop/rounds/r11/retrieval.jsonl`, KHÔNG chạy lại r11) trên
700 item, cùng (a)(b)(c), để xem hiệu ứng dense-nguyên-văn (+45 ở r17) còn giữ khi
router bật. Nếu hiệu ứng đảo chiều hoặc mất tín hiệu ⇒ ghi "tương tác với router" và
**không** bật cờ dense-nguyên-văn làm mặc định cho tới khi giải quyết xong.

**Tương tác (thăm dò, không quyết định):** DiD = (r18 − r11) − (r17-T − all-off) ghép
cặp theo item; bootstrap cụm như trên; chỉ in số, không tuyên bố.

**Fail-fast (không tự chọn số):**

1. Lượt đối chứng (router TẮT + dense nguyên văn) phải tái lập **từng item** r17-T
   (hạng gold 700 item, neo HUMAN 97 item); lệch 1 item ⇒ dừng.
2. Đối chiếu **r11 đã công bố** phải trùng khít `retrieval.jsonl` của r11 theo từng
   item (không chạy lại r11); lệch 1 item ⇒ dừng và báo xung đột dụng cụ đo.
3. Mọi lượt phải có `attribute.py` trước/sau và một artifact ghép cặp
   (`tools/diag/bonus_paired.py` khi hai round cùng định dạng); thiếu ⇒ **không mở cổng**
   (luật PA-48).

**Điều kiện công cụ (phải duyệt trước khi chạy):** `tools/loop/run_round.py` hiện
**không ghi** `ENABLE_DENSE_ORIGINAL_QUERY` vào `settings` của manifest ⇒ round chạy
qua runner sẽ tự ký thiếu biến và trông như "cùng cấu hình". Vì vậy r18 chỉ được chạy
theo một trong hai đường, cả hai đều cần duyệt riêng: (A) thêm khóa đó vào manifest
runner (PA-51, không đổi trọng tài), rồi chạy runner bình thường; (B) chạy như
diagnostic tự ký (như r17) **và** ghi thêm `retrieval.jsonl` đúng định dạng round vào
thư mục **mới** `data/loop/rounds/r18/` để `attribute.py` đọc được. Không ghi đè
round nào đã công bố.

**Chi phí:** 811 lượt classifier Ollama (~40–60 phút), 0 Gemini, không đổi index.

**Kết quả & phán quyết:** ghi `tmp/r18_router_raw_2026-10-27.json` + log cùng tên,
và (nếu đường B) `data/loop/rounds/r18/`. Tên mới, không ghi đè artifact đã công bố.
Mọi thay đổi mặc định sau r18 phải qua PA riêng.

## Q2 — ĐĂNG KÝ TRƯỚC r20 (viết 27-10, TRƯỚC khi chạy)

**Câu hỏi.** Khi bật `ENABLE_DENSE_ORIGINAL_QUERY=1` trên đúng cấu hình pha sinh của r5,
chất lượng đầu-cuối có đổi không — và đổi theo chiều nào? Đây là điều kiện "kiểm ở pha
sinh" đã ghi trong PA-49; r17 chỉ đo pha truy xuất.

**Cấu hình = r5, đúng MỘT biến.** n = 100 item, `--pin-subset-from r5` (cùng 100 id),
`--phase full --split all --limit 100 --only-retrieved`, `--generator offline_qwen`,
`ENABLE_CLASSIFIER=1`, `ENABLE_ANSWER_GUARD=1`, `ROUTER_SOFT_FILTER=1`,
`ROUTER_FILTER_RANK_BONUS=3`, `ROUTER_SOURCE_QUOTA=0`, `ENABLE_ANSWER_RESCUE=1`,
`RESCUE_MIN_SCORE=0.8`, cache **mới** `GENERATION_CACHE_DIR=tmp/loop_gen_cache_r20`.
Biến duy nhất: `ENABLE_DENSE_ORIGINAL_QUERY=1` (r5 chạy với cờ TẮT).

**Hệ quả phải ghi, không được quy công:** cờ này đổi **cả** truy vấn đưa vào dense
retriever **và** ngữ cảnh mà generator nhìn thấy. Vì vậy r20 đo **hệ thống**, không đo
riêng "tầng sinh"; mọi khác biệt về `gold_in_top_k`/`FAIL_RETRIEVAL` là một phần của can thiệp.

**Đối chứng.** `data/loop/rounds_v2/r5/verdicts_full.jsonl` — chính 100 item đó, chấm lại
bằng trọng tài hiện hành `2911c69f740d`. Không chạy lại r5, không đổi mẫu số.

**Điểm cuối chính:** `PASS_CORRECT` ghép cặp theo `id`.

**Luật quyết định (chốt trước, không sửa sau khi thấy số):**

- (a) McNemar chính xác hai phía trên số cặp bất đồng, p ≤ 0,05;
- (b) bootstrap cụm theo `source_document` (10.000 lần, seed `20261027`, CI percentile 95%)
  không chứa 0;
- (c) |Δ| ≥ **3 item / 100** (băng nhiễu ±3 item đã đo ở pha sinh).
- Đủ cả ba ⇒ "có tín hiệu" (ghi chiều). Thiếu một ⇒ **"không kết luận"**.
- **Veto an toàn:** nếu `FAIL_HALLUCINATED_ON_UNANSWERABLE` hoặc `FAIL_FABRICATED` **tăng**
  so với r5 thì dù `PASS_CORRECT` tăng cũng **không** được đề xuất bật cờ làm mặc định.
- Không tuyên bố theo family (n < 8, cụm < 20 đối với hầu hết family); chỉ in số thăm dò.

**Báo cáo bắt buộc:** `PASS_CORRECT`, `PASS_REFUSAL`, `FAIL_OVERREFUSAL`, `FAIL_RETRIEVAL`,
`FAIL_HALLUCINATED_ON_UNANSWERABLE`, `FAIL_FABRICATED`, `FAIL_INCOMPLETE`; `refusal_rate`;
`fabrication_rate_on_answered`; tỉ lệ `gold_in_top_k` (cơ chế); latency median/p95.

**Điều kiện công cụ đã biết (không được giấu):** `tools/loop/run_round.py` **không ghi**
`ENABLE_DENSE_ORIGINAL_QUERY` vào `settings` (PA-51 chưa duyệt). Vì vậy sau lượt chạy phải
ghi sidecar `data/loop/rounds/r20/env_sidecar.json` (biến môi trường thật + lệnh chạy) và
coi sidecar là bản tự ký bổ sung; manifest của runner một mình **không đủ** để chứng minh
cấu hình. Không sửa runner trong lượt này.

**Chi phí dự kiến:** ~100 lượt classifier Ollama + 100 lượt sinh (~16 s/item ở r5) ⇒
khoảng 30–45 phút; 0 Gemini; không đổi index/`k`/trọng số.

**Artifact:** `data/loop/rounds/r20/` (thư mục mới), `tmp/r20_paired_2026-10-27.json` + `.log`.
Không ghi đè round nào đã công bố.

## Q4 — ĐĂNG KÝ TRƯỚC phép thử căng cho PA-49 (viết 27-10, TRƯỚC khi chạy)

**Câu hỏi.** Nếu **mọi** câu hỏi đã bị `fold` từ đầu (đầu vào mất dấu — kịch bản xấu nhất),
cờ `ENABLE_DENSE_ORIGINAL_QUERY` còn tạo khác biệt nào không?

**Thiết kế.** 811 item, cùng bản sao index 361 chunk, mọi cờ khác TẮT (nền r17-T). Mỗi item
dùng `q' = fold(raw_query)` cho cả hai lượt; cờ BẬT và TẮT; `k` nhánh = 12, top-6. Đo trên
700 item có gold (gold@6) và 97 item HUMAN (nguồn đúng còn trong top-6).

**Kỳ vọng đăng ký trước (để phát hiện lỗi triển khai, không phải giả thuyết cần chứng minh):**
vì `fold` idempotent (đã kiểm 811/811 ở r17), nhánh dense nhận **cùng một chuỗi** ở cả hai cờ
⇒ hai lượt phải trùng **từng item** (tập và thứ tự top-6). Lệch 1 item ⇒ lỗi triển khai, dừng.

**Cách đọc số:** nếu trùng, gold@6 và neo HUMAN của **cả hai** cờ bằng mức nền all-off
(536/700 và 75/97 theo r17); nghĩa là lợi ích +45 của r17 **biến mất** khi đầu vào không còn
dấu. Đây là **giới hạn phạm vi** của PA-49 (production giả định câu hỏi tiếng Việt có dấu),
không phải bằng chứng chống bật cờ. Không đổi ngưỡng nào.

**Artifact:** `tmp/q4_fold_stress_2026-10-27.json` + `.log` (tên mới).

## Q5 — KẾ HOẠCH THĂM DÒ index cũ/mới trên 606 item đã neo (viết 27-10, TRƯỚC khi chạy)

Đây là **thăm dò**, không mở cổng, không thay r19: r19 vẫn đóng vì điều kiện ≥90% neo chưa đạt
(58,14% V3 + 199 neo mục = 606/700 = 86,57%). Phạm vi đúng 606 item đã neo; **94 item chưa neo
bị loại** (đo trên chúng là đo một tập khác).

- **Neo:** 407 item có `target_ids` từ V3 (`tmp/vie_anchored.json`) + 199 item neo theo
  `nguồn + tiêu đề mục` (P6). Item có nhiều chunk đích được tính "trúng" nếu **bất kỳ** chunk
  đích nào vào top-6; vì vậy phải in kèm phân bố số đích (trung bình, tối đa, % item > 1 đích)
  — không được đọc con số hit@6 như thể mỗi item có một đáp án duy nhất.
- **Hai lượt:** cùng một câu hỏi **nguyên văn**, mọi cờ TẮT (nền r17-T), chỉ khác index
  (bản sao `chroma_db` vs bản sao `chroma_db_vie`), `k`=12, top-6.
- **Số báo:** hit@6 ghép cặp trên 606 (McNemar chính xác + bootstrap cụm `source_document`,
  10k, seed `20261027`), theo family chỉ khi n≥8 (thăm dò); latency; phân bố số đích.
- **Xuất để duyệt tay:** 30 neo tự động (phân tầng theo `anchor_kind` và family, seed cố định),
  mỗi dòng có câu hỏi, nguồn, mục, chunk cũ, (các) chunk mới, bằng chứng khớp, số đích →
  `tmp/q5_anchor_review_30.md`. Không tuyên bố 30/30 đạt thay người duyệt.
- **Không** ghi đè `tmp/vie_anchored.json`, không sửa `chroma_db*`, không sinh testset mới.

## r21 — ĐĂNG KÝ TRƯỚC xác nhận độc lập (28-10-2026, TRƯỚC chọn mẫu và chạy)

**Phạm vi được duyệt:** tự trị, không hỏi, không tạo PA mới, 0 Gemini. Hai nhánh pha full
trên cùng 300 item mới có `gold_chunk_id`, loại TOÀN BỘ 100 id r5 (kể cả id không có gold).
Không sửa `src/`, runner, trọng tài, ngưỡng, index thật hoặc artifact đã công bố.

**Làm rõ cấu hình trước khi thấy số:** r5 lịch sử bật classifier/answer_guard/soft_filter/rescue,
nhưng yêu cầu r21 ghi rõ “mọi cờ TẮT”. Ưu tiên yêu cầu all-off: A giữ model/cửa sổ/trọng số của
r5 nhưng TẮT classifier, answer_guard, rescue, soft_filter, query expansion và mọi lever khác;
B = A với duy nhất `ENABLE_DENSE_ORIGINAL_QUERY=1`. r21 vì vậy là xác nhận hiệu ứng dense raw
trên nền all-off, KHÔNG phải sao lặp đúng cấu hình r20. Không nhập nhằng hai nền khi pooled.
`ENABLE_HYBRID_SEARCH=1` là đường truy xuất nền BM25+dense cần kiểm, không phải lever can thiệp.
Chuẩn hóa LocalSLM tiền xử lý vẫn theo pipeline hiện hành (không có cờ tắt, không sửa code).

**Mẫu cố định:** lấy pool gold của `testset_v1.jsonl`, bỏ 100 id ở `rounds/r5/full.jsonl`;
phân tầng theo family, quota tỷ lệ kích thước family theo Hamilton (largest remainder), bảo đảm
ít nhất 1 item/family nếu còn item; trong mỗi family sắp id rồi dùng RNG Python seed `20261028`
để lấy mẫu không hoàn lại. Xáo thứ tự 300 item một lần với cùng RNG, hai nhánh dùng đúng thứ tự.
Lưu TRƯỚC khi gọi pipeline: `tmp/r21_20261028/ids.json`, `items.jsonl`, quota, danh sách id r5
bị loại, hash testset/input và snapshot nguyên byte mục đăng ký này. Không chọn mẫu theo recall,
verdict hay câu trả lời; không `--only-retrieved` vì sẽ làm co mẫu số theo can thiệp.

**Cấu hình chung A/B (ký sidecar trước mỗi nhánh):**

- `--phase full --split all --strategy all --limit 300 --top-k 6 --generator offline_qwen`
  với `--testset tmp/r21_20261028/items.jsonl`; không lọc lại family hoặc recall.
- Qwen `qwen2.5:1.5b-instruct`, temperature 0,1, num_ctx 8192, num_predict 512, prompt v1.3;
  Ollama cùng host/model/digest cho hai nhánh; embedding BAAI/bge-m3 CPU.
- Hybrid BM25/dense 0,5/0,5, RRF c=60, oversampling=2 (12 ứng viên, top-6 cho generator).
- TẮT: `ENABLE_CLASSIFIER`, `ENABLE_ANSWER_GUARD`, `ENABLE_ANSWER_RESCUE`,
  `ROUTER_SOFT_FILTER`, `NORMALIZE_SANITY_GUARD`, `ENABLE_DECOUPLED_REFUSAL`,
  `ENABLE_EVIDENCE_SELECTION`, `ENABLE_RERANKER`, `ENABLE_CONTEXTUAL_HEADER`,
  `ENABLE_QUERY_EXPANSION`, `RERANKER_KEEP_CANDIDATES`, `RERANKER_FALLBACK`;
  `ROUTER_SOURCE_QUOTA=0`. `ROUTER_FILTER_RANK_BONUS=3`, `RESCUE_MIN_SCORE=0.8`
  giữ nguyên nhưng không hoạt động khi classifier/rescue TẮT.
- `GENERATION_CACHE=0`; thư mục cache mới riêng A/B, không tái dùng câu trả lời của r5/r20.
  A `ENABLE_DENSE_ORIGINAL_QUERY=0`; B `=1`; ngoài cờ này chỉ đường dẫn output/cache/index-copy
  khác để cách ly, không khác nội dung index/model/input.
- Copy index cũ thành hai bản mới dưới `tmp/r21_20261028/`, kiểm tên collection
  `agu_regulations` và count=361; lệch thì dừng. Không mở `chroma_db`/`chroma_db_vie` thật.
- Chạy tuần tự A rồi B, không tranh GPU; ký model digest trước mỗi nhánh. Seed chỉ ghim mẫu và
  bootstrap; sampling sinh temperature 0,1 theo pipeline cũ, KHÔNG giả vờ đã ghim RNG Ollama.

**Trọng tài:** `2911c69f740d` hiện hành, chấm bằng `score_item`/runner hiện có. Hash nguyên byte
runner/trọng tài/pipeline trước-sau; sai chữ ký, khác id, lỗi hệ thống hoặc nhánh thiếu item ⇒
phép thử không đủ điều kiện kết luận, giữ nguyên số đã đo và lý do.

**Điểm cuối chính:** `PASS_CORRECT` ghép cặp theo id, CHỈ 300 item mới.
Gọi b = A sai/B đúng, c = A đúng/B sai, delta = B−A = b−c (item).

**LUẬT QUYẾT ĐỊNH CHỐT TRƯỚC:** McNemar chính xác hai phía **p < 0,05** VÀ
**|delta| >= 3 item** VÀ veto an toàn không kích hoạt (số `FAIL_FABRICATED` và
`FAIL_HALLUCINATED_ON_UNANSWERABLE` ở B KHÔNG tăng so A) ⇒ **“xác nhận”**, ghi rõ chiều.
Nếu xác nhận chiều âm thì là xác nhận suy giảm, KHÔNG phải ủng hộ bật cờ. Ngược lại ⇒
**“không xác nhận”**. CI bootstrap chỉ báo bổ sung, KHÔNG thêm điều kiện CI vào luật này.
Ngưỡng p nghiêm ngặt `<` (khác r20 `<=`); |delta| tính bằng item, không đổi thành phần trăm.
Không sửa luật hoặc đổi mẫu sau khi thấy số.

**Báo bắt buộc:** PASS_CORRECT từng nhánh, bảng mọi verdict, refusal (số và tỷ lệ), bịa (số
FAIL_FABRICATED, tỷ lệ unsupported trên answered), hallucinated, gold-in-context, latency;
McNemar b/c/p; bảng theo family là thăm dò (không dùng để kết luận, không hiệu chỉnh ngưỡng
riêng để “cứu” kết quả). Bootstrap paired theo cụm `source_document`, 10.000 lần,
seed `20261028`, CI percentile 95% cho delta-rate; in số cụm.

**Noise floor:** mốc lịch sử ±3 item/100 của pha sinh, KHÔNG phải đo nhiễu trên mẫu r21.
Báo mốc này kèm kết quả; quy đổi tỷ lệ mô tả ±3 điểm % tương đương ±9/300 nhưng KHÔNG coi
đây là ước lượng noise floor đã kiểm ở n=300, không thay ngưỡng |delta|>=3 của yêu cầu.
Không phát sinh nhánh lặp noise-control ngoài hai nhánh được duyệt.

**Pooled mô tả:** r21 300 + r20/r5-v2 100 = 400 cặp không trùng id; chỉ cộng PASS_CORRECT,
refusal/verdict và delta mô tả. Ghi rõ 100 cặp cũ chứa 20 item không gold và cấu hình khác;
KHÔNG dùng pooled p/CI để kết luận “xác nhận”.

**Hạn chót cứng:** thứ Năm **29-10-2026 22:00:00 +07:00 (Asia/Ho_Chi_Minh)**.
Controller tính thời gian còn lại cho từng subprocess; đến hạn dừng nhánh đang chạy và
không mở nhánh mới. Ghi số dòng hoàn thành/dở từng nhánh, chấm chỉ-đọc phần có sẵn, trạng thái
“DỞ — không đủ 300 cặp, không kết luận”; không ngoại suy hoặc đổi tiêu chí để lấp phần thiếu.
Ước tính người dùng ~2,7 giờ máy là dự kiến, không phải ngân sách cho phép đổi mẫu.

**Artifact mới:** `data/loop/rounds/r21_A/`, `r21_B/`,
`tmp/r21_20261028/{ids.json,items.jsonl,preregistration.txt,status.json,paired_analysis.json,report.md}`.
Không ghi đè nếu đường dẫn tồn tại; không commit, không tạo PA mới, không tự bật mặc định.
Manifest hiện có đã đỏ 3 tệp container sau r20: ghi delta trước-sau, không sinh lại để làm xanh giả.

## r21 nhãn lại — KHÔNG HỢP LỆ (đăng ký 28-10, SAU khi có status; không phải sửa số)

r21 lần 1 mang nhãn **`INVALID_ANCHOR_DRIFT`**: controller ghi
`anchor_files_changed = [tools/eval/classify_real_questions.py]` — runner D3 (ca kiểm classifier,
phiên trước) tạo tệp lúc **12:01:53**, rơi vào cửa sổ nhánh B (B chạy 11:15:18–12:17:48). Hai nhánh
vẫn COMPLETE 300/300, 0 lỗi hệ thống, model/index-copy nguyên vẹn; `eligible_primary=false` nên
không kết luận. **Giữ nguyên mọi số mô tả** của lần 1 (`tmp/r21_20261028/{paired_analysis.json,report.md}`,
`data/loop/rounds/r21_A|B/`): không xóa, không chỉnh, không dùng làm bằng chứng xác nhận.
Bài học đăng ký: không thêm/sửa tệp trong cây mã khóa (theo `snapshot_files` cũ gồm toàn bộ `tools/**/*.py`)
trong khung giờ hai nhánh của paired round.

## r21b — ĐĂNG KÝ (bản sao lặp, KHÔNG mù) xác nhận tái lập r21 (28-10, trước khi chạy r21b)

**Bản chất, ghi nhận trung thực:** kết quả r21 lần 1 đã thấy (dù không hợp lệ để kết luận), nên
r21b **không phải kiểm định độc lập mù**; đây là **bản sao lặp xác nhận** — mục tiêu là tái lập
hành vi hai nhánh và đo **nhiễu thực của cấu hình** (verdict đổi chỗ giữa lần chạy 1 và 2),
không phải cơ hội sửa kết luận. Luật, mẫu, cấu hình giữ NGUYÊN văn bản mục r21 ở trên.

**Chạy lại:** hai nhánh tuần tự A (all-off) rồi B (`ENABLE_DENSE_ORIGINAL_QUERY=1`), trên **ĐÚNG
300 id đã đóng băng** trong `tmp/r21_20261028/ids.json` (hash `ids_sha256` từ `prelaunch_lock.json`
lần 1 được chép sang làm mốc; không chọn mẫu mới, không đổi seed). Round mới
`data/loop/rounds/r21b_A/`, `r21b_B/`; thư mục làm việc riêng `tmp/r21b_20261028/`
(không đụng artifact r21 lần 1, **không dùng lại** `tmp/r21_20261028/prelaunch_lock.json` —
lock mới tự sinh, controller mới từ chối chạy nếu status/round đã tồn tại).

**LUẬT QUYẾT ĐỊNH GIỮ NGUYÊN, không đổi sau khi thấy số:** McNemar chính xác hai phía **p < 0,05**
VÀ **|Δ| >= 3 item** VÀ `FAIL_FABRICATED_B <= A` VÀ
`FAIL_HALLUCINATED_ON_UNANSWERABLE_B <= A` ⇒ “xác nhận” (ghi rõ chiều); ngược lại “không xác nhận”.
CI bootstrap bổ sung mô tả, không thêm điều kiện. Family: thăm dò.

**Thu hẹp danh sách tệp neo của controller r21b (thay đổi dụng cụ, khai báo minh bạch):** neo =
**chỉ các tệp nằm trên đường chạy** — `src/**/*.py` và `tools/loop/**/*.py` (mọi tệp run_round.py
import trực tiếp/gián tiếp; đã kiểm AST/grep 28-10: `src.*` + `tools.loop.verify`). **Lý do thu
hẹp:** `snapshot_files()` của r21 ghim cả `tools/**/*.py`, `README`, manifest, `docs/evidence_pack.json`,
chroma — nên một tệp ngoài đường chạy (`tools/eval/classify_real_questions.py`, chưa từng được
run_round import) vẫn làm trôi neo và giết round hợp lệ về mặt khoa học. Ghi nhận trung thực chiều
ngược: neo rộng có giá trị phát hiện can thiệp ngoài đường chạy; r21b đánh đổi giá trị đó lấy việc
round không chết vì tài liệu. Các kiểm soát độc lập vẫn giữ NGUYÊN và không bỏ: `check_lock`
(sha256 của ids/items/testset/prereg/controller/analysis), fingerprint trọng tài
`2911c69f740d` trước/sau mỗi nhánh, model digest, index-copy digest, auxiliary hashes.
Không thêm/bớt tệp nào khác khỏi phạm vi đo.

**Watchdog (mới, một chiều chỉ phát hiện):** trong lúc chạy, một luồng poll mỗi ≤60s tính
sha256+mtime mọi tệp neo đường chạy; nếu lệch: ghi `tmp/r21b_20261028/drift_log.txt` (tệp + giờ +
hash trước/sau), dừng nhánh đang chạy, trạng thái `DRIFT_STOPPED`, **không kết luận, không tự chạy lại**.

**Hạn chót cứng:** 29-10-2026 22:00 +07:00 (như r21); chưa xong ⇒ dừng, ghi dở, chấm chỉ-đọc phần có sẵn.

**Phân tích sau chạy (đăng ký trước):** (1) luật ở trên; (2) so run1↔run2 **từng nhánh**
(A1-A2, B1-B2): số verdict đổi chỗ + McNemar ghép cặp — mô tả nhiễu thực, KHÔNG pool với r20 để
kết luận; (3) hậu nghiệm, gắn nhãn rõ: danh sách ca `FAIL_FABRICATED` của B lần 2 (câu hỏi, thực thể
không căn cứ, `answer_guard` hiện hành có chặn không — chạy trên văn bản đã lưu, 0 gọi model);
(4) xác nhận fingerprint/pytest/`ARTIFACT_MANIFEST --check`, đỏ do container Chroma tự ghi lại thì
ghi nguyên nhân, không sinh manifest giả xanh. Báo cáo: `tmp/r21b_report.md`. Không mục “Ngã rẽ”.
