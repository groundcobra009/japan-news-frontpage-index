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


def test_build_discord_payload_picks_keyword_scored_headline_over_first():
    articles = [
        make_article(newspaper="朝日新聞", headline="猫の写真展が人気", url="https://example.com/1"),
        make_article(newspaper="朝日新聞", headline="台風接近で交通機関に影響拡大", url="https://example.com/2"),
        make_article(newspaper="毎日新聞", headline="台風の進路予想を発表", url="https://example.com/3"),
    ]
    payload = build_discord_payload(articles, date="2026-07-21", repo_readme_url="https://example.com/repo")
    description = payload["embeds"][0]["description"]

    assert "朝日新聞：台風接近で交通機関に影響拡大" in description
    assert "猫の写真展が人気" not in description


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


def test_build_discord_payload_puts_summary_first():
    articles = [make_article(newspaper="朝日新聞", headline="朝日の見出し")]
    payload = build_discord_payload(
        articles, date="2026-07-21", repo_readme_url="https://example.com/repo",
        summary="本日は台風の話題が中心でした。",
    )
    description = payload["embeds"][0]["description"]
    assert description.startswith("**本日のまとめ**")
    assert description.index("本日は台風") < description.index("朝日新聞：")


def test_build_discord_payload_keeps_summary_when_headlines_overflow():
    """見出しが上限を超えても、まとめが切り落とされないこと。"""
    articles = [make_article(newspaper=f"新聞{i}", headline="あ" * 200) for i in range(60)]
    summary = "ま" * 350
    payload = build_discord_payload(
        articles, date="2026-07-21", repo_readme_url="https://example.com/repo", summary=summary
    )
    description = payload["embeds"][0]["description"]
    assert summary in description
    assert len(description) <= 4096
    assert description.endswith("...")


def test_build_discord_payload_without_summary_has_no_header():
    articles = [make_article()]
    payload = build_discord_payload(articles, date="2026-07-21", repo_readme_url="https://example.com/repo")
    assert "**本日のまとめ**" not in payload["embeds"][0]["description"]


def test_build_discord_payload_excludes_other_media():
    articles = [
        make_article(newspaper="朝日新聞", headline="全国紙の見出し"),
        make_article(newspaper="共同通信", category="その他メディア", region="", headline="通信社の見出し"),
    ]
    payload = build_discord_payload(articles, date="2026-07-21", repo_readme_url="https://example.com/repo")
    description = payload["embeds"][0]["description"]
    assert "朝日新聞：全国紙の見出し" in description
    assert "共同通信" not in description


def test_build_discord_payload_title_includes_time_and_no_morning_edition():
    payload = build_discord_payload(
        [make_article()], date="2026-07-21", repo_readme_url="https://example.com/repo", time_label="19:00"
    )
    title = payload["embeds"][0]["title"]
    assert "19:00" in title
    # 1日3回配信なので「朝刊」表記はしない。
    assert "朝刊" not in title


def test_build_discord_payload_title_falls_back_without_time():
    payload = build_discord_payload(
        [make_article()], date="2026-07-21", repo_readme_url="https://example.com/repo"
    )
    title = payload["embeds"][0]["title"]
    assert "2026-07-21" in title
    assert "朝刊" not in title
