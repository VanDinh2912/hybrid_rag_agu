# Kiểm thử T5 — `ENABLE_RERANKER` + contextual chunk header

Ngày: 24-10 (ca tối). Người chạy: agent kiểm thử (chế độ tự trị).
Phạm vi: **thêm test + một module build-time mới + script mutation**; KHÔNG sửa
`src/reranker.py`, `src/pipeline.py`, trọng tài (`tools/loop/verify.py`,
`src/answer_guard.py`, `src/text_utils.py`), `tools/loop/gate.py`; KHÔNG build/kích hoạt
index mới; KHÔNG chạy round; **0 lượt gọi Gemini**.

## 1. Đã làm gì

1. **Hợp đồng reranker, mục 1–6** — [`tests/test_t5_reranker_contract.py`](../../tests/test_t5_reranker_contract.py)
   **26 test**. Mọi tầng dưới là fake: `FakeCrossEncoder` chấm điểm theo bảng, `FakeEnsemble`
   trả danh sách cố định, `FakeVectorDB` ghi lại mọi lần `similarity_search`. Không tải
   cross-encoder thật (2,3 GB), không gọi mạng.
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
   theo byte-anchor trên chính file nguồn; mỗi đột biến chạy **cả hai** file test T5, sau đó
   khôi phục bằng `write_bytes` và xác nhận SHA-256 trùng bản gốc. Log:
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
| Hai file T5 (baseline trước mutation) | **68 passed** (26 + 42), 3 warnings, 2,89 s | `tmp/mutation_check_t5.log` dòng `[baseline]` |
| Hai file T5 (sau mutation, cây đã hoàn nguyên) | **68 passed** trong lần chạy baseline của mutation log lần 2 | `tmp/mutation_check_t5.log` |
| Toàn repo (trước mutation) | **957 passed**, 3 warnings, 29,84 s | `tmp/pytest_t5_before_mutation.txt` |
| Toàn repo (sau mutation) | **957 passed**, 3 warnings, 26,84 s | `tmp/pytest_t5_final.txt` |

### 2.2 Từng mục của đề bài

| Mục | Trạng thái | Bằng chứng (test) |
|---|---|---|
| 1. Cờ TẮT ⇒ top-k byte-identical | **XANH** | golden 30 item khớp `core` sha `344d55cd…`; `retrieve()` trả đúng các **đối tượng** cũ cùng thứ tự; leg k = 6; `last_rerank_call is None`; không gọi `get_reranker` |
| 2. BẬT: đúng 20 ứng viên, trả 6, tập con của 20, đảo theo điểm giả | **XANH** | 6 test; `n_candidates=30`, `n_scored=20`, `pool=20`; model giả đảo ⇒ đầu ra `[20,19,18,17,16,15]`; chunk hạng 11 vào cửa sổ 6 |
| 3. Hoà điểm: tie-break ổn định, cùng input → cùng output | **XANH** | 4 test; toàn 0 điểm giữ thứ tự 1→30; hoà một phần giữ thứ tự cho từng cặp; đổi thứ tự cặp đưa vào model không đổi kết quả |
| 4. < 6 ứng viên hoặc rỗng: không crash | **XANH** | 3 test; 4 ứng viên ⇒ trả đủ 4; rỗng ⇒ `[]`, không nạp model; 1 ứng viên ⇒ trả 1 |
| 5. Reranker lỗi/timeout: lùi RRF + cảnh báo, không hỏng câu trả lời | **XANH theo thiết kế đã đăng ký — KHÔNG xanh theo câu chữ đề bài** | 5 test; timeout bị bọc `RerankerUnavailable` kèm nguyên văn; pipeline **ném lên**, không gọi `similarity_search`; test tên `test_de_bai_muc_5_noi_lui_rrf_nhung_thiet_ke_da_dang_ky_thi_khong` ghim đúng khác biệt này. Xem mục 4.1 và PA-18 |
| 6. Không mất bonus lọc mềm / lọc nguồn | **XANH** | 4 test; reranker nhận đúng thứ tự sau `rescore_with_source_preference(..., rank_bonus=3)`; đổi bonus đổi thứ tự ứng viên trước rerank; lọc **cứng** vẫn cắt trước reranker (giới hạn được ghim thành chữ) |
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

### 2.6 Mutation check — 10/10 bắt được, 10/10 hoàn nguyên byte-identical

Nguồn: [`tmp/mutation_check_t5.log`](../../tmp/mutation_check_t5.log). Mỗi dòng nêu số test đỏ
khi phá đúng một hành vi.

| Đột biến | Kỳ vọng phá | Test đỏ | Hoàn nguyên |
|---|---|---|---|
| M1 đảo tie-break | hoà điểm bị xếp ngược thứ tự RRF | 2 | có |
| M2 bỏ cắt pool | chấm cả 30 thay vì 20 ứng viên | 7 | có |
| M3 bỏ fold query | query không fold trước cross-encoder | 1 | có |
| M4 cờ TẮT vẫn quét sâu | leg k = 20 khi cờ TẮT (phá byte-identical) | 1 | có |
| M5 reranker lỗi lùi RRF | âm thầm rơi xuống `similarity_search` | 3 | có |
| M6 bỏ tên văn bản | header mất title | 24 | có |
| M7 fallback `"None"` | chunk không Điều nhận nhãn `None` | 11 | có |
| M8 bỏ thân chunk | `contextualize_text` nuốt body | 4 | có |
| M9 cờ TẮT vẫn chèn header | phá off = identical | 2 | có |
| M10 bỏ guard thư mục | cho ghi đè/nằm trong index bảo vệ | 1 | có |

M1/M2/M3/M5 đột biến trên `src/reranker.py` / `src/pipeline.py` (file của phiên khác, PA-8);
script sao lưu byte gốc trước khi sửa và kiểm SHA-256 sau khi khôi phục — cả 10 lần đều trùng.

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

## 4. Điều KHÔNG kết luận được / phần chưa kiểm

### 4.1 Mục 5 khác câu chữ đề bài (đã ghim thành test)

Đề bài yêu cầu "lùi về thứ tự RRF cũ và ghi log cảnh báo". Thiết kế T5 đã đăng ký trước trong
`data/loop/README.md` cấm lùi thầm vì "một round đo nhầm lever còn tệ hơn một round dừng lại
tường minh". Test hiện tại ghim hành vi **ném lỗi**, không phải lùi. Vì vậy:

- theo **thiết kế đã đăng ký**: mục 5 ĐẠT;
- theo **câu chữ đề bài**: mục 5 CHƯA ĐẠT.

Không tự thêm cờ fallback trong nhiệm vụ test (một biến một lần, và hành vi này đã đăng ký).
Đề xuất cờ tuỳ chọn mặc định TẮT ở **PA-18**.

### 4.2 Mục 10 chưa có index T5b thật

Chưa build index mới vì (a) corpus đang chờ quyết định PA-1, (b) `src/contextual_header.py`
chưa được nối vào `ingest.py` (PA-16 vẫn treo), (c) nhiệm vụ đêm quy định "chưa chạy round".
Bằng chứng hiện có chỉ là unit: guard đường dẫn + index nhỏ trong `tmp_path` + digest hai index
thật không đổi. **Không** có số đo retrieval trên index header.

### 4.3 Chưa kiểm lại gold@6 của cấu hình TẮT so với round đã đóng

Tiêu chí đạt của đề bài yêu cầu "kiểm lại gold@6 cấu hình TẮT trùng số của round tương ứng đã
đóng". Đêm nay **không chạy round retrieval-only 811 item** (đúng thứ tự đêm: viết code + test
với mọi cờ TẮT, chưa chạy round). Golden 30 item chứng minh đường `pipeline.run` không đổi,
nhưng **không thay thế** phép kiểm gold@6 trên 811 item. Hạng mục này vẫn treo ở task T5a
(#34/#35) và phải chạy trước khi nghiệm thu T5.

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

## 5. Tiêu chí xong

- Mục 1–10: **1–4, 6–10 xanh**; **mục 5 xanh theo thiết kế đã đăng ký, không xanh theo câu
  chữ đề bài** (PA-18).
- Kiểm lại gold@6 cấu hình TẮT so với round đã đóng: **CHƯA chạy** → nghiệm thu đầy đủ theo
  câu chữ đề bài **CHƯA đạt**; phần hợp đồng đơn vị đã xong.
- Không đỏ test cũ: toàn repo **957 passed** sau mutation (`tmp/pytest_t5_final.txt`), tăng 68
  test so với 889 trước đó; không sửa test cũ nào.

## 6. Lệnh tái lập

```bash
# Hai file test T5
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  tests/test_t5_reranker_contract.py tests/test_t5_contextual_header.py -q

# Toàn repo
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q

# Mutation check (10 đột biến, tự hoàn nguyên + kiểm SHA-256)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t5.py

# Riêng số liệu header trên index thật (in header_stats)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  "tests/test_t5_contextual_header.py::TestMuoiIndexRiengVaBam::test_index_that_du_36x_chunk_va_nhan_hop_le" -q -s
```

## 7. Đề xuất cần duyệt

- **PA-18 (mới):** ba quyết định T5 — (a) cờ fallback reranker tuỳ chọn mặc định TẮT cho mục 5
  theo câu chữ đề bài; (b) header có/không đi vào ngữ cảnh generator; (c) nối
  `src/contextual_header.py` vào `ingest.py` và build index mới ở thư mục riêng. Chi tiết + diff
  ở [`docs/PENDING_APPROVAL.md`](../PENDING_APPROVAL.md).
- **PA-8** vẫn treo: không commit các thay đổi `src/` chưa hoàn tất của phiên khác
  (`src/reranker.py`, `src/pipeline.py`, `src/generator.py`, `src/query_normalizer.py`,
  `src/router.py` cùng test đi kèm).
- **PA-1/PA-16** vẫn là điều kiện trước khi build index T5b thật.
