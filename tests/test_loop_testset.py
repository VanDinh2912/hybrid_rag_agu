# -*- coding: utf-8 -*-
"""Test quy tắc độc nhất id của bộ test (`tools/loop/testset.py`).

id sinh từ hash(nguồn + câu + thực thể chính), KHÔNG chứa mẫu câu, nên hai câu hỏi
khác nhau cùng mọc từ một mảnh vàng có thể trùng id. Vòng lặp chấm theo id:
`item_by_id` chỉ giữ một item mỗi id, item còn lại bị chấm bằng gold của item khác
(im lặng), và câu chưa chạy bị coi là đã chạy. r0 thật từng có 811 item mà chỉ 805
id — nghĩa là 6 câu không bao giờ được đo đúng.
"""

from __future__ import annotations

from tools.loop.testset import resolve_id_collisions


def it(i: str, q: str) -> dict:
    return {"id": i, "raw_query": q, "family": "NUMERIC", "split": "test"}


class TestResolveIdCollisions:
    def test_giữ_id_cho_lần_đầu_thêm_hậu_tố_cho_lần_sau(self):
        items = [it("A", "Câu 1"), it("A", "Câu 2"), it("A", "Câu 3"), it("B", "Câu 4")]
        fixed, collisions = resolve_id_collisions(items)
        assert [i["id"] for i in fixed] == ["A", "A#2", "A#3", "B"]
        assert collisions == 2

    def test_không_đổi_khi_id_đã_độc_nhất(self):
        items = [it("A", "1"), it("B", "2")]
        fixed, collisions = resolve_id_collisions([dict(i) for i in items])
        assert [i["id"] for i in fixed] == ["A", "B"] and collisions == 0

    def test_tất_định_theo_thứ_tự_danh_sách(self):
        a = resolve_id_collisions([it("A", "x"), it("A", "y")])[0]
        b = resolve_id_collisions([it("A", "x"), it("A", "y")])[0]
        assert [i["id"] for i in a] == [i["id"] for i in b]

    def test_thứ_tự_và_nội_dung_khác_không_bị_động(self):
        items = [it("A", "x"), it("B", "y"), it("A", "z")]
        fixed, _ = resolve_id_collisions(items)
        assert [i["raw_query"] for i in fixed] == ["x", "y", "z"]

    def test_không_bao_giờ_còn_hai_item_cùng_id(self):
        items = [it("A", str(n)) for n in range(5)]
        fixed, collisions = resolve_id_collisions(items)
        assert len({i["id"] for i in fixed}) == len(fixed) == 5 and collisions == 4
