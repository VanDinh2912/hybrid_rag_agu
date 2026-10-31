# Gói bằng chứng cho `EXPERIMENTS.md` (27-10, phạm vi cập nhật 28-10)

Bảng [EXPERIMENTS.md](EXPERIMENTS.md) có 25 dòng D-01…D-42 (đánh số không liên tục, giữ nguyên
theo [DECISION_LOG.md](DECISION_LOG.md)). Mỗi dòng trích số từ một artifact nằm trong `data/loop/`,
`docs/` hoặc `tmp/`. Tệp này ghim `(path, bytes, sha256)` cho **mọi** tệp cần để đọc lại số đó, và
kiểm lại được bằng một lệnh — **không** chép artifact nặng vào git (PA-33, [PA_TRIAGE.md](PA_TRIAGE.md)).

**Phạm vi thực tế của gói (đính chính 28-10, tự công bố điểm mù):** hàng đợi của dụng cụ
`tools/diag/evidence_pack_check.py` là **25 dòng D-01…D-42 cứng trong mã**, được chốt trước khi
EXPERIMENTS.md tái cấu trúc thành **Bảng A (khoa học) + Bảng B (quy trình)**. Vì vậy gói này **chưa** ghim
bằng chứng cho các dòng mới của EXPERIMENTS.md: `C1…C6`, `C2b`, `T0`, `V1`, `V2`, `r17`, `P5`, `Q4`, `Q5`,
`Oracle (a)`, `Oracle (c)`, `r20`, `r21` — và **vẫn còn** dòng `D-16` (tổng điểm trọng số 7,2), thứ từ
28-10 chỉ nằm trong [DECISION_LOG.md](DECISION_LOG.md) chứ **không** còn là một dòng thí nghiệm.
Hai hệ quả phải đọc kèm mọi lần chạy gói này: (i) "`--check` mã 0" chỉ chứng minh 25 dòng cũ còn tái lập
được, **không** chứng minh toàn bộ EXPERIMENTS.md có bằng chứng; (ii) đường dẫn của các dòng mới được kiểm
bằng **script chỉ-đọc riêng** (`tmp/experiments_e_20261028/experiments_source_audit.py` — tồn tại từng tệp
+ chữ số đối chiếu artifact), không bằng cách sửa hàng đợi của dụng cụ. Việc mở rộng hàng đợi thuộc quyền
user (dụng cụ đo không được sửa trong ca tài liệu), nên ở đây chỉ ghi rõ khoảng trống.

## 1. Ba lệnh

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/evidence_pack_check.py
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/evidence_pack_check.py --check
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/evidence_pack_check.py --write
```

- **không cờ** (mặc định, chỉ đọc): in số D-row, số tệp, tổng byte, bao nhiêu tệp đã vào git.
- `--check`: băm lại từng tệp và so với `docs/evidence_pack.json`; báo **THIẾU / ĐỔI / JSON lệch
  spec / bảng MD lệch JSON**, trả mã 1 nếu có bất kỳ mục nào — mã 0 khi khớp.
- `--write`: sinh lại JSON và bảng ở §2 (chỉ dùng khi cây artifact đổi **có chủ đích**).

## 2. Bảng nguồn

`chính` = đúng tệp ở cột "Tệp nguồn" của EXPERIMENTS.md; `phụ` = tệp cần để đọc/đối chiếu số trong
cùng dòng (mốc baseline, cổng so sánh, nhật ký đếm); `neo` = neo đóng băng không thuộc D-row.

<!-- evidence-table:start -->

| D | Vai trò | Tệp | byte | sha256 (12 đầu) | git |
|---|---|---|---:|---|---|
| D-01 | chính | `data/loop/rounds/r1/round_summary_retrieval.json` | 6124 | `1dffdcd81cf1` | chưa |
| D-01 | phụ | `data/loop/rounds/r0/round_summary_retrieval.json` | 6132 | `7429d64c5d6a` | chưa |
| D-01 | phụ | `data/loop/rounds/r1/gate_vs_r0_retrieval.json` | 172365 | `d247900f7667` | chưa |
| D-02 | chính | `data/loop/rounds/r4/round_summary_retrieval.json` | 6164 | `a8d6e13dc7a0` | chưa |
| D-02 | phụ | `data/loop/rounds/r2/round_summary_retrieval.json` | 6131 | `d0975ac4e788` | chưa |
| D-02 | phụ | `data/loop/rounds/r4/gate_vs_r2_retrieval.json` | 15897 | `0cf21e44615a` | chưa |
| D-03 | chính | `data/loop/rounds/r5b/rescue_tally.txt` | 1966 | `ba1dceb4bc2d` | chưa |
| D-03 | phụ | `data/loop/rounds/r5b/round_summary_full.json` | 6966 | `1e4f509e7729` | chưa |
| D-03 | phụ | `data/loop/rounds/r5b/gate_vs_r5_full.json` | 9731 | `c70561f917f8` | chưa |
| D-04 | chính | `data/loop/rounds/r6/round_summary_full.json` | 6992 | `99378f180ad0` | chưa |
| D-04 | phụ | `data/loop/rounds/r6/normalizer_guard_tally.txt` | 4277 | `af3671918a08` | chưa |
| D-04 | phụ | `data/loop/rounds/r6/gate_vs_r5b_full.json` | 12726 | `468a3bc1ca0b` | chưa |
| D-05 | chính | `data/loop/rounds/r7/gate_vs_r6_full.json` | 13846 | `1bc972e8b8d6` | chưa |
| D-05 | phụ | `data/loop/rounds/r7/round_summary_full.json` | 6932 | `ce1c9bbfbe57` | chưa |
| D-05 | phụ | `data/loop/rounds/r7/combo_tally.txt` | 5293 | `759443d6705d` | chưa |
| D-06 | chính | `data/loop/diag/bonus_paired.json` | 39740 | `d090df9693d4` | tracked |
| D-06 | phụ | `data/loop/diag/bonus_paired_r1_r2.json` | 50083 | `e29bd3f8a810` | tracked |
| D-07 | chính | `data/loop/rounds/r8/round_summary_full.json` | 7464 | `54838ba05e55` | chưa |
| D-07 | phụ | `data/loop/rounds/r8/gate_vs_r5_full.json` | 25771 | `d70b0ea168a7` | chưa |
| D-07 | phụ | `data/loop/rounds/r8/attribution_vs_r5.txt` | 5536 | `08ee08706b20` | chưa |
| D-08 | chính | `data/loop/rounds/r9/round_summary_full.json` | 7615 | `9805db65b717` | chưa |
| D-08 | phụ | `data/loop/rounds/r9/gate_vs_r8_full.json` | 18471 | `b7083e6068df` | chưa |
| D-08 | phụ | `data/loop/rounds/r9/attribution_vs_r8.txt` | 3875 | `f8ea639a274c` | chưa |
| D-09 | chính | `data/loop/rounds/r10/t4_stats.json` | 7915 | `0bc52dfc6753` | chưa |
| D-09 | phụ | `data/loop/rounds/r10/round_summary_full.json` | 7364 | `7aec7449eb16` | chưa |
| D-09 | phụ | `data/loop/diag/one_variable_check.json` | 1394 | `87e802b10ff3` | tracked |
| D-09 | phụ | `data/loop/diag/t4_latency_20q.json` | 3702 | `8c9819fbf7d7` | tracked |
| D-10 | chính | `data/loop/diag/t4b_memory_probe_len.json` | 3103 | `f7772219b13f` | tracked |
| D-10 | phụ | `data/loop/diag/t4b_memory_probe.json` | 2635 | `386aae7f9f24` | tracked |
| D-11 | chính | `data/loop/diag/reranker_paired_r11_r12.json` | 166377 | `b7d823dd02d2` | tracked |
| D-11 | phụ | `tmp/probe_r12_fold.json` | 6402 | `03e6f168f77a` | chưa |
| D-11 | phụ | `data/loop/rounds/r12/round_summary_retrieval.json` | 8428 | `67879ac8e265` | chưa |
| D-12 | chính | `data/loop/diag/header_paired_r11_r13.json` | 37597 | `301244a88c09` | tracked |
| D-12 | phụ | `data/loop/diag/header_index_old_build.json` | 1159 | `621b03bbe110` | tracked |
| D-12 | phụ | `data/loop/rounds/r13/round_summary_retrieval.json` | 7896 | `3e72bb950140` | chưa |
| D-13 | chính | `data/loop/diag/corpus_diagnostics/index_after.json` | 284 | `e27986be0605` | tracked |
| D-13 | phụ | `data/loop/diag/corpus_diagnostics/index_before.json` | 282 | `47bf9e148f12` | tracked |
| D-13 | phụ | `data/loop/diag/corpus_diagnostics/quality_vie.json` | 5258 | `383281e68922` | tracked |
| D-13 | phụ | `data/loop/diag/corpus_diagnostics/easyocr_trial.json` | 1949 | `ccf36bbd7169` | tracked |
| D-13 | phụ | `data/loop/diag/corpus_diagnostics/manual_20_segments.txt` | 282491 | `fee3ce7de84f` | tracked |
| D-13 | phụ | `data/loop/diag/corpus_diagnostics/per_file.json` | 22998 | `23f2ccae828f` | tracked |
| D-14 | chính | `data/loop/diag/b_gemini_top6/bootstrap_ci_25.json` | 423 | `a5f38107f803` | tracked |
| D-14 | phụ | `data/loop/diag/b_gemini_top6/summary.json` | 35527 | `c56de3bf0471` | tracked |
| D-14 | phụ | `data/loop/diag/b_gemini_top6/id_status.json` | 14525 | `766d36ab1735` | tracked |
| D-14 | phụ | `data/loop/diag/b_gemini_top6/rows.jsonl` | 153108 | `5ddf2b1bdc67` | tracked |
| D-14 | phụ | `data/loop/diag/b_gemini_top6/settings.json` | 734 | `993191ec9a85` | tracked |
| D-16 | chính | `docs/bao_cao/danh_gia_tong_quan_2026-10-23.md` | 47101 | `dcc488f27e39` | tracked |
| D-20 | chính | `data/loop/rounds/r12/round_summary_retrieval.json` | 8428 | `67879ac8e265` | chưa |
| D-20 | phụ | `data/loop/diag/reranker_cost_gpu.json` | 38663 | `bd6bbee25d18` | tracked |
| D-20 | phụ | `data/loop/diag/reranker_cost.json` | 848 | `bb8671041993` | tracked |
| D-22 | chính | `tools/loop/chains/t5a_reranker.json` | 1198 | `c3a59927ae25` | tracked |
| D-22 | phụ | `tools/loop/chains/t7_repro_r0.json` | 1212 | `77b890111701` | tracked |
| D-22 | phụ | `tools/loop/chains/demo_dryrun.json` | 1055 | `4051b9651470` | tracked |
| D-30 | chính | `tmp/compare_r0_repro.json` | 7199 | `1a0fe4348678` | chưa |
| D-30 | phụ | `data/loop/diag/chain_manifest_t7_repro_r0.json` | 1330 | `295413c196de` | tracked |
| D-30 | phụ | `tools/loop/chains/t7_repro_r0.json` | 1212 | `77b890111701` | tracked |
| D-33 | chính | `docs/archive/reports/test_final.md` | 67360 | `32f22d09e538` | tracked |
| D-37 | chính | `data/loop/rounds_v2/r16/gate_vs_r11_retrieval.json` | 66189 | `9e526c5005f6` | chưa |
| D-37 | phụ | `data/loop/diag/reranker_paired_r11_r16.json` | 125562 | `1c0cdd686965` | tracked |
| D-37 | phụ | `tmp/probe_r12_fold.json` | 6402 | `03e6f168f77a` | chưa |
| D-37 | phụ | `data/loop/rounds_v2/r16/round_summary_retrieval.json` | 8468 | `c23bcaaac0b1` | chưa |
| D-38 | chính | `data/loop/diag/answerability_probe_r5.json` | 40156 | `577bf36a8133` | tracked |
| D-38 | phụ | `data/loop/diag/answerability_labelset_r5.jsonl` | 888362 | `182dd5cb71a6` | tracked |
| D-38 | phụ | `data/loop/diag/answerability_probe_r5_buildonly.json` | 1617 | `ce03a3e7c300` | tracked |
| D-38 | phụ | `data/loop/diag/answerability_probe_r11_retrieval.json` | 322961 | `325ac38914de` | tracked |
| D-38 | phụ | `data/loop/diag/answerability_probe_r12_retrieval.json` | 292037 | `214555de030a` | tracked |
| D-39 | chính | `data/loop/diag/answer_token_logits_probe_real_fraction.json` | 10292 | `7fbae749a7a4` | tracked |
| D-39 | phụ | `data/loop/diag/answer_token_logits_probe.json` | 5636 | `5e3a19f214b0` | tracked |
| D-39 | phụ | `data/loop/diag/answer_token_logits_probe_oom_bound.json` | 5649 | `ef6172c7b9d5` | tracked |
| D-39 | phụ | `data/loop/diag/b5_answer_fraction.json` | 22449 | `b9c55781b8f9` | tracked |
| D-39 | phụ | `data/loop/diag/b5_wddm_oversubscription.json` | 2665 | `89bdfe3cfed4` | tracked |
| D-40 | chính | `data/loop/diag/b1_cprime/analysis.json` | 15728 | `2669243d4109` | tracked |
| D-40 | phụ | `data/loop/diag/b1_cprime/mapping.json` | 21716 | `3252e0969a4b` | tracked |
| D-40 | phụ | `data/loop/diag/b1_cprime/settings.json` | 455 | `a3c1ee9ce498` | tracked |
| D-41 | chính | `data/loop/rounds_v2/compare_v1_v2.json` | 16587 | `bfc32497b78d` | chưa |
| D-42 | chính | `tmp/final_number_audit_b_shift.json` | 14175 | `dde6e59d288a` | chưa |
| D-42 | phụ | `tmp/final_number_audit.json` | 12054 | `53f4767f518a` | chưa |
| D-42 | phụ | `tmp/final_number_audit_table.md` | 7240 | `3478c9dca8ba` | chưa |
| neo | neo | `docs/CLEANUP_ANCHORS.md` | 10957 | `8c47b8480d9a` | tracked |
| neo | neo | `tools/loop/verify.py` | 14960 | `137ee884af3c` | tracked |
| neo | neo | `tools/diag/rescore_retrieval_round_v2.py` | 10027 | `1d5d8af50053` | tracked |
| neo | neo | `data/loop/rounds/r11/verdicts_retrieval.jsonl` | 697158 | `d0a1b08dd096` | chưa |
| neo | neo | `data/loop/rounds/r11/round_summary_retrieval.json` | 7896 | `00e114c09afe` | chưa |
| neo | neo | `tmp/anchor_r11_rescore_v2.json` | 657 | `cefb17a5d00c` | chưa |
| neo | neo | `tmp/b0_golden_env_off.txt` | 3302 | `ccc8a92e1d92` | chưa |
| neo | neo | `tmp/b0_anchor_numbers.py` | 2198 | `186fdacc8c48` | chưa |
| neo | neo | `ARTIFACT_MANIFEST.json` | 37225 | `414bbb81776d` | tracked |

<!-- evidence-table:end -->

## 3. Neo đóng băng

Chín tệp `neo` phía cuối bảng là đầu vào của bốn cổng sau mỗi bước (giá trị kỳ vọng ghi ở
[CLEANUP_ANCHORS.md](CLEANUP_ANCHORS.md)):

- `tools/loop/verify.py` — dụng cụ tính **chữ ký trọng tài** trên byte thô của ba tệp trọng tài.
- `data/loop/rounds/r11/` — round neo pha truy xuất (811 item, không có `full.jsonl`), cộng bản
  chấm lại bằng trọng tài v2 ở `tmp/anchor_r11_rescore_v2.json`.
- `tmp/b0_golden_env_off.txt` + `tmp/b0_anchor_numbers.py` — golden 41 dòng giá trị env/hàm thuần.
- `ARTIFACT_MANIFEST.json` — manifest 158 tệp artifact (B3), nay ổn định qua pytest nhờ C1.

## 4. Quy ước đọc bảng

- **Byte thô, không chuẩn hoá EOL.** `sha256` tính trên đúng byte trên đĩa; bảng in 12 hex đầu,
  JSON giữ 64 hex. Cùng luật với chữ ký trọng tài — thêm một `\r` là đổi hash.
- **`git` = `tracked` hay `chưa`.** Artifact nặng (`data/loop/rounds*`, `tmp/`, `chroma_db*`, model)
  phần lớn **chưa** vào git. Hash chứng minh "đúng tệp đã dùng", **không** chứng minh "đủ môi
  trường để tái lập" — phần đó ở [REPRODUCE.md](REPRODUCE.md).
- **Nguồn là tài liệu, không phải artifact đo:** D-16 (bảng điểm tổng quan) và D-33 (đếm đột biến
  từ 13 log) trích số ngay trong tệp nguồn; không có artifact JSON riêng để băm.
- **Trọng tài:** round đóng trước 25-10 chấm bằng chữ ký v1; bản chấm lại bằng trọng tài hiện hành
  nằm dưới `data/loop/rounds_v2/` (D-41). Đọc số round cũ phải dùng bản chấm lại, không trộn hai
  chữ ký.
- **Một tệp phụ xuất hiện ở nhiều dòng** (ví dụ probe fold của D-11 và D-37) chỉ được băm một lần
  trong JSON; bảng lặp lại theo vai trò của từng dòng.

## 5. Cách tái lập một dòng

Mỗi round đóng gói cùng một bộ: `round_summary_*.json` (metric + cấu hình), `gate_vs_*.json`
(so với mốc), và `attribution_*.json`/`*_tally.txt` (phân rã ca). Để đọc lại một con số:

1. mở `chính` của dòng đó, đối chiếu `metrics` và `config` với cột "Kết quả" của EXPERIMENTS.md;
2. nếu số là **delta**, mở `phụ` để lấy mốc so sánh và `n` của phép ghép cặp;
3. nếu cần chấm lại round pha truy xuất, dùng `tools/diag/rescore_retrieval_round_v2.py` với
   `--out tmp/...` — **không** trỏ vào thư mục round công bố.

## 6. Hạn chế đã biết

- **Bốn tệp `tmp/` chưa vào git** (`compare_r0_repro.json`, `probe_r12_fold.json`,
  `final_number_audit*.json`). Máy khác không có chúng thì `--check` báo THIẾU — đó là hành vi
  đúng của gói, không phải lỗi cấu hình; cần xin artifact gốc hoặc tái lập phép đo.
- **Hash không thay thế tái lập độc lập.** Nó bắt được "tệp bị sửa/xoá/đổi tên", không bắt được
  "chạy lại ra số khác vì phiên bản thư viện/model khác". Câu hỏi đó thuộc REPRODUCE.md.
- **Gói ghim cả tuyên bố mở:** D-10 và D-39 (câu hỏi train thật của SFT) đang **MỞ/CHỜ DUYỆT**;
  D-11, D-12, D-37 là kết quả âm hoặc cổng đỏ được giữ nguyên. `--check` xanh nghĩa là "đọc đúng
  tệp", **không** nghĩa là "các giả thuyết đó đúng".
- **Cache Gemini bị loại** (`b_gemini_top6/cache/`): là phản hồi thô có thể dùng lại, không cần
  cho bất kỳ con số nào trong bảng, và chứa nội dung dài không nên phát tán.
- **Không chạy lại script đo ghi đè artifact công bố.** Nếu một phép đo được chạy lại, ghi ra tên
  mới rồi `--write` lại gói; artifact cũ giữ nguyên để so.

## 7. Khi nào cập nhật gói

Chỉ khi (a) thêm/bớt một dòng EXPERIMENTS, (b) artifact nguồn được sinh lại có chủ đích, hoặc
(c) neo đổi sau một bước dọn. Khi đó: chạy `--write`, chạy `--check`, rồi ghi lý do vào
`DECISION_LOG.md` (nếu là số đo mới) — không sửa tay bảng ở §2.
