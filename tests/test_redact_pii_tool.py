# -*- coding: utf-8 -*-
"""PA-31 — kiểm dụng cụ che PII `tools/diag/redact_pii.py`.

Vì sao có tệp này (01-11): tool đã chạy một lượt bằng tay cho 18 artifact nhưng **không có test
nào gọi nó**. Nó là tool GHI, và ba lỗi của loại tool này đều im lặng: làm hỏng JSON (escape `\\`
đứng trước token), đổi số dòng/kiểu xuống dòng, hoặc che nhầm số tiền/số thực thành số điện thoại.
Lượt chạy 01-11 còn lộ hai lỗi thật, cả hai được khoá lại dưới đây:

* `--out` tương đối làm `relative_to(ROOT)` ném `ValueError` SAU khi đã che xong;
* `count_personal_paths` đếm `C:/Users/<tên>` hai lần (hai khuôn cùng khớp) trong khi lượt che
  chỉ thay một lần ⇒ cột "trước" trong báo cáo lớn hơn số thật.

Mọi test chạy trên cây giả trong `tmp_path` (`monkeypatch` `redact_pii.ROOT`) — không đọc, không
ghi tệp thật, không đụng `.env`.

Chuỗi mẫu ở đây **được ghép từ mảnh** (`_ghep`): `secret_scan.py` quét MỌI file track, nên một
email/đường dẫn viết liền trong tệp test sẽ bị đếm là PII thật và làm đỏ pin 76/1 của
`test_final_secret_scan.py`. Đây là bài học từ chính lượt viết tệp này.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools.diag import redact_pii as redact


def _ghep(*parts: str) -> str:
    """Ghép mảnh chuỗi mẫu để tệp test không tự chứa email/SĐT/đường dẫn cá nhân đầy đủ."""
    return "".join(parts)


MAIL = _ghep("sv1@", "truong.edu.vn")
MAIL2 = _ghep("sv2@", "truong.edu.vn")
MAIL_KHAC = _ghep("ccc@", "truong.edu.vn")

P_WIN = _ghep("D:", "\\", "Users", "\\", "vandi", "\\logs\\run.txt")
P_WIN_MASK = _ghep("D:", "\\", "Users", "\\", "<user>", "\\logs\\run.txt")
P_DRIVE = _ghep("C:/", "Users", "/alice/x.txt")
P_DRIVE_MASK = _ghep("C:/", "Users", "/<user>/x.txt")
P_HOME = _ghep("/home", "/alice/x.txt")
P_HOME_MASK = _ghep("/home", "/<user>/x.txt")
P_USERS = _ghep("/Users", "/bob/x.txt")
P_USERS_MASK = _ghep("/Users", "/<user>/x.txt")
P_XEM = _ghep("xem /home", "/alice/x.txt")
P_XEM_MASK = _ghep("xem /home", "/<user>/x.txt")

SDT = _ghep("0987", "654321")
SDT_CHAM = _ghep("0987", ".654.321")
SDT_SPACE = _ghep("0987", " 654 321")
MSSV = _ghep("MSSV: ", "2021", "0001")


def _ghi(root: Path, rel: str, text: str) -> Path:
    """Ghi tệp nguồn trong cây giả; giữ nguyên byte (không đổi kiểu xuống dòng)."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="")
    return p


def _doc(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8", newline="")


# ---------------------------------------------------------------------------
# Phạm vi che: bộ mặc định không được phình, testset đóng băng không được che
# ---------------------------------------------------------------------------
def test_bo_mac_dinh_dung_8_tep_ho_so_va_full_them_10():
    assert len(redact.PA31_FILES) == 8
    assert len(set(redact.PA31_FILES)) == 8
    assert len(redact.PA31_EXTRA_FILES) == 10
    assert len(set(redact.PA31_EXTRA_FILES)) == 10
    assert not set(redact.PA31_FILES) & set(redact.PA31_EXTRA_FILES)


def test_testset_dong_bang_khong_bao_gio_bi_che():
    """`data/loop/testset_v1.jsonl` là tập đo đã đóng băng (sha `202ca508…`) — che là đổi thước."""
    testset = "data/loop/testset_v1.jsonl"

    assert testset not in redact.PA31_FILES
    assert testset not in redact.PA31_EXTRA_FILES
    # Không tệp nào khác trùng tên ⇒ `--set full` cũng không chạm testset.
    assert Path(testset).name not in {
        Path(rel).name for rel in redact.PA31_FILES + redact.PA31_EXTRA_FILES
    }


def test_chi_che_lop_du_cao_nhan_hoc():
    """Tool KHÔNG che SECRET_COTHAT/BI_MAU: máy quét khai 0 ca secret, và đổi lớp là đổi thước."""
    import tools.diag.secret_scan as secret_scan

    assert {kind for kind, _name, _rx in redact.PII_PATTERNS} == {"DU_CAO_NHAN_HOC"}
    assert len(redact.PII_PATTERNS) == sum(
        1 for kind, _name, _rx in secret_scan.PATTERNS if kind == "DU_CAO_NHAN_HOC"
    )
    # Dùng ĐÚNG khuôn của máy quét đã công bố, không phát minh khuôn mới.
    assert [rx.pattern for _k, _n, rx in redact.PII_PATTERNS] == [
        rx.pattern for kind, _n, rx in secret_scan.PATTERNS if kind == "DU_CAO_NHAN_HOC"
    ]


# ---------------------------------------------------------------------------
# Đường dẫn cá nhân
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (P_WIN, P_WIN_MASK),
        (P_DRIVE, P_DRIVE_MASK),
        (P_HOME, P_HOME_MASK),
        (P_USERS, P_USERS_MASK),
        # Không phải thư mục người dùng ⇒ giữ nguyên.
        (r"D:\DoAn\hybrid_rag_agu\data\x.txt", r"D:\DoAn\hybrid_rag_agu\data\x.txt"),
        # `...stuff/home/...` không phải đường dẫn tuyệt đối ⇒ không khớp (lookbehind).
        ("mystuff/home/alice/x.txt", "mystuff/home/alice/x.txt"),
        (P_XEM, P_XEM_MASK),
    ],
)
def test_che_dung_ten_nguoi_dung_trong_duong_dan(raw, expected):
    masked, n = redact.mask_personal_paths(raw)

    assert masked == expected
    # `C:/Users/<tên>` khớp CẢ hai khuôn; bộ đếm phải bằng số lần che THẬT (1), không phải 2.
    assert n == redact.count_personal_paths(raw)


def test_dem_duong_dan_ca_nhan_truoc_va_sau_khi_che():
    raw = _ghep("C:", "\\", "Users", "\\", "vandi", "\\a.txt và /home", "/alice/b.txt")
    masked, n = redact.mask_personal_paths(raw)

    assert n == 2
    assert "vandi" not in masked and "alice" not in masked
    assert redact.count_personal_paths(raw) == 2
    assert redact.count_personal_paths(masked) == 0


# ---------------------------------------------------------------------------
# Số điện thoại: chốt chống dương tính giả
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("candidate", "ok"),
    [
        (SDT, True),                                  # di động 10 số, viết liền
        (SDT_CHAM, True),                             # di động 10 số, có dấu chấm
        (SDT_SPACE, True),                            # di động 10 số, có khoảng trắng
        (_ghep("024", "12345678"), True),             # cố định 11 số
        (_ghep("024", ".1234.5678"), True),
        ("0.987654321", False),                       # số THỰC: đếm chữ số sẽ che nhầm
        ("000 988.400", False),                       # số tiền
        (_ghep("0987", "65432"), False),              # 9 chữ số
        (_ghep("0987", "6543210"), False),            # 11 chữ số nhưng không phải đầu 02
    ],
)
def test_phone_ok_chi_nhan_sdt_vn_tron_ven(candidate, ok):
    assert redact.phone_ok(candidate) is ok


def test_che_sdt_dang_nhom_nhung_khong_che_so_thuc():
    seen: dict[str, str] = {}
    out, n = redact.mask_broad_phone(
        _ghep("Hotline 0987", ".654.321, giá 0.987654321"), seen)

    assert n == 1
    assert _ghep("0987", ".654.321") not in out
    assert "0.987654321" in out
    assert "[PHONE_B_1]" in out
    assert redact.count_broad(out) == 0

    # Cùng số ⇒ cùng token (tất định), số khác ⇒ token mới.
    out2, _ = redact.mask_broad_phone(_ghep("lại 0987", " 654 321"), seen)
    out3, _ = redact.mask_broad_phone(_ghep("và 0912", ".345.678"), seen)
    assert "[PHONE_B_1]" in out2
    assert "[PHONE_B_2]" in out3


# ---------------------------------------------------------------------------
# Che tất định + toàn vẹn cấu trúc
# ---------------------------------------------------------------------------
def test_che_tat_dinh_giu_so_dong_va_khong_sua_tep_goc(tmp_path, monkeypatch):
    rel = "data/loop/f.txt"
    goc = f"a {MAIL}\r\nb {MAIL} {MAIL2}\r\n"
    src = _ghi(tmp_path, rel, goc)
    monkeypatch.setattr(redact, "ROOT", tmp_path)

    rec = redact.redact_file(rel, tmp_path / "out", dry=False)
    out = _doc(tmp_path, "out/f.txt")

    assert rec["lines_before"] == rec["lines_after"] == 2
    assert out.count("\r\n") == 2, "phải giữ CRLF"
    assert out.count("[EMAIL_1]") == 2, "cùng giá trị ⇒ cùng token"
    assert out.count("[EMAIL_2]") == 1
    assert _ghep("sv1@", "truong") not in out
    assert rec["pii_hits_before"] == 3
    assert rec["pii_hits_after"] == 0
    # Bản gốc chỉ được ĐỌC.
    assert _doc(tmp_path, rel) == goc


def test_che_lai_ban_da_che_khong_doi_them(tmp_path, monkeypatch):
    rel = "data/loop/f.txt"
    _ghi(tmp_path, rel, f"lien he {MAIL}\n")
    monkeypatch.setattr(redact, "ROOT", tmp_path)

    redact.redact_file(rel, tmp_path / "out", dry=False)
    lan1 = _doc(tmp_path, "out/f.txt")
    rec2 = redact.redact_file("out/f.txt", tmp_path / "out2", dry=False)

    assert rec2["pii_hits_before"] == 0
    assert _doc(tmp_path, "out2/out/f.txt") == lan1


def test_json_van_hop_le_khi_email_nam_sat_escape(tmp_path, monkeypatch):
    """Chuỗi JSON `"dong1\\nsv1@…"` làm khuôn email khớp từ chữ `n` của escape.

    Thay thẳng bằng `[EMAIL_1]` sẽ tạo `\\[` = escape KHÔNG hợp lệ; tool phải nhân đôi `\\`.
    """
    rel = "data/loop/d.json"
    _ghi(tmp_path, rel, '{"msg": "dong1\\n' + MAIL + '"}\n')
    monkeypatch.setattr(redact, "ROOT", tmp_path)

    rec = redact.redact_file(rel, tmp_path / "out", dry=False)
    out = _doc(tmp_path, "out/d.json")

    assert rec["json_valid_after"] is True
    assert rec["pii_hits_after"] == 0
    assert json.loads(out)["msg"].endswith("[EMAIL_1]")
    assert '"dong1\\\\[EMAIL_1]"' in out, "phải là `\\\\[` (escape hợp lệ), không phải `\\[`"


def test_jsonl_giu_so_ban_ghi_sau_khi_che(tmp_path, monkeypatch):
    rel = "data/loop/d.jsonl"
    goc = (
        json.dumps({"q": MSSV, "sdt": SDT}, ensure_ascii=False) + "\n"
        + json.dumps({"q": "không có gì"}, ensure_ascii=False) + "\n"
    )
    _ghi(tmp_path, rel, goc)
    monkeypatch.setattr(redact, "ROOT", tmp_path)

    rec = redact.redact_file(rel, tmp_path / "out", dry=False)
    lines = _doc(tmp_path, "out/d.jsonl").splitlines()

    assert rec["lines_before"] == rec["lines_after"] == len(lines) == 2
    rows = [json.loads(x) for x in lines]
    assert rows[0]["q"] == "MSSV: [ID_1]"
    assert rows[0]["sdt"] == "[PHONE_1]"
    assert rows[1] == {"q": "không có gì"}


def test_email_vi_du_allowlist_khong_bi_che(tmp_path, monkeypatch):
    """Cùng luật bỏ qua với máy quét: domain ví dụ không tính là PII."""
    rel = "data/loop/f.txt"
    _ghi(tmp_path, rel, "aaa@example.com bbb@test.com " + MAIL_KHAC + "\n")
    monkeypatch.setattr(redact, "ROOT", tmp_path)

    rec = redact.redact_file(rel, tmp_path / "out", dry=True)
    assert rec["pii_hits_before"] == 1

    redact.redact_file(rel, tmp_path / "out", dry=False)
    out = _doc(tmp_path, "out/f.txt")
    assert "aaa@example.com" in out and "bbb@test.com" in out
    assert MAIL_KHAC not in out


def test_out_path_for_bo_tien_to_data_loop_va_giu_duong_dan_khac():
    assert redact.out_path_for("data/loop/diag/a.jsonl", Path("/tmp/out")).as_posix() == \
        "/tmp/out/diag/a.jsonl"
    assert redact.out_path_for("outputs/ab.json", Path("/tmp/out")).as_posix() == \
        "/tmp/out/outputs/ab.json"


# ---------------------------------------------------------------------------
# Giao diện dòng lệnh: `--out` tương đối (lỗi thật gặp 01-11) và `--out` ngoài repo
# ---------------------------------------------------------------------------
def test_out_tuong_doi_khong_no_va_ghi_dung_cho(tmp_path, monkeypatch):
    monkeypatch.setattr(redact, "ROOT", tmp_path)
    monkeypatch.setattr(redact, "PA31_FILES", ["data/loop/a.txt"])
    monkeypatch.setattr(redact, "PA31_EXTRA_FILES", [])
    _ghi(tmp_path, "data/loop/a.txt", f"lien he {MAIL}\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["redact_pii.py", "--out", "out_rel"])

    assert redact.main() == 0
    assert _doc(tmp_path, "out_rel/a.txt") == "lien he [EMAIL_1]\n"
    rep = json.loads(_doc(tmp_path, "out_rel/REDACTION_REPORT.json"))
    assert rep["gate"] == {"lines_kept": True, "json_valid": True, "pii_zero_after": True}
    assert rep["files"][0]["out"] == "out_rel/a.txt"


def test_out_ngoai_root_van_ghi_va_bao_cao_khong_no(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _ghi(repo, "data/loop/a.txt", f"lien he {MAIL}\n")
    monkeypatch.setattr(redact, "ROOT", repo)

    rec = redact.redact_file("data/loop/a.txt", tmp_path / "ngoai", dry=False)

    assert Path(rec["out"]).is_absolute()
    assert _doc(tmp_path, "ngoai/a.txt") == "lien he [EMAIL_1]\n"
