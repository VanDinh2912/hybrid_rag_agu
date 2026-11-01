# -*- coding: utf-8 -*-
"""`LEARN_AUTO_APPLY` — cờ học tự động của Tab 3, mặc định TẮT.

Vì sao có test này: bật cờ là GUI được phép sửa ba tệp đang được round paired theo dõi
(`benchmark_questions.json`, `normalization_pairs.json`, `ghi_chu_hoc_them.txt`) và rebuild
`chroma_db/` ngay giữa phiên. Mặc định phải là TẮT, và chỉ đúng tập giá trị `on` mới bật —
giá trị lạ không được vô tình bật đường ghi.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core import config

ROOT = Path(__file__).resolve().parents[1]


def test_mac_dinh_tat(monkeypatch):
    monkeypatch.delenv("LEARN_AUTO_APPLY", raising=False)
    assert config.learn_auto_apply_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", " on "])
def test_chi_bat_voi_tap_gia_tri_on(monkeypatch, value):
    monkeypatch.setenv("LEARN_AUTO_APPLY", value)
    assert config.learn_auto_apply_enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "bat", "2"])
def test_gia_tri_la_van_tat(monkeypatch, value):
    monkeypatch.setenv("LEARN_AUTO_APPLY", value)
    assert config.learn_auto_apply_enabled() is False


def test_hai_tep_mau_khai_bao_tat():
    """Người clone phải thấy cờ trong tệp mẫu, và giá trị khai báo phải là TẮT."""
    for rel in (".env.example", "config/runtime.env.example"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        dong = [ln.strip() for ln in text.splitlines()
                if ln.strip().startswith("LEARN_AUTO_APPLY=")]
        assert dong, f"{rel} chưa khai báo LEARN_AUTO_APPLY"
        assert dong == ["LEARN_AUTO_APPLY=0"], f"{rel}: {dong}"
