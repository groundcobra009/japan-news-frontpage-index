"""Discord Webhookによる配信。"""

from __future__ import annotations

import requests

from src.models.article import Article
from src.processors.keywords import build_extra_stopwords, build_keyword_pool, pick_representative_article

DISCORD_EMBED_DESCRIPTION_LIMIT = 4096
REQUEST_TIMEOUT_SECONDS = 10


def _group_by_newspaper_preserving_order(articles: list[Article]) -> dict[str, list[Article]]:
    grouped: dict[str, list[Article]] = {}
    for article in articles:
        grouped.setdefault(article.newspaper, []).append(article)
    return grouped


def _representative_line(
    newspaper: str,
    articles_for_paper: list[Article],
    keyword_pool: set[str],
    extra_stopwords: frozenset[str],
) -> str:
    best = pick_representative_article(articles_for_paper, keyword_pool, extra_stopwords)
    if best:
        return f"・{newspaper}：{best.headline}"
    return f"・{newspaper}：(取得できませんでした)"


def build_discord_payload(articles: list[Article], date: str, repo_readme_url: str) -> dict:
    """Discord webhook用のJSONペイロード(embed形式)を組み立てる。"""
    extra_stopwords = build_extra_stopwords(articles)
    keyword_pool = build_keyword_pool(articles, extra_stopwords)
    grouped = _group_by_newspaper_preserving_order(articles)
    lines = [_representative_line(name, rows, keyword_pool, extra_stopwords) for name, rows in grouped.items()]
    description = "\n".join(lines) or "(データがありません)"
    if len(description) > DISCORD_EMBED_DESCRIPTION_LIMIT:
        description = description[: DISCORD_EMBED_DESCRIPTION_LIMIT - 3] + "..."

    return {
        "embeds": [
            {
                "title": f"📰 {date}の朝刊インデックス",
                "description": description,
                "fields": [
                    {"name": "詳細", "value": repo_readme_url, "inline": False},
                ],
            }
        ]
    }


def send_discord(payload: dict, webhook_url: str) -> None:
    """呼び出し元main.pyでtry/exceptし、失敗しても他チャネルをブロックしない。"""
    response = requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
