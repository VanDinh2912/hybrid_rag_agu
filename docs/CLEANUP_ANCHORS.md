# Neo dọn repo (BƯỚC 0) — 26-10-2026

Mục tiêu của đợt dọn: **đổi cấu trúc repo mà không đổi một con số đo nào**. File này chốt các con
số neo; mỗi bước B1–B7 phải chạy lại các cổng ở §6 và khớp đúng trước khi được giữ.

## 1. Thẻ đóng băng

- `git tag research-freeze` đã tạo tại HEAD `471fb66` ("Kết phiên (nối tiếp 2): đính chính câu
  'không còn artifact' ở B5 + Ngã rẽ 36").
- **Phạm vi tag = file TRACKED.** `tools/loop/verify.py`, `src/answer_guard.py`, `src/reranker.py`
  đang **UNTRACKED** (`git status --porcelain` = `??`) ⇒ `git revert` **không** khôi phục được
  chúng. Trước mỗi bước có khả năng chạm file untracked phải chụp backup byte vào
  `tmp/backup_<bước>.zip`; riêng B4 (gom chỗ đọc env) là bắt buộc.

## 2. Chữ ký trọng tài — băm BYTE THÔ

Trích `tools/loop/verify.py::referee_fingerprint()`: `hashlib.sha256` cập nhật
`path.read_bytes()` của từng file trong `REFEREE_FILES` rồi lấy 12 hex đầu
⇒ **không chuẩn hóa EOL, không decode**: thêm/bớt một `\r` là đổi chữ ký.

- Giá trị neo: **`2911c69f740d`**

| file | sha256 (12 đầu) | bytes | EOL worktree | git |
|---|---|---:|---|---|
| `tools/loop/verify.py` | `137ee884af3c` | 14.960 | LF thuần (0 CRLF) | UNTRACKED |
| `src/answer_guard.py` | `ab4a8a73292f` | 24.279 | LF thuần (0 CRLF) | UNTRACKED |
| `src/text_utils.py` | `5f810aa52b6b` | 1.235 | CRLF toàn bộ (23 dòng) | TRACKED; index LF, worktree CRLF, không attr |

Hệ quả áp cho cả đợt: (a) B1 **không** chuẩn hóa EOL ba file này — chỉ đề xuất vào
`docs/PENDING_APPROVAL.md`; (b) `src/config.py` (B4) không được sửa ba file này; (c) mốc kiểm:

```
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c "import sys;sys.path.insert(0,'tools/loop');from verify import referee_fingerprint;print(referee_fingerprint())"
```

→ kỳ vọng `2911c69f740d`.

## 3. pytest

Lệnh chuẩn — **phải dùng venv và chỉ trỏ `tests`**:

```
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
```

Neo (26-10, 14:1x): **1495 passed, 5 skipped, 3 warnings — 344,93 s**.

Hai bẫy đã gặp: `pytest -q` ở gốc repo nhặt `tmp/t3_baseline_head/` ⇒ 32 lỗi collection;
interpreter hệ thống thiếu `pypdfium2`/`streamlit` ⇒ lỗi collection giả (không phải test đỏ).

## 4. Round neo retrieval-only: `r11`

Round pha truy xuất đã đóng: có `retrieval.jsonl` 811 dòng và **không có `full.jsonl`** — cùng
nhóm với `r2, r4, r11, r12, r13, r14_repro_off, r15_repro_on` (đều 811 dòng). Chọn `r11` vì là
round gần nhất đủ bộ 811 item và từng được chấm bằng cả hai trọng tài với 0 lệch.

Số neo đọc từ `data/loop/rounds/r11/verdicts_retrieval.jsonl` (sha256 12 đầu `d0a1b08dd096`):

- n = 811; verdict **FAIL_RETRIEVAL = 182**, **PENDING_GENERATION = 629**.
- `n_gold_items` = 700 (dòng `has_gold_chunk = true`); `gold_in_top_k` = 518
  ⇒ **gold@6 = 0,74** theo đúng mẫu số 700 của `gold_in_top_k_rate` (`tools/loop/gate.py`).
  (Nếu lấy mẫu số 811: 0,6387 — ghi kèm để không lẫn hai định nghĩa.)
- Lúc đóng, round chấm bằng trọng tài gốc `9f1179ccab74`; bản chấm lại bằng trọng tài hiện hành
  `2911c69f740d` cho **0 lệch verdict, 0 item drift** ⇒ so được với các round chấm bằng v2.

Mốc kiểm:

```
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/rescore_retrieval_round_v2.py --rounds r11 --phase retrieval --out tmp/anchor_r11_rescore_v2.json
```

→ kỳ vọng `[r11] 811 dòng: retrieval verdict FAIL_RETRIEVAL=182 PENDING_GENERATION=629; so với bản
công bố: 0 lệch; item drift 0`.

Tác dụng phụ đã biết: lệnh ghi lại `data/loop/rounds_v2/r11/verdicts_retrieval.jsonl` và
`data/loop/rounds_v2/r11/round_summary_retrieval.json` (bản chấm lại của phiên B, **không phải**
bản công bố). `verdicts` byte-identical mỗi lần (sha `d0a1b08dd096`); `round_summary` chỉ đổi
`generated_at`. Bản công bố `data/loop/rounds/r11/` **không bị ghi**.

Đọc nhanh, không chạy lại phép đo: `venv/Scripts/python.exe tmp/b0_anchor_numbers.py`.

## 5. Golden cho B4 — mọi cờ = mặc định

- Máy hiện không đặt biến env nào trong danh sách (`env` lọc theo tiền tố cờ = rỗng).
- File `tmp/b0_golden_env_off.txt`, **3.302 byte / 41 dòng giá trị**:
  - sha256 toàn file: `ccc8a92e1d928ba09b8203f59a9058f4b809788bd2b65830dd8958531243a1bb`
  - sha256 41 dòng giá trị (` = `): `0ff9135504e5613d922c21b398469e20ce396e6da81434d1cbb4ee582f7fe410`
- Nội dung: **A** — 23 getter đọc env (cờ, ngưỡng, mô hình, thiết bị, quota) sau khi xoá sạch
  41 tên biến env khỏi `os.environ`; **B** — đầu ra 12 lời gọi hàm thuần trên input cố định
  (`check_grounding` cả ca đúng và ca bịa số, `extract_entities`, `decide_pre_generation` cả ca
  có căn cứ và lạc đề, `build_header`, `looks_like_table`, `split_sentences`,
  `heuristic_faithfulness`, `clean_normalized_text`, `token_containment`).
- Chụp lại: `venv/Scripts/python.exe tmp/b0_capture_golden.py` — đã chạy 2 lần, cùng sha.
- Luật so sánh ở B4: so **41 dòng giá trị**; dòng `# số tên env quét được` được phép đổi khi tên
  biến chuyển vào `src/config.py` (không tính là lệch số đo).
- Giới hạn phải nói rõ: golden chốt **giá trị env + hành vi hàm thuần**, không chứng minh đầu ra
  tuyến RAG (embedding/LLM) không đổi; tuyến đó được bảo vệ gián tiếp bởi §4 và bởi luật cấm sửa
  file đo.

## 6. Cổng sau MỖI bước

1. pytest `tests`: 1495 passed / 5 skipped.
2. fingerprint: `2911c69f740d`.
3. round `r11`: 182 / 629, gold@6 0,74, `0 lệch`.
4. (chỉ B4) golden: sha 41 dòng = `0ff913…`.

Lệch bất kỳ mục nào ⇒ `git revert` commit của bước đó (file tracked) + khôi phục file untracked từ
backup byte + ghi lý do, và **bỏ bước**.

## 7. Bảng neo trước/sau

| mốc | fingerprint | pytest | r11 FAIL/PENDING | r11 gold@6 | golden (41 dòng) |
|---|---|---|---|---|---|
| B0 — trước dọn | `2911c69f740d` | 1495 / 5 skip | 182 / 629 | 0,74 | `0ff9135504e5` |
| sau B1–B7 | điền ở KẾT PHIÊN | | | | |

Ghi chú B2 (26-10 chiều): đã cắt **một bước con** của B2 — chuyển `learn.py` + `benchmark_chunking.py`
vào `tools/` — vì làm đỏ bất biến #7 trên dữ liệu train (74 dòng `metadata.file` không còn tồn tại);
lý do đầy đủ ở AUTONOMY_LOG (Ngã rẽ 37) và PA-43. Sau khi cắt, cả 4 cổng §6 khớp neo
(pytest 1495/5, `2911c69f740d`, r11 182/629 + 0 lệch).
