# PENDING_APPROVAL — việc cần người dùng duyệt (phiên tự trị KHÔNG tự làm)

Mỗi mục: bối cảnh → đề xuất → diff/đường dẫn → cách hoàn tác nếu bị từ chối.

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

## PA-3 — cổng gate.py (đang chờ từ trước, không đổi): #23 quy tắc refusal tương đối + veto family
- Giữ nguyên trạng thái "chờ duyệt"; `gate.py` chưa sửa. Xem `docs/reports/T0.md` mục hệ quả cổng.

## PA-4 — T1 (b) tiếp tục: cần quota Gemini các ngày sau
- (b) dừng ở 6/30 vì PerDay. Đề xuất: cho resume các ngày sau (lệnh ở STATE.md) để đủ n rồi mới
  chốt nhánh bảng quyết định (T4 vs T2/T6). Đêm nay KHÔNG gọi thêm.

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

