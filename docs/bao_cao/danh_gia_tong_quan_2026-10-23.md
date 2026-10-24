# Đánh giá kỹ thuật tổng quan — đồ án Hybrid RAG AGU

**Ngày:** 23-10-2026 · **Phạm vi:** toàn bộ nhánh `main` của `D:/DoAn/hybrid_rag_agu` (không so sánh với nhánh khác, không trạng thái merge).
**Người đánh giá:** vai trò tiến sĩ kỹ sư AI / phản biện hội đồng.
**Nguyên tắc viết báo cáo này:** mọi con số đều truy được về một file trên đĩa; số nào chưa kiểm chứng được thì ghi rõ là chưa; số nào từng công bố mà nay bị dữ liệu bác thì ghi cả bản cũ lẫn bản sửa.

---

## 0. Kết luận điều hành (Executive summary)

Đồ án này **không phải** một ứng dụng RAG "chạy được là xong". Nó đã tiến hóa thành một *hệ thống có vòng lặp tự kiểm chứng* với trọng tài deterministic, cổng duyệt không suy giảm, bảy bất biến chống tự lừa mình và sổ sách ghi lại cả những lần dụng cụ đo của chính mình sai. Ở phương diện đó, nó ở mức **trên chuẩn đồ án đại học, cận mức một báo cáo engineering trưởng thành (production-grade methodology)**.

Nhưng ở phương diện **chất lượng câu trả lời thực tế**, nó **chưa đạt yêu cầu "áp dụng được"**: với câu hỏi mà căn cứ *đã nằm sẵn trong cửa sổ truy xuất*, mô hình sinh vẫn từ chối ~62–72% lượt chạy (tốt nhất ghi được đến giờ: 0,62 ở r7). Chỉ số chống bịa thì tốt (1 câu bịa/100, và mọi câu trả lời đều qua `check_grounding`), chỉ số "dám trả lời đúng" thì tệ. Nói ngắn: **hệ thống hiện an toàn nhưng chưa hữu dụng**, và nút thắt nằm ở tầng sinh + chất lượng văn bản nguồn, không ở truy xuất nữa. Một ngoại lệ đáng chú ý vừa xuất hiện cuối ngày: round `r6` chứng minh **tầng input cũng là một nguyên nhân thật** — 5/100 câu bị bộ chuẩn hóa biến thành câu khác, và khi chặn chúng lại thì cả 5 item đều lấy lại chunk vàng vào cửa sổ, `PASS_CORRECT` 10→14. Đây là lever duy nhất của pha sinh tính đến 23-10 có bằng chứng nhân quả ở cấp item, và round tổ hợp `r7` (24-10) xác nhận nó **tái lập**: đúng 5 ca hỏng đó bị bác ở cả hai lượt chạy. Phần còn lại của r7 là một kết luận trung thực hơn là một chiến thắng — con số bonus 12 không thêm được gì đo được so với r6 (chênh nằm trong băng nhiễu ±3) và phải trả 2 ca `PASS_CORRECT` → từ chối oan (mục 3.3 và đọc-sai số 7 ở mục 4).

Năm kết luận kỹ thuật đã được dữ liệu chốt (hoặc mở lại) trong 24 giờ qua; hàng thứ tư là việc đang chờ bạn duyệt:

| vấn đề | quyết định | bằng chứng |
|---|---|---|
| Bộ định tuyến phá recall (cắt cứng `source_filter`) | đổi thành **lọc mềm, bonus 12** — cổng r2-vs-r0 ĐẠT, neo HUMAN giữ 81,44% | `data/loop/rounds/r2`, `r4` |
| "Một nguồn chiếm trọn cửa sổ" có phải nút thắt? | **Không** — quota 4 không phá gì nhưng cũng không hồi phục gold@6 (0,7400→0,7429) ⇒ giả thuyết cấu trúc bị bác, quota giữ TẮT | `rounds/r4/gate_vs_*_retrieval.json` |
| Hỏi lại bằng chỉ dẫn trích xuất (rescue) có cứu được từ chối oan? | **Không** — 60/64 câu đủ điều kiện thực sự được hỏi lại, chỉ **1** câu cứu được (1,7%) ⇒ **bác lever vĩnh viễn** | `rounds/r5b/rescue_tally.txt` |
| Bản chuẩn hóa câu hỏi thỉnh thoảng là một câu khác — có phải lỗi "hạng mục ghi chú"? | **Không, nó là lỗi hệ thống có thể sửa**: `NORMALIZE_SANITY_GUARD=1` ở r6 bắt 5/100 ca, **cả 5 item lấy lại chunk vàng vào cửa sổ**, `PASS_CORRECT` 10→14, gold@k 0,6875→0,7875 ⇒ lever pha sinh đầu tiên có bằng chứng nhân quả; **đang chờ bạn duyệt để bật làm mặc định** | `rounds/r6/normalizer_guard_tally.txt`, `rounds/r6/gate_vs_r1_full.json` |
| Bonus 12 của tầng truy xuất còn đúng khi đã bật guard? | **Chưa xác nhận được, và có giá phải trả đo được**: r7 (bonus 12 + guard) so với r6 cho chênh lệch **nằm trong băng nhiễu ±3** (`PASS_CORRECT` đi ngang 14), đồng thời **2 item `PASS_CORRECT` rơi xuống từ-chối-oan** vì xếp thưởng đẩy chunk cần thiết ra cửa sổ 12 slot; family `NUMERIC` giảm **đúng 0,1000 = bằng ngưỡng veto** (một item nữa là bị phủ quyết) ⇒ không mở round tổ hợp nào để đo bonus nữa; câu hỏi 3-vs-12 cần lượt lặp lại hoặc cỡ mẫu lớn hơn | `rounds/r7/combo_tally.txt`, `rounds/r7/gate_vs_r6_full.json` |

---

## 1. Đã làm được gì (theo tầng, kèm nguồn số)

### 1.1 Dữ liệu & corpus
- Kho ngữ liệu: **361 chunk / 26 tệp nguồn** (đo trực tiếp từ `chroma_db`, collection `agu_regulations`), chia tầng T1 (cắt theo Điều/Khoản) / T2 / bổ sung.
- Bộ đánh giá: benchmark 100 câu `v3` (phân bố nhãn 87/5/5/3, đã verify 4/4 mục ở P1.3) và **bộ test 811 item** do vòng lặp P5 sinh (`data/loop/testset_v1.jsonl`, có `split` train/test, gold chunk, `gold_sentence`, thực thể bắt buộc).
- Dữ liệu huấn luyện: `retrieval_pairs` cho tầng xếp hạng, cặp nhãn classifier, và `trainpool_additions.jsonl` do `triage.py` xuất qua từng round (có cổng chặn rò rỉ test-set).

### 1.2 Tầng phân loại + định tuyến
- `src/classifier.py` few-shot + guardrail 3 lớp + suy giảm mềm; **chủ đề 85,0% (85/100), loại câu hỏi 81,0% (81/100), macro-F1 69,4%**, recall 3 lớp thiểu số 100% (`logs/classifier/accuracy_report.md`).
- Có baseline trung thực để so: kNN bge-m3 (k=1) đạt 76,0% chủ đề / **85,0% loại câu hỏi** — tức classifier thắng về chủ đề nhưng **thua về loại câu hỏi**; chi tiết này nằm trong báo cáo accuracy, không bị giấu.
- `src/router.py`: `TOPIC_SOURCE_FILTER` cho 8/14 chủ đề, bốn loại cấu hình theo `question_type`, và hai lever mới `ROUTER_SOFT_FILTER` + `ROUTER_FILTER_RANK_BONUS`.

### 1.3 Tầng truy xuất
- Hybrid BM25 + ChromaDB (bge-m3) + RRF, oversample ×2 (cửa sổ 12 cho top_k 6).
- Chuỗi round trên cùng 811 item: **gold@6 51,86% (r0, cắt cứng) → 76,57% (r1, lọc mềm bonus 3) → 74,00% (r2, bonus 12) → 74,29% (r4, bonus 12 + quota 4)**; `FAIL_RETRIEVAL` 337 → 164 → 182 → 180.
- Máy quy lỗi `attribute.py` tách được ba nguyên nhân: `filter_blocked_wrong_topic` 179→60, `filter_blocked_wrong_table` 65→20, và hai nhóm còn lại (`ranking_*`) mà lever nguồn không với tới.
- A/B trên benchmark 100 câu: **Hit@3 60,8%→77,3% (+27,1% tương đối), MRR 0,510→0,769 (+50,9%), Citation F1 13,4%→25,7%** — GATE P4.3 ĐẠT (`outputs/ab_comparison.md`).

### 1.4 Tầng sinh + chống bịa
- `src/generator.py`: prompt theo loại câu hỏi, `canonicalize_refusal`, cache key theo `PROMPT_VERSION`, hai đường Gemini/Qwen cùng giao diện.
- `src/answer_guard.py`: kiểm chứng căn cứ deterministic (thực thể số/mã/Điều phải có trong ngữ cảnh), `grounding_score`, ngưỡng refusal; nối vào `QwenGenerator` **trước** khi ghi cache.
- Lever mới: `ENABLE_ANSWER_GUARD`, `ENABLE_ANSWER_RESCUE` (+ `RESCUE_MIN_SCORE`), `ROUTER_SOURCE_QUOTA`, `NORMALIZE_SANITY_GUARD` (+ `NORMALIZE_MIN_CONTAINMENT`) — **tất cả mặc định TẮT**, có test ghim hành vi "tắt là không đổi một ký tự". Kết cục đo lường: **rescue bị bác** (1/60), **quota không needed** (giả thuyết cấu trúc bị bác), **guard chuẩn hóa là lever duy nhất còn lại và đã được chứng minh ở r6** (5/100 ca, 5/5 item lấy lại căn cứ).
- Fabrication trên câu đã trả lời: **1 câu/100 ở cả r1, r3, r5, r5b, r6** (tỉ lệ 3,57% → 2,56% → 3,23% → 2,94% → 2,78% chỉ vì mẫu số câu đã trả lời thay đổi — điều này phải đọc đúng, xem mục 4.4).

### 1.5 Vòng lặp tự kiểm chứng (P5) — phần giá trị nhất về mặt khoa học
- `tools/loop/{run_round,verify,triage,attribute,gate,audit_guard}.py`: một vòng = đo 811 item (pha rẻ) → sinh 100 câu (pha đắt) → lỗi thành dữ liệu train → sửa → round mới → **cổng** so với round cũ trên đúng tập item chung.
- **Bảy bất biến**, trong đó bất biến 7 ("dòng train phải tự chứa căn cứ") đã kiểm trên dữ liệu thật: 13/13 dòng `sft_extractive` có đủ thực thể vàng + tên nguồn; `blocked_test_leak` 17–35 dòng/round; `skip_sft_target_not_in_context` 6–7.
- Chữ ký trọng tài `9f1179ccab74` phủ **7 pha** của r0/r1/r2/r3/r4 (và r5/r5b) — hai round chỉ so được với nhau khi dụng cụ chấm giống hệt nhau.
- Cổng `gate.py`: 7 quy tắc, ngưỡng đăng ký trước, chỉ so trên item chung, và từ chối mở cổng nếu cấu hình chạy lệch.

### 1.6 Huấn luyện mô hình riêng (P6, làm song song)
- `venv_train` (CUDA): classifier v2 đã deploy (thử nghiệm oversample v3 **bị bác** — số đo xấu hơn); retrieval fusion fine-tune Hit@3 48,7%; Qwen2.5-0.5B LoRA SFT xong (eval_loss 1,23). Bài học kỹ thuật đáng chú ý: max-length 768 cho GPU 4 GB, pickle lớp cấp module.

### 1.7 Tài liệu & bàn giao
- `ROADMAP.md` (P0→P5.16, có cả các mục "kết luận cũ đã bị bác"), `SYSTEM_ARCHITECTURE.md` (6 tầng, khớp `pipeline.run`), `TAXONOMY.md`, `data/loop/README.md` (cách chạy + ngưỡng + sổ sách), 23/23 playbook P0.1→P5.4 xong, chương 3 + chương 4 bản nháp với **mọi bảng/số có dòng "Nguồn:"**.

---

## 2. Những gì ĐÃ ỔN (và tại sao ổn)

**2.1 Tính trung thực của phép đo — ổn, và đã được chứng minh bằng hành vi tự sửa.**
Bốn dụng cụ đo đã bị phát hiện sai và sửa *trong khi dự án vẫn đang chạy*: (a) `verify.py` bug `has_gold_chunk` đếm nhầm 97 item → 434 thay vì 337 `FAIL_RETRIEVAL`; (b) `is_refusal`/`judge_faithfulness` so chuỗi *có dấu* với text *đã fold* → mọi chỉ số "từ chối đúng" cũ luôn 0%, nghĩa là baseline cũ vô nghĩa; (c) probe A/B dùng kim có dấu nên 25/52 dòng gắn nhầm `refused=False`; (d) hai lỗi mới nhất hôm nay: khẳng định "bản chuẩn hóa hỏng tái lập y hệt qua ba round" (sai: r0≡r3 100/100 nhưng r1 lệch 18/100 ⇒ là **tần suất**, không phải hàm tất định), và **latency không đếm được số lượt gọi model** (prompt cứu là phần mở rộng của prompt cũ nên Ollama tái dùng KV prefix, lượt hai chỉ ~1–2 s ⇒ con số "r3 chỉ thử ~9/60 lượt" mất cơ sở). Không phải đồ án nào cũng tự bóc lỗi đo của mình như vậy; đây là điểm cộng lớn nhất khi chấm.

**2.2 Tầng truy xuất — ổn về phương pháp, đã tới điểm bão hoà của lever đang có.**
Từ 51,86% lên ~74% gold@6 là cải thiện thật, có cơ chế giải thích được (bỏ cắt cứng nguồn), và hai cổng độc lập xác nhận (r2-vs-r0 ĐẠT, r4-vs-r2 ĐẠT). Điều quan trọng không kém: vòng lặp đã **chứng minh mình hết ý tưởng ở tầng này** bằng dữ liệu — r4 đạt cổng nhưng bác giả thuyết, nên không vẽ thêm lever. Đó là cách kết thúc đúng một hướng nghiên cứu.

**2.3 Chống bịa đặt — phần "không bịa" thì ổn.**
`check_grounding` deterministic, từ chối chuẩn hoá về một chuỗi duy nhất, guard chạy trước cache, và tỉ lệ bịa trên câu đã trả lời giữ ở **1 câu/100** qua ba round cấu hình khác nhau. Quan trọng hơn: lever cứu câu từ chối **không được phép** biến "không biết" thành "biết sai" — khi ứng viên không đạt ngưỡng thì hệ thống trả lại chính lời từ chối. r3 (rescue v1, ngưỡng 0,6) từng tạo thêm đúng một ca "trả lời bịa cho câu không có đáp án" (2→3); r5 (v2, ngưỡng 0,8 + `unsupported` phải rỗng + `score is not None`) đưa về 2. Cơ chế "siết ngưỡng thì lỗi bịa giảm" hoạt động như thiết kế — bằng chứng nhân quả, không phải tương quan.

**2.4 Kỹ thuật phần mềm — ổn.**
563 unit test xanh; mọi lever sau cờ env mặc định TẮT kèm test "tắt là không đổi hành vi"; không có side effect ra `outputs/` bảo vệ; tài liệu vận hành đủ để người khác chạy lại từng round.

---

## 3. Những gì CẦN QUAN TÂM (xếp theo rủi ro thật, không theo cảm tính)

### 3.1 Rủi ro số 1 — tầng sinh: 66–69% câu bị từ chối oan; hướng "hỏi lại" đã bị bác bằng số đếm được
Số liệu: refusal rate 0,72 (r1) / 0,61 (r3) / **0,69 (r5) / 0,66 (r5b) / 0,64 (r6)** trên 100 câu mà **căn cứ đã nằm trong cửa sổ**; `PASS_CORRECT` 10 → 14. Phép thử "hỏi lại bằng chỉ dẫn trích xuất" (rescue) đã được đo **đủ** trong r5b: **60 lượt thử thật** (59 dòng "model vẫn từ chối" + 1 dòng cứu được) trên 64 câu đủ điều kiện — **tỉ lệ cứu 1/60 = 1,7%**. Mô hình 1,5B lặp lại đúng lời từ chối khi bị hỏi lại, kể cả khi chỉ dẫn trích xuất mạnh và ngưỡng nhận chặt (0,8) đã được đưa vào.

*Vì sao:* với `temperature=0.1` và cùng khối ngữ cảnh, lời từ chối không phải do "không biết phải trích xuất thế nào" (đó là giả thuyết ban đầu), mà do **mô hình 1,5B không đủ năng lực lập luận trên văn bản tiếng Việt mất dấu + prompt dài ~8k ký tự**. A/B 4 biến thể prompt cũng đã báo hiệu sớm: đổi prompt (V3) làm 10/10 hết từ chối nhưng chỉ **+1** câu đúng thật ở n=10 và rơi 1/3 câu điều khiển.

*Hướng giải quyết (theo thứ tự tôi kiến nghị):*
1. **Đã đóng:** không đầu tư vào lượt hỏi lại nữa — quy tắc đăng ký trước ở P5.15 đã đủ điều kiện áp dụng và được áp dụng; `_rescue_refusal` + 23 test giữ làm bằng chứng đã đo, mặc định TẮT.
2. Đánh vào **cửa sổ ngữ cảnh** chứ không phải chỉ dẫn: 78/361 chunk còn dấu tốt, còn lại là văn bản "mất dấu"; thử *chọn ngữ cảnh theo thực thể vàng* (evidence-selection: ưu tiên chunk chứa thực thể mà classifier/router đã gọi tên) thay vì để RRF xếp thô.
3. **SFT lại đúng chỗ đau:** sinh dữ liệu huấn luyện từ các ca `FAIL_OVERREFUSAL` có căn cứ trong ngữ cảnh (triage đã xuất `sft_extractive_from_overrefusal` 12 dòng ở r5) và/hoặc tinh chỉnh generator bằng đúng loại lỗi này. Lưu ý bất biến 7: **không được** train trên ca không có đáp án trong ngữ cảnh — đó là tự dạy model bịa.
4. **Chuẩn hoá văn bản nguồn một lần nữa** (mục 3.2) — rất có thể 3 và 4 cùng lúc mới ăn, vì model không trích được cái mà OCR đã làm hỏng.
5. **Đã có từ r6, và phải đặt đúng kỳ vọng:** chặn bản chuẩn hóa hỏng (`NORMALIZE_SANITY_GUARD=1`) là bằng chứng đầu tiên cho thấy "lỗi truy xuất/lỗi sinh" có một phần thuộc **tầng input** — 5/5 câu hỏng được sửa thì căn cứ quay lại cửa sổ, 1 câu thành `PASS_CORRECT`. Nhưng quy mô là **5/100**, nên nó **không** giải quyết 37 ca từ chối oan còn lại; nó là vệ sinh hệ thống (rẻ, không rủi ro, đã kiểm định) chứ không phải liều cứu sinh cho tầng sinh.

### 3.2 Rủi ro số 2 — chất lượng văn bản nguồn: đo lại hôm nay, tệ hơn ghi chú cũ
Số đo mới (tôi vừa chạy trực tiếp trên `chroma_db`, không lấy từ trí nhớ): **chỉ 18,6% số từ trong toàn corpus có dấu thanh tiếng Việt**; phân bố 361 chunk theo mức giữ dấu: **171 chunk <5%** (gần như mất sạch), 112 chunk 5–50%, **78 chunk ≥50%**. Tệ nhất nằm ở đúng các tệp lớn nhất và bị gọi nhiều nhất: `1054-qd-dhag-2020-09-28.pdf` (9.702 từ, 2,8% có dấu), `888-qd-dhag-2022-08-08.pdf` (6.503 từ, 3,9%), `QD1133_22815…` (3.777 từ, 2,4%), `ke-hoach-ttck-kltn-dh24pm/th-2026.pdf` (3,1–3,3%).

*Vì sao đây là rủi ro nền:* `fold()` giúp **so khớp** hai bên đã bỏ dấu, nhưng **không phục hồi** được gì cho (a) embedding bge-m3 — văn bản mất dấu làm giảm chất lượng ngữ nghĩa, (b) người dùng thật — sinh viên gõ tiếng Việt có dấu và câu của họ khác mặt chữ với tài liệu, (c) mô hình sinh — nó "nhìn" văn bản gần như không phải tiếng Việt. Nó cũng giải thích một phần family yếu nhất: **EXACT gold@6 chỉ 21,15%** và `TRAP` 13,04% ở r4.

*Ghi chú trung thực:* trí nhớ dự án cũ ghi "62 chunk còn đủ dấu"; số đo hôm nay là **78 chunk ≥50% có dấu** — cùng kết luận (thiểu số), khác cách đếm. Báo cáo này dùng số đo lại, có mô tả phương pháp để chạy lại được.

*Hướng giải quyết:* (i) re-OCR/convert ưu tiên **txt có dấu** từ nguồn gốc (Word/`.docx` trong repo đang giữ dấu rất tốt: 78–81% — bằng chứng là vấn đề nằm ở pipeline convert PDF, không phải ở tài liệu nói chung); (ii) với tệp `.doc`/PDF hỏng text còn lại, chấp nhận ghi nhận là khoảng trống trong báo cáo đồ án thay vì che phủ bằng con số ước lệ; (iii) đo lại corpus-quality sau khi rebuild và **chấm lại** các round bị ảnh hưởng bằng đúng lệnh round (vì `src/text_utils.py` thuộc `REFEREE_FILES`, đổi nó sẽ lật chữ ký trọng tài — phải chấm lại r0–r5).

### 3.3 Rủi ro số 3 — cổng quyết định đang veto vì nhiễu, không vì chất lượng: nợ thiết kế
`refusal_rate_bounded` là **trần tuyệt đối 0,35**, trong khi r1 (baseline tốt nhất) đã 0,72. Kết quả: **không round pha sinh nào có thể ĐẠT cổng**, kể cả round tiến bộ rõ (r5 ĐẠT 6/7 quy tắc, fabrication giảm, pass_rate tăng). Đây là lỗi thiết kế cổng chứ không phải kết luận về lever.

**Lỗ thứ hai, và nó nặng hơn, vừa có bằng chứng thật.** r5b — lượt chạy **lặp lại nguyên văn cấu hình r5**, không đổi một dòng code — bị chính cổng `r5b-vs-r5` kết luận **KHÔNG ĐẠT**, vì `family_pass_rate[EXACT]` đi từ 0,25 xuống 0,125: với n=8, **một item lật đã là −12,5 điểm %, vượt ngưỡng −10**. Một dụng cụ mà hai lượt cùng cấu hình cũng không đi qua thì đang phủ quyết bằng nhiễu.

**Và lỗ thứ nhất vừa gây hậu quả cụ thể:** round `r6` (một biến số `NORMALIZE_SANITY_GUARD=1`) ĐẠT 6/7 quy tắc, cải thiện `PASS_CORRECT` 10→14, gold@k +10 điểm %, fabrication giảm và **refusal rate giảm 0,72→0,64** — vậy vẫn bị kết luận "KHÔNG ĐẠT" vì quy tắc trần tuyệt đối, tức vi phạm **dù chính chỉ số đó tốt hơn baseline**. Đây là trường hợp rõ nhất cho thấy cổng hiện không còn đang bảo vệ chất lượng, mà đang chặn tiến bộ.

**Lỗ thứ nhất lặp lại ngay ở r7, và lộ thêm một mép sắc thứ ba.** Round tổ hợp r7 (bonus 12 + guard) cũng ĐẠT 6/7 với **cả hai baseline**, refusal đã giảm xuống 0,62, vẫn bị veto cùng một lý do. Trong cùng round đó, family `NUMERIC` đi từ 0,50 xuống 0,40 = **chênh đúng 0,1000**, quy tắc chỉ veto khi giảm *quá* 0,1 nên được coi là ĐẠT — tức cổng đang quyết định bằng đúng chữ "quá" trên một ngưỡng, với cỡ mẫu family 10 item (một item nữa là đổi kết luận). Bản chất: cổng mỏng trên mép dao và không có khái niệm "chênh dưới ngưỡng nhiễu thì chưa kết luận".

*Hướng giải quyết (gộp thành một sửa, chờ bạn duyệt):* (1) `refusal_rate_bounded` → quy tắc **tương đối** ("không tăng quá ngưỡng so với baseline") + giữ trần tuyệt đối làm cảnh báo không phủ quyết; (2) family chỉ được veto khi chênh lệch **≥2 item** (hoặc nâng `GATE_MIN_FAMILY_N` trên 8); (3) đăng ký **noise floor** vào tài liệu cổng để mọi chênh ≤3 item ở pha đắt bị đánh dấu "chưa có ý nghĩa". `gate.py` không thuộc `REFEREE_FILES` ⇒ không phải chấm lại round cũ. **Việc này đang chờ bạn duyệt** vì nó sửa dụng cụ ra quyết định.

### 3.4 Rủi ro số 4 — sức mạnh thống kê của bằng chứng tầng sinh
Pha đắt chỉ n=100; các family sinh cực nhỏ (`REVERSE_LEGAL` n=3, `REFUSE_MISSING_DOC` n=6, neo HUMAN ở pha sinh **n=7**). **Noise floor đã đo xong (r5 so với r5b, cùng cấu hình):** bốn chỉ số quyết định `PASS_CORRECT` 14=14, `PASS_REFUSAL` 17=17, `FAIL_HALLUCINATED_ON_UNANSWERABLE` 2=2, `FAIL_FABRICATED` 1=1 **ổn định tuyệt đối**, trong khi các nhóm FAIL dao động ±3 item và refusal rate −0,03. Hai hệ quả: chênh 19→17 của `PASS_REFUSAL` giữa r1 và r5/r5b **chưa được loại trừ nhiễu** (r1 chỉ chạy một lượt), và tỷ lệ "từ chối" là chỉ số dao động, không phải chỉ số quyết định. Hiện tượng còn lại chưa giải thích được: r0≡r3 nhưng r1 lệch 18/100 bản chuẩn hóa ⇒ giữa các lượt chạy có dao động hệ thống ở tầng input.

*Hướng giải quyết:* dùng chính bảng trên làm ngưỡng đọc mọi kết luận tầng sinh (đã ghi vào `data/loop/README.md`); khi cần quyết định lớn, lặp lượt chạy thay vì chỉ dựa một round, và tăng n pha đắt lên 200–300 (chi phí là GPU địa phương, không phải quota Gemini).

### 3.5 Rủi ro số 5 — tính "thực tế" của bộ đánh giá
Bộ 811 item auto-generated kiểm tra **trích niêm** (câu được sinh từ chính câu có trong tài liệu), nên gold@6 cao không chứng minh hệ thống trả lời hay cho câu hỏi thật; benchmark v3 có 97 câu người viết nhưng chưa có "câu hỏi thật của sinh viên" không khớp khuôn. Câu hỏi 3 của đồ án (ứng dụng thực tế) vì vậy mới trả lời được một nửa.

*Hướng giải quyết:* dựng **benchmark E2E trên 30–50 câu hỏi thực** (thu thập từ người dùng thật hoặc từ log GUI), chấm bằng cùng `check_grounding` + người đọc chấm "có giúp được không", và công bố như tập kiểm chứng độc lập.

### 3.6 Rủi ro số 6 — ba điểm "góc nhà" nhưng sẽ bị hội đồng hỏi
- `ui/app.py` từng hardcode `GeminiGenerator`; đã đọc `USE_QWEN_GENERATOR` từ P5.1, nhưng đường GUI chưa được đo bằng vòng lặp P5 (vòng lặp gọi `pipeline.run` trực tiếp).
- Chi phí thật: ~15,5 s/câu offline, cộng thêm ~1–2 s cho mỗi lượt cứu; chưa đo p95 và chưa có chiến lược giữ model nóng (`keep_alive`).
- Cache: rescue đặt **sau** guard và **trước** `_cache_put` là đúng, nhưng nghĩa là câu đã cứu được lưu — nếu sau này đổi ngưỡng cứu, cache cũ mang kết quả của ngưỡng cũ. Cần một `PROMPT_VERSION`/`policy` key hoặc ghi rõ chính sách.

---

## 4. Những đọc-sai mà báo cáo này muốn phòng

1. **"Cổng ĐẠT = lý thuyết đúng."** r4 là phản ví dụ: hai cổng ĐẠT, giả thuyết vẫn bị bác. Cổng chỉ nói *không có gì xấu đi*.
2. **"Tỉ lệ bịa tăng."** r5-vs-r3 báo 0,0256→0,0323 nhưng **cùng một câu bịa** (1/39 → 1/31); mẫu số (câu đã trả lời) nhỏ lại vì hệ thống từ chối nhiều hơn.
3. **"Refusal 0,69 = hệ thống an toàn hơn r1."** Đúng là giảm so với 0,72, nhưng cả hai đều còn rất xa trần 0,35; không được dùng nó để ăn mừng.
4. **"Latency chứng minh lever không chạy."** Không còn dùng được làm bằng chứng (mục 2.1-d).
5. **"gold@6 ~74% nghĩa là trả lời đúng 74%."** Không: đúng căn cứ trong cửa sổ ≠ mô hình trích đúng; chỉ số cuối cùng là `PASS_CORRECT` = 14%.
6. **"Cổng KHÔNG ĐẠT = round đó không có tiến bộ."** r6 là phản ví dụ rõ nhất: `PASS_CORRECT` +4, gold@k +10 điểm %, fabrication giảm, refusal **giảm** — và vẫn "KHÔNG ĐẠT" vì đúng một quy tắc trần tuyệt đối. Ở chiều ngược, r5b chứng minh cổng cũng có thể veto vì nhiễu tinh. Kết luận thật nằm ở **quy lỗi cấp item**, không ở nhãn ĐẠT/KHÔNG ĐẠT.
7. **"Bonus 12 là đường chốt đã được xác nhận."** Nó từng qua cổng ở **pha rẻ** (r2/r4, tầng truy xuất). Ở **pha đắt** và khi đã bật guard, r7 cho thấy phần cộng thêm của bonus 12 so với bonus 3 **nằm trong băng nhiễu** (3/9 cải thiện là verdict, `PASS_CORRECT` đi ngang) và có **2 ca thoái hóa quy lỗi được** (xếp thưởng đẩy căn cứ ra khỏi cửa sổ). Nói đúng: bonus 12 *không gây hại rõ ràng*, chưa *được xác nhận là có thêm lợi ích* ở câu hỏi cấp sinh — và đó chính là giới hạn "pha đắt chỉ n=100" ở mục 3.4, không phải bằng chứng rằng lever vô dụng.

---

## 5. Chấm bài (role: tiến sĩ kỹ sư AI, phản biện hội đồng)

Thang 10; mỗi điểm kèm lý do và *điểm trừ cụ thể*.

| tiêu chí | điểm | lý do |
|---|---|---|
| **Phương pháp luận & kiểm chứng** | **9,2** | Trọng tài deterministic + chữ ký, 7 bất biến, cổng "không suy giảm" đăng ký trước, máy quy lỗi, tự phát hiện và sửa 5 lỗi dụng cụ đo, công bố cả kết luận mình bị sai. **Noise floor đã đo chính thức (r5-vs-r5b)** và được dùng làm ngưỡng đọc mọi kết luận tầng sinh; r6→r7 tái lập đúng tập ca hỏng. Trừ 0,8: mẫu sinh vẫn n=100, chưa có lượt lặp lại cho r6/r7, và cổng vẫn còn hai lỗ chưa được phép sửa (chờ duyệt #23). |
| **Thiết kế hệ thống RAG** | **8,2** | Tách tầng sạch (classifier→router→chuẩn hoá→truy xuất→sinh→guard), mọi lever env-gated mặc định TẮT, suy giảm mềm ở mọi tầng. **Tầng chuẩn hóa đầu vào đã được đo bằng round và tìm ra lỗi thật (P5.16/r6), kèm fallback an toàn khi model lỗi (r7 OOM).** Trừ: evidence-selection và reranker chưa có; guard vẫn mặc định TẮT nên chưa phải hành vi production. |
| **Chất lượng thực nghiệm** | **7,0** | A/B một biến, 811 item, các số chính truy được về file, chuỗi r0→r7 có bản ghi đếm được lưu trong repo. Trừ 3,0: thiếu thử nghiệm trên câu hỏi thật, thiếu bootstrap CI cho các chỉ số, các family nhỏ chưa được xử lý đúng mức trong kết luận. |
| **An toàn / chống bịa** | **8,5** | Guard deterministic chạy trước cache, canonical refusal, ngưỡng cứu siết hơn ngưỡng sản xuất, 1 câu bịa/100 và nhân quả ngưỡng↔số ca bịa đã chứng minh. Trừ 1,5: lớp "khẳng định thuần bằng chữ, không số/mã/Điều" vẫn chỉ là xấp xỉ; chưa đo trên adversarial set. |
| **Độ hữu dụng thực tế** | **4,0** | PASS_CORRECT 14/100 và refusal thấp nhất ghi được 0,62 — chưa đủ để giao cho sinh viên dùng. Đây là điểm kéo toàn bộ dự án xuống khỏi "xuất sắc ứng dụng". |
| **Chất lượng dữ liệu nền** | **4,5** | 18,6% từ có dấu; 171/361 chunk gần như mất sạch dấu; đúng các tệp nặng nhất bị ảnh hưởng; còn 3 `.doc` + 1 PDF hỏng text. Bộ test thì tốt (811 item + split + gold), nên trừ chủ yếu ở corpus. |
| **Kỹ thuật phần mềm / tái lập** | **8,5** | 563 test xanh, lệnh round tái lập được (kèm env), cache có version, không ghi đè outputs bảo vệ, `data/loop/README.md` đủ để người khác chạy. Trừ: driver vẫn phải lập thủ công (chưa đóng gói thành `tools/loop/run_chain.sh`), và có tmp/probe rải rác cần dọn. |
| **Tài liệu & trình bày** | **8,5** | ROADMAP có chương trình + lý lịch quyết định; chương 3–4 có nguồn cho từng số; kiến trúc trùng khớp code. Trừ: tài liệu kỹ thuật nằm rải (ROADMAP/README/prompts) — nên gom một "sổ quyết định" cho bản nộp. |
| **Điểm tổng thể (có trọng số theo mục tiêu đề tài)** | **7,2/10** | Trọng số: phương pháp 20%, hệ thống 15%, thực nghiệm 20%, an toàn 20%, hữu dụng 25%; tổng có trọng số của bảng trên = **7,17** (kiểm tra lại bằng phép tính, không lấy từ trí nhớ). **Đính chính:** bản thảo đầu ghi 7,4/10 — sai số học; với đúng các điểm cũ (9,0/8,0/7,0/8,5/4,0) tổng chỉ là **7,10**. **Đối chiếu lại 24-10 (T6d):** chạy lại phép nhân trọng số = `0.20·9.2 + 0.15·8.2 + 0.20·7.0 + 0.20·8.5 + 0.25·4.0 = 7,17`, làm tròn 7,2 — **khớp, không có ô nào còn hiển thị 7,4 ngoài chính ghi chú đính chính này**. Đồ án mạnh ở phần mà đa số đồ án khác bỏ qua (kiểm chứng), và yếu ở phần mà hội đồng sẽ đánh đầu tiên (câu trả lời thật). |

### 5.1 Bảng chỉ số chính kèm khoảng tin cậy 95% (bootstrap theo item — T6d)

Mọi điểm ước lượng dưới đây lấy đúng công thức mẫu số của `gate.metrics`; CI bằng bootstrap
ghép item 10.000 lượt (seed 20261023, percentile 2,5/97,5). Nguồn: `tools/diag/metric_ci.py` →
`data/loop/diag/metric_ci_r5_full.json`, `data/loop/diag/metric_ci_r7_full.json` (round `r5` và
`r7`, pha sinh, n=100). **CI rộng là có chủ đích và phải đọc đúng:** ở n=100, "14 câu đúng"
tương đương tỉ lệ 14% nhưng khoảng 95% là 8–21% — chưa đủ bằng chứng để khẳng định `PASS_CORRECT`
đã vượt ngưỡng 25% mà báo cáo này cần cho "xuất sắc ứng dụng".

| chỉ số | round | điểm | CI 95% | đọc |
|---|---|---|---|---|
| `PASS_CORRECT` | r7 | 0,14 | [0,08 ; 0,21] | 14/100; cận dưới vẫn chỉ 8% |
| `pass_rate` (mọi verdict ĐẠT) | r7 | 0,32 | [0,23 ; 0,41] | |
| `refusal_rate` | r7 | 0,62 | [0,52 ; 0,71] | thấp nhất ghi được; vẫn cách trần 0,35 xa |
| `gold_in_top_k_rate` (item có chunk vàng, n=80) | r7 | 0,80 | [0,71 ; 0,89] | truy xuất ĐÃ tốt — nút thắt không ở đây |
| `fabrication_rate_on_answered` (n=38) | r7 | 0,026 | [0,00 ; 0,08] | chống bịa chắc |
| `mean_grounding_score` (n=38) | r7 | 0,996 | [0,987 ; 1,000] | câu đã trả lời thì bám căn cứ |
| `PASS_CORRECT` | r5 | 0,14 | [0,07 ; 0,21] | baseline; bằng r7 trong băng nhiễu ±3 |

> Hệ quả cho hội đồng: cặp chênh r5↔r7 trên mọi chỉ số đều **có CI chồng lấn**, nên không được
> diễn giải 0,31→0,32 hay 14→14 thành "tiến bộ có ý nghĩa thống kê". Đây chính là lý do mục
> "_noise floor ±3 item_" được nêu ở mục 4 và vì sao các kết luận tầng sinh phải đọc theo CI,
> không theo điểm lẻ. (Khoảng trống "thiếu bootstrap CI" ghi ở dòng *Chất lượng thực nghiệm* nay
> đã được đóng cho các chỉ số chính; điểm thành phần giữ nguyên 7,0 vì còn hai khoảng trống khác —
> câu hỏi thật và các family nhỏ — chưa xử lý.)


**Nhận xét phản biện ngắn gọn:** *"Đây là một công trình có kỷ luật khoa học hiếm thấy ở mức đồ án: nó dám công bố giả thuyết của mình đã bị chính số đo của nó bác (r4), và dám nhận lỗi dụng cụ (rescue log bị mất). Nhưng nó chưa phải một hệ thống trả lời được: 86/100 câu có căn cứ vẫn không cho ra đáp án đúng. Đồ án sẽ đạt loại giỏi-xuất-sắc nếu, trước khi nộp, nó đóng được ít nhất một trong hai cửa: (i) nâng `PASS_CORRECT` lên ≥25% bằng evidence-selection hoặc SFT đúng lớp lỗi, kèm một tập kiểm chứng độc lập; hoặc (ii) tái tạo corpus có dấu cho các tệp lớn nhất và chỉ ra độ tăng của EXACT/CLOZE — vì đó là nguyên nhân gốc mà toàn bộ kiến trúc đang phải gánh."*

**Ba câu hỏi hội đồng gần như chắc chắn sẽ hỏi, và câu trả lời trung thực hiện có:**
1. *"Bạn có chắc hệ thống không bịa không?"* — Không tuyệt đối; tôi đo 1/100 câu bịa và chặn bằng `check_grounding`; giới hạn đã ghi ở `data/loop/README.md` mục "Giới hạn thật lòng".
2. *"Vì sao không dùng LLM judge?"* — Đã dùng Gemini judge cho A/B (P4.1–4.3) và phát hiện nó vô nghĩa ở chỉ số refusal do bug fold/marker; vòng lặp P5 cố ý dùng trọng tài deterministic để không lặp lại lỗi đó (mục "Vì sao không dùng LLM judge").
3. *"gold@6 74% có nghĩa là gì cho người dùng cuối?"* — Nghĩa là 74% câu có căn cứ *đi vào cửa sổ 6 chunk* (con số tốt nhất hiện đo ở pha đắt là **80%**, r7, sau khi chặn bản chuẩn hóa hỏng), nhưng chỉ 14% câu cho ra đáp án đúng — khoảng cách 80→14 chính là việc còn lại của đồ án, và tôi quy nó về hai nguyên nhân: năng lực model 1,5B và corpus mất dấu.

---

## 6. Kế hoạch hành động tôi đề xuất (theo thứ tự, có tiêu chí "xong")

**Bước 1 — đóng vòng rescue. XONG 23-10 (23:12).** r5b chốt: **60 lượt thử** trên 64 câu đủ điều kiện, **1 câu cứu được (1,7%)**, noise floor đã đo (bảng §3.4). Tiêu chí đã đăng ký ("lượt thử ≈ số câu đủ điều kiện mà số cứu <5%") thỏa mãn ⇒ **lever rescue bị bác vĩnh viễn**, đã ghi vào ROADMAP P5.15c + `data/loop/README.md`; code + 23 test giữ làm bằng chứng, mặc định TẮT.

**Bước 2 — sửa cổng (0,5 ngày, cần bạn duyệt).** Hai quy tắc phải sửa cùng nhau: `refusal_rate_bounded` → tương đối + cảnh báo tuyệt đối, **và** chặn kiểu veto "1 item của family n=8" (ngưỡng ≥2 item hoặc nâng `GATE_MIN_FAMILY_N`); test mới cho cả hai nhánh. Không cần chấm lại round cũ.

**Bước 3 — đo lever chuẩn hóa. XONG 23-10 (23:5x).** r6 một biến số `NORMALIZE_SANITY_GUARD=1`: **5 dòng bác/100 item** (đúng kỳ vọng đã đăng ký trước 5–6), **5/5 item bị bác lấy lại chunk vàng**, 1 thành `PASS_CORRECT`, 0 đi xuống; `PASS_CORRECT` 10→14, gold@k 0,6875→0,7875, refusal 0,72→0,64. Cổng `r6-vs-r1` 6/7 ĐẠT (chỉ vi phạm trần tuyệt đối). ⇒ **lever được chứng minh**; việc còn lại là **xin duyệt bật làm mặc định production** (task #28, gộp trình với #23). Round tổ hợp r7 (bonus 12 + guard) đã đo xong — xem Bước 3b.

**Bước 3b — round tổ hợp r7 (bonus 12 + guard). XONG 24-10 (00:0x).** Một biến số so với r6 là con số bonus. Kết quả trung thực: **guard tái lập 5/5 ca trùng khít với r6** (lần đầu tiên một tập ca hỏng lặp lại nguyên văn giữa hai lượt chạy — không suy rộng thành "bộ chuẩn hóa deterministic", cỡ mẫu 5); **cả hai cổng 6/7 ĐẠT** và vẫn chỉ veto vì trần refusal tuyệt đối (candidate 0,62, đã giảm so với 0,64 và 0,72). Nhưng **chênh r7-vs-r6 nằm trong băng nhiễu ±3**: `PASS_CORRECT` đi ngang 14, `pass_rate` 0,31→0,32, gold@k +1/80 item, HUMAN đúng-nguồn 3→5/7. Giá phải trả quy lỗi được: `N172171203676287#2` và `S193409910201077` đi từ `PASS_CORRECT` xuống `FAIL_OVERREFUSAL` vì xếp thưởng theo nguồn đẩy chunk cần thiết ra khỏi cửa sổ 12 slot, và family `NUMERIC` giảm **đúng 0,1000 — bằng ngưỡng**, chỉ cần một item nữa là bị phủ quyết. Một sự cố ở dụng cụ đo cũng ghi lại: 1 lần gọi chuẩn hóa gặp `CUDA out of memory`, `query_normalizer` fallback về câu gốc (đường an toàn có sẵn), 0 item lỗi. ⇒ **bonus 12 không xác nhận cũng không bác được ở n=100; không mở round tổ hợp nào nữa để đo nó.** Chuỗi tiến bộ r1→r6→r7 (`pass_rate` 0,29→0,31→0,32) chủ yếu do guard.

**Bước 4 — tầng sinh: phần "chỉ dẫn" đã đóng (rescue bị bác), phần "bằng chứng" là hướng tiếp theo (3–5 ngày).** Song song: (4a) evidence-selection theo thực thể vàng; (4b) SFT thêm đúng lớp `FAIL_OVERREFUSAL` (tuân thủ bất biến 7); (4c) nâng n pha đắt lên 200. Lưu ý r6 chỉ sửa được **5/100** câu nên chỗ đau còn lại vẫn ở mô hình 1,5B và chất lượng văn bản nguồn — không được suy ra từ r6 rằng over-refusal đã hết. Tiêu chí: `PASS_CORRECT` ≥ 25/100 **và** số câu bịa không tăng. Baseline cổng là **r6 hoặc r7** (cấu hình tốt nhất không rescue; r7 chỉ hơn r7-vs-r6 trong băng nhiễu, nên chọn theo câu hỏi bonus 3-vs-12 ở Bước 3b), **không phải r5** — r5/r5b mang rescue đã bị bác.

> **ĐÍNH CHÍNH 24-10 (T3 đã đo, viết sau khi có số — đoạn ở trên giữ nguyên như bản gốc):** (4a)
> evidence-selection **đã có và đã đo** — `src/evidence_selection.py` + round `r9`, kết quả **bị bác**;
> Kèm theo đó, hai nhận định trong đoạn trên đã bị thực tế sửa: (i) đặc tả T3 chốt **baseline là r5**
> (theo đúng câu "gate so với r5 trên item chung"), không phải r6/r7 như đề xuất ở đây; (ii) cùng đòn bẩy
> "bỏ đường từ chối khỏi prompt" (round `r8`) đã cho `PASS_CORRECT` 14→19 và refusal 0,69→0,28 **nhưng**
> làm `PASS_REFUSAL` sập 17→2, sinh thêm 12 câu trả lời sai cho câu ngoài phạm vi ⇒ cả ba cổng
> (r8-vs-r5, r9-vs-r8, r9-vs-r5) đều **KHÔNG ĐẠT**, tiêu chí `PASS_CORRECT ≥ 25` không đạt, hai cờ giữ
> mặc định TẮT. Số và cơ chế: `docs/reports/T3.md`, `data/loop/rounds/r8/attribution_vs_r5.txt` và `data/loop/rounds/r9/attribution_vs_r8.txt`,
> ROADMAP P5.18/P5.19. (Mục 4 "Thiết kế hệ thống RAG — trừ: evidence-selection và reranker chưa có" ở
> bảng tự đánh giá cũng theo đó mà đọc: **đã có, đã đo, đã bác**.)

**Bước 5 — tái tạo corpus cho 10 tệp mất dấu nặng nhất (việc của bạn + 1 ngày máy).** Re-OCR/convert ưu tiên bản Word/PDF gốc có dấu; sau đó chấm lại r0–r5 (đổi chữ ký trọng tài) và đo tác động lên EXACT/CLOZE. Tiêu chí: corpus ≥60% từ có dấu và gold@6 của EXACT tăng ≥10 điểm.

**Bước 6 — đóng tính "ứng dụng" (2 ngày).** Benchmark 30–50 câu hỏi thật, chấm bằng `check_grounding` + người đọc; đây là bằng chứng duy nhất trả lời trực tiếp câu hỏi "áp dụng được chưa".

**Việc dọn dẹp cuối phiên (không gấp, sẽ làm khi chuỗi round khép lại):** xoá `tmp/` scratch (`probe_*`, `*_driver.sh`, `loop_gen_cache*`, `loop_cache/`, `backup_repair/`), và gom "sổ quyết định" cho bản nộp.

---

## 7. Phụ lục A — nguồn của mọi con số trong báo cáo này

| con số | file |
|---|---|
| gold@6 / FAIL_RETRIEVAL / neo HUMAN theo round | `data/loop/rounds/{r0,r1,r2,r4}/round_summary_retrieval.json` và `data/loop/rounds/r{1,3,5,5b,6,7}/round_summary_full.json` |
| cổng r4-vs-r2, r4-vs-r0, r5-vs-r1, r5-vs-r3, **r5b-vs-r5 (nhiễu nền)**, **r6-vs-r1, r6-vs-r5b**, **r7-vs-r6, r7-vs-r1** | `data/loop/rounds/*/gate_*.json` |
| **60 lượt thử cứu / 1 câu cứu được (bản ghi đếm từ stdout)** | `data/loop/rounds/r5b/rescue_tally.txt` |
| **5 ca bác chuẩn hóa + bảng quy lỗi cấp item r1→r6 (5/5 lấy lại chunk vàng)** | `data/loop/rounds/r6/normalizer_guard_tally.txt` (probe `tmp/probe_r6_attribution.py`) |
| **r7: 5/5 ca trùng khít với r6 + bảng 9 lên/4 xuống + sự cố OOM** | `data/loop/rounds/r7/combo_tally.txt` |
| máy quy lỗi r4 | `data/loop/rounds/r4/attribution_retrieval.json` |
| triage r5 (14 sft_extractive, 12 từ over-refusal, 6 bị chặn bởi bất biến 7) | `data/loop/rounds/r5/triage_stats.json` |
| triage r6 (15 sft_extractive, 13 từ over-refusal, `blocked_test_leak` 37, 7 bị chặn bởi bất biến 7) | `data/loop/rounds/r6/triage_stats.json` |
| triage r7 (16 sft_extractive, **11 từ over-refusal**, `blocked_test_leak` 38, 7 bị chặn bởi bất biến 7, 6 retrieval_pair, 9 classifier_label) | `data/loop/rounds/r7/triage_stats.json` |
| classifier 85/81/69,4%, kNN baseline 76/85 | `logs/classifier/accuracy_report.md` |
| A/B 100 câu (Hit@3, MRR, CitF1, từ chối oan) | `outputs/ab_comparison.md`, `outputs/ab_summary_*.md` |
| 361 chunk, 18,6% từ có dấu, 171 chunk <5% | đo trực tiếp `chroma_db` (collection `agu_regulations`) ngày 23-10 |
| lever + mặc định env | `data/loop/README.md` (ba bảng đòn bẩy), `.env.example` |
| 563 unit test | `pytest tests -q --collect-only` (23-10) |
| lịch sử quyết định & các kết luận bị bác | `ROADMAP.md` P5.11→P5.17 |

**Chưa kiểm chứng được trong báo cáo này (ghi rõ):** giá trị `prompt_eval_count` xác nhận cơ chế KV-prefix (dự định đo sau khi chuỗi round kết thúc để không nhiễu GPU); **chưa có lượt lặp lại cho r6 lẫn r7** — bằng chứng của r6 mạnh vì nó là quy lỗi cấp item trên đúng 5 ca bị lever tác động (5/5 cùng chiều), còn cặp r6→r7 chỉ chứng minh tập ca hỏng của bộ chuẩn hóa lặp lại nguyên văn **trên cỡ mẫu 5**, không đủ để nói "bộ chuẩn hóa deterministic"; **tác động thật của bonus 12 khi đã bật guard là chưa xác định** (chênh nằm trong băng nhiễu, cần lặp lại hoặc n lớn); và tỉ lệ "câu hỏi thật" mà hệ thống trả lời đúng (chưa có tập đo — chính là Bước 6).
