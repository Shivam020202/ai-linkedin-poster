import json

from postbot.telegram.api import TelegramAPI, split_text
from postbot.telegram.listener import is_allowed, parse_times


def test_split_respects_limit_and_keeps_content():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 150 for i in range(12))
    chunks = split_text(text, 4000)
    assert len(chunks) > 1 and all(len(c) <= 4000 for c in chunks)
    assert "".join(chunks).replace(" ", "").replace("\n", "") == text.replace(" ", "").replace("\n", "")


def test_split_short_text_is_one_chunk():
    assert split_text("hello") == ["hello"]


def test_split_hard_cuts_unbroken_text():
    chunks = split_text("x" * 9000, 4000)
    assert [len(c) for c in chunks] == [4000, 4000, 1000]


def msg(chat, sender=None):
    return {"message": {"chat": {"id": chat}, "from": {"id": sender or chat}, "text": "/now"}}


def test_allow_list():
    assert is_allowed(msg(42), "42")
    assert not is_allowed(msg(43), "42")
    assert not is_allowed({"message": {}}, "42")
    cb = {"callback_query": {"from": {"id": 42}, "message": {"chat": {"id": 42}}}}
    assert is_allowed(cb, "42")
    cb["callback_query"]["from"]["id"] = 7
    assert not is_allowed(cb, "42")


def test_parse_times():
    assert parse_times("9:00, 18:30") == ["09:00", "18:30"]
    assert parse_times("25:00") is None
    assert parse_times("") is None


def test_flood_limit_is_retried(fake_tg, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    fake_tg.fail_next.append({"ok": False, "error_code": 429, "description": "Too Many Requests",
                              "parameters": {"retry_after": 3}})
    api = TelegramAPI("1:x", base_url=fake_tg.url)
    api.send_message(1, "hi")
    assert fake_tg.methods() == ["sendMessage", "sendMessage"]


def test_media_group_chunks_of_ten(fake_tg, tmp_path):
    from PIL import Image
    paths = []
    for i in range(12):
        p = tmp_path / f"{i}.png"
        Image.new("RGB", (10, 10)).save(p)
        paths.append(p)
    TelegramAPI("1:x", base_url=fake_tg.url).send_media_group(1, paths)
    assert fake_tg.methods() == ["sendMediaGroup", "sendMediaGroup"]
    assert len(json.loads(fake_tg.calls[0][1]["media"])) == 10
    assert len(fake_tg.calls[1][2]) == 2


def test_token_not_in_error(fake_tg):
    import pytest
    from postbot.telegram.api import TelegramError
    fake_tg.fail_next.append({"ok": False, "error_code": 400, "description": "Bad Request"})
    with pytest.raises(TelegramError) as exc:
        TelegramAPI("123456:SECRETSECRETSECRETSECRET", base_url=fake_tg.url).send_message(1, "x")
    assert "SECRET" not in str(exc.value)


def test_log_redaction(monkeypatch):
    from postbot.logutil import redact
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyFAKEKEY123456")
    line = "GET https://api.telegram.org/bot123456789:AAHfakefakefakefakefakefake/getMe key=AIzaSyFAKEKEY123456"
    out = redact(line)
    assert "AAHfake" not in out and "AIzaSyFAKEKEY123456" not in out
