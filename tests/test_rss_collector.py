import pytest

from src.collectors.rss_collector import collect_rss
from src.models.article import STATUS_OK

ASAHI_CONFIG = {
    "name": "朝日新聞",
    "key": "asahi",
    "category": "全国紙",
    "region": "全国",
    "source_type": "rss",
    "rss_url": "tests/fixtures/rss/asahi_sample.rdf",
}

MAINICHI_CONFIG = {
    "name": "毎日新聞",
    "key": "mainichi",
    "category": "全国紙",
    "region": "全国",
    "source_type": "rss",
    "rss_url": "tests/fixtures/rss/mainichi_sample.rss",
}


def test_collect_rss_parses_asahi_fixture():
    articles = collect_rss(ASAHI_CONFIG, collected_at="2026-07-21T07:05:00+09:00", date="2026-07-21")

    assert len(articles) == 2
    first = articles[0]
    assert first.newspaper == "朝日新聞"
    assert first.status == STATUS_OK
    assert first.headline.startswith("救援物資は")
    assert first.url == "http://www.asahi.com/articles/ASV7K1FPCV7KUJUB00CM.html?ref=rss"
    assert first.source_url == ASAHI_CONFIG["rss_url"]
    assert first.date == "2026-07-21"
    assert first.collected_at == "2026-07-21T07:05:00+09:00"


def test_collect_rss_parses_mainichi_fixture():
    articles = collect_rss(MAINICHI_CONFIG, collected_at="2026-07-21T07:05:00+09:00", date="2026-07-21")

    assert len(articles) == 2
    assert articles[0].newspaper == "毎日新聞"
    assert articles[1].headline.startswith("朝ドラの反省")


def test_collect_rss_raises_for_unreachable_feed():
    bad_config = {**ASAHI_CONFIG, "rss_url": "tests/fixtures/rss/does_not_exist.rdf"}
    with pytest.raises(ValueError):
        collect_rss(bad_config, collected_at="2026-07-21T07:05:00+09:00", date="2026-07-21")
