# -*- coding: utf-8 -*-
"""Manifest artifact — vùng log tự sinh vô hạn phải nằm NGOÀI phạm vi ghim.

Vì sao có test này: `logs/feedback/` (bản ghi phản hồi + hàng đợi chờ duyệt) và
`logs/learning/` lớn thêm ở mỗi thao tác người dùng. Nếu manifest ghim chúng thì mỗi lần lưu
phản hồi là một lần `--check` đỏ, và manifest phình mãi không có mốc dừng. Test khẳng định:

1. Bản ghi trong hai vùng vô hạn KHÔNG vào manifest.
2. Log có hạn khác dưới `logs/` VẪN được ghim (không nới scope quá tay).
3. So khớp theo ranh giới thư mục — `logs/feedback_old/` không bị loại oan.
4. Thêm bản ghi mới vào hai vùng đó KHÔNG làm `--check` báo lệch, nhưng sửa một log có hạn
   thì vẫn bị bắt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.diag import artifact_manifest as am


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cây giả lập tối thiểu: chỉ scope `logs` có nội dung."""
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(am, "ROOT", root)
    _write(root / "logs" / "README.md", "readme")
    _write(root / "logs" / "benchmark" / "params.json", "{}")
    _write(root / "logs" / "feedback" / "user_feedback.json", "[]")
    _write(root / "logs" / "feedback" / "queue" / "20261101T000000Z_abcd1234.json", "{}")
    _write(root / "logs" / "learning" / "learning_log.csv", "a,b\n")
    # Hai tệp "gần giống" để bắt lỗi so khớp tiền tố không có ranh giới thư mục.
    _write(root / "logs" / "learning_extra.txt", "phải được ghim")
    _write(root / "logs" / "feedback_old" / "x.txt", "phải được ghim")
    return root


def _paths(manifest: dict) -> set[str]:
    return {f["path"] for scope in manifest["scopes"] for f in scope["files"]}


def _manifest_file(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(am.build_manifest(), ensure_ascii=False), encoding="utf-8")
    return path


def test_hai_vung_vo_han_khong_vao_manifest(fake_root):
    paths = _paths(am.build_manifest())
    assert "logs/feedback/user_feedback.json" not in paths
    assert "logs/feedback/queue/20261101T000000Z_abcd1234.json" not in paths
    assert "logs/learning/learning_log.csv" not in paths


def test_log_co_han_van_duoc_ghim(fake_root):
    paths = _paths(am.build_manifest())
    assert "logs/README.md" in paths
    assert "logs/benchmark/params.json" in paths
    # Ranh giới thư mục: chỉ `logs/feedback/` và `logs/learning/` bị loại.
    assert "logs/learning_extra.txt" in paths
    assert "logs/feedback_old/x.txt" in paths


def test_them_ban_ghi_van_khong_lam_check_lech(fake_root, tmp_path):
    manifest = _manifest_file(tmp_path)
    _write(fake_root / "logs" / "feedback" / "queue" / "moi.json", '{"id": 2}')
    _write(fake_root / "logs" / "feedback" / "user_feedback.json", '[{"id": 1}]')
    _write(fake_root / "logs" / "learning" / "learning_log.csv", "a,b\nc,d\n")
    assert am.check(manifest) == 0


def test_sua_log_co_han_van_bi_bat(fake_root, tmp_path, capsys):
    manifest = _manifest_file(tmp_path)
    _write(fake_root / "logs" / "benchmark" / "params.json", '{"doi": true}')
    assert am.check(manifest) == 1
    assert "ĐỔI" in capsys.readouterr().out
