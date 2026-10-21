# -*- coding: utf-8 -*-
"""Unit test P3.5 — hiển thị nhãn phân loại ở GUI (format_labels_display).

Thuần offline: format_labels_display là hàm thuần, import ui.app không mở
cửa sổ (khối chạy app nằm sau `if __name__ == "__main__"`).
"""

from ui.app import format_labels_display

LABELS = {"topic": "hoc_phi", "question_type": "SO_SANH"}
CFG = {
    "top_k": 8,
    "bm25_weight": 0.4,
    "chroma_weight": 0.6,
    "source_filter": ["1059-qd-dhag.pdf", "hoc-phi.pdf"],
    "enable_subquery": True,
}


class TestFormatLabelsDisplay:
    def test_none_labels_shows_dash(self):
        assert format_labels_display(None, None) == "—"

    def test_empty_labels_shows_dash(self):
        assert format_labels_display({}, CFG) == "—"

    def test_full_labels_line(self):
        line = format_labels_display(LABELS, CFG)
        assert "chủ đề: hoc_phi" in line
        assert "loại: SO_SANH" in line
        assert "top_k=8" in line
        assert "bm25=0.4/chroma=0.6" in line
        assert "lọc nguồn: 1059-qd-dhag.pdf, hoc-phi.pdf" in line

    def test_no_filter_omits_filter_part(self):
        line = format_labels_display(
            LABELS, {"top_k": 6, "bm25_weight": 0.5, "chroma_weight": 0.5, "source_filter": []}
        )
        assert "lọc nguồn" not in line
        assert "top_k=6" in line

    def test_missing_config_values_show_dash(self):
        line = format_labels_display(LABELS, {})
        assert "top_k=—" in line
        assert "loại: SO_SANH" in line
