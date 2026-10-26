# Kiểm thử T5 — `ENABLE_RERANKER` + contextual chunk header

Ngày: 24-10 (ca tối), cập nhật 25-10 (ca trưa — mục 5 + đo 811 item). Người chạy: agent
kiểm thử (chế độ tự trị).
Phạm vi đợt 24-10: **thêm test + một module build-time mới + script mutation**; KHÔNG sửa
`src/reranker.py`, `src/pipeline.py`, trọng tài (`tools/loop/verify.py`,
`src/answer_guard.py`, `src/text_utils.py`), `tools/loop/gate.py`; KHÔNG build/kích hoạt
index mới; KHÔNG chạy round; **0 lượt gọi Gemini**.
Phạm vi đợt 25-10 (thêm): cờ **tuỳ chọn** `RERANKER_FALLBACK` (mặc định TẮT) để mục 5 xanh
theo câu chữ đề bài mà không đổi đường đang chạy; **không** sửa trọng tài/`gate.py`; đo lại
retrieval-only 811 item trong round MỚI (`r14_repro_off`, `r15_repro_on`), không ghi đè
round đã đóng; **0 lượt Gemini**.

## 1. Đã làm gì

1. **Hợp đồng reranker, mục 1–6** — [`tests/test_t5_reranker_contract.py`](../../tests/test_t5_reranker_contract.py)
   **33 test** (26 của đợt 24-10 + 7 của đợt 25-10: 6 test cờ lùi `RERANKER_FALLBACK` và 1
   test thứ tự/tập ứng viên sau bonus). Mọi tầng dưới là fake: `FakeCrossEncoder` chấm điểm
   theo bảng, `FakeEnsemble` trả danh sách cố định, `FakeVectorDB` ghi lại mọi lần
   `similarity_search`. Không tải cross-encoder thật (2,3 GB), không gọi mạng.
2. **Mục 1 dùng lại golden T3** — [`tests/golden/t3_off_30items_head_f492f05.json`](../../tests/golden/t3_off_30items_head_f492f05.json),
   chụp từ `git archive HEAD` tại commit `f492f05` (trước khi nối T3), qua harness
   [`tools/diag/t3_golden_dump.py`](../../tools/diag/t3_golden_dump.py). Harness đặt
   `ENABLE_RERANKER=0` trong `pin_env()`; test chạy lại 30 item trên cây hiện tại và so
   **từng item, từng khoá**.
3. **Contextual header, mục 7–10** — module build-time mới
   [`src/contextual_header.py`](../../src/contextual_header.py), cờ `ENABLE_CONTEXTUAL_HEADER`
   mặc định **TẮT**, hàm thuần (không ghi đĩa, không gọi model), và
   [`tests/test_t5_contextual_header.py`](../../tests/test_t5_contextual_header.py) **42 test**.
4. **Mutation check** — [`tmp/mutation_check_t5.py`](../../tmp/mutation_check_t5.py), 10 đột biến
   của đợt 24-10 + **3 đột biến mới M11–M13** cho nhánh lùi (tổng **13**) theo byte-anchor
   trên chính file nguồn; mỗi đột biến chạy **cả hai** file test T5, sau đó khôi phục bằng
   `write_bytes` và xác nhận SHA-256 trùng bản gốc. Log:
   [`tmp/mutation_check_t5.log`](../../tmp/mutation_check_t5.log). Vì `src/pipeline.py` và
   `src/reranker.py` đang là file dirty/untracked của phiên khác (PA-8), bước hoàn nguyên
   byte-identical là bắt buộc và đã kiểm từng đột biến.

Thiết kế header (đã ghi trong docstring module):

- header = `[tên văn bản] - [Chương …] - [Điều …] - [Khoản …] - [Điểm …]`, giữ hậu tố
  `(phần i/n)` của header cũ;
- chunk không có Điều nhận nhãn dự phòng theo thứ tự: nhãn cũ → `Phần mở đầu` → `Phụ lục` →
  `Bảng biểu` → `Toàn văn`; không bao giờ phát `None`/`[]`/nhãn rỗng;
- thân chunk giữ **nguyên văn byte-for-byte**; hàm idempotent (gọi lại không cộng dồn nhãn);
- Chương chỉ xuất hiện khi có tiêu đề Chương trong chunk hoặc do nơi build truyền vào qua
  `chapters_for_chunks(full_text, chunks)`;
- header nằm **trong `page_content`** (giống header cũ đang chạy), nên đi vào `contexts` gửi
  generator; `sources`/citation vẫn lấy định danh từ `metadata`;
- `ensure_separate_index_target()` từ chối đích trùng/nằm trong/là thư mục cha của
  `chroma_db`, `chroma_db_vie`, hoặc trùng gốc repo.

## 2. Kết quả số (nguồn: file trên đĩa)

### 2.1 Số test

| Lần chạy | Kết quả | Nguồn |
|---|---|---|
| Hai file T5 (24-10, baseline trước mutation) | **68 passed** (26 + 42), 3 warnings, 2,89 s | `tmp/mutation_check_t5.log` (bản 10 đột biến, lịch sử) |
| Hai file T5 (25-10, baseline của mutation 13 đột biến) | **75 passed** (33 + 42) | dòng `[baseline]` trong `tmp/mutation_check_t5.log` |
| Toàn repo (24-10) | **957 passed**, 3 warnings, 26,84 s | `tmp/pytest_t5_final.txt` |
| Toàn repo (25-10, sau khi thêm cờ lùi + 7 test) | **1.064 passed, 2 skipped** (21,02 s) | `tmp/pytest_t5_final_2.txt` |

### 2.2 Từng mục của đề bài

| Mục | Trạng thái | Bằng chứng (test) |
|---|---|---|
| 1. Cờ TẮT ⇒ top-k byte-identical | **XANH** | golden 30 item khớp `core` sha `344d55cd…`; `retrieve()` trả đúng các **đối tượng** cũ cùng thứ tự; leg k = 6; `last_rerank_call is None`; không gọi `get_reranker` |
| 2. BẬT: đúng 20 ứng viên, trả 6, tập con của 20, đảo theo điểm giả | **XANH** | 6 test; `n_candidates=30`, `n_scored=20`, `pool=20`; model giả đảo ⇒ đầu ra `[20,19,18,17,16,15]`; chunk hạng 11 vào cửa sổ 6 |
| 3. Hoà điểm: tie-break ổn định, cùng input → cùng output | **XANH** | 4 test; toàn 0 điểm giữ thứ tự 1→30; hoà một phần giữ thứ tự cho từng cặp; đổi thứ tự cặp đưa vào model không đổi kết quả |
| 4. < 6 ứng viên hoặc rỗng: không crash | **XANH** | 3 test; 4 ứng viên ⇒ trả đủ 4; rỗng ⇒ `[]`, không nạp model; 1 ứng viên ⇒ trả 1 |
| 5. Reranker lỗi/timeout: lùi RRF + cảnh báo, không hỏng câu trả lời | **XANH khi bật `RERANKER_FALLBACK=1`; mặc định TẮT vẫn dừng loudly** | 6 test cờ lùi + 5 test cũ; bật cờ: trả **đúng object/thứ tự RRF trước rerank**, in `[Reranker] Cảnh báo …`, `last_rerank_call["fallback_used"]=True`, `similarity_search` **không** được gọi, `pipeline.run` vẫn trả câu trả lời (generator 1 lượt, contexts 6, sources 12 = retrieve_k). Mặc định: ném `RerankerUnavailable` (test cũ ghim). Xem mục 4.1 và PA-18(a) |
| 6. Không mất bonus lọc mềm / lọc nguồn | **XANH** | 5 test; reranker nhận đúng thứ tự sau `rescore_with_source_preference(..., rank_bonus=3)`; đổi bonus đổi thứ tự ứng viên trước rerank; **bonus=12** giữ nguyên thứ tự + tập ứng viên (test mới 25-10); lọc **cứng** vẫn cắt trước reranker |
| 7. Header đủ tên văn bản + Chương/Điều/Khoản; nhãn dự phòng rõ, không `None` | **XANH** | 21 test; header đủ `[A.pdf] - [Chương II] - [Điều 8] - [Khoản 1-2] - [Điểm a-b]`; bảng → `[Bảng biểu]`; phụ lục → `[Phụ lục]`; mở đầu giữ `[Phần mở đầu]`; không Điều → `[Toàn văn]`; 7 biến thể rác không sinh `None`/`[]`/nhãn rỗng |
| 8. Header qua cùng fold; BM25 không hỏng | **XANH** | 7 test; `bm25_tokenize(header)` sinh cả dạng có dấu lẫn không dấu (`điều`+`dieu`, `khoản`+`khoan`, `điểm`+`diem`); trên corpus tổng hợp, 4 truy vấn `Điều 8`/`dieu 8`/`Khoản 2`/`khoan 2` đều trả chunk 1; `Điều 12` trả chunk 3 |
| 9. Header không vào citation sai | **XANH (có ghi chú thiết kế)** | 5 test; `contexts` = `page_content` của đúng docs gửi generator, thân nguyên văn; `sources` lấy `source`/`chunk_id`/`tier`/`rank` từ metadata; prompt có header trong phần nội dung nhưng dòng `Nguồn:` lấy từ metadata; cờ TẮT không chèn gì |
| 10. Index mới ghi thư mục khác; index cũ giữ nguyên | **XANH ở mức unit — CHƯA build index T5b thật** | 9 test; cờ TẮT trả nguyên đầu vào; cờ BẬT áp header từng chunk; sai độ dài `titles`/`chapters` ⇒ `ValueError`; guard từ chối `chroma_db`, `chroma_db/headers`, `chroma_db_vie`, gốc repo, thư mục cha của index bảo vệ; index Chroma nhỏ build trong `tmp_path/chroma_db_headers`, digest index cũ không đổi; đọc `chroma_db` (361) + `chroma_db_vie` (342), biến đổi header trong bộ nhớ, digest trước/sau **không đổi** |

### 2.3 Golden cờ TẮT

| Chỉ số | Giá trị |
|---|---|
| SHA-256 file golden | `e59b9ebb6b12c2d6844356f5861cc98d418c11b26f83a49fdae1f8f2ea1728b5` |
| SHA-256 khối `core` (30 item, JSON `sort_keys`) | `344d55cd35ec64b876d1f7580724eb968f158a21fbf42c64a28b54d3c8784b11` |
| Số item | 30 |
| `meta.pipeline_has_t3_fields` | `false` (chụp từ cây baseline `f492f05`, chưa nối T3) |
| Môi trường golden | `ENABLE_RERANKER=0`, `ENABLE_CLASSIFIER=0`, `GENERATION_CACHE=0`, `OLLAMA_HOST=http://127.0.0.1:1` |

Test so cả `json.dumps(...)` SHA-256 lẫn `rows == golden["core"]`, nên một thay đổi nhỏ về
thứ tự khoá, nội dung context, source hay answer đều đỏ.

### 2.4 Số liệu reranker (fake model)

- 30 ứng viên → `n_candidates=30`, `n_scored=20`, `pool=20`, `keep_candidates=false`;
- 20 ứng viên đầu được chấm theo đúng thứ tự RRF+bonus; phần dư (hạng 21–30) đứng sau, giữ
  nguyên thứ tự tương đối;
- `top_score=20.0`, `bottom_score=1.0` với model giả chấm điểm theo nội dung; `order_changed=true`;
- cửa sổ trả về đúng 6, là tập con của 20; chunk hạng 11 được kéo vào đầu khi model cho điểm cao;
- query gửi model là `fold(query)`, passage giữ nguyên văn `page_content`.

### 2.5 Header trên hai index thật (chỉ đọc)

Nguồn: `test_index_that_du_36x_chunk_va_nhan_hop_le` in `header_stats=…`; chạy `pytest -s`
ngày 24-10.

| Nhãn | `chroma_db` (361 chunk) | `chroma_db_vie` (342 chunk) |
|---|---|---|
| `article` (Điều) | 232 (64,27%) | 227 (66,37%) |
| `preamble` (Phần mở đầu) | 21 (5,82%) | 20 (5,85%) |
| `table` (Bảng biểu) | 1 (0,28%) | 1 (0,29%) |
| `appendix` (Phụ lục) | 0 (0,00%) | 0 (0,00%) |
| `whole` (Toàn văn) | 107 (29,64%) | 94 (27,49%) |
| `chapter` (Chương — **chồng lấn**, không cộng vào tổng) | 9 (2,49%) | 18 (5,26%) |

Tổng nhãn loại trừ nhau = **361/361** và **342/342** (test assert đúng).

Digest thư mục hiện tại (SHA-256 trên danh sách tệp + kích thước + byte):

| Index | Digest |
|---|---|
| `chroma_db` | `c68623f74945255c45649dc87527d0c90db745b3dd2fb8bd7552fd0ed2fe1138` |
| `chroma_db_vie` | `15dab0c96e0c6b7305a69e983b5cadbb0e2a617de39dee4527d539f908d2507f` |

Đây là số **đo tại chỗ**, không phải hằng số trong test; test so digest trước/sau trong cùng
một lượt đọc để chứng minh thao tác header không ghi đĩa.

### 2.6 Mutation check — 13/13 bắt được, 13/13 hoàn nguyên byte-identical

Nguồn: [`tmp/mutation_check_t5.log`](../../tmp/mutation_check_t5.log). Mỗi dòng nêu số test đỏ
khi phá đúng một hành vi. M11–M13 thêm ngày 25-10 cho nhánh lùi RRF.

| Đột biến | Kỳ vọng phá | Test đỏ | Hoàn nguyên |
|---|---|---|---|
| M1 đảo tie-break | hoà điểm bị xếp ngược thứ tự RRF | 2 | có |
| M2 bỏ cắt pool | chấm cả 30 thay vì 20 ứng viên | 7 | có |
| M3 bỏ fold query | query không fold trước cross-encoder | 1 | có |
| M4 cờ TẮT vẫn quét sâu | leg k = 20 khi cờ TẮT (phá byte-identical) | 1 | có |
| M5 cờ lùi TẮT vẫn lùi | âm thầm rơi xuống `similarity_search` | 4 | có |
| M6 bỏ tên văn bản | header mất title | 24 | có |
| M7 fallback `"None"` | chunk không Điều nhận nhãn `None` | 11 | có |
| M8 bỏ thân chunk | `contextualize_text` nuốt body | 4 | có |
| M9 cờ TẮT vẫn chèn header | phá off = identical | 2 | có |
| M10 bỏ guard thư mục | cho ghi đè/nằm trong index bảo vệ | 1 | có |
| M11 `if False` cho guard cờ lùi | cờ lùi TẮT vẫn lùi (mất dừng loudly) | 4 | có |
| M12 lùi trả `reversed(docs[:k])` | lùi sai thứ tự RRF | 4 | có |
| M13 lùi xuống `similarity_search` | lùi rơi xuống nhánh tương thích ngược | 4 | có |

M1–M5, M11–M13 đột biến trên `src/reranker.py` / `src/pipeline.py` (file của phiên khác,
PA-8); script sao lưu byte gốc trước khi sửa và kiểm SHA-256 sau khi khôi phục — cả 13 lần
đều trùng.

## 3. Kết luận chỉ từ số

- Cờ `ENABLE_RERANKER` TẮT giữ nguyên hành vi ở mức **30 item pipeline.run** (golden T3 khớp
  từng khoá) và ở mức **đối tượng** trả về của `retrieve()` (cùng object, cùng thứ tự, leg k
  không đổi, không nạp model).
- Cờ BẬT thực hiện đúng hợp đồng đã đăng ký: quét `max(k, 20)`, rerank đúng 20 ứng viên đầu,
  trả 6 (hoặc cả pool khi `RERANKER_KEEP_CANDIDATES=1`), ổn định khi hoà điểm, không crash khi
  thiếu ứng viên.
- Reranker lỗi **không** âm thầm lùi về `similarity_search`; lỗi được ném lên tường minh, đúng
  thiết kế đã đăng ký trước trong `data/loop/README.md`.
- Module header sinh nhãn xác định, idempotent, không bao giờ phát `None`/nhãn rỗng, giữ nguyên
  văn thân chunk, và không ghi gì lên hai index thật (digest trước/sau trùng).
- Trên dữ liệu thật, 64,27%/66,37% chunk có nhãn Điều; 29,64%/27,49% là `Toàn văn`; Chương chỉ
  xuất hiện ở 2,49%/5,26% chunk — tức header mới **không** phủ Chương cho phần lớn chunk nếu
  nơi build không truyền `chapters_for_chunks`.

### 2.7 Kiểm tái lập cấu hình TẮT trên 811 item (25-10)

Round mới `r14_repro_off`, **cùng env đăng ký của r11** (`ENABLE_RERANKER=0`, classifier 1, bonus 12,
quota 0), `--phase retrieval --split all --top-k 6`, chạy trên `venv/` (CPU):

| Chỉ số | r11 (đã đóng) | r14_repro_off |
|---|---:|---:|
| item chấm | 811 | 811 |
| `FAIL_RETRIEVAL` | 182 | **182** |
| `PENDING_GENERATION` | 629 | **629** |
| gold@6 (700 item có vàng) | 0,7400 | **0,7400** |
| median / p95 latency | 2,78 / 3,87 s | 2,71 / 2,91 s |

Đối chiếu **từng item** (811 id, cùng tập), dùng dữ liệu hợp nhất từ `retrieval.jsonl` +
`verdicts_retrieval.jsonl` (bản đầu của tool chỉ đọc verdict — file này không chứa `sources`
nên báo "811/811" vô nghĩa; đã sửa 25-10):

| Trường | Khớp |
|---|---:|
| `verdict` | 811/811 |
| `gold_in_top_k` + `has_gold_chunk` | 811/811 |
| `sources` **top-6** (cửa sổ chấm) | 811/811 |
| `contexts` | 811/811 |
| `sources` **toàn bộ** (retrieve_k = 12) | **809/811** |

Hai item lệch (`O146386093628032` hạng 8, `S8445186527785` hạng 10) chỉ đổi thứ tự/tập ở
đuôi danh sách **sau cửa sổ 6**, do tie-break của tầng truy xuất; `verdict`, gold và
`contexts` không đổi. Vì vậy `match_scored_fields = true`, `match_all_fields = false`.
Nguồn: `data/loop/diag/reranker_paired_family.json`; log `tmp/t5_repro_off.log`.
Đây là phép kiểm tiêu chí đạt của đề bài: **gold@6 cấu hình TẮT trùng đúng round đã đóng**
(0,7400; FAIL 182), không phải "gần đúng". Ghi chú tái lập: đuôi `sources` **không** deterministic
tuyệt đối (2/811 item), nên mọi phép kiểm tương lai phải so trên cửa sổ chấm, không so byte toàn list.

### 2.8 Kiểm tái lập cấu hình BẬT + hiệu ứng ghép cặp/tách family (25-10)

Round mới `r15_repro_on`, cùng env của r12 (`ENABLE_RERANKER=1`,
`RERANKER_KEEP_CANDIDATES=1`, `RERANKER_DEVICE=cuda`, `RERANKER_FALLBACK=0`), chạy trên
`venv_gpu` (GPU 4 GB), `--phase retrieval --split all --top-k 6`:

| Chỉ số | r12 (đã đóng) | r15_repro_on |
|---|---:|---:|
| item chấm | 811 | 811 |
| `FAIL_RETRIEVAL` | 232 | **232** |
| `PENDING_GENERATION` | 579 | **579** |
| gold@6 (700 item có vàng) | 0,6686 | **0,6686** |
| `sources` top-6 / `contexts` / `verdict` khớp | — | **811/811** cả ba |
| `sources` toàn bộ khớp | — | **802/811** (9 item lệch đuôi, hạng 7–36) |

Suy ra delta OFF→ON trên **cùng 811 item** (ghép cặp, `tools/diag/reranker_paired_family.py`,
bootstrap 10.000 lượt seed 20261023):

| Chỉ báo | OFF | ON | delta | McNemar p | CI95% |
|---|---:|---:|---:|---:|---|
| gold@6 (n=700) | 0,7400 | 0,6686 | **−0,0714** | 3,87×10⁻⁶ | [−0,1014; −0,0429] |
| FAIL_RETRIEVAL (n=811) | 0,2244 | 0,2861 | **+0,0617** | 3,87×10⁻⁶ | [+0,0358; +0,0875] |

Ma trận chuyển verdict: 149 giữ FAIL, 546 giữ PENDING, **33 câu từ FAIL → PENDING** (cứu),
**83 câu từ PENDING → FAIL** (mất). Tách family (chỉ family `n_gold ≥ 10`):

| Family | n | gold@6 OFF→ON | delta | p |
|---|---:|---:|---:|---:|
| CLOZE | 153 | 0,9085→0,8105 | −0,0980 | 0,0135 |
| EXACT | 52 | 0,2115→0,0385 | −0,1731 | 0,0117 |
| SOURCE_LOOKUP | 102 | 0,8529→0,6373 | **−0,2157** | 2,74×10⁻⁵ |
| NUMERIC | 112 | 0,4375→0,4821 | +0,0446 | 0,36 |
| CLOZE_OCR | 206 | 0,9709→0,9612 | −0,0097 | 0,77 |
| TRAP | 23 | 0,1304→0,0000 | −0,1304 | 0,25 |
| YESNO_FACT | 32 | 0,5938→0,4688 | −0,1250 | 0,29 |

Reranker **làm hỏng đúng lớp cần tra cứu chính xác/nguồn** (SOURCE_LOOKUP −21,6 điểm, EXACT
−17,3, CLOZE −9,8 — cả ba p < 0,05) và chỉ nhích NUMERIC +4,5 điểm không có ý nghĩa. Đây là
lý do định lượng để giữ `ENABLE_RERANKER=0` (không chỉ vì delta tổng âm).

## 4. Điều KHÔNG kết luận được / phần chưa kiểm

### 4.1 Mục 5: đã giải quyết bằng cờ tuỳ chọn, mặc định vẫn dừng loudly

Đề bài yêu cầu "lùi về thứ tự RRF cũ và ghi log cảnh báo". Thiết kế T5 đã đăng ký trước trong
`data/loop/README.md` cấm lùi thầm vì "một round đo nhầm lever còn tệ hơn một round dừng lại
tường minh". Đợt 25-10 hiện thực **đúng đề xuất PA-18(a)**: thêm `RERANKER_FALLBACK`
(**mặc định `0` = TẮT**). Khi BẬT:

- `RerankerUnavailable` được bắt, in `[Reranker] Cảnh báo: …` kèm nguyên văn lỗi;
- trả **đúng danh sách và thứ tự RRF+bonus trước rerank** (cùng object, không cắt lại);
- **không** gọi `similarity_search`; `last_rerank_call` ghi `fallback_used=True` + `error`;
- `pipeline.run` vẫn một lượt generator, `contexts` = 6, `sources` = 12 (retrieve_k), câu trả
  lời không hỏng.

Mặc định TẮT giữ nguyên hành vi đã đăng ký (ném lỗi) nên **r11/r12 vẫn tái lập được** — đây là
lý do chọn cờ thay vì đổi mặc định. Vậy: mục 5 **XANH theo cả câu chữ đề bài** khi cờ BẬT, và
hành vi production không đổi. Cờ nằm trong bảng env của `src/reranker.py`; bật là quyết định
tường minh, không phải mặc định.

### 4.2 Mục 10 chưa có index T5b thật

Chưa build index mới vì (a) corpus đang chờ quyết định PA-1, (b) `src/contextual_header.py`
chưa được nối vào `ingest.py` (PA-16 vẫn treo), (c) nhiệm vụ đêm quy định "chưa chạy round".
Bằng chứng hiện có chỉ là unit: guard đường dẫn + index nhỏ trong `tmp_path` + digest hai index
thật không đổi. **Không** có số đo retrieval trên index header.

### 4.3 Kiểm lại gold@6 cấu hình TẮT so với round đã đóng — ĐÃ CHẠY, TRÙNG TUYỆT ĐỐI

Tiêu chí đạt của đề bài yêu cầu "kiểm lại gold@6 cấu hình TẮT trùng số của round tương ứng đã
đóng". Đợt 25-10 đã chạy round MỚI `r14_repro_off` (811 item, cùng env r11) và so **từng item**:
`verdict`, `gold_in_top_k`, `sources` top-6, `contexts` khớp **811/811**; `sources` toàn bộ
khớp 809/811 (2 item lệch thứ tự ở hạng 8/10, ngoài cửa sổ chấm); gold@6 = **0,7400** bằng đúng
r11, `FAIL_RETRIEVAL` = **182** bằng đúng r11 (chi tiết §2.7). Không có lỗi tái lập ở mọi trường
được dùng để chấm, nên các so sánh OFF↔ON dùng được round mới. Điều **không** được tuyên bố:
đuôi `sources` tái lập byte-tuyệt-đối — nó không (2/811 ở OFF, 9/811 ở ON).

### 4.4 Không test chất lượng model thật

Test dùng `FakeCrossEncoder`; không tải `BAAI/bge-reranker-v2-m3`, không đo độ trễ/RAM, không
so điểm thật. Đó là phạm vi của cost probe/round T5a, không phải unit test.

### 4.5 Giới hạn đã biết của thiết kế header

- Chương chỉ có khi tiêu đề Chương nằm trong chunk hoặc do build truyền vào; trên index thật
  chỉ 9/361 và 18/342 chunk có Chương.
- Header nằm trong `page_content` nên **có** đi vào ngữ cảnh generator (giống header cũ). Nếu
  hội đồng muốn header chỉ phục vụ truy xuất, cần tách trường metadata riêng — thay đổi thiết
  kế, ghi ở PA-18.
- Mục 6 ghim thêm giới hạn: lọc **cứng** theo nguồn vẫn cắt ứng viên trước khi reranker nhìn
  thấy; reranker chỉ xếp lại những gì được giao.
- Test mục 8 chạy trên corpus tổng hợp, không chạy BM25 trên index thật.

### 4.6 Ghi chú tái lập phát hiện trong lúc kiểm ON

Bản đầu của `tools/diag/reranker_paired_family.py` đọc `sources`/`contexts` từ file verdict —
nơi hai trường này không tồn tại — nên báo "811/811" một cách vô nghĩa. Đã sửa sang hợp nhất
`retrieval.jsonl` + `verdicts_retrieval.jsonl` và tách thang `sources_top_k` / `sources_full`.
Sau khi sửa: OFF 809/811, ON 802/811 ở **toàn bộ** danh sách (hạng sâu đổi do tie-break), trong
khi cửa sổ 6, `contexts`, `verdict`, gold đều 811/811. Mọi kết luận metric trong báo cáo chỉ dựa
trên các trường đã khớp 811/811; hiện tượng đuôi không deterministic được ghi thành nợ điều tra
(cùng họ với "r0≡r3 nhưng r1 lệch 18/100 bản chuẩn hóa").

## 5. Tiêu chí xong

- Mục 1–10: **1–4, 6–10 xanh**; **mục 5 xanh khi bật cờ tuỳ chọn `RERANKER_FALLBACK=1`**,
  mặc định TẮT giữ hành vi đã đăng ký (dừng loudly) — PA-18(a).
- Kiểm lại gold@6 cấu hình TẮT so với round đã đóng: **ĐÃ CHẠY, khớp 0,7400** và FAIL 182;
  cửa sổ/verdict/gold/contexts khớp 811/811 (§2.7). Tiêu chí đạt của đề bài: **ĐẠT**.
- Tái lập ON: gold@6 0,6686, FAIL 232 — khớp đúng r12; ghép cặp OFF→ON âm rõ
  (−0,0714, p=3,9×10⁻⁶) và tách family chỉ ra ba lớp bị hỏng nặng (§2.8).
- Không đỏ test cũ: hai file T5 **75 passed**; toàn repo **1.064 passed, 2 skipped**
  (`tmp/pytest_t5_final_2.txt`); mutation **13/13** bắt được và hoàn nguyên byte-identical;
  không sửa test cũ nào.

## 6. Lệnh tái lập

```bash
# Hai file test T5
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  tests/test_t5_reranker_contract.py tests/test_t5_contextual_header.py -q

# Toàn repo
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q

# Mutation check (13 đột biến, tự hoàn nguyên + kiểm SHA-256)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t5.py

# Riêng số liệu header trên index thật (in header_stats)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  "tests/test_t5_contextual_header.py::TestMuoiIndexRiengVaBam::test_index_that_du_36x_chunk_va_nhan_hop_le" -q -s
```

## 7. Đề xuất cần duyệt

- **PA-18 (mới):** ba quyết định T5 — (a) cờ fallback reranker tuỳ chọn mặc định TẮT cho mục 5
  theo câu chữ đề bài — **đã hiện thực 25-10** (`RERANKER_FALLBACK`, 7 test), không đổi hành vi
  mặc định nên không phải chấm lại round; (b) header có/không đi vào ngữ cảnh generator; (c) nối
  `src/contextual_header.py` vào `ingest.py` và build index mới ở thư mục riêng. (b)+(c) vẫn chờ
  duyệt. Chi tiết + diff ở [`docs/PENDING_APPROVAL.md`](../PENDING_APPROVAL.md).
- **PA-8** vẫn treo: không commit các thay đổi `src/` chưa hoàn tất của phiên khác
  (`src/reranker.py`, `src/pipeline.py`, `src/generator.py`, `src/query_normalizer.py`,
  `src/router.py` cùng test đi kèm).
- **PA-1/PA-16** vẫn là điều kiện trước khi build index T5b thật.
