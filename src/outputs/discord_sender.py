"""Discord Webhookによる配信。"""

from __future__ import annotations

import requests

from src.models.article import NEWSPAPER_CATEGORIES, Article
from src.processors.keywords import build_extra_stopwords, build_keyword_pool, pick_representative_article

DISCORD_EMBED_DESCRIPTION_LIMIT = 4096
REQUEST_TIMEOUT_SECONDS = 10

# 太字記法を使えるのは、summarizer.sanitize_summary が本文から * を除去しており
# まとめ側から装飾を注入できないため。
SUMMARY_HEADER = "**本日のまとめ**\n"


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


def build_discord_payload(
    articles: list[Article], date: str, repo_readme_url: str, summary: str = ""
) -> dict:
    """Discord webhook用のJSONペイロード(embed形式)を組み立てる。"""
    extra_stopwords = build_extra_stopwords(articles)
    keyword_pool = build_keyword_pool(articles, extra_stopwords)
    # アグリゲーター経由の「その他メディア」は紙別の行には並べない。
    grouped = _group_by_newspaper_preserving_order(
        [a for a in articles if a.category in NEWSPAPER_CATEGORIES]
    )
    lines = [_representative_line(name, rows, keyword_pool, extra_stopwords) for name, rows in grouped.items()]
    headline_block = "\n".join(lines) or "(データがありません)"

    # まとめの領域を先に確保し、切り詰めは見出し側だけに効かせる。
    # (単純に全体をスライスすると、将来まとめを末尾に置いた瞬間に無言で消える)
    summary_block = f"{SUMMARY_HEADER}{summary.strip()}\n\n" if summary.strip() else ""
    available = max(DISCORD_EMBED_DESCRIPTION_LIMIT - len(summary_block), 0)
    if len(headline_block) > available:
        headline_block = headline_block[: max(available - 3, 0)] + "..." if available >= 3 else ""

    description = (summary_block + headline_block)[:DISCORD_EMBED_DESCRIPTION_LIMIT]

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
