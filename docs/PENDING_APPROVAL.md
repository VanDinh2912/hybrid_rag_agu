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
