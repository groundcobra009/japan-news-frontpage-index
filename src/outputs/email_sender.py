"""Gmail SMTPによるメール配信。"""

from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage

from src.models.article import STATUS_OK, Article

DEFAULT_TEMPLATE_PATH = "templates/email.template.html"
DEFAULT_REPO_URL = "https://github.com/groundcobra009/japan-news-frontpage-index"


def _group_by_newspaper_preserving_order(articles: list[Article]) -> dict[str, list[Article]]:
    grouped: dict[str, list[Article]] = {}
    for article in articles:
        grouped.setdefault(article.newspaper, []).append(article)
    return grouped


def _render_newspaper_section(newspaper: str, articles_for_paper: list[Article]) -> str:
    ok_articles = [a for a in articles_for_paper if a.status == STATUS_OK]
    name = html.escape(newspaper)
    if ok_articles:
        headline = html.escape(ok_articles[0].headline)
        url = html.escape(ok_articles[0].url)
        return f'<p><strong>{name}</strong><br>見出し：{headline}<br>URL：<a href="{url}">{url}</a></p>'
    return f"<p><strong>{name}</strong><br>（取得できませんでした）</p>"


def render_email_html(
    articles: list[Article],
    generated_at: str,
    repo_url: str = DEFAULT_REPO_URL,
    template_path: str = DEFAULT_TEMPLATE_PATH,
) -> str:
    """テンプレートのプレースホルダを当日データで置換したHTML文字列を返す(純粋関数)。"""
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    grouped = _group_by_newspaper_preserving_order(articles)
    sections = "\n".join(_render_newspaper_section(name, rows) for name, rows in grouped.items())

    rendered = template.replace("{{NEWSPAPER_SECTIONS}}", sections or "<p>(データがありません)</p>")
    rendered = rendered.replace("{{REPO_URL}}", repo_url)
    rendered = rendered.replace("{{GENERATED_AT}}", generated_at)
    return rendered


def send_email(
    subject: str,
    html_body: str,
    mail_to: str,
    mail_from: str,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
) -> None:
    """Gmail SMTP(SSL)でメールを送信する。呼び出し元main.pyでtry/exceptし、失敗しても他チャネルをブロックしない。"""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = mail_from
    message["To"] = mail_to
    message.set_content("このメールはHTML形式です。対応するメールクライアントでご覧ください。")
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL(smtp_host, int(smtp_port)) as smtp:
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)
