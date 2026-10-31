# Phân loại PA-1…PA-48 + PA-54…PA-59 (27-10; PA-48 thêm 28-10, **đã áp `ed0fc74` 29-10**; PA-54–55 thêm 29-10, **đã đóng 29-10**; PA-56–59 đề xuất 31-10, **PA-57 đã áp `18ecc88`**, còn lại hoãn/đóng — xem mục cuối)

PA-49…PA-53 không nằm trong bảng này — ghi thành mục riêng trong `docs/archive/PENDING_APPROVAL.md`.
PA-56…PA-60 là đề xuất 31-10, ghi ở mục riêng cuối tệp (đã chốt quyết định 31-10).

Mục đích: một bảng để quyết định việc duyệt tiếp theo, **không** áp PA nào. Ba nhóm:

- **(a) ảnh hưởng số đo/benchmark** — đụng mã đường chạy, dữ liệu, index, trọng tài hoặc cổng; mọi
  thay đổi phải kèm round mới và đủ 4 cổng.
- **(b) môi trường/tài liệu** — đường dẫn, git, manifest, cách chạy, cách phát ngôn; không đổi số đo.
- **(c) refactor** — dời/tách mã, giữ nguyên hành vi; rủi ro là bất biến #7 và PA-26.

Cột "khuyến nghị": **duyệt** = nên làm, thường rẻ và không đổi số; **đóng** = không làm nữa (đã áp,
đã bị số đo bác, hoặc khuyến nghị giữ nguyên); **hoãn** = cần điều kiện khác (duyệt ngưỡng, quota,
PA-26, re-anchor) trước khi làm.

Đếm: (a) 26 · (b) 19 · (c) 5 (50 hàng; PA-55 thuộc (b) nhưng dòng đếm cũ ghi 18). Đã đóng 18:
PA-2, 5, 6, 9, 10, 19, 20, 25, 34, 45, 47, **48 (đã áp `ed0fc74`), 54 (hướng phát triển),
55 (bản ghi lịch sử)**, **31 (đã áp 01-11, merge ff vào `main`)**, **8, 26, 33 (đối soát cây
01-11 — xem cột lý do)**.

| PA | Việc | Nhóm | Khuyến nghị | Lý do ngắn |
|---|---|---|---|---|
| PA-1 | Kích hoạt `indexes/experimental/chroma_db_vie` (path cũ `chroma_db_vie/`, đổi 28-10) + chấm lại r0–r5 | a | **hoãn** | phải re-anchor trước (PA-17/PA-21), nếu không mất 48,81% neo |
| PA-2 | Nới luật "Theo Bản" trong `answer_guard` | a | **đóng** | đã áp ở trọng tài v2 `2911c69f740d` |
| PA-3 | Sửa cổng #23 refusal tương đối + veto family | a | **hoãn** | là dụng cụ đo; phải đăng ký round mới trước khi sửa |
| PA-4 | Resume (b) đủ 30 id Gemini | a | **hoãn** | chỉ chạy khi có quota; hiện 25/30 nên chưa kết luận |
| PA-5 | Đặc tả T3/T5/TT0–TT3 không tồn tại | b | **đóng** | không còn dùng; T3/T5 đã chốt theo đặc tả khác |
| PA-6 | Giữ `easyocr` làm dependency? | b | **đóng** | chỉ dùng chẩn đoán một lần; pipeline không import |
| PA-7 | Loại 2 PDF bảng khỏi corpus | a | **hoãn** | đụng corpus/index; phải chấm lại toàn bộ round |
| PA-8 | Bằng chứng loop P5 chưa vào git | b | **đóng** | **ĐỐI SOÁT 01-11: đã có trong kho** — `tools/loop/` 15 tệp + `data/loop/testset_v1.jsonl` (và 93 tệp `data/loop/` khác) đã track; `data/loop/rounds/` + `rounds_v2/` **0 tệp** trong kho, đúng luật "không commit rounds nặng". Đưa vào kho ở `16b75fc` (Q1b) |
| PA-9 | Tầng luật ngoài phủ lên prompt cũ | a | **đóng** | r8 bác: PASS_REFUSAL 17→2, ảo giác ngoài phạm vi 2→12 |
| PA-10 | Tín hiệu "trả lời được" thay hạng truy xuất | a | **đóng** | r9 bác; `grounding_score` ≡ 1,0 nên mù lớp lạc đề |
| PA-11 | QLoRA 4-bit trên model triển khai | a | **hoãn** | cần cài `bitsandbytes` + tải 3B; câu hỏi train thật còn mở |
| PA-12 | Đổi định dạng dòng SFT vừa 1.000 token | a | **hoãn** | PA-39 là đường thay thế; cắt căn cứ phá bất biến #7 |
| PA-13 | Cổng refusal tuyệt đối → tương đối | a | **hoãn** | đổi dụng cụ đo; mới có mô-đun test tạm |
| PA-14 | Đường Gemini thiếu nhánh `DECOUPLED` | a | **hoãn** | đụng generator/prompt; lever đang TẮT |
| PA-15 | `DEC_MAX_UNSUPPORTED=1` là dead code | a | **hoãn** | sửa mã lever TẮT; cần test byte-identical |
| PA-16 | Nối `plan_index_write` vào `ingest.py` | b | **duyệt** | rẻ, chặn xoá index; không đổi số đo |
| PA-17 | Re-anchor 292 item mất neo | a | **duyệt** | mở khoá PA-1/PA-21; phải làm trước mọi chấm lại |
| PA-18 | Ba quyết định thiết kế T5 | a | **hoãn** | cần đặc tả người dùng; cách đọc đã đăng ký |
| PA-19 | Chi phí reranker vượt 60 phút | b | **đóng** | đã giải quyết 25-10 (GPU 2,05 s/item) kèm đính chính |
| PA-20 | Số ngắn khớp oan `required_entities` | a | **đóng** | đã áp ở trọng tài v2 |
| PA-21 | Neo vàng cũ không ánh xạ corpus T2 | a | **hoãn** | gộp vào PA-17 re-anchor |
| PA-22 | Manifest round thiếu thư mục index | b | **hoãn** | r13 đã chứng minh bằng nội dung; sửa manifest sau |
| PA-23 | Bốn dòng bảng điểm đã cũ | b | **hoãn** | khối đính chính đã thêm; còn chọn điểm thành phần |
| PA-24 | Danh sách `tmp/` đề xuất xoá | b | **hoãn** | chưa duyệt xoá; 92,1 MB vẫn là bằng chứng |
| PA-25 | Bỏ `fold(query)` trong reranker | a | **đóng** | đã áp; r16 đo lại, cờ vẫn TẮT chờ PA-35 |
| PA-26 | HEAD không tái lập cây đã test | b | **đóng** | **ĐỐI SOÁT 01-11: HEAD tái lập được** — `git ls-files src` = **25/25** tệp (gồm `generator.py`, `retrieval/reranker.py`, `answer_guard.py`), `git ls-files --others --exclude-standard src` = 0, working tree sạch ⇒ không còn tệp nguồn/test nào chỉ nằm trên đĩa |
| PA-27 | Khoá cache tách theo lever TẮT | a | **hoãn** | sửa `cache_policy`; phải giữ byte-identical khi TẮT |
| PA-28 | Bộ sinh SFT giữ dòng thiếu thực thể | a | **hoãn** | đụng dữ liệu train; cần chốt đặc tả T4 |
| PA-29 | 5 script thiếu argparse; `ingest` xoá index | b | **duyệt** | rẻ: thêm dry-run/xác nhận; không đổi số |
| PA-30 | `.env.example` thiếu 13 cờ lever | b | **duyệt** | rẻ, chỉ tài liệu |
| PA-31 | PII nhân thân trong artifact đã commit (89 khớp/8 tệp lúc 25-10; **640 khớp/18 tệp** trên dòng `main` sau `ea9416d`) | b | **ĐÃ ÁP 01-11** (nhánh `refactor/phase1-runtime`, merge ff vào `main`) | Che 17/18 tệp bằng `tools/diag/redact_pii.py --set full`: **564 khớp PII + 1 đường dẫn cá nhân → 0**, giữ số dòng và JSON hợp lệ. `data/loop/testset_v1.jsonl` **giữ nguyên** (76 khớp, sha `202ca508…`) vì che nó là đổi tập đo đóng băng ⇒ pin test hạ `165/9 → 76/1` có chủ đích. `thesis-final` `9c1c00e` **không đổi**, không tag `thesis-final-pii` |
| PA-32 | 3 id trùng tên train/val/benchmark | a | **hoãn** | đụng dữ liệu train; cần quyết định tách id |
| PA-33 | `.gitignore` chưa phủ vùng artifact | b | **đóng** | **ĐỐI SOÁT 01-11: đã áp 29-10** — khối "PA-33 (29-10)" phủ `tmp/`, `models/`, `data/loop/rounds/`, `data/loop/rounds_v2/`, `data/training/`, `data/loop/diag/**/cache/`; đo ngay trước khi thêm luật: 2.655 đường dẫn / 406,6 MiB chưa bị ignore (ghi trong `.gitignore`). Artifact vẫn nằm trên đĩa + được manifest theo dõi, chỉ không vào git |
| PA-34 | Điều kiện chạy test chưa đăng ký | b | **đóng** | REPRODUCE.md đã ghi venv + PYTHONIOENCODING; guard đã có |
| PA-35 | Bật `ENABLE_RERANKER` mặc định | a | **hoãn** | cổng đỏ HUMAN −6,32%; chờ PA-36 |
| PA-36 | Ngưỡng neo HUMAN −5% trên 11 cặp | a | **hoãn** | là dụng cụ đo; p=0,2266, CI chứa 0 |
| PA-37 | Tải cross-encoder nhỏ để trả lời B4 | a | **hoãn** | chưa cần; model 568M hiện có đủ |
| PA-38 | Đăng ký lại mốc "hạng truy xuất" | a | **hoãn** | nhãn degenerate 0,5; cần phép đo mới trước |
| PA-39 | Logits theo vị trí đáp án + 1 lượt train thật | a | **hoãn** | cần GPU/thời gian; câu hỏi train thật mở |
| PA-40 | Quy ước phát ngôn về bộ nhớ | b | **duyệt** | rẻ; chỉ sửa cách nói trong tài liệu |
| PA-41 | Hai kỳ vọng cũ trong audit | b | **duyệt** | rẻ; chỉ máy kiểm, không đổi số đo |
| PA-42 | Chữ ký trọng tài băm byte thô | a | **duyệt** | (a) commit 2 file untracked byte-nguyên; không chuẩn hoá EOL |
| PA-43 | Chuyển 2 script công cụ vào `tools/` | c | **hoãn** | đỏ bất biến #7 (74 dòng train); phải đổi dữ liệu cùng lúc |
| PA-44 | Gom 45 site đọc env còn lại | c | **hoãn** | rủi ro cao; nhóm (c) vẫn cần duyệt riêng, không đổi số |
| PA-45 | Tách 3 tệp đánh giá khỏi `src/` | c | **đóng** | khuyến nghị giữ nguyên (bất biến #7 + import thư viện) — **đã bị Phase 3 vượt**: commit `876e017` move cả 3 tệp vào `src/assessment/` sau khi user duyệt phạm vi đóng gói `src/`, giải #7 bằng 704 citation `metadata.file` (tiền lệ Phase 1 đã duyệt), import thư viện không đổi vì chỉ đổi path. Chi tiết + cổng: `docs/RESTRUCTURE_MAP.md` §6 |
| PA-46 | Tách `generator.py` + `negative_results` | c | **duyệt (a)** | chỉ tạo `experiments/negative_results/README.md`; (b)–(d) hoãn |
| PA-47 | Manifest ghim byte container Chroma | b | **đóng** | C1 đã cô lập test + sinh lại manifest; index digest hoãn |
| PA-48 | Re-anchor manifest + ghim chốt an toàn cho layout `indexes/`+`.cache/` | b | **đóng** | **ĐÃ ÁP 29-10, commit `ed0fc74`** (user duyệt): `_scope_dirs()` nhận `indexes/experimental/chroma_db*` + `.cache/ocr/*` (giữ glob cũ cho máy chưa dời); điều kiện cứng 36/36 hash cũ↔mới khớp byte đã kiểm TRƯỚC khi ghi (`tmp/restructure/pa48_crosscheck.py`, MẤT 0/MỚI 0/tổng 158 tệp 390.961.924 B không đổi) ⇒ `artifact_manifest --check` **KHỚP**; 2 test mới ghim `PROTECTED_INDEX_DIRS` + đối chứng "chỉ khai tên cũ thì lọt". Hệ quả: evidence pack re-pin đúng 1 mục (chính manifest), tổng 4.041.502→4.041.992 B; protected 491 báo ĐỔI 1 = manifest. Chi tiết §5.3 `docs/RESTRUCTURE_MAP.md` |
| PA-54 | Đóng gói nốt `src/generator.py` (và nếu muốn, 2 tệp trọng tài) vào `src/generation/` | c | **đóng** | **ĐÓNG 29-10 theo chỉ đạo user — ghi nhận là HƯỚNG PHÁT TRIỂN, không làm.** Điều kiện cứng: `src/answer_guard.py` import `REFUSAL_TEXT` của generator lúc chạy và là tệp bị băm trong `REFEREE_FILES`; move generator ⇒ phải đổi byte `answer_guard` ⇒ **đổi chữ ký trọng tài** `2911c69f740d` + vỡ 2 SHA-12 ghim ở `tests/test_final_council_scripts.py:446-447`. Đây là sửa dụng cụ đo. `generator.py` ở lại gốc `src/`; không đụng 4 tệp trọng tài/cây đo. Phase 3 đã thử và hoàn tác (bằng chứng `tmp/restructure/phase3_attempt1_apply.txt`) — xem `docs/RESTRUCTURE_MAP.md` §6.1, §6.5 |
| PA-55 | Xử lý 2.230 chuỗi `src/<mod>.py` cũ trong ANSWER của `data/training/sft_*.jsonl` + 293 lần trong 42 tệp tài liệu lịch sử đã track (`docs/archive/*`, `dev/prompts/*`, `data/loop/README.md`) | b | **đóng** | **ĐÓNG 29-10 theo chỉ đạo user — BẢN GHI LỊCH SỬ.** Đây là nội dung dữ liệu đã sinh và tài liệu đã công bố, không phải citation hỏng ⇒ để nguyên là đúng luật "không sửa dữ liệu đã công bố". Muốn sạch phải **rebuild** `data/training` (đổi bộ train đã công bố, đụng benchmark) — không tự làm. Chi tiết: `docs/RESTRUCTURE_MAP.md` §6.5, §7 |

**Thứ tự rẻ trước (nếu duyệt một lượt):** PA-41, PA-30, PA-29, PA-16, PA-40 — toàn bộ là
môi trường/tài liệu, không đụng số đo. PA-42 cũng rẻ (chỉ `git add` hai tệp byte-nguyên) nhưng xếp (a)
vì đụng chữ ký trọng tài. PA-26 **đã đóng 01-11** nên nhóm (c) không còn bị nó chặn, nhưng vẫn cần
duyệt riêng từng mục; nhóm (a) chờ quyết định ngưỡng và PA-17. Không mục nào trong bảng này được tự áp.


---

## PA-56…PA-60 — đề xuất 31-10 (nhánh `fix/audit-20261031`; **PA-57 đã áp `18ecc88`**, còn lại đã chốt)

Sinh ra từ đợt rà soát toàn dự án 31-10 (ca trực tự động). Các mục dưới **không** nằm trong bảng
PA-1…PA-48 ở trên; mỗi mục ghi rõ bằng chứng đo được và điều kiện cứng trước khi áp.
Quyết định 31-10 (người dùng giao toàn quyền cho ca trực): **PA-57 áp ngay** (chỉ thêm cổng đọc,
không đổi số đo); PA-56/PA-58 **hoãn** vì đụng vùng neo/số đo; PA-59 **đóng** (không còn tệp nào
lệch byte); PA-60 **chấp nhận** bằng thứ tự cổng, không sửa dụng cụ đo.

| PA | Việc | Nhóm | Khuyến nghị | Lý do ngắn |
|---|---|---|---|---|
| PA-56 | Bỏ `load_dotenv()` **lúc import** ở `src/core/classifier.py:38`, `src/retrieval/router.py:48`, `src/assessment/evaluation.py:72`; chuyển sang đọc qua `settings()` (đã snapshot `os.environ` mỗi lần gọi) | a | **HOÃN (quyết định 31-10)** | Không sửa `src/` trong nhánh audit; lối tắt đã có: test hermetic ghim lever + preflight cảnh báo. Muốn đo sạch thì tắt `NORMALIZE_SANITY_GUARD` trong `.env` **của máy** (agent không chạm `.env`). Bằng chứng: `.env` máy này bật `NORMALIZE_SANITY_GUARD=1` ⇒ `load_dotenv()` lúc import làm **10 test hermetic đỏ** và đổi `cache_policy_deviation()` của mọi tiến trình (kể cả `run_round.py`). Sửa mã đổi byte 3 tệp trong vùng neo ⇒ phải có round mới + fingerprint, không tự áp |
| PA-57 | Ghim byte `data/training/` (24 tệp = 18 jsonl + 6 phụ, 10.672 dòng — 10.619 dòng ở cấp gốc) vào một manifest riêng hoặc thêm scope vào `ARTIFACT_MANIFEST.json` | b | **ĐÃ ÁP `18ecc88`** | `tools/diag/repro_preflight.py` + `docs/repro_pins_20261031.json` + 8 test; chỉ đọc, không đổi số đo, không đụng manifest gốc. Bằng chứng: 24 tệp này **bị gitignore + ngoài manifest** nên bị tái sinh âm thầm (13 test đỏ suốt một phiên); đã khôi phục byte-nguyên từ backup 29-10 nhưng **không có cổng nào chặn tái diễn**. Chỉ thêm manifest, không đổi số đo |
| PA-58 | Quyết định chuẩn hoá `data/corpus/` (29 tệp) với index sản xuất (26 nguồn / 361 chunk) | a | **QUYẾT ĐỊNH 31-10: giữ nguyên** | Giữ 29 tệp corpus / 26 nguồn / 361 chunk; 3 PDF 28-10 là tư liệu tham chiếu, **chưa ingest**. Chuẩn hoá phải là round mới + đo lại neo (PA-17), không làm trong nhánh audit. Bằng chứng: `ingest.py` trên thư mục hiện hành sinh **443 chunk**; 3 PDF thêm 28-10 (`dh24-ky`, `qd-1543-BGDDT`, `so-tay-sktt`) chưa ingest. Hai đường: (i) ingest thành round mới + đo lại neo, (ii) chuyển 3 tệp sang vùng "chưa ingest". Không tự chọn — đụng số đo |
| PA-59 | Re-pin `logs/README.md` (và các tệp bị manifest băm) sau khi sửa câu chữ lỗi thời | b | **ĐÓNG — không cần** | Không tệp nào trong manifest bị sửa câu chữ ở nhánh này (`logs/README.md` giữ nguyên byte); mọi sửa docs đều ngoài manifest. Nếu sau này sửa thì gộp vào lượt re-pin có duyệt. Bối cảnh: `logs/README.md` nằm trong 158 tệp manifest ⇒ sửa chữ là đổi hash; cần một lượt `artifact_manifest --write` + `evidence_pack --write` có duyệt, gộp với PA-57 |
| PA-60 | `final_number_audit.py` tự khai **CHỈ-ĐỌC** nhưng sau chuỗi cổng từng thấy `chroma_db` + `indexes/experimental/chroma_db_vie` bị tái ghi byte (`chroma.sqlite3`, `data_level0.bin`, `length.bin`) ⇒ `artifact_manifest --check` báo LỆCH ngay sau khi chạy | b | **CHẤP NHẬN, không sửa dụng cụ** | Chọn (ii): ghi thứ tự cổng — audit TRƯỚC, `artifact_manifest --check` SAU CÙNG (đã ghi `REPRODUCE.md` §5). Không sửa `final_number_audit.py` vì là dụng cụ đo đã công bố. Bằng chứng: sự kiện có thật — sau khi phục hồi byte từ backup rồi chạy chuỗi cổng, manifest LỆCH đúng 3 tệp mỗi index dù nội dung logic (361/342 embedding) không đổi; **nhưng kiểm soát lại 31-10** (băm 10 tệp → chạy riêng `final_number_audit.py` → băm lại) cho **0/10 tệp đổi** ⇒ chưa quy được cho audit, bước gây tái ghi **chưa xác định** (`tmp/chroma_hash_pa60_recheck_before/after.json`). Hai cách: (i) cho audit mở **bản sao** index, (ii) ghi thứ tự cổng: audit TRƯỚC, `artifact_manifest --check` SAU CÙNG. Sửa `tools/` là sửa dụng cụ đo ⇒ cần duyệt |

**Đã sửa ngay trong nhánh này (không cần duyệt vì không đổi số đo):** test hermetic ghim lever
chuẩn hoá (`3757344`, 4 tệp test, 38 dòng thêm); 6 tài liệu sống hết lỗi thời (29 tệp corpus /
361 chunk / đường dẫn `src/assessment/*` / cây `src/` 5 tiểu package); `docs/REPRODUCE.md` thêm
2 cảnh báo tái lập. Chi tiết + quyết định: `tmp/CA_TRUC_20261031.md`.
