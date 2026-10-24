# AUTONOMY_LOG — phiên tự trị qua đêm (23-10 → 24-10)

Chế độ: người dùng ngủ, TUYỆT ĐỐI không hỏi. Mỗi ngã rẽ chọn phương án BẢO THỦ NHẤT
(không phá dữ liệu, không đổi trọng tài, ít tốn quota), ghi ở đây rồi làm tiếp.
Việc cần duyệt → KHÔNG tự làm, ghi vào `docs/PENDING_APPROVAL.md`.

---

## 00:1x — Ngã rẽ: chi nhánh git khi cây làm việc đang dirty

Bối cảnh: `main` có nhiều file `src/` (generator, pipeline, query_normalizer, router) và
tests đang sửa DANG (từ công việc r6/r7 của phiên/automation khác), chưa commit.

Lựa chọn:
- (A) commit toàn bộ `-A` lên nhánh mới → LOẠI (dính cả công việc người khác, có thể chưa xanh).
- (B) tạo `auto/overnight` từ HEAD hiện tại, cây giữ nguyên; MỖI bước chỉ `git add <đường dẫn
  artifact của em>` rồi commit. File `src/` dirty của người khác KHÔNG commit, KHÔNG revert.
- (C) ở lại main → LOẠI (đề bài yêu cầu nhánh riêng).

**Quyết định: (B).** Lý do: không phá/chiếm công việc đang dở của phiên khác; commit tối thiểu,
review được. Hoàn tác: `git checkout main` (các commit của em nằm ở `auto/overnight`, main
không đổi); file dirty của người khác vẫn còn nguyên trong cây.

## 00:1x — Ngã rẽ: T1 cấu hình (b) khi quota Gemini hết giữa chừng

Bối cảnh: (b) `b_gemini_top6` chạy resume → 7 dòng hợp lệ / 30, 26 dòng lỗi PerDay. Luật ngân
sách: ≤14 Gemini/đêm, "hết quota thì bỏ qua phần cần Gemini", "lỗi/timeout không tính quota".

**Quyết định: KHÔNG cố gọi thêm Gemini đêm nay.** Ghi T1 với (b) = n=7/30, dán nhãn "bị chặn
quota, chưa đủ n, không ngoại suy, không chốt nhánh bảng quyết định". Hoàn tác: không có ghi đè;
chỉ sửa `docs/reports/T1.md`. (b) tiếp tục vào các ngày sau bằng đúng lệnh resume cũ.

## 00:1x — Ngã rẽ: T2 Bước 2 chọn hướng nào (đã hỏi thì đáp án là "tự trị")

Bối cảnh: 13 PDF scan là ảnh thuần (không text-layer), repo không có bản gốc .docx, chỉ còn OCR.
EasyOCR `vi` trial đạt 0,73–0,83 nhưng KHÔNG đảm bảo "Điều/Khoản khớp 100%".

Lựa chọn bảo thủ:
- (A) OCR cả 13 tệp, ghi đè corpus sản xuất → LOẠI (phá dữ liệu + đổi đầu vào trọng tài).
- (B) OCR cả 13 tệp vào **cache MỚI** `.ocr_cache_vie/` (không đụng `.ocr_cache`), build **index
  MỚI vào thư mục riêng** `chroma_db_vie/`, KHÔNG kích hoạt, KHÔNG chấm lại round; đo chất lượng
  thật (Step 3) và để việc "kích hoạt + chấm lại r0–r5" vào PENDING_APPROVAL.
- (C) chỉ OCR tệp ≥0,6 → cân nhắc; nhưng vì mọi thứ nằm ở bản sao mới, chưa kích hoạt, chọn (B)
  để có số liệu đầy đủ cho người dùng quyết; tệp mờ/không cứu được vẫn bị đánh dấu "khoảng trống"
  trong báo cáo.

**Quyết định: (B).** Không phá dữ liệu gốc, không đổi trọng tài, 0 Gemini. Hoàn tác: xóa
`chroma_db_vie/` + `.ocr_cache_vie/` (bản gốc `chroma_db/`, `.ocr_cache/` không hề bị đụng).

## 04:0x — Ngã rẽ: T2 xong, có "kích hoạt" index mới và chấm lại r0–r5 không?

Bối cảnh: `chroma_db_vie/` (342 chunk, từ có dấu 0,803) đã build xong và đo đạt ngưỡng ≥60%.
Đề bài ban đầu nói "DỪNG trước khi chạy lại round"; đề bài tự trị liệt kê "chuyển chroma_db sang
index mới" và "chạy lại/chấm lại round r0–r5" là **việc cần duyệt ⇒ KHÔNG tự làm**.

Lựa chọn:
- (A) trỏ `.env`/mặc định sang `chroma_db_vie` rồi chạy round → LOẠI: đúng hai việc bị cấm,
  đổi đầu vào của mọi số liệu đã đóng, tốn quota Gemini.
- (B) giữ nguyên cấu hình sản xuất, nộp PA-1 kèm lệnh tái lập + danh sách round chấm lại.

**Quyết định: (B).** Hoàn tác: không có thay đổi nào để hoàn tác; index mới nằm riêng.

## 04:0x — Ngã rẽ: T3/T5/TT0–TT3 không có đặc tả trong repo

Bối cảnh: thứ tự đêm nay yêu cầu "viết code + test cho T3 và T5 với mọi cờ TẮT" và "chạy test
TT0–TT3". Tìm trong `ROADMAP.md`, `docs/`, `*.md`: không có đầu bài T3/T5/TT0–TT3 (chỉ có tên
nhóm trong bảng quyết định T1).

Lựa chọn:
- (A) tự suy đoán yêu cầu rồi viết lever → LOẠI: vi phạm tinh thần "một biến mỗi lever, có test
  chứng minh off = identical" và tạo số liệu không ai kiểm chứng được.
- (B) đánh dấu "bị chặn — chờ đặc tả" (PA-5), dùng quỹ thời gian cho phần T2 còn lại (Bước 3–4).

**Quyết định: (B).** Hoàn tác: không có code được viết thừa.

## 04:0x — Ngã rẽ: commit gì khi cây làm việc dirty vì phiên khác

Bối cảnh: `git status` trên `auto/overnight` vẫn có `src/generator.py`, `src/pipeline.py`,
`src/query_normalizer.py`, `src/router.py`, `tests/test_pipeline.py`, `tests/test_subquery.py`,
`ROADMAP.md` sửa dở (công việc r6/r7 của phiên khác) + blob lớn `.ocr_cache_vie/`, `chroma_db_vie/`.

**Quyết định: chỉ `git add` đường dẫn artifact của em** (docs/*, tools/diag/*,
data/loop/diag/corpus_diagnostics/*), **KHÔNG commit** file dirty của phiên khác, **KHÔNG commit**
blob `.ocr_cache_vie/` và `chroma_db_vie/` (dữ liệu sinh lại được bằng lệnh trong STATE.md, tránh
đẩy 100+ MB lên git). Lưu ý: `data/loop/diag/b_gemini_top6/rows.jsonl` + `summary.json` ĐÃ đổi ở
phiên này (6 dòng hợp lệ + 34 dòng lỗi) — commit riêng hai tệp đó vì là bằng chứng số liệu của T1.
Hoàn tác: `git reset` các path tương ứng, không đụng file khác.

## 01:2x — Ngã rẽ: (b) có 2 dòng trùng id ⇒ số trong `summary.json` đếm theo dòng (n=9)

Bối cảnh: lượt gọi cuối thành công lúc 00:22 nâng số id hợp lệ lên 7, nhưng `rows.jsonl` có
9 dòng hợp lệ vì `O10235702435549` và `T24199159682252` được hai tiến trình (b) cùng sinh
(hai đáp án khác nhau cho cùng một câu). `summarize()` gốc đếm theo dòng ⇒ báo n=9/PASS 6.

Lựa chọn:
- (A) sửa/xóa dòng trong `rows.jsonl` cho "sạch" → LOẠI: xóa bằng chứng là việc cần duyệt,
  và làm mất dấu vết lỗi vận hành.
- (B) giữ nguyên `rows.jsonl`, thêm `tools/diag/recount_dedup.py` đếm gộp-theo-id ra file mới
  `summary_dedup.json`; chứng minh script không đổi định nghĩa số liệu bằng cách chạy
  `--compare-with-summary` trên (a)/(c) (khớp CHÍNH XÁC, exit 0); ghi cả số cũ lẫn số mới trong T1.md.

**Quyết định: (B).** Kết quả (b): 7 id, PASS_CORRECT 5/7 = 71,4%, refusal 0,1429, fabrication 1/6.
Hoàn tác: xóa `summary_dedup.json` + `recount_dedup.py`.

## 01:3x — Ngã rẽ: "trước" của T2 đo ở đâu để so được với "sau"

Bối cảnh: bản interim so 0,803 (index mới) với 0,178 (văn bản tệp) và 171/78 chunk (phép đo
ngày 23-10, không còn script tái lập). Trộn thước đo ⇒ kết luận "đạt ngưỡng" không đứng.

Lựa chọn: (A) giữ số cũ cho khớp báo cáo → LOẠI (vi phạm quy tắc số liệu);
(B) dựng `tools/diag/measure_index.py` đo CẢ hai index bằng cùng định nghĩa, lưu
`index_before.json` (mới) + `index_after.json` (tái sinh, 4 chỉ số chính trùng khít bản cũ),
sửa T2.md/STATE.md/MORNING_REPORT theo cặp 0,1913 → 0,8029 và 167 → 2 / 79 → 337.

**Quyết định: (B).** Không ghi đè dữ liệu gốc: `index_after.json` chỉ bị viết lại bằng đúng giá trị
nó đã có + các trường mới (median/p10), đã đối chiếu trước khi ghi.
Ghi chú bổ sung: có xóa 1 tệp scratch do chính em tạo vài phút trước
(`tmp/index_after_check.json`, bản sao để đối chiếu) — không phải dữ liệu, không có giá trị bằng
chứng; mọi tệp khác trong `tmp/` vẫn còn nguyên và nằm trong danh sách "dọn chờ duyệt".

---

## 05:2x–06:1x — Phiên T3 (decoupled refusal + evidence selection): quy tắc tự trị mới

**Chỉ thị mới của người dùng (ghi nguyên văn để đời sau đối chiếu):** từ 24-10, CẤM dùng công
cụ hỏi người dùng trong toàn bộ phiên (người dùng ngủ). Gặp ngã rẽ: áp BẢNG MẶC ĐỊNH; nếu
không có trong bảng thì chọn phương án được đánh dấu *Recommended* miễn không vi phạm bất
biến, ngược lại chọn phương án bảo thủ nhất; ghi quyết định ở đây rồi làm tiếp.

Bảng mặc định đã nhận (áp dụng cho mọi bước còn lại của phiên):
tên round = số lớn nhất đang có + 1 (r8, r9), không tái dùng/không xóa round cũ; sửa trọng
tài/`gate.py`/`text_utils.py` ⇒ KHÔNG sửa, ghi diff vào `docs/PENDING_APPROVAL.md` rồi làm
việc khác; Gemini tối đa 14 lượt/ngày, n=30 theo đăng ký, hết quota thì bỏ; OCR chỉ nhận tệp
đạt cổng tự động; thư mục đã tồn tại ⇒ dùng tên mới; test đỏ ⇒ hoàn tác thay đổi của nhiệm vụ
đó và chuyển sang nhiệm vụ độc lập; không xóa file, chỉ liệt kê; không chắc thiết kế ⇒ chọn
phương án đổi ít code nhất, cờ env mặc định TẮT.

## 05:2x — Đổi tên round T3: r6/r7 → r8/r9 (theo bảng mặc định)

Bối cảnh: đặc tả T3 ban đầu ghi "r6 (chỉ decoupled), r7 (decoupled + evidence selection)"
nhưng r6/r7 đã ĐÓNG (lever guard chuẩn hóa và bonus 12) và `run_round.py` NỐI vào
`data/loop/rounds/<round>/full.jsonl` — tái dùng tên sẽ trộn lẫn số liệu cũ và mới trong
cùng một file.

**Quyết định: r8 = decoupled refusal, r9 = decoupled + evidence selection**, đã sửa mọi chỗ
ghi r6/r7 trong `data/loop/README.md` (mục T3) và đăng ký lệnh gate tương ứng (r8 vs r5,
r9 vs r8, kèm r9 vs r5 để đọc tổng biến). Không sửa lại round đã đóng.

## 05:4x — Ba ngã rẽ "không sở thích" → chọn Recommended

1. **Index nào cho r8/r9?** Người dùng trả lời "không có sở thích". Recommended = giữ
   `chroma_db/` đang được mọi round r0–r7 dùng (kích hoạt `chroma_db_vie` là PA-1, chưa
   duyệt). **Quyết định: chạy r8/r9 trên `chroma_db/` cũ**; corpus có dấu là biến số thứ hai,
   không được trộn vào round đang đo đòn bẩy sinh.
2. **"Thực thể vàng" hiểu thế nào cho luật 2 và xếp hạng bằng chứng?** `required_entities`/
   `primary_entity` của testset được sinh từ ĐÁP ÁN ⇒ dùng ở runtime là rò đáp án (bất biến #6).
   **Quyết định: chỉ dùng thực thể phía CÂU HỎI** (`extract_entities(normalized_query)`) + tên
   nguồn router gọi; đã ghi thành quy tắc chống rò trong README.
3. **Reranker cho đòn bẩy 3?** `bge-reranker-base` chưa có trong cache HF (chỉ bge-m3 và
   Qwen2.5-0.5B). **Quyết định: giữ `EVIDENCE_RERANKER` mặc định theo đăng ký, nhưng probe
   trước bằng `HF_HUB_OFFLINE=1` để KHÔNG tải ngầm hàng GB giữa round; nếu không tải được thì
   lùi về bi-encoder bge-m3 (dùng lại hàm nhúng của pipeline, không nhân đôi RAM trên máy 4GB)
   và manifest phải ghi `evidence_reranker.kind` thực tế** — đúng điều README đã đăng ký.

## 06:0x — Ngã rẽ thiết kế: cửa sổ nào cho luật 1–3 khi r9 bật thêm chọn câu?

Lựa chọn: (A) luật 1–3 đo trên cửa sổ đã cắt câu → r9 vừa đổi đầu vào model vừa đổi luôn
phán quyết từ chối, thành HAI biến; (B) luật 1–3 đo trên chunk gốc, chọn câu chạy SAU phán
quyết và TRƯỚC khi sinh → r8 và r9 chỉ khác nhau đúng "model được đọc gì".

**Quyết định: (B)** (ít code hơn và giữ được nghĩa so sánh của hai round); đã ghi thành đoạn
"Thứ tự trong luồng (chốt trước khi chạy)" trong `data/loop/README.md` mục T3.

## 06:0x — Ngã rẽ: `extract_entities` trên câu hỏi rỗng làm đòn bẩy 3 vĩnh viễn câm

Đo nhanh: với câu hỏi "Sinh viên học lại tối đa bao nhiêu lần mỗi học phần?",
`query_entities()` trả `[]` và `refusal_policy.content_tokens()` chỉ còn MỘT token ('phan')
⇒ luật "chọn câu chứa thực thể" không bao giờ khớp, `select_evidence` luôn đi nhánh "giữ
nguyên window" = lever không tồn tại.

Lựa chọn: (A) nới luật bằng cách đọc `required_entities` của testset → LOẠI (rò đáp án);
(B) thêm bậc "câu chia sẻ ≥ `EV_MIN_KEYWORD_HITS` (2) TỪ KHÓA phía câu hỏi" với danh sách hư
từ riêng của module, đăng ký env + ghi lý do vào README TRƯỚC khi chạy round nào, và giữ nguyên
toàn bộ ngưỡng từ chối đã duyệt.

**Quyết định: (B).** Ngưỡng `DEC_*` của năm luật từ chối KHÔNG đổi một chữ.

## 05:54–06:56 — Chạy r8 rồi r9 theo đúng đăng ký trước (0 lượt Gemini)

Ngã rẽ: có chạy hai round ngay trong phiên tự trị hay chờ duyệt. Theo đề bài T3 ("làm lần lượt,
mỗi lần một biến, thành 2 round") + bảng mặc định (id round = số lớn nhất + 1; không tái dùng;
thư mục mới không ghi đè), **quyết định chạy**. r8 = cấu hình r5 từng ký tự +
`ENABLE_DECOUPLED_REFUSAL=1`, cache lạnh `tmp/loop_gen_cache_r8`; r9 = r8 +
`ENABLE_EVIDENCE_SELECTION=1`, cache lạnh `tmp/loop_gen_cache_r9`. Cả hai 100/100 item, exit 0,
**0 lượt Gemini** (chỉ Ollama cục bộ), thư mục `data/loop/rounds/r8`/`r9` là thư mục MỚI —
không đụng r0–r7 đã đóng. Log: `tmp/r8_run.log`, `tmp/r9_run.log`.

## 06:56–07:03 — Số ra ÂM: giữ điều khoản đã ký, không cứu số

`PASS_CORRECT` 19/100 ở cả r8 và r9 (< 25), ba cổng đều KHÔNG ĐẠT. Lựa chọn:
(A) hạ `DEC_MIN_RRF_NORM` hoặc đổi `EV_MAX_SENTENCES` rồi chạy lại cho đẹp số → **LOẠI**, vi phạm
điều khoản "ngưỡng đăng ký trước, không chỉnh theo kết quả" và quy tắc "không thêm lever thứ ba";
(B) ghi kết quả âm kèm phân tích cơ chế, giữ hai cờ mặc định TẮT.
**Quyết định: (B)** — `docs/reports/T3.md`, ROADMAP P5.18/P5.19, `data/loop/README.md` (khối
"r8 + r9" trong mục Số đo đã có), `docs/STATE.md`.

## 06:56–07:03 — Hai ý tưởng tiếp theo CHỈ ghi thành đề xuất, chưa viết code

PA-9 (tầng luật ngoài phủ trên prompt cũ, cần round r10) và PA-10 (probe 0 lượt sinh cho tín hiệu
"căn cứ có trả lời được câu hỏi không") đã vào `docs/PENDING_APPROVAL.md`. Không tự code, không tự
mở round — đây là ngã rẽ cần người, và bảng mặc định quy ước chọn phương án bảo thủ nhất.

## 06:56–07:03 — Một ký tự CJK lạc trong ô MÔ TẢ của README đã đăng ký trước

`data/loop/README.md` dòng `DEC_MAX_UNSUPPORTED` có chữ "đồng口径" (ký tự CJK lẫn vào). Lựa chọn:
(A) để nguyên vì "đừng sửa tệp đăng ký trước"; (B) sửa thành "cùng chuẩn" và ghi rõ trong chính
README rằng đây là sửa chính tả, KHÔNG đổi ngưỡng và KHÔNG đổi ý nghĩa luật.
**Quyết định: (B)** — ô ngưỡng (`1`) và các `DEC_*` khác giữ nguyên từng ký tự; ghi chú nội tuyến
ngay dưới dòng sửa để người sau không đọc nhầm thành chỉnh sửa sau khi có số.

## 06:56–07:03 — p95 latency: hai cách lấy phân vị cho hai số khác nhau

`round_summary_full.json` (dùng `run_round._percentile`, phần tử thứ `ceil(0,95·n)−1`) ghi
r8 19,73 / r9 33,20; phép tính lại chung cho cả ba round bằng `tmp/probe_t3_table.py`
(phần tử thứ `int(0,95·n)`) ghi 19,93 / 33,27 và là số duy nhất có được cho r5 (r5 chạy trước khi
chìa khóa `p95_latency` tồn tại). **Quyết định:** bảng trong `docs/reports/T3.md` dùng MỘT cách tính
cho ba cột và ghi chú rõ con số của manifest, để không ai đọc chênh 0,2 s thành chênh dữ liệu.

## 06:56–07:03 — Chạy pytest SAU khi round kết thúc, không chạy song song

`pytest tests -q` tốn CPU trong lúc Ollama sinh câu trả lời; độ trễ là chỉ số đã đăng ký đo
(p95/median). **Quyết định:** xếp pytest sau khi r9 exit 0 → **610 passed** (`tmp/pytest_t3_final.txt`).

## 07:0x — Phạm vi commit của T3: chỉ tệp tài liệu thuần của T3

`git diff --stat` cho thấy `ROADMAP.md` (+783), `src/generator.py` (+310), `src/pipeline.py` (+201),
`tests/test_pipeline.py` (+96) **đang chứa cả công việc dở của phiên khác** lẫn chữ của T3
(P5.18/P5.19 nằm trong tệp ROADMAP trộn lẫn). Bảng mặc định không cho phép ghi đè/commit hộ, và
một commit "bundle" sẽ khiến người sau không revert riêng T3 được.
**Quyết định:** commit `fc80222` chỉ gồm `docs/reports/T3.md`, `docs/STATE.md`,
`docs/PENDING_APPROVAL.md`, `docs/AUTONOMY_LOG.md`; ROADMAP + src + tests **để nguyên trên đĩa**
và ghi thẳng vào thông điệp commit rằng chúng còn dirty vì chứa work của phiên khác. Văn P5.18/P5.19 vẫn đọc được
ở `ROADMAP.md` (chưa vào git) — trùng đúng tình trạng PA-8.

## 07:0x — Đính chính lớp phủ trên báo cáo tự đánh giá 23-10 (không viết lại lịch sử)

`docs/bao_cao/danh_gia_tong_quan_2026-10-23.md` (untracked, của phiên trước) còn ghi
"evidence-selection và reranker chưa có" và đề xuất baseline cổng cho bước 4 là **r6/r7**. Sau T3,
hai ý đó đã bị thực tế sửa. **Quyết định:** THÊM một khối "ĐÍNH CHÍNH 24-10" ngay sau đoạn cũ
(không xoá, không sửa câu gốc), ghi rõ đặc tả T3 chốt baseline là r5 và kết quả r8/r9 KHÔNG ĐẠT;
không commit tệp đó vì nó là deliverable untracked của phiên khác.

## 09:2x — T4: user đánh thức và trả lời ba câu hỏi; bảng mặc định tự trị thôi chi phối

Điều kiện vào việc của T4 ("chỉ làm nếu T1 chỉ ra năng lực model là nút thắt") **chưa được T1 chốt**:
`docs/reports/T1.md` mục 4 ghi rành rành "KHÔNG kết luận được", phép thử phân nhánh (b) mới 7/30 id
vì PerDay chặn đêm 23-10. Đây là ngã rẽ có chi phí thật (download ~2 GB + 1–2 giờ GPU + nguy cơ train
QLoRA trên 4 GB), nên theo đúng ngoặc "hỏi tôi nếu chưa rõ" của đặc tả T4 tôi hỏi. Tiền đề của lệnh
cấm hỏi ("tôi đang ngủ, không ai trả lời") đã hết hiệu lực từ 09:22 24-10.

**Ba quyết định của user (chép nguyên văn ý, không diễn giải thêm):**
1. **Chạy song song**: (b) resume tới đủ `n=30` với GIỮ NGUYÊN `sample_ids.json` (không thêm/bớt/đổi
   id sau khi đã thấy 7 kết quả đầu), 14 lượt/ngày, checkpoint mỗi lượt, lỗi/timeout không tính quota;
   4a chạy offline trên GPU như phép **THĂM DÒ**, round id mới = số lớn nhất + 1, mọi cờ mặc định TẮT.
   **Chưa** kết luận "năng lực model là nút thắt" và **chưa** bắt đầu 4b (SFT) cho tới khi (b) đủ 30 id;
   khi cả hai xong, diễn giải theo bảng quyết định đã đăng ký và ghi rõ "n=30 trên nhóm over-refusal,
   không ngoại suy".
2. **Model 4a = `qwen2.5:3b-instruct` q4** (không phải Qwen3-4B): chỉ đổi model, giữ nguyên prompt /
   ngữ cảnh / temperature / `num_ctx` như baseline 1,5B và ghi `num_ctx` vào manifest. Phải chạy
   `ollama ps` trong lúc chạy để xác nhận model nằm 100% trên GPU; nếu offload CPU thì ghi rõ vào
   báo cáo và **không so latency trực tiếp** với baseline. Qwen3-4B chỉ thành round riêng nếu 3B cải
   thiện nhưng chưa đạt mục tiêu; **không chạy gộp**.
3. **4b = chỉ dựng pipeline + báo cáo chi phí**, không train trong phiên này.

**Hệ quả kỹ thuật tôi phát hiện khi kiểm "một biến" (trước khi sửa gì):** `OLLAMA_MODEL` dẫn năm nơi —
`src/generator.py:1050`, `src/local_slm.py:232`, `src/query_normalizer.py:419`, `src/classifier.py:553`,
`src/retrieval.py:299` — nên dùng nó sẽ đổi đồng thời sinh + chuẩn hóa + phân loại + tách câu.
**Quyết định:** thêm cờ riêng `GENERATOR_OLLAMA_MODEL` (mặc định rỗng = không truyền `ollama_model`,
fallback cũ từng ký tự), chỉ đọc ở `build_pipeline()` của `tools/loop/run_round.py`, kèm test chứng
minh tắt = identical. Đây là tệp không thuộc `REFEREE_FILES` ⇒ chữ ký trọng tài `9f1179ccab74` không đổi.

**Tie-break "round tốt nhất của T3" chốt TRƯỚC khi chạy:** r8 và r9 hòa `PASS_CORRECT` 19 ⇒ chọn r9
theo an toàn im lặng (`PASS_REFUSAL` 14 vs 2; `HALLUCINATED_ON_UNANSWERABLE` 3 vs 12). Gate chính vẫn
là `r10 vs r5` vì đó mới là one-variable. Ghi đầy đủ ở `data/loop/README.md` mục T4.

**Ngân sách khai TRƯỚC khi gọi** (bất biến #8): (b) còn 23 id, hôm nay ≤14 lượt Gemini; 4a = 0 lượt
Gemini, ~100 lượt Ollama.

## 09:3x–10:2x — T4 đang chạy: r10 trên GPU, (b) dừng ở 12/30 vì PerDay, và hai phát hiện phụ

**Tiến độ đo được.** r8/r9 đã đóng; round mới lấy tên kế tiếp **r10** (`data/loop/rounds/r10/`,
cache lạnh `tmp/loop_gen_cache_r10`, `GENERATOR_OLLAMA_MODEL=qwen2.5:3b-instruct`, cấu hình còn lại
đúng như r5 từng ký). Resume T1(b) sáng 24-10 lấy thêm được **3 id** rồi lại gặp PerDay
(`retry_delay 16394 s` ⇒ window reset ~14:00 VN): hiện **12/30 id hợp lệ**
(`data/loop/diag/b_gemini_top6/summary_dedup.json`, gộp theo id). **Không** chạy tiếp đêm nay,
**không** đổi danh sách id, **không** lấy n=12 làm phán quyết — bảng quyết định T1 chỉ được đóng
khi đủ 30.

**Phát hiện 1 — "một biến" hóa ra không mặc định là một biến.** `OLLAMA_MODEL` dẫn năm nơi
(generator, LocalSLM, query_normalizer, classifier fallback, retrieval splitter). Nếu round dùng
nó thì r10 đổi đồng thời bốn tầng. **Quyết định:** cờ riêng `GENERATOR_OLLAMA_MODEL` chỉ đọc ở
`build_pipeline()`, mặc định rỗng, kèm `tests/test_loop_generator_model_flag.py` (11 test) chứng minh
(i) tắt ⇒ `QwenGenerator` nhận `None` ⇒ chuỗi fallback cũ từng ký tự, (ii) `LocalSLM` không nhận gì mới,
(iii) tắt ⇒ cache key không đổi (cache cũ còn giá trị), (iv) bật ⇒ chỉ đổi `model` trong payload.
Manifest nay ghi thêm `generator_status` (slug/temperature/num_ctx/prompt_version/trần ký tự) vì
`gate.compatibility()` chỉ so khóa `generator` ⇒ cổng mù với biến số này.

**Phát hiện 2 — bẫy đo độ dài dòng train.** `PreTrainedTokenizerFast.apply_chat_template(..., tokenize=True)`
trên `models/qwen25_05b_sft_adapter` với `transformers 5.20.2` trả về **2 token** cho một dòng 3.424 ký
tự, trong khi `tokenize=False` rồi encode cho **1.204 token**. Hai script train/eval của repo đã dùng
đúng đường `tokenize=False`, nên số cũ không sai — nhưng nếu ai "đơn giản hóa" phép đo thì mọi dòng
train đều "vừa" `max_length` một cách giả tạo. **Quyết định:** `exact_token_lengths()` trong
`tools/build_sft_from_round.py` dùng đường `tokenize=False` + encode, và có test chốt (`assert
len(apply_chat_template(tokenize=True)) in (0,1,2)`) để bug quay lại là test đỏ.

**Phát hiện 3 — số của 4b (chưa train):** pool qua `triage.build_rows` rồi group-split theo tài liệu
cho `data/training/t4b_r5r6r7`: **16 dòng SFT** từ 3 round (8 document), train 12 / holdout 4, holdout
chỉ **MỘT tài liệu**; bị chặn `blocked_test_leak` 109 (cộng dồn theo round),
`skip_sft_target_not_in_context` 20, `overrefusal_threshold_only` 7, trùng id giữa round 29.
Độ dài dòng train do tokenizer thật đo: **min 1.016 / median 1.439 / max 1.707 token**, tức **12/12 dòng
vượt trần 768** đã chốt cho GPU 4 GB ở lượt 0,5B. Kết luận trung thực: pipeline chạy được nhưng
**nguồn dữ liệu và bộ nhớ** mới là hai thứ chặn 4b, không phải thiếu script. Chưa train gì cả.

**Quyết định deferred:** probe VRAM cho QLoRA 3B **chưa chạy** vì r10 đang chiếm GPU 4 GB (chạy song
song là tự gây OOM cho chính phép đo) — để sau khi r10 exit 0. `bitsandbytes` **không có** trong
`venv_train` (đã kiểm tra bằng importlib.metadata), nên QLoRA 4-bit hôm nay không chạy được dù có
quyết định train; cài thêm thư viện = thay đổi môi trường ⇒ ghi `docs/PENDING_APPROVAL.md` (PA-11),
không tự cài.

## 10:1x–11:0x — T4 đóng vòng (r10 xong 100/100) và T5a vào nền (r11 đang chạy)

**Quyết định đã làm (không cần hỏi thêm, vì nằm trong đặc tả T4/T5 và điều khoản đã ký):**

1. **Đọc r10 theo đúng quy tắc đăng ký trước, không diễn giải lại khi thấy số.** r10 =
   `PASS_CORRECT` 16/100 < 22 ⇒ "3B không có tín hiệu"; điều khoản "chỉ chạy Qwen3-4B nếu 3B cải
   thiện" **không kích hoạt** vì CI delta [−0,06; +0,10] chứa 0. Không mở round 4B, không đổi model.
2. **Bổ sung thống kê ghép cặp cho bảng model** (`tools/diag/t4_stats.py`, đã viết trước đó) thay vì
   chỉ đưa point estimate, vì hai round sinh chỉ cách nhau 2 item trên 100 — dưới băng nhiễu ±3 của
   T0, nếu không có McNemar + CI thì bảng số vô nghĩa.
3. **Chụp manifest `generator_status` cho r10 là bắt buộc**, vì `gate.compatibility()` không biết gì
   về slug Ollama; không có nó thì cổng sẽ so 3B với 1,5B như hai round cùng cấu hình.
4. **Probe VRAM chỉ chạy sau khi `ollama ps` trả về rỗng** (đúng lời hứa trong log 09:3x): đo đè lên
   model đang resident thì hoặc OOM hoặc số sai. Kết quả đo thật: **hết chỗ từ 1.024 token**,
   `gradient_checkpointing` không giảm ⇒ 13/13 dòng train của T4b (min 1.016 token) không train
   được trên máy này. Hai việc cần duyệt sinh ra từ đây: **PA-11** (cài `bitsandbytes` + tải 3B) và
   **PA-12** (đổi định dạng dòng SFT) — chỉ ghi đề xuất, **không tự cài, không tự tải, không train**.
5. **Bộ dữ liệu T4b mới đặt tên `data/training/t4b_r5r8r9r10/`** (không ghi đè `t4b_r5`, `t4b_r5r6r7`),
   và đếm token bằng tokenizer thật qua đường `apply_chat_template(tokenize=False)` + encode.

**Phát hiện & đính chính (ghi cả bản cũ):**

- `data/loop/README.md` mục T5 từng ghi "r11 ~5 phút CPU (r2 median 0,28 s)" và "retrieval-only không
  đụng GPU". **Cả hai sai** — đo lại 24-10: median `latency_seconds` của r2 là **2,76 s/item**
  (p95 8,59) và `src/classifier.py:581` gọi Ollama `qwen2.5:1.5b-instruct` cho **mỗi** câu hỏi khi
  `ENABLE_CLASSIFIER=1` (811/811 dòng r2 có `labels.raw_response` khác rỗng). Đã đính chính bằng khối
  "Sửa hai câu trên" ngay dưới đoạn gốc, **không** sửa ngưỡng, không sửa thiết kế. Bài học vận hành
  rút ra: **không bấm probe/model khác trong lúc round truy xuất chạy** — classifier timeout 20 s sẽ
  rơi về `topic=None` và hỏng cả round.
- `pytest tests -q` bằng python hệ thống cho **3 lỗi collection** (`streamlit`, `pypdfium2` thiếu);
  đó là **sai môi trường, không phải đỏ test**. Chạy lại bằng `venv/Scripts/python.exe`: **677 passed**.
  Đã ghi vào mục LỆNH TÁI LẬP của `docs/STATE.md` để lần sau không mất thì giờ đoán.
- Thử chụp lại `ollama ps` cho 3B thành tệp (10:3x) **không thành công**: model đã nhả và ngay khi gọi
  lại thì 1,5B của r11 chiếm GPU. Không làm nhiễu r11 để lấy snapshot; việc này chuyển thành
  "bằng chứng chờ" trong `docs/reports/T4.md` §5.4, và **không** ảnh hưởng quyết định (không offload
  nên so latency hợp lệ, còn residency của 3B đã thấy tận mắt trong lúc r10 chạy).

**T5a đang chạy — tiến trình và kiểm giữa chừng:** r11 (nền retrieval-only, 811 item, bonus 12,
quota 0, mọi cờ T3/T4/T5 TẮT, `--strategy all --limit 811` cho đúng thứ tự item của r2). Ở 182 item
đã ghi: `error` = 0, `raw_response` rỗng = 0, `topic=None` = 10 (bình thường, `topic=None` cũng xảy ra
ở đường production), và **`labels` trùng khít r2 ở 181/182 item** — khác 1 item là dao động của LLM ở
nhiệt độ 0, không phải code drift; điều này khiến cặp `r11 vs r2` vẫn dùng được làm thước đo drift.
Chi phí reranker **chưa đo** (phải đo trên item thật của r11, theo đúng thứ tự đã đăng ký), nên
chưa bấm r12.

---

## 24-10 (chiều) — T6: dựng khung kiểm chứng để mọi kết luận đứng trước hội đồng

Lồng ghép trong lúc `r11` (811 item) vẫn chạy nền; **T6 không bấm thêm model/GPU** — chỉ đọc
verdict có trên đĩa và chạy bootstrap/schema.

**Quyết định đã tự chốt (trong phạm vi cho phép):**
- T6a: coi `gate.py` là vùng cấm theo bất biến #5 ⇒ viết luật refusal tương đối ở **module tạm
  không import gate** + test 8 case + diff đầy đủ ở **PA-13**; **không sửa gate.py**. Chọn cách
  "warning không nằm trong `checks`" để cảnh báo tuyệt đối 0,35 **không** kéo `passed` xuống
  (thay vì đánh dấu ok=True trong checks — vừa in vừa vô hiệu hoá `all(checks)` một cách khó đọc).
- T6b: xếp `FAIL_RETRIEVAL` vào lớp "sai" vì phía người học, đáp án thiếu căn cứ vẫn không dùng
  được; **ẩn cả verdict lẫn trường vàng** để nhãn tay là phán quyết ĐỘC LẬP, không bị neo.
- T6c: dùng stub pipeline trong test (nạp Ollama/Chroma trong unit test là không ổn) và `--dry-run`
  bắt đếm lượt model trước (bất biến #8). Ghi `extra_haystack`=tên nguồn khi chấm grounding để
  khỏi gọi số trong tên file là "bịa" (đúng like pipeline sản xuất đã làm).
- T6d: **không tự đổi điểm thành phần.** Số học tổng đã khớp 7,17→7,2; con số 7,1 user nhớ ứng với
  bộ điểm CŨ. Đây là phán chấm điểm ⇒ đưa vào mục "cần user chốt", không âm thầm sửa.

**Không làm (đúng cổng duyệt):** không áp diff vào `gate.py`; không chạy `referee_agreement` ra số
(thiếu nhãn tay, `n_filled=0`); không chấm câu hỏi thật (0 câu được điền); không chạy `r12`.

**Kiểm:** `pytest tests -q` = **691 passed** (thêm 8 gate proposal + 6 eval framework). Điểm ước
lượng `metric_ci.py` khớp `gate.metrics` trên mọi chỉ số dùng chung (`match_gate=True`), nên CI không
dựng nên thang đo thứ hai. Không sửa `src/` sản xuất; không ghi đè round đã đóng (mọi output T6 vào
`data/loop/diag/`, `tools/eval/`, `docs/`).

**Bằng chứng chờ (nợ user):** (1) nhãn 60 mẫu 6b; (2) duyệt PA-13 để áp cổng tương đối; (3) 30–50
câu hỏi thật cho 6c; (4) chốt có muốn đầu ra ghi 7,1 (=dùng điểm cũ) hay giữ 7,2.

---

## 24-10 (ca ngày) — Kiểm thử T1 (the task user giao) + quét trạng tháiLoop Guardian

**Việc user giao (đã xong):** unit test cho `tools/diag/ablation_generation.py` bằng STUB
generator — KHÔNG gọi model thật. `tests/test_ablation_generation.py` **24 test / 7 ca đề bài**,
xanh; toàn suite **736 passed** (baseline 712 + 24). Báo cáo: `docs/reports/test_T1.md`.
Hai seam thêm vào script (chỉ phục vụ đo, không phải lever `src/`, không đổi hành vi sản xuất):
(1) guard `--force` (mặc định từ chối đè thư mục đã có `rows.jsonl`); (2) `interpret_decision(...)`
thuần mã hóa bảng quyết định đã đăng ký, ngưỡng **tham số hóa** (a=0,15 / b=0,30 / band=0,02) vì
README chỉ đăng ký chiều, không đăng ký con số.

**Mutation check (`tmp/mutation_check_t1.py`, patch bytes trên ĐÚNG ablation script, không đụng
`verify.py`; 3/3 BẮT ĐƯỢC, 3/3 hoàn nguyên byte-identical sha256 `9c7ffa1734a5`):**
- M-T1-1 lấy nhầm chunk (`chunks.get(gold_id)`→`+1`) → đỏ `test_a_chi_goi_dung_chunk_vang` + 3 `test_c_*`.
- M-T1-2 bỏ ràng buộc cùng item id (`if unknown:`→`if False:`) → đỏ `test_id_ngoai_r5_bi_tu_choi`.
- M-T1-3 bỏ force guard → đỏ `test_thu_muc_da_co_rows_tu_choi`.
Trọng tài giữ nguyên: `git diff` rỗng trên `verify.py`/`answer_guard.py`/`text_utils.py`, chữ ký `9f1179ccab74`.

**Quét trạng thái (Loop Guardian):**
- `r11` (T5a retrieval-only, 811 item) **ĐÃ XONG** ~11:02, không cần resume (log kết bằng summary
  JSON: 182 FAIL_RETRIEVAL, 629 PENDING_GENERATION). Bước kế tiếp ĐỂ NGAY: gate/attribution r11 vs
  r5 rồi mới cân nhắc `r12` — **không tự mở r12** (nằm sau quyết định, thuộc phạm vi user).
- T1(b) Gemini: recount_dedup → **12/30 id** hợp lệ (9 PASS_CORRECT, refusal 0,083, 2 FAIL_FABRICATED,
  1 OVERREFUSAL). Tín hiệu tiếp tục **nghiêng T4 (năng lực model)** nhưng **<30 ⇒ chưa chốt nhánh**.
  2 FAIL_FABRICATED = **cảnh báo ≥2/30** cho nhánh "nghi trọng tài" (`Theo Bản` kiểu `LOOKS_LIKE_FORMATTING`)
  → ghi vào **PA-2 (chờ duyệt)**, KHÔNG tự sửa `answer_guard.py`.
- **KHÔNG gọi Gemini tiếp ca này**: đồng hồ (~11:00) **trước** quota window ~14:00 VN; để dành lượt
  cho khi window mở (≤14/ngày).

**Không làm:** không sửa gate/trọng tài/`src/`; không mở `r12`; không đổi ngưỡng; không ghi đè round đã
đóng (mọi output test vào `tests/`, `tmp/`, `docs/reports/`).
