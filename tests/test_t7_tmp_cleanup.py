# -*- coding: utf-8 -*-
"""Test cho `tools/diag/tmp_cleanup.py` (T7 — mục 4 đề bài: dọn dẹp có cổng an toàn).

Bốn bất biến phải giữ, và mỗi cái được test bằng cách "cố tình vi phạm":

1. **Mặc định chỉ liệt kê.** Không có `--yes` thì không một file nào bị xoá, dù mục đó hợp lệ.
2. **Vùng cho phép duy nhất là `<root>/tmp`.** `../outputs`, đường dẫn tuyệt đối, tên có phân cấp,
   tên rỗng — tất cả bị `check_target()` từ chối **kể cả khi** người gọi đã truyền `--yes`.
3. **Mục được trích dẫn trong tài liệu thì không xoá được**, kể cả `--yes`.
4. **Không đi theo symlink/junction ra ngoài repo.**

Toàn bộ test chạy trên **cây giả trong `tmp_path`** — không đụng `tmp/` thật, không sửa dữ liệu,
không gọi model. Riêng nhóm `TestRepoThatNgoai` đọc repo thật ở chế độ chỉ-đọc để chắc rằng dụng cụ
không đề xuất xoá một mục đã được dẫn chứng.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.diag import tmp_cleanup as tc

ROOT = Path(__file__).resolve().parents[1]


def fake_repo(tmp_path: Path, *, cited_docs: bool = False) -> Path:
    """Dựng repo giả: có `tmp/` với vài mục, `outputs/` và `data/loop/rounds/` để thử vượt biên."""
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "loop" / "rounds" / "r9").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tmp" / "scratch.log").write_text("a" * 100, encoding="utf-8")
    (tmp_path / "tmp" / "cache_dir").mkdir(exist_ok=True)
    (tmp_path / "tmp" / "cache_dir" / "one.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "tmp" / "cache_dir" / "two.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "outputs" / "keep.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "data" / "loop" / "rounds" / "r9" / "verdicts_full.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    if cited_docs:
        docs = tmp_path / "docs" / "reports"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "test_T7.md").write_text(
            "Nguồn: `tmp/dan_chung.log` và `tmp/scratch.log`.\n", encoding="utf-8"
        )
        (tmp_path / "tmp" / "dan_chung.log").write_text("x" * 10, encoding="utf-8")
    return tmp_path


class TestMacDinhChiLietKe:
    def test_khong_co_yes_khong_xoa_bat_cu_thuoc_nao(self, tmp_path):
        root = fake_repo(tmp_path)
        names = [r["name"] for r in tc.inventory(root) if r["action"] == "XOÁ-ĐỀ-XUẤT"]
        assert "scratch.log" in names and "cache_dir" in names
        report = tc.delete_targets(root, names, apply=False)
        assert report["deleted"] == []
        assert {w["name"] for w in report["would_delete"]} == set(names)
        assert (root / "tmp" / "scratch.log").exists()
        assert (root / "tmp" / "cache_dir").is_dir()
        assert report["mode"].startswith("DRY-RUN")

    def test_inventory_phan_loai_va_tinh_bytes_khong_ghi_de(self, tmp_path):
        root = fake_repo(tmp_path)
        rows = {r["name"]: r for r in tc.inventory(root)}
        assert rows["scratch.log"]["bytes"] == 100
        assert rows["cache_dir"]["kind"] == "dir"
        assert rows["cache_dir"]["bytes"] == 0 or rows["cache_dir"]["bytes"] > 0  # dir vẫn đếm được
        # inventory không được phép tạo/xoá gì
        assert sorted(p.name for p in (root / "tmp").iterdir()) == ["cache_dir", "scratch.log"]

    def test_cli_main_mac_dinh_la_dry_run(self, tmp_path, capsys):
        root = fake_repo(tmp_path)
        code = tc.main(["--root", str(root)])
        assert code == 0
        out = capsys.readouterr().out
        assert "che-do=LIET KE" in out and "deleted=0" in out
        assert (root / "tmp" / "scratch.log").exists()


class TestXoaThatKhiDuocDuyet:
    def test_co_yes_thi_xoa_dung_muc_trong_tmp(self, tmp_path):
        root = fake_repo(tmp_path)
        report = tc.delete_targets(root, ["scratch.log", "cache_dir"], apply=True)
        assert {d["name"] for d in report["deleted"]} == {"scratch.log", "cache_dir"}
        assert not (root / "tmp" / "scratch.log").exists()
        assert not (root / "tmp" / "cache_dir").exists()
        assert (root / "outputs" / "keep.json").exists()  # không liên quan, vẫn nguyên

    def test_cli_co_yes_xoa_va_in_bao_cao_json(self, tmp_path, capsys):
        root = fake_repo(tmp_path)
        out = root / "tmp" / "report.json"
        assert tc.main(["--root", str(root), "--yes", "--only", "scratch.log", "--json", str(out)]) == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["deletion"]["mode"] == "XOÁ THẬT"
        assert [d["name"] for d in payload["deletion"]["deleted"]] == ["scratch.log"]
        assert (root / "tmp" / "cache_dir").exists()  # mục không được nêu tên vẫn còn


class TestTuChoiDuongDanNgoaiVung:
    @pytest.mark.parametrize(
        "ten",
        [
            "../outputs",
            "../data/loop/rounds/r9",
            "..",
            "../../etc/passwd",
            "nested/deep.txt",
            "back\\slash",
            "",
            ".",
        ],
    )
    def test_check_target_tu_choi_ke_ca_khi_co_yes(self, tmp_path, ten):
        root = fake_repo(tmp_path)
        with pytest.raises(tc.CleanupRefusal):
            tc.check_target(root, ten)

    def test_duong_dan_tuyet_doi_bi_tu_choi(self, tmp_path):
        root = fake_repo(tmp_path)
        with pytest.raises(tc.CleanupRefusal):
            tc.check_target(root, str(root / "outputs" / "keep.json"))

    def test_xoa_bang_ham_truc_tiep_van_khong_cham_duoc_vung_bao_ve(self, tmp_path):
        """`--yes` không phải tấm vé: gọi delete_targets(apply=True) với tên vượt biên vẫn bị chặn."""
        root = fake_repo(tmp_path)
        report = tc.delete_targets(root, ["../outputs", "../data/loop/rounds/r9"], apply=True)
        assert report["deleted"] == []
        assert len(report["blocked"]) == 2
        assert (root / "outputs" / "keep.json").exists()
        assert (root / "data" / "loop" / "rounds" / "r9" / "verdicts_full.jsonl").exists()

    @pytest.mark.parametrize(
        "prefix",
        ["outputs", "data/loop/rounds", "data/loop/diag", "data/training", "models", ".git", "src", "docs"],
    )
    def test_dang_khai_vung_bao_ve_khong_phai_la_duong_dan_de_gian(self, prefix):
        assert prefix in tc.PROTECTED_PREFIXES


class TestDanChungVaSymlink:
    def test_muc_duoc_dan_trong_tai_lieu_khong_xoa_duoc_kem_yes(self, tmp_path):
        root = fake_repo(tmp_path, cited_docs=True)
        cited = tc.cited_names(root)
        assert {"dan_chung.log", "scratch.log"} <= cited  # README/docs nhắc cả hai
        report = tc.delete_targets(root, ["dan_chung.log", "scratch.log"], apply=True)
        assert report["deleted"] == []
        assert {b["name"] for b in report["blocked"]} == {"dan_chung.log", "scratch.log"}
        assert (root / "tmp" / "dan_chung.log").exists()
        assert (root / "tmp" / "scratch.log").exists()

    def test_inventory_danh_dau_giu_vi_duoc_dan(self, tmp_path):
        root = fake_repo(tmp_path, cited_docs=True)
        rows = {r["name"]: r for r in tc.inventory(root)}
        assert rows["dan_chung.log"]["action"] == "GIU" and rows["dan_chung.log"]["cited"]

    def test_symlink_dan_ra_ngoai_tmp_bi_chan(self, tmp_path):
        root = fake_repo(tmp_path)
        link = root / "tmp" / "shortcut"
        outside = root / "outputs"
        try:
            os.symlink(str(outside), str(link), target_is_directory=True)
        except (OSError, NotImplementedError):  # Windows không có quyền tạo symlink
            pytest.skip("hệ thống không cho phép tạo symlink trong test này")
        with pytest.raises(tc.CleanupRefusal):
            tc.check_target(root, "shortcut")
        report = tc.delete_targets(root, ["shortcut"], apply=True)
        assert report["deleted"] == [] and len(report["blocked"]) == 1
        assert outside.exists() and (root / "outputs" / "keep.json").exists()

    def test_junction_khong_can_quyen_van_bi_chan(self, tmp_path):
        """`mklink /J` (Windows) tạo junction **không cần quyền admin** và `is_symlink()` trả `False`
        — đúng lỗ hổng mà `is_link()` phải bắt được bằng so sánh realpath."""
        root = fake_repo(tmp_path)
        if not shutil.which("cmd"):
            pytest.skip("không có cmd (không phải Windows)")
        link = root / "tmp" / "junction"
        res = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(root / "outputs")],
                             capture_output=True, text=True)
        if res.returncode != 0 or not link.exists():
            pytest.skip(f"không tạo được junction: {(res.stdout + res.stderr)[:80]}")
        assert not link.is_symlink()            # bằng chứng: is_symlink() mù với junction
        assert tc.is_link(link, root / "tmp")   # nhưng is_link() vẫn nhận ra
        with pytest.raises(tc.CleanupRefusal):
            tc.check_target(root, "junction")
        report = tc.delete_targets(root, ["junction"], apply=True)
        assert report["deleted"] == [] and len(report["blocked"]) == 1
        assert (root / "outputs" / "keep.json").exists()   # không xoá xuyên junction
        rows = {r["name"]: r for r in tc.inventory(root)}
        assert rows["junction"]["action"] == "CHAN"

    def test_chan_symlink_khong_phan_biet_no_travo_dau(self, tmp_path):
        """Luật là 'mọi symlink đều chặn', kể cả khi nó trỏ tới một mục vô hại bên trong tmp/."""
        root = fake_repo(tmp_path)
        link = root / "tmp" / "shortcut_in_tmp"
        try:
            os.symlink(str(root / "tmp" / "cache_dir"), str(link), target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("hệ thống không cho phép tạo symlink")
        with pytest.raises(tc.CleanupRefusal):
            tc.check_target(root, "shortcut_in_tmp")

    def test_muc_trong_tmp_trung_ten_vung_bao_ve_van_xoa_duoc(self, tmp_path):
        """Chặn theo **vị trí thật**, không theo tên: `tmp/outputs` là scratch, không phải outputs/ của repo."""
        root = fake_repo(tmp_path)
        inside = root / "tmp" / "outputs"
        inside.mkdir()
        (inside / "junk.log").write_text("x", encoding="utf-8")
        assert tc.check_target(root, "outputs") == inside
        report = tc.delete_targets(root, ["outputs"], apply=True)
        assert [d["name"] for d in report["deleted"]] == ["outputs"]
        assert not inside.exists()
        assert (root / "outputs" / "keep.json").exists()  # vùng bảo vệ thật vẫn nguyên

    # -- hai ca chứng minh ba lớp chặn KHÔNG dư nhau (đột biến M12/M14 của tmp/mutation_check_t7.py) --

    @staticmethod
    def _mkjunction(link: Path, target: Path) -> None:
        """Junction Windows (`mklink /J`) không cần quyền admin; `is_symlink()` mù với nó."""
        if not shutil.which("cmd"):
            pytest.skip("không có cmd (không phải Windows)")
        res = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                             capture_output=True, text=True)
        if res.returncode != 0 or not link.exists():
            pytest.skip(f"không tạo được junction: {(res.stdout + res.stderr)[:80]}")

    def test_junction_trong_tmp_dan_den_muc_khac_trong_tmp_van_bi_chan(self, tmp_path):
        """Lớp 1 (chặn MỌI link) là duy nhất ở ca này: realpath vẫn nằm trong `tmp/` nên lớp 2 im
        lặng, và `tmp/neo` không thuộc vùng bảo vệ nên lớp 3 cũng im lặng. Nếu bỏ lớp 1, lệnh xoá
        `shortcut_in_tmp` sẽ xuyên vào thư mục thật bên cạnh."""
        root = fake_repo(tmp_path)
        anchor = root / "tmp" / "neo"
        anchor.mkdir()
        (anchor / "quan_trong.log").write_text("du lieu" * 10, encoding="utf-8")
        self._mkjunction(root / "tmp" / "shortcut_in_tmp", anchor)
        with pytest.raises(tc.CleanupRefusal):
            tc.check_target(root, "shortcut_in_tmp")
        report = tc.delete_targets(root, ["shortcut_in_tmp"], apply=True)
        assert report["deleted"] == [] and len(report["blocked"]) == 1
        assert (anchor / "quan_trong.log").exists()      # không bị xoá xuyên junction
        rows = {r["name"]: r for r in tc.inventory(root)}
        assert rows["shortcut_in_tmp"]["action"] == "CHAN"

    def test_tmp_chinh_no_la_junction_ra_vung_bao_ve_bi_chan(self, tmp_path):
        """Lớp 3 (vùng bảo vệ theo realpath) là duy nhất ở ca này: `tmp/` được thay bằng junction trỏ
        thẳng vào `outputs/`. Khi đó `allow.resolve()` CHÍNH là `outputs/`, nên lớp 1 và lớp 2 đều
        không phát hiện gì — chỉ còn lớp 3 chặn được việc xoá dữ liệu được bảo vệ."""
        root = tmp_path
        (root / "outputs").mkdir()
        keep = root / "outputs" / "keep.json"
        keep.write_text('{"a": 1}', encoding="utf-8")
        self._mkjunction(root / "tmp", root / "outputs")
        assert tc.inventory(root)  # kiểm kê được nhưng không được xoá
        with pytest.raises(tc.CleanupRefusal):
            tc.check_target(root, "keep.json")
        report = tc.delete_targets(root, ["keep.json"], apply=True)
        assert report["deleted"] == [] and len(report["blocked"]) == 1
        assert keep.exists()



class TestRepoThatChiDoc:
    """Đọc repo thật để chắc dụng cụ không đề xuất xoá bằng chứng đã công bố."""

    def test_tmp_that_khong_co_de_xuat_trung_voi_bang_dan_chung(self):
        allow = ROOT / "tmp"
        if not allow.is_dir():
            pytest.skip("repo chạy test không có tmp/")
        rows = {r["name"]: r for r in tc.inventory(ROOT)}
        cited = tc.cited_names(ROOT)
        for evidence in ("mutation_check_t6.log", "mutation_check_t7.log", "chain_demo3",
                         "pytest_t5_final.txt", "mutation_check_cache_policy.py"):
            if evidence not in rows:
                continue
            assert rows[evidence]["action"] != "XOÁ-ĐỀ-XUẤT", evidence
        assert cited  # chứng tỏ phát hiện dẫn chứng chạy được trên repo thật

    def test_de_xuat_xoa_that_cua_repo_dau_nam_trong_tmp(self):
        allow = ROOT / "tmp"
        if not allow.is_dir():
            pytest.skip("repo chạy test không có tmp/")
        proposed = tc.summarize(tc.inventory(ROOT))["n_proposed_delete"]
        rows = {r["name"]: r for r in tc.inventory(ROOT)}
        assert proposed > 0
        for name, r in rows.items():
            if r["action"] == "XOÁ-ĐỀ-XUẤT":
                assert (allow / name).exists() and "/" not in name and "\\" not in name
