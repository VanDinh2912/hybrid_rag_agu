# dev/ — tài liệu và quy tắc phát triển (không phải mã chạy)

- `dev/.maestro/playbooks/` — quy tắc cộng tác đa-agent (`base_prompt.md` + 4 group).
  Trước 26-10 nằm ở `.maestro/`.
- `dev/prompts/` — playbook nhiệm vụ P0→P5, `PROGRESS.md`, template prompt.
  Trước 26-10 nằm ở `prompts/`.

Đường dẫn cũ trong tài liệu lịch sử (đặc biệt `dev/prompts/archive/**`) được giữ nguyên văn —
đó là bản ghi nhiệm vụ đã chạy, không phải hướng dẫn hiện hành. Khi dẫn lại, dùng đường dẫn mới
trong `README.md` / `docs/planning/ROADMAP.md`.

`SYSTEM_ARCHITECTURE.txt`/`.docx` không còn trong kho: sinh lại bằng
`python scripts/export_architecture.py` (ghi vào `docs/architecture/`) khi cần nộp kèm. Hai script
`scripts/learn.py` và `scripts/benchmark_chunking.py` được chuyển xuống `scripts/` trong đợt tái cấu
trúc 28-10 (ánh xạ cũ → mới: `docs/RESTRUCTURE_MAP.md`). Lưu ý PA-43: 74 dòng code-QA trong dữ liệu
train cũ trích theo **đường dẫn gốc thời điểm đó**; dữ liệu đã sinh không đổi, nhưng mọi lượt tái sinh
data-train sau này phải map đường dẫn nếu không muốn lệch bất biến #7.
