# `indexes/experimental/` — index ChromaDB thực nghiệm (KHÔNG phải đích production)

Thư mục này chứa các index **để đo**, không cái nào được pipeline đọc: đường dẫn production
là `./chroma_db` (đặt qua `CHROMA_PERSIST_DIR`, mặc định trong `src/retrieval/vector_db.py` và `ingest.py`).
Toàn bộ cây do `chroma_db*` trong `.gitignore` nên **không được git track** — snapshot bên dưới
chỉ tồn tại trên máy đã chạy lượt đo tương ứng.

## Ánh xạ đường dẫn cũ → mới (tái cấu trúc 28-10, `docs/RESTRUCTURE_MAP.md` §5.2)

| Đường dẫn cũ (xuất hiện trong `docs/EXPERIMENTS.md`, `data/loop/**`, artifact 24-10/26-10) | Đường dẫn mới | Số chunk | Trạng thái |
|---|---|---|---|
| `chroma_db_vie/` | `indexes/experimental/chroma_db_vie/` | 342 | re-OCR EasyOCR `vi`, **CHƯA kích hoạt** — mất neo vàng 48,81%, chờ PA-17 re-anchor |
| `chroma_db_headers_old/` | `indexes/experimental/chroma_db_headers_old/` | 361 | snapshot làm nền phép đo header r13 (T5 25-10, kết luận ÂM) |
| `chroma_db/` | `chroma_db/` (không đổi) | 361 | index SẢN XUẤT |

Việc di chuyển chỉ đổi **đường dẫn**: từng tệp đã được băm trước/sau và **khớp byte 5/5 + 5/5**
(bằng chứng: `tmp/restructure/phase2_hashes.json` + `tmp/restructure/phase2_verify.py`).
Vì vậy mọi con số đã công bố gắn với hai index này vẫn đọc được nguyên văn.

## An toàn ghi

`src/indexing/contextual_header.py::PROTECTED_INDEX_DIRS` liệt kê **cả tên cũ lẫn đường dẫn mới**
(`indexes/experimental/chroma_db_vie`, `indexes/experimental/chroma_db_headers_old`), vì
`ensure_separate_index_target()` so đường dẫn đã resolve theo gốc repo chứ không so tên cuối.
Hệ quả có chủ đích: `indexes/` và `indexes/experimental/` cũng bị từ chối làm đích build
(chúng là thư mục cha của index được bảo vệ) — index mới phải là thư mục con phía trong,
ví dụ `indexes/experimental/<tên_mới>`. Đo chứng minh (28-10, trước/sau khi nối đường dẫn
mới): `pytest tests/test_t5_contextual_header.py` 42 passed (0 skip), và chốt lỏng thật được
chứng minh bằng probe đột biến trước khi sửa. **Nợ**: bộ test hiện chỉ khai báo tên cũ
(`chroma_db_vie`) trong `test_guard_tu_choi_ghi_de_index_cu`, chưa có test ghim tên mới ⇒ đã
đăng ký cùng PA-48 (`docs/PA_TRIAGE.md`) để ai đó thêm test bền vững.

## Chạy lại các phép đo trên đường dẫn mới

```bash
# Đo chất lượng index re-OCR (chỉ đọc)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/measure_index.py \
  --db ./indexes/experimental/chroma_db_vie --out tmp/index_after.json

# So corpus cũ ↔ mới (mặc định --new-db đã trỏ đường dẫn mới)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/check_corpus.py
```
