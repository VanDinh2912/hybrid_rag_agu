# Rà soát và phương án cải thiện dự án

> Tài liệu này tổng hợp kết quả rà soát cấu trúc, logic và chất lượng mã nguồn của
> `hybrid_rag_agu`. Phạm vi rà soát chỉ đọc; tài liệu này không thay đổi hành vi
> hiện tại của hệ thống.

## 1. Kết luận tổng quan

Dự án hiện có nền tảng nghiên cứu khá đầy đủ, nhiều test và nhiều guardrail cho
pipeline RAG. Tuy nhiên, codebase đang pha trộn giữa:

- Mã vận hành chính.
- Mã đánh giá và thí nghiệm.
- Script chẩn đoán.
- Artifact kết quả.
- Snapshot kiểm thử.
- Tài liệu lịch sử.
- Môi trường Python cục bộ.

Vì vậy, dự án vẫn phù hợp cho đồ án nghiên cứu, nhưng chưa thật sự clean và
chưa có ranh giới rõ ràng để phát triển như một sản phẩm lâu dài.

Các ưu tiên cao nhất:

1. Làm mới retriever sau khi ingest.
2. Không hiển thị thành công khi rebuild thất bại.
3. Thống nhất cấu hình `top_k`.
4. Chuẩn hóa đường dẫn theo root của project.
5. Làm rõ cấu hình, artifact và ranh giới giữa các thư mục.

---

## 2. Lỗi logic cần ưu tiên xử lý

### 2.1. Retriever không được làm mới sau khi ingest

**Vị trí:** [`ui/app.py`](ui/app.py), đoạn cập nhật `self.pipeline.vector_db`.

Sau khi ingest, GUI chỉ thay vector database:

```python
self.pipeline.vector_db = new_vector_db
```

Trong khi đó, `pipeline.ensemble_retriever` vẫn có thể chứa BM25 retriever
được xây dựng từ danh sách document cũ. Các tài liệu mới vừa ingest vì vậy có
thể chưa được tìm thấy ngay trong lượt hỏi tiếp theo.

**Phương án xử lý:**

1. Tạo API chính thức trong `HybridRAGPipeline`, ví dụ:
   - `set_vector_db(new_vector_db)`;
   - hoặc `rebuild_retriever()`.
2. API này phải:
   - cập nhật `self.vector_db`;
   - xóa retriever cũ;
   - tạo lại BM25 từ collection mới;
   - tạo lại Chroma retriever;
   - giữ nguyên `use_hybrid` và trọng số hiện tại.
3. GUI chỉ gọi API này, không gán trực tiếp thuộc tính nội bộ.
4. Nếu rebuild retriever thất bại, phải trả về lỗi rõ ràng.
5. Thêm test kiểm tra:
   - ingest một collection mới;
   - retriever chứa document mới;
   - pipeline tìm được document mới ngay sau ingest.

**Mức độ:** Cao.

### 2.2. Hiển thị thành công dù rebuild học thất bại

**Vị trí:** [`ui/app.py`](ui/app.py), luồng `save_wrong_feedback`.

Hiện tại lỗi rebuild chỉ được in ra bằng `print`, nhưng thông báo cuối vẫn nói
hệ thống đã cập nhật bài học và ChromaDB thành công.

**Phương án xử lý:**

1. Tách trạng thái:
   - `feedback_saved`;
   - `note_saved`;
   - `rebuild_succeeded`;
   - `benchmark_saved`;
   - `normalization_pair_saved`.
2. Chỉ hiển thị thông báo rebuild thành công nếu thao tác rebuild thực sự hoàn tất.
3. Nếu feedback đã lưu nhưng rebuild thất bại, thông báo phải nói rõ:
   - feedback đã lưu;
   - dữ liệu học đã ghi hoặc chưa ghi;
   - ChromaDB chưa được cập nhật;
   - lỗi cụ thể.
4. Không dùng `except Exception` rồi tiếp tục theo nhánh thành công.
5. Có thể cho phép người dùng thử rebuild lại sau.

**Mức độ:** Cao.

---

## 3. Thống nhất `top_k`

### 3.1. Hiện trạng

`top_k` đang có nhiều giá trị mặc định:

- `.env.example`: `RAG_TOP_K=4`.
- `pipeline.py`: `top_k=4`.
- `router.py`: `DEFAULT_TOP_K=4`.
- `main.py`: `DEFAULT_TOP_K=6`.
- `evaluation.py`: `DEFAULT_TOP_K=6`.
- GUI test: gọi cứng `top_k=6`.

Điều này làm CLI, GUI, evaluation và pipeline có thể chạy với cấu hình khác
nhau mà người dùng không nhận ra.

### 3.2. Phương án

1. Chọn một nguồn sự thật duy nhất, nên là `src/core/config.py`.
2. Khai báo một `DEFAULT_TOP_K`.
3. Tạo accessor dùng chung để đọc `RAG_TOP_K`.
4. CLI, GUI, router, pipeline và evaluation dùng accessor đó.
5. Vẫn cho phép override minh bạch:
   - CLI bằng `--top-k`;
   - evaluation bằng `--top-k`;
   - GUI bằng control riêng nếu cần.
6. Phân biệt rõ:
   - `top_k`: số chunk đưa vào generator;
   - `retrieve_k`: số chunk dùng cho recall/evaluation.
7. Cập nhật README, `.env.example`, docstring và test.

**Khuyến nghị:** chọn `6` làm mặc định vận hành vì CLI, GUI và evaluation hiện
đã chủ yếu dùng giá trị này. Tuy nhiên, cần xác nhận lại với mục tiêu benchmark
trước khi thay đổi.

**Mức độ:** Cao.

---

## 4. Chuẩn hóa đường dẫn theo project root

### 4.1. Hiện trạng

Một số module dùng đường dẫn tương đối như:

```python
Path("data/...")
Path("outputs/...")
Path("logs/...")
```

Trong khi GUI dùng root được suy ra từ vị trí file. Kết quả có thể khác nhau
khi chạy từ root repository, IDE, task runner hoặc thư mục khác.

### 4.2. Phương án

1. Tạo module dùng chung, ví dụ `src/core/paths.py`.
2. Xác định root project từ vị trí module.
3. Khai báo các path chuẩn:
   - `PROJECT_ROOT`;
   - `DATA_DIR`;
   - `CORPUS_DIR`;
   - `EVALUATION_DIR`;
   - `LOGS_DIR`;
   - `OUTPUTS_DIR`;
   - `CACHE_DIR`;
   - `CHROMA_DIR`.
4. Cho phép `.env` override các thư mục cần thiết.
5. Thay thế dần path tương đối trong:
   - `ingest.py`;
   - `src/core/query_normalizer.py`;
   - `src/assessment/evaluation.py`;
   - `ui/demo_streamlit.py`;
   - các script vận hành chính.
6. Test chạy từ nhiều working directory khác nhau.

**Mức độ:** Cao.

---

## 5. Hoàn thiện cơ chế cấu hình tập trung

`src/core/config.py` đã gom một phần biến môi trường, nhưng nhiều module vẫn
đọc trực tiếp, gồm generator, pipeline, query normalizer, router, answer guard,
evaluation và reranker.

### Phương án an toàn

#### Giai đoạn 1: lập danh mục

Với mỗi biến môi trường, ghi rõ:

- module sử dụng;
- giá trị mặc định;
- kiểu dữ liệu;
- cách xử lý giá trị sai;
- ý nghĩa của chuỗi rỗng;
- giá trị lạ được coi là bật hay tắt.

#### Giai đoạn 2: chuẩn hóa accessor

Dùng các accessor có tên thể hiện đúng ngữ nghĩa:

- `get_bool_flag`;
- `get_optional_text`;
- `get_required_int`;
- `get_defaulted_float`.

Không nên có nhiều accessor tên gần giống nhưng xử lý khác nhau.

#### Giai đoạn 3: di chuyển từng nhóm

Nên di chuyển theo thứ tự:

1. Router.
2. Pipeline.
3. Reranker.
4. Query normalizer.
5. Answer guard.
6. Generator.
7. Evaluation.

Mỗi nhóm phải chạy regression test trước và sau khi di chuyển. Không nên gom
toàn bộ trong một commit vì dự án đang phụ thuộc vào nhiều hành vi mặc định và
cache cũ.

**Mức độ:** Trung bình đến cao.

---

## 6. Tách `src/generator.py`

`src/generator.py` đang chứa nhiều trách nhiệm: Gemini, Qwen, prompt, cache,
quota, retry, fallback, citation và guard. File lớn làm việc kiểm thử và thay
đổi trở nên khó khăn.

### Cấu trúc đề xuất

```text
src/generation/
├── generator_base.py
├── gemini_generator.py
├── qwen_generator.py
├── prompt_builder.py
├── generation_cache.py
├── quota_policy.py
├── citation_injection.py
├── fallback_policy.py
└── __init__.py
```

### Phân chia trách nhiệm

- `gemini_generator.py`: gọi Gemini.
- `qwen_generator.py`: gọi Ollama/Qwen.
- `prompt_builder.py`: dựng prompt.
- `generation_cache.py`: cache key và đọc/ghi cache.
- `quota_policy.py`: nhận diện quota và retry.
- `fallback_policy.py`: quyết định fallback.
- `citation_injection.py`: bổ sung citation.
- `generator_base.py`: interface chung.

### Cách triển khai

1. Giữ API cũ trong `src/generator.py`.
2. Di chuyển từng nhóm hàm.
3. Re-export tên cũ để không phá import.
4. Chạy test generator sau mỗi nhóm.
5. Chỉ xóa code cũ khi toàn bộ import đã chuyển.

**Mức độ:** Trung bình.

---

## 7. Tách `ui/app.py`

`ui/app.py` hiện vừa tạo GUI, vừa khởi tạo backend, chạy search, ingest,
feedback, benchmark và active learning.

### Cấu trúc đề xuất

```text
ui/
├── app.py
├── backend_controller.py
├── search_controller.py
├── ingest_controller.py
├── feedback_controller.py
├── ui_state.py
└── widgets/
    ├── search_tab.py
    ├── ingest_tab.py
    └── feedback_tab.py
```

### Phân chia

`app.py` chỉ nên giữ:

- tạo cửa sổ;
- tạo tab;
- kết nối callback;
- quản lý state giao diện.

Các controller xử lý:

- khởi tạo backend;
- search thread;
- ingest thread;
- lưu feedback;
- cập nhật benchmark;
- active learning.

### Lưu ý

- Worker thread không được cập nhật trực tiếp widget Tkinter.
- Callback UI phải đi qua `after()`.
- Không nên thay `sys.stdout` toàn cục để hiển thị log.

**Mức độ:** Trung bình.

---

## 8. Thay thế cơ chế đổi `sys.stdout` toàn cục

GUI hiện chuyển `sys.stdout` sang `StdoutRedirector` trong thời gian ingest.
Điều này có thể ảnh hưởng các thread khác và làm mất log khi chạy đồng thời.

### Phương án

1. Dùng module `logging`.
2. Tạo `QueueHandler` cho log giao diện.
3. Worker ghi log vào queue.
4. Tkinter dùng `after()` để đọc queue.
5. Backend nhận logger hoặc callback tùy chọn.
6. Giữ `print` chỉ cho CLI đơn giản, không dùng cho trạng thái quan trọng.

**Mức độ:** Trung bình.

---

## 9. Phân định lại `scripts/`, `tools/` và `src/assessment/`

### Vấn đề

Các thư mục hiện có ranh giới chưa thật rõ:

- `scripts/` và `tools/`;
- `src/assessment/` và `tools/eval/`;
- `tools/diag/` và `tools/loop/`;
- `outputs/`, `logs/`, `data/loop/diag/` và `tmp/`.

### Cấu trúc đề xuất

```text
src/
├── core/
├── indexing/
├── retrieval/
├── generation/
└── assessment/

cli/
├── ingest.py
├── serve.py
└── evaluate.py

tools/
├── diagnostics/
├── experiments/
├── training/
└── maintenance/
```

Quy ước:

- `src/`: thư viện runtime có thể import.
- `cli/`: entry point người dùng chạy trực tiếp.
- `tools/diagnostics/`: công cụ chẩn đoán.
- `tools/experiments/`: script thí nghiệm.
- `tools/training/`: train và build dataset.
- `ui/`: giao diện.

Không nên di chuyển đồng loạt. Mỗi lần di chuyển phải cập nhật import, README,
test và manifest.

**Mức độ:** Trung bình.

---

## 10. Phân loại lại artifact

Các thư mục `outputs/`, `logs/`, `data/loop/diag/` và `tmp/` đang có ý nghĩa
gần nhau nhưng chưa có lifecycle hoàn toàn rõ ràng.

### Quy ước đề xuất

```text
data/
├── corpus/
├── evaluation/
├── learning/
└── experiments/

artifacts/
├── indexes/
├── model_outputs/
├── evaluation_runs/
└── manifests/

logs/
└── runtime logs

tmp/
└── dữ liệu tái tạo, không commit

outputs/
└── kết quả đã chọn để đưa vào báo cáo
```

Nếu chưa đổi tên thư mục, cần thêm README cho `data/loop/`, `outputs/`,
`indexes/`, `tmp/` và `models/`, trong đó ghi rõ:

- nguồn tạo file;
- file có thể xóa hay không;
- lệnh tái tạo;
- file có được dùng trong runtime hay chỉ dùng để báo cáo.

**Mức độ:** Trung bình.

---

## 11. Đồng bộ tài liệu và docstring

Một số tài liệu còn lệch code hiện tại:

1. `src/retrieval/vector_db.py` mô tả trọng số `[0.4, 0.6]`, nhưng code là
   `[0.5, 0.5]`.
2. `logs/README.md` còn trỏ `src/evaluate_classifier.py`, trong khi file hiện
   tại ở `src/assessment/evaluate_classifier.py`.
3. `src/assessment/evaluation.py` có phần mô tả benchmark cũ nhưng mặc định code
   dùng benchmark v2.
4. README mô tả nhiều benchmark nhưng chưa phân biệt rõ benchmark chính thức,
   benchmark cũ và benchmark dùng cho demo.
5. Một số tài liệu archive chứa đường dẫn cũ nhưng không luôn ghi rõ đó là tài
   liệu lịch sử.

### Phương án

- Tài liệu đang dùng phải khớp code hiện tại.
- Tài liệu lịch sử được giữ nguyên nhưng thêm nhãn `historical`.
- Tài liệu sinh tự động phải ghi file nguồn và lệnh sinh.
- Thêm kiểm tra path tồn tại và giá trị mặc định trong tài liệu.

**Mức độ:** Trung bình.

---

## 12. Thu hẹp `except Exception`

Không nên thay toàn bộ một lần vì một số fallback mạng, OCR và Ollama là có chủ
ý. Tuy nhiên, mỗi `except` phải có một hành vi rõ ràng:

1. Ném lại lỗi.
2. Trả trạng thái thất bại rõ ràng.
3. Fallback có log và lý do cụ thể.

Các điểm cần xem xét trước:

- `pass` khi xóa collection trong `vector_db.py`.
- Exception trong GUI chỉ in ra console.
- Exception khiến luồng tiếp tục nhưng caller không biết đã fallback.
- Persistence JSON bị lỗi nhưng giao diện vẫn báo thành công.

Không được dùng fallback im lặng hoặc success-shaped fallback.

**Mức độ:** Trung bình.

---

## 13. An toàn khi lưu feedback và benchmark

GUI hiện ghi JSON trực tiếp vào file đích. Nếu chương trình dừng khi đang ghi,
file có thể bị hỏng; hai thao tác đồng thời cũng có thể ghi đè dữ liệu.

### Phương án

1. Ghi ra file tạm trong cùng thư mục.
2. Flush dữ liệu.
3. Thay thế file đích theo cách atomic.
4. Dùng lock khi ghi.
5. Validate schema trước khi lưu.
6. Thêm các trường:
   - `schema_version`;
   - `created_at`;
   - `raw_query`;
   - `answer`;
   - `feedback_type`;
   - `source`.
7. Kiểm tra ID benchmark không trùng trước khi append.

**Mức độ:** Trung bình.

---

## 14. Tách cấu hình runtime và cấu hình thí nghiệm

`.env.example` hiện chứa cả cấu hình vận hành, benchmark, ablation và cờ thử
nghiệm.

### Phương án

Có thể tách thành:

```text
config/
├── runtime.env.example
├── evaluation.env.example
├── experiment.env.example
└── README.md
```

Hoặc dùng profile:

```text
ENV_PROFILE=runtime
```

Các profile nên gồm:

- `runtime`: chạy CLI/GUI.
- `offline`: chỉ dùng Qwen/Ollama.
- `evaluation`: benchmark.
- `experiment`: bật lever thử nghiệm.

Không bật cờ thí nghiệm trong profile runtime.

**Mức độ:** Trung bình.

---

## 15. Thứ tự triển khai khuyến nghị

### Giai đoạn 1: sửa lỗi hành vi

1. Cập nhật retriever sau ingest.
2. Sửa thông báo thành công giả.
3. Thống nhất `top_k`.
4. Chuẩn hóa project root.
5. Thêm regression test.

### Giai đoạn 2: làm rõ cấu hình và lỗi

6. Hoàn thiện config accessor.
7. Thu hẹp `except Exception`.
8. Chuẩn hóa persistence.
9. Sửa tài liệu lệch code.

### Giai đoạn 3: tái cấu trúc

10. Tách `ui/app.py`.
11. Tách `src/generator.py`.
12. Phân định `scripts/`, `tools/` và `assessment/`.
13. Chuẩn hóa artifact directories.

### Giai đoạn 4: kiểm chứng

Sau mỗi thay đổi nên chạy:

```powershell
python -m pytest tests -q
python tools/diag/docs_consistency_check.py
python tools/diag/artifact_manifest.py --check
```

Không nên di chuyển thư mục lớn trước khi xử lý hai vấn đề logic ở GUI và thống
nhất cấu hình mặc định.
