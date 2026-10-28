# -*- coding: utf-8 -*-
"""Test cho `tools/diag/docs_consistency_check.py` (T7 — mục 5–6 đề bài).

Mục 5: mỗi mục trong `docs/DECISION_LOG.md` phải có **ngày – giả thuyết – số đo – nguồn – trạng
thái**, và **mọi đường dẫn nguồn phải tồn tại trên đĩa**.
Mục 6: mọi file README/ROADMAP nhắc tới phải có thật; mọi lệnh trỏ script repo phải chạy được ở
chế độ `--help` (hoặc ít nhất file phải tồn tại).

Test chạy trên **cây giả trong `tmp_path`** cho phần "dụng cụ có bắt được lỗi không", và trên
**repo thật ở chế độ chỉ-đọc** cho phần "tài liệu hiện tại sạch". Nhóm giả phải đỏ khi cố tình
gài lỗi; nhóm thật phải xanh. Không gọi model, không ghi file thật.

Vì sao phải dựng cây giả: nếu chỉ test "repo thật sạch" thì một dụng cụ luôn trả rỗng cũng xanh.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools.diag import docs_consistency_check as dc

ROOT = Path(__file__).resolve().parents[1]

GOOD_ROW = (
    "| D-01 | 24-10 | Giả thuyết: bonus 12 giữ neo vàng nên tăng gold | "
    "gold@6 0,5186 → 0,7400 (811 item) | `data/loop/rounds/r2` + `tools/loop/gate.py` | GIỮ |"
)


def make_repo(tmp_path: Path, *, log_rows=(GOOD_ROW,), readme="", roadmap="") -> Path:
    """Cây repo tối giản: docs/DECISION_LOG.md + README.md + ROADMAP.md + vài file thật."""
    root = tmp_path
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "src" / "gate_like.py").write_text("# chỉ chạy trực tiếp, không có CLI\nprint('hi')\n",
                                                encoding="utf-8")
    (root / "tools" / "real.py").write_text(
        "import argparse\np = argparse.ArgumentParser()\np.parse_args()\n", encoding="utf-8"
    )
    # đường dẫn mà GOOD_ROW dẫn làm nguồn — phải có thật trong cây giả
    (root / "tools" / "loop").mkdir(parents=True, exist_ok=True)
    (root / "tools" / "loop" / "gate.py").write_text(
        "import argparse\np = argparse.ArgumentParser()\np.parse_args()\n", encoding="utf-8"
    )
    (root / "data" / "loop" / "rounds" / "r2").mkdir(parents=True, exist_ok=True)
    (root / "data" / "loop" / "rounds" / "r2" / "retrieval.jsonl").write_text("{}\n", encoding="utf-8")
    header = "| ID | Ngày | Giả thuyết | Số đo quyết định | Nguồn | Trạng thái |\n|---|---|---|---|---|---|\n"
    (root / "docs" / "DECISION_LOG.md").write_text(header + "\n".join(log_rows) + "\n", encoding="utf-8")
    (root / "README.md").write_text(readme or "# Dự án\n\nXem `tools/real.py`.\n", encoding="utf-8")
    (root / "docs" / "planning").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "planning" / "ROADMAP.md").write_text(roadmap or "# Lộ trình\n\nDùng `src/gate_like.py`.\n", encoding="utf-8")
    return root


def rows_of(text: str) -> list[dict]:
    return dc.decision_rows(text)


# ---------------------------------------------------------------------------
# Mục 5(a) — đủ trường
# ---------------------------------------------------------------------------

class TestSoQuyetDinhDuTruong:
    def test_dong_du_sau_cot_sach(self, tmp_path):
        root = make_repo(tmp_path)
        text = (root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8")
        assert dc.check_decision_log(rows_of(text)) == []

    def test_thieu_ngay_bi_bat(self, tmp_path):
        bad = GOOD_ROW.replace("| 24-10 |", "|  |")
        root = make_repo(tmp_path, log_rows=(bad,))
        probs = dc.check_decision_log(rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8")))
        assert any("ngày" in p for p in probs)

    def test_so_do_khong_chua_con_so_bi_bat(self, tmp_path):
        bad = GOOD_ROW.replace("gold@6 0,5186 → 0,7400 (811 item)", "cảm giác là tốt hơn")
        root = make_repo(tmp_path, log_rows=(bad,))
        probs = dc.check_decision_log(rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8")))
        assert any("con số" in p for p in probs)

    def test_gia_thuyet_rong_bi_bat(self, tmp_path):
        bad = GOOD_ROW.replace("Giả thuyết: bonus 12 giữ neo vàng nên tăng gold", "-")
        root = make_repo(tmp_path, log_rows=(bad,))
        probs = dc.check_decision_log(rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8")))
        assert any("giả thuyết" in p for p in probs)

    def test_trang_thai_khong_phai_quy_uoc_bi_bat(self, tmp_path):
        bad = GOOD_ROW.replace("| GIỮ |", "| ok thì cứ làm |")
        root = make_repo(tmp_path, log_rows=(bad,))
        probs = dc.check_decision_log(rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8")))
        assert any("trạng thái" in p for p in probs)

    def test_bang_non_du_cot_van_doc_dung_sau_o(self, tmp_path):
        """`| 8 cột |` dính sát hai bên dấu `|` từng làm ô bị cắt sai — giữ làm hồi quy."""
        row = "| D-09 | 24-10 | Giả thuyết dài đủ mười ký tự | delta = −0,0257 (p = 0,00028, 8 cột so 7 cột) | `tools/loop/gate.py` | GIỮ |"
        parsed = rows_of(row)[0]
        assert parsed["n_cells"] == 6
        assert parsed["source"] == "`tools/loop/gate.py`"
        assert dc.check_decision_log([parsed]) == []

    def test_id_lap_bi_bat(self, tmp_path):
        root = make_repo(tmp_path, log_rows=(GOOD_ROW, GOOD_ROW))
        probs = dc.check_decision_log(rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8")))
        assert any("bị lặp" in p for p in probs)

    def test_thieu_cot_bi_bat(self, tmp_path):
        cut = "|".join(GOOD_ROW.split("|")[:6]) + "|"
        root = make_repo(tmp_path, log_rows=(cut,))
        probs = dc.check_decision_log(rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8")))
        assert any("6 cột" in p for p in probs)


# ---------------------------------------------------------------------------
# Mục 5(b) — đường dẫn nguồn phải tồn tại
# ---------------------------------------------------------------------------

class TestDuongDanNguonTonTai:
    def test_duong_dan_hop_le_khong_bao_loi(self, tmp_path):
        root = make_repo(tmp_path)
        rows = rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8"))
        assert dc.check_source_paths(root, rows) == []

    def test_nguon_khong_co_that_bi_bat(self, tmp_path):
        bad = GOOD_ROW.replace("`data/loop/rounds/r2`", "`data/loop/rounds/khong_co`")
        root = make_repo(tmp_path, log_rows=(bad,))
        rows = rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8"))
        probs = dc.check_source_paths(root, rows)
        assert any("khong_co" in p for p in probs) and any("D-01" in p for p in probs)

    def test_ten_tran_tim_duoc_trong_repo_thoa_mai(self, tmp_path):
        bad = GOOD_ROW.replace("`data/loop/rounds/r2`", "`retrieval.jsonl`")
        root = make_repo(tmp_path, log_rows=(bad,))
        rows = rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8"))
        assert dc.check_source_paths(root, rows) == []

    def test_brace_moi_rong_that_bi_bat(self, tmp_path):
        root = make_repo(tmp_path)
        bad = GOOD_ROW.replace("`data/loop/rounds/r2`", "`data/loop/rounds/r2/probe{,_len}.json`")
        (root / "docs" / "DECISION_LOG.md").write_text(
            (root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8").replace(
                "`data/loop/rounds/r2`", "`data/loop/rounds/r2/probe{,_len}.json`"
            ), encoding="utf-8")
        rows = rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8"))
        probs = dc.check_source_paths(root, rows)
        assert len(probs) == 2 and all("probe" in p for p in probs)
        # khi cả hai nhánh đều có file thì phải sạch (chứng minh test trên không đỏ cố định)
        for name in ("probe.json", "probe_len.json"):
            (root / "data" / "loop" / "rounds" / "r2" / name).write_text("{}", encoding="utf-8")
        assert dc.check_source_paths(root, rows) == []

    def test_hau_to_so_va_chu_thich_ham_khong_lam_sai_duong_dan(self, tmp_path):
        root = make_repo(tmp_path)
        for cand in ("`tools/real.py::ham_kiem`", "`tools/real.py:95`", "`tools/real.py,356,386`",
                     "`data/loop/rounds/r2/*`", "`docs/DECISION_LOG.md §2.7`"):
            got = dc.path_candidates(cand)
            assert got and all("§" not in g and "::" not in g and ":" not in g for g in got), cand

    def test_chuang_mo_ta_khong_ban_thanh_loi(self, tmp_path):
        assert dc.looks_like_pattern("logs/benchmark/chroma_<strategy>/")
        assert dc.looks_like_pattern("src/a|b.py")
        assert not dc.looks_like_pattern("tools/real.py")

    def test_mota_khong_phai_file_khong_bao_loi(self, tmp_path):
        root = make_repo(tmp_path)
        bad = GOOD_ROW.replace("`data/loop/rounds/r2`", "`logs/benchmark/chroma_<strategy>/`")
        (root / "docs" / "DECISION_LOG.md").write_text(
            (root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8").replace(
                "`data/loop/rounds/r2`", "`logs/benchmark/chroma_<strategy>/`"), encoding="utf-8")
        rows = rows_of((root / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8"))
        assert dc.check_source_paths(root, rows) == []


# ---------------------------------------------------------------------------
# Mục 6(a) — file được nhắc phải tồn tại
# ---------------------------------------------------------------------------

class TestFileDuocNhcPhaiTonTai:
    def test_doc_sach_khong_loi(self, tmp_path):
        root = make_repo(tmp_path)
        probs, notes = dc.check_referenced_files(root)
        assert probs == []
        assert any("đã kiểm" in n for n in notes)

    def test_nhac_file_khong_co_that_bi_bat(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\nSửa `src/khong_ton_tai.py` nhé.\n")
        probs, _ = dc.check_referenced_files(root)
        assert any("src/khong_ton_tai.py" in p for p in probs)

    def test_link_markdown_cung_bi_kiem(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\n[xem](tools/loop/khong.py)\n")
        probs, _ = dc.check_referenced_files(root)
        assert any("tools/loop/khong.py" in p for p in probs)

    def test_thu_muc_sinh_luc_chay_khong_bao_loi(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\nLog ở `logs/feedback/`, cache ở `chroma_db/`, "
                                           "nháp trong `tmp/`.\n")
        probs, _ = dc.check_referenced_files(root)
        assert probs == []

    def test_file_tu_sinh_cua_gui_khong_bao_loi_nhung_ghi_ranh(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\nGhi vào `data/normalization_pairs.json`.\n")
        probs, notes = dc.check_referenced_files(root)
        assert probs == []
        assert any("tự sinh" in n for n in notes)
        # một file `data/` KHÁC mà không có thật vẫn phải bị bắt:
        root2 = make_repo(tmp_path / "b", readme="# A\n\nGhi vào `data/keyword_maps.json`.\n")
        probs2, _ = dc.check_referenced_files(root2)
        assert any("keyword_maps" in p for p in probs2)

    def test_nhac_bang_ky_tu_dac_biet_khong_phai_file(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\nChiến lược `data/loop/rounds/<r>/`, `a|b.py`, "
                                          "`tools/loop/*.py`.\n")
        probs, _ = dc.check_referenced_files(root)
        assert probs == []


# ---------------------------------------------------------------------------
# Mục 6(b) — lệnh trong tài liệu phải chạy được ở --help
# ---------------------------------------------------------------------------

class TestLenhPhaiChayDuoc:
    def test_lenh_tro_script_khong_co_file_la_loi(self, tmp_path):
        root = make_repo(tmp_path, readme=(
            "# A\n\n```bash\npython tools/khong_co.py --help\n```\n"))
        cmds = dc.commands_from_docs(root)
        probs, warns = dc.check_command_scripts(root, cmds)
        assert any("tools/khong_co.py" in p for p in probs)
        assert warns == []

    def test_script_khong_argparse_chi_la_canh_bao(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\n```bash\npython src/gate_like.py\n```\n")
        cmds = dc.commands_from_docs(root)
        probs, warns = dc.check_command_scripts(root, cmds)
        assert probs == []
        assert any("src/gate_like.py" in w and "argparse" in w for w in warns)

    def test_lenh_ha_tang_khong_bi_tinh(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\n```bash\npip install -r requirements.txt\n"
                                          "git clone X\n```\n")
        assert dc.check_command_scripts(root, dc.commands_from_docs(root))[0] == []

    def test_module_duoc_anh_xa_ra_file(self, tmp_path):
        line = "python -m tools.loop.gate --candidate x"
        info = dc.classify_command(make_repo(tmp_path), line)
        assert info["kind"] == "repo-script" and info["script"] == "tools/loop/gate.py"

    def test_run_help_tra_rc_0_va_phat_hien_rc_khac_0(self, tmp_path):
        root = make_repo(tmp_path)
        (root / "tools" / "bad.py").write_text(
            "import argparse, sys\nargparse.ArgumentParser()\nsys.exit(3)\n", encoding="utf-8")
        res = {r["script"]: r["rc"] for r in dc.run_help(root, ["tools/real.py", "tools/bad.py"])}
        assert res["tools/real.py"] == 0
        assert res["tools/bad.py"] == 3

    def test_run_help_khong_loai_bang_file_thieu(self, tmp_path):
        root = make_repo(tmp_path)
        res = dc.run_help(root, ["tools/khong_co_file.py"])
        assert res[0]["rc"] in (1, 2, 127)   # python báo "cannot find file", không được ném ngoại lệ

    def test_run_help_bat_timeout(self, tmp_path):
        root = make_repo(tmp_path)
        (root / "tools" / "tre.py").write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        res = dc.run_help(root, ["tools/tre.py"], timeout=2)
        assert res[0]["rc"] == 124

    def test_main_tra_1_khi_co_loi_0_khi_sach(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\nSửa `src/khong_ton_tai.py`.\n")
        out = dc.check_all(root)
        assert out["referenced_file_problems"] and out["decision_problems"] == []
        assert dc.main(["--root", str(root)]) == 1
        ok = make_repo(tmp_path / "b")
        assert dc.main(["--root", str(ok)]) == 0

    def test_scope_loc_nhom_kiem(self, tmp_path):
        root = make_repo(tmp_path, readme="# A\n\nSửa `src/khong_ton_tai.py`.\n")
        assert dc.main(["--root", str(root), "--scope", "log"]) == 0     # lỗi nằm ở nhóm files
        assert dc.main(["--root", str(root), "--scope", "files"]) == 1
        assert dc.main(["--root", str(root), "--scope", "all"]) == 1

    def test_json_ghi_du_ket_qua(self, tmp_path):
        root = make_repo(tmp_path)
        out = root / "tmp" / "chk.json"
        assert dc.main(["--root", str(root), "--json", str(out)]) == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        for key in ("decision_rows", "decision_problems", "referenced_file_problems",
                    "command_problems", "command_warnings", "help_checked", "notes"):
            assert key in payload


# ---------------------------------------------------------------------------
# Repo thật — chế độ chỉ-đọc: tài liệu hiện tại PHẢI sạch
# ---------------------------------------------------------------------------

class TestRepoThatChiDoc:
    def test_sach_loi_ca_ba_nhom_kiem(self):
        out = dc.check_all(ROOT)
        assert out["decision_problems"] == [], out["decision_problems"]
        assert out["referenced_file_problems"] == [], out["referenced_file_problems"]
        assert out["command_problems"] == [], out["command_problems"]

    def test_so_muc_quyet_dinh_khong_giam(self):
        rows = dc.decision_rows((ROOT / dc.DECISION_LOG).read_text(encoding="utf-8"))
        assert len(rows) >= 20
        assert len({r["id"] for r in rows}) == len(rows)
        assert all(r["n_cells"] == 6 for r in rows)

    def test_moi_duong_dan_nguon_trong_so_ton_tai_tren_dia(self):
        """Đúng câu chữ đề bài: 'test kiểm mọi đường dẫn nguồn trong sổ tồn tại trên đĩa'."""
        rows = dc.decision_rows((ROOT / dc.DECISION_LOG).read_text(encoding="utf-8"))
        missing = []
        for r in rows:
            for cand in dc.path_candidates(r["source"]):
                p = ROOT / cand
                if p.exists() or p.parent.exists() and cand.endswith(("*", "…")):
                    continue
                if "/" not in cand and list(ROOT.glob(f"**/{cand}")):
                    continue
                missing.append(f"{r['id']}: {cand}")
        assert missing == []

    def test_script_khong_argparse_chi_dung_o_muc_canh_bao(self):
        """Danh sách 5 script chưa có --help (PA đề xuất thêm CLI). Test hướng subset: thêm argparse
        thì vẫn xanh, nhưng đưa thêm script chưa-argparse vào README sẽ đỏ."""
        out = dc.check_all(ROOT)
        da_biet = {"demo_streamlit.py", "ingest.py", "learn.py", "src/assessment/analyze_ab.py", "ui/app.py"}
        for w in out["command_warnings"]:
            assert any(s in w for s in da_biet), w
        assert out["help_problems"] == []

    def test_script_repo_doc_nhom_argparse_deu_in_duoc_help(self):
        """`--run-help` trên repo thật: mọi script README gọi mà có argparse phải trả mã 0."""
        out = dc.check_all(ROOT, run_help_checks=True)
        assert out["help_checked"] >= 3
        assert out["help_problems"] == [], out["help_problems"]
