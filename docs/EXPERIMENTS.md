# Thí nghiệm đã đo — một bảng

Bảng dưới đây tóm tắt các phép đo quyết định trong [DECISION_LOG.md](DECISION_LOG.md) (sổ đầy đủ
42 dòng, kèm ngữ cảnh và trạng thái từng mục). Quy ước đọc:

- Số trong ô "Kết quả" được chép từ artifact hoặc từ dòng D-xx tương ứng; **không** làm tròn thêm.
- `n` là số đơn vị đo, đọc kèm đơn vị ghi ngay trong ô.
- `CI 95%` chỉ điền khi artifact có khoảng tin cậy; `—` nghĩa là chưa tính, không phải "không đáng kể".
- Cột nguồn là **một tệp chính**; danh sách đầy đủ nằm ở cột "Nguồn" của DECISION_LOG.
- Ngưỡng đã đăng ký trước không chỉnh sau khi thấy số; kết quả âm giữ nguyên.

| Giả thuyết | Kết quả | n | CI 95% | Tệp nguồn |
|---|---|---|---|---|
| D-01 · lọc nguồn mềm thay lọc cứng kéo recall lên | GIỮ lever: gold@6 51,86→**76,57%**; FAIL_RETRIEVAL 337→164; bị lọc cắt 244→0; neo HUMAN 81,44→77,32% (−5,06% tương đối) nên cổng chặn | 811 item (700 vàng) | — | `data/loop/rounds/r1/round_summary_retrieval.json` |
| D-02 · hạn ngạch 4 nguồn/cửa sổ sửa "một nguồn chiếm cả cửa sổ" | **BÁC** (giả thuyết cấu trúc sai): gold@6 74,00→74,29% (+0,29 ≈ 2 item), 2 cổng ĐẠT nhưng gold không hồi phục | 811 item (700 vàng) | — | `data/loop/rounds/r4/round_summary_retrieval.json` |
| D-03 · rescue cứu được câu sai | **BÁC vĩnh viễn**: 60/64 lượt thử, cứu được **1 = 1,7%**; r5b lặp lại y hệt | 64 lượt thử / 100 item | — | `data/loop/rounds/r5b/rescue_tally.txt` |
| D-04 · guard chuẩn hóa lấy lại chunk vàng | GIỮ lever (bật mặc định = CHỜ DUYỆT #23): **5/5** ca lấy lại chunk vàng; PASS_CORRECT 10→14; gold@k 0,6875→0,7875; refusal 0,72→0,64 | 5 ca bị bác / 100 item | — | `data/loop/rounds/r6/round_summary_full.json` |
| D-05 · bonus 12 cộng hưởng với guard | **BÁC** tổ hợp: PASS_CORRECT 14→14 (trong băng nhiễu ±3); 2 ca PASS_CORRECT → từ chối oan | 100 item | — | `data/loop/rounds/r7/gate_vs_r6_full.json` |
| D-06 · "bonus 12 mất 2,57 điểm" là do chỉnh sai hằng số | **BÁC**: delta −0,0257; 21/21 chunk vàng rơi hạng 7–12; EXACT/TRAP bất biến | 811 item | [−0,04; −0,0129] | `data/loop/diag/bonus_paired.json` |
| D-07 · bỏ đường từ chối + 5 luật ngoài tăng câu đúng, không tăng bịa | **BÁC**: PASS_CORRECT 14→19 (<25); PASS_REFUSAL 17→2; HALLUCINATED_ON_UNANSWERABLE 2→12; refusal 0,69→0,28; fabrication 0,0323→0 | 100 item | — | `data/loop/rounds/r8/round_summary_full.json` |
| D-08 · cửa sổ 3–5 câu bằng chứng giúp model 1,5B trả lời đúng hơn | **BÁC**: 75/75 cửa sổ đúng 5 câu (6.898→1.022 ký tự); model_still_refuses 3→32; PASS_CORRECT 19→19 (tập khác); refusal 0,57; p95 19,93→33,27 s | 100 item | — | `data/loop/rounds/r9/round_summary_full.json` |
| D-09 · nâng model sinh 1,5B → 3B vượt 22/100 câu đúng | **BÁC**: PASS_CORRECT 14→16; McNemar p=0,804; p95 18,65→34,12 s; một-biến 100/100 item trùng | 100 item | [−0,06; +0,10] | `data/loop/rounds/r10/t4_stats.json` |
| D-10 · SFT chạy được trên GPU 4 GB với dữ liệu hiện tại | **MỞ**: trần VRAM ≈1.000 token/dòng; 13/13 dòng train ≥1.016 token; gradient checkpointing không giúp. D-39 hạ cấp cách đọc "không train nổi" (peak một mình chưa đủ) | 13 dòng train | — | `data/loop/diag/t4b_memory_probe_len.json` |
| D-11 · reranker cross-encoder (top-20 → top-6) nâng gold@6 | **MỞ** (PA-25): delta −0,0714; McNemar 83/33 p=3,9e−06; probe 0/30 với `fold(query)` vs 28/30 query nguyên văn ⇒ lỗi build | 700 cặp | [−0,1014; −0,0414] | `data/loop/diag/reranker_paired_r11_r12.json` |
| D-12 · header Chương/Điều/Khoản tăng gold@6 | **BÁC** trên corpus cũ (corpus T2 = MỞ/PA-21): delta −0,0029 (= −2/700), độ lớn delta < nhiễu 11, p=0,79. ĐÍNH CHÍNH 25-10: −0,0028 → −0,0029 | 700 cặp | [−0,0129; +0,0071] | `data/loop/diag/header_paired_r11_r13.json` |
| D-13 · OCR lại bằng EasyOCR `vi` sửa được nút thắt dấu | GIỮ artifact `chroma_db_vie/` (kích hoạt = CHỜ DUYỆT PA-1): OCR 3,3→82,3%; index 19,13→80,29% từ có dấu; chunk <5% dấu 167→2 | 342 chunk (OCR 123 trang) | — | `data/loop/diag/corpus_diagnostics/index_after.json` |
| D-14 · năng lực Gemini là nút thắt của cấu hình (b) | **MỞ**: PASS_CORRECT 16/25 = 64,0%; refusal 12,0%; 5 id thiếu đúng là 5 id cuối theo thứ tự r5 | 25/30 id | [44,0; 84,0] | `data/loop/diag/b_gemini_top6/bootstrap_ci_25.json` |
| D-16 · tổng điểm trọng số trong báo cáo đánh giá sai số học | GIỮ 7,2 (bản cũ ghi 7,4): 0,20·9,2+0,15·8,2+0,20·7,0+0,20·8,5+0,25·4,0 = 7,17 → 7,2; điểm thành phần = CHỜ DUYỆT PA-23 | 5 điểm thành phần | — | `docs/bao_cao/danh_gia_tong_quan_2026-10-23.md` |
| D-20 · ngoại suy chi phí round = chi phí riêng tầng rerank | **BÁC phương pháp**: r12 thật ≈66 phút = 4,74 s/item = 2,0 s rerank + 2,78 s truy xuất nền, vượt ngưỡng tự đặt 60 phút | 100 item | — | `data/loop/rounds/r12/round_summary_retrieval.json` |
| D-22 · driver `.sh` viết tay đủ để tái lập một round | GIỮ công cụ: chuỗi demo 2×20 item chạy end-to-end (gate + attribute); 11 test; đột biến 6/6 bắt | 2×20 item | — | `tools/loop/chains/t5a_reranker.json` |
| D-30 · người ngoài tái lập round r0 bằng một lệnh | **ĐẠT**: 811/811 item, gold@6 0,5186 = 0,5186, 0 verdict đổi chiều, 811/811 top-6 cùng thứ tự; 37,5 phút; 0 lượt Gemini; manifest dry-run = manifest thật (SHA `295413c196de`) | 811 item | — | `tmp/compare_r0_repro.json` |
| D-33 · số "79/79 đột biến bị bắt" giữ được khi tổng kết | **KHÔNG** — đếm từ 13 log: **126/126** bị bắt, 0 dòng sống sót; số cũ vừa thiếu 3 harness vừa tự mâu thuẫn | 126 đột biến | — | `docs/archive/reports/test_final.md` |
| D-37 · reranker chấm query nguyên văn (PA-25) biến lever từ âm sang dương | **CHỜ DUYỆT** (PA-35/PA-36; cờ vẫn TẮT): gold@6 0,7400→0,8357; EXACT 0,2115→0,4231 (delta +0,2116, n=52, p=0,0034); cổng ĐỎ vì neo HUMAN 0,8144→0,7629 (−6,32% tương đối, ngưỡng −5%, n=97) | 811 item | [0,0714; 0,1200] | `data/loop/rounds_v2/r16/gate_vs_r11_retrieval.json` |
| D-38 · cross-encoder phân biệt cặp có/không chunk vàng đủ mạnh (auc ≥ 0,75 trên ≥ 30 cặp) | **MAU_QUA_NHO**: mẫu chính r5 chỉ có 19 cặp eval sạch < 30 (ngưỡng không hạ); auc_ce_max 0,8643; eval_all 0,8038 (29); nhãn NEG still_answerable 45,8%; mốc hạng degenerate 0,5 | 59 cặp | — | `data/loop/diag/answerability_probe_r5.json` |
| D-39 · chỉ tính logits trên token đáp án mở thêm trần độ dài SFT | **CHỜ DUYỆT** (PA-39): tiêu chí không đạt và không bị bác — `full` không OOM tới 3.072 token (đỉnh 10.429,4 MiB trên card 4.095,5); tiết kiệm 1,764–1,894 MiB/token; dòng 1.707 token 6.238,3→3.328,3 MiB | 6 độ dài × 2 mode | — | `data/loop/diag/answer_token_logits_probe_real_fraction.json` |
| D-40 · chunk vàng có dấu (index mới) giúp Qwen 1,5B trả lời đúng hơn | **BÁC cách thiết kế phép thử** (không bác giả thuyết): 54/57 chunk vàng giống từng byte, 3 khác thật ⇒ 57/57 câu trả lời byte-identical; McNemar 0 bất đồng p=1,0 | 57 item | [0,0000; 0,0000] | `data/loop/diag/b1_cprime/analysis.json` |
| D-41 · siết hai luật trọng tài (PA-2 + PA-20) không đổi verdict round đã đóng | GIỮ trọng tài v2: 5/1000 verdict đổi chiều, 100% chặt hơn; PASS_CORRECT 148→143; refusal/fabrication không đổi | 1.000 câu × 10 round | — | `data/loop/rounds_v2/compare_v1_v2.json` |
| D-42 · máy kiểm số cuối tái lập được mọi số sau ba mục đã duyệt | **CHỜ DUYỆT** (PA-41): 63 dòng, **61 KHỚP / 2 LỆCH**, rc=0; hai lệch là kỳ vọng cũ của máy kiểm (46→51 test; chữ ký `9f1179ccab74`→`2911c69f740d`) | 63 dòng kiểm | — | `tmp/final_number_audit_b_shift.json` |
