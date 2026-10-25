# PENDING_APPROVAL — việc cần người dùng duyệt (phiên tự trị KHÔNG tự làm)

Mỗi mục: bối cảnh → đề xuất → diff/đường dẫn → cách hoàn tác nếu bị từ chối.

---

## Trạng thái PHIÊN B (26-10 03:2x) — đọc mục này trước khi xuống các PA cũ

**Đã duyệt VÀ đã áp dụng trong phiên B** (bằng chứng: `docs/DECISION_LOG.md` D-37, D-41; báo cáo
`docs/reports/B2.md`, `docs/reports/B3.md`):

- **PA-2 + PA-20** → trọng tài v1 `9f1179ccab74` **→** v2 `2911c69f740d`; chấm lại OFFLINE 10 round ×
  100 câu vào `data/loop/rounds_v2/` (5/1000 verdict đổi, tất cả theo hướng chặt hơn; PASS_CORRECT
  148 → 143). `data/loop/rounds/` và `gate.py` **không đổi một byte nào**.
- **PA-25** → `src/reranker.py` chấm query **nguyên văn** (bỏ `fold()`); round mới **r16** = số đo
  retrieval tốt nhất từng ghi trên bộ 811 item (gold@6 0,8357; EXACT 0,4231). **`ENABLE_RERANKER` vẫn
  TẮT** — r16 chỉ bật bằng biến môi trường của riêng tiến trình đo.

**Đã duyệt nhưng CHƯA áp trong phiên B** (không có mục nào trong đề bài B1–B5 yêu cầu, và cả hai đều
đụng tới thước đo/index đang có số công bố):

- **PA-13** (cổng refusal tương đối Δ 0,05 + trần 0,35 thành cảnh báo) — `tools/loop/gate.py` vẫn là
  cổng cũ; xem ghi chú trong `docs/AUTONOMY_LOG.md` (Ngã rẽ 25, mục (d)).
- **PA-7** (loại 2 tệp `ke-hoach` khỏi index mới) — chưa dựng index nào trong phiên B; nợ vẫn nằm ở
  **PA-17** (re-anchor) vì `chroma_db_vie` đang ĐỎ mất neo 48,81%.

**Chờ duyệt — mới trong phiên B:** PA-35 (bật reranker) · PA-36 (cổng neo HUMAN n=97/11 cặp bất đồng) ·
PA-37 (weights cross-encoder nhỏ) · PA-38 (đăng ký lại phép đo có mốc hạng) · PA-39 (lượt train thật
logits-theo-đáp-án) · PA-40 (quy ước phát ngôn bộ nhớ) · PA-41 (hai kỳ vọng cũ của `final_number_audit`).

**Thứ tự đề xuất cho sáng mai:** PA-35 (hoặc chạy pha sinh trên r16 trước) → PA-17 → PA-26/PA-33/PA-31/
PA-34 → PA-39 (+ PA-40) để đóng T4 mục 5, có thể rút PA-11/PA-12 nếu xanh → PA-41 để máy kiểm số xanh lại.

**Máy kiểm đang đỏ CÓ CHỦ ĐÍCH:** `tools/diag/final_number_audit.py` in **2/63 dòng LỆCH** — không tự sửa,
xem D-42 + PA-41. **Đính chính số đo:** máy kiểm **trả rc=0** chứ không phải 1 (nó chỉ in bảng, không có
đường fail) ⇒ "đỏ" ở đây là **đỏ trong bảng**, không phải đỏ trong exit code; ai dựa vào rc sẽ không thấy gì.
Phải chạy bằng `venv/Scripts/python.exe`: interpreter hệ thống thiếu `pypdfium2`/`streamlit` làm
collect-only lỗi 4 file và thêm **1 LỆCH GIẢ** ("81 test corpus rebuild" = -1).

---
## PA-1 — T2: kích hoạt index mới `chroma_db_vie/` và chấm lại r0–r5
- Bối cảnh: OCR lại 13 PDF scan bằng EasyOCR `vi` nâng corpus từ 0,178 → (dự kiến ~0,7). Toàn bộ
  nằm ở BẢN SAO (`chroma_db_vie/`, `.ocr_cache_vie/`); pipeline sản xuất và `chroma_db/` gốc KHÔNG đổi.
- Đề xuất (khi người dùng đồng ý): (1) đổi con trỏ corpus/DB sang bản mới; (2) chạy lại round
  r0–r5 để lấy số trên corpus đã hồi phục dấu.
- Hệ quả: đổi nội dung nạp → **chữ ký trọng tài/đầu vào đổi** → **phải chấm lại r0–r5** (quota Gemini).
- Chưa làm: chưa kích hoạt, chưa chấm lại. Hoàn tác: `rm -rf chroma_db_vie/ .ocr_cache_vie/` (bản gốc nguyên vẹn).

## PA-2 — T1: đề xuất sửa `answer_guard` cho lỗi nhận diện "Theo Bản" (LOOKS_LIKE_FORMATTING)
- Bối cảnh: dòng (b) `C10492769338965` bị `FAIL_FABRICATED` vì trọng tài gắn cờ "Theo Bản" là tên
  riêng bịa đặt — thực chất là cụm chính tả bình thường (lỗi LOOKS_LIKE_FORMATTING, cùng họ đã ghi ở audit_guard).
- Đề xuất: nới luật phát hiện tên riêng trong `src/answer_guard.py` (KHÔNG tự sửa — file thuộc
  REFEREE_FILES, đổi chữ ký `9f1179ccab74`). Cần danh sách round phải chấm lại kèm theo.
- Chặn: cần (b) đủ n=30 để đếm tỉ lệ dương-giả loại này (≥2/30 mới đáng sửa). Hiện mới n=7.
- Diff: sẽ bổ sung khi có đủ n; hiện CHƯA có thay đổi code.

**Bổ sung 24-10 23:08 — đã đủ bằng chứng để sửa, nhưng vẫn CHỜ DUYỆT:**
- Kiểm tay 5/5 ca `FAIL_FABRICATED` của (b) (25 id): **3 cờ proper là dương giả cơ học**
  (`Theo Bản` ×2, `Theo Thông` ×1); 1 ca `Khoản 1` có căn cứ ("1. Quy chế…" ngay dưới Điều 16);
  1 ca `Mục 2` là diễn giải của "2. Hồ sơ xin học". Chi tiết + nguồn chunk: `docs/reports/T1.md`
  mục "Kiểm tay 5 ca FAIL_FABRICATED". Tỉ lệ 3/25 đã vượt ngưỡng tự đặt ≥2/30.
- **Diff đề xuất** (`src/answer_guard.py`, KHÔNG áp dụng): thêm tập stopword cho từ mở đầu cụm
  hoa, để "Theo Bản mô tả…"/"Theo Thông báo…" không bị cắt thành tên riêng:
```diff
@@
+_PROPER_RUN_STOPWORDS = {fold(w) for w in {
+    "Theo", "Tại", "Căn", "Các", "Trong", "Nếu", "Khi", "Vì", "Do",
+    "Đối", "Phần", "Mục", "Về", "Bằng", "Từ", "Đến", "Với",
+}}
@@ def _scan_proper_runs(text: str) -> list[tuple[int, int, str]]:
         tok = m.group(0)
-        is_cap = bool(tok) and tok[0].isupper() and len(tok) >= 2 and not tok.isdigit()
+        is_cap = (
+            bool(tok)
+            and tok[0].isupper()
+            and len(tok) >= 2
+            and not tok.isdigit()
+            and fold(tok) not in _PROPER_RUN_STOPWORDS
+        )
```
- Hệ quả bắt buộc: đổi chữ ký trọng tài `9f1179ccab74` ⇒ phải chấm lại **mọi round đang bật
  guard** (r5, r5b, r8, r9, r10, T1(b)) và cập nhật mọi bảng số. Vì vậy đề xuất **gộp với PA-20**
  và làm thành một "referee v2" có một commit riêng + test hồi quy 5 ca này.
- Test đề xuất: `test_answer_guard.py` thêm 3 ca dương (`Theo Bản`, `Theo Thông`, `Theo Điều`)
  không sinh entity proper; giữ 1 ca âm ("Trường Đại học An Giang" vẫn được xử lý như hiện tại).

## PA-3 — cổng gate.py (đang chờ từ trước, không đổi): #23 quy tắc refusal tương đối + veto family
- Giữ nguyên trạng thái "chờ duyệt"; `gate.py` chưa sửa. Xem `docs/reports/T0.md` mục hệ quả cổng.

## PA-4 — T1 (b) tiếp tục: cần quota Gemini các ngày sau
- (b) dừng ở 6/30 vì PerDay. Đề xuất: cho resume các ngày sau (lệnh ở STATE.md) để đủ n rồi mới
  chốt nhánh bảng quyết định (T4 vs T2/T6). Đêm nay KHÔNG gọi thêm.
- **Cập nhật 24-10 23:09:** đã lên **25/30** (5 id cuối kẹt PerDay, cửa sổ kế tiếp ~14:30 25-10).
  Đây là **tiền tố theo thứ tự r5**, không phải mẫu ngẫu nhiên — xem giới hạn trong T1.md.
  Cần thêm đúng 5 lượt ở cửa sổ sau; ngân sách đêm 25-10 vẫn ≤14.

## PA-5 — T3 / T5 / TT0–TT3: KHÔNG có đặc tả trong repo hay hội thoại → bị chặn
- Bối cảnh: lệnh tự trị qua đêm ghi "viết code + test cho T3 và T5 với mọi cờ TẮT" và "chạy test
  TT0–TT3". Nhưng tìm `ROADMAP.md`, `docs/`, `*.md` **không có định nghĩa** T3/T5/TT0–TT3 (chỉ
  STATE.md do em tự chép lại từ lệnh). T1 có nhắc "T3 = chọn/độ dài ngữ cảnh", "T4 = năng lực
  model/SFT", "T2+T6 = trọng tài/corpus" nhưng KHÔNG có đầu bài cụ thể (ràng buộc, tiêu chí xong).
- Quyết định bảo thủ: **KHÔNG bịa yêu cầu để viết code** (sẽ tạo lever sai, vi phạm tinh thần
  "mỗi lever sau cờ, có test chứng minh off=identical"). Đánh dấu **bị chặn — chờ đặc tả**.
- Cần người dùng: dán đặc tả T3/T5 (và TT0–TT3 là gì) để phiên sau làm.
- Việc đã làm thay thế trong khung giờ đó: dựng công cụ T2 Bước 3 (`quality_check_vie.py`) và
  kiểm thử đường code — nằm trong phạm vi T2 đã đặc tả rõ.

## PA-6 — T2: giữ `easyocr` làm dependency hay chỉ dùng chẩn đoán một lần
- Bối cảnh: để OCR lại 13 PDF scan bằng tiếng Việt, em đã `pip install easyocr torchvision
  scikit-image` vào `venv` (không sửa `requirements.txt`). Không có gì trong pipeline sản xuất
  import easyocr — nó chỉ được `tools/diag/reocr_vie.py` nạp khi chạy tay.
- Đề xuất A (an toàn): giữ nguyên `requirements.txt`, coi easyocr là công cụ chẩn đoán; cache
  `.ocr_cache_vie/` đã sinh nên không cần cài lại nếu chỉ nạp index.
- Đề xuất B: thêm `easyocr` (+ torch/torchvision) vào requirements nếu muốn tái OCR trên máy khác.
- Chưa làm: chưa đổi requirements, chưa commit lockfile. Hoàn tác: `pip uninstall easyocr
  torchvision scikit-image` trong `venv` (không ảnh hưởng `chroma_db/`, `.ocr_cache/`).

## PA-7 — T2: có loại 2 tệp `ke-hoach-ttck-kltn-dh24pm/th-2026.pdf` khỏi corpus không?
- Bối cảnh: đây là 2 tệp chủ yếu BẢNG BIỂU; EasyOCR trả 0,602–0,603 nhưng số từ giảm mạnh
  (1710 → 560 và 1607 → 572) và 20 đoạn đối chiếu mắt thường cho thấy phần lớn là ký tự rác.
  Chúng chiếm 7 của 337 chunk ≥50% dấu trong `chroma_db_vie/`.
- Đề xuất: hoặc (1) giữ như hiện tại (index mới đã có chúng), hoặc (2) đưa sang thư mục
  `data/corpus/_khong_index/` và rebuild `chroma_db_vie/`, hoặc (3) số hóa bảng bằng tay
  (đường T6, tốn công).
- Chưa làm: KHÔNG xóa/di chuyển file corpus nào (xóa = việc cần duyệt). Hoàn tác: không có thay đổi.
- **Bổ sung 24-10 (check_corpus mục 7b):** tệp thứ **ba** cũng là "khoảng trống" và vẫn nằm trong
  index mới: `TB16 THAY DOI CONG RA VAO KTX.pdf` (2 chunk, **0,000** từ có dấu, 328 từ, PDF-TEXT
  font `Helvetica`, `tounicode_frac=0.0` — nguyên nhân ghi trong `per_file.json`: "text-layer mất
  dấu không rõ nguyên nhân"). Tệp này **không cứu được bằng re-OCR** (không phải scan); lựa chọn
  là số hóa lại bằng tay/OCR có kiểm, hoặc loại khỏi corpus. Danh sách leak đầy đủ:
  `corpus_check.json:gate.leak.leaked` = 3 tệp.

## PA-8 — Toàn bộ bằng chứng vòng lặp P5 đang KHÔNG nằm trong git (rủi ro mất dữ liệu)
- Bối cảnh (kiểm chứng 24-10): `git ls-files data/loop/rounds` = **0 file** dù thư mục nặng
  **46 MB** (r0–r7); `git ls-files tools/loop/` = **0**; `src/answer_guard.py` và
  `tests/test_loop_*.py`, `tests/test_answer_guard.py`, `tools/build_training_data.py`,
  `data/loop/testset_v1.jsonl` đều **untracked**. Nghĩa là trọng tài, gate, testset và mọi
  verdict của r0–r6 chỉ tồn tại trên đĩa, chưa có lịch sử, chưa có backup git.
  *(cập nhật 24-10 sau r8/r9: `du -sh data/loop/rounds` = **48 MB**, round đã có **r0…r9**;
  `git ls-files data/loop/rounds` và `git ls-files tools/loop` vẫn = **0** — đo lại bằng chính hai lệnh đó.)*
- Đề xuất: một commit "freeze" trên `main` (hoặc `auto/overnight` rồi merge) chứa
  `tools/loop/`, `src/answer_guard.py`, `tests/test_loop_*.py`, `data/loop/testset_v1*.{jsonl,json}`,
  `data/loop/rounds/**` (46 MB — cân nhắc `rounds/r0_pilot` và PNG trong round), kèm thông báo
  cho phiên đang dở `src/`.
- Chưa làm: em KHÔNG commit hộ công việc đang dở của phiên khác (đã ghi ở AUTONOMY_LOG #1).
- Hoàn tác: `git revert` commit freeze; không có ghi đè nào.

## PA-9 — T3: dùng tầng luật ngoài như LỚP PHỦ trên prompt cũ (không thay prompt)

- Bối cảnh (đo 24-10, `data/loop/rounds/r8/attribution_vs_r5.txt`): r8 bỏ đường từ chối khỏi prompt
  để tầng ngoài quyết ⇒ `refusal_rate` 0,69→0,28 và `PASS_CORRECT` 14→19, **nhưng** `PASS_REFUSAL`
  17→2, tức lớp "im lặng đúng khi ngoài phạm vi" gần như biến mất; hệ quả: 12 câu trả lời sai cho
  `REFUSE_OOD`/`REFUSE_MISSING_DOC` + 4 ca tiền giả sai, `pass_rate` tụt 0,31→0,21 và cổng veto.
  Phần có giá trị của lever (16 câu cứu từ over-refusal) KHÔNG đòi hỏi phải lấy đi khả năng tự im
  lặng của model.
- Đề xuất: thêm MỘT trục cấu hình (ví dụ `DEC_USE_EXTRACT_PROMPT=0|1`, mặc định `1` = hành vi r8 đã
  đo, `0` = giữ prompt `v1.3` và chỉ áp các luật ngoài) + **đăng ký ngưỡng trước** + một round mới
  (`r10`, id tăng dần, cache lạnh riêng). Đây là mở trục cấu hình mới ⇒ cần duyệt, em đã **không** viết code.
- Lợi dự kiến đo được: giữ `PASS_REFUSAL` gần mức r5 trong khi vẫn giữ luật 3 (rank) và luật 5.
- Rủi ro: thêm một tổ hợp cấu hình phải duy trì; nếu cả hai đường đều từ chối thì lever không còn ý nghĩa.
- Hoàn tác: không có gì đã đổi; tài liệu này chỉ là đề xuất.

## PA-10 — T3: thay tín hiệu "hạng truy xuất" bằng tín hiệu "căn cứ có trả lời được câu hỏi không"

- Bối cảnh (đo 24-10, `tmp/r9_run.log` + `data/loop/rounds/r8/attribution_vs_r5.txt` mục đếm luật):
  trong năm luật **chỉ hai luật bắt** (rank 25, refusal-marker), `no_evidence`/`off_topic_window`/
  `ungrounded` = 0. Nguyên nhân cấu trúc đã đo: `overlap` min 0,333 > ngưỡng 0,20 mà luật 2 là HOẶC;
  `grounding_score` ≡ 1,0 trên mọi câu đã sinh vì prompt chỉ-trích-xuất sao nguyên văn căn cứ ⇒
  tầng ngoài **mù với lớp "có căn cứ nhưng lạc đề"**, chính là lớp phình lên ở r8.
- Đề xuất: trước khi viết bất kỳ code nào, chạy **probe 0 lượt sinh** trên đĩa: với 12 ca
  `FAIL_HALLUCINATED_ON_UNANSWERABLE` của r8 và 72 câu đã trả lời, một bộ kiểm tra kiểu
  "câu hỏi có khớp với MỘT CÂU trong cửa sổ không" (cặp question↔candidate-sentence, không phải
  tập token) phân biệt được bao nhiêu ca. Nếu tỷ lệ phân biệt thấp thì bỏ hướng này ngay và ghi
  "đã đo, bị bác" — không mở round.
- Việc cần duyệt: (1) cho phép chạy probe (CPU/local, 0 Gemini); (2) nếu probe cho tín hiệu tốt,
  duyệt thiết kế luật mới + ngưỡng đăng ký trước rồi mới tới round.
- Hoàn tác: không có gì đã đổi.


## PA-11 — T4b: có mở đường QLoRA 4-bit trên model triển khai không (cài `bitsandbytes` + tải 3B)

- Bối cảnh (đo 24-10, `data/loop/diag/t4b_memory_probe.json` + `t4b_memory_probe_len.json`,
  `data/training/t4b_r5r8r9r10/manifest.json`): trên đúng card 4 GB, LoRA fp16 của Qwen2.5-0.5B
  chạy được ở dòng ≤960 token (peak 3.931,0 MiB) nhưng **vượt tổng card từ 1.024 token**
  (4.156,9 MiB) và ở 1.768 token cần 6.437,9 MiB (157% card). `gradient_checkpointing` **không**
  giảm đáng kể (3.356,0 so với 3.339,8 ở 768; 6.451,0 so với 6.437,9 ở 1.768) ⇒ bộ nhớ bị chiếm
  bởi logits của LM head. Trong khi đó **13/13 dòng train thật dài ≥ 1.016 token** (median 1.439).
  Thêm hai chặn nữa: `bitsandbytes` **chưa cài** trong `venv_train` (`find_spec` → `None`), và
  `Qwen/Qwen2.5-3B-Instruct` **không có trong cache HF** (`cached_locally: false`).
- Đề xuất: (1) cho phép cài `bitsandbytes` vào `venv_train`; (2) cho phép tải trọng số HF
  3B (~6,2 GB fp16, hoặc bản 4-bit) — kiểm tra dung lượng đĩa trước; (3) chạy lại
  `tools/diag/qlora_memory_probe.py --model Qwen/Qwen2.5-3B-Instruct` để có số THẬT thay ngoại suy.
  Chỉ khi probe lọt mới bàn tới lượt train.
- Chưa làm: KHÔNG cài thư viện, KHÔNG tải trọng số, KHÔNG train. Hoàn tác: không có thay đổi.

## PA-12 — T4b: đổi định dạng dòng SFT để vừa trần ~1.000 token của card 4 GB

- Bối cảnh (đo 24-10): như PA-11, dữ liệu do `tools/build_sft_from_round.py` sinh ra (nguồn r5/r8/
  r9/r10, 23 dòng, group-split theo tài liệu, assert chống rò rỉ đều true) **dài hơn trần bộ nhớ**
  ở mọi dòng train. Cắt dòng về 768 token nghĩa là cắt căn cứ ⇒ phá bất biến #7 ("dòng train phải
  tự chứa đáp án của nó"), nên KHÔNG được làm âm thầm.
- Đề xuất (chọn một, cần duyệt thiết kế trước khi code):
  (A) giảm số chunk trong `messages` xuống 1–2 chunk đúng Điều chứa đáp án (đo lại độ dài bằng
  tokenizer thật trước khi chốt);
  (B) đổi nhiệm vụ huấn luyện sang cặp (câu hỏi, câu trả lời ngắn có trích nguồn) thay vì nguyên
  cửa sổ — khi đó căn cứ nằm trong `prompt` ngắn, nhưng lever học được cũng hẹp hơn;
  (C) giữ nguyên dữ liệu và **không train trên máy này** (đưa lượt train sang phần cứng ≥ 8 GB).
- Rủi ro: (A)/(B) đổi phân bố dữ liệu nên không so sánh được với lượt 0,5B đã làm; (C) chặn toàn bộ
  hướng SFT cho tới khi đổi máy.
- Chưa làm: không đổi bộ dữ liệu nào, không train. Hoàn tác: không có thay đổi.


## PA-13 — T6a: cổng `refusal_rate_bounded` chuyển từ TUYỆT ĐỐI sang TƯƠNG ĐỐI (giữ 0,35 làm cảnh báo)

- Bối cảnh: `tools/loop/gate.py::compare()` hiện veto một round chỉ vì
  `candidate.refusal_rate > GATE_MAX_REFUSAL_RATE (0.35)`, bất kể baseline. Hệ quả đã thấy ở
  T3: r8/r9 bị báo KHÔNG ĐẠT một phần vì trần tuyệt đối, trong khi độ tăng refusal so với baseline
  mới là "cái giá" thật sự của lever. Khi corpus có nhiều câu ngoài phạm vi, một round tốt vẫn bị
  veto oan; ngược lại candidate 0,34 luôn lọt dù baseline chỉ 0,05.
- Đề xuất (CHỈ diff, chưa nối vào gate.py):
  1) Luật phủ quyết thành TƯƠNG ĐỐI: `candidate <= baseline + GATE_MAX_REFUSAL_RATE_DELTA`
     (mặc định 0,05). Thiếu `baseline.refusal_rate` ⇒ KHÔNG ĐO ĐƯỢC = CẤM (đúng quy tắc gate:
     rule không đo được không được tính là ĐẠT).
  2) Trần tuyệt đối 0,35 giữ nguyên nhưng hạ cấp thành CẢNH BÁO (`warnings`, in ra hội đồng,
     không nằm trong `checks` nên không kéo `passed` xuống).
  3) Thêm ngưỡng mới `GATE_MAX_REFUSAL_RATE_DELTA` vào dict `thresholds` để truy vết.
- Logic đã chứng minh ở bản tạm: `tools/diag/gate_refusal_relative_proposal.py` +
  `tests/test_gate_refusal_relative_proposal.py` (8 case: tăng≤delta→ĐẠT, tăng>delta→BỊ,
  thiếu baseline→CẤM, candidate giảm→ĐẠT, 0,38>trần nhưng tương đối ĐẠT kèm warning, delta chỉnh
  được, mặc định 0,35, retrieval-phase không thêm gì).
- Diff dự kiến vào `tools/loop/gate.py`:

```diff
@@ compare() — khai báo ngưỡng + danh sách cảnh báo
     fab_delta = _env_float("GATE_MAX_FABRICATION_DELTA", 0.0)
     missed_delta = _env_int("GATE_MAX_MISSED_REFUSAL_DELTA", 0)
     max_refusal = _env_float("GATE_MAX_REFUSAL_RATE", 0.35)
+    max_refusal_delta = _env_float("GATE_MAX_REFUSAL_RATE_DELTA", 0.05)
     min_family_n = _env_int("GATE_MIN_FAMILY_N", 8)
 
     checks: list[dict] = []
+    warnings: list[dict] = []
 
     def add(name: str, ok: bool, detail: str) -> None:
         checks.append({"rule": name, "ok": bool(ok), "detail": detail})
 
+    def warn(name: str, detail: str) -> None:
+        warnings.append({"rule": name, "severity": "warning", "detail": detail})
```

```diff
@@ compare() — luật 4 (thay toàn bộ khối cũ)
-    # 4. cái giá từ chối oan có trần
-    cr = candidate["refusal_rate"]
-    if cr is not None:
-        add(
-            "refusal_rate_bounded",
-            cr <= max_refusal,
-            f"candidate={cr} baseline={baseline['refusal_rate']} (trần {max_refusal})",
-        )
+    # 4. cái giá từ chối oan: TEST TƯƠNG ĐỐI (phủ quyết) + trần tuyệt đối (chỉ cảnh báo)
+    cr = candidate["refusal_rate"]
+    br = baseline["refusal_rate"]
+    if cr is not None:
+        if br is not None:
+            add(
+                "refusal_rate_not_increased",
+                cr <= br + max_refusal_delta,
+                f"candidate={cr} baseline={br} delta={_delta(cr, br)} "
+                f"(ngưỡng tương đối +{max_refusal_delta})",
+            )
+        else:
+            add(
+                "refusal_rate_not_increased",
+                False,
+                f"KHÔNG ĐO ĐƯỢC: candidate={cr} nhưng baseline thiếu refusal_rate "
+                "(round đối chiếu chạy bằng verify cũ/khác pha) — chạy lại baseline rồi mở cổng",
+            )
+        if cr > max_refusal:
+            warn(
+                "refusal_rate_absolute_ceiling",
+                f"candidate={cr} vượt trần tuyệt đối {max_refusal} — cảnh báo cho hội đồng, "
+                "không tự phủ quyết",
+            )
```

```diff
@@ compare() — payload trả về
         "passed": passed,
         "n_common_items": len(common_ids),
         "thresholds": {
             ...
             "GATE_MAX_REFUSAL_RATE": max_refusal,
+            "GATE_MAX_REFUSAL_RATE_DELTA": max_refusal_delta,
             "GATE_MAX_RECALL_DROP": _env_float("GATE_MAX_RECALL_DROP", 0.02),
             "GATE_MIN_FAMILY_N": min_family_n,
         },
         "checks": checks,
+        "warnings": warnings,
         "family_deltas": fam_lines,
```

```diff
@@ main() — in báo cáo
     for check in result["checks"]:
         print(f"  [{'ĐẠT ' if check['ok'] else 'VI PHẠM'}] {check['rule']:34s} {check['detail']}")
+    for w in result.get("warnings", []):
+        print(f"  [CANH BAO] {w['rule']:34s} {w['detail']}")
```

- Rủi ro / lưu ý: delta 0,05 là Ngưỡng ĐĂNG KÝ TRƯỚC; nếu hội đồng muốn siết/nới thì chốt con số
  này TRƯỚC khi mở round, không chỉnh sau khi thấy số. Đổi tên rule từ `refusal_rate_bounded` sang
  `refusal_rate_not_increased` làm các báo cáo gate cũ (JSON trên đĩa) không còn khớp tên — chỉ ảnh
  hưởng hiển thị, không ảnh hưởng verdict đã ghi. round_summary/gate không đổi chữ ký trọng tài.
- Chưa làm: KHÔNG sửa `gate.py`. Hoàn tác: không có thay đổi; chỉ có module tạm + test tạm mới.
- Việc cần duyệt: (1) chốt delta mặc định 0,05; (2) cho phép áp diff vào `gate.py`; (3) xác nhận
  việc đổi tên rule (nếu muốn giữ tên cũ `refusal_rate_bounded` thì báo trước để không tách nhánh
  báo cáo).
- **Test đã viết sẵn, chạy ngay khi diff được duyệt (bổ sung 25-10, đợt kiểm thử T6):**
  `tests/test_t6_gate_refusal_and_regression.py` (**28 test**, toàn repo **1.124 passed** —
  `tmp/pytest_t6_final.txt`). Phủ mục 1–6 đề bài: 0,69/0,72 ĐẠT + cảnh báo trần không phủ quyết;
  0,80/0,72 BỊ; ba điểm biên (+0,0499/+0,05/+0,0501); baseline rỗng hoặc `n=0` ⇒ CẤM với thông báo
  "KHÔNG ĐO ĐƯỢC"; ghim 6 luật còn lại bằng test biên từng luật; cổng từ chối mở khi chữ ký trọng tài
  hoặc cấu hình hai round lệch. Hàm `apply_to_gate_result()` trong
  `tools/diag/gate_refusal_relative_proposal.py` áp luật mới lên **chính JSON cổng đã công bố**.
- **Số thật khi áp luật mới (đính chính đề bài, không hạ mức đỏ):** r5-vs-r1 **lật sang ĐẠT**
  (0,69 vs 0,72 ⇒ ĐẠT + cảnh báo vượt trần 0,35); **r5-vs-r3 vẫn KHÔNG ĐẠT** vì delta refusal
  **+0,08 > 0,05** và fabrication 0,0256→0,0323 tăng; r3-vs-r1 vẫn đỏ vì
  `no_new_hallucinated_refusal` (2→3). Cổng retrieval r4-vs-r2 giữ nguyên ĐẠT. Nói cách khác PA-13
  **không** tự nó làm round âm gần nhất thành đạt.
- Mutation chứng minh test có hiệu lực: M1 đổi dấu `<=`→`<` và M3 bỏ kiểm chữ ký trọng tài **đều bị bắt**
  (10/10, `tmp/mutation_check_t6_tests.log`; chạy trên bản sao `tmp/mut6_tree/` nên `gate.py` thật
  không bị chạm).


## PA-14 — T3: đường Gemini KHÔNG có nhánh `ENABLE_DECOUPLED_REFUSAL` (lever im lặng không chạy)

- Bối cảnh (đo 24-10, `docs/reports/test_T3.md` mục 4.1): `GeminiGenerator.build_prompt`
  (`src/generator.py:597`) không đọc cờ T3; prompt vẫn chứa chuỗi canonical và lời mời từ chối.
  `GeminiGenerator._cache_key` (`src/generator.py:765`) dùng `PROMPT_VERSION` **tĩnh**, trong khi
  QwenGenerator (`src/generator.py:1176`) dùng `effective_prompt_version()`. Test đặc tả hiện
  trạng: `tests/test_t3_guardrails.py::TestPromptHasNoRefusalAffordance::test_DUONG_GEMINI_hien_trang_khong_co_nhanh_T3_dac_ta_hien_trang`.
  Vòng lặp P5 chạy Qwen nên r8/r9 KHÔNG bị ảnh hưởng; rủi ro là người dùng chuyển sang Gemini
  tưởng T3 đang bật.
- Hai lựa chọn (chờ duyệt, chưa làm):
  (a) Nối T3 vào Gemini: `build_prompt` dùng `EXTRACT_ONLY_HEAD` khi cờ bật; `_cache_key` dùng
      `effective_prompt_version()`. Kèm test cặp off/on y như Qwen + golden prompt Gemini OFF.
  (b) Không nối; ghi rõ trong `data/loop/README.md` + README rằng T3 chỉ áp cho đường Qwen.
- Đề xuất bảo thủ: (b) — không đổi hành vi đường Gemini khi chưa có phép đo nào trên đường đó.
- Rủi ro nếu chọn (a): prompt Gemini đổi ⇒ cache Gemini cũ vô hiệu; cần đo lại refusal trên
  đường Gemini trước khi tuyên bố lever có tác dụng.
- Hoàn tác: không có thay đổi nào đang áp dụng (chỉ test đặc tả).


## PA-15 — T3: `DEC_MAX_UNSUPPORTED = 1` là dead code; trần hiệu dụng thực tế = 0

- Bối cảnh (đo 24-10): `Report.fabricated` (`src/answer_guard.py:156-157`) trả
  `bool(self.unsupported)`; luật 4 của `refusal_policy` dựa trên `fabricated`, nên **một** thực
  thể chưa căn cứ đã bị chặn. Đặt `DEC_MAX_UNSUPPORTED=9` vẫn chặn (test
  `test_max_unsupported_hien_trang_bi_luat_fabricated_che_khu_dac_ta_hien_trang`). Nghĩa là con
  số 1 đã đăng ký trong `data/loop/README.md` không bao giờ được dùng — hành vi đang **nghiêm
  hơn** văn bản đăng ký.
- Hai lựa chọn (chờ duyệt):
  (a) Sửa luật 4 dùng đúng trần: `n_unsupported > th["max_unsupported"]` thay vì `fabricated`
      (chạm `src/refusal_policy.py`; ngưỡng đã công bố ⇒ phải đo lại r8/r9 nếu muốn so sánh);
  (b) Giữ hành vi, **đăng ký lại** trần hiệu dụng = 0 trong README (không đổi code, chỉ sửa tài
      liệu + báo cáo cũ đã công bố con số 1).
- Đề xuất bảo thủ: (b) — không đổi hành vi phòng thủ đang chạy; chỉ sửa tài liệu cho khớp số đo.
- Rủi ro nếu chọn (a): nới guard (1 thực thể bịa lọt) — ngược mục tiêu chống bịa; chỉ nên làm nếu
  có phép đo cho thấy guard đang chặn oan câu trả lời đúng.
- Hoàn tác: không có thay đổi nào đang áp dụng (chỉ test đặc tả hiện trạng).


## PA-16 — T2: nối cổng an toàn `plan_index_write` vào đường build thật (`ingest.py`)

- Bối cảnh (đo 24-10, test T2): hàm thuần `plan_index_write` trong
  `tools/diag/check_corpus.py:264` **từ chối** ghi đè thư mục đích đã tồn tại (8 test trong
  `tests/test_corpus_rebuild.py::TestDataSafety`). NHƯNG đường build thật `ingest.py:24-27` vẫn
  `reset=True` → `shutil.rmtree(persist_dir)` **không hỏi**. Lần build `chroma_db_vie/` ngày 24-10
  trỏ vào thư mục mới rỗng nên không mất gì; lần sau gõ nhầm `CHROMA_PERSIST_DIR=./chroma_db`
  sẽ xóa index đang dùng. Trọng tài không liên quan (không đổi chữ ký).
- Đề xuất (a) — bảo thủ, tối thiểu (khuyến nghị): thêm cờ env **mặc định TẮT** `INGEST_ALLOW_RESET`
  vào `ingest.py`; nếu đích đã có dữ liệu và cờ chưa bật ⇒ `SystemExit` in đường dẫn tuyệt đối.
  Diff dự kiến:

```diff
--- a/ingest.py
+++ b/ingest.py
@@ def run_ingestion(...):
     if reset:
         if os.path.isdir(persist_dir):
+            if os.listdir(persist_dir) and os.getenv("INGEST_ALLOW_RESET") != "1":
+                raise SystemExit(
+                    f"[an toàn] '{os.path.abspath(persist_dir)}' đã có dữ liệu — từ chối xóa. "
+                    "Đặt INGEST_ALLOW_RESET=1 nếu THẬT SỰ muốn build lại toàn bộ index này."
+                )
             shutil.rmtree(persist_dir)
             print(f"\n[1/4] Đã xóa ChromaDB cũ tại '{persist_dir}' (reset toàn bộ index).")
```

  Kèm: cập nhật lệnh trong README/`docs/reports/T2.md` thành
  `INGEST_ALLOW_RESET=1 python ingest.py` cho lần build chủ đích; thêm 2 test cặp
  (thiếu cờ ⇒ từ chối, có cờ ⇒ cho phép) nếu chuyển logic thành hàm thuần.
- Đề xuất (b) — nếu không muốn đổi `ingest.py`: giữ nguyên, ghi rõ trong README "ingest.py xóa
  toàn bộ thư mục đích; luôn kiểm `CHROMA_PERSIST_DIR` trước khi chạy".
- Đề xuất bảo thủ: **(a)** — đúng bài học "đích đã tồn tại thì từ chối", mặc định TẮT nên không
  đổi hành vi trừ khi người dùng chủ động bật.
- Hoàn tác: xóa 2 dòng `if ... INGEST_ALLOW_RESET` (chưa áp dụng gì).


## PA-17 — T2: re-anchor `gold_sentence` cho 292 item regression trước khi chấm lại round

- Bối cảnh (đo 24-10, `corpus_check.json:gold_coverage`): index mới mất neo **389/797 = 48,81%**
  (ngưỡng đăng ký 2% ⇒ ĐỎ). Trong đó **97 item đã mất neo ngay trên index CŨ** (12,17%),
  **292 item là regression riêng do rebuild** (36,64%; danh sách id đầy đủ ở
  `corpus_check.json:gold_coverage.paired.regressed_ids`, 292 id không trùng). Chẩn đoán:
  375/389 là "near" (nội dung còn, câu chữ OCR khác), 14 là "absent" (1,76%).
- Vì sao phải re-anchor: `gold_sentence` là neo **nguyên văn** dùng để đo gold@k của round; giữ
  nguyên thì mọi round trên corpus mới sẽ bị tính "trượt" vì lý do OCR viết khác, không phải vì
  truy xuất kém. Re-anchor là thay đổi DỮ LIỆU ĐO ⇒ cần duyệt, và phải làm **trước** khi chấm lại.
- Đề xuất (a) — bảo thủ (khuyến nghị): tạo tệp **MỚI** `data/loop/testset_v1_reanchored.jsonl`
  (KHÔNG ghi đè tệp gốc):
  1) với từng id trong `regressed_ids`, tìm chunk mới có overlap token cao nhất với `gold_sentence`
     cũ; nếu overlap ≥ 0,60, thay `gold_sentence` bằng **câu nguyên văn** trong chunk đó (câu có
     overlap cao nhất), giữ nguyên `id`, `family`, câu hỏi, `required_entities`;
  2) lưu bản đồ `old → new` + overlap vào `data/loop/diag/reanchor_map.json`;
  3) kiểm: 811 id duy nhất, không thêm/bớt item, `gold_sentence` không rỗng ở đúng những item
     trước đây có; chạy lại `check_corpus.py` với `--testset` mới ⇒ mục 9 phải ≤ 2%;
  4) xác nhận bất biến #6: không có đường runtime nào đọc `gold_sentence`
     (`grep -rn "gold_sentence" src tools/loop | grep -v testset.py`).
- Đề xuất (b): không re-anchor; chấp nhận mọi so sánh round trên corpus mới là **baseline mới**
  (không so cặp item với r0–r11), và ghi rõ mục 9 đỏ trong mọi báo cáo.
- Đề xuất bảo thủ: **(a)** nhưng chỉ sau khi người dùng duyệt; không tự sửa testset trong phiên tự trị.
- Rủi ro nếu chọn (a): re-anchor có thể vô tình "làm đẹp" số (chọn câu dễ trúng) ⇒ bắt buộc giữ
  nguyên phân bố family và công bố cả tỉ lệ near/absent trước–sau; mọi round chấm trên testset
  mới là **nguồn số mới**, không được ghép với số cũ.
- Hoàn tác: xóa 2 tệp mới (`testset_v1_reanchored.jsonl`, `reanchor_map.json`); tệp gốc không đổi.

## PA-18 — T5: ba quyết định thiết kế trước khi nghiệm thu (fallback, header-trong-context, wire/build)

- Bối cảnh (đo 24-10, `docs/reports/test_T5.md`): 68 test T5 xanh, mutation 10/10 bắt được và
  hoàn nguyên byte-identical. Hai điểm **chưa khớp câu chữ đề bài**:
  1) mục 5 yêu cầu reranker lỗi thì "lùi về thứ tự RRF + log cảnh báo"; thiết kế T5 đã đăng ký
     trước trong `data/loop/README.md` lại **cấm lùi thầm** và hiện `src/pipeline.py` ném
     `RerankerUnavailable` lên trên;
  2) mục 10 yêu cầu index mới ở thư mục khác, nhưng `src/contextual_header.py` chưa được nối
     vào `ingest.py` và chưa build index T5b thật (chờ PA-1/PA-16).
- Đề xuất (a) — **fallback tuỳ chọn, mặc định TẮT** (khuyến nghị):
  thêm cờ `RERANKER_FALLBACK` (mặc định `0`) đọc trong `src/reranker.py`; khi BẬT, pipeline
  bắt `RerankerUnavailable`, in cảnh báo `[Reranker] …`, ghi manifest `fallback_used=true` và
  trả **đúng danh sách trước rerank** (thứ tự RRF+bonus), không rơi xuống `similarity_search`.
  Diff dự kiến trong `src/pipeline.py`:

```diff
--- a/src/pipeline.py
+++ b/src/pipeline.py
@@             except RerankerUnavailable:
                 # Không để reranker rơi vào nhánh lùi về similarity_search ở dưới: một
                 # round đo nhầm lever còn tệ hơn round dừng tường minh.
-                raise
+                if not reranker_fallback_enabled():
+                    raise
+                print(f"[Reranker] Cảnh báo: {exc} — lùi về thứ tự RRF trước rerank "
+                      "(RERANKER_FALLBACK=1).")
+                self.last_rerank_call = {"fallback_used": True, "error": str(exc)}
+                return docs[:k]
```

  Kèm 2 test cặp: cờ TẮT ⇒ ném lỗi như hiện tại (nguyên văn); cờ BẬT ⇒ trả đúng thứ tự
  trước rerank, có log, **không** gọi `similarity_search`, manifest ghi `fallback_used=true`.
  Không đổi ngưỡng/round; không ảnh hưởng đường đang chạy vì mặc định TẮT.
- Đề xuất (b) — **header có/không đi vào ngữ cảnh generator**: thiết kế hiện tại đặt header
  trong `page_content` (giống header cũ đang chạy), nên `contexts` gửi generator có header;
  `sources`/citation vẫn lấy từ metadata. Giữ nguyên (khuyến nghị) hoặc tách header sang
  metadata riêng — phương án sau phải sửa `describe_document`, prompt và mọi nơi đọc
  `page_content`, và phải đo lại vì đổi đầu vào generator. Chưa làm.
- Đề xuất (c) — **wire + build index T5b** (chỉ sau khi duyệt PA-1/PA-16):
  trong `ingest.py`, sau bước chunk và trước embed, nếu `ENABLE_CONTEXTUAL_HEADER=1` thì gọi
  `apply_contextual_headers(...)` với `titles` từ metadata tệp và `chapters` từ
  `chapters_for_chunks(full_text, chunks)`; đích bắt buộc qua `ensure_separate_index_target`
  (ví dụ `./chroma_db_headers`), **không** ghi `chroma_db`/`chroma_db_vie`. Sau đó mới chạy
  retrieval-only 811 item (r11/r12 của T5a, task #34/#35) để có số gold@6/F1 theo family.
- Đề xuất bảo thủ: duyệt (a) dạng cờ TẮT; giữ (b) như thiết kế; hoãn (c) tới khi chốt corpus.
- Hoàn tác: (a) xóa cờ + 5 dòng trong nhánh `except`; (b) không có thay đổi nào; (c) chưa áp
  dụng gì, chỉ build vào thư mục mới và có thể xóa thư mục đó.
- **Còn treo để nghiệm thu T5:** chạy lại gold@6 cấu hình TẮT trên 811 item và so với round đã
  đóng (đề bài yêu cầu); hiện chỉ có golden 30 item `pipeline.run`.

## PA-19 — T5a: chi phí reranker vượt ngưỡng 60 phút, r12 CHƯA chạy (24-10 23:20)

> **ĐÃ GIẢI QUYẾT 25-10 03:0x — kèm ĐÍNH CHÍNH 04:1x (không cần duyệt nữa):** đo lại trên **GPU**
> bằng `venv_gpu/` riêng, giữ nguyên model/`max_length=512`/pool/batch đã đăng ký ⇒ median **2,05 s/item
> riêng tầng rerank**. Lúc cho phép chạy, ngoại suy "27–30 phút < 60" đã **bỏ sót truy xuất nền**
> (2,78 s/item); đo thật r12 = **≈66 phút**, tức **VƯỢT** ngưỡng 60 phút (xem `docs/reports/T5.md`
> §2.6 đính chính). r12 vẫn **đã chạy và chấm xong** (811/811, 0 lỗi) ⇒ dùng được để kết luận âm.
> Các phương án (a)/(b)/(c)/(d) dưới đây **hết hiệu lực**; vấn đề còn lại của 5a là **PA-25**.

**Số đo (nguồn `data/loop/diag/reranker_cost_only.json`, đo bổ sung ngoài thiết kế):**
nạp riêng reranker 17,0 s; chấm 20 cặp/item median 18,47 s, mean 18,44 s, p95 20,10 s trên
30 item r11 (max_length 512, batch 4, CPU). Ngoại suy 811 item = **249,3 phút (4,15 giờ)**,
chưa tính nạp pipeline. Probe chính thức (pipeline bge-m3 + reranker) chạy ~45–50 phút mới
nạp xong hai model, **chưa chấm được cặp nào**; RAM trống sau khi nạp reranker chỉ 1.793 MiB
⇒ không giữ đồng thời hai model. Theo luật đăng ký trước ("dừng nếu ngoại suy >60 phút"),
**r12 không chạy**. Không sửa model/device/max_length/batch/model để "cho chạy được".

**Cần duyệt một trong các hướng:**
| | Phương án | Đánh đổi |
|---|---|---|
| a | Chạy r12 qua đêm trên CPU, bỏ ngưỡng 60 phút | ~5 giờ; có thể fail giữa chừng |
| b | Đóng ứng dụng nền để trống ≥6 GB rồi chạy lại probe chính thức | **không đổi thiết kế**; cần người dùng đóng ứng dụng |
| c | Hạ `RERANKER_MAX_LENGTH` 512 → 256 | đổi thiết kế đã đăng ký; phải đăng ký lại ngưỡng |
| d | Đổi reranker nhỏ hơn (`bge-reranker-base`) | đổi model đã đăng ký; mất chất lượng |
| e | Chuyển GPU (`venv_train`, torch CUDA) | đổi device đã đăng ký; 4 GB VRAM có thể không đủ |
| f | Bỏ T5a, giữ cờ TẮT | không có kết quả hiệu quả; tiết kiệm thời gian |

Khuyến nghị bảo thủ: **(b) trước** (không đổi thiết kế); nếu vẫn >60 phút thì **(a) hoặc (f)**.
Không có thay đổi code nào được áp dụng cho các phương án này.

**Đo bổ sung 24-10 23:11 — phương án (c) max_length 256 (NGOÀI thiết kế đăng ký):**
cùng script, 5 item × 20 cặp, `RERANKER_MAX_LENGTH=256`: nạp 15,17 s; **median 9,294 s/item**
(mean 9,248, p95 9,407) so với 18,473 s ở 512 ⇒ giảm ~50%, nhưng ngoại suy 811 item vẫn
**125,0 phút (2,08 giờ)**, chưa tính pipeline. RAM trống sau nạp 1.646,6 MiB. Kết luận:
**(c) một mình vẫn vượt luật 60 phút**; nếu chọn (c) phải đăng ký lại ngưỡng và vẫn cần ~2 giờ
chạy. Nguồn: `data/loop/diag/reranker_cost_only_256.json` (5 item nên chỉ là ước lượng thô).

## PA-20 — trọng tài: required_entities số ngắn khớp oan trong mã khác ("1" khớp "B1"/"2021") (24-10 23:09)

**Bằng chứng (T1(b), không đổi verdict):** `C145524027648409` trả lời **sai** (hỏi ELO của
"Áp dụng kiến thức nền tảng…" — chunk 329 ghi **ELO 1**, model trả **ELO 9**), nhưng
`_answer_covers_gold` trả **True** vì `required_entities=['1']` và `_number_in` khớp số "1"
nằm trong "B1"/"2021". Nếu chỉ gỡ cờ proper của PA-2 mà không sửa chỗ này, ca sai sẽ được
**PASS_CORRECT oan** (đã gọi trực tiếp hàm để kiểm, không sửa file).

**Đề xuất diff** (`tools/loop/verify.py` — REFEREE_FILES, KHÔNG áp dụng):
```diff
@@ def _entity_in_answer(entity: str, answer: str) -> bool:
 def _entity_in_answer(entity: str, answer: str) -> bool:
+    ent = (entity or "").strip()
+    if re.fullmatch(r"\d{1,2}", ent):
+        # Số ngắn (1–2 chữ số) phải đứng độc lập: không khớp trong "B1", "2021",
+        # "ELO 10" khi cần "1". Giữ nguyên _number_in cho các trường hợp khác.
+        return re.search(rf"(?<![\w]){re.escape(fold(ent))}(?![\w])", fold(answer)) is not None
     if re.fullmatch(r"[\d.,\s]+đ?%", entity or "") or re.search(r"\d", entity or ""):
         return _number_in(answer, entity)
     return fold(entity) in fold(answer)
```
- Test hồi quy đề xuất: `required_entities=['1']` + đáp án "ELO 9 … B1 … 2021" ⇒ **False**;
  "ELO 1 …" ⇒ True; `['2024']` + "2024-2025" ⇒ True; `['2570']` + "2570/QĐ-DHAG" ⇒ True.
- Hệ quả: đổi chữ ký trọng tài; phải chấm lại mọi round đã đóng. Đề xuất làm **cùng lúc với
  PA-2** thành "referee v2" và công bố cả số cũ lẫn số mới.
- Vì sao không sửa `_number_in` toàn cục: nó đang phục vụ nhiều loại thực thể (mã, ngày, tiền);
  đổi toàn cục có thể làm đỏ các round cũ mà chưa lượng hóa được. Bản đề xuất chỉ thắt đúng ca
  số ngắn trong `_answer_covers_gold` — phạm vi hẹp, dễ test.

**Ước lượng tác động (chỉ đọc, chưa đổi gì):** áp bản strict lên 4 round đã đóng —
r5 **1/14** PASS_CORRECT bị hạ, r10 **2/16** bị hạ, r8/r9 **0**; các ca bị hạ đều là số ngắn
khớp trong chuỗi khác (ví dụ `required=['2']` khớp "2026-2028"; `['20']` khớp "2026").
Ba ca này **đã chấm tay ở mục dưới**: không phải cả 3 là "PASS oan", nên **không áp strict một
mình**; nếu duyệt, phải sửa metadata trước và công bố lại bảng r5/r8/r9/r10 (r5 là baseline
của T3/T4). Vì có thể đổi kết luận các round cũ, đây là lý do chính để **không tự sửa**.

**Chấm tay 3 dòng PASS bị strict hạ (24-10 23:20) — KHÔNG phải cả 3 là "PASS oan":**
| round | id | required | đọc tay | kết luận |
|---|---|---|---|---|
| r5, r10 | T111158251954171 | `['2']` | gold_sentence kết thúc bằng số trang "2"; câu trả lời không có số 2 độc lập | strict hạ PASS→INCOMPLETE, nhưng **metadata vàng kém** (số trang), không phải câu trả lời sai chắc chắn |
| r5 | C162319281103737 | `['20']` | verdict là FAIL_OVERREFUSAL (câu trả lời từ chối) | coverage đổi nhưng **verdict không đổi** — không có tác động |
| r10 | C162319281103737 | `['20']` | gold_sentence là mẫu "ngày tháng năm 20…"; model điền "2026" | strict hạ PASS→INCOMPLETE, nhưng **"2026" có thể là điền hợp lệ cho mẫu "20…"** — chưa đủ căn cứ nói PASS oan |

⇒ **Không nên áp diff strict một mình.** Gốc rễ là `required_entities` ngắn/kém (số trang lẫn
vào gold; "20" là tiền tố năm). Hướng an toàn hơn:
1. Làm sạch metadata: bỏ required_entities là số trang/rác; đổi `['1']` thành `['ELO 1']`,
   `['20']` thành giá trị đầy đủ nếu mẫu yêu cầu; **cần duyệt vì đổi testset**.
2. Nếu vẫn muốn sửa `verify.py`, phải kèm test đúng 4 ca: C1455 (phải FAIL), T1111 (không được
   coi là PASS nếu gold chỉ là số trang), C1623-r10 (phải xử lý mẫu "20…" đúng), và ELO 10/2024.
3. Audit tái lập: `tools/diag/referee_strict_number_audit.py` → `data/loop/diag/referee_strict_number_audit.json`
   (chỉ đọc; 5 test trong `tests/test_referee_strict_number_audit.py`).

## PA-21 — 5b: neo `gold_chunk_id` cũ KHÔNG ánh xạ sang corpus T2, không chấm được header trên `chroma_db_vie` (24-10 23:35)

**Bối cảnh:** T2 đã build `chroma_db_vie` (342 chunk) nhưng chưa kích hoạt (PA-1). Yêu cầu T5b
là "làm SAU T2 để không đo trên corpus sắp thay". Khi kiểm tra khả năng chấm trên corpus mới,
neo vàng của testset cũ không còn trỏ đúng chunk:

| Phép kiểm (797 item kiểm được; 14 item không có `gold_sentence`) | `chroma_db` cũ | `chroma_db_vie` mới |
|---|---:|---:|
| `gold_sentence` còn khớp (fold, đúng luật `testset.py`) | 700 (87,83%) | 408 (51,19%) |
| Mất neo | 97 (12,17%) | **389 (48,81%)** |
| Mất **thêm** do rebuild | — | **292 (36,64%)** |
| Trong 389 ca mất: gần nội dung (overlap ≥0,6) / mất thật | — | 375 / 14 |

Nguồn: `data/loop/diag/corpus_check/corpus_check.json → gold_coverage` (chỉ đọc).

**Vì sao không tự sửa:** ánh xạ lại gold là **đổi dụng cụ đo** (testset), không phải sửa code
sản phẩm. Nếu tự chọn quy tắc, mọi so sánh r0–r5 sẽ đổi nghĩa và không thể quy lỗi cho header.
Ngoài ra 14 item mất thật + 375 item chỉ "gần nội dung" không thể neo lại bằng khớp chuỗi —
cần người quyết định loại khỏi mẫu số hay chấp nhận neo xấp xỉ.

**Đề xuất (chọn một):**
| | Phương án | Đánh đổi |
|---|---|---|
| a | **Giữ corpus cũ cho mọi so sánh đóng**; 5b đo cơ chế trên `chroma_db` cũ (đã làm, r13) | hợp lệ ngay; chưa nói được header trên corpus T2 |
| b | Neo lại gold tự động: khớp `gold_sentence` duy nhất trên corpus mới; ca nhập nhằng chọn cùng nguồn + gần offset nhất; còn lại **loại khỏi mẫu số** và công bố | đổi mẫu số; phải chấm lại r0–r5 (PA-1) |
| c | Neo tay 389 ca mất neo | tốn người; chính xác nhất |
| d | Build testset mới cho corpus T2 từ đầu | sạch nhất; tốn nhiều người + không so sánh được với lịch sử |

Khuyến nghị bảo thủ: **(a) cho hôm nay** (đã có r13, không đổi dụng cụ đo), và chỉ chuyển sang
(b) khi user duyệt PA-1. Không có file testset nào bị sửa; `chroma_db_vie` chưa được kích hoạt.

**Ghi chú vận hành:** index header cũ `chroma_db_headers_old` được build từ bản sao
`chroma_db` (361 chunk, id/metadata/thân chunk giữ nguyên); index gốc không bị ghi. Báo cáo:
`data/loop/diag/header_index_old_build.json`.

## PA-22 — manifest round không ghi thư mục index ⇒ r13 không phân biệt được với r11 bằng `settings` (25-10 02:15)

**Bằng chứng:** `tools/diag/bonus_paired.py --baseline r11 --candidate r13` báo
`settings khác nhau giữa hai round: {}` dù r13 đọc `chroma_db_headers_old` còn r11 đọc `chroma_db`.
Một biến chỉ chứng minh được bằng **nội dung** (4.866/4.866 context r13 mang header mới — xem
`docs/reports/T5.md` §2.5). Mọi round sau đổi index (PA-1, 5b trên corpus T2) sẽ gặp lại lỗ này.

**Vì sao không tự sửa:** `tools/loop/run_round.py` là dụng cụ đo; luật tự trị = ghi diff chờ duyệt.
Thêm khoá vào `settings` **không** đổi chữ ký trọng tài (đã kiểm: `REFEREE_FILES` trong
`tools/loop/verify.py:45` chỉ băm `verify.py`, `src/answer_guard.py`, `src/text_utils.py`), nhưng làm `bonus_paired`/`gate` thấy một khoá mới khác nhau
giữa round cũ (thiếu khoá) và round mới.

**Diff đề xuất** (`tools/loop/run_round.py`, khối `settings`, cạnh `generation_cache_dir`):

```diff
             "generation_cache_dir": os.getenv("GENERATION_CACHE_DIR", "./.generation_cache"),
+            # Index truy xuất đang đọc: thiếu khoá này thì round đổi index (r13) trông
+            # y hệt round nền trong `settings` (PA-22).
+            "chroma_persist_dir": os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"),
             # Chữ ký của dụng cụ đo. Hai round chỉ so được nhau khi cùng chữ ký.
             "referee": referee_fingerprint(),
```

Kèm 1 test: đặt `CHROMA_PERSIST_DIR=./x` ⇒ `settings["chroma_persist_dir"] == "./x"`.
Round đã đóng (r0–r13) **không** sửa hồi tố; r13 ghi chú bằng tài liệu.

## PA-23 — bốn dòng trong bảng tự chấm điểm đã cũ so với số mới (25-10 02:50)

`docs/bao_cao/danh_gia_tong_quan_2026-10-23.md` §5 vẫn ghi: "evidence-selection và reranker chưa có",
"thiếu bootstrap CI", "18,6% từ có dấu", "563 test xanh". Cả bốn đã được đo lại/làm xong sau đó
(T3, T5, T2, T6d, 967 test). **Đã thêm khối ĐÍNH CHÍNH 25-10 ngay dưới bảng** (không đổi dòng gốc),
nhưng **điểm thành phần KHÔNG tự đổi** vì đó là phán chấm điểm của người duyệt — đúng quy tắc
"ngưỡng/điểm đã ghi trước thì không tự chỉnh".

**Đề xuất:** user quyết có nâng điểm nào không. Gợi ý chỉ để tham khảo, chưa áp dụng:
`Chất lượng thực nghiệm` 7,0 (đã có CI + quy lỗi + 3 round kiểm chứng âm công bố) và
`Kỹ thuật phần mềm` 8,5 (967 test) là hai dòng đáng xem lại; `Chất lượng dữ liệu nền` 4,5 **giữ nguyên**
cho tới khi PA-1 kích hoạt `chroma_db_vie`, vì hệ thống đang chạy thật vẫn đọc corpus 18,6% dấu.
Nếu đổi điểm, phải tính lại tổng có trọng số (công thức ở dòng cuối §5) và sửa lại cả câu
"đính chính 7,4 → 7,2".

## PA-24 — T7: danh sách `tmp/` đề xuất XOÁ (chưa xoá gì; cần anh duyệt) (25-10 03:25)

Kiểm kê bằng script chỉ-đọc: một file được coi là "dẫn chứng" nếu đường dẫn `tmp/<tên>` xuất hiện
trong `docs/**/*.md`, `ROADMAP.md`, `README.md` hoặc `data/loop/README.md`. Tổng `tmp/` = **92,1 MB**
(104 mục). **Không xoá gì khi chưa có duyệt.**

**A. GIỮ — 45 mục được dẫn trong báo cáo** (không đề xuất xoá), gồm:
`loop_gen_cache{,_r3,_r5,_r5b,_r6,_r7,_r8,_r9,_r10}` (cache lạnh của từng round, dẫn trong ROADMAP +
`data/loop/README.md`), `mutation_check*.py` + `mutation_check_t5.log`, `probe_*` được ROADMAP dẫn
(`probe_bonus_regressions.py`, `probe_guard_scope.py`, `probe_overrefusal.py`, `probe_prefix_cache.py`
+ `probe_prefix_cache_result.json`, `probe_prompt_window.py`, `probe_r6_attribution.py`,
`probe_round_attribution.py`, `probe_t3_table.py`), `pytest_t{2,3,5}_*.txt`, `pytest_tt0_tt3_final.txt`,
`r{8,9,10}_run.log`, `r{5b,6,7}_driver.sh`, `t2_*.log`, `t2_p_1054_1.png`, `t3_baseline_head/`,
`t5_cost_probe_20261024.log`, `t5b_r13_header.log`, `vram_r12_probe.log`, `r12_gpu_probe.log`, `r12_run.log`.

**B. GIỮ thêm (script KHÔNG bắt được vì dẫn gián tiếp / đang dùng của phiên này):**
`r11_run.log` + `r11_resume.log` (log của round nền r11, r11 được dẫn khắp nơi),
`t1_b_resume_2410_0925.log` (log resume T1(b) 12→25 id, số chốt nằm ở
`data/loop/diag/b_gemini_top6/summary_dedup_25.json`), `venv_gpu_install.log`, `vram_r12_run.log`
(đang ghi), `repair_ids.py` + `backup_repair/` (liên quan sửa id round — xem nhóm C),
`t3_golden_head.json` / `t3_golden_now.json` (ảnh chụp golden dùng bởi mutation check T3).

**Bổ sung 25-10 11:5x (sau khi viết `test_T4.md` / `test_T6.md` / `test_final.md`):** GIỮ thêm
`mutation_check_t4.py` + `mutation_check_t4.log`, `mutation_check_t6.py` + `mutation_check_t6.log`,
`pytest_t4t6_final.txt` — ba báo cáo mới dẫn trực tiếp các file này, tức chúng thuộc diện "dẫn chứng"
của nhóm A; không đưa vào danh sách xoá. Bổ sung 11:51: GIỮ `mutation_check_t0.log` + `pytest_t0_final.txt`
(sau khi siết test T0 lên 22; `test_T0.md`/`test_final.md` dẫn trực tiếp). Bổ sung 11:55: GIỮ
`mutation_check_t1.log` + `pytest_t1_final.txt` (sau khi siết T1 lên 29; `test_T1.md`/`test_final.md` dẫn).

**C. CẦN ANH QUYẾT (nhạy cảm, không tự xếp vào nhóm xoá):**

| mục | cỡ | vì sao ngập ngừng |
|---|---:|---|
| `backup_repair/` + `repair_ids.py` | ~? MB | bản sao lưu trước khi sửa id round; xoá = mất đường lùi của lần sửa đó |
| `t2_p_1054_2.png` | 1,47 MB | ảnh trang 2 của T2; bản `_1.png` được dẫn, bản này thì không |
| `diag_a_run.log`, `diag_b_run.log`, `diag_c_run.log` | 52 KB | log thô của T1(a)/(b)/(c); số chốt đã nằm trong `data/loop/diag/*/summary*.json` |
| `prompt_ab.json`, `probe_prompt_ab.py`, `probe2.{py,json}` | 39 KB | probe so sánh prompt cũ; kết luận đã vào ROADMAP |
| `guard_audit.json`, `probe_guard_off.{py,json}` | 33 KB | audit guard; kết luận đã vào ROADMAP/báo cáo |

**D. ĐỀ XUẤT XOÁ — 45 mục, ~33 MB, không được dẫn ở đâu và không đang dùng:**
`_pipprobe/`, `_pipprobe2/`, `envcheck.log`, `envcheck_rounds/`, `gate_demo.log`, `gate_demo_rounds/`,
`gate_r8_vs_r5.txt`, `gate_r9_vs_r5.txt`, `gate_r9_vs_r8.txt` (bản chính thức nằm trong
`data/loop/rounds/r8|r9/gate_vs_*.json`), `dl_reranker_v2m3.log`, `ingest_vie.log`, `reocr_vie.log`,
`loop_cache/`, `loop_gen_cache_smoke/`, `loop_smoke/`, `loop_smoke_cache/`, `ollama_ps_3b.txt`,
`p520_section.md` (đã nằm trong ROADMAP P5.20), `p5_driver.sh`, `p5_rest.sh`, `p5_rest.log`,
`probe_anchor.{py,json}`, `probe_r8_attribution.py`, `probe_rescue_regex.py`, `probe_rescue_smoke.py`,
`probe_t4_gpu.py`, `qa_baseline_pytest.txt`, `r0_driver.sh`, `r1_driver.sh`, `r5_driver.sh`,
`reranker_probe.log`, `smoke_r8.log`, `t1b_resume_20261024.log`, `t1b_resume2_20261024.log`,
`t1b_resume3_20261024.log` (ba file 0 byte), `warm3b.err`, `warm3b.json`, `warm3b.txt`.

**Lệnh khi được duyệt (chỉ chạy sau khi anh gạch tên mục muốn giữ):**
```
cd D:/DoAn/hybrid_rag_agu && rm -rf tmp/_pipprobe tmp/_pipprobe2 tmp/envcheck_rounds tmp/gate_demo_rounds \
  tmp/loop_cache tmp/loop_gen_cache_smoke tmp/loop_smoke tmp/loop_smoke_cache \
  tmp/{envcheck,gate_demo,dl_reranker_v2m3,ingest_vie,reocr_vie,p5_rest,reranker_probe,smoke_r8}.log \
  tmp/gate_r{8_vs_r5,9_vs_r5,9_vs_r8}.txt tmp/ollama_ps_3b.txt tmp/p520_section.md \
  tmp/p5_driver.sh tmp/p5_rest.sh tmp/r{0,1,5}_driver.sh \
  tmp/probe_anchor.{py,json} tmp/probe_r8_attribution.py tmp/probe_rescue_{regex,smoke}.py \
  tmp/probe_t4_gpu.py tmp/qa_baseline_pytest.txt tmp/t1b_resume*_20261024.log tmp/warm3b.{err,json,txt}
```
Hoàn tác: `tmp/` không nằm trong git (`.gitignore` có `tmp/`? — kiểm: **không**, nhưng chưa từng
được commit), nên **xoá là mất hẳn**; đó là lý do phải duyệt trước. Nếu muốn an toàn hơn: chuyển
sang `tmp/_trash_20261025/` rồi xoá sau 7 ngày.

**Cập nhật 25-10 11:3x (sau T7).** Thêm vào **A. GIỮ** (nay được dẫn trong ROADMAP P5.23 /
`docs/DECISION_LOG.md`): `mutation_check_cache_policy.py`, `mutation_check_t7.py`, `chain_demo3/`
(evidence chuỗi run_chain chạy end-to-end 2×20 item). Thêm vào **A. GIỮ** vì đã thành dẫn chứng cho
PA-25 / T5.md §2.7: `probe_r12_fold.py`, `probe_r12_fold.json`. Thêm vào **D. ĐỀ XUẤT XOÁ**:
`chain_demo/`, `chain_demo2/` (hai lượt thử đầu, hỏng cấu hình, đã thay bằng `chain_demo3/`).
`chain_demo_manifest.json` giữ (manifest tất định của lượt demo cuối). Không xoá gì ở bước này.

## PA-25 — 5a: `score_pairs` fold query MẤT DẤU rồi chấm với passage CÒN DẤU ⇒ r12 sụp; đề xuất bỏ fold + chạy r14 (25-10 03:45)

**Vấn đề (đã kiểm, không suy đoán).** `src/reranker.py:242` chấm `fold(query)` (mất dấu thanh) với
`page_content` **nguyên văn còn dấu**. `bge-reranker-v2-m3` là model đa ngôn ngữ nhạy dấu thanh, nên
cặp lệch-dấu cho điểm gần như nhiễu. Probe `tmp/probe_r12_fold.py` trên **30 item mà r11 xếp chunk
vàng TRONG cửa sổ nhưng r12 đẩy ra ngoài**:

| cách chấm query | chunk vàng vào top-6 | median s/item |
|---|---:|---:|
| RRF gốc (không rerank) | 27/30 | — |
| `fold(query)` (r12 đang dùng) | **0/30** (`rank_folded=None` = rơi khỏi cả 20 hạng) | 2,13 |
| query **nguyên văn** (đề xuất) | **28/30**, đa số **hạng 1** | 2,08 |

Nguồn: `tmp/probe_r12_fold.json`. Hệ quả trên round thật (§2.7): gold@6 0,7400 → 0,6686
(delta −0,0714 CI [−0,1014; −0,0414], McNemar 83 mất/33 được p = 3,9e−06), EXACT 0,2115 → 0,0385,
TRAP → 0, neo HUMAN 0,8144 → 0,7010, gate **6/8 kiểm tra VI PHẠM**.

**Vì sao fold từng được chọn (ghi trong docstring `src/reranker.py:35`):** nhánh Chroma hay trả về
chunk sai nguồn khi query có dấu gặp corpus Tầng 1 mất dấu (OCR). Nhưng **reranker khác nhánh Chroma**:
nó chấm query × passage, và passage giữ nguyên văn (Tầng 2 `.docx` CÓ dấu). Fold query một phía ⇒ với
chính những passage còn dấu (Tầng 2, và 80,29% corpus mới `chroma_db_vie`) thì tín hiệu bị phá.

**Diff đề xuất (`src/reranker.py`) — KHÔNG tự áp dụng vì đây là quy ước đã đăng ký trước khi chạy round:**

```diff
 def score_pairs(model: Any, query: str, passages: Sequence[str]) -> list[float]:
     """Điểm relevance cho từng cặp (query, passage) — API của CrossEncoder."""
-    folded = fold(query)
-    pairs = [(folded, p or "") for p in passages]
+    # PA-25: chấm query NGUYÊN VĂN với passage nguyên văn. fold(query) từng làm r12 sụp
+    # (gold@6 0,74->0,6686, EXACT 0,2115->0,0385) vì cặp lệch dấu thanh với model đa ngôn ngữ.
+    # Bằng chứng: tmp/probe_r12_fold.json (0/30 -> 28/30 chunk vàng vào top-6).
+    q = (query or "").strip()
+    pairs = [(q, p or "") for p in passages]
     raw = model.predict(pairs, batch_size=reranker_batch_size(), convert_to_numpy=True)
     return [float(x) for x in raw]
```

Kèm: (1) sửa docstring "Qui ước chấm điểm" + `query_convention` trong `last_call`/manifest cho khớp;
(2) thêm test `tests/test_reranker_flag.py`: `score_pairs` truyền query nguyên văn (fake model ghi lại
cặp nhận được); (3) **chạy r14 = r11 + `ENABLE_RERANKER=1` (query nguyên văn)**, gate r14-vs-r11,
`bonus_paired --baseline r11 --candidate r14`, attribute trước/sau, `gold_rank_ceiling` pool 20.
Ước lượng chi phí r14: **~66 phút** (đo thật r12, không phải 45), 0 Gemini, VRAM 3,6/4,0 GB dùng chung Ollama.

**Không tự chạy r14 vì:** đổi `fold→nguyên văn` là **đổi quy ước đã đăng ký trước** (README mục T5 +
docstring), luật tự trị buộc ghi diff chờ duyệt; và r12 đã cho **kết luận âm rõ ràng** = thỏa tiêu chí
"xong" của T5 theo nhánh âm. Nếu anh duyệt, em áp diff + chạy r14 trong một bước.

**Trần để kỳ vọng đúng:** oracle pool 20 = **0,8871** (EXACT 0,6154; SOURCE_LOOKUP/CLOZE 1,000).
Nếu reranker query-nguyên văn kéo được dù chỉ nửa khoảng cách 0,7400→0,8871 thì EXACT mới có cửa +10 điểm;
probe 28/30 (hạng 1) là tín hiệu mạnh nhưng **probe 30 item chọn thiên lệch, không thay round 811 item**.

## PA-26 — HEAD KHÔNG tái lập được cây đã test: 35 file nguồn/test chưa được commit + 6 file đang sửa dở (mở rộng PA-8; 25-10 11:3x, cập nhật sau `79a02e5`)

**Vấn đề (đo được, không suy đoán).** `git status --short` tại HEAD `456f35c` cho thấy **một fresh
clone sẽ không chạy nổi test**: `src/cache_policy.py` (mới) import `src/answer_guard.py` — file **chưa
tracked**; `src/generator.py` trong working tree có `effective_prompt_version()`/`answer_rescue_enabled()`
mà `git show HEAD:src/generator.py` **không có** (grep = 0). Nghĩa là 1.014 test xanh hiện tại thuộc về
**working tree**, không thuộc về commit nào. Đây là lỗ tái lập, không phải lỗi chức năng.

> Cập nhật sau commit `79a02e5` (T7 docs + `run_chain`): 6 trong 41 file đã được tracked
> (`run_chain.py`, `run_chain.ps1`, `run_chain.sh`, `chains/t5a_reranker.json`,
> `chains/demo_dryrun.json`, `tests/test_run_chain.py`) ⇒ **còn 35 = 3 nguồn + 17 công cụ + 15 test**
> + 6 file tracked đang sửa. Lỗ tái lập **vẫn còn** vì `src/cache_policy.py`, `src/answer_guard.py`
> và các hunk `_cache_key` trong `src/generator.py` chưa được commit.

**Danh sách chính xác** (đo tại `456f35c` bằng `git ls-files --others --exclude-standard src tools tests | grep -v __pycache__`; trừ 6 file đã tracked ở `79a02e5`):

- Nguồn chưa tracked (3): `src/answer_guard.py`, `src/reranker.py`, `src/cache_policy.py`
- Công cụ chưa tracked (17 sau commit): phần còn lại của `tools/loop/` (`run_round.py`, `gate.py`, `attribute.py`,
  `verify.py`, `testset.py`, `triage.py`, `audit_guard.py`, `calibrate_guard.py`, `noise_floor.py`),
  `tools/build_sft_from_round.py`, `tools/build_training_data.py`, `tools/validate_training_data.py`,
  `tools/diag/{bonus_paired,one_variable_check,qlora_memory_probe,reranker_cost_probe,t4_stats}.py`
  (đã tracked ở `79a02e5`: `run_chain.{py,ps1,sh}`, `chains/{t5a_reranker,demo_dryrun}.json` — 5 file)
- Test chưa tracked (15 sau commit): `test_answer_guard.py`, `test_answer_rescue.py`,
  `test_build_sft_from_round.py`, `test_cache_policy.py`,
  `test_loop_{attribute,gate,generator_model_flag,round,testset,triage,verify}.py`,
  `test_noise_floor.py`, `test_query_normalizer_guard.py`, `test_reranker_flag.py`, `test_router_soft_filter.py`
  (đã tracked ở `79a02e5`: `test_run_chain.py` — 1 file)
- File tracked đang sửa (6): `src/generator.py` (+369/−…), `src/pipeline.py` (+235), `src/query_normalizer.py` (+161),
  `src/router.py` (+105), `tests/test_pipeline.py` (+96), `tests/test_subquery.py` (+1/−1)
- Artifact **KHÔNG nên commit**: `models/` 321 MB, `data/loop/rounds/` 78 MB, `chroma_db_vie/` 6,0 MB,
  `chroma_db_headers_old/` 5,7 MB, `.ocr_cache_vie/` 300 KB, `.generation_cache/` 977 KB — trừ khi chọn (i).

**Vì sao em không tự commit:** luật tự trị "KHÔNG commit file `src/` dirty của phiên khác"; 6 file tracked
đang sửa thuộc công việc T3–T5 của phiên trước, và `src/generator.py` chứa lẫn 310 dòng của phiên đó với
đúng 2 hunk T7 của em. Commit cả file sẽ gán sai tác giả/thời điểm cho thay đổi chưa được phiên này kiểm.

**Phần T7 của em:** `tools/loop/run_chain.{py,ps1,sh}` + `chains/*.json` + `tests/test_run_chain.py`
(11 test, mutation **6/6** bị bắt) **đã commit** trong `79a02e5`; phần còn lại chờ đúng một lần commit:
`src/cache_policy.py` + 2 hunk `_cache_key` trong `src/generator.py` + `tests/test_cache_policy.py`
(26 test, mutation **10/10 bị bắt** — log `tmp/mutation_check_cache_policy.log`).

**Ba phương án cần anh chọn:**

| | Nội dung | Ưu | Nhược |
|---|---|---|---|
| (i) | **Freeze đầy đủ**: commit 3 nguồn + 17 công cụ + 15 test + 6 file sửa + `data/loop/rounds/` | tái lập 100%, round là bằng chứng đi kèm | repo +80 MB; không xoá được round cũ dễ dàng |
| (ii) | **Freeze mã + bằng chứng gọn** (đề xuất): commit nguồn/công cụ/test/6 file sửa + chỉ `data/loop/rounds/**/{round_summary_*.json,gate_*.json,attribution_*.json,*_tally.txt}`, thêm `models/`, `chroma_*`, `data/loop/rounds/**/full.jsonl` vào `.gitignore` | tái lập test + số liệu, repo nhỏ | muốn xem lại từng câu phải chạy round (hoặc xin file) |
| (iii) | Giữ nguyên hiện trạng, chỉ commit docs | không rủi ro | **không bao giờ tái lập được**; "người ngoài chạy lại từ README" thất bại |

**Lệnh kiểm chứng sau khi duyệt (em sẽ chạy, không cần anh gõ):**
```
git clone D:/DoAn/hybrid_rag_agu tmp/_fresh_clone && cd tmp/_fresh_clone \
  && python -m pytest tests -q          # kỳ vọng: 1016 passed
python -m pytest tests -q               # trong cây chính, sau commit
git status --short                      # kỳ vọng: chỉ còn artifact trong .gitignore
```
Hoàn tác: commit freeze là commit thường (không force-push) ⇒ `git revert <sha>` nếu sai; không đụng
`data/loop/rounds` trên đĩa khi chọn (ii).

## PA-27 — Chế độ T3 TẮT vẫn TÁCH khóa cache theo env của lever đang TẮT (25-10 12:1x)

**Vấn đề (đo được).** Với **cả hai cờ T3 TẮT** và env sạch, `cache_policy_deviation()` = `None`
(khóa legacy `v1.3`, đúng như golden). Nhưng chỉ cần env còn giá trị của một lever **đang TẮT**,
khóa cache lập tức tách:

| Env đặt thêm (cả hai cờ T3 vẫn TẮT) | `cache_policy_deviation()` |
|---|---|
| — (sạch) | `None` |
| `DEC_MIN_RRF_NORM=0.5` | `e95e6efa2617` |
| `EV_MAX_SENTENCES=3` | `1670eb7035ac` |
| `ANSWER_GUARD_MIN_SCORE=0.75` (guard TẮT) | `94515a7efa5d` |

Trong khi **đầu ra không đổi**: 30 item golden vẫn byte-identical trên mọi mặt trừ
`qwen_cache_key` (test mới `TestOffInvariantWhenDisabledLeversConfigured`, 25-10). Nguyên nhân:
`policy_cache_token()` (src/cache_policy.py:106) đưa **mọi** ngưỡng vào token bất kể `enabled`,
nên `DEFAULT_CACHE_TOKEN` chỉ khớp đúng ảnh chụp env rỗng.

**Đây không phải lỗi trả lời sai, mà là lỗi phát biểu + phí lượt.** Câu "cache key không đổi" của
A1 (T3) chỉ đúng trong env rỗng; một round TẮT cờ thừa hưởng `DEC_*`/`EV_*` từ round trước sẽ sinh
lại toàn bộ dù hành vi y hệt. Đồng thời nó làm nhiễu mutation: M2 (bốn ngưỡng → 0) giờ đỏ **11**
test T3, trong đó 4 test `TestOffGolden`, vì đổi ngưỡng đổi **khóa** chứ không đổi logic từ chối
(24-10 M2 chỉ đỏ 6 test).

**Phương án (a) — đề xuất, hẹp:** chỉ đưa ngưỡng vào token khi **lever của nó BẬT**, và chỉ áp cho
hai lever đã có bằng chứng "ngưỡng trơ khi TẮT" (30 item byte-identical): `decoupled_refusal` +
`evidence_selection`. `rescue`/`guard`/`normalize_sanity` **giữ nguyên** cho tới khi mỗi lever có
một phép đo A1'-kiểu riêng (phương án (b)).

```python
# src/cache_policy.py — policy_cache_token()
    dec = snap["decoupled_refusal"]
    ev = snap["evidence_selection"]
    # Ngưỡng chỉ vào khóa khi lever BẬT: lever TẮT ⇒ runtime không đọc ngưỡng
    # (đã chứng minh 30 item byte-identical), nên đổi ngưỡng không được tách cache.
    dec_payload = None if not dec["enabled"] else {
        "min_entity_coverage": dec["min_entity_coverage"],
        "min_token_overlap": dec["min_token_overlap"],
        "min_rrf_norm": dec["min_rrf_norm"],
        "min_grounding": dec["min_grounding"],
        "max_unsupported": dec["max_unsupported"],
    }
    ev_payload = ev if ev["enabled"] else None
    return _hash12({...
        "decoupled_refusal": dec_payload,
        "evidence_selection": ev_payload, ...})
```

Kèm: bump `CACHE_TOKEN_VERSION` → `cache-policy-v2` (payload đổi cấu trúc) và **đăng ký lại**
`DEFAULT_CACHE_TOKEN` bằng lệnh trong docstring `test_policy_cache_token_default_matches_cleared_env`.
Khóa legacy vẫn dùng được vì env mặc định ⇒ deviation `None` ⇒ **không** thêm trường `policy`.

**Test buộc phải đổi (đo, không đoán):**

| Test | Hiện tại | Sau (a) |
|---|---|---|
| `tests/test_cache_policy.py::test_policy_cache_token_ignores_decoupled_flag_but_not_its_thresholds` (dòng 348) | ngưỡng DEC đổi token **khi cờ TẮT** | ngược lại: TẮT ⇒ token không đổi; BẬT ⇒ đổi |
| `tests/test_cache_policy.py::test_policy_cache_token_default_matches_cleared_env` (dòng 335) | so với hằng | giữ nguyên test; chỉ đăng ký lại hằng |
| `tests/test_t3_guardrails.py::TestOffInvariantWhenDisabledLeversConfigured::test_DAC_TA_HIEN_TRANG_...` (dòng 351) | ghim hiện trạng "TẮT vẫn tách" | thay bằng "khóa TẮT = legacy bất kể `DEC_*`/`EV_*`"; `ANSWER_GUARD_MIN_SCORE` vẫn tách (chờ (b)) |

Không đổi: các test dùng `RESCUE_MIN_SCORE`/`ANSWER_GUARD_MAX_UNSUPPORTED` (giữ bảo thủ ở (a)).

**Rủi ro của (a) và cách chặn:** nếu có đường runtime đọc `DEC_*`/`EV_*` **khi cờ TẮT**, hai cấu
hình khác ngưỡng sẽ dùng chung entry ⇒ trả lời cũ. Bằng chứng ngược: 30 item byte-identical + M8
(ép `decoupled=True` mới đổi đầu ra ⇒ cờ chính là cổng). Bổ sung sau khi duyệt: một test grep/AST
khẳng định `thresholds()`/`sentence_budget()` chỉ được gọi trong nhánh `if ...enabled`.

**Phương án (b):** gate cả 5 nhóm — cần thêm 4 phép đo A1' cho `rescue`/`guard`/`normalize_sanity`
(rẻ, cùng harness). **Phương án (c):** không sửa code, chỉ ghi rõ trong `docs/reports/test_T3.md`
rằng "khóa TẮT không đổi" chỉ đúng với env rỗng — chấp nhận phân mảnh cache.

**Lệnh kiểm chứng sau khi duyệt (em chạy):**
```
venv/Scripts/python.exe -m pytest tests/test_cache_policy.py tests/test_t3_guardrails.py -q
venv/Scripts/python.exe -m pytest tests -q          # kỳ vọng: 1016 passed (± test mới)
venv/Scripts/python.exe tmp/mutation_check_t3.py    # kỳ vọng 9/9, M2 không còn đỏ test golden
# golden 30 item phải byte-identical CẢ qwen_cache_key trong env rỗng
```
Hoàn tác: `git checkout -- src/cache_policy.py tests/test_cache_policy.py tests/test_t3_guardrails.py`
(hoặc `git revert <sha>`) — không đụng dữ liệu, không đụng trọng tài.

## PA-28 — Bộ sinh SFT GIỮ dòng thiếu THỰC THỂ vàng (luật 2/N), trái mục 1 của đặc tả T4 (25-10 12:2x)

**Vấn đề (đo được, không suy đoán).** Đặc tả T4 mục 1 đòi *mọi dòng train phải chứa thực thể vàng và
tên nguồn trong ngữ cảnh của chính dòng đó*. Bộ sinh hiện hành (`tools/loop/triage.py`, dòng
`if not blocks or (frags and len(covered) < min(2, len(frags)))`) chỉ đòi **2 mẩu bất kỳ** trong
`frags = required_entities + primary_entity + gold_sentence + source_document`. Vì vậy một dòng có
**nguồn + câu vàng** nhưng **không có thực thể** vẫn được giữ.

Bằng chứng:

| Đo | Kết quả | Nguồn |
|---|---|---|
| Dòng giả: ngữ cảnh chỉ có nguồn + câu vàng, item đòi thực thể `42` | **được GIỮ** (`skip_sft_target_not_in_context = 0`) | `tests/test_t4_sft_invariants.py::test_dong_thieu_thuc_the_nhung_du_nguon_va_cau_vang_hien_hanh_van_giu` |
| Cùng dòng đó đưa vào bộ kiểm | **ĐỎ** `missing_by_kind = {"entity": 1}` | `tools/diag/check_sft_invariants.py` |
| Dòng giả: ngữ cảnh không có cả nguồn lẫn thực thể | bị loại, đếm `skip… = 1` | `test_dong_thieu_ca_thuc_the_va_nguon_bi_loai_va_dem` |
| Artifact đã công bố `t4b_r5r8r9r10` (13 train/10 holdout) | **0/13 dòng thiếu thực thể**; 5/13 thiếu `gold_sentence` (chỉ là INFO) | `tmp/t4_invariants_report.json` |

Nghĩa là: dữ liệu **đã công bố** không vi phạm mục 1, nhưng bộ sinh **có thể** sinh ra dòng vi phạm
nếu lần chạy sau rơi vào đúng tổ hợp đó — rủi ro nằm ở producer, không nằm ở artifact hiện tại.

**Vì sao KHÔNG tự sửa.** Nới/siết luật này đổi **phân bố dữ liệu** của mọi round tương lai và (nếu
siết) có thể loại thêm dòng của artifact sắp dùng cho PA-11/PA-12 ⇒ phải duyệt thiết kế trước, không
được sửa lặng lẽ trong phiên kiểm thử. Đồng thời chưa đo được luật "bắt buộc đủ mọi `required_entities`"
sẽ loại bao nhiêu dòng (các family SOURCE_LOOKUP/TRAP có thể không có thực thể trong câu vàng).

**Đề xuất (chọn một):**
- (a) **Siết có kiểm soát**: bắt buộc `source_document` + mọi `required_entities`/`primary_entity`;
  `gold_sentence` vẫn tuỳ chọn. Trước khi đổi, chạy `collect()` trên r5/r8/r9/r10 ở chế độ chỉ-đọc
  và báo **số dòng bị loại thêm** (kỳ vọng: nhỏ, vì artifact hiện tại 13/13 dòng đều có thực thể).
- (b) **Giữ 2/N** và ghi rõ trong `data/loop/README.md` rằng "thực thể là mẩu ưu tiên, không bắt buộc"
  — chấp nhận rủi ro dòng thiếu thực thể.
- (c) Siết + **sinh lại artifact T4b** (thư mục mới, không ghi đè) để dùng cho lượt train sau.

**Đã làm trong phiên này (không đụng dữ liệu):** thêm bộ kiểm chỉ-đọc
`tools/diag/check_sft_invariants.py`, 29 test `tests/test_t4_sft_invariants.py` (có ca ghim đúng trạng
thái 2/N hiện hành + ca chứng minh bộ kiểm báo ĐỎ cho nó), mutation **M1 "bỏ kiểm thực thể" bị bắt**
(2 test đỏ, `tmp/mutation_check_t4_new.log`).

**Hoàn tác:** xoá 3 tệp mới (`tools/diag/check_sft_invariants.py`,
`tests/test_t4_sft_invariants.py`, `tests/test_t4_generator_contract.py`) hoặc `git revert <sha>`
commit test T4; **không có dữ liệu/`src/` nào bị đổi**.

---

## PA-29 — 5 script README nhắc **không có argparse**; `ingest.py` xoá index sản xuất mà không có dry-run lẫn xác nhận (đợt kiểm thử T7, 25-10 16:5x)

**Vấn đề (đo được, không suy đoán).** Đề bài T7 mục 6 đòi "mọi lệnh trong README chạy được ở chế độ
`--help` hoặc dry-run". Bộ kiểm `tools/diag/docs_consistency_check.py` phân loại 264 lệnh trong
README/ROADMAP/docs và phát hiện **9 script repo** được nhắc; trong đó **5 script không chứa
`ArgumentParser(`** ⇒ không thể tự động kiểm `--help`/dry-run, chỉ ghi nhận được ở mức **CẢNH BÁO**:

| Script | Bao nhiêu dòng | Hành vi thật khi chạy theo README |
|---|---|---|
| `ingest.py` | 88 | `shutil.rmtree(persist_dir)` với `persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")` (dòng 22–26) ⇒ **xoá index hiện có ngay tại chỗ**, rồi OCR + nhúng lại toàn bộ corpus; không hỏi lại, không dry-run |
| `learn.py` | 139 | `from ingest import run_ingestion` ⇒ cùng hệ quả xoá index khi đi vào nhánh rebuild |
| `src/analyze_ab.py` | 463 | đọc `outputs/` và ghi phân tích + biểu đồ; không cờ nào để chạy thử |
| `demo_streamlit.py` | 1217 | app Streamlit (giữ cổng) — không có `--help` |
| `ui/app.py` | 1014 | GUI Tkinter, mở cửa sổ và **không tự thoát** ⇒ checker cố chạy nó sẽ treo tới timeout |

Riêng **`ingest.py` là rủi ro thật với người mới**: README §5.1 (dòng 338) và §5.4 (dòng 420) bảo
"chạy `python ingest.py`"; `chroma_db/` đang gitignore nên bản clone mới **buộc** phải chạy lệnh này
trước khi tái lập r0 — và chỉ một lần chạy nhầm khi `CHROMA_PERSIST_DIR` trỏ về `./chroma_db` là mất
index sản xuất (361 chunk, tái tạo = hàng giờ OCR + nhúng).

Bằng chứng: `tmp/docs_check_t7_dot2.json` (`command_warnings` = 5 dòng trên, `help_checked` = 4 script
còn lại đều rc=0), `README.md:338`, `README.md:420`, `ingest.py:22–26`.

**Vì sao KHÔNG tự sửa.** `ingest.py`/`learn.py` thuộc nhóm file nguồn production chưa được commit
(PA-26) và là đường onboarding chính của repo; đổi CLI của chúng — dù "thêm argparse" là không đổi
hành vi mặc định — vẫn là thay đổi công cụ mà người dùng cuối chạy theo trí nhớ, cần anh duyệt.
`ui/app.py`/`demo_streamlit.py` thuộc phần frontend, ngoài phạm vi code của anh theo thoả thuận.

**Đề xuất (chọn một hoặc kết hợp):**
- (a) **Tối thiểu, an toàn nhất**: `ingest.py` thêm `--dry-run` (in: corpus sẽ đọc, `persist_dir` sẽ ghi,
  collection hiện có bao nhiêu chunk, có bị `rmtree` hay không — **không** đụng đĩa) + `--yes` để cho
  phép xoá, mặc định là **dừng và hỏi**; README §5.1 ghi lại hai lệnh đó.
- (b) **Cho phép tái lập trên bản clone mới** (đúng tiêu chí nghiệm thu T7): thêm `--out <dir>` để
  người mới build index vào `chroma_db_repro/` mà không đụng index đang dùng; `run_chain`/spec nhận
  thêm env `CHROMA_PERSIST_DIR` (đã có cơ chế `requires` + manifest).
- (c) `src/analyze_ab.py` + `learn.py`: thêm argparse cùng kiểu `tools/diag/*` (chế độ chỉ-đọc trước).
- (d) `ui/app.py`, `demo_streamlit.py`: **không** thêm `--help` cũng được, nhưng README phải ghi rõ
  "GUI, không có chế độ dry-run" ⇒ để checker khỏi báo cảnh báo lặp (thêm whitelist có đăng ký).
- (e) Kèm theo (dù chọn a–d nào): `run_help()` trong `tools/diag/docs_consistency_check.py` đang chạy
  `--help` với **env kế thừa**; đề nghị truyền env đã gỡ `GEMINI_API_KEY`/`GOOGLE_API_KEY`/`HF_TOKEN`
  để việc "kiểm tra CLI" không bao giờ đưa bí mật vào process của script được kiểm.

**Đã làm trong phiên này (không sửa script nào):** checker phân loại rõ LỖI (script repo không tồn tại)
vs CẢNH BÁO (script tồn tại nhưng không argparse) — nghĩa là 5 script trên **không được tính là đã đạt**
mục 6; mutation **M20** ("mọi script đều được coi là có `--help` ⇒ mất cảnh báo onboarding") bị bắt,
kèm test ghim đúng danh sách 5 cảnh báo của repo thật
(`TestRepoThatChiDoc.test_script_khong_argparse_chi_dung_o_muc_canh_bao`).

**Hoàn tác:** không có thay đổi nào ở script production để hoàn tác; nếu anh từ chối PA-29 thì chỉ cần
xoá mục này — cảnh báo vẫn còn trong `tmp/docs_check_t7_dot2.json` và bộ test không đổi kết luận.

## PA-30 — `.env.example` không khai báo 13 cờ lever ⇒ người mới không biết lever tồn tại (nghiệm thu cuối, 25-10 18:5x)

**Vấn đề (đo được).** `tools/diag/env_flag_audit.py` → `tmp/env_flag_audit.json`: `.env.example` khai báo
**26 khóa**, nhưng **0 khóa** trong số 13 cờ lever của T3/T4/T5/T7 (`ENABLE_DECOUPLED_REFUSAL`,
`ENABLE_EVIDENCE_SELECTION`, `ENABLE_ANSWER_GUARD`, `ENABLE_RERANKER`, `RERANKER_KEEP_CANDIDATES`,
`ENABLE_CONTEXTUAL_HEADER`, `OLLAMA_MODEL`, `LOCAL_SLM_MODEL`, khóa chính sách cache và các ngưỡng
`DEC_*`/`EV_*`/`RESCUE_*`). Người clone repo **không thể bật/tắt lever một cách có ý thức** — họ chỉ tình
cờ biết qua README.

Mặt tốt đã kiểm: 5 khóa đang bật trong `.env.example` (`GENERATION_CACHE`, `QWEN_FALLBACK`,
`ENABLE_HYBRID_SEARCH`, `ENABLE_QUERY_EXPANSION`, `OCR_ENABLED`) đều là chức năng **có trước vòng lặp**;
`env_example_not_off = {}` ⇒ không lever nào bị bật ngầm.

**Đề xuất:** thêm khối chú thích "LOOP LEVERS — mặc định TẮT" vào `.env.example`, mỗi cờ một dòng dạng
`ENABLE_RERANKER=0` kèm chú giải 1 dòng + ghi nguồn task; giữ nguyên giá trị 0 để không đổi hành vi.
Test đã có răng chờ sẵn (`test_final_env_flag_defaults.py::test_dotenv_example_khong_bat_cua_lever_nao`
sẽ vẫn xanh vì chỉ kiểm "không bật"; phần "phải khai báo" cần thêm assertion khi anh duyệt).
**Không tự làm** vì `.env.example` là file cấu hình dùng chung, dễ xung đột với env cá nhân của anh.

## PA-31 — 89 dòng dữ liệu nhân thân trên 8 file chưa mask (nghiệm thu cuối, 25-10 18:5x)

**Vấn đề (đo được).** `tools/diag/secret_scan.py` → `tmp/secret_scan.json`: **0 secret**, **0 đường dẫn
theo tên user**, nhưng **89 dòng `DU_CAO_NHAN_HOC`** trên 8 file: `data/loop/diag/referee_labeling_r5.jsonl`
28, `referee_labeling_r5.md` 28, `b_gemini_top6/rows.jsonl` 11, `a_oracle_qwen/rows.jsonl` 6,
`c_gold_window_qwen/rows.jsonl` 6, `outputs/ab_results_without_classifier.json` 4,
`outputs/ab_results_with_classifier.json` 3, `data/loop/diag/corpus_diagnostics/manual_20_segments.txt` 3.
Chiếu theo pattern: 65 số điện thoại VN, 24 email. Đây là dữ liệu trích từ tài liệu nội bộ nhà trường;
**tất cả 8 file đang untracked** nên chưa từng rời máy.

**Rủi ro:** PA-26 (freeze) sẽ kéo theo các file này vào commit ⇒ thông tin liên hệ của sinh viên/giảng
viên vào git history (không xoá được sạch sau khi push).

**Đề xuất (chọn một):** (a) thêm chế độ `--redact-out <dir>` vào `tools/diag/secret_scan.py` (script đã có
hàm `redact()` ở dòng 100 nhưng hiện chỉ dùng che mẫu tin in ra, **chưa** có CLI nào ghi file đã mask),
xuất bản redact của 8 file sang thư mục mới rồi commit bản redact đó, giữ artifact gốc trong `tmp/`;
(b) commit **trích chọn** — chỉ `round_summary_*.json`,
`gate_*.json`, `attribution_*.json` (không chứa câu hỏi thô) theo PA-26 phương án (ii); (c) chấp nhận
rủi ro nội bộ nếu repo chỉ chạy trên máy nội bộ — cần anh quyết, em không tự chọn.
**Không tự làm** vì redact làm đổi nội dung artifact đã công bố (golden `referee_labeling_r5` được test
T6 đếm theo dòng).

## PA-32 — 3 id dữ liệu train trùng tên giữa train/val/benchmark (nghiệm thu cuối, 25-10 18:5x)

**Vấn đề (đo được).** `tools/diag/train_data_audit.py` → `tmp/train_data_audit.json`: `tong_roi_le_thuc = 0`
nhưng `tong_id_trung_ten = 3`: `code_tests-00049` (train↔val), `refusal-00380` và `router_config-00237`
(train↔benchmark seed). Phân tích nội dung cho thấy **cùng id, khác câu hỏi/nội dung**
(`roi_le_theo_cau_hoi = []`, `roi_le_theo_text_classifier = []`) ⇒ không phải leak, nhưng định danh không
độc nhất giữa các split.

**Hệ quả thực tế:** bất kỳ công cụ nào khớp theo id (dọn dữ liệu, suy attribution, báo cáo theo id) sẽ
gán nhầm bản ghi giữa split; nếu sau này đổi cách sinh id thì 3 va chạm thành leak thật.

**Đề xuất:** thêm kiểm "id độc nhất trong toàn bộ manifest" vào `tools/validate_training_data.py` (thành
bất biến #8) + đánh số lại 3 dòng bằng script chỉ-đọc xuất diff, hoặc giữ nguyên và ghi chú "id chỉ độc
nhất trong từng split" trong `data/training/README.md`. **Không tự làm** vì đổi id = đổi dữ liệu train đã
được dùng để train classifier đang deploy.

## PA-33 — `.gitignore` không loại các thư mục artifact ⇒ `git add -A` sẽ stage 1.980 đường dẫn, gồm 321 MB `models/` (nghiệm thu cuối, 25-10 18:5x)

**Vấn đề (đo được).** `git ls-files --others --exclude-standard` = **1.980** đường dẫn không bị loại:
`tmp/` 1.483 (119 MB) · `data/` 343 (trong đó `data/loop/rounds/` 98 MB, `data/training/` 13 MB) ·
`models/` 58 (321 MB) · `.ocr_cache_vie/` 13 · `chroma_db_vie/` 5 · `chroma_db_headers_old/` 5 · cùng 47
file nguồn/công cụ/test của PA-26. `.gitignore` hiện chỉ có `chroma_db/`, `.ocr_cache/`, `.generation_cache/`,
`logs/*`, caches Python — **không** có các tên hậu tố `_vie`, `_old`, `models/`, `tmp/`, `data/loop/rounds/`.

**Rủi ro:** một lần `git add -A` (rất hay xảy ra khi freeze theo PA-26) làm phồng repo ~500 MB, và không
gột lại được sạch sau push; ngược lại nếu chỉ `git add` từng file thì dễ bỏ sót chính 47 file PA-26 cần commit.

**Đề xuất (chọn):** (a) thêm vào `.gitignore`: `tmp/`, `models/`, `data/loop/rounds/`, `data/training/`,
`chroma_db_vie/`, `chroma_db_headers_old/`, `.ocr_cache_vie/` **rồi** commit 47 file nguồn/test theo
PA-26 (đề xuất này); (b) giữ nguyên `.gitignore` và đóng gói artifact sang LFS/ngoài repo; (c) freeze full
kèm artifact theo PA-26 (i). Kèm theo đó nên có `scripts/freeze_for_repro.ps1` liệt kê đích danh file được
stage để không ai phải dùng `git add -A`.
**Không tự làm** vì `.gitignore` quyết định nội dung commit của PA-26 — hai quyết định này dính nhau.


## PA-34 — Điều kiện "chạy được bộ test" chưa được đăng ký ở đâu cả: interpreter + bảng mã console + 8 lời gọi subprocess còn thiếu `stdin` ở 6 file (D-35 + D-36, 25-10 19:1x → 20:0x)

**Vấn đề (đo được, không suy đoán).** Mọi số đã công bố của T0–T7 được đo bằng
`venv\Scripts\python.exe`. Máy này có **hai interpreter cùng bản 3.14.8** — cái trong `venv` cài
đủ package, cái ngoài PATH (`%LOCALAPPDATA%\Python\pythoncore-3.14-64`, `include-system-site-packages = false`) thì
không. Nếu người tái lập gõ `python` trên PATH thì:

* **4 file test lỗi collection** — `tests/test_corpus_rebuild.py`, `tests/test_demo_streamlit_display.py`,
  `tests/test_ui_generator_flag.py`, `tests/test_ui_labels.py`, vì `pypdfium2` và `streamlit` chỉ có trong
  `venv/` (bằng chứng: `tmp/pytest_baseline_stdin_closed.txt` — `Interrupted: 4 errors during collection`);
* **console của máy đo là cp1258** (`chcp` = 1258, `locale.getpreferredencoding()` = cp1258), không phải UTF-8
  ⇒ một máy kiểm in tiếng Việt có dấu sẽ văng `UnicodeEncodeError` và trả **exit code 1**, dễ đọc nhầm thành
  "máy kiểm KHÔNG ĐẠT". Đã đặt guard UTF-8 ở 7 máy kiểm (D-36); chưa có chỗ nào ngoài báo cáo này ghi điều
  kiện bảng mã cho người tái lập.
* trước đợt siết D-35, **10 test đỏ/ERROR** chỉ vì `subprocess` kế thừa handle stdin hỏng
  (`OSError: [WinError 6]`) — đã sửa cho các máy kiểm trong phạm vi nghiệm thu cuối, **còn 8 lời gọi
  chưa siết ở 6 file**. Con số này **đếm bằng AST**, không đếm tay: `tmp/count_stdin_sites.py` đi qua
  toàn bộ `tools/` + `tests/` + `src/`, gặp `subprocess.run/Popen/check_output/call` và kiểm tham số
  `stdin` ⇒ **17** lời gọi, **9** đã có `stdin`, **8** còn thiếu:
  `tools/loop/run_chain.py:284` và `:289`, `tools/diag/t4_latency_probe.py:65`,
  `tests/test_t7_tmp_cleanup.py:181` và `:225` (`mklink /J`), `tests/test_t4_gpu_slow.py:41`,
  `tests/test_t4_sft_invariants.py:444`, `tests/test_t6_gate_refusal_and_regression.py:325`.
  Bộ test hiện vẫn xanh với các file đó, nên đây là **rủi ro tiềm ẩn**, không phải lỗi đang đỏ.

**Vì sao KHÔNG tự sửa.** (i) `run_chain.py` là dụng cụ đã sinh artifact tái lập r0 đã công bố (D-30) —
thay đổi dù "không đổi hành vi" vẫn đi ngược thoả thuận không chạy lại/không đụng dụng cụ đã đo;
(ii) sửa CLI/README về interpreter là nội dung người dùng cuối đọc theo, cần anh duyệt;
(iii) `t4_latency_probe.py` là máy đo đã công bố số latency/VRAM (T4).

**Đề xuất (chọn một hoặc kết hợp):**
- (a) **Rẻ nhất, nên làm ngay:** thêm vào README mục chạy test hai dòng — lệnh chuẩn
  `venv\Scripts\python.exe -m pytest tests -q` và ghi chú "Python hệ thống không có `pypdfium2`/`streamlit`
  ⇒ 4 file test sẽ lỗi collection". Kèm `requirements-lock.txt` đã liệt kê đủ hai gói này hay chưa.
- (b) Siết `stdin=subprocess.DEVNULL` cho 8 lời gọi còn lại (6 file) theo khuôn 
  `tools/diag/docs_consistency_check.py` (không đổi tham số, không đổi env, không đổi output) — chạy lại
  `pytest tests -q` và đối chiếu **1372 passed / 5 skipped**; riêng `run_chain.py` chỉ siết
  khi nào anh chấp nhận đo lại tái lập r0 (artifact đã công bố, D-30).
- (c) Thêm `tools/diag/env_probe.py` (chỉ đọc) in ra interpreter + phiên bản pytest + sự hiện diện của
  `pypdfium2`/`streamlit`/`torch` + **bảng mã console** (`locale.getpreferredencoding()`), để báo cáo
  "không chạy được" phân biệt được **code sai** với **môi trường sai** ngay từ dòng đầu tiên.
- (d) Gộp vào PA-26: khi freeze nguồn, đóng kèm `environment.yml`/`requirements-lock.txt` và một
  `make test`/`scripts/run_tests.ps1` trỏ thẳng interpreter của repo.

**Đã làm trong phiên này:** siết 3 máy kiểm (`tools/diag/council_kit.py`, `tools/diag/secret_scan.py`,
`tools/diag/final_number_audit.py`) + 2 bộ test (`tests/test_final_secret_scan.py`,
`tests/test_final_env_flag_defaults.py`), thêm `tests/test_final_subprocess_stdin_guard.py` **34 test**
(đột biến **9/9** bắt được), đặt khối guard in UTF-8 ở **7** máy kiểm, và ghi nguyên ba hiện tượng
môi trường vào `docs/reports/test_final.md` §14. **Không** đổi số đã công bố: kiểm toán **63 dòng**
vẫn `0 dòng LỆCH`, chữ ký `9f1179ccab74`, secret scan `0/0/89/8`. Phát hiện mới của đợt này: chính một
câu của báo cáo này chứa đường dẫn cá nhân ghép từ `C:` + `Users` + tên người dùng ⇒ máy quét bắt được
và test ghim hiện trạng báo đỏ — đã che lại, **không nới máy quét, không hạ assertion** (§14.5).
(Cùng lúc, một cách viết cũ dùng **dấu ngoặc nhọn** bọc chữ 'tên' để mô tả hiểm hoạ đã trúng luật
`Placeholder đã biết`, nâng BI_MAU 251 → 252; đã **đổi câu** chứ không đổi máy quét, để số công bố
khớp đúng tree sẽ commit.)

**Hoàn tác:** `git revert` commit của đợt D-35 + D-36 là đủ — phạm vi chỉ gồm `stdin` ở 3 máy
kiểm, khối in UTF-8 ở 7 máy kiểm, 1 bộ test mới (34 test) + 2 bộ test bổ sung, và tài liệu.
Nếu anh từ chối PA-34 thì xoá mục này; các test đã siết vẫn xanh và không đòi hỏi thêm gì.


## PA-35 — Kích hoạt `ENABLE_RERANKER` (lever T5a sau khi áp PA-25) làm mặc định? (B3, 26-10 02:0x)

**Số đo được (cây trọng tài v2 `2911c69f740d`, cùng `rounds_v2`, `config_mismatches: []`).**
r16 = r12 nhưng query chấm **nguyên văn** (PA-25), mọi khóa settings khác bất biến (đã diff manifest):

| Chỉ số | r11 (reranker TẮT) | r12 (fold) | r16 (PA-25) | Ghép cặp 811 r11 -> r16 |
|---|---|---|---|---|
| gold@6 | 0,7400 | 0,6686 | **0,8357** | delta +0,0957, CI [0,0714; 0,1200], McNemar p=2,4e-14 |
| EXACT gold@6 | 0,2115 | 0,0385 | **0,4231** | delta +0,2116, n=52, p=0,0034 |
| `FAIL_RETRIEVAL` | 182 | 232 | **115** | -67 item |
| neo toàn bộ | 0,8319 | 0,7553 | **0,8883** | +0,0564 |
| neo HUMAN (n=97) | 0,8144 | 0,7010 | 0,7629 | **-0,0515, CI [-0,1237; +0,0103]** |
| median / p95 latency | 2,78 / 3,87 s | 4,74 / 5,09 s | 4,73 / 5,09 s | +70% / +31% |

Cổng r16-vs-r11: **KHÔNG ĐẠT** (5/6 ĐẠT, vi phạm duy nhất là neo HUMAN -6,32% so ngưỡng -5%).
Cổng r16-vs-r12: **ĐẠT cả 6** (neo HUMAN +8,83%). Tiêu chí đăng ký trước của B3 (`EXACT delta >= +0,10`): **ĐẠT**.

**Rủi ro nếu bật ngay.** (1) Đây là **pha truy xuất thuần** — chưa có lượt sinh trên r16, nên chưa biết
+0,0957 gold@6 có chuyển thành PASS_CORRECT hay bị lấp bởi over-refusal/tốc độ; (2) +1,95 s median là chi
phí thực cho mọi câu hỏi sản xuất, và GPU 4 GB đang phải chia với Ollama; (3) hồi quy neo HUMAN tập trung
vào 8 item HQ23/HQ35/HQ36/HQ39/HQ40/HQ43/HQ44/HQ58, trong đó `ke-hoach-ttck-kltn-dh24th-2026.pdf` là tệp
PA-7 đã kết luận phải loại khỏi index mới — tín hiệu này lẫn với nợ corpus chưa trả.

**Đề xuất (chọn (a)).** (a) **Chưa bật.** Chạy **pha sinh trên r16** (Ollama local, 0 lượt Gemini) để lấy
PASS_CORRECT/refusal/fabrication thật, rồi chấm cổng full-phase r16-vs-r11; chỉ khi đạt mới đổi mặc định.
(b) Bật `ENABLE_RERANKER=1` mặc định ngay theo bảng truy xuất. (c) Bật kèm `RERANKER_KEEP_CANDIDATES` —
**không khuyến nghị**: chưa đo riêng, thêm biến số.
**Không tự làm** vì đổi mặc định của một lever sản xuất nằm ngoài phạm vi đã duyệt, và cổng chính thức
đang báo KHÔNG ĐẠT.


## PA-36 — Cổng `human_anchor_source_not_degraded`: ngưỡng tương đối -5% đo trên 11 cặp bất đồng (B3, 26-10 02:1x)

**Vấn đề (đo được).** Điều kiện này so sánh `expected_source_in_window` của riêng family HUMAN (n=97).
Ở r16-vs-r11 nó đổi chiều từ ĐẠT sang VI PHẠM vì **8 item mất / 3 item lấy** — McNemar chính xác p=0,2266,
bootstrap 10.000 lượt seed 20261023 cho CI [-0,1237; +0,0103] chứa 0. Nói cách khác cổng đang bật đỏ theo
một hiệu ứng mà chính bộ đo thống kê của repo không phân biệt được với nhiễu, trong khi các cổng khác
(gold@k) dùng mẫu 700 item. Toàn bộ 97 item HUMAN có `has_gold_chunk=False`, nên neo nguồn là thước
*duy nhất* của family này.

**Rủi ro:** hai loại lỗi đối xứng — một lever tốt bị chặn vì 5/97 item (chuyện vừa xảy ra với r16), và
ngược lại một lever phá neo HUMAN thật sự vẫn lọt nếu tình cờ net <= 4 item.

**Đề xuất (chọn (a), CHỈ ĐỀ XUẤT — `tools/loop/gate.py` là dụng cụ đo, không tự sửa).**
(a) Giữ ngưỡng -5% nhưng thêm điều kiện *độ rộng mẫu*: chỉ tính VI PHẠM khi tổng số cặp bất đồng
(lost+gained) >= `GATE_MIN_ANCHOR_DISCORDANT` (đăng ký trước, gợi ý 20) — dưới ngưỡng thì báo
`KHONG_KET_LUAN_DU_MAU` và yêu cầu mẫu lớn hơn; (b) đổi sang kiểm định chính xác (McNemar p < 0,05) thay
vì điểm tương đối; (c) giữ nguyên như hiện tại, coi đây là bộ lọc bảo thủ chủ động.
Kèm theo: nếu chấp nhận (a) hoặc (b), phải **chấm lại toàn bộ các cổng đã công bố** bằng công cụ mới trong
thư mục riêng (không ghi đè) và báo bảng cũ-vs-mới, như đã làm với trọng tài v2.
**Không tự làm** vì đây là thay đổi thước đo đã đăng ký; mọi số lịch sử đang dựa vào thước cũ.


## PA-37 — Cho phép tải weights cross-encoder NHỎ để trả lời đúng vế "model nhỏ" của B4? (B4, 26-10 02:1x)

**Vấn đề (đo được).** Câu hỏi đề bài là "đo một cross-encoder **nhỏ**". `BAAI/bge-reranker-base` (278M)
không có weights trên đĩa; `~/.cache` chỉ có `BAAI/bge-reranker-v2-m3` (568M) — đúng model của lever T5a —
và `Qwen2.5-0.5B` (đã có cho B5). Ngã rẽ bảo thủ trong ca trực là **không tải 1,1 GB weights mới**, nên các
AUC 0,80–0,83 là của model 568M. Vì vậy câu "một model nhỏ hơn có phân biệt được POS/NEG không" vẫn **TRỐNG**,
và mọi kế hoạch answerability chạy trên máy không GPU (CPU-only) đang chưa có cơ sở.

**Đề xuất.** (a) **Chưa tải gì** — ghi nhận khoảng trống, chỉ dùng 568M khi nào cần chất lượng, và chấp nhận
rằng answerability chỉ chạy được ở nơi có GPU (khuyến nghị nếu mục tiêu chỉ là cổng trong loop);
(b) cho phép tải `BAAI/bge-reranker-base` (~1,1 GB) rồi **chấm lại cùng ba labelset đã lưu** (dựng nhãn không
phải chạy lại) để so AUC 278M vs 568M và cả tốc độ CPU; (c) một phương án nhẹ hơn — dùng đúng `Qwen2.5-0.5B`
đã có trên đĩa làm scorer sinh nhãn có/không, 0 dung lượng tải thêm, nhưng phải đăng ký tiêu chí mới.
**Không tự làm** vì tải weights ngoài là thay đổi môi trường đo và B4 đã chấm xong bằng thước đã ghi.


## PA-38 — Đăng ký lại phép đo answerability có mốc "hạng truy xuất" hợp lệ (B4, 26-10 02:3x)

**Vấn đề (đo được, không phải suy đoán).** Trong cả ba mẫu, `auc_rank_min` = **0,5** và `rank_min_phang` =
**true**: cặp NEG được tạo bằng cách rút chunk vàng khỏi cửa sổ nên POS và NEG luôn bắt đầu ở hạng vị trí 1.
Đây là hệ quả trực tiếp của bản sửa rò rỉ nhãn phát hiện khi viết test (Ngã rẽ 29) — giữ `rank` truy xuất gốc
làm feature thì nhãn tự lộ. Kết cục trung thực: B4 trả lời được "cross-encoder phân biệt POS/NEG tới đâu",
**không** trả lời "tốt HƠN hạng truy xuất bao nhiêu" — tức vế so sánh trong đề bài chưa có số.

**Đề xuất (CHỈ ĐỀ XUẤT — nhãn hiển thị trong dụng cụ đo đã chạy không được sửa lại để vừa số).**
(a) Đăng ký TRƯỚC một phép đo mới trên chính ba labelset đã lưu, dùng `neg_source_ranks` (đã ghi trong từng
dòng) làm mốc, với thiết kế cặp không lộ nhãn: POS = hạng vàng trong cửa sổ, NEG = hạng cao nhất mà ô thay
vào chiếm; chỉ tiêu So SÁNH là `auc_ce_max − auc_rank_max` (delta AUC), mẫu >= 100 cặp eval_clean;
(b) bỏ hẳn vế "so với hạng truy xuất" khỏi câu hỏi B4 và coi lever chỉ còn giá trị làm bộ lọc tiên đoán
"có đáp được không"; (c) dựng lại nhãn NEG theo kiểu khác (rút vàng + thay bằng ứng viên **khác tài liệu**)
để giảm 60–65% `still_answerable` rồi mới đo mốc hạng. Kèm theo đề xuất nhỏ: đổi tên trường
`dataset_path` thành `dataset_out_default`/`dataset_in` trong `tools/diag/answerability_probe.py` để artifact
khỏi gây nhầm (trường này hiện trỏ về labelset r5 ở hai lượt bổ sung dù `pairs_source` và `n_pairs` đúng).
**Không tự làm** vì đây là đổi thiết kế đo và đổi dụng cụ đo sau khi số đã công bố.


## PA-39 — Thêm đường "logits theo vị trí đáp án" vào `models/train_sft_lora.py` rồi chạy MỘT lượt train thật (B5, 26-10 02:5x)

**Số đo được (probe, 1 bước fwd+bwd, batch 1).** Ở tỷ lệ đáp án thật của đúng 13 dòng D-25 (median 0,0393):
dòng 1707 token cần **6238,3 MiB** theo đường hiện tại (`full`) nhưng **3328,3 MiB** khi LM head chỉ tính ở
vị trí có nhãn — từ 152,3% xuống 81,3% tổng card. Kiểm chứng độc lập cho thấy con số vượt card **không** còn
là bằng chứng thất bại (CUDA oversubscribe tới 8 GiB, cái giá là tốc độ x4,25), nên câu hỏi thật sự giờ là
"một epoch có chạy xong trong bao lâu", không phải "có chạy được không".

**Rủi ro nếu tự làm.** Probe không có Adam state, không padding động, không dataloader; đổi `train_sft_lora.py`
là đổi code train đang có phiên bản đã deploy (classifier v2 / LoRA 0,5B) và một lượt train thật chiếm GPU
vài chục phút tới giờ — đúng loại việc ngoài phạm vi "Không train" của đề bài B5.

**Đề xuất (chọn (a)).** (a) Thêm cờ `SFT_ANSWER_ONLY_LOGITS` (mặc định **TẮT**, đọc env như mọi cờ khác) áp
dụng cơ chế đã được test + đột biến ở `tools/diag/answer_token_logits_probe.py`, chạy **một** lượt train 13 dòng
ở `max_length=1768` với cờ BẬT, báo peak + `nvidia-smi` + thời gian/bước + loss cuối, so với lượt T4b đã công bố
(artifact tên mới, không ghi đè); nếu lượt đó xanh thì PA-11 (4-bit) / PA-12 (đổi định dạng) có thể rút.
(b) Chạy lượt train thật với đường **hiện tại** (không sửa gì) ở 1707 token để đo mức chậm do oversubscription —
trả lời "có sống nổi không" mà không đụng code; (c) không train gì thêm, giữ PA-11/PA-12 là hai đường duy nhất
(theo bảng đọc cũ của T4b — giờ đã biết là suy từ peak, không phải quan sát).
**Không tự làm** vì đề bài B5 ghi rõ "Không train".


## PA-40 — Quy ước phát ngôn về bộ nhớ: "peak > VRAM" không còn là bằng chứng "hết chỗ" (B5, 26-10 02:5x)

**Bằng chứng.** `data/loop/diag/b5_wddm_oversubscription.json`: trên RTX 3050 4 GB (tổng 4095,5 MiB, RAM hệ
thống 16088,1 MiB, pagefile 32176,1 MiB), `torch.empty` được cấp và **ghi đủ** 1/2/3/4/6/8 GiB mà không có
ngoại lệ nào; `nvidia-smi` khoá ở 3849 MiB trong lúc tensor 8 GiB còn sống; thời gian `fill_` giảm từ
33,6 GiB/s (3 GiB) xuống 7,9 GiB/s (8 GiB) — tức **x4,25**. Kết luận: driver ở máy này oversubscribe, cái giá
là băng thông, không phải từ chối cấp.

**Việc cần duyệt — ba lựa chọn.** (a) Sửa **cách đọc số trong báo cáo**: mọi phát ngôn "hết chỗ / không train
nổi / cần 4-bit" phải kèm bằng chứng thất bại thật (ngoại lệ OOM, hoặc thời gian mỗi bước đo được), không chỉ
`peak_allocated > tổng VRAM`; đính chính có kiểm-soát ở `docs/reports/T4.md` + `docs/STATE.md` (giữ nguyên số,
chỉ đổi câu diễn giải và ghi rõ "chưa quan sát thất bại"); (b) thêm vào
`tools/diag/answer_token_logits_probe.py` một lần sample `nvidia-smi` **trong lúc** tensor còn sống để tách
"resides trên card" khỏi "đã spill" (sửa dụng cụ đo ⇒ chỉ đề xuất, và nếu chấp thuận thì chạy lại bằng artifact
tên mới, không ghi đè ba lượt đã công bố); (c) giữ nguyên, chấp nhận rằng các con số peak trong T4b/D-25 chỉ có
ý nghĩa tương đối giữa hai mode.
**Không tự làm** vì cả ba đều đụng tới dụng cụ đo hoặc lời văn đã công bố.


## PA-41 — Hai kỳ vọng cũ của `tools/diag/final_number_audit.py` đã bị công việc được duyệt làm lỗi thời (B-kết, 26-10 03:0x)

**Số đo được (đã đính chính 26-10).** `venv/Scripts/python.exe tools/diag/final_number_audit.py` cho 61/63 KHỚP,
2 dòng LỆCH và **rc = 0** — grep cả script chỉ thấy một `return 0` rồi `raise SystemExit(main())`, không có
đường trả mã lỗi nào. Cách nói "máy kiểm fail" trong D-42/MORNING/STATE và dòng đầu của PA-41 là **suy diễn từ chính
trạng thái đỏ**, chưa từng được đo; đã sửa cả năm chỗ. Hệ quả thật: không có gì chặn khi máy kiểm lệch.

| Dòng kiểm | kỳ vọng trong máy kiểm | đĩa hiện tại | vì sao lệch |
|---|---|---|---|
| `T5 — 46 test cờ RERANKER_FALLBACK` | 46 | **51** (`--collect-only tests/test_reranker_flag.py`) | B3 thêm test khoá `query_convention` của PA-25 vào đúng file đó |
| `Chung — chữ ký trọng tài 9f1179ccab74` | v1 | **`2911c69f740d`** | B2 áp PA-2 + PA-20 (đã được duyệt), phiên bản hoá trong `tests/test_t8_referee_v2.py` |

**Rủi ro hai chiều.** Tự sửa cho xanh = xoá dấu vết của chính hai thay đổi được duyệt (máy kiểm sinh ra để bắt
loại lệch này). Để đỏ = từ nay mọi lần chạy nghiệm thu đều phải giải thích "hai dòng LỆCH này là cố tình, không phải lệch thật", và một
lệch thật sẽ lẫn vào hai lệch đã biết.

**Đề xuất (chọn (a)).** (a) Cập nhật hai dòng trong `tools/diag/final_number_audit.py` thành `51` và
`2911c69f740d`, **giữ lại chú thích nguồn** ("46/`9f1179ccab74` tới 25-10, đổi vì B2+B3 — xem D-41, D-42"), rồi
chạy lại để xác nhận 63/63 KHỚP; (b) thêm cơ chế "kỳ vọng theo phiên bản" (máy kiểm chọn giá trị theo chữ ký
trọng tài của round đang kiểm) — đắt hơn, nhưng đúng bài học B2; (c) giữ nguyên, chấp nhận đỏ có chủ đích và
ghi chú ở README; (d) **hai điều kiện kỹ thuật mới phát hiện khi đính chính** — cho máy kiểm **trả mã lỗi khác 0 khi có dòng LỆCH** (hiện luôn trả 0, nên "đỏ" chỉ tồn tại trên văn bản in ra), và in rõ yêu cầu chạy bằng venv của repo (interpreter hệ thống thiếu `pypdfium2`/`streamlit` ⇒ 4 file collect-only lỗi ⇒ thêm 1 LỆCH GIẢ). **Không tự làm** vì đây là sửa máy kiểm, không phải sửa dữ liệu đo.
