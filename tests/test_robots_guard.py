from urllib.robotparser import RobotFileParser

import pytest

from src.collectors import robots_guard
from src.collectors.robots_guard import RobotsDisallowedError


@pytest.fixture(autouse=True)
def clear_robots_cache():
    robots_guard._fetch_robots_parser.cache_clear()
    yield
    robots_guard._fetch_robots_parser.cache_clear()


def _fake_read_allow_all(self):
    self.parse(["User-agent: *", "Allow: /"])


def _fake_read_disallow_private(self):
    self.parse(["User-agent: *", "Disallow: /private"])


def _fake_read_raises(self):
    raise OSError("network error")


def test_is_allowed_true_when_robots_allows(monkeypatch):
    monkeypatch.setattr(RobotFileParser, "read", _fake_read_allow_all)
    assert (
        robots_guard.is_allowed(
            "https://example.com/page",
            "test-bot",
            "https://example.com/robots-allow.txt",
        )
        is True
    )


def test_is_allowed_false_when_disallowed(monkeypatch):
    monkeypatch.setattr(RobotFileParser, "read", _fake_read_disallow_private)
    assert (
        robots_guard.is_allowed(
            "https://example.com/private/page",
            "test-bot",
            "https://example.com/robots-disallow.txt",
        )
        is False
    )


def test_is_allowed_false_when_fetch_fails_failsafe(monkeypatch):
    monkeypatch.setattr(RobotFileParser, "read", _fake_read_raises)
    assert (
        robots_guard.is_allowed(
            "https://example.com/page",
            "test-bot",
            "https://example.com/robots-error.txt",
        )
        is False
    )


def test_is_allowed_derives_robots_url_from_target_url(monkeypatch):
    monkeypatch.setattr(RobotFileParser, "read", _fake_read_allow_all)
    assert robots_guard.is_allowed("https://derive-example.com/page", "test-bot") is True


def test_assert_allowed_raises_when_disallowed(monkeypatch):
    monkeypatch.setattr(RobotFileParser, "read", _fake_read_disallow_private)
    with pytest.raises(RobotsDisallowedError):
        robots_guard.assert_allowed(
            "https://example.com/private/page",
            "test-bot",
            "https://example.com/robots-disallow2.txt",
        )


def test_assert_allowed_does_not_raise_when_allowed(monkeypatch):
    monkeypatch.setattr(RobotFileParser, "read", _fake_read_allow_all)
    robots_guard.assert_allowed(
        "https://example.com/page",
        "test-bot",
        "https://example.com/robots-allow2.txt",
    )
