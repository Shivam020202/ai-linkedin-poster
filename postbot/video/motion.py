"""Time-based easing and closed-form springs.

Everything here is a pure function of t, so any frame can be rendered without the frames before it.
"""
from __future__ import annotations

import math


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out_cubic(x: float) -> float:
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_cubic(x: float) -> float:
    x = clamp01(x)
    return x ** 3


def ease_in_out(x: float) -> float:
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def spring(t: float, stiffness: float = 170.0, damping: float = 26.0, mass: float = 1.0) -> float:
    """Closed-form step response of a damped spring going 0 -> 1 (may overshoot slightly).

    Unlike a frame-by-frame simulation, this needs no previous state: spring(t) is exact for any t.
    """
    if t <= 0:
        return 0.0
    w0 = math.sqrt(stiffness / mass)
    zeta = damping / (2 * math.sqrt(stiffness * mass))
    if zeta < 1:
        wd = w0 * math.sqrt(1 - zeta * zeta)
        return 1 - math.exp(-zeta * w0 * t) * (math.cos(wd * t) + zeta * w0 / wd * math.sin(wd * t))
    return 1 - math.exp(-w0 * t) * (1 + w0 * t)  # critically damped (or over): no overshoot


def multi_spring(t: float, initial: float, changes: list[tuple[float, float]], **kw) -> float:
    """value(t) = initial + sum(delta * spring(t - time)) for a property whose target changes over time."""
    return initial + sum(delta * spring(t - at, **kw) for at, delta in changes)


def fade(t: float, start: float, length: float = 0.25) -> float:
    return clamp01((t - start) / length) if length > 0 else float(t >= start)
