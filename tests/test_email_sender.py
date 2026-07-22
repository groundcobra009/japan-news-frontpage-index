from unittest.mock import MagicMock

from src.models.article import STATUS_OK, STATUS_SKIPPED, Article
from src.outputs.email_sender import render_email_html, send_email

TEMPLATE = """<html><body>
{{NEWSPAPER_SECTIONS}}
{{REPO_URL}}
{{GENERATED_AT}}
</body></html>
"""


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


def test_render_email_html_includes_headline_and_url(tmp_path):
    template_path = tmp_path / "email.template.html"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    articles = [make_article(newspaper="朝日新聞", headline="朝日の見出し", url="https://asahi.example/1")]
    rendered = render_email_html(
        articles, generated_at="2026年7月21日 7:05", repo_url="https://example.com/repo", template_path=str(template_path)
    )

    assert "朝日の見出し" in rendered
    assert "https://asahi.example/1" in rendered
    assert "https://example.com/repo" in rendered
    assert "2026年7月21日 7:05" in rendered
    assert "{{" not in rendered


def test_render_email_html_shows_placeholder_when_not_ok(tmp_path):
    template_path = tmp_path / "email.template.html"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    articles = [make_article(newspaper="読売新聞", status=STATUS_SKIPPED, headline="", url="")]
    rendered = render_email_html(articles, generated_at="x", template_path=str(template_path))

    assert "読売新聞" in rendered
    assert "取得できませんでした" in rendered


def test_render_email_html_escapes_headline(tmp_path):
    template_path = tmp_path / "email.template.html"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    articles = [make_article(headline="<script>alert(1)</script>")]
    rendered = render_email_html(articles, generated_at="x", template_path=str(template_path))

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_send_email_posts_to_resend_api(monkeypatch):
    mock_response = MagicMock()
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("requests.post", mock_post)

    send_email(
        subject="件名",
        html_body="<p>本文</p>",
        mail_to="to@example.com",
        mail_from="from@example.com",
        api_key="re_test_key",
    )

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.resend.com/emails"
    assert kwargs["json"] == {
        "from": "from@example.com",
        "to": ["to@example.com"],
        "subject": "件名",
        "html": "<p>本文</p>",
    }
    assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
    mock_response.raise_for_status.assert_called_once()
