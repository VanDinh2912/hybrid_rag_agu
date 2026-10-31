# `indexes/` — index ChromaDB KHÔNG phải bản sản xuất

Thư mục này chứa các index chỉ dùng để **đo**, không dùng để trả lời người dùng:

| Đường dẫn | Vai trò | Trạng thái |
|---|---|---|
| `indexes/experimental/chroma_db_vie/` | index re-OCR EasyOCR `vi` (342 chunk) | **Chưa kích hoạt** — mất neo vàng 48,81%, chờ PA-17 |
| `indexes/experimental/chroma_db_headers_old/` | snapshot nền cho phép đo header r13 | Kết luận ÂM; giữ làm bằng chứng |

**Index sản xuất là `./chroma_db`** (đường dẫn `CHROMA_PERSIST_DIR`, mặc định trong
`src/core/paths.py` / `ingest.py`) — nằm ở gốc repo, không nằm trong thư mục này.

## Vòng đời (REVIEW §10)

- **Nguồn tạo**: `tools/diag/reocr_vie.py` (index `_vie`), `tools/diag/build_header_index.py`
  (index header). Lệnh tái tạo ghi trong `indexes/experimental/README.md`.
- **Xoá được không**: được, nhưng là artefact của phép đo đã công bố ⇒ coi như **không xoá**;
  nếu buộc phải dựng lại thì ghi lại trong `docs/REPO_LAYOUT.md` §2.
- **Dùng trong runtime**: không. Pipeline không mở hai index này.
- **Trạng thái git**: toàn bộ `indexes/experimental/chroma_db*` bị `.gitignore` chặn
  (`chroma_db*`); byte vẫn được `ARTIFACT_MANIFEST.json` theo dõi theo sha256.

## An toàn ghi

`src/indexing/contextual_header.py::PROTECTED_INDEX_DIRS` bảo vệ hai index trên (cả tên cũ
lẫn đường dẫn mới). Hệ quả có chủ đích: `indexes/` và `indexes/experimental/` cũng bị từ
chối làm **đích build**; index mới phải là thư mục con phía trong, ví dụ
`indexes/experimental/<tên_mới>`. Chi tiết và bằng chứng: `indexes/experimental/README.md`.

## Đo lại trên một bản sao

Mở trực tiếp một index bằng ChromaDB có thể **ghi** vào nó (khoá, siêu dữ liệu), nên mọi
phép đo phải mở **bản sao**:

```bash
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/measure_index.py \
  --db ./indexes/experimental/chroma_db_vie --out tmp/index_after.json
```
