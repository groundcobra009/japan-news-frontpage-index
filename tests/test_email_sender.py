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


def test_send_email_uses_smtp_ssl_and_logs_in(monkeypatch):
    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance
    mock_smtp_ssl = MagicMock(return_value=mock_smtp_instance)
    monkeypatch.setattr("smtplib.SMTP_SSL", mock_smtp_ssl)

    send_email(
        subject="件名",
        html_body="<p>本文</p>",
        mail_to="to@example.com",
        mail_from="from@example.com",
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        smtp_username="user",
        smtp_password="pass",
    )

    mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465)
    mock_smtp_instance.login.assert_called_once_with("user", "pass")
    assert mock_smtp_instance.send_message.called
    sent_message = mock_smtp_instance.send_message.call_args[0][0]
    assert sent_message["Subject"] == "件名"
    assert sent_message["To"] == "to@example.com"
