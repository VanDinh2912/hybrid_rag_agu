# dev/ — tài liệu và quy tắc phát triển (không phải mã chạy)

- `dev/.maestro/playbooks/` — quy tắc cộng tác đa-agent (`base_prompt.md` + 4 group).
  Trước 26-10 nằm ở `.maestro/`.
- `dev/prompts/` — playbook nhiệm vụ P0→P5, `PROGRESS.md`, template prompt.
  Trước 26-10 nằm ở `prompts/`.

Đường dẫn cũ trong tài liệu lịch sử (đặc biệt `dev/prompts/archive/**`) được giữ nguyên văn —
đó là bản ghi nhiệm vụ đã chạy, không phải hướng dẫn hiện hành. Khi dẫn lại, dùng đường dẫn mới
trong `README.md` / `ROADMAP.md`.

`SYSTEM_ARCHITECTURE.txt`/`.docx` không còn trong kho: sinh lại bằng
`python export_architecture.py` khi cần nộp kèm. Hai script `learn.py` và
`benchmark_chunking.py` **vẫn ở thư mục gốc** — phương án chuyển vào `tools/` bị chặn bởi
bất biến #7 trên dữ liệu train (74 dòng code-QA trích theo đường dẫn gốc), xem PA-43.
