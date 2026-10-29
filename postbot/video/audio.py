"""A small original soundtrack, synthesised from scratch (no licensing questions).

A soft chord pad that changes with each scene, plus gentle 'whoosh' transitions and 'pop' accents
placed exactly on the visual events — sound is part of the timeline, not added afterwards.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

RATE = 32000
# chord progressions as semitone offsets from the root (I–V–vi–IV and friends)
PROGRESSIONS = [
    [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)],
    [(9, 12, 16), (5, 9, 12), (0, 4, 7), (7, 11, 14)],
    [(0, 4, 7), (5, 9, 12), (9, 12, 16), (7, 11, 14)],
]


def _freq(semitone: float, root: float) -> float:
    return root * 2 ** (semitone / 12)


def synth(duration: float, scene_starts: list[float], pops: list[float], seed: str, path: Path,
          volume: float = 0.5) -> Path:
    rng = random.Random(seed)
    n = int(duration * RATE)
    out = [0.0] * n
    root = rng.choice([110.0, 116.54, 123.47, 130.81, 146.83])  # A2..D3
    prog = rng.choice(PROGRESSIONS)
    bounds = list(scene_starts) + [duration]

    # --- pad: three detuned voices per chord, slow attack/release per scene
    for si in range(len(bounds) - 1):
        a, b = bounds[si], bounds[si + 1]
        chord = prog[si % len(prog)]
        i0, i1 = int(a * RATE), min(n, int((b + 0.35) * RATE))
        voices = []
        for st in chord:
            f = _freq(st, root * 2)
            voices.append((2 * math.pi * f / RATE, 2 * math.pi * f * 1.004 / RATE))
        seg = i1 - i0
        att, rel = int(0.45 * RATE), int(0.6 * RATE)
        for k in range(seg):
            env = min(1.0, k / att, (seg - k) / rel)
            idx = i0 + k
            s = 0.0
            for w1, w2 in voices:
                s += math.sin(w1 * idx) + 0.6 * math.sin(w2 * idx)
            out[idx] += s * env * 0.045

    # --- whoosh on scene changes: filtered noise swelling into the cut
    for at in scene_starts[1:]:
        i0 = int((at - 0.35) * RATE)
        length = int(0.5 * RATE)
        lp = 0.0
        for k in range(length):
            idx = i0 + k
            if 0 <= idx < n:
                lp += 0.08 * (rng.uniform(-1, 1) - lp)
                env = math.sin(math.pi * k / length) ** 2
                out[idx] += lp * env * 0.55

    # --- soft pop when a graphic lands
    for at in pops:
        i0 = int(at * RATE)
        length = int(0.09 * RATE)
        for k in range(length):
            idx = i0 + k
            if 0 <= idx < n:
                f = 880 - 420 * k / length
                out[idx] += math.sin(2 * math.pi * f * k / RATE) * math.exp(-k / (0.02 * RATE)) * 0.22

    # master fade in/out + normalise
    fade_in, fade_out = int(0.5 * RATE), int(1.4 * RATE)
    peak = max(1e-6, max(abs(x) for x in out))
    gain = volume / peak
    frames = bytearray()
    for i, x in enumerate(out):
        env = min(1.0, i / fade_in, (n - i) / fade_out)
        frames += struct.pack("<h", int(max(-1, min(1, x * gain * env)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return path
