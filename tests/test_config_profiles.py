"""REVIEW §14 — profile cấu hình không được âm thầm bật cờ thí nghiệm.

Bốn tệp trong `config/` là **tài liệu + mẫu**; mã không đọc chúng. Vì vậy test ở đây
ghim hai thứ mà mắt người hay bỏ sót:

* **Tập khoá**: mọi khoá xuất hiện dưới dạng DÒNG HOẠT ĐỘNG phải là khoá đã có chủ
  (`.env.example`, `TRACKED_ENV`, hoặc danh sách `LEVERS`). Không phát minh biến mới.
* **Bất biến profile**: `runtime` khai báo ĐỦ mọi lever và tất cả đều TẮT; `experiment`
  không có dòng lever nào đang bật (phải bỏ `#` mới bật).

Không đọc/ghi `.env`; chỉ đọc tệp mẫu trong `config/`.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

env_flag_audit = importlib.import_module("tools.diag.env_flag_audit")
from src.core.config import TRACKED_ENV  # noqa: E402

CONFIG = ROOT / "config"
PROFILES = {
    "runtime": CONFIG / "runtime.env.example",
    "offline": CONFIG / "offline.env.example",
    "evaluation": CONFIG / "evaluation.env.example",
    "experiment": CONFIG / "experiment.env.example",
}
LEVERS = {row["name"] for row in env_flag_audit.LEVERS if row["group"] == "lever"}


def active_pairs(path: Path) -> dict[str, str]:
    """Các dòng `KEY=value` đang hoạt động (bỏ chú thích và phần comment cuối dòng)."""
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key.replace("_", "").isalnum():
            continue
        out[key] = value.split("#")[0].strip().strip("\"'")
    return out


def known_keys() -> set[str]:
    return set(env_flag_audit.dotenv_example()) | set(TRACKED_ENV) | LEVERS


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_profile_ton_tai_va_co_ten_trong_readme(name):
    path = PROFILES[name]
    assert path.is_file(), f"thiếu profile {path}"
    readme = (CONFIG / "README.md").read_text(encoding="utf-8")
    assert path.name in readme, f"config/README.md chưa nhắc {path.name}"


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_moi_khoa_deu_da_co_chu(name):
    la = set(active_pairs(PROFILES[name]))
    khong_ro = sorted(la - known_keys())
    assert khong_ro == [], (
        f"{PROFILES[name].name}: khoá chưa có chủ {khong_ro} — thêm vào .env.example/"
        f"TRACKED_ENV trước, hoặc bỏ khỏi profile")


def test_runtime_ghim_du_moi_lever_va_tat():
    """Profile runtime phải khai báo TẤT CẢ lever = TẮT (không chỉ vắng mặt)."""
    pairs = active_pairs(PROFILES["runtime"])
    missing = sorted(LEVERS - set(pairs))
    assert missing == [], f"runtime thiếu khai báo lever: {missing}"
    bat = {k: v for k, v in pairs.items()
           if k in LEVERS and v.strip().lower() not in env_flag_audit.OFF_LITERALS}
    assert bat == {}, f"profile runtime đang bật lever: {bat}"


@pytest.mark.parametrize("name", ["offline", "evaluation"])
def test_profile_khac_cung_khong_bat_lever(name):
    pairs = active_pairs(PROFILES[name])
    bat = {k: v for k, v in pairs.items()
           if k in LEVERS and v.strip().lower() not in env_flag_audit.OFF_LITERALS}
    assert bat == {}, f"profile {name} đang bật lever: {bat}"


def test_experiment_khong_bat_san_lever_nao():
    """Muốn bật phải bỏ `#` — chép nguyên tệp không được đổi hành vi."""
    pairs = active_pairs(PROFILES["experiment"])
    assert not (set(pairs) & LEVERS), (
        f"experiment có lever đang hoạt động: {sorted(set(pairs) & LEVERS)}")


def test_runtime_va_offline_khac_nhau_dung_o_generator():
    runtime = active_pairs(PROFILES["runtime"])
    offline = active_pairs(PROFILES["offline"])
    assert runtime["USE_QWEN_GENERATOR"] == "0"
    assert offline["USE_QWEN_GENERATOR"] == "1"
    assert "GEMINI_API_KEY" not in offline, "profile offline không được khai báo Gemini"


def test_repo_layout_ghi_du_vung_artifact():
    text = (ROOT / "docs" / "REPO_LAYOUT.md").read_text(encoding="utf-8")
    for token in ("chroma_db/", "indexes/experimental/", "outputs/", "logs/", "tmp/",
                  "data/loop/rounds/", "models/", ".cache/ocr/", ".generation_cache/"):
        assert token in text, f"docs/REPO_LAYOUT.md thiếu vòng đời cho {token}"
    assert "CHƯA THỰC HIỆN" in text  # §9/§10 có ghi rõ trạng thái
    assert (ROOT / "indexes" / "README.md").is_file()
