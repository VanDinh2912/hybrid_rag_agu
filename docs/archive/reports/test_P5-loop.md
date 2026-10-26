# Báo cáo kiểm thử — Test Engineer, vòng lặp P5 (`D:/DoAn/hybrid_rag_agu`)

Ngày: 2026-10-24 · Nhánh: `auto/overnight` · Vai trò: kỹ sư kiểm thử (QA pass, không phải task T0–T6).

Phạm vi: kiểm chứng bộ test của các lever cờ env và các bất biến `data/loop/README.md`
đã dựng trong T0–T6. Đây là **một lượt QA trên mã đã tồn tại**, không phải lượt thêm
tính năng — nên "số test thêm mới = 0" là kết quả trung thực, không phải thiếu sót
(trong lượt này **không phát hiện lỗi chức năng nào**, nên nguyên tắc "viết test trước
khi sửa lỗi" không kích hoạt; xem mục "Kết luận").

## 1. Đã làm gì

1. Chốt baseline: chạy toàn bộ `tests/` bằng `venv` → **691 passed, 0 failed** (nguồn: `venv/Scripts/python.exe -m pytest tests -q`).
2. Kiểm chữ ký trọng tài **trước và sau** toàn bộ thao tác: `referee_fingerprint() == 9f1179ccab74` (nguồn: `tools/loop/verify.py::referee_fingerprint`; hành vi đã được ghim bằng test ở `tests/test_loop_verify.py:195-219`).
3. Viết và chạy **mutation check** (nguyên tắc #3): chủ đích phá logic của 6 lever/bất biến, chạy module test tương ứng, xác nhận ≥1 test chuyển đỏ, rồi hoàn nguyên byte-identical. Harness tái lập được: `tmp/mutation_check.py` (mỗi vòng: đọc bytes gốc → patch 1 đoạn → pytest module → ghi bytes gốc lại → so SHA-256).
4. Hoàn nguyên và **xác minh** sau khi phá: không còn chuỗi `# MUTATION` trong `src/ tools/ tests/`; 5 tệp đã chạm trở về LF thuần (`CRLF count = 0`); `git diff --stat src/router.py src/query_normalizer.py` trả về đúng các con số **trước** khi chạy (router +105, query_normalizer +161) ⇒ nội dung không đổi, chỉ có tác dụng phụ dòng kết thúc (xem §5).
5. Chạy lại `pytest tests -q` sau hoàn nguyên → **691 passed**.

## 2. Số test

| Đại lượng | Giá trị | Nguồn |
|---|---|---|
| Tổng test bộ `tests/` (venv) | **691 passed** | `venv/... -m pytest tests -q` |
| Test thêm mới lượt này | 0 (không phát hiện lỗi chức năng) | — |
| Test đỏ sau hoàn nguyên | 0 | `pytest tests -q` |
| Module KHÔNG chạy được bằng Python hệ thống | 3 (thiếu dep tùy chọn) | xem §5 |
| `pytest tests -q` bằng Python hệ thống (3.14) | 677 passed + 3 collection ERROR | `python -m pytest tests -q` |

Số test theo module đã mutation-check: `test_answer_guard` 36 · `test_answer_rescue` 23 ·
`test_query_normalizer_guard` 27 · `test_reranker_flag` 46 · `test_router_soft_filter` 34 ·
`test_decoupled_refusal` 29 · `test_evidence_selection` 18 · `test_loop_gate` 33 ·
`test_loop_verify` 30 · `test_loop_triage` 16 · `test_loop_testset` 5 · `test_pipeline` 24.

## 3. Bảng mutation check (lỗi cố ý → test nào bắt)

Mỗi dòng: phá **một** quyết định logic, chạy module test của chính tính năng đó. Tất cả
6/6 đều **BẮT ĐƯỢC** (≥1 test đỏ) và **hoàn nguyên OK** (SHA-256 khớp bytes gốc sau khi trả).

| # | Tính năng bị phá (đổi chủ đích) | Tệp | Module test | Kết quả | Test đỏ đầu tiên | Bắt được |
|---|---|---|---|---|---|---|
| M1 | Tắt guard chặn bản chuẩn hóa rác (`normalize_sanity_guard_enabled()` → `if False`) | `src/query_normalizer.py` | `test_query_normalizer_guard.py` | 3 failed / 24 passed | `test_echo_few_shot_bat_ve_cau_goc` | ✅ |
| M2 | Coi **mọi** thực thể là "có căn cứ" (mất khả năng phát hiện bịa: `if hit:` → `if True:`) | `src/answer_guard.py` | `test_answer_guard.py` | 11 failed / 25 passed | `test_số_bịa_bị_gọi_tên` | ✅ |
| M3 | Ép cờ reranker **BẬT** mặc định (`reranker_enabled()` → `return True`) — phá bất biến "cờ TẮT = đường cũ" | `src/reranker.py` | `test_reranker_flag.py` | 11 failed / 35 passed | `test_không_cờ_thì_tắt` | ✅ |
| M4 | Hạn ngạch nguồn lệch 1 suất (`used >= quota` → `used > quota`) | `src/router.py` | `test_router_soft_filter.py` | 1 failed / 33 passed | `test_mỗi_nguồn_tối_đa_quota_suat_…_giữ_thứ_tự` | ✅ |
| M5 | Đảo chiều ưu tiên nguồn (`key = pos − rank_bonus` → `pos + rank_bonus`) | `src/router.py` | `test_router_soft_filter.py` | 4 failed / 30 passed | `test_doc_thuộc_nguồn_được_dời_lên_theo_hạng` | ✅ |
| M6 | Phá chốt chống rò rỉ test→train, bất biến #2 (`if item["split"] != "trainpool"` → `if False`) | `tools/loop/triage.py` | `test_loop_triage.py` | 3 failed / 13 passed | `test_item_test_không_sinh_dòng_train` | ✅ |

Kết luận từ bảng: các nhóm test **không phải test giả** — mỗi lỗi đưa vào đều làm đỏ ít
nhất một test, và test đỏ **đúng là** test mô tả hành vi bị phá (tên test tương ứng 1-1
với mutation). Riêng M3 chứng minh nguyên tắc #4(a): hành vi "cờ tắt = đường cũ" có thật
và bị gãy ngay khi ép cờ bật.

## 4. Đã kiểm chứng là ĐẠT, không sửa gì

- **Determinism (nguyên tắc #2):** không có gọi mạng/Gemini/Ollama thật trong unit test.
  Mọi tham chiếu `ollama.*`/`genai.*` trong `tests/` là **fake/monkeypatch**
  (`tests/test_generator_prompts.py` dùng `fake_ollama` và assert `_total_calls(...) == 0`;
  `tests/test_pipeline.py:33` monkeypatch nhánh tự tạo `ollama.Client`). Toàn bộ suite chạy
  offline trong ~13–30 s.
- **Bất biến #5 (chữ ký trọng tài):** ghim bằng `tests/test_loop_verify.py` (độc định, dài 12,
  đổi khi sửa tệp, rỗng khi tắt). Chữ ký vẫn `9f1179ccab74` sau lượt này.
- **`tools/loop/gate.py` và các tệp trọng tài:** KHÔNG bị mutation, KHÔNG bị sửa
  (đúng ràng buộc #4/#5). M2 chạm `src/answer_guard.py` chỉ là patch logic thuận trong bộ
  nhớ rồi trả bytes gốc; chữ ký tính trên bytes đã hoàn nguyên nên vẫn `9f1179ccab74`.

## 5. Phần KHÔNG được kiểm thử lượt này + lý do

1. **3 module UI** (`tests/test_demo_streamlit_display.py`, `tests/test_ui_generator_flag.py`,
   `tests/test_ui_labels.py`) **lỗi khi import bằng Python hệ thống** vì thiếu phụ thuộc tùy chọn
   `streamlit` và `pypdfium2` (`ModuleNotFoundError` ở cấp import module). Đây là **khoảng hở
   môi trường, không phải lùi do tính năng** — nên không áp dụng nguyên tắc #5 (dừng & báo vì
   test cũ đỏ do tính năng mới). Chúng **xanh đầy đủ khi chạy bằng `venv`** (venv có 2 dep này);
   bằng chứng: 691 passed = 677 + 14 test của 3 module UI đó.
2. **Không có test gắn `@pytest.mark.slow`**, và cấu hình pytest **không đăng ký marker `slow`**
   (`pytest.ini`/`pyproject.toml`/`setup.cfg` không khai báo `markers`). Đây là hệ quả đúng:
   tầng sinh/truy xuất model thật **đã được fake toàn bộ** trong unit test, nên không tồn tại
   test chậm cần tách. Nếu về sau đưa test model thật vào, phải thêm `@pytest.mark.slow` **và**
   đăng ký marker — đề xuất ở §7.
3. **Ngưỡng bên trong trọng tài** (các constant chấm điểm trong `tools/loop/verify.py`) không bị
   mutation — chúng thuộc `REFEREE_FILES`; phá chúng đổi chữ ký và nằm ngoài thẩm quyền QA tự
   trị (chờ duyệt nếu muốn mở). Hành vi của chúng **có** được test (`test_loop_verify` 30 test).
4. **Golden byte-identical cho toàn pipeline:** cặp off/on được kiểm ở cấp **predicate + hành vi**
   (reranker off, classifier off, guard off, …) chứ chưa có snapshot toàn bộ đầu ra pipeline so
   byte-đến-byte. `test_pipeline` (24 test) và các test `_enabled()` phủ phần quyết định; chưa phủ
   dạng "diff toàn JSON kết quả cuối" — chấp nhận được vì đã có chữ ký trọng tài + cổng round làm
   neo.

## 6. Lệnh tái lập

```bash
cd D:/DoAn/hybrid_rag_agu
# 0) Baseline — BẮT BUỘC dùng venv (Python hệ thống thiếu streamlit/pypdfium2):
venv/Scripts/python.exe -m pytest tests -q                 # kỳ vọng: 691 passed

# 1) Chữ ký trọng tài phải còn nguyên:
venv/Scripts/python.exe -c "import sys;sys.path[:0]=['tools/loop','.'];from verify import referee_fingerprint;print(referee_fingerprint())"
# kỳ vọng: 9f1179ccab74

# 2) Mutation check (tự phá → tự đỏ → tự hoàn nguyên byte-identical, in SHA verify):
venv/Scripts/python.exe tmp/mutation_check.py
```

Chạy bằng Python hệ thống (không có venv) sẽ cho `677 passed` + 3 collection ERROR ở `test_demo_streamlit_display/test_ui_generator_flag/test_ui_labels`; đó là do thiếu 2 dep tùy chọn, không phải lỗi mã.

## 7. Đề xuất + việc cần user duyệt

- **DE-TEST-1 (duyệt):** thêm `streamlit` và `pypdfium2` vào `venv` đã có sẵn nên **không** bắt buộc;
  thay vào đó, thêm skip-if-missing-dep cho 3 module UI để `pytest tests -q` chạy xanh trên **mọi**
  môi trường. Đây là sửa test **cũ** ⇒ cần duyệt (ràng buộc #5); chưa tự làm.
- **DE-TEST-2 (duyệt):** đăng ký `markers = slow: …` trong cấu hình pytest + thêm `@pytest.mark.slow`
  khi (và chỉ khi) có test model-thật đầu tiên. Hiện chưa có test chậm nên chưa cấp thiết.
- **DE-TEST-3 (nên, không phá gì):** giữ `tmp/mutation_check.py` (hoặc nâng thành `tests/mutation/`)
  làm bước kiểm tra hồi quy mỗi lần thêm lever mới — mỗi lever mới phải có ≥1 mutation bị bắt.
- Không phát hiện lỗi chức năng ⇒ **không** đổi `src/` hay `tools/` ngoài các patch thuận đã hoàn
  nguyên; `git status` trở về đúng tập tệp như đầu phiên.
