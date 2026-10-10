"""Cho phép pytest import src.* từ gốc dự án mà không cần cài package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
