import pytest

from postbot.images.contrast import contrast_ratio, ensure_contrast, hex_to_rgb
from postbot.images.themes import THEME_NAMES, build_theme, get_theme, theme_passes


def test_known_ratios():
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21, abs=0.01)
    assert contrast_ratio(hex_to_rgb("#777777"), (255, 255, 255)) == pytest.approx(4.48, abs=0.01)
    assert contrast_ratio((10, 10, 10), (10, 10, 10)) == pytest.approx(1)


@pytest.mark.parametrize("fg,bg", [("#999999", "#FFFFFF"), ("#F59E0B", "#FFFFFF"), ("#4F46E5", "#0F172A"),
                                   ("#FFFFFF", "#FFEE00"), ("#808080", "#7F7F7F")])
def test_ensure_contrast_reaches_aa(fg, bg):
    fixed = ensure_contrast(hex_to_rgb(fg), hex_to_rgb(bg), 4.5)
    assert contrast_ratio(fixed, hex_to_rgb(bg)) >= 4.5


@pytest.mark.parametrize("primary,secondary", [("#4F46E5", "#F59E0B"), ("#FFEE00", "#AAAAAA"),
                                               ("#22D3EE", "#FFFFFF"), ("#111827", "#0F172A")])
@pytest.mark.parametrize("name", THEME_NAMES)
def test_every_theme_passes_for_any_brand(primary, secondary, name):
    brand = {"primary": primary, "secondary": secondary, "dark": "#0F172A", "light": "#F8FAFC"}
    assert theme_passes(build_theme(name, brand))
    assert theme_passes(get_theme(name, brand))


@pytest.mark.parametrize("primary,secondary", [("#111827", "#FF6B4A"), ("#4F46E5", "#F59E0B"),
                                               ("#6A994E", "#53599A"), ("#FFEE00", "#AAAAAA")])
@pytest.mark.parametrize("name", ["gradient", "glass", "tiles", "skeuo", "aurora", "editorial", "brutal", "noir",
                                  "blueprint", "clay"])
def test_painted_backgrounds_pass_on_real_pixels(cfg, primary, secondary, name):
    """Text colours are checked against the actual painted background, not an average colour."""
    from postbot.images.render import Renderer
    from postbot.images.styles import _samples, min_contrast
    cfg["brand"].update(primary=primary, secondary=secondary)
    r = Renderer(cfg, name)
    samples = _samples(r.background, (r.M, r.M, r.W - r.M, r.H - r.M))
    for color in (r.theme.fg, r.theme.body, r.theme.muted):
        assert min_contrast(color, samples) >= 4.5
    assert min_contrast(r.theme.accent, samples) >= 3.0
