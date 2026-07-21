from pathlib import Path

import pytest

from src.collectors.html_collector import collect_html
from src.collectors.robots_guard import RobotsDisallowedError
from src.models.article import STATUS_OK

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"

TOKYO_CONFIG = {
    "name": "東京新聞",
    "key": "tokyo",
    "category": "全国紙",
    "region": "全国",
    "source_type": "html",
    "top_page_url": "https://www.tokyo-np.co.jp/",
    "robots_txt_url": "https://www.tokyo-np.co.jp/robots.txt",
    "user_agent": "test-bot/1.0",
    "article_link_pattern": "/article/",
    "max_items": 20,
}

CHUNICHI_CONFIG = {
    "name": "中日新聞",
    "key": "chunichi",
    "category": "全国紙",
    "region": "全国",
    "source_type": "html",
    "top_page_url": "https://www.chunichi.co.jp/",
    "robots_txt_url": "https://www.chunichi.co.jp/robots.txt",
    "user_agent": "test-bot/1.0",
    "article_link_pattern": "/article/",
    "max_items": 20,
}


def _fixture_fetcher(filename):
    def _fetch(url, user_agent):
        return (FIXTURES_DIR / filename).read_text(encoding="utf-8")

    return _fetch


def _allow_all(monkeypatch, module):
    monkeypatch.setattr(module.robots_guard, "assert_allowed", lambda *a, **k: None)


def test_collect_html_extracts_matching_links_and_skips_others(monkeypatch):
    import src.collectors.html_collector as module

    _allow_all(monkeypatch, module)

    articles = collect_html(
        TOKYO_CONFIG,
        collected_at="2026-07-21T07:05:00+09:00",
        date="2026-07-21",
        fetch_html=_fixture_fetcher("tokyo_sample.html"),
    )

    assert len(articles) == 3
    headlines = [a.headline for a in articles]
    assert "攻撃用ドローン導入を進める防衛省…市民が危ぶむ「イスラエル支援」" in headlines
    assert all(a.status == STATUS_OK for a in articles)
    assert all(a.newspaper == "東京新聞" for a in articles)
    # ログイン/検索リンクはarticle_link_patternに一致しないので含まれない
    assert not any("ログイン" in h or "検索" in h for h in headlines)


def test_collect_html_deduplicates_identical_href_within_page(monkeypatch):
    import src.collectors.html_collector as module

    _allow_all(monkeypatch, module)

    articles = collect_html(
        CHUNICHI_CONFIG,
        collected_at="2026-07-21T07:05:00+09:00",
        date="2026-07-21",
        fetch_html=_fixture_fetcher("chunichi_sample.html"),
    )

    urls = [a.url for a in articles]
    assert len(urls) == len(set(urls))
    assert len(articles) == 2


def test_collect_html_respects_max_items(monkeypatch):
    import src.collectors.html_collector as module

    _allow_all(monkeypatch, module)

    limited_config = {**TOKYO_CONFIG, "max_items": 1}
    articles = collect_html(
        limited_config,
        collected_at="2026-07-21T07:05:00+09:00",
        date="2026-07-21",
        fetch_html=_fixture_fetcher("tokyo_sample.html"),
    )
    assert len(articles) == 1


def test_collect_html_supports_regex_pattern(monkeypatch):
    import src.collectors.html_collector as module

    _allow_all(monkeypatch, module)

    html = """
    <html><body>
      <a href="/common/auth/webnp.shtml?nppaper=morning">朝刊</a>
      <a href="/news/society/202607/0020613977.shtml">兵庫の公立プール値上げ相次ぐ</a>
      <a href="/news/akashi/202607/0020613843.shtml">明石歩道橋事故25年</a>
    </body></html>
    """
    config = {
        "name": "神戸新聞",
        "key": "kobe",
        "category": "地方紙",
        "region": "兵庫",
        "source_type": "html",
        "top_page_url": "https://www.kobe-np.co.jp/",
        "user_agent": "test-bot/1.0",
        "article_link_pattern": r"/news/[a-z]+/\d{6}/\d+\.shtml",
        "max_items": 20,
    }

    articles = collect_html(
        config,
        collected_at="2026-07-21T07:05:00+09:00",
        date="2026-07-21",
        fetch_html=lambda url, ua: html,
    )

    assert len(articles) == 2
    assert all("news" in a.url for a in articles)
    assert not any("朝刊" == a.headline for a in articles)


def test_collect_html_raises_when_robots_disallows(monkeypatch):
    import src.collectors.html_collector as module

    def _deny(*a, **k):
        raise RobotsDisallowedError("disallowed")

    monkeypatch.setattr(module.robots_guard, "assert_allowed", _deny)

    with pytest.raises(RobotsDisallowedError):
        collect_html(
            TOKYO_CONFIG,
            collected_at="2026-07-21T07:05:00+09:00",
            date="2026-07-21",
            fetch_html=_fixture_fetcher("tokyo_sample.html"),
        )
