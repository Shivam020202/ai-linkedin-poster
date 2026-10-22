import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from postbot.config import DEFAULTS, deep_merge  # noqa: E402
from tests.fake_telegram import FakeTelegram  # noqa: E402


@pytest.fixture
def cfg():
    return deep_merge(DEFAULTS, {"profile": {"name": "Test Person", "handle": "@test"}})


@pytest.fixture
def fake_tg():
    fake = FakeTelegram()
    yield fake
    fake.close()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point output/ and data/ at a temp dir."""
    import postbot.pipeline as pipeline
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    from postbot.storage import Store
    return Store(tmp_path / "data")
