# -*- coding: utf-8 -*-
"""Unit test cổng duyệt vòng lặp (`tools/loop/gate.py`).

Cổng là nơi duy nhất ngăn vòng lặp tự lừa mình, nên mỗi luật phải có một test
'nếu nới thì sao'. Không đụng GPU/Ollama: chỉ chấm trên dòng verdict giả lập.
"""

from __future__ import annotations

import copy

import pytest

from tools.loop.gate import compare, compatibility, load_rows, metrics, round_settings


def row(item_id: str, family: str, verdict: str, *, refusal: bool = False,
        unsupported: list | None = None, answer_chars: int = 200,
        gold_in_top_k: bool = True, grounding: float = 1.0,
        has_gold_chunk: bool | None = True,
        anchor: bool | None = None) -> dict:
    data = {
        "id": item_id,
        "family": family,
        "split": "test",
        "verdict": verdict,
        "is_refusal": refusal,
        "unsupported": unsupported or [],
        "answer_chars": answer_chars,
        "gold_in_top_k": gold_in_top_k,
        "grounding_score": grounding,
        "raw_query": f"câu hỏi {item_id}",
    }
    # None = verdict ghi bởi verify.py cũ (chưa có cờ này) — cổng phải coi là không đo được.
    if has_gold_chunk is not None:
        data["has_gold_chunk"] = has_gold_chunk
    if anchor is not None:
        data["expected_source_in_window"] = anchor
    return data


def bank(n: int = 40, *, family: str = "NUMERIC", fabricated: int = 0,
         refusals: int = 0) -> dict[str, dict]:
    """Ngân hàng n câu: phần lớn ĐÚNG, `fabricated` câu bịa, `refusals` câu từ chối oan."""
    rows = {}
    for i in range(n):
        if i < fabricated:
            rows[f"{family}-{i}"] = row(f"{family}-{i}", family, "FAIL_FABRICATED",
                                        unsupported=[{"kind": "number", "text": "500.000"}], grounding=0.7)
        elif i < fabricated + refusals:
            rows[f"{family}-{i}"] = row(f"{family}-{i}", family, "FAIL_OVERREFUSAL",
                                        refusal=True, answer_chars=70, gold_in_top_k=True)
        else:
            rows[f"{family}-{i}"] = row(f"{family}-{i}", family, "PASS_CORRECT")
    return rows


def _cmp(cand: dict[str, dict], base: dict[str, dict]) -> dict:
    common = sorted(set(cand) & set(base))
    c = metrics([cand[i] for i in common])
    b = metrics([base[i] for i in common])
    c["_rows"], b["_rows"] = cand, base
    return compare(c, b, common)


def retrieval_bank(n: int = 40, *, family: str = "NUMERIC", hits: int | None = None) -> dict[str, dict]:
    """Ngân hàng verdict của PHA TRUY XUẤT: `hits` câu PENDING (chunk vàng vào cửa sổ),
    còn lại FAIL_RETRIEVAL. Không câu nào có văn bản trả lời."""
    hits = n * 3 // 4 if hits is None else hits
    rows = {}
    for i in range(n):
        if i < hits:
            rows[f"{family}-{i}"] = row(
                f"{family}-{i}", family, "PENDING_GENERATION", answer_chars=0, gold_in_top_k=True
            )
        else:
            rows[f"{family}-{i}"] = row(
                f"{family}-{i}", family, "FAIL_RETRIEVAL", answer_chars=0, gold_in_top_k=False
            )
    return rows


def human_bank(n: int = 20, *, hits: int = 16, with_anchor_flag: bool = True) -> dict[str, dict]:
    """Neo HUMAN ở pha truy xuất: không có chunk vàng duy nhất, chỉ đo được
    'đúng văn bản có vào cửa sổ' (`expected_source_in_window`)."""
    rows = {}
    for i in range(n):
        rows[f"HUMAN-{i}"] = row(
            f"HUMAN-{i}",
            "HUMAN",
            "PENDING_GENERATION",
            answer_chars=0,
            has_gold_chunk=False,
            gold_in_top_k=False,
            anchor=(i < hits) if with_anchor_flag else None,
        )
    return rows


class TestMetrics:
    def test_tính_đúng_pass_rate_và_fabrication(self):
        rows = list(bank(20, fabricated=4).values())
        m = metrics(rows)
        assert m["n_decided"] == 20
        assert m["pass_rate"] == 0.8
        assert m["fabrication_rate_on_answered"] == round(4 / 20, 4)

    def test_câu_pending_không_tính_vào_mẫu(self):
        rows = [row("a", "EXACT", "PENDING_GENERATION", answer_chars=0)] + list(bank(19).values())
        m = metrics(rows)
        assert m["n"] == 20 and m["n_decided"] == 19

    def test_từ_chối_oan_đẩy_refusal_rate(self):
        m = metrics(list(bank(20, refusals=5).values()))
        assert m["refusal_rate"] == 0.25
        assert m["overrefusal"] == 5

    def test_pha_truy_xuất_recall_tính_trên_cả_câu_pending(self):
        """PENDING_GENERATION chính là 'đã trúng chunk vàng' — loại nó khỏi mẫu số
        (bug cũ) làm gold@k luôn bằng 0 và cổng báo ĐẠT giả."""
        m = metrics(list(retrieval_bank(40, hits=30).values()))
        assert m["n_gold_items"] == 40
        assert m["gold_in_top_k_rate"] == 0.75
        assert m["has_answer_signal"] is False
        assert m["pass_rate"] is None
        assert m["by_family"]["NUMERIC"]["gold_rate"] == 0.75

    def test_item_không_có_chunk_vàng_nằm_ngoài_mẫu_số_recall(self):
        rows = list(retrieval_bank(8, hits=6).values()) + [
            row(f"HUMAN-{i}", "HUMAN", "PENDING_GENERATION", answer_chars=0,
                gold_in_top_k=False, has_gold_chunk=False)
            for i in range(4)
        ]
        m = metrics(rows)
        assert m["n_gold_items"] == 8
        assert m["gold_in_top_k_rate"] == 0.75

    def test_neo_human_đo_bằng_tỉ_lệ_đúng_nguồn_vào_cửa_sổ(self):
        m = metrics(list(human_bank(20, hits=15).values()))
        assert m["by_family"]["HUMAN"]["n_anchor"] == 20
        assert m["by_family"]["HUMAN"]["anchor_rate"] == 0.75
        assert m["by_family"]["HUMAN"]["gold_rate"] is None
        assert m["by_family"]["HUMAN"]["gold_rate"] is None


class TestGateRules:
    def test_round_giống_hệt_thì_đạt(self):
        base = bank(40)
        result = _cmp(copy.deepcopy(base), base)
        assert result["passed"] is True
        assert result["regressions"] == [] and result["improvements"] == []

    def test_pha_truy_xuất_cải_thiện_recall_thì_đạt(self):
        base = retrieval_bank(40, hits=20)
        cand = retrieval_bank(40, hits=36)
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "retrieval_not_degraded"][0]
        assert rule["ok"] is True and "0.5->0.9" in rule["detail"]
        assert result["passed"] is True

    def test_recall_tệ_đi_bị_chặn_trên_đúng_mẫu_số(self):
        base = retrieval_bank(40, hits=30)
        cand = retrieval_bank(40, hits=20)
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "retrieval_not_degraded"][0]
        assert rule["ok"] is False
        assert result["passed"] is False

    def test_family_giảm_recall_bị_chặn_dù_không_đo_được_pass_rate(self):
        base = retrieval_bank(40, hits=36)
        cand = retrieval_bank(40, hits=24)
        result = _cmp(cand, base)
        fam = [c for c in result["checks"] if c["rule"].startswith("family_pass_rate")]
        assert any(c["rule"] == "family_pass_rate[NUMERIC]" and not c["ok"] for c in fam)

    def test_verdict_thiếu_has_gold_chunk_thì_cổng_từ_chối_mở(self):
        """Không đo được != ĐẠT. Verdict do verify.py cũ ghi phải bị chặn để chấm lại."""
        base = {k: {**v, "has_gold_chunk": None} for k, v in retrieval_bank(40).items()}
        for v in base.values():
            v.pop("has_gold_chunk")
        cand = copy.deepcopy(base)
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "retrieval_not_degraded"][0]
        assert rule["ok"] is False
        assert "has_gold_chunk" in rule["detail"]
        assert result["passed"] is False

    def test_thêm_câu_bịa_thì_vi_phạm(self):
        base, cand = bank(40), bank(40, fabricated=2)
        result = _cmp(cand, base)
        bad = [c for c in result["checks"] if c["rule"] == "fabrication_not_increased"]
        assert bad and not bad[0]["ok"]
        assert result["passed"] is False

    def test_trả_lời_bừa_câu_ngoại_phạm_vi_bị_chặn_ngay(self):
        base = bank(40)
        cand = dict(base)
        for key in list(cand)[:2]:
            cand[key] = row(key, "REFUSE_OOD", "FAIL_HALLUCINATED_ON_UNANSWERABLE")
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "no_new_hallucinated_refusal"][0]
        assert rule["ok"] is False and result["passed"] is False

    def test_bớt_câu_bịa_thì_đạt_và_ghi_nhận_cải_thiện(self):
        base, cand = bank(40, fabricated=6), bank(40, fabricated=0)
        result = _cmp(cand, base)
        assert result["passed"] is True
        assert len(result["improvements"]) == 6

    def test_pass_rate_rơi_quá_ngưỡng_bị_chặn(self, monkeypatch):
        monkeypatch.setenv("GATE_MAX_PASS_DROP", "0.02")
        base, cand = bank(40), bank(40, fabricated=5)
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "pass_rate_not_dropped"][0]
        assert rule["ok"] is False

    def test_từ_chối_oan_hàng_loạt_bị_chặn_dù_không_bịa(self, monkeypatch):
        """Đường tắt 'trả lời ít cho an toàn' — cổng phải từ chối."""
        monkeypatch.setenv("GATE_MAX_REFUSAL_RATE", "0.35")
        base, cand = bank(40), bank(40, refusals=30)
        result = _cmp(cand, base)
        rules = {c["rule"]: c["ok"] for c in result["checks"]}
        assert rules["refusal_rate_bounded"] is False
        assert rules["fabrication_not_increased"] is True  # không bịa nhưng vẫn trượt cổng

    def test_suy_giảm_một_family_bị_phát_hiện_dù_toàn_cục_đạt(self, monkeypatch):
        monkeypatch.setenv("GATE_MAX_FAMILY_DROP", "0.10")
        base = {**bank(30, family="NUMERIC"), **bank(20, family="CLOZE", fabricated=0)}
        cand = {**base, **{k: row(k, "CLOZE", "FAIL_RETRIEVAL", gold_in_top_k=False)
                           for k in [f"CLOZE-{i}" for i in range(8)]}}
        result = _cmp(cand, base)
        fam = [c for c in result["checks"] if c["rule"].startswith("family_pass_rate")]
        assert any(c["rule"] == "family_pass_rate[CLOZE]" and not c["ok"] for c in fam)
        assert result["passed"] is False

    def test_neo_human_giảm_tương_đối_bị_chặn(self, monkeypatch):
        monkeypatch.setenv("GATE_MAX_HUMAN_REL_DROP", "0.05")
        base = {**bank(40), **bank(20, family="HUMAN")}
        cand = dict(base)
        for i in range(4):  # HUMAN 20 câu, mất 4 = -20% tương đối
            key = f"HUMAN-{i}"
            cand[key] = row(key, "HUMAN", "FAIL_INCOMPLETE")
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "human_anchor_not_degraded"]
        assert rule and rule[0]["ok"] is False

    def test_truy_xuất_tệ_đi_bị_chặn_kể_cả_khi_pass_rate_giữ(self):
        base = bank(40)
        cand = {k: {**v, "gold_in_top_k": False} for k, v in base.items()}
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "retrieval_not_degraded"][0]
        assert rule["ok"] is False

    def test_chỉ_so_trên_item_chung(self):
        base = bank(40)
        cand = {**{k: base[k] for k in list(base)[:20]}, **bank(20, family="EXACT", fabricated=10)}
        result = _cmp(cand, base)
        assert result["n_common_items"] == 20
        assert result["passed"] is True  # 20 item EXACT mới không thuộc phạm vi so sánh

    def test_pha_truy_xuất_neo_human_mất_nguồn_bị_chặn(self, monkeypatch):
        monkeypatch.setenv("GATE_MAX_HUMAN_REL_DROP", "0.05")
        base = {**retrieval_bank(40), **human_bank(20, hits=16)}
        cand = {**retrieval_bank(40), **human_bank(20, hits=8)}
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "human_anchor_source_not_degraded"]
        assert rule and rule[0]["ok"] is False, "lever router không được phá neo bằng cách cắt nguồn"
        assert result["passed"] is False

    def test_neo_human_đo_được_ở_pha_rẻ_và_cải_thiện_thì_đạt(self):
        base = {**retrieval_bank(40), **human_bank(20, hits=10)}
        cand = {**retrieval_bank(40), **human_bank(20, hits=18)}
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "human_anchor_source_not_degraded"]
        assert rule and rule[0]["ok"] is True

    def test_thiếu_cờ_anchor_thì_cổng_từ_chối_so_neo(self):
        base = {**retrieval_bank(40), **human_bank(20, hits=16, with_anchor_flag=False)}
        cand = {**retrieval_bank(40), **human_bank(20, hits=16)}
        result = _cmp(cand, base)
        rule = [c for c in result["checks"] if c["rule"] == "human_anchor_source_not_degraded"]
        assert rule and rule[0]["ok"] is False, "verdict cũ không có cờ -> không được mở cổng"

    def test_bằng_chứng_cải_thiện_gồm_cả_item_vào_cửa_sổ_lại(self):
        """Cổng pha truy xuất phải liệt kê được item vừa vào cửa sổ (bản cũ in 0)."""
        base = retrieval_bank(40, hits=10)
        cand = retrieval_bank(40, hits=30)
        result = _cmp(cand, base)
        kinds = [e["kind"] for e in result["improvements"]]
        assert kinds.count("recall") == 20
        assert all(e["from"] == "gold@k=False" and e["to"] == "gold@k=True" for e in result["improvements"])

    def test_bằng_chứng_ghi_rõ_câu_nao_mất_đúng_nguồn(self):
        base = {**retrieval_bank(40), **human_bank(20, hits=18)}
        cand = {**retrieval_bank(40), **human_bank(20, hits=16)}
        result = _cmp(cand, base)
        lost = [e for e in result["regressions"] if e["kind"] == "anchor"]
        gained = [e for e in result["improvements"] if e["kind"] == "anchor"]
        assert len(lost) == 2 and not gained
        assert {e["family"] for e in lost} == {"HUMAN"}
        assert all(e["to"] == "nguon_trong_cua_so=False" for e in lost)


class TestLoadRows:
    def test_bỏ_dòng_không_có_id(self, tmp_path):
        p = tmp_path / "verdicts_full.jsonl"
        p.write_text(
            '{"id":"A","family":"EXACT","verdict":"PASS_CORRECT"}\n'
            '{"family":"EXACT","verdict":"PASS_CORRECT"}\n',
            encoding="utf-8",
        )
        rows = load_rows(tmp_path, "full")
        assert list(rows) == ["A"]


class TestRoundCompatibility:
    def test_cùng_cấu_hình_thì_không_mâu_thuẫn(self):
        cfg = {"testset": "data/loop/testset_v1.jsonl", "top_k": 6, "generator": "offline_qwen",
               "normalize_query": False, "enable_classifier": "0"}
        assert compatibility(dict(cfg), dict(cfg)) == []

    def test_top_k_khác_thì_phát_hiện(self):
        base = {"testset": "t.jsonl", "top_k": 6, "generator": "offline_qwen",
                "normalize_query": False, "enable_classifier": "0"}
        cand = dict(base, top_k=10)
        problems = compatibility(cand, base)
        assert any("top_k" in p for p in problems)

    def test_classifier_bật_ở_một_round_là_đòn_bẩy_nhưng_phải_khai_báo(self):
        base = {"testset": "t.jsonl", "top_k": 6, "generator": "offline_qwen",
                "normalize_query": False, "enable_classifier": "0"}
        cand = dict(base, enable_classifier="1")
        assert any("enable_classifier" in p for p in compatibility(cand, base))

    def test_thiếu_round_summary_thì_cảnh_báo_một_lần(self, tmp_path):
        assert round_settings(tmp_path, "full") == {}
        assert compatibility({}, {"top_k": 6}) == [
            "thiếu round_summary — không xác nhận được hai round chạy chung cấu hình"
        ]
        # Một round ghi testset, round kia không -> không xác nhận được cùng ngân hàng
        # câu hỏi, cổng phải báo chứ không giả định là giống nhau.
        problems = compatibility({"top_k": 6}, {"top_k": 6, "testset": "t.jsonl"})
        assert any("testset" in p for p in problems)

    def test_trọng_tài_khác_phiên_bản_thì_phát_hiện_và_hướng_dẫn_sửa(self):
        base = {"testset": "t.jsonl", "top_k": 6, "referee": "aaaaaaaaaaaa"}
        cand = dict(base, referee="bbbbbbbbbbbb")
        problems = compatibility(cand, base)
        assert any("trọng tài khác phiên bản" in p for p in problems)
        assert any("chấm lại" in p for p in problems)

    def test_round_cũ_không_ghi_chữ_ký_trọng_tài_cũng_là_mâu_thuẫn(self):
        base = {"testset": "t.jsonl", "top_k": 6}
        cand = dict(base, referee="bbbbbbbbbbbb")
        assert any("không_ghi" in p for p in compatibility(cand, base))

    def test_đọc_settings_từ_round_summary(self, tmp_path):
        import json

        (tmp_path / "round_summary_full.json").write_text(
            json.dumps({"settings": {"top_k": 6}}), encoding="utf-8"
        )
        assert round_settings(tmp_path, "full") == {"top_k": 6}

