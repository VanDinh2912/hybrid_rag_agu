# -*- coding: utf-8 -*-
"""T6 — tiện ích số học cho báo cáo: CI tỉ lệ + điểm có trọng số.

Vì sao tách riêng: cùng một con số "7/10 giúp được" phải được tính bằng ĐÚNG một công
thức ở mọi chỗ trong báo cáo. Hàm ở đây thuần, không đọc đĩa, không gọi model, để test
được bằng ví dụ tính tay.

* `wilson_ci(k, n)`: khoảng tin cậy Wilson 95% cho tỉ lệ nhị thức — không suy biến ở
  0/n và n/n (bootstrap percentile thì suy biến, xem `bootstrap_rate_ci`).
* `bootstrap_rate_ci(k, n, seed=None)`: bootstrap percentile 95% trên đúng k biến cố
  trong n quan sát; seed cố định để tái lập.
* `weighted_score(scores, weights)`: tổng có trọng số; ASSERT tổng trọng số = 1,0
  (sai lệch quá `tol` => ValueError, không âm thầm chia lại).
"""

from __future__ import annotations

import math
import random

Z95 = 1.959963984540054  # z hai phía cho 95%


def _check_counts(k: int, n: int) -> None:
    if not isinstance(k, int) or not isinstance(n, int):
        raise ValueError(f"k và n phải là số nguyên (nhận k={k!r}, n={n!r})")
    if n <= 0:
        raise ValueError(f"n phải > 0 (nhận n={n})")
    if k < 0 or k > n:
        raise ValueError(f"k phải trong [0, n] (nhận k={k}, n={n})")


def wilson_ci(k: int, n: int, z: float = Z95) -> list[float]:
    """Wilson score interval 95% (mặc định), kẹp trong [0, 1]."""
    _check_counts(k, n)
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    low = max(0.0, center - half)
    high = min(1.0, center + half)
    return [round(low, 4), round(high, 4)]


def bootstrap_rate_ci(k: int, n: int, seed: int | None = None, reps: int = 10000) -> list[float]:
    """Bootstrap percentile 95% cho tỉ lệ k/n. Suy biến đúng: 0/n -> [0, 0], n/n -> [1, 1]."""
    _check_counts(k, n)
    if reps <= 0:
        raise ValueError(f"reps phải > 0 (nhận {reps})")
    rng = random.Random(seed)
    values = [1] * k + [0] * (n - k)
    means: list[float] = []
    for _ in range(reps):
        total = sum(values[rng.randrange(n)] for _ in range(n))
        means.append(total / n)
    means.sort()
    last = len(means) - 1
    pos = lambda q: means[min(last, max(0, int(q * len(means))))]  # noqa: E731
    low = max(0.0, pos(0.025))
    high = min(1.0, pos(0.975))
    return [round(low, 4), round(high, 4)]


def rate_with_ci(k: int, n: int, seed: int | None = 20261024, reps: int = 10000) -> dict:
    """Gói cả điểm ước lượng + hai loại CI để báo cáo không phải tự tính tay."""
    _check_counts(k, n)
    return {
        "k": k,
        "n": n,
        "rate": round(k / n, 4),
        "wilson95": wilson_ci(k, n),
        "bootstrap95": bootstrap_rate_ci(k, n, seed=seed, reps=reps),
    }


def _total(weights) -> float:
    values = list(weights.values()) if isinstance(weights, dict) else list(weights)
    return math.fsum(float(w) for w in values)


def weighted_score(scores, weights, tol: float = 1e-9) -> float:
    """Tổng có trọng số. Tổng trọng số PHẢI bằng 1,0 (sai lệch > tol => ValueError).

    Nhận dict (khuyến nghị: tên chiều) hoặc list; nếu là dict thì hai bên phải cùng khoá.
    """
    if isinstance(scores, dict) or isinstance(weights, dict):
        if not isinstance(scores, dict) or not isinstance(weights, dict):
            raise ValueError("scores và weights phải CÙNG là dict hoặc CÙNG là list")
        if set(scores) != set(weights):
            raise ValueError(
                "khoá scores/weights không khớp: "
                f"thiếu ở weights={sorted(set(scores) - set(weights))}, "
                f"thừa ở weights={sorted(set(weights) - set(scores))}"
            )
        pairs = [(float(scores[key]), float(weights[key])) for key in scores]
    else:
        if len(scores) != len(weights):
            raise ValueError(f"số điểm ({len(scores)}) khác số trọng số ({len(weights)})")
        pairs = [(float(s), float(w)) for s, w in zip(scores, weights)]

    total = math.fsum(w for _, w in pairs)
    if abs(total - 1.0) > tol:
        raise ValueError(f"tổng trọng số phải bằng 1,0 (nhận {total!r}, lệch {total - 1.0:+.6f})")
    return math.fsum(s * w for s, w in pairs)
