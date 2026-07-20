"""RSSフィードからの記事収集(朝日新聞・毎日新聞など)。"""

from __future__ import annotations

import feedparser

from src.models.article import STATUS_OK, Article


def collect_rss(newspaper_config: dict, collected_at: str, date: str) -> list[Article]:
    """RSSフィードを取得しArticleのリストに変換する。

    ネットワーク/パースエラーは呼び出し元(main.py)がcatchできるよう、そのまま送出する。
    """
    rss_url = newspaper_config["rss_url"]
    feed = feedparser.parse(rss_url)

    if feed.bozo and not feed.entries:
        raise ValueError(f"RSSの取得/パースに失敗しました: {rss_url} ({feed.bozo_exception})")

    articles = []
    for entry in feed.entries:
        articles.append(
            Article(
                date=date,
                collected_at=collected_at,
                category=newspaper_config.get("category", ""),
                region=newspaper_config.get("region", ""),
                newspaper=newspaper_config["name"],
                headline=entry.get("title", ""),
                url=entry.get("link", ""),
                source_url=rss_url,
                status=STATUS_OK,
            )
        )
    return articles
