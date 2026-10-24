# Báo cáo test T1 — unit test cho `tools/diag/ablation_generation.py`

> Ngày: 2026-10-24. Vai trò: Test Engineer (stub generator, **không gọi model thật**).
> Phạm vi test: phần deterministic của script ablation tầng sinh (dựng docs theo cấu hình,
> ghép id, đếm lượt gọi, thư mục ra, metric, bảng quyết định).
> **Không sửa trọng tài**: `tools/loop/verify.py` / `src/answer_guard.py` / `src/text_utils.py`
> giữ nguyên (`git diff` rỗng, chữ ký `9f1179ccab74` vẫn khớp).

## 1. Số kiểm thử thêm / xanh / đỏ

| Hạng mục | Số |
|---|---|
| Test mới trong `tests/test_ablation_generation.py` | **24** |
| Xanh đơn lẻ (file T1) | **24 passed** |
| Đỏ sau khi sửa fixture | **0** |
| Toàn bộ `pytest tests -q` (baseline 712 + 24) | **736 passed, 0 failed** |
| Sinh bởi | `venv/Scripts/python.exe` (torch CPU — có streamlit/pypdfium2) |

24 test chia 7 nhóm, đúng 7 ca của đề bài:

| Ca đề bài | Nhóm test | Test |
|---|---|---|
| #1 cô lập `src/` | `TestIsolation` | `test_chay_docs_for_khong_ghi_vao_src`, `test_load_chunks_doc_khong_ghi_src` (so mtime_ns từng file `src/*.py` trước/sau) |
| #2 cùng tập item | `TestSameItemSet` | id ngoài r5 → `SystemExit "KHÔNG thuộc 100 item r5"`; subset → `n_base_items==2` |
| #3 ngữ cảnh theo config | `TestDocsForContext` | (a) chỉ chunk vàng, không lẫn chunk khác; (a) không gold → loại; (c) gold ± đúng 2 câu; (c) biên **đầu** và **cuối** chunk không crash, không lan ra ngoài |
| #4 lượt gọi (b) + dry-run | `TestGeminiCallCount` | dry-run **không tạo generator nào**; số lượt `generate_answer` == số item; dry-run in `todo=3` + "không gọi model" rồi dừng |
| #5 thư mục ra + chống đè | `TestOutputDirSafety` | ra đúng `data/loop/diag/<config>/`; đã có `rows.jsonl` → từ chối đòi `--force`; `--force` → **append**, giữ dòng cũ |
| #6 metric khớp tính tay | `TestMetrics` | refusal 0,25 / PASS_CORRECT 0,5 / fabrication 1/3 trên 5 dòng giả; dùng **trọng tài thật** (`referee==9f1179ccab74`); dòng `error` bị loại khỏi overall |
| #7 bảng quyết định | `TestDecisionTable` | (a thấp + b cao)→T4; (a cao)→T3; (cả hai thấp)→T2+T6; sát ngưỡng → "không kết luận được"; (a thấp, chưa có b) → "chờ (b)" |

## 2. Mutation check (`tmp/mutation_check_t1.py`)

Patch **nhân-but cấp BYTES** trên đúng `tools/diag/ablation_generation.py` (không đụng
`verify.py`), hoàn nguyên + đối chiếu SHA-256 sau mỗi vòng. Kết quả: **3/3 bị bắt, 3/3 hoàn
nguyên byte-identical** (sha256 `9c7ffa1734a5…` khớp trước/sau).

| ID | Mutation | Test đỏ | Bắt được? |
|---|---|---|---|
| M-T1-1 | **lấy nhầm chunk**: `chunks.get(gold_id)` → `chunks.get(gold_id + 1)` | `test_a_chi_goi_dung_chunk_vang` + 3 test `test_c_*` (4 failed, 20 passed) | **CÓ** |
| M-T1-2 | **bỏ ràng buộc cùng item id**: `if unknown:` → `if False:` | `test_id_ngoai_r5_bi_tu_choi` (1 failed, 23 passed) | **CÓ** |
| M-T1-3 | bỏ force guard: `if rows_path.exists() and not force:` → `if False:` | `test_thu_muc_da_co_rows_tu_choi` (1 failed, 23 passed) | **CÓ** |

Hai mutation đề bài yêu cầu ("lấy nhầm chunk", "bỏ ràng buộc cùng item id") đều bị bắt;
thêm M-T1-3 để chứng minh guard `--force` không phải chữ chết.

## 3. Phần ĐÃ thêm vào script để test được (không phải lever sản xuất)

1. **Guard `--force`** ở đầu `run_config`: thư mục đã có `rows.jsonl` thì `raise SystemExit`
   đòi cờ rõ ràng (mặc định **an toàn** — không tự đè). Đây là cổng an toàn, mặc định tắt tính
   "tự chạy tiếp", không đổi hành vi sản xuất.
2. **`interpret_decision(a_pass_rate, b_pass_rate=None, *, a_threshold, b_threshold, band)`** —
   hàm thuần, không gọi model, mã hóa bảng quyết định đã đăng ký ở `data/loop/README.md`.
   Ngưỡng **không** được đăng ký con số → tham số hóa (`a=0.15`, `b=0.30`, `band=0.02`);
   test chỉ kiểm **thứ tự nhãn** theo vị trí so ngưỡng, không tuyên bố ngưỡng chuẩn.

Cả hai chỉ dùng cho đo/chẩn đoán (`tools/diag`), không nằm trên đường sinh sản xuất nên không
cần cờ env off/on (nguyên tắc #2 áp cho `src/`).

## 4. Phần KHÔNG test được + lý do

- **Hành vi model thật** (Qwen/Gemini trả lời đúng/sai): ngoài phạm vi unit test — test dùng
  `StubGenerator` đếm lượt và bắt docs, không kiểm chất lượng câu. Route vào round thật, đã có
  ở `docs/reports/T1.md`.
- **`score_item` đúng trên văn bản thật**: metric test dùng trọng tài thật nhưng với **verdict
  đã ghi sẵn** trong `rows.jsonl` giả để kiểm **phép đếm** (refusal/PASS/fabrication); không
  kiểm lại logic chấm từng entity (thuộc phạm vi test của `verify.py`, chữ ký bất biến).
- **Gọi API Gemini thật + resume nhiều ngày (PerDay)**: cần mạng, gắn `@pytest.mark.slow` nếu
  về sau muốn; mặc định không chạy.
- **`load_chunks()` đọc chroma index thật**: test chỉ chứng minh nó **không ghi `src/`**; nội
  dung chunk vàng lấy từ nguồn production, kiểm ở vòng eval chứ không ở unit test.

## 5. Lệnh tái lập

```bash
# Toàn bộ unit test T1 (stub, không gọi model)
venv/Scripts/python.exe -m pytest tests/test_ablation_generation.py -q

# Suite đầy đủ (kỳ vọng 736 passed)
venv/Scripts/python.exe -m pytest tests -q

# Mutation check (tự vá + hoàn nguyên byte-identical)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t1.py

# Xác minh trọng tài không đổi
venv/Scripts/python.exe -c "from tools.loop import verify; print(verify.referee_fingerprint())"
```

## 6. Tiêu chí xong

| Tiêu chí | Đạt? |
|---|---|
| Stub generator, không gọi model thật trong unit test | **ĐẠT** (monkeypatch `GeminiGenerator`/`QwenGenerator` = `StubGenerator`) |
| 7 ca đề bài có test | **ĐẠT** (24 test, bảng mục 1) |
| Toàn xanh, không đỏ hồi quy | **ĐẠT** (736 passed; `git diff` trọng tài rỗng) |
| Mutation check "lấy nhầm chunk" + "bỏ ràng buộc cùng id" bị bắt | **ĐẠT** (+ M-T1-3 force guard) |
