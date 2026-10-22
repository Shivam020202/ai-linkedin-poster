import random
from datetime import date, timedelta

from postbot.content.topics import Topic, add_topic, load_topics, pick_case_study, pick_topic, remove_topic


def test_no_repeats_within_30_days_over_three_months():
    topics = load_topics()
    rng = random.Random(7)
    history = []
    start = date(2026, 1, 1)
    for d in range(90):
        day = start + timedelta(days=d)
        for _ in range(2):
            t = pick_topic(topics, history, day, rng, 30, 0.15)
            history.append({"topic": t.text, "category": t.category, "date": day.isoformat()})
    last_seen = {}
    for h in history:
        day = date.fromisoformat(h["date"])
        if h["topic"] in last_seen:
            assert (day - last_seen[h["topic"]]).days >= 30, h["topic"]
        last_seen[h["topic"]] = day


def test_falls_back_to_least_recently_used_when_bank_is_exhausted():
    topics = [Topic("A", "x", "X"), Topic("B", "x", "X")]
    history = [{"topic": "A", "date": "2026-01-01"}, {"topic": "B", "date": "2026-01-02"}]
    t = pick_topic(topics, history, date(2026, 1, 3), random.Random(1), 30, 0)
    assert t.text == "A"


def test_exclude_avoids_topic():
    topics = [Topic("A", "x", "X"), Topic("B", "x", "X")]
    for seed in range(10):
        assert pick_topic(topics, [], date(2026, 1, 1), random.Random(seed), exclude={"A"}).text == "B"


def test_add_and_remove_topic(tmp_path):
    path = tmp_path / "topics.yaml"
    path.write_text("# header\ncategories:\n  a:\n    label: A\n    topics: [One]\n", encoding="utf-8")
    assert add_topic("Two", path)
    assert not add_topic("two", path)  # duplicate, case-insensitive
    assert {t.text for t in load_topics(path)} == {"One", "Two"}
    assert remove_topic("One", path)
    assert [t.text for t in load_topics(path)] == ["Two"]
    assert path.read_text().startswith("# header")


def test_case_study_rotates_projects():
    portfolio = [{"name": "P1"}, {"name": "P2"}]
    history = [{"category": "portfolio", "project": "P1", "date": "2026-01-01", "angle": "case_study:x"}]
    project, focus = pick_case_study(portfolio, history)
    assert project["name"] == "P2" and focus
