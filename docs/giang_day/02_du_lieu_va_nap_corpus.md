# Chương 02 — Dữ liệu, nạp corpus và phân đoạn

> **Mục tiêu chương:** giải thích được đường đi của một file PDF từ đĩa đến một dòng
> trong ChromaDB; đọc hiểu cả `DocumentChunker` (production) lẫn ba chiến lược
> chunking đếm theo token (thực nghiệm); biết vì sao OCR làm hỏng dấu và hệ quả lên
> toàn bộ hệ thống.

---

## 1. Corpus được tổ chức thế nào?

`data/corpus/` chia theo thư mục con — **tên thư mục cấp 1 chính là `tier`**:

```
data/corpus/
├── Tầng 1/     # quy chế, quyết định gốc — PDF scan, OCR mất dấu
├── Tầng 2/     # thông báo, kế hoạch — PDF text, còn dấu
└── Bổ sung/    # tài liệu bổ sung (nếu có)
```

`DocumentLoader._tier_of` (`src/indexing/loader.py:115`) lấy phần tử đầu của đường dẫn tương
đối; file nằm ngay trong `data/corpus/` nhận `default_tier="Khác"`. `tier` đi theo
chunk vào ChromaDB và cuối cùng vào prompt, nơi generator được dặn “ưu tiên Tầng 1
khi mâu thuẫn”.

> Vì sao phân tầng? Không phải để đẹp. Khi một thông báo Tầng 2 nói “hạn nộp 30/6”
> còn quy chế Tầng 1 nói “31/5”, hệ thống cần biết văn bản nào có thẩm quyền cao hơn.
> `tier` là metadata mang thông tin đó.

---

## 2. `src/indexing/loader.py` — từ file đến `{title, content, tier}`

### 2.1. Bảng hàm

| Hàm | Dòng | Vào → Ra | Ghi chú |
|---|---:|---|---|
| `_extract_txt` | 38 | path → str | đọc UTF-8 |
| `_extract_docx` | 43 | path → str | paragraph + bảng, ô nối bằng ` \| ` |
| `TEXT_EXTRACTORS` | 52 | dict định dạng → hàm | `.txt`, `.docx` |
| `UNSUPPORTED_FORMATS` | 56 | dict định dạng → lý do | `.doc` báo lỗi rõ thay vì bỏ im lặng |
| `_get_ocr_engine` | 61 | → RapidOCR | singleton toàn tiến trình |
| `_ocr_page_text` | 73 | engine, ảnh → str | mỗi box một dòng |
| `DocumentLoader.__init__` | 96 | tham số + env | cấu hình OCR, dpi, ngưỡng |
| `_tier_of` | 115 | path → str | thư mục cấp 1 |
| `_skip` | 119 | path, lý do | ghi `self.skipped`, in cảnh báo |
| `_cache_file` | 125 | path → đường dẫn cache | hash nội dung + tham số |
| `_cache_load` | 134 | path, trang scan → dict | `None` nếu thiếu/không khớp |
| `_cache_save` | 145 | path, pages | ghi JSON |
| `_ocr_pages` | 152 | path, trang scan, tổng | OCR từng trang, cache |
| `_extract_pdf` | 183 | path → str \| None | text trước, OCR trang nghèo chữ |
| `_read_document` | 207 | path → str \| None | định tuyến theo đuôi file |
| `load_documents` | 221 | → `[{title, content, tier}]` | quét đệ quy, sắp xếp ổn định |

### 2.2. Cơ chế OCR theo từng trang

`_extract_pdf` không quyết định “file này scan hay không”, mà quyết định **từng
trang**:

```python
pages = [page.extract_text() or "" for page in reader.pages]
scan_pages = [i for i, text in enumerate(pages)
              if len(text.strip()) < self.min_chars_per_page]  # mặc định 50
```

Vì sao theo trang? Một PDF thường có trang bìa scan + trang thân text. OCR cả file sẽ
tốn thời gian vô ích; chỉ OCR trang nghèo chữ mới đúng.

Quy trình một trang scan:

```
pdfium.PdfDocument(path)[index]
  .render(scale=dpi/72)        # 200 dpi mặc định
  .to_pil().convert("RGB")
        │
        ▼
RapidOCR(np.array(image))      # trả [[box, text, score], ...]
        │
        ▼
"\n".join(text của từng box)   # giữ "Dieu 7." ở đầu dòng
```

Giữ xuống dòng rất quan trọng: `ARTICLE_HEADING_RE` chỉ nhận “Điều N.” **ở đầu dòng**.
Nếu nối tất cả bằng space, chunking sẽ không nhận ra cấu trúc Điều và rơi về fallback.

### 2.3. Cache OCR

OCR toàn bộ Tầng 1 mất khoảng 10 phút. Cache key gồm:

```
đường_dẫn_tương_đối | size | mtime | dpi | min_chars_per_page
```

→ SHA-1 16 ký tự → `.cache/ocr/rapidocr/<tên_file>__<hash>.json`. Sửa file hoặc đổi dpi là
hash đổi, cache tự hỏng. `_cache_load` còn kiểm tra **tập trang scan khớp chính xác**;
nếu file đổi số trang, cache bị bỏ.

> ⚠️ Cache không lưu ảnh, chỉ lưu text. Xóa `.cache/ocr/rapidocr/` an toàn nhưng lần ingest sau
> sẽ OCR lại từ đầu.

### 2.4. Lỗi được ghi nhận, không bị nuốt

```python
self.skipped: list[tuple[str, str]] = []       # (đường dẫn, lý do)
self.ocr_stats: list[tuple[str, int, int, int]] = []  # (file, trang OCR, tổng trang, ký tự)
```

`ingest.py` in cả hai danh sách. Một đồ án nghiêm túc không được “âm thầm mất 3 file”;
hội đồng sẽ hỏi “vì sao corpus chỉ có 40 file trong khi thư mục có 44?”.

---

## 3. `ingest.py` — bốn bước nạp

```python
def run_ingestion(db_manager=None, reset=True):
```

| Bước | Việc làm | Dữ liệu |
|---|---|---|
| 1/4 | Xóa `chroma_db/` nếu `reset=True` | tránh nhân đôi chunk |
| 2/4 | `DocumentLoader.load_documents()` | in số file, file OCR, file skip |
| 3/4 | `DocumentChunker().chunk_document(doc)` từng file | in chunk theo file + tầng |
| 4/4 | `VectorStoreManager.create_vector_store(chunks)` | nhúng bge-m3, persist |

`main()` kiểm tra `stored == total`, nếu không thì `SystemExit`. Đây là **assertion
toàn vẹn**: ChromaDB phải chứa đúng số chunk vừa tạo.

`reset=False` dành cho `scripts/learn.py`: giữ đối tượng `VectorStoreManager` (đã nạp bge-m3)
và để `create_vector_store` xóa collection bên trong — tránh `rmtree` vấp file lock
trên Windows.

---

## 4. `DocumentChunker` — chunking production (đếm theo ký tự)

### 4.1. Vì sao không cắt 512 token ở production?

Code production cắt theo **ký tự** (`max_chars=1200`, `min_chars=20`,
`overlap_chars=150`). Với tiếng Việt khoảng 2 ký tự/token, 1200 ký tự ≈ 600 token —
vừa cửa sổ bge-m3, lại không cần nạp tokenizer mỗi lần ingest. Ba chiến lược token ở
nửa sau file là **thực nghiệm**, không được `ingest.py` gọi.

> Đừng nhầm hai hàm cùng tên `structure_aware_chunking`: bản **method** của
> `DocumentChunker` cắt theo ký tự; bản **module-level** cắt theo token. Docstring
> `src/indexing/chunking.py:185` cảnh báo đúng điểm này.

### 4.2. Nhận diện cấu trúc Điều

```python
ARTICLE_WORD = r"[ĐÐD][iI](?:[êềếểễệEeÉéÈè])?[uUùú]"
ARTICLE_HEADING_RE = re.compile(rf"^\s*({ARTICLE_WORD}\s*\d+\.)", re.MULTILINE)
```

Regex này nhận cả:

- `Điều 4.` — chuẩn;
- `Dieu 4.` — OCR mất dấu;
- `Ðiều 4.` — lỗi font PDF (chữ Ð U+00D0).

Ba ràng buộc thiết kế:

1. **`^` + `MULTILINE`**: chỉ nhận ở đầu dòng. Câu “...theo Điều 5.” giữa câu không
   được cắt — nếu nhận nhầm, toàn bộ nội dung trước đó biến mất.
2. **Dấu chấm sau số**: “Điều 12” không có dấu chấm có thể là trích dẫn, không phải
   tiêu đề.
3. **`canonical_article`** chuẩn hóa mọi biến thể về `Điều N.` để trích dẫn không lỗi
   dấu.

### 4.3. `chunk_document` — cổng vào

```
doc = {title, content, tier}
  │ has_article_structure(content)?
  ├─ có  → structure_aware_chunking(content, doc_title=title)
  └─ không → fallback_chunking(content, doc_title=title)
  ▼
[{text, tier, source}, ...]
```

Mọi chunk đều mang tiền tố `[Tên văn bản]` — nhờ vậy embedding của chunk chứa cả ngữ
cảnh văn bản, không chỉ nội dung trần.

### 4.4. `DocumentChunker.structure_aware_chunking` (dòng 72)

```
text
 ├─ phần trước "Điều 1."  → [Phần mở đầu]   (quốc hiệu, căn cứ, số quyết định)
 └─ từng cặp (tiêu đề Điều, thân Điều)
      ├─ thân ≤ max_chars → 1 chunk "[Tên] - [Điều N.] \n thân"
      └─ thân dài → _pack_text → nhiều phần "(phần i/n)"
```

Vì sao giữ “Phần mở đầu”? Với quyết định scan, trang 1 chứa số hiệu, ngày ban hành,
căn cứ pháp lý — mất nó là mất khả năng trích dẫn nguồn gốc. Đây là lỗi phổ biến của
các pipeline “chỉ lấy từ Điều 1”.

### 4.5. `_pack_text` và `_split_oversized`

- `_pack_text` (dòng 121): tách theo đoạn `\n\s*\n`, gộp tham lam đến `max_chars`;
  khi tràn, chunk mới bắt đầu bằng đuôi chunk cũ (`_overlap_prefix`).
- `_overlap_prefix` (dòng 106): lấy tối đa `overlap_chars` ký tự cuối, rồi **dịch
  tới ranh giới câu gần nhất** để không bắt đầu giữa câu.
- `_split_oversized` (dòng 151): đoạn đơn dài hơn `max_chars` → tách câu; câu vẫn quá
  dài → cắt cứng.

Ví dụ overlap:

```
Chunk 1: "... Mức học phí là 15.000.000 đồng/học kỳ. Sinh viên phải nộp trước 15/8."
Chunk 2: "Sinh viên phải nộp trước 15/8.\n\nĐiều 12. Miễn giảm học phí ..."
```

Câu cuối được nhân bản sang chunk 2. Đánh đổi: tốn token, nhưng thông tin nằm ở biên
không bị tách đôi khỏi ngữ cảnh.

### 4.6. `fallback_chunking` (dòng 102)

Văn bản hành chính không có “Điều” (thông báo, kế hoạch) được gom đoạn đến `max_chars`
với tiền tố `[Tên văn bản]\n`. Không có cấu trúc pháp lý để bảo toàn, nên tiêu chí là
“đừng cắt giữa câu”.

### 4.7. Con số thực tế

| Nguồn | Số chunk |
|---|---:|
| Tầng 1 | 234 |
| Tầng 2 | 50 |
| Bổ sung | 77 |
| **Tổng đã index** | **361** |

> Docstring đầu file ghi “388 chunk” — đó là số của một lần rebuild trước. Luôn đếm
> từ ChromaDB (`vector_db._collection.count()`) thay vì tin comment. Đây là bài học
> về **số liệu tự động** thay vì số liệu chép tay.

---

## 5. Nửa sau `chunking.py` — ba chiến lược đếm token

Đây là phần **nghiên cứu thực nghiệm**, không dùng ở production. Mục tiêu: so sánh
công bằng ba cách chia trên cùng văn bản, cùng tokenizer, cùng ngưỡng 512 token.

### 5.1. Tokenizer

| Thành phần | Dòng | Vai trò |
|---|---:|---|
| `BaseTokenCounter` | 224 | giao diện `count`, `window`, `windows` |
| `HuggingFaceTokenCounter` | 255 | tokenizer thật của bge-m3; `encode` không thêm special token |
| `WhitespaceTokenCounter` | 326 | dự phòng đếm theo âm tiết khi không nạp được transformers |
| `get_token_counter` | 347 | cache theo tên model, tự lùi whitespace |

Chi tiết đáng học: `HuggingFaceTokenCounter._shrink` (dòng 308) decode rồi **đếm lại**
chuỗi thành phẩm. Vì tokenizer không thuận nghịch tuyệt đối ở biên khoảng trắng, 512
id có thể decode thành chuỗi mã hóa lại 513 token. Nếu không kiểm tra lại, “fixed 512”
lệch đúng tiêu chí đang đo.

`windows` (dòng 294) tiến theo **số token thật đã lấy**, không theo `length`; nếu
không, phần bị gọt sẽ biến mất khỏi corpus và ba chiến lược so sánh trên tập văn bản
khác nhau.

### 5.2. Khóa bảng Markdown

`split_around_tables` (dòng 368): gom dòng `|...|` liền nhau, cần ≥ 2 dòng mới coi là
bảng. `_chunk_with_table_lock` (dòng 401): bảng được giữ **nguyên khối**, kể cả dài
hơn 512 token.

Vì sao phá lệ ngưỡng? Một bảng học phí bị cắt đôi sẽ mất hàng tiêu đề cột; nửa bảng
còn lại vô nghĩa với cả embedding lẫn generator. “Một chunk vượt ngưỡng” tốt hơn “hai
nửa bảng”.

### 5.3. Ba chiến lược

| Chiến lược | Hàm | Cách cắt | Điểm mạnh | Điểm yếu |
|---|---|---|---|---|
| Fixed-size | `fixed_size_chunking` (450) | cửa sổ token, mặc định 512/overlap 0 | đơn giản, baseline công bằng | cắt giữa câu, mất cấu trúc |
| Recursive | `recursive_chunking` (553) | `\n\n` → `\n` → câu → mệnh đề → từ → cắt cứng | ranh giới tự nhiên | không biết Điều/Khoản |
| Structure-aware | `structure_aware_chunking` (772) | Điều → Khoản → Điểm, gộp tới ngưỡng, tiền tố phân cấp | giữ đơn vị pháp lý, trích dẫn đúng cấp | phức tạp, phụ thuộc regex |

**Fixed-size** dùng `_hard_slice` (428) và `_validate_budget` (442) chặn
`max_tokens <= 0` hoặc `overlap >= max_tokens`.

**Recursive** dùng:

- `_recursive_split` (523): thử separator lớn nhất có trong text; quá dài thì đệ quy
  xuống cấp nhỏ hơn; hết separator thì cắt cứng.
- `_merge_pieces` (489): gộp các mảnh liền kề đến ngưỡng. Nhánh đặc biệt: nếu buffer
  chỉ còn ≤ 4 token (nhãn “16.” bị tách khỏi thân), dán lại rồi cắt ở cấp nhỏ hơn —
  tránh chunk rác 1 token.
- `_apply_overlap` (540): áp overlap **sau** khi cắt, tính theo token.

**Structure-aware** là phần dày nhất:

| Hàm | Dòng | Việc |
|---|---:|---|
| `_split_keep_markers` | 594 | cắt tại mốc nhưng **giữ dòng tiêu đề** trong thân |
| `_article_units` | 622 | bóc Điều thành các unit (Khoản, Điểm, nội dung) |
| `_label_range` | 645 | `['1','2']` → `Khoản 1-2` |
| `_hierarchical_prefix` | 656 | `[Tên] - [Điều N.] - [Khoản x-y] - [Điểm a-b]` |
| `_flush_group` | 675 | render một nhóm unit thành 1..n chunk, trừ ngân sách tiền tố |
| `_starts_new_group` | 702 | unit không nhãn Khoản luôn đứng riêng |
| `_emit_units` | 713 | gộp tham lam các unit liền kề |
| `_chunk_article_segment` | 738 | chunk một đoạn không chứa bảng, mang nhãn Điều đang mở |
| `chunk_with_strategy` | 831 | cổng gọi chung cho thí nghiệm |

Ba quyết định đáng nhớ:

1. **Giữ marker trong thân** (`_split_keep_markers`): nếu dùng `re.split`, nhãn “1.”
   biến mất; generator không thể trích “Khoản 1”. Hàm này cắt bằng `finditer` để giữ
   nguyên dòng tiêu đề.
2. **Unit không nhãn đứng riêng** (`_starts_new_group`): lời dẫn của Điều hoặc dòng
   “1.500.000 đồng là mức học phí” không được gộp vào Khoản kế tiếp, nếu không nội
   dung bị gán nhầm nhãn pháp lý.
3. **Tiền tố phân cấp** (`_hierarchical_prefix`): câu hỏi “Khoản 5 Điều 8 quy định
   gì?” khớp được cả phần nhãn, không chỉ thân. Đây là lợi thế chính của chiến lược 3.

### 5.4. Ví dụ một chunk structure-aware

```
[Quy chế đào tạo đại học 2021] - [Điều 12.] - [Khoản 2-3]
2. Sinh viên được đăng ký học lại ...
3. Điểm học phần lần thứ hai ...
```

Nếu thân quá dài:

```
[...] - [Điều 12.] - [Khoản 2] (phần 1/2)
...
```

`_flush_group` trừ ngân sách tiền tố + 8 token cho hậu tố “(phần i/n)” trước khi gọi
recursive, nhờ vậy chunk thành phẩm **luôn** nằm trong mốc 512 token.

### 5.5. Cách chạy thí nghiệm

```bash
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/benchmark_chunking.py --limit 2
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/benchmark_chunking.py --strategies structure
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/benchmark_chunking.py --generator qwen
```

`chunk_with_strategy` là cổng duy nhất — cả benchmark và Streamlit đều gọi nó, nên
không có chuyện “UI cắt kiểu khác benchmark”.

---

## 6. `src/retrieval/vector_db.py` — nhúng và lưu

| Hàm/class | Dòng | Vai trò |
|---|---:|---|
| `bm25_tokenize` | 26 | sinh **cả** token có dấu và đã fold |
| `extract_documents_from_chroma` | 40 | đọc toàn bộ document + metadata từ Chroma để dựng BM25 |
| `VectorStoreManager.__init__` | 56 | nạp bge-m3 trên CPU, normalize embedding |
| `create_vector_store` | 65 | xóa collection cũ, tạo Document, nhúng, persist |
| `load_vector_store` | 101 | nối collection đã persist (không embed lại corpus) |
| `create_bm25_retriever` | 109 | BM25 từ toàn bộ chunk, tokenizer kép |
| `create_ensemble_retriever` | 122 | BM25 + Chroma qua RRF |

### 6.1. Metadata của một chunk

```python
{
  "tier": "Tầng 1",
  "source": "1059-qd-dhag-2020-09-29.pdf",
  "chunk_id": 42
}
```

`chunk_id` đánh số tuần tự **toàn đợt nạp**, không phải trong từng file. Nó là khóa
khử trùng giữa các nhánh truy xuất và giữa kết quả BM25/Chroma.

### 6.2. `bm25_tokenize` — chi tiết quyết định

```python
clean_raw = re.sub(r"[^\w\s]", " ", text.lower())
raw_tokens = clean_raw.split()
clean_folded = re.sub(r"[^\w\s]", " ", fold(text))
folded_tokens = clean_folded.split()
return raw_tokens + folded_tokens
```

Mỗi chunk được index **hai lần token**: dạng gốc và dạng bỏ dấu. Nhờ vậy:

- chunk OCR “hoc phi” khớp query có dấu “học phí” (qua token fold);
- chunk chuẩn “Thiết kế và cài đặt mạng” khớp query viết đúng (qua token gốc);
- không cần chọn “index bản nào” — index cả hai.

Đánh đổi: chỉ mục BM25 phình gấp đôi. Với 361 chunk, chi phí không đáng kể; với hàng
trăm nghìn chunk sẽ phải cân nhắc.

### 6.3. Vì sao BM25 được dựng lại lúc serve?

ChromaDB lưu vector và text, không lưu chỉ mục BM25. `HybridRAGPipeline._init_hybrid_retriever`
gọi `extract_documents_from_chroma` rồi `BM25Retriever.from_documents`. Với 361 chunk,
dựng lại mất vài giây. Với corpus lớn, đây là điểm cần tối ưu (lưu chỉ mục BM25 ra
đĩa).

---

## 7. Vòng đời một file mới (thực hành)

Giả sử thêm `data/corpus/Tầng 2/thong-bao-moi.pdf`:

1. `DocumentLoader.load_documents` quét, `tier = "Tầng 2"`.
2. Nếu PDF text: `pypdf` trích; nếu trang scan: OCR + cache.
3. `has_article_structure` quyết định chiến lược chunk.
4. Chunk nhận `source = "thong-bao-moi.pdf"`, `chunk_id` mới.
5. `create_vector_store` **xóa collection cũ** và nhúng lại toàn bộ — không phải chỉ
   thêm file mới.
6. `main.py` lần sau tự thấy dữ liệu mới vì nối lại collection.

> ⚠️ Vì bước 5 xóa toàn bộ, mọi `chunk_id` có thể đổi. Nếu đang có kết quả đánh giá
> cũ, chúng vẫn dùng được cho phân tích nhưng `chunk_id` trong JSON không còn trỏ
> đúng chunk mới. Luôn ghi ngày ingest vào báo cáo.

---

## 8. Bài tập chương

**A. Đọc regex.** Vì sao `ARTICLE_HEADING_RE` cần `^` và `MULTILINE`? Cho ví dụ một
câu bị nhận nhầm nếu bỏ `^`.

**B. Tính overlap.** Với `max_chars=1200`, `overlap_chars=150`, một Điều dài 3000 ký
tự cần bao nhiêu phần tối thiểu? Vì sao `overlap_chars` bị chặn ở `max_chars // 3`?

**C. So sánh chiến lược.** Với một bảng học phí 12 dòng, chiến lược nào giữ bảng tốt
nhất và tại sao? Với một Điều có 8 Khoản ngắn, chiến lược nào tạo chunk “giàu ngữ
cảnh” nhất?

**D. Chẩn đoán.** Sau khi ingest, số chunk là 340 thay vì 361. Nêu 3 nguyên nhân có
thể và nơi kiểm tra.

<details>
<summary>Đáp án gợi ý</summary>

**A.** `^` buộc mốc ở đầu dòng; `MULTILINE` cho `^` khớp sau mỗi `\n`. Bỏ `^`, câu
“Theo Điều 5. quy định...” giữa đoạn sẽ bị coi là tiêu đề và cắt văn bản trước đó.

**B.** Mỗi phần tối đa 1200 ký tự, nhưng overlap 150 làm phần “mới” chỉ 1050 ký tự:
(3000−1200)/1050 ≈ 1,7 → cần 3 phần. Chặn ở 1/3 để overlap không chiếm quá nhiều,
tránh chunk gần trùng lặp hoàn toàn.

**C.** Bảng: structure-aware (hoặc bất kỳ chiến lược nào có `lock_markdown_tables`) giữ
nguyên khối. 8 Khoản ngắn: structure-aware gộp tham lam các Khoản liền kề, nhãn thành
`[Khoản 1-8]`, chunk giàu ngữ cảnh hơn 8 chunk vụn.

**D.** (1) File bị `skipped` do `.doc`/OCR lỗi — xem log ingest; (2) chunk dưới
`min_chars=20` bị loại; (3) regex Điều nhận nhầm/không nhận, làm gộp hoặc tách khác;
(4) đang nối nhầm một ChromaDB cũ hoặc collection khác. Kiểm tra `loader.skipped`,
`loader.ocr_stats`, và `vector_db._collection.count()`.
</details>

Tiếp theo: [03 — Truy xuất Hybrid](03_truy_xuat_hybrid.md).
