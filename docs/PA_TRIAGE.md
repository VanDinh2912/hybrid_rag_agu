# Phân loại PA-1…PA-48 (27-10; PA-48 thêm 28-10)

Mục đích: một bảng để quyết định việc duyệt tiếp theo, **không** áp PA nào. Ba nhóm:

- **(a) ảnh hưởng số đo/benchmark** — đụng mã đường chạy, dữ liệu, index, trọng tài hoặc cổng; mọi
  thay đổi phải kèm round mới và đủ 4 cổng.
- **(b) môi trường/tài liệu** — đường dẫn, git, manifest, cách chạy, cách phát ngôn; không đổi số đo.
- **(c) refactor** — dời/tách mã, giữ nguyên hành vi; rủi ro là bất biến #7 và PA-26.

Cột "khuyến nghị": **duyệt** = nên làm, thường rẻ và không đổi số; **đóng** = không làm nữa (đã áp,
đã bị số đo bác, hoặc khuyến nghị giữ nguyên); **hoãn** = cần điều kiện khác (duyệt ngưỡng, quota,
PA-26, re-anchor) trước khi làm.

Đếm: (a) 26 · (b) 17 · (c) 4. Đã đóng 11: PA-2, 5, 6, 9, 10, 19, 20, 25, 34, 45, 47.

| PA | Việc | Nhóm | Khuyến nghị | Lý do ngắn |
|---|---|---|---|---|
| PA-1 | Kích hoạt `indexes/experimental/chroma_db_vie` (path cũ `chroma_db_vie/`, đổi 28-10) + chấm lại r0–r5 | a | **hoãn** | phải re-anchor trước (PA-17/PA-21), nếu không mất 48,81% neo |
| PA-2 | Nới luật "Theo Bản" trong `answer_guard` | a | **đóng** | đã áp ở trọng tài v2 `2911c69f740d` |
| PA-3 | Sửa cổng #23 refusal tương đối + veto family | a | **hoãn** | là dụng cụ đo; phải đăng ký round mới trước khi sửa |
| PA-4 | Resume (b) đủ 30 id Gemini | a | **hoãn** | chỉ chạy khi có quota; hiện 25/30 nên chưa kết luận |
| PA-5 | Đặc tả T3/T5/TT0–TT3 không tồn tại | b | **đóng** | không còn dùng; T3/T5 đã chốt theo đặc tả khác |
| PA-6 | Giữ `easyocr` làm dependency? | b | **đóng** | chỉ dùng chẩn đoán một lần; pipeline không import |
| PA-7 | Loại 2 PDF bảng khỏi corpus | a | **hoãn** | đụng corpus/index; phải chấm lại toàn bộ round |
| PA-8 | Bằng chứng loop P5 chưa vào git | b | **duyệt** | commit `tools/loop` + testset + verdicts nhỏ; không commit rounds nặng |
| PA-9 | Tầng luật ngoài phủ lên prompt cũ | a | **đóng** | r8 bác: PASS_REFUSAL 17→2, ảo giác ngoài phạm vi 2→12 |
| PA-10 | Tín hiệu "trả lời được" thay hạng truy xuất | a | **đóng** | r9 bác; `grounding_score` ≡ 1,0 nên mù lớp lạc đề |
| PA-11 | QLoRA 4-bit trên model triển khai | a | **hoãn** | cần cài `bitsandbytes` + tải 3B; câu hỏi train thật còn mở |
| PA-12 | Đổi định dạng dòng SFT vừa 1.000 token | a | **hoãn** | PA-39 là đường thay thế; cắt căn cứ phá bất biến #7 |
| PA-13 | Cổng refusal tuyệt đối → tương đối | a | **hoãn** | đổi dụng cụ đo; mới có mô-đun test tạm |
| PA-14 | Đường Gemini thiếu nhánh `DECOUPLED` | a | **hoãn** | đụng generator/prompt (PA-26); lever đang TẮT |
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
| PA-26 | HEAD không tái lập cây đã test | b | **duyệt** | commit 35 file nguồn/test trước khi mở round mới |
| PA-27 | Khoá cache tách theo lever TẮT | a | **hoãn** | sửa `cache_policy`; phải giữ byte-identical khi TẮT |
| PA-28 | Bộ sinh SFT giữ dòng thiếu thực thể | a | **hoãn** | đụng dữ liệu train; cần chốt đặc tả T4 |
| PA-29 | 5 script thiếu argparse; `ingest` xoá index | b | **duyệt** | rẻ: thêm dry-run/xác nhận; không đổi số |
| PA-30 | `.env.example` thiếu 13 cờ lever | b | **duyệt** | rẻ, chỉ tài liệu |
| PA-31 | 89 dòng nhân thân chưa mask | b | **duyệt** | tạo bản redacted; không sửa artifact gốc |
| PA-32 | 3 id trùng tên train/val/benchmark | a | **hoãn** | đụng dữ liệu train; cần quyết định tách id |
| PA-33 | `.gitignore` chưa phủ vùng artifact | b | **duyệt** | rẻ; chặn stage 1.980 đường dẫn |
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
| PA-44 | Gom 45 site đọc env còn lại | c | **hoãn** | rủi ro cao; PA-26 chưa đóng, không đổi số |
| PA-45 | Tách 3 tệp đánh giá khỏi `src/` | c | **đóng** | khuyến nghị giữ nguyên (bất biến #7 + import thư viện) |
| PA-46 | Tách `generator.py` + `negative_results` | c | **duyệt (a)** | chỉ tạo `experiments/negative_results/README.md`; (b)–(d) hoãn |
| PA-47 | Manifest ghim byte container Chroma | b | **đóng** | C1 đã cô lập test + sinh lại manifest; index digest hoãn |
| PA-48 | Re-anchor manifest + ghim chốt an toàn cho layout `indexes/`+`.cache/` | b | **duyệt** | `_scope_dirs()` glob `chroma_db*` và `.ocr_cache*` **chỉ ở gốc repo** ⇒ sau Phase 2 `--check` báo THÊM **THIẾU 36** (26 cache + 10 index, 158→122 tệp). Cần: (1) nối `.cache/ocr/*` + `indexes/experimental/*` vào scope rồi sinh lại manifest, đối chiếu 36 hash cũ↔mới khớp byte trước commit; (2) thêm test ghim `PROTECTED_INDEX_DIRS` bản đường dẫn mới (test hiện tại chỉ khai tên cũ). KHÔNG tự sửa glob/manifest khi chờ duyệt — xem `docs/RESTRUCTURE_MAP.md` §5.3 |

**Thứ tự rẻ trước (nếu duyệt một lượt):** PA-41, PA-30, PA-29, PA-33, PA-16, PA-40 — toàn bộ là
môi trường/tài liệu, không đụng số đo. PA-42 cũng rẻ (chỉ `git add` hai tệp byte-nguyên) nhưng xếp (a)
vì đụng chữ ký trọng tài. Nhóm (c) chờ PA-26 đóng; nhóm (a) chờ quyết định ngưỡng và PA-17. Không
mục nào trong bảng này được tự áp.
