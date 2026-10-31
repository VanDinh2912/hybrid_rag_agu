# Danh mục biến môi trường và accessor (§5)

Tài liệu sống — sinh từ REVIEW §5 ngày 31-10. Nguồn đọc duy nhất của các nhóm dưới đây là
`src/core/config.py` (`settings()` chụp ảnh `TRACKED_ENV`); đường dẫn vận hành đọc qua
`src/core/paths.py`. Bảng ghi đúng **ngữ nghĩa parse cũ**, không phải ngữ nghĩa mong muốn:
mỗi accessor là bản sao từng ký tự của site trước khi chuyển, có test đối chiếu ở
`tests/test_env_accessor_equivalence.py`.

## 1. Quy ước accessor

| Accessor | Công thức | Rỗng | Sai định dạng | Giá trị lạ |
|---|---|---|---|---|
| `text(name, default)` | `os.getenv(name, default)` | giữ `""` | — | giữ nguyên |
| `text_or(name, default)` | `os.getenv(name) or default` | → default | — | giữ nguyên |
| `text_strip_or(name, default)` | `os.getenv(name, default).strip() or default` | → default | — | giữ nguyên (đã strip) |
| `_env_str(name, default)` | như `text` | giữ `""` | — | giữ nguyên |
| `_flag(name, default="0")` | `strip().lower() in {"1","true","yes","on"}` | TẮT | TẮT | TẮT |
| `_env_flag(name, default="0")` | `strip().lower() not in {"","0","false","no","off"}` | TẮT | BẬT | BẬT |
| `_env_int(name, default, minimum=1)` | `int(raw)`, dưới `minimum` → default | default | default | default |
| `_int_env(name, default, minimum=1)` | `max(minimum, int(float(raw)))` | default | default | kẹp `minimum` |
| `_env_float(name, default, lo/hi/gt)` | `float(raw)` trong khoảng, ngoài khoảng → default | default | default | default |
| `_env_float_clamped(name, default, lo, hi)` | `min(hi, max(lo, float(raw)))` | default | default | kẹp `[lo, hi]` |
| `int_required` / `float_required` | `int(float)(env, default)` | default | **ném `ValueError`** | — |

Không thêm accessor mới nếu công thức đã có trong bảng: hai accessor tên gần giống nhưng parse
khác nhau là nguồn lỗi mà REVIEW §5 muốn loại bỏ.

## 2. Router — `src/retrieval/router.py`

| Biến | Mặc định | Kiểu | Rỗng | Sai định dạng | Ý nghĩa |
|---|---|---|---|---|---|
| `RAG_TOP_K` | `6` (`DEFAULT_TOP_K`) | int | 6 | 6 | `top_k` nền (REVIEW §3) |
| `BM25_WEIGHT` | `0.5` | float | 0.5 | 0.5 | trọng số RRF nhánh BM25 |
| `CHROMA_WEIGHT` | `0.5` | float | 0.5 | 0.5 | trọng số RRF nhánh vector |
| `ROUTER_SOFT_FILTER` | `0` | cờ whitelist | TẮT | TẮT | bật lọc mềm theo nguồn |
| `ROUTER_FILTER_RANK_BONUS` | `3` | int ≥ 0 | 3 | 3 | số hạng cộng cho nguồn ưu tiên |
| `ROUTER_SOURCE_QUOTA` | `0` | int ≥ 0 | 0 | 0 | trần suất một nguồn (0 = không trần) |

## 3. Reranker — `src/retrieval/reranker.py`

| Biến | Mặc định | Kiểu | Rỗng | Sai định dạng | Ý nghĩa |
|---|---|---|---|---|---|
| `ENABLE_RERANKER` | `0` | cờ whitelist | TẮT | TẮT | bật cross-encoder |
| `RERANKER_KEEP_CANDIDATES` | `0` | cờ whitelist | TẮT | TẮT | trả nguyên pool thay vì cắt `[:k]` |
| `RERANKER_FALLBACK` | `0` | cờ whitelist | TẮT | TẮT | lùi RRF khi lỗi (PA-18a) |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | text | default | — | id model, bắt buộc tiền tố `org/` |
| `RERANKER_DEVICE` | `cpu` | text | `cpu` | — | thiết bị chấm điểm |
| `RERANKER_CANDIDATE_POOL` | `20` | int ≥ 1 | 20 | 20 | số ứng viên đem rerank |
| `RERANKER_MAX_LENGTH` | `512` | int ≥ 1 | 512 | 512 | trần token mỗi cặp |
| `RERANKER_BATCH_SIZE` | `4` | int ≥ 1 | 4 | 4 | batch CPU |

## 4. Query normalizer — `src/core/query_normalizer.py`

| Biến | Mặc định | Kiểu | Rỗng | Sai định dạng | Ý nghĩa |
|---|---|---|---|---|---|
| `NORMALIZE_SANITY_GUARD` | `0` | cờ blocklist | TẮT | BẬT | guard chống chuẩn hóa làm mất nội dung |
| `NORMALIZE_MIN_CONTAINMENT` | `0.3` | float, kẹp 0..1 | 0.3 | 0.3 | ngưỡng token gốc còn sót |
| `OLLAMA_MODEL` | `qwen2.5:1.5b-instruct` | text | default | — | model chuẩn hóa |
| `OLLAMA_HOST` | `http://localhost:11434` | text | default | — | địa chỉ Ollama |
| `OLLAMA_TIMEOUT` | `90` | float | 90 | **ném `ValueError`** | timeout giây |

## 5. Pipeline — `src/core/pipeline.py`

| Biến | Mặc định | Kiểu | Nguồn đọc | Ghi chú |
|---|---|---|---|---|
| `BM25_WEIGHT` | tham số khởi tạo (`0.5`) | float bắt buộc | `settings().float_required` | giữ `ValueError` khi hỏng |
| `CHROMA_WEIGHT` | tham số khởi tạo (`0.5`) | float bắt buộc | `settings().float_required` | giữ `ValueError` khi hỏng |
| `ENABLE_HYBRID_SEARCH` | `1` | cờ blocklist hẹp | `os.getenv` trực tiếp | PA-26: không strip, `""` = BẬT |
| `ENABLE_QUERY_EXPANSION` | `1` | cờ blocklist hẹp | `os.getenv` trực tiếp | PA-26: như trên |
| `ENABLE_CLASSIFIER` | `0` | cờ blocklist hẹp | `os.getenv` trực tiếp | PA-26: có strip, `"off"` = BẬT |
| `ENABLE_DENSE_ORIGINAL_QUERY` | `0` | cờ whitelist | `settings()._flag` | PA-48a |

Ba cờ PA-26 cố ý **không** chuyển: chúng dùng ba ngữ nghĩa khác nhau (không strip / có strip /
tập TẮT khác nhau). Chuyển sang accessor chung sẽ đổi hành vi khi env rỗng hoặc có khoảng trắng.

## 6. Ngoại lệ đã đăng ký (không chuyển)

| Nhóm | Lý do | Tình trạng |
|---|---|---|
| `src/generator.py` | file bị chặn sửa bởi lệnh đứng (xem §6 review) | đề xuất tách ghi ở `docs/GENERATOR_SPLIT_PROPOSAL.md` |
| `src/answer_guard.py` | file trọng tài — `referee_fingerprint` băm byte | giữ nguyên |
| `src/assessment/evaluation.py` | runner đo đã công bố | chỉ đồng bộ docstring (§11) |
| `ui/demo_streamlit.py` | GUI demo, không thuộc đường production | giữ nguyên |

## 7. Kiểm tra tự động

- `tests/test_env_accessor_equivalence.py` — 128 ca env × hàm, so công thức cũ.
- `tests/test_final_env_flag_defaults.py` — mọi lever vẫn mặc định TẮT sau khi chuyển.
- `tests/test_project_paths.py` — đường dẫn vận hành đi qua `src/core/paths.py`.
