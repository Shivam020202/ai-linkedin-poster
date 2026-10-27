"""Hand-written sample posts used by `preview`, `--offline` dry runs and tests (no AI needed)."""
from __future__ import annotations

import copy

POST_TEXT = (
    "Horizontal scrolling tables on a phone are where good data goes to hide.\n\n"
    "Picture an orders table with seven columns: ID, date, customer, status, amount, payment, actions.\n"
    "On desktop it's fine. On a 375px screen it turns into a sideways scavenger hunt, and people lose track "
    "of which row they were reading.\n\n"
    "What works better for me is to stop treating it as a table at all.\n\n"
    "Each row becomes a card:\n"
    "→ The thing people scan for (order number) goes top-left in 16px semibold\n"
    "→ The status becomes a coloured chip top-right\n"
    "→ Two or three secondary values sit underneath with 12px labels\n"
    "→ Everything else moves behind a tap to expand\n\n"
    "The trick is deciding what deserves to be on the card. I ask: what would someone look for "
    "if they opened this screen with one hand while walking?\n\n"
    "Cards take more vertical space, and that's fine. Vertical scrolling is the one gesture everybody "
    "already does without thinking.\n\n"
    "Keep the table on desktop. Give phones their own layout.\n\n"
    "What's your go-to pattern when dense data meets a small screen?"
)

CAROUSEL = {
    "format": "carousel",
    "topic": "Making a dense data table readable on a phone",
    "hook": "Horizontal scrolling tables on a phone are where good data goes to hide.",
    "post_text": POST_TEXT,
    "hashtags": ["#UXDesign", "#MobileDesign", "#ProductDesign", "#UIDesign"],
    "slides": [
        {"kind": "cover", "title": "Your table doesn't fit. Stop forcing it.",
         "caption": "Dense data on small screens, rethought",
         "graphic": {"type": "compare", "left_label": "Scroll table", "right_label": "Stacked cards",
                     "left_screen": "table", "right_screen": "table_cards", "winner": "right", "title": "Orders"}},
        {"kind": "point", "title": "Lead with what people scan for",
         "graphic": {"type": "phone", "screen": "table_cards", "title": "Orders",
                     "items": ["Order #1042", "Order #1043", "Order #1044", "Order #1045"]}},
        {"kind": "point", "title": "Decide what earns a spot",
         "caption": "Everything else moves behind a tap",
         "graphic": {"type": "layers", "items": ["Hidden details", "Secondary values", "Status chip", "Order number"]}},
        {"kind": "point", "title": "Status as colour, not a column",
         "graphic": {"type": "components", "items": ["chip", "toggle", "progress", "avatars", "rating", "button"]}},
        {"kind": "point", "title": "From grid to stack in 4 moves",
         "graphic": {"type": "steps", "items": [{"icon": "search", "label": "Find the key"},
                                                {"icon": "layers", "label": "Group"},
                                                {"icon": "eye", "label": "Hide the rest"},
                                                {"icon": "check", "label": "Test one-handed"}]}},
        {"kind": "checklist", "title": "Before you ship it",
         "graphic": {"type": "checklist", "items": ["Primary value top-left", "Status is a coloured chip",
                                                    "Max 3 secondary values", "Details behind a tap"]}},
        {"kind": "cta", "title": "Save this for your next dashboard",
         "caption": "What's your go-to pattern for dense data?"},
    ],
    "alt_text": ("A 7-slide carousel showing a cramped phone table turning into stacked order cards, with an "
                 "exploded diagram of what goes on each card, UI components and a short checklist."),
    "image_caption": "Dense tables on phones, rethought as cards",
}

SINGLES = {
    "timeline": {"kind": "cover", "title": "Skeuomorphism deserves a comeback",
                 "caption": "Just not the leather stitching",
                 "graphic": {"type": "timeline", "items": [{"year": "2007", "label": "Skeuomorphic"},
                                                           {"year": "2013", "label": "Flat design"},
                                                           {"year": "2020", "label": "Neumorphism"},
                                                           {"year": "Now", "label": "Tactile depth"}]}},
    "browser": {"kind": "cover", "title": "Bento grids, without the puzzle",
                "graphic": {"type": "browser", "layout": "bento", "title": "Everything in one place",
                            "items": ["Fast", "Secure", "Collaborative", "Accessible", "Beautiful"]}},
    "palette": {"kind": "cover", "title": "One accent colour, used with intent",
                "graphic": {"type": "palette", "colors": [{"hex": "#FF6B4A", "name": "Accent"},
                                                          {"hex": "#7C3AED", "name": "Support"},
                                                          {"hex": "#111827", "name": "Ink"},
                                                          {"hex": "#F5F5F7", "name": "Paper"}]}},
    "spectrum": {"kind": "cover", "title": "Minimal isn't the same as empty",
                 "graphic": {"type": "spectrum", "left": "Bare", "right": "Busy", "marker": 40,
                             "marker_label": "Calm, not empty"}},
    "type": {"kind": "cover", "title": "Serif fonts belong in product UI too",
             "graphic": {"type": "type", "sample": "Ag", "style": "serif", "label": "Serif for headings"}},
    "stat": {"kind": "cover", "title": "The number every button should pass",
             "graphic": {"type": "stat", "value": "4.5:1", "label": "WCAG AA body text", "icon": "eye"}},
    "quote": {"kind": "quote", "title": "Your empty state is the first screen a new user really reads. Design it like one.",
              "caption": "A note to myself after redoing an onboarding flow",
              "graphic": {"type": "hero_icon", "icon": "sparkle", "items": ["heart", "chat", "star", "bolt"]}},
    "checklist": {"kind": "checklist", "title": "Before you hand off a screen",
                  "graphic": {"type": "checklist", "items": ["Empty, loading and error states", "Spacing on the scale",
                                                             "Text passes AA contrast", "Touch targets 44px+",
                                                             "Names match the code"]}},
}


def sample_post(kind: str = "carousel") -> dict:
    if kind == "carousel":
        return copy.deepcopy(CAROUSEL)
    slide = SINGLES[kind]
    fmt = "quote" if kind == "quote" else "checklist" if kind == "checklist" else "single"
    post = copy.deepcopy(CAROUSEL)
    post.update(format=fmt, slides=[copy.deepcopy(slide)], topic=slide["title"],
                alt_text=f"A designed card titled '{slide['title']}'.", image_caption=slide["title"])
    return post
