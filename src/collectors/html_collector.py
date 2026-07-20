"""トップページの軽量HTMLスクレイピングによる記事収集(産経新聞・東京新聞・中日新聞など)。

必ず robots_guard 経由でアクセス許可を確認してから取得する。CSSセレクタはサイト
構造の変更で壊れやすいため、記事リンクの正規表現パターン(article_link_pattern)を
config側で管理し、パターンに一致する<a>タグのテキストを見出しとして扱う。
"""

from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.collectors import robots_guard
from src.models.article import STATUS_OK, Article

DEFAULT_MAX_ITEMS = 20
REQUEST_TIMEOUT_SECONDS = 10


def _default_fetch_html(url: str, user_agent: str) -> str:
    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def collect_html(
    newspaper_config: dict,
    collected_at: str,
    date: str,
    fetch_html=None,
) -> list[Article]:
    """トップページを取得し、article_link_patternに一致する<a>タグを見出しとして返す。

    fetch_html は (url, user_agent) -> html文字列 の差し替え用フック(テスト用)。
    robots.txtでDisallowされている場合は robots_guard.RobotsDisallowedError を送出する
    (呼び出し元main.pyがstatus=skippedのArticleに変換する)。
    """
    top_page_url = newspaper_config["top_page_url"]
    user_agent = newspaper_config["user_agent"]
    robots_txt_url = newspaper_config.get("robots_txt_url")
    article_link_pattern = newspaper_config.get("article_link_pattern", "/article/")
    max_items = newspaper_config.get("max_items", DEFAULT_MAX_ITEMS)

    robots_guard.assert_allowed(top_page_url, user_agent, robots_txt_url)

    getter = fetch_html or _default_fetch_html
    html = getter(top_page_url, user_agent)

    soup = BeautifulSoup(html, "html.parser")
    articles: list[Article] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if article_link_pattern not in href:
            continue
        headline = anchor.get_text(strip=True)
        if not headline:
            continue
        absolute_url = urljoin(top_page_url, href)
        if absolute_url in seen_urls:
            continue
        seen_urls.add(absolute_url)

        articles.append(
            Article(
                date=date,
                collected_at=collected_at,
                category=newspaper_config.get("category", ""),
                region=newspaper_config.get("region", ""),
                newspaper=newspaper_config["name"],
                headline=headline,
                url=absolute_url,
                source_url=top_page_url,
                status=STATUS_OK,
            )
        )
        if len(articles) >= max_items:
            break

    return articles
