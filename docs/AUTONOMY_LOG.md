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
