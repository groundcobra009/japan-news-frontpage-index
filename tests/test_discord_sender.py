from unittest.mock import MagicMock

from src.models.article import STATUS_OK, STATUS_SKIPPED, Article
from src.outputs.discord_sender import build_discord_payload, send_discord


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


def test_build_discord_payload_includes_representative_headline():
    articles = [make_article(newspaper="朝日新聞", headline="朝日の見出し")]
    payload = build_discord_payload(articles, date="2026-07-21", repo_readme_url="https://example.com/repo")

    embed = payload["embeds"][0]
    assert "2026-07-21" in embed["title"]
    assert "朝日新聞：朝日の見出し" in embed["description"]
    assert embed["fields"][0]["value"] == "https://example.com/repo"


def test_build_discord_payload_shows_placeholder_when_not_ok():
    articles = [make_article(newspaper="読売新聞", status=STATUS_SKIPPED, headline="", url="")]
    payload = build_discord_payload(articles, date="2026-07-21", repo_readme_url="https://example.com/repo")
    assert "読売新聞：(取得できませんでした)" in payload["embeds"][0]["description"]


def test_build_discord_payload_truncates_long_description():
    articles = [make_article(newspaper=f"新聞{i}", headline="あ" * 200) for i in range(30)]
    payload = build_discord_payload(articles, date="2026-07-21", repo_readme_url="https://example.com/repo")
    assert len(payload["embeds"][0]["description"]) <= 4096


def test_send_discord_posts_payload_and_raises_for_http_error(monkeypatch):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = None
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("requests.post", mock_post)

    send_discord({"embeds": []}, webhook_url="https://discord.example/webhook")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://discord.example/webhook"
    assert kwargs["json"] == {"embeds": []}
    mock_response.raise_for_status.assert_called_once()
