# Đề xuất tách `src/generator.py` (REVIEW §6) — CHƯA THỰC HIỆN

**Trạng thái:** đề xuất, chờ người dùng duyệt. Không có dòng mã nào trong `src/generator.py`
bị sửa bởi tài liệu này.

**Vì sao dừng ở đề xuất**

1. Ràng buộc đang hiệu lực của phiên làm việc: **không sửa `src/generator.py`**, cùng nhóm với
   `verify.py`, `answer_guard.py`, `text_utils.py`, `gate.py`.
2. Repo đang đóng băng số đo: fingerprint trọng tài, cache generation (`PROMPT_VERSION`,
   `EXTRACT_ONLY_PROMPT_VERSION`) và các round r0–r23 được trích trong báo cáo. Một lần tách file
   sai thứ tự nạp có thể đổi `effective_prompt_version()`/cache key ⇒ số đo cũ không tái lập.
3. Đây là việc "Mức độ: Trung bình" theo REVIEW, không chặn bất kỳ lỗi hành vi nào đã sửa ở
   Phase 1–2. Làm sau khi hội đồng chốt bản nộp là an toàn hơn.

---

## 1. Hiện trạng (đo trên cây `refactor/phase1-runtime`, 31-10)

`src/generator.py` dài **1.377 dòng**, gánh 9 nhóm trách nhiệm:

| Dòng | Nhóm | Nội dung |
|---|---|---|
| 1–76 | Hằng số + docstring | `DEFAULT_MODEL`, `REFUSAL_TEXT`, `REFUSAL_MARKER`, `PROMPT_VERSION`, `EXTRACT_ONLY_PROMPT_VERSION` |
| 79–414 | Chính sách prompt/từ chối | `effective_prompt_version`, `quota_error_kind`, `rescue_min_score`, `answer_rescue_enabled`, `looks_like_refusal`, `demands_specific_value`, `canonicalize_refusal`, `is_canonical_refusal_answer`, `select_prompt_rules` |
| 416–465 | Lỗi + đọc env | `GeneratorError`, `is_quota_error`, `is_fallback_answer`, `_env_float/_env_int/_env_flag/_pick` |
| 467–597 | Chuẩn hóa ngữ cảnh + trích dẫn | `normalize_docs`, `extract_citation_from_metadata`, `inject_citations_from_metadata` |
| 599–620 | Dựng prompt Gemini | `build_prompt` + `SYSTEM_INSTRUCTION`/luật prompt |
| 622–1012 | **GeminiGenerator** | client, retry/quota, cache, citation, fallback Qwen, guard |
| 1013–1042 | Tiện ích Qwen | `_qwen_text` |
| 1044–1377 | **QwenGenerator** | prompt riêng, rescue refusal, cache, guard |

Điểm bám bên ngoài (không được đổi tên):

- `main.py`, `scripts/learn.py`, `scripts/benchmark_chunking.py`, `src/assessment/evaluation.py`,
  `tools/diag/*` import trực tiếp `GeminiGenerator`, `QwenGenerator`, `build_prompt`,
  `GeneratorError`, `effective_prompt_version`, `looks_like_refusal`, `quota_error_kind`,
  `REFUSAL_TEXT`, `REFUSAL_MARKER`, `DEFAULT_OLLAMA_MODEL`.
- `src/answer_guard.py:505`, `src/core/pipeline.py:715`, `src/generation/refusal_policy.py:295`,
  `src/core/faithfulness_heuristic.py:19` import **trễ** từ `src.generator` để tránh vòng module.
- 20+ test dùng `import src.generator as gen_module` rồi monkeypatch thuộc tính cấp module
  (`gen_module.genai`, `gen_module.ollama`, `gen_module.REFUSAL_TEXT`, …). Mọi bước tách phải giữ
  **đúng điểm vá** này.
- `src/core/cache_policy.py:60` cũng `from src import generator as generator_module`.

Ngoài ra `src/generation/` **đã tồn tại** (namespace package, chưa có `__init__.py`) với
`local_slm.py`, `refusal_policy.py`, `evidence_selection.py` — nên đích đến không phải thư mục
mới tinh.

---

## 2. Cấu trúc đích (điều chỉnh cho khớp cây hiện có)

```text
src/generation/
├── __init__.py                # thêm mới: re-export công khai, KHÔNG logic
├── generator_base.py          # GeneratorError, interface generate_answer, is_fallback_answer
├── prompt_builder.py          # build_prompt, SYSTEM_INSTRUCTION, select_prompt_rules
├── context_citations.py       # normalize_docs, extract_citation_from_metadata, inject_citations_from_metadata
├── generation_cache.py        # _cache_key/_cache_get/_cache_put (dùng chung 2 generator)
├── quota_policy.py            # quota_error_kind, is_quota_error, retry delay
├── refusal_text.py            # REFUSAL_TEXT, REFUSAL_MARKER, looks_like_refusal, canonicalize_refusal,
│                              # is_canonical_refusal_answer, demands_specific_value, rescue_min_score
├── gemini_generator.py        # GeminiGenerator (+ fallback hook sang Qwen)
├── qwen_generator.py          # QwenGenerator, _qwen_text, _rescue_refusal
└── (đã có) local_slm.py, refusal_policy.py, evidence_selection.py
```

`src/generator.py` sau cùng chỉ còn **re-export** đúng các tên cũ ở mục 1 để `from src.generator
import X` và `src.generator.X` tiếp tục chạy; không xoá file.

Khác REVIEW một điểm: REVIEW đề xuất `fallback_policy.py` riêng, nhưng fallback Gemini→Qwen hiện
gắn chặt với state của `GeminiGenerator` (cache, guard, cờ `ENABLE_*`). Tách policy thuần chỉ nên
làm ở bước 6 nếu đo được lợi ích; trước đó giữ trong `gemini_generator.py` để không đổi hành vi.

---

## 3. Thứ tự di chuyển (mỗi bước là một commit + một lần chạy test)

1. **Bước 0 — chốt baseline.** Ghi `git hash-object src/generator.py`, chạy
   `pytest tests/test_generator_prompts.py tests/test_t3_guardrails.py tests/test_t4_generator_contract.py
   tests/test_answer_rescue.py tests/test_cache_policy.py tests/test_answer_guard.py -q`. Lưu kết quả
   vào `tmp/` (không commit artifact sinh máy).
2. **Bước 1 — hằng số + refusal_text.** Chuyển `REFUSAL_TEXT`, `REFUSAL_MARKER`, các hàm
   `looks_like_refusal`… sang `src/generation/refusal_text.py`; `src/generator.py` import lại.
   *Rủi ro:* `answer_guard` và `pipeline` import trễ tên `REFUSAL_TEXT` — phải còn nguyên trên
   `src.generator` trước khi bước này merge.
3. **Bước 2 — prompt_builder + context_citations.** Chuyển `build_prompt`, `select_prompt_rules`,
   `normalize_docs`, `inject_citations_from_metadata`. Giữ `PROMPT_VERSION` ở `src/generator.py`
   (cache key phụ thuộc) và import ngược vào prompt_builder, không chuyển hằng số.
4. **Bước 3 — generation_cache.** Tách `_cache_key/_cache_get/_cache_put` thành hàm nhận
   `(model, temperature, prompt)`; hai generator gọi qua module. **Bất biến:** chuỗi key từng byte
   phải giữ nguyên — test `test_cache_policy.py` + `test_t7_cache_reuse_e2e.py` là lưới an toàn.
5. **Bước 4 — tách QwenGenerator** (ít phụ thuộc hơn) rồi **Bước 5 — GeminiGenerator**. Mỗi bước
   chạy lại toàn bộ danh sách test ở Bước 0 + `tests/test_decoupled_refusal.py`.
6. **Bước 6 — dọn re-export.** Chỉ đổi import nội bộ sang module mới; tên cũ vẫn re-export. Không
   xoá `src/generator.py`.

Mỗi bước phải giữ **hành vi từng ký tự khi cờ TẮT** (bất biến #2 của repo): so sánh
`build_prompt` và cache key trước/sau bằng golden snapshot, không chỉ dựa vào test xanh.

---

## 4. Kiểm chứng bắt buộc trước khi merge

```bash
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/env_flag_audit.py
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/docs_consistency_check.py
```

Thêm một test ghim `src.generator` re-export đủ tên (danh sách ở mục 1) — nếu ai xoá re-export,
test đỏ ngay thay vì lỗi import lúc chạy runner đo.

**Không** chạy `tools/loop/run_round.py`, `src/assessment/evaluation.py` hay bất kỳ runner đo nào
để "xác nhận" việc tách file: fingerprint/cache đã đóng băng; kiểm chứng bằng test + so byte
prompt là đủ.

---

## 5. Quyết định cần người dùng

- [ ] Duyệt tách theo thứ tự 6 bước trên (khuyến nghị: sau khi chốt bản nộp).
- [ ] Hoặc giữ `src/generator.py` nguyên trạng và chỉ ghi nhận nợ kỹ thuật này trong
      `docs/DECISION_LOG.md`.

Cho đến khi có quyết định, mọi thay đổi tiếp theo **không** đụng `src/generator.py`.
