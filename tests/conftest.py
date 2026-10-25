"""Cho phép pytest import src.* từ gốc dự án mà không cần cài package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_configure(config):
    """Khai báo marker `slow` (T4 mục 8–9): test cần GPU/Ollama thật, mặc định KHÔNG chạy.

    Chạy bằng `T4_RUN_SLOW=1 pytest tests/test_t4_gpu_slow.py -q`. Không dùng
    `-m "not slow"` mặc định vì repo chưa có pytest.ini; cách env-gate giữ bộ test
    tất định mà không phải thêm cấu hình toàn cục.
    """
    config.addinivalue_line(
        "markers", "slow: cần GPU/Ollama thật (T4 mục 8–9); bật bằng T4_RUN_SLOW=1"
    )

