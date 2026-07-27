from unittest.mock import MagicMock

from src.models.article import STATUS_ERROR, STATUS_OK, STATUS_SKIPPED, Article
from src.outputs.issue_notifier import (
    add_issue_comment,
    build_failure_issue,
    create_github_issue,
    find_open_issue_by_title,
    get_error_newspapers,
    should_notify,
)


def make_article(**overrides) -> Article:
    defaults = dict(
        date="2026-07-21",
        collected_at="2026-07-21T07:05:00+09:00",
        category="全国紙",
        region="全国",
        newspaper="朝日新聞",
        headline="見出し",
        url="https://example.com/1",
        source_url="https://example.com/",
        status=STATUS_OK,
    )
    defaults.update(overrides)
    return Article(**defaults)


def test_get_error_newspapers_only_includes_error_status():
    articles = [
        make_article(newspaper="朝日新聞", status=STATUS_OK),
        make_article(newspaper="読売新聞", status=STATUS_SKIPPED, headline="", url=""),
        make_article(newspaper="毎日新聞", status=STATUS_ERROR, headline="", url="", error_message="timeout"),
    ]
    assert get_error_newspapers(articles) == ["毎日新聞"]


def test_should_notify_false_when_no_errors():
    articles = [make_article(status=STATUS_OK), make_article(newspaper="読売新聞", status=STATUS_SKIPPED)]
    assert should_notify(articles) is False


def test_should_notify_true_when_error_meets_threshold():
    articles = [make_article(newspaper="毎日新聞", status=STATUS_ERROR, error_message="timeout")]
    assert should_notify(articles, threshold=1) is True


def test_should_notify_false_when_below_threshold():
    articles = [make_article(newspaper="毎日新聞", status=STATUS_ERROR, error_message="timeout")]
    assert should_notify(articles, threshold=2) is False


def test_build_failure_issue_includes_error_message():
    articles = [
        make_article(newspaper="毎日新聞", status=STATUS_ERROR, headline="", url="", error_message="network timeout")
    ]
    title, body = build_failure_issue(articles, date="2026-07-21")
    assert "2026-07-21" in title
    assert "毎日新聞" in body
    assert "network timeout" in body


def test_create_github_issue_posts_expected_payload(monkeypatch):
    mock_response = MagicMock()
    mock_response.json.return_value = {"number": 42}
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("requests.post", mock_post)

    result = create_github_issue(
        title="件名", body="本文", repo="groundcobra009/japan-news-frontpage-index", token="tok", labels=["bug"]
    )

    assert result == {"number": 42}
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.github.com/repos/groundcobra009/japan-news-frontpage-index/issues"
    assert kwargs["json"] == {"title": "件名", "body": "本文", "labels": ["bug"]}
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    mock_response.raise_for_status.assert_called_once()


def test_find_open_issue_by_title_returns_matching_issue(monkeypatch):
    response = MagicMock()
    response.json.return_value = [
        {"number": 1, "title": "別のIssue"},
        {"number": 7, "title": "【japan-news-frontpage-index】取得失敗通知: 2026-07-21"},
    ]
    monkeypatch.setattr("requests.get", MagicMock(return_value=response))

    found = find_open_issue_by_title(
        "【japan-news-frontpage-index】取得失敗通知: 2026-07-21", "owner/repo", "token"
    )
    assert found["number"] == 7


def test_find_open_issue_by_title_ignores_pull_requests(monkeypatch):
    response = MagicMock()
    response.json.return_value = [{"number": 3, "title": "同じ題名", "pull_request": {"url": "x"}}]
    monkeypatch.setattr("requests.get", MagicMock(return_value=response))

    assert find_open_issue_by_title("同じ題名", "owner/repo", "token") is None


def test_find_open_issue_by_title_returns_none_when_absent(monkeypatch):
    response = MagicMock()
    response.json.return_value = []
    monkeypatch.setattr("requests.get", MagicMock(return_value=response))

    assert find_open_issue_by_title("題名", "owner/repo", "token") is None


def test_add_issue_comment_posts_to_comments_endpoint(monkeypatch):
    response = MagicMock()
    post = MagicMock(return_value=response)
    monkeypatch.setattr("requests.post", post)

    add_issue_comment(7, "本文", "owner/repo", "token")

    args, kwargs = post.call_args
    assert args[0] == "https://api.github.com/repos/owner/repo/issues/7/comments"
    assert kwargs["json"] == {"body": "本文"}
    response.raise_for_status.assert_called_once()
