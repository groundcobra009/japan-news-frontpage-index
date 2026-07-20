"""見出し・URLの正規化。"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from src.models.article import Article

TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAM_NAMES = {"ref", "rct"}


def normalize_headline(raw_text: str) -> str:
    """全角/半角統一、前後・連続空白の除去を行う。"""
    if not raw_text:
        return ""
    text = unicodedata.normalize("NFKC", raw_text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_url(raw_url: str, base_url: str = "") -> str:
    """相対URL→絶対URL変換、トラッキングクエリパラメータの除去を行う。"""
    if not raw_url:
        return ""
    absolute_url = urljoin(base_url, raw_url) if base_url else raw_url
    parts = urlsplit(absolute_url)

    kept_query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in TRACKING_PARAM_NAMES and not k.startswith(TRACKING_PARAM_PREFIXES)
    ]
    new_query = urlencode(kept_query)

    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, ""))


def normalize_article(article: Article) -> Article:
    """見出し・URLを正規化した新しいArticleを返す(元のarticleは変更しない)。"""
    return Article(
        date=article.date,
        collected_at=article.collected_at,
        category=article.category,
        region=article.region,
        newspaper=article.newspaper,
        headline=normalize_headline(article.headline),
        url=normalize_url(article.url, base_url=article.source_url),
        source_url=article.source_url,
        status=article.status,
        error_message=article.error_message,
    )
