import random

import pytest

from postbot.images.textfit import fit_text, wrap
from postbot.images.fonts import load_font

WORDS = ("design spacing hierarchy typography contrast accessibility onboarding "
         "a an the of to components tokens supercalifragilisticexpialidocious").split()


@pytest.mark.parametrize("seed", range(25))
def test_fit_never_overflows(seed):
    rng = random.Random(seed)
    text = " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 120)))
    w, h = rng.randint(200, 900), rng.randint(60, 600)
    fit = fit_text(text, "inter", 700, w, h, 90, 20, 1.2)
    assert fit.height <= h or len(fit.lines) == 1
    for line in fit.lines:
        assert fit.font.getlength(line) <= w + 1


def test_shrinks_before_truncating():
    text = "Stop guessing spacing. Use an eight point scale."
    fit = fit_text(text, "inter", 800, 600, 400, 120, 30, 1.1)
    assert not fit.truncated and fit.size < 120


def test_truncates_with_ellipsis_when_impossible():
    fit = fit_text("word " * 400, "inter", 400, 300, 100, 40, 30, 1.2)
    assert fit.truncated and fit.lines[-1].endswith("…") and fit.height <= 100


def test_long_word_is_broken():
    font = load_font("inter", 400, 40)
    lines = wrap("x" * 200, font, 200)
    assert len(lines) > 1 and all(font.getlength(l) <= 200 for l in lines)
