# Kiểm thử T3 — `ENABLE_DECOUPLED_REFUSAL` + `ENABLE_EVIDENCE_SELECTION`

Ngày: 24-10 (ca tối). Người chạy: agent kiểm thử (chế độ tự trị).
Phạm vi: **chỉ thêm test + golden + script mutation**, không sửa `src/`, không sửa trọng tài
(`tools/loop/verify.py`, `src/answer_guard.py`, `src/text_utils.py`, `tools/loop/gate.py`).

## 1. Đã làm gì

1. **Golden cờ TẮT (mục A):** dựng harness [`tools/diag/t3_golden_dump.py`](../../tools/diag/t3_golden_dump.py)
   30 item cố định (10 câu hỏi × 3 biến thể chunk giả), chạy nó trong **hai cây**:
   - cây hiện tại (có nối T3, nhưng cờ TẮT),
   - bản `git archive HEAD` tại commit `f492f05` đổ vào `tmp/t3_baseline_head`.
   Tại `f492f05`, `src/pipeline.py` **không có dòng T3 nào** (`meta.pipeline_has_t3_fields=false`
   trong golden), nên đây là "trước khi sửa" thật, không phải golden tự sinh vòng tròn.
   Golden lưu tại [`tests/golden/t3_off_30items_head_f492f05.json`](../../tests/golden/t3_off_30items_head_f492f05.json).
2. **Bộ test** [`tests/test_t3_guardrails.py`](../../tests/test_t3_guardrails.py): **75 test**,
   phủ đủ A/B/C/D của đề bài; mọi tầng dưới là fake/stub (`StubGenerator` trả chuỗi cố định,
   `FakeOllama` cho QwenGenerator, `sentence_transformers` bị chặn bằng module giả nên
   **không tải model hàng GB**).
3. **Mutation check** [`tmp/mutation_check_t3.py`](../../tmp/mutation_check_t3.py): 7 đột biến,
   sửa theo **byte-anchor** trên chính file nguồn, chạy lại file test, khôi phục bằng
   `write_bytes` và xác nhận SHA-256 **từng byte** trùng bản gốc.

## 2. Kết quả số (nguồn: file trên đĩa)

### A. Cờ TẮT — byte-identical

| Chỉ số | Giá trị | Nguồn |
|---|---|---|
| SHA-256 file golden | `e59b9ebb6b12c2d6844356f5861cc98d418c11b26f83a49fdae1f8f2ea1728b5` | `tests/golden/t3_off_30items_head_f492f05.json` |
| SHA-256 khối `core` (30 item, JSON sort_keys) | `344d55cd35ec64b876d1f7580724eb968f158a21fbf42c64a28b54d3c8784b11` | như trên |
| Số item / số cache key Qwen phân biệt | 30 / 30 | `meta` + `core[*].qwen_cache_key` |
| `gen_calls` / `leg_calls` / `ensemble_calls` | 30×{1} / 30×(0,0) / 15×{2}, 15×{1} | `core[*]` |
| `pipeline_has_t3_fields` tại baseline | `false` | `meta` |

Test `test_off_30item_dau_ra_byte_identical_voi_golden` chạy lại 30 item trên cây hiện tại và
so **từng item, từng khoá** với golden: khớp (75/75 test xanh). Hành vi cũ được ghim thêm:
không có dòng log `[DecoupledRefusal]`/`[EvidenceSelection]`, hai khoá `refusal_decision`/
`evidence_selection` là `None`, `leg_calls` không được đo (đường tắt không đụng per-leg rank),
prompt Qwen và `qwen_cache_key` trùng golden (cùng công thức legacy `v1.3`).

### B. Decoupled refusal

- **Prompt BẬT không còn lời mời từ chối:** bộ regex có răng (`không tìm thấy`, `không đủ thông
  tin`, `từ chối`, chuỗi canonical, marker fold) trả **0 hit** cho cả 4 nhãn câu hỏi
  (None/SO_SANH/THU_TUC/NGOAI_PHAM_VI). Chứng minh regex không rỗng: chạy trên prompt đường
  TẮT cho **≥2 hit**, gồm đúng chuỗi canonical.
- **Ngoại lệ đã ghim chính xác:** `EXTRACT_ONLY_HEAD` (src/generator.py:1018) có chữ "từ chối",
  nhưng **chỉ trong câu cấm** "Bạn KHÔNG được quyền phán xét ngữ cảnh, không được quyền từ
  chối" (dòng 1021). Test kiểm **mọi** lần xuất hiện đều nằm ngay sau phủ định — nếu ai thêm
  một lời mời từ chối thật, test đỏ.
- **Guard chặn câu bịa:** 5 dạng thực thể bịa (số lần, tiền+ngày, tỉ lệ %, giờ mở cửa,
  Điều/Khoản bịa) + ca gốc ⇒ **6/6** trả về **đúng** `REFUSAL_TEXT` (so `==`, không `in`).
- **Có căn cứ thì trả lời:** câu chép nguyên văn từ ngữ cảnh ⇒ `refuse=False`, câu trả lời
  **không bị ghi đè**.
- **Luật pre chặn trước khi sinh:** hạng yếu (chunk vàng tụt hạng 12/9 ở hai nhánh), cửa sổ lạc
  đề (overlap 0,0), ngữ cảnh rỗng ⇒ `gen.calls == 0` đúng như đăng ký.
- **Ngưỡng biên:** mặc định đọc từ `thresholds()` = `0.34 / 0.20 / 0.90 / 0.60 / 1`. Với fixture
  đo được coverage `0,5` và overlap `0,6667` (câu hỏi 2 thực thể, 3 token; ngữ cảnh chứa 1 thực
  thể): đặt ngưỡng **đúng bằng** ⇒ ĐẠT; **+1e-6** ⇒ CHẶN `off_topic_window`; **−1e-6** ⇒ ĐẠT.
  `rrf_norm` thử biên ở hạng (4,4) và (10,10); grounding thử ở 1,0 và env ngoài [0,1] bị kẹp về
  mặc định. Test `inspect.getsource` xác nhận `decide_*` chỉ so với `th[...]`, không hardcode
  "0.34"/"0.90"/… trong thân hàm.
- **Thứ tự guard/cache:** chặn trước sinh ⇒ cache **rỗng**; chặn sau sinh ⇒ cache có **đúng 1**
  entry là **văn bản thô** của model, **không bao giờ** là `REFUSAL_TEXT`; lần chạy thứ hai trúng
  cache nhưng **vẫn bị chặn** (phán quyết là hàm deterministic của answer × contexts).
- **Cache key:** đường TẮT = công thức legacy `v1.3` (tính lại độc lập bằng sha1); đường BẬT =
  sha1 với `prompt_version = v2.0-extract-only`; bật↔tắt **không đọc nhầm** cache của nhau
  (đo bằng số lần gọi `FakeOllama` và ở cả hai chiều).
- **Bất thường:** ngữ cảnh rỗng ⇒ `REFUSAL_TEXT`, `gen.calls=0`; câu hỏi rỗng ⇒ `ValueError`
  nhất quán ở cả cờ TẮT/BẬT, `gen.calls=0`; câu hỏi chỉ khác dấu ⇒ cùng phán quyết và cùng
  `coverage`/`overlap`/`n_relevant_chunks`.

### C. Evidence selection

- Số câu chọn trong **[3,5]** khi cửa sổ đủ câu; ngữ cảnh ngắn hơn min ⇒ **giữ nguyên cửa sổ
  gốc** kèm `reason="not_enough_qualifying_sentences"` (không cắt bừa).
- Thứ tự: **giữa chunk** theo hạng chunk gốc; **trong chunk** theo mạch đọc gốc (test kiểm vị
  trí `original.index(s)` tăng dần).
- Ưu tiên bậc thang: câu chứa thực thể phía câu hỏi nằm trong tập chọn khi đủ ngân sách; thực
  thể **không có** trong ngữ cảnh ⇒ không crash, không bịa câu mới; câu tier thấp **không** được
  nhặt khi còn câu tier cao bị loại.
- Deterministic: hai lần chạy cùng input ⇒ cùng nội dung, cùng metadata, cùng `info`; tie-break
  khi mọi điểm = 0 là `(doc_index, sent_index)`.
- Không bịa: **mọi** câu trả về là **chuỗi con nguyên văn** của một chunk gốc; metadata
  (`chunk_id`/`source`/`tier`) sao nguyên; `sources` (cửa sổ recall) **không đổi**.

### D. Chống bịa — 10 câu "không có đáp án"

**10/10 từ chối** (mỗi ca so `== REFUSAL_TEXT`), **0/10 gọi generator**. Đo chi tiết: cả 10 ca bị
chặn ở **pre**, lý do `off_topic_window`, `overlap=0.0`.

**Hạn chế của D (ghi thẳng):** cả 10 ca đều bị **luật 2** chặn vì ngữ cảnh tổng hợp không chia
token nội dung nào với câu hỏi. Vì vậy D **một mình không chứng minh** guard sau sinh còn hoạt
động — phần đó do `TestOuterRefusal` (5 dạng bịa) đảm nhiệm, và mutation M1b dưới đây chứng minh
test đó thật sự bắt lỗi.

## 3. Mutation check — 7/7 BẮT ĐƯỢC, 7/7 hoàn nguyên byte-identical

Chạy: `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t3.py`
(baseline xanh 75 passed trước khi đột biến).

| # | Đột biến (byte-anchor trên file nguồn) | Kỳ vọng phá | Test đỏ (số lượng) | Khôi phục |
|---|---|---|---|---|
| M1 | `_cache_put(..., text)` → `_cache_put(..., REFUSAL_TEXT)` (cache chứa kết quả **sau** guard = đảo thứ tự guard/cache) | câu bị chặn không bao giờ vào cache | `test_luat_chan_sau_sinh_refusal_khong_bao_gio_vao_cache` (1) | byte-identical |
| M1b | `if post.refuse:` → `if False and post.refuse:` (bỏ guard sau sinh) | câu bịa bị thay bằng canonical | 7 test: ca bịa gốc + 5 dạng bịa + cache-order (7) | byte-identical |
| M2 | 4 hằng ngưỡng `0.34/0.20/0.90/0.60` → `0.0` | luật 2/3/4 mất hiệu lực | 6 test: pre-block ×2, cổng trước sinh, aggregate D, mặc định ngưỡng, biên rrf (6) | byte-identical |
| M3 | pre `answer = REFUSAL_TEXT` → `None`; post `answer = REFUSAL_TEXT` → `answer = answer` | bỏ nhánh từ chối | **23 test** (toàn bộ TestOuterRefusal, 10 ca D, cache-order, ngữ cảnh rỗng) | byte-identical |
| M4 | `key=lambda c: c.sent_index` → `c.sentence` | đảo mạch đọc trong chunk | `test_thu_tu_giua_chunk_theo_hang_goc_trong_chunk_theo_mach_doc` (1) | byte-identical |
| M5 | tie-break `(doc_index, sent_index)` → `(-doc_index, -sent_index)` | tie-break sai chiều | `test_tie_break_on_dinh_khi_diem_bang_nhau_het` (1) | byte-identical |
| M6 | `effective_prompt_version()` luôn trả `PROMPT_VERSION` | bật/tắt dùng chung cache | `test_ON_cache_key_chua_PROMPT_VERSION_moi` (1) | byte-identical |

Ghi chú M2: 10 ca D **riêng lẻ** vẫn xanh dưới M2 vì `answer_guard` chặn theo
`fabricated = bool(unsupported)` (xem mục 4.3) — chỉ test **tổng hợp** D đỏ (vì đòi ≥8 ca bị
chặn ở pre). Đây là lý do phải có cả test tổng hợp chứ không chỉ 10 ca rời.

## 4. Phát hiện trung thực (cần đưa vào hội đồng)

1. **Đường Gemini không có nhánh T3 (PA-14).** `GeminiGenerator.build_prompt`
   (src/generator.py:597) **không** đọc cờ `ENABLE_DECOUPLED_REFUSAL`; prompt vẫn chứa nguyên
   chuỗi canonical + lời mời từ chối. Cache key của Gemini (src/generator.py:765) dùng
   `PROMPT_VERSION` **tĩnh**, không dùng `effective_prompt_version()` như Qwen
   (src/generator.py:1176). Hệ quả: T3 chỉ có tác dụng trên đường Qwen/Ollama — đúng đường vòng
   lặp P5 đang chạy (r8/r9), nhưng nếu chuyển sang Gemini thì lever **im lặng không hoạt động**.
   Test `test_DUONG_GEMINI_hien_trang_khong_co_nhanh_T3_dac_ta_hien_trang` ghim hiện trạng để
   không ai tưởng nhầm là đã phủ.
2. **Chữ "từ chối" trong prompt BẬT là câu cấm, không phải lời mời.** Đề bài yêu cầu regex bắt
   cụm này; nếu kiểm thô "không được chứa chữ 'từ chối'" thì **đỏ oan** và sẽ dẫn tới sửa sai
   thiết kế (xoá câu cấm quyền từ chối của model — trái mục tiêu decoupled). Test ghim đúng
   phạm vi "mọi lần xuất hiện phải nằm sau phủ định".
3. **`DEC_MAX_UNSUPPORTED = 1` là dead code, trần hiệu dụng = 0 (PA-15).**
   `Report.fabricated` (src/answer_guard.py:156-157) trả `bool(self.unsupported)`; luật 4 của
   `refusal_policy` dựa trên `fabricated`, nên **một** thực thể chưa căn cứ đã chặn — nghiêm hơn
   con số 1 đã đăng ký. Test
   `test_max_unsupported_hien_trang_bi_luat_fabricated_che_khu_dac_ta_hien_trang` đo: đặt
   `DEC_MAX_UNSUPPORTED=9` vẫn chặn. Không sửa gì (trọng tài/`answer_guard`) — chỉ ghi đề xuất.
4. **Luật 2 là nhị phân trên câu hỏi chuẩn của P5.** `content_tokens("Sinh viên học lại tối đa
   bao nhiêu lần mỗi học phần?")` chỉ còn **1 token** (`phan`) ⇒ overlap chỉ có thể 0,0 hoặc 1,0;
   ngưỡng đăng ký 0,20 **không thể thử biên** trên câu này. Vì vậy bài test biên dùng fixture
   riêng `Q_BOUNDARY` (2 thực thể, 3 token) đo được coverage 0,5 / overlap 0,6667. Hệ quả cho
   thiết kế: với câu hỏi ngắn tiếng Việt, luật 2 thực chất là "có/không có token nội dung", không
   phải thang điểm — nên ghi vào hạn chế, không chỉnh ngưỡng (đã đăng ký trước).

## 5. Phần KHÔNG được kiểm thử + lý do

- **Sinh thật bằng Qwen/Ollama và reranker cross-encoder thật:** unit test cấm tải model/mạng
  (máy 4 GB). Hành vi thật đã được đo ở round r8/r9; bộ test này chỉ kiểm **logic quyết định**
  với stub. Không suy ra được từ đây con số refusal/PASS_CORRECT thật.
- **Đường Gemini (mục 4.1):** không có nhánh T3 để kiểm; chỉ có test đặc tả hiện trạng.
- **Testset 811 item thật:** golden dùng 30 item tổng hợp cố định (fake retrieval) để bảo đảm
  byte-identical và không phụ thuộc ChromaDB/model.
- **Latency, `prompt_eval_count`, VRAM:** không phải phạm vi unit test.
- **"Độ phủ thực thể vàng" theo nghĩa testset:** không đọc `gold_*`/`required_entities` ở runtime
  (bất biến #6) nên các test dùng **thực thể phía câu hỏi**; nhãn "vàng" trong đề bài được hiểu
  là thực thể mà câu hỏi yêu cầu, không phải trường đáp án.
- **Hành vi `answer_guard` độc lập** (đã có `tests/test_answer_guard.py` của phiên khác).

## 6. Tiêu chí xong

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| A xanh tuyệt đối | **ĐẠT** — 30/30 item byte-identical, cache key trùng | 6 test `TestOffGolden`, golden sha `e59b9ebb…`, core sha `344d55cd…` |
| D không đỏ | **ĐẠT** — 10/10 từ chối, 0/10 gọi generator | `TestRefusesAllUnanswerable` |
| Mutation (guard/cache, ngưỡng→0, bỏ nhánh từ chối) bị bắt | **ĐẠT** — 7/7 | mục 3 |
| Toàn suite xanh | **ĐẠT** — `854 passed` (37,33 s) | `venv/Scripts/python.exe -m pytest tests -q` |
| Trọng tài không đổi | **ĐẠT** — `9f1179ccab74`; `git diff` rỗng trên `verify.py`/`answer_guard.py`/`text_utils.py`/`gate.py` | lệnh ở mục 7 |

## 7. Lệnh tái lập

```bash
cd D:/DoAn/hybrid_rag_agu
export PYTHONIOENCODING=utf-8            # Windows console cp1258 làm vỡ tiếng Việt

# (a) riêng nhóm T3
venv/Scripts/python.exe -m pytest tests/test_t3_guardrails.py -q -p no:cacheprovider

# (b) toàn suite
venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider

# (c) chữ ký trọng tài + xác nhận không sửa file bảo vệ
venv/Scripts/python.exe -c "from tools.loop.verify import referee_fingerprint as f; print(f())"
git diff -- tools/loop/verify.py src/answer_guard.py src/text_utils.py tools/loop/gate.py

# (d) mutation check (tự khôi phục từng byte)
venv/Scripts/python.exe tmp/mutation_check_t3.py

# (e) chụp lại golden (chỉ khi cần dựng lại baseline từ HEAD)
git archive HEAD | tar -x -C tmp/t3_baseline_head
cp tools/diag/t3_golden_dump.py tmp/t3_baseline_head/tools/diag/
cd tmp/t3_baseline_head && PYTHONIOENCODING=utf-8 ../../venv/Scripts/python.exe tools/diag/t3_golden_dump.py
```

## 8. Đề xuất cần duyệt (đã ghi vào `docs/PENDING_APPROVAL.md`)

- **PA-14:** có nối `ENABLE_DECOUPLED_REFUSAL` vào đường Gemini hay không (prompt + cache key),
  kèm diff đề xuất; nếu không, ghi rõ trong README rằng T3 chỉ áp cho đường Qwen.
- **PA-15:** xử lý `DEC_MAX_UNSUPPORTED` đang là dead code — chọn (a) sửa luật 4 dùng đúng trần
  đã đăng ký, hay (b) đăng ký lại trần hiệu dụng = 0; cả hai đều cần duyệt vì chạm ngưỡng đã
  công bố.
