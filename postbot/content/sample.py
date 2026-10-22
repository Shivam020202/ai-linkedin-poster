"""Hand-written sample posts used by `preview`, `--offline` dry runs and tests (no AI needed)."""
from __future__ import annotations

import copy

CAROUSEL = {
    "format": "carousel",
    "topic": "The 8-point spacing system and why it speeds up decisions",
    "hook": "I stopped guessing spacing values the day I switched to an 8-point scale.",
    "post_text": (
        "I stopped guessing spacing values the day I switched to an 8-point scale.\n\n"
        "Before, every gap was a small decision. 13px here, 18px there.\n"
        "The screens looked fine on their own, but side by side they felt slightly off.\n\n"
        "Now I only reach for 8, 16, 24, 32, 48 and 64.\n\n"
        "A simple example from a settings screen:\n"
        "→ 8px between a label and its input\n"
        "→ 16px between fields in the same group\n"
        "→ 32px between groups\n\n"
        "That's it. The grouping explains itself, so I don't need divider lines.\n\n"
        "The real win isn't pixel perfection. It's speed.\n"
        "Fewer options means fewer debates in review, and developers can map the values "
        "straight to tokens.\n\n"
        "It also fixes the slow drift that happens on bigger files.\n"
        "When three designers each eyeball a gap, you get three slightly different gaps. "
        "With a scale, you get the same one.\n\n"
        "If 8 feels too coarse for small UI, use 4 for tight spots like icon padding. "
        "Just keep it on the scale.\n\n"
        "What spacing scale are you using right now?"
    ),
    "hashtags": ["#UIDesign", "#DesignSystems", "#ProductDesign", "#Figma"],
    "slides": [
        {"kind": "hook", "title": "Stop guessing spacing. Use an 8-point scale.",
         "body": "A small rule that makes every screen feel calmer", "visual": "none"},
        {"kind": "problem", "title": "Random gaps feel “off”",
         "body": "13px here, 18px there. Each screen looks fine alone, but the product never feels consistent.",
         "visual": "alignment"},
        {"kind": "tip", "title": "Pick a short scale",
         "body": "8, 16, 24, 32, 48, 64. Use 4 only for tight spots like icon padding.", "visual": "spacing"},
        {"kind": "tip", "title": "Snap layouts to the grid",
         "body": "Cards, padding and gaps all land on multiples of 8, so edges line up across screens.",
         "visual": "grid8"},
        {"kind": "do_dont", "title": "Group with space, not lines",
         "do": "8px label→input, 16px between fields, 32px between groups",
         "dont": "Same 16px everywhere plus a divider line between each group", "visual": "none"},
        {"kind": "tip", "title": "Size type on the same rhythm",
         "body": "Line heights of 24 and 32 keep text blocks sitting on the grid too.", "visual": "type_scale"},
        {"kind": "tip", "title": "Hand off tokens, not pixels",
         "body": "space-2 = 16px. Developers map the scale once and stop measuring your mockups.",
         "visual": "card"},
        {"kind": "recap", "title": "Recap", "items": [
            "Use 8, 16, 24, 32, 48, 64", "Group with space instead of lines",
            "Keep line heights on the grid", "Name the steps as tokens"], "visual": "none"},
        {"kind": "cta", "title": "Save this for your next layout",
         "body": "What spacing scale are you using right now?", "visual": "none"},
    ],
    "alt_text": ("A 9-slide carousel about using an 8-point spacing scale: examples of spacing values 8 to 64, "
                 "a card snapped to a grid, a do/don't comparison and a recap list."),
    "image_caption": "8-point spacing system, explained in 9 slides",
}

SINGLES = {
    "statement": {"kind": "statement", "title": "If everything is bold, nothing is.",
                  "body": "Hierarchy comes from contrast between elements, not from making each one louder.",
                  "visual": "hierarchy"},
    "do_dont": {"kind": "do_dont", "title": "Form labels",
                "do": "Put the label above the field so it stays visible while typing",
                "dont": "Use placeholder text as the only label", "visual": "form_field"},
    "before_after": {"kind": "before_after", "title": "One primary button per screen",
                     "before": "Three equally bold buttons fighting for attention",
                     "after": "One filled primary, one outlined secondary, one text link", "visual": "buttons"},
    "myth_reality": {"kind": "myth_reality", "title": "Accessible colour",
                     "myth": "Accessible colours have to look dull",
                     "reality": "You can keep a bright brand colour; check text contrast and darken only where text sits on it.",
                     "visual": "contrast"},
    "quote": {"kind": "quote", "title": "Your empty state is the first screen a new user really reads. Design it like one.",
              "body": "A note to myself after redoing an onboarding flow", "visual": "none"},
    "checklist": {"kind": "checklist", "title": "Before you hand off a screen",
                  "items": ["Every state designed: empty, loading, error", "Spacing uses the scale only",
                            "Text contrast passes AA (4.5:1)", "Touch targets are 44px or larger",
                            "Components named the same as in code"], "visual": "none"},
}


def sample_post(kind: str = "carousel") -> dict:
    if kind == "carousel":
        return copy.deepcopy(CAROUSEL)
    slide = SINGLES[kind]
    fmt = "quote" if kind == "quote" else "checklist" if kind == "checklist" else "single"
    post = copy.deepcopy(CAROUSEL)
    post.update(format=fmt, slides=[copy.deepcopy(slide)], topic=slide["title"],
                alt_text=f"A single card titled '{slide['title']}'.", image_caption=slide["title"])
    return post
