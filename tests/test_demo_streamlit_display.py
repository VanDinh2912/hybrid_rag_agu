"""P5.1 — khối hiển thị "🏷️ Phân loại câu hỏi" của ui/demo_streamlit.py.

Thuần offline: chỉ test hàm format thuần; import ui.demo_streamlit không chạy app.
"""

from __future__ import annotations

from ui.demo_streamlit import format_classification_lines


def test_labels_none_live_shows_dash_only():
    lines = format_classification_lines(None, None, None, "live")
    assert lines == ["Nhãn phân loại: —"]


def test_labels_none_replay_shows_guide_note():
    lines = format_classification_lines(None, None, None, "replay")
    assert lines[0] == "Nhãn phân loại: —"
    assert any("--with-classifier" in line for line in lines)


def test_labels_full_with_subqueries():
    labels = {"topic": "khen thưởng sinh viên", "question_type": "SO_SANH"}
    config = {
        "top_k": 6,
        "bm25_weight": 0.5,
        "chroma_weight": 0.5,
        "source_filter": ["quy-che-khen-thuong.pdf"],
        "enable_subquery": True,
    }
    lines = format_classification_lines(labels, config, ["q1", "q2"], "live")
    text = "\n".join(lines)
    assert "khen thưởng sinh viên" in text
    assert "SO_SANH" in text
    assert "top_k=6" in text
    assert "bm25=0.5/chroma=0.5" in text
    assert "lọc nguồn: quy-che-khen-thuong.pdf" in text
    assert "Tách truy vấn con: CÓ (2 nhánh)" in text


def test_labels_subquery_enabled_but_guardrail_fell_back():
    labels = {"topic": "học phí", "question_type": "TRA_CUU"}
    config = {"top_k": 3, "bm25_weight": 0.4, "chroma_weight": 0.3, "enable_subquery": True}
    lines = format_classification_lines(labels, config, None, "live")
    assert "Tách truy vấn con: CÓ (guardrail lùi về đường đơn)" in lines[-1]


def test_labels_subquery_disabled():
    labels = {"topic": "ký túc xá", "question_type": "TRA_CUU"}
    config = {"top_k": 3, "bm25_weight": 0.4, "chroma_weight": 0.3, "enable_subquery": False}
    lines = format_classification_lines(labels, config, None, "live")
    assert "Tách truy vấn con: KHÔNG" in lines[-1]


def test_labels_none_values_show_dash_not_raw_none():
    """Classifier trả None cho giá trị (vd câu ngoài corpus → chủ đề None) —
    hiển thị '—', KHÔNG render chữ 'None' thô (.get(key, '—') không bắt None)."""
    labels = {"topic": None, "question_type": "TRA_CUU"}
    config = {"top_k": 3, "bm25_weight": 0.5, "chroma_weight": 0.5}
    lines = format_classification_lines(labels, config, None, "live")
    text = "\n".join(lines)
    assert "chủ đề **—**" in text
    assert "loại câu hỏi **TRA_CUU**" in text
    assert "None" not in text

