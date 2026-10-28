"""Khóa chính sách (policy key) cho cache của tầng sinh — T7.

Vì sao cần: cache sinh văn bản (`_cache_key` trong `src/generator.py`) vốn chỉ băm
`{model, temperature, prompt_version, prompt}`. Nhưng hành vi của một lượt chạy còn phụ thuộc vào
**thể chế bên ngoài câu trả lời thô**:

- cứu câu từ chối oan (`ENABLE_ANSWER_RESCUE`, `RESCUE_MIN_SCORE`) — lượt cứu là một lần SINH nữa;
- guard chặn câu bịa (`ENABLE_ANSWER_GUARD`, `ANSWER_GUARD_MIN_SCORE`, `ANSWER_GUARD_MAX_UNSUPPORTED`);
- quyền từ chối ngoài (`ENABLE_DECOUPLED_REFUSAL`, bộ `DEC_*`);
- chọn câu bằng chứng (`ENABLE_EVIDENCE_SELECTION`, `EV_*`, `EVIDENCE_RERANKER`);
- guard chuẩn hóa câu hỏi (`NORMALIZE_SANITY_GUARD`, `NORMALIZE_MIN_CONTAINMENT`).

Nếu chỉ băm prompt, đổi `RESCUE_MIN_SCORE` 0,8 → 0,6 mà cache cũ vẫn trúng thì round sau sẽ "tái dùng
câu trả lời của thể chế cũ": phép đo lever trông như không có tác dụng, hoặc tệ hơn, hai cấu hình
khác nhau chia sẻ câu trả lời. Vì vậy khóa cache phải gồm **dấu vân tay của thể chế đang chạy**.

Nguyên tắc:
1. `policy_fingerprint()` **chỉ đọc**, không ghi đĩa, không gọi model. Cùng env/ngưỡng ⇒ cùng chuỗi.
2. Giá trị lấy từ **chính các hàm phân giải của module sở hữu** (import trễ để không vòng import),
   nên không có bảng mặc định thứ hai dễ lệch.
3. Không bao giờ chứa bí mật: registry chỉ gồm cờ/ngưỡng, và `policy_snapshot()` trả về giá trị đã
   phân giải dạng số/bool/chuỗi ngắn.
4. `POLICY_KEY_VERSION`: bump khi *bản thân* cách tính đổi (không phải khi đổi ngưỡng) — để cache cũ
   của mọi thể chế đều bị tách khỏi thể chế tính mới.

Lưu ý trung thực: đưa ngưỡng vào khóa làm **mất** một phần lợi ích cache khi chỉ đổi ngưỡng hậu xử lý
(những lượt đó buộc sinh lại). Đây là đánh đổi có chủ đích theo yêu cầu T7: thà tốn lượt hơn tái dùng
câu trả lời của thể chế khác.
"""

from __future__ import annotations

import hashlib
import json

POLICY_KEY_VERSION = "policy-v1"

# Version của *cách tính* token đưa vào khóa cache (khác `POLICY_KEY_VERSION` của ảnh chụp
# đầy đủ): bump khi payload token đổi cấu trúc.
CACHE_TOKEN_VERSION = "cache-policy-v1"

# Token của THỂ CHẾ MẶC ĐỊNH ĐÃ ĐĂNG KÝ (mọi biến chính sách không đặt). Đây là mốc so
# sánh: thể chế trùng mốc thì KHÔNG thêm trường `policy` vào khóa cache — giữ nguyên khóa
# cũ từng byte (bất biến #2: cờ TẮT = hành vi cũ, và cache 351+ entry còn dùng được).
# Test `test_policy_cache_token_default_matches_cleared_env` tính lại dưới env rỗng và
# đối chiếu; đổi default của module sở hữu sẽ làm test đỏ → phải đăng ký lại token này.
DEFAULT_CACHE_TOKEN = "d0b4c6a65f83"  # sinh bằng lệnh trong docstring test cùng tên


def _hash12(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def policy_snapshot() -> dict:
    """Ảnh chụp THỂ CHẾ đang chạy (chỉ cờ + ngưỡng), dùng để băm thành khóa cache."""
    # Import trễ: tránh vòng import generator → cache_policy → generator.
    from src import answer_guard; from src.generation import refusal_policy
    from src.generation import evidence_selection; from src.core import query_normalizer
    from src import generator as generator_module

    guard_min, guard_max = answer_guard.refusal_thresholds()
    ev_min, ev_max = evidence_selection.sentence_budget()
    dec = refusal_policy.thresholds()

    return {
        "policy_key_version": POLICY_KEY_VERSION,
        "prompt_version": generator_module.effective_prompt_version(),
        "rescue": {
            "enabled": generator_module.answer_rescue_enabled(),
            "min_score": round(generator_module.rescue_min_score(), 6),
        },
        "guard": {
            "enabled": answer_guard.answer_guard_enabled(),
            "min_score": round(float(guard_min), 6),
            "max_unsupported": int(guard_max),
        },
        "decoupled_refusal": {
            "enabled": refusal_policy.decoupled_refusal_enabled(),
            "min_entity_coverage": round(float(dec["min_entity_coverage"]), 6),
            "min_token_overlap": round(float(dec["min_token_overlap"]), 6),
            "min_rrf_norm": round(float(dec["min_rrf_norm"]), 6),
            "min_grounding": round(float(dec["min_grounding"]), 6),
            "max_unsupported": int(dec["max_unsupported"]),
        },
        "evidence_selection": {
            "enabled": evidence_selection.evidence_selection_enabled(),
            "min_sentences": int(ev_min),
            "max_sentences": int(ev_max),
            "min_keyword_hits": int(evidence_selection.min_keyword_hits()),
            "reranker": (evidence_selection.reranker_status() or {}).get("requested"),
        },
        "normalize_sanity": {
            "enabled": query_normalizer.normalize_sanity_guard_enabled(),
            "min_containment": round(float(query_normalizer.normalize_min_containment()), 6),
        },
    }


def policy_fingerprint(snapshot: dict | None = None) -> str:
    """12 ký tự hex đại diện cho TOÀN BỘ thể chế hiện tại (log/manifest/test)."""
    payload = snapshot if snapshot is not None else policy_snapshot()
    return _hash12(payload)


def policy_cache_token(snapshot: dict | None = None) -> str:
    """Token đưa vào khóa cache: chỉ những gì **chưa** được `prompt_version` mã hóa.

    Loại khỏi token:
    - `prompt_version`: đã là một trường riêng của khóa cache;
    - `decoupled_refusal.enabled` + `policy_key_version`: bật/tắt cờ T3 đã làm đổi
      `prompt_version` ("v1.3" ↔ "v2.0-extract-only"), nên nhắc lại là thừa.

    Giữ lại: mọi **ngưỡng** cứu/guard/từ chối/chọn câu bằng chứng/chuẩn hóa. Đây đúng là
    phần "đổi ngưỡng mà cache cũ vẫn trúng" mà T7 muốn chặn.
    """
    snap = snapshot if snapshot is not None else policy_snapshot()
    dec = snap["decoupled_refusal"]
    return _hash12(
        {
            "cache_token_version": CACHE_TOKEN_VERSION,
            "rescue": snap["rescue"],
            "guard": snap["guard"],
            "decoupled_refusal": {
                "min_entity_coverage": dec["min_entity_coverage"],
                "min_token_overlap": dec["min_token_overlap"],
                "min_rrf_norm": dec["min_rrf_norm"],
                "min_grounding": dec["min_grounding"],
                "max_unsupported": dec["max_unsupported"],
            },
            "evidence_selection": snap["evidence_selection"],
            "normalize_sanity": snap["normalize_sanity"],
        }
    )


def cache_policy_deviation(snapshot: dict | None = None) -> str | None:
    """`None` nếu thể chế trùng mặc định đã đăng ký, ngược lại là token lệch.

    Generator dùng hàm này để quyết định có thêm trường `policy` vào khóa cache hay không.
    """
    token = policy_cache_token(snapshot)
    return None if token == DEFAULT_CACHE_TOKEN else token
