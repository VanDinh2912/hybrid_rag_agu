# Bố cục repo, ranh giới công cụ và vòng đời artifact

Tài liệu này là nguồn sự thật DUY NHẤT cho hai câu hỏi hay bị trả lời sai:

1. **Một file mới nên nằm ở đâu** — `src/`, `scripts/`, `tools/` hay `ui/`?
2. **Một thư mục kết quả có xoá được không, tái tạo bằng lệnh nào, và có được dùng
   lúc chạy hay chỉ để báo cáo?**

Nó cũng ghi lại hai đề xuất **chưa thực hiện** của `REVIEW_AND_REMEDIATION_PLAN.md`
(§9 cây `cli/` + `tools/diagnostics|experiments|training|maintenance`, §10 thư mục
`artifacts/`) và lý do — để lần sau không ai "sửa cho đẹp" rồi làm gãy chốt đã công bố.

---

## 1. Ranh giới hiện hành (đang dùng)

| Vùng | Vai trò | Ai được import / chạy |
|---|---|---|
| `src/` | **Thư viện runtime**: `core/`, `indexing/`, `retrieval/`, `generation/`, `assessment/`, `generator.py`, `answer_guard.py`, `text_utils.py` | Mọi entry point đều import từ đây. Module trong `src/` **không** được import ngược từ `ui/`, `scripts/`, `tools/`. |
| `main.py`, `ingest.py` (gốc repo) | **Entry point CLI** người dùng chạy trực tiếp: hỏi–đáp và xây index | Chạy bằng `python main.py`, `python ingest.py`. `ingest.py` có `--dry-run` và **từ chối xoá** index đã có dữ liệu trừ khi `INGEST_ALLOW_RESET=1` + `--yes` (PA-16/PA-29). Giữ ở gốc vì mọi tài liệu, lệnh trong README và test đều trỏ `ingest.py` / `main.py`. |
| `ui/` | **Giao diện**: `app.py` (Tkinter 3 tab), `demo_streamlit.py` (demo chunking), các `*_controller.py` thuần logic (không import tkinter) | `python ui/app.py`, `streamlit run ui/demo_streamlit.py`. Controller được test trực tiếp (xem `tests/test_ui_split_modules.py`). |
| `scripts/` | **Script phụ chạy tay khi làm báo cáo** — không thuộc pipeline, không có lịch chạy: `learn.py`, `benchmark_chunking.py`, `export_architecture.py` | Chạy từ gốc repo. Định nghĩa đầy đủ ở `scripts/README.md`. |
| `tools/diag/` | **Chẩn đoán & kiểm chứng chỉ-đọc**: đo index, kiểm tài liệu, chốt manifest/evidence, quét secret, đo lại round | Mỗi tệp có `argparse` và mặc định không ghi gì (trừ khi truyền `--json`/`--write`). |
| `tools/eval/` | **Đo câu hỏi thật** (`tools/eval/real_questions.jsonl`, runner/score/report) | Xem `tools/eval/README.md`. |
| `tools/loop/` | **Vòng lặp P5**: `run_round.py`, `gate.py`, `verify.py` (trọng tài), `triage.py`, `cmd chains/` | Chỉ được chạy khi round đã **đăng ký trước** trong `data/loop/README.md`. |
| `tools/train/` | **Train + build dataset** (classifier, retrieval baseline, SFT LoRA) | Artifact ghi vào `models/`; xem `models/README.md`. |
| `src/assessment/` | **Runner đo đã công bố**: `evaluation.py` (Hit@K/MRR/Citation/Faithfulness), `evaluate_classifier.py`, `analyze_ab.py` | Đây là "dụng cụ đo" — **không sửa** hành vi/tham số mặc định của ba tệp này khi chưa có quyết định. Lệnh: `python src/assessment/evaluation.py`. |
| `tests/` | Kiểm thử tự động | `pytest tests -q`. |
| `docs/` | Tài liệu sống (`ARCHITECTURE.md`, `DECISION_LOG.md`, `EXPERIMENTS.md`, …) và `docs/archive/` (bản ghi lịch sử, có banner `historical`) | — |

**Quy tắc chọn chỗ cho file mới**

- Logic dùng lại được trong pipeline → `src/<vùng>/`.
- Công cụ một lần / đọc-đo → `tools/diag/`; đo câu hỏi thật → `tools/eval/`; round →
  `tools/loop/`; train → `tools/train/`.
- Script tiện tay khi viết báo cáo → `scripts/`.
- Thử nghiệm chưa chốt → `tmp/`, **không bao giờ** `src/`.

**Vì sao không có thư mục `cli/` hay `tools/diagnostics|experiments`?** Xem §4.

---

## 2. Vòng đời artifact (REVIEW §10)

Cột "Dùng lúc chạy?" trả lời: pipeline/GUI có đọc thư mục này trong một lượt hỏi–đáp
bình thường không; "Chỉ báo cáo" nghĩa là chỉ số liệu/bản thảo hoặc phép đo đọc nó.

| Đường dẫn | Ai sinh | Xoá được? | Lệnh tái tạo | Dùng lúc chạy? |
|---|---|---|---|---|
| `chroma_db/` | `ingest.py` / GUI tab "Nạp dữ liệu" (`run_ingestion`) | ❌ **Không** xoá tuỳ tiện — đây là **index sản xuất** 361 chunk đã công bố. Xoá = phải ingest lại và mọi số Hit@K cũ mất nền. | `python ingest.py --dry-run` để xem trước; `INGEST_ALLOW_RESET=1 python ingest.py --yes` mới ghi đè (PA-16) | ✅ Runtime (mọi lượt truy xuất) |
| `indexes/experimental/chroma_db_vie/` | `tools/diag/reocr_vie.py` | ✅ Đo lại được (tốn công re-OCR) | Xem `indexes/experimental/README.md` §"Chạy lại" | ❌ Chỉ phép đo (index `_vie` **chưa kích hoạt**) |
| `indexes/experimental/chroma_db_headers_old/` | `tools/diag/build_header_index.py` | ✅ Đo lại được | Xem `indexes/experimental/README.md` | ❌ Chỉ phép đo (nền r13, kết luận ÂM) |
| `.cache/ocr/rapidocr/`, `.cache/ocr/easyocr_vie/` | `src/indexing/loader.py` | ✅ Xoá được — chỉ chậm hơn ở lần OCR kế tiếp | Tự sinh khi `ingest.py` / `scripts/learn.py` gặp PDF scan; có thể xoá rồi ingest lại | ✅ Runtime (tăng tốc OCR) |
| `.generation_cache/` | `src/generator.py` | ✅ Xoá được — câu hỏi cũ sẽ gọi lại API | Tự sinh ở lượt hỏi; xoá để ép sinh lại | ✅ Runtime (tiết kiệm quota Gemini) |
| `outputs/` | `src/assessment/evaluation.py`, `src/assessment/analyze_ab.py`, `scripts/benchmark_chunking.py`, `scripts/export_architecture.py` | ⚠️ File **đã track** giữ nguyên; file mới **không** tự stage (`.gitignore: outputs/*`). Chốt một kết quả mới thì `git add -f outputs/<file>` rồi chạy lại manifest. | Chạy lại đúng runner sinh ra tệp đó (lệnh ở §5 README) | ❌ Chỉ báo cáo (trừ khi được trích dẫn lại) |
| `logs/benchmark/`, `logs/classifier/`, `logs/export/` | `scripts/benchmark_chunking.py`, `src/assessment/evaluate_classifier.py`, `scripts/export_architecture.py` | ✅ Xoá được — chạy lại là có | Chạy lại script tương ứng | ❌ Chỉ báo cáo |
| `logs/learning/learning_log.csv`, `logs/feedback/user_feedback.json` | `scripts/learn.py` + GUI tab "Vừa test vừa học" | ❌ **Không xoá** — là dữ liệu lịch sử (log học, phản hồi người dùng) | Không tái tạo được (do người dùng sinh ra) | ⚠️ GUI đọc để hiển thị/ghi tiếp |
| `data/loop/rounds/`, `data/loop/rounds_v2/` | `tools/loop/run_round.py`, `tools/diag/rescore_rounds_v2.py` | ✅ Về mặt kỹ thuật là đo lại được, **nhưng tốn GPU và phải đăng ký round trước**; artefact hiện tại là bằng chứng đã công bố ⇒ coi như **không xoá** | `tools/loop/run_round.py` (`--phase retrieval` hoặc `--phase full`) sau khi đăng ký trong `data/loop/README.md` | ❌ Chỉ báo cáo/đo |
| `data/loop/diag/` | các `tools/diag/*` đo một lần | ✅ Đo lại được — **trừ** các tệp đã commit làm bằng chứng. PII đã được che 01-11 (PA-31, `redact_pii.py --set full`); **riêng `data/loop/testset_v1.jsonl` giữ nguyên** vì là tập đo đóng băng (sha `202ca508…`), nên bản che không làm số này về 0 | Chạy lại đúng công cụ đã sinh tệp | ❌ Chỉ báo cáo |
| `tmp/` | mọi script thử nghiệm, probe, bản nháp báo cáo | ✅ Phần lớn xoá tự do — **trừ các tệp neo** đã ghim trong `docs/evidence_pack.json` (`tmp/anchor_r11_rescore_v2.json`, `tmp/b0_golden_env_off.txt`, `tmp/b0_anchor_numbers.py`); xoá chúng làm `evidence_pack_check --check` đỏ | Tuỳ tệp; không có lệnh chung | ❌ Không (chỉ trung gian/đo) |
| `models/` | `tools/train/*` | ✅ Train lại được (tốn GPU) — xem `models/README.md` | Lệnh từng model ở `models/README.md` | ❌ Không (pipeline dùng `BAAI/bge-m3` + Ollama, không dùng adapter) |
| `ARTIFACT_MANIFEST.json` | `tools/diag/artifact_manifest.py --write` | ❌ Là **chốt** byte/sha256 của vùng artifact | `venv/Scripts/python.exe tools/diag/artifact_manifest.py --write` — chỉ khi artifact đổi **có chủ đích** | ❌ Chỉ kiểm chứng |
| `docs/evidence_pack.json` + `docs/EVIDENCE_PACK.md` | `tools/diag/evidence_pack_check.py --write` | ❌ Là **chốt** nguồn số của `docs/EXPERIMENTS.md` | `venv/Scripts/python.exe tools/diag/evidence_pack_check.py --write` — chỉ khi D-row đổi có chủ đích | ❌ Chỉ kiểm chứng |

**Vì sao `outputs/` và `tmp/` không có README riêng trong chính thư mục đó?**

- `tmp/` bị `.gitignore` chặn toàn bộ, và `tests/test_final_secret_scan.py::test_ghim_hien_trang_gitignore_da_loai_tru_tmp_models_rounds`
  ghim rằng `git add -A` **không được** stage bất cứ thứ gì dưới `tmp/`. Thêm
  `!tmp/README.md` sẽ làm test đó đỏ ⇒ vòng đời của `tmp/` ghi ở đây.
- `outputs/` nằm trọn trong phạm vi `ARTIFACT_MANIFEST.json`; thêm một tệp vào đó buộc
  phải `--write` manifest, kéo theo `ARTIFACT_MANIFEST.json` đổi hash ⇒ buộc
  `evidence_pack_check --write` (vì manifest là một anchor). Đổi hai chốt đã công bố chỉ
  để thêm một tệp tài liệu là cái giá không tương xứng ⇒ vòng đời `outputs/` ghi ở đây.

Các thư mục **đã có** README riêng (đọc thêm khi cần chi tiết): `logs/README.md`,
`models/README.md`, `indexes/README.md`, `indexes/experimental/README.md`,
`data/loop/README.md`, `scripts/README.md`, `tools/eval/README.md`.

---

## 3. Artifact nào được git theo dõi, artifact nào không

- **Tracked**: `docs/`, `src/`, `tests/`, `tools/`, `ui/`, `scripts/`, `data/corpus/`,
  `data/evaluation/`, `data/learning/` (README), `logs/README.md`, `logs/learning/`,
  `logs/feedback/`, các file `outputs/` đã chốt, `ARTIFACT_MANIFEST.json`.
- **Không tracked (nhưng vẫn nằm trên đĩa và được manifest/evidence theo dõi)**:
  `chroma_db*/`, `indexes/experimental/chroma_db*/`, `.cache/`, `.ocr_cache*/`,
  `models/*` (trừ `models/README.md`), `data/loop/rounds*/`, `data/loop/diag/**/cache/`,
  `data/training/`, `tmp/`.
- `outputs/*` và `tmp/` **không** tự stage; muốn chốt một tệp phải `git add -f`.

---

## 4. REVIEW §9 — cây `cli/` + `tools/diagnostics|experiments|training|maintenance`: CHƯA THỰC HIỆN

Đề xuất gốc (rút gọn):

```text
cli/{ingest,serve,evaluate}.py
tools/{diagnostics,experiments,training,maintenance}/
```

**Trạng thái: KHÔNG làm trong đợt này.** Lý do, theo thứ tự quan trọng:

1. `ingest.py` và `main.py` ở gốc repo là **hợp đồng đã công bố**: README, `docs/REPRODUCE.md`,
   mọi block lệnh trong tài liệu và nhiều test gọi thẳng `ingest.py` / `main.py`. Dời chúng
   phải sửa đồng loạt tài liệu và test — đúng loại thay đổi mà đợt rà soát này đang cố tránh.
2. Đổi tên thư mục dưới `tools/` làm đổi **đường dẫn nguồn** trong `docs/DECISION_LOG.md`,
   `docs/EXPERIMENTS.md` và `docs/evidence_pack.json` ⇒ `docs_consistency_check` và
   `evidence_pack_check --check` đỏ; phải re-anchor hai chốt đã công bố.
3. `tools/loop/` có **luật đăng ký trước** trỏ tới đường dẫn công cụ; dời đi phải sửa
   `data/loop/README.md` — tệp được đối chiếu với từng round đã chạy.
4. Lợi ích là thẩm mỹ; rủi ro là làm lệch bằng chứng. Tỉ lệ đó không đáng.

**Nếu sau này vẫn muốn làm**, quy tắc bắt buộc (mỗi lần chỉ một thư mục):

1. Mở PA riêng trong `docs/PA_TRIAGE.md`, ghi rõ thư mục nguồn → đích.
2. `git mv` (không copy), cập nhật import + mọi block lệnh trong `README.md` và
   `docs/planning/ROADMAP.md`.
3. Cập nhật `docs/DECISION_LOG.md` (cột "Nguồn") và `tools/diag/evidence_pack_check.py::ROWS/ANCHORS`.
4. `pytest tests -q` → `docs_consistency_check.py` → `evidence_pack_check.py --write` rồi
   `--check` → **cuối cùng** `artifact_manifest.py --check`.
5. Commit riêng cho phần move, riêng cho phần re-anchor.

---

## 5. REVIEW §10 — thư mục `artifacts/` gộp: CHƯA THỰC HIỆN

Đề xuất gộp `data/experiments/`, `artifacts/{indexes,model_outputs,evaluation_runs,manifests}`.
**Trạng thái: KHÔNG làm.** Cùng lý do §4 cộng thêm: `chroma_db/` (index sản xuất) đang
được `CHROMA_PERSIST_DIR` mặc định trỏ tới; dời nó là đổi đường dẫn runtime của **mọi**
lượt truy xuất, không chỉ đường dẫn tài liệu. Thay vào đó, §2 ở trên làm rõ vòng đời ngay
tại chỗ — đúng mục tiêu thực chất của §10.

---

## 6. Cấu hình theo profile (REVIEW §14)

`config/` chứa bốn profile mẫu (`runtime`, `offline`, `evaluation`, `experiment`).
Đọc `config/README.md` để biết cách dùng và bất biến "profile runtime không bật cờ thí nghiệm".
Mã nguồn **không** đọc thư mục này; các tệp ở đây là tài liệu + mẫu để chép thành `.env`.
