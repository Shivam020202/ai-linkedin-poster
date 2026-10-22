import json

import pytest

from postbot.content.generator import Plan, generate_content
from postbot.content.sample import sample_post
from postbot.content.schema import KINDS, ValidationError, normalize, parse_json, validate
from postbot.content.topics import Topic


class ScriptedChain:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def generate(self, system, user):
        self.prompts.append(user)
        return self.responses.pop(0)


def plan(fmt="carousel"):
    return Plan(fmt, "tips", Topic("Spacing", "ui_fundamentals", "UI design fundamentals"), "Direct")


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! Here it is: {"a": 2} Hope it helps') == {"a": 2}
    with pytest.raises(ValidationError):
        parse_json("no json here")
    with pytest.raises(ValidationError):
        parse_json('{"a": ')


def test_sample_post_is_valid():
    hard, soft = validate(sample_post(), "carousel")
    assert hard == [] and soft == []


def test_wrong_slide_count_is_hard_error():
    data = sample_post()
    data["slides"] = data["slides"][:3]
    hard, _ = validate(data, "carousel")
    assert any("7–9 slides" in e for e in hard)


def test_soft_errors_detect_cliches_stats_and_emoji():
    data = sample_post()
    data["post_text"] += "\nStudies show 73% of users love it. A real game-changer 🚀🔥✨"
    _, soft = validate(data, "carousel")
    text = " ".join(soft)
    assert "game-changer" in text and "emoji" in text and "statistic" in text


def test_retry_once_on_malformed_json_then_succeeds(cfg):
    chain = ScriptedChain("{oops", json.dumps(sample_post()))
    data = generate_content(chain, cfg, plan(), [])
    assert len(chain.prompts) == 2
    assert "PREVIOUS ANSWER HAD PROBLEMS" in chain.prompts[1]
    assert data["format"] == "carousel" and len(data["slides"]) == 9


def test_gives_up_after_second_malformed_answer(cfg):
    chain = ScriptedChain("{oops", "still not json")
    with pytest.raises(ValidationError):
        generate_content(chain, cfg, plan(), [])


def test_soft_issues_after_retry_are_normalised(cfg):
    bad = sample_post()
    bad["slides"][2]["body"] = "word " * 100          # way over the limit
    bad["post_text"] += "\n\n#Extra #Tags"
    chain = ScriptedChain(json.dumps(bad), json.dumps(bad))
    data = generate_content(chain, cfg, plan(), [])
    assert len(data["slides"][2]["body"]) <= KINDS["tip"]["body"]
    assert "#Extra" not in data["post_text"]
    assert 3 <= len(data["hashtags"]) <= 4


def test_normalize_limits_emoji_and_strips_slide_emoji():
    data = sample_post("quote")
    data["post_text"] = "Hook 🎯\n\nBody 🚀 more 🔥 text ✨"
    data["slides"][0]["title"] = "Design 🎨 matters"
    out = normalize(data, "quote", ["#UX", "#UI", "#Design"])
    assert out["post_text"].count("🔥") == 0 and out["post_text"].count("✨") == 0
    assert out["slides"][0]["title"] == "Design matters"
