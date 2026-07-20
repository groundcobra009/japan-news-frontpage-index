"""同一新聞社内での重複記事除去。

異なる新聞社が同じニュースを報じるのは意図した挙動(各紙の見出しの違いを見せるのが
本サービスの価値)のため、新聞社をまたいだ統合は行わない。
"""

from __future__ import annotations

from src.models.article import Article


def compute_dedup_key(article: Article) -> str:
    return article.dedup_key()


def deduplicate(articles: list[Article]) -> list[Article]:
    """同一新聞社内の重複を除去する(最初に出現したものを残し、順序を保持する)。"""
    seen: set[str] = set()
    result: list[Article] = []
    for article in articles:
        key = compute_dedup_key(article)
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result
