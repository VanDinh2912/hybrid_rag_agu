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
