# `config/` — profile cấu hình mẫu (REVIEW §14)

Bốn profile, mỗi profile là **một tệp mẫu độc lập** cho một chế độ chạy:

| Tệp | Dùng cho | Điểm khác biệt chính |
|---|---|---|
| `runtime.env.example` | CLI + GUI hằng ngày | Gemini sinh câu trả lời; **mọi lever = 0** |
| `offline.env.example` | Không mạng / hết quota | `USE_QWEN_GENERATOR=1`; không khai báo `GEMINI_*` |
| `evaluation.env.example` | `src/assessment/evaluation.py`, A/B | tách `GEMINI_JUDGE_MODEL`; `USE_QWEN_GENERATOR=0` |
| `experiment.env.example` | Một round thí nghiệm đã đăng ký trước | nền runtime + **mọi lever ở dạng chú thích** |

## Cách dùng

Mã nguồn **không** đọc thư mục này. Entry point nạp duy nhất tệp `.env` ở gốc repo
(`main.py`, `ingest.py`, `ui/app.py`, `ui/demo_streamlit.py`, `src/assessment/evaluation.py`,
`scripts/*.py`). Vì vậy:

1. Tạo `.env` từ danh sách khoá đầy đủ: `copy .env.example .env` (Windows) hoặc
   `cp .env.example .env`.
2. Chép các dòng của profile muốn dùng vào **cuối** `.env`. python-dotenv ghi đè theo
   thứ tự khai báo, nên dòng sau thắng dòng trước; biến môi trường của tiến trình
   (nếu đã đặt) vẫn thắng `.env`.
3. Điền giá trị thật cho `GEMINI_API_KEY`. **Không** commit `.env` (đã nằm trong
   `.gitignore`).

Các tệp trong `config/` là **mẫu để commit** — mọi giá trị nhạy cảm ở đây chỉ là
placeholder (`your_gemini_api_key_here`).

## Bất biến

1. **Profile runtime không bật cờ thí nghiệm nào.** Mười một lever của vòng lặp đo
   được ghi `=0` tường minh; nếu ai đổi một dòng thành `=1`, test
   `tests/test_config_profiles.py` đỏ.
2. **Mọi khoá trong profile phải là khoá đã có chủ** — thuộc `.env.example`,
   `TRACKED_ENV` (`src/core/config.py`) hoặc danh sách `LEVERS`
   (`tools/diag/env_flag_audit.py`). Không tự phát minh biến mới trong profile; test
   cũng ghim điều này để profile không lệch khỏi mã.
3. **Không có cơ chế `ENV_PROFILE` trong mã.** Phương án "một biến `ENV_PROFILE`
   chọn profile" bị loại vì phải thêm một tầng đọc env mới vào các module đang đóng
   băng (generator/pipeline/evaluation) và làm mất tính "một giá trị = một nguồn".
   Chọn tệp rời: rõ ràng, không đổi hành vi, không cần sửa mã.
4. **Cờ mặc định vẫn TẮT trong code**, không phụ thuộc profile nào được dùng
   (`tests/test_final_env_flag_defaults.py`).

## Liên quan

- Vòng đời thư mục chứa kết quả của từng profile: `docs/REPO_LAYOUT.md` §2.
- Đăng ký round trước khi dùng `experiment.env.example`: `data/loop/README.md`.
- Danh sách khoá đầy đủ + chú thích từng biến: `.env.example`.
