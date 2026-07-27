from pathlib import Path

import pytest

from src.collectors import robots_guard
from src.collectors.ceek_collector import (
    build_newspaper_index,
    collect_ceek,
    parse_title,
    resolve_outlet,
)
from src.models.article import CATEGORY_OTHER_MEDIA, STATUS_OK

FIXTURE = Path(__file__).parent / "fixtures" / "rss" / "ceek_politics_sample.xml"

NEWSPAPER_CONFIGS = [
    {"name": "日本経済新聞", "category": "全国紙", "region": "全国"},
    {"name": "読売新聞", "category": "全国紙", "region": "全国"},
    {"name": "毎日新聞", "category": "全国紙", "region": "全国"},
    {"name": "朝日新聞", "category": "全国紙", "region": "全国"},
    {"name": "沖縄タイムス", "category": "地方紙", "region": "沖縄"},
]

BASE_CONFIG = {
    "name": "Ceek.jp News",
    "key": "ceek",
    "source_type": "ceek",
    "feed_url_template": "https://news.ceek.jp/search.cgi?category_id={category_id}&feed=1",
    "user_agent": "test-bot/1.0",
    "robots_txt_url": "https://news.ceek.jp/robots.txt",
    "categories": ["politics"],
    "crawl_delay_seconds": 600,
    "respect_robots": False,
}


def make_config(**overrides) -> dict:
    config = dict(BASE_CONFIG)
    config.update(overrides)
    return config


def fake_fetch(url, user_agent, timeout):
    return FIXTURE.read_bytes()


def collect(**overrides):
    return collect_ceek(
        make_config(**overrides),
        collected_at="2026-07-28T06:00:00+09:00",
        date="2026-07-28",
        newspaper_index=build_newspaper_index(NEWSPAPER_CONFIGS),
        fetch_feed=fake_fetch,
        sleep=lambda _: None,
    )


def test_parse_title_splits_headline_and_outlet():
    assert parse_title("見出しです (毎日新聞)") == ("見出しです", "毎日新聞")


def test_parse_title_keeps_inner_parentheses_in_headline():
    headline, outlet = parse_title("（速報）内閣改造を検討 (毎日新聞)")
    assert headline == "（速報）内閣改造を検討"
    assert outlet == "毎日新聞"


def test_parse_title_without_outlet_returns_empty_outlet():
    assert parse_title("媒体名のない見出し") == ("媒体名のない見出し", "")


def test_resolve_outlet_inherits_category_and_region_from_existing_newspaper():
    index = build_newspaper_index(NEWSPAPER_CONFIGS)
    assert resolve_outlet("日本経済新聞", index) == ("日本経済新聞", "全国紙", "全国")
    assert resolve_outlet("沖縄タイムス", index) == ("沖縄タイムス", "地方紙", "沖縄")


def test_resolve_outlet_uses_organisation_after_colon():
    index = build_newspaper_index(NEWSPAPER_CONFIGS)
    assert resolve_outlet("FNN : フジテレビ", index) == ("フジテレビ", CATEGORY_OTHER_MEDIA, "")
    assert resolve_outlet("47NEWS : 共同通信", index) == ("共同通信", CATEGORY_OTHER_MEDIA, "")


def test_resolve_outlet_unmapped_becomes_other_media():
    index = build_newspaper_index(NEWSPAPER_CONFIGS)
    assert resolve_outlet("釧路新聞", index) == ("釧路新聞", CATEGORY_OTHER_MEDIA, "")


def test_resolve_outlet_applies_aliases():
    index = build_newspaper_index(NEWSPAPER_CONFIGS)
    assert resolve_outlet("日経", index, {"日経": "日本経済新聞"}) == ("日本経済新聞", "全国紙", "全国")


def test_collect_ceek_returns_only_ok_articles_with_expected_identity():
    result = collect()
    assert result.failures == []
    assert result.fetched_categories == ["politics"]
    assert all(a.status == STATUS_OK for a in result.articles)

    by_paper = {a.newspaper: a for a in result.articles}
    assert by_paper["日本経済新聞"].category == "全国紙"
    assert by_paper["沖縄タイムス"].region == "沖縄"
    assert by_paper["釧路新聞"].category == CATEGORY_OTHER_MEDIA
    assert by_paper["日本経済新聞"].source_url.endswith("category_id=politics&feed=1")
    assert by_paper["日本経済新聞"].topic == "政治"


def test_collect_ceek_never_stores_article_body_excerpt():
    """<description>の本文抜粋がArticleのどのフィールドにも入らないこと。"""
    result = collect()
    for article in result.articles:
        for value in (article.headline, article.url, article.error_message, article.topic):
            assert "本文抜粋" not in value


def test_collect_ceek_drops_items_without_outlet_or_link():
    result = collect()
    headlines = [a.headline for a in result.articles]
    assert "媒体名のない見出し" not in headlines
    assert "リンクのない記事" not in headlines
    assert len(result.articles) == 7


def test_collect_ceek_respects_max_items_per_category():
    result = collect(max_items_per_category=3)
    assert len(result.articles) <= 3


def test_collect_ceek_sleeps_between_categories_only():
    slept = []
    result = collect_ceek(
        make_config(categories=["politics", "business", "national"]),
        collected_at="x",
        date="2026-07-28",
        newspaper_index=build_newspaper_index(NEWSPAPER_CONFIGS),
        fetch_feed=fake_fetch,
        sleep=slept.append,
        monotonic=lambda: 0.0,
    )
    # 3カテゴリ = 待機2回。最初の取得前と最後の取得後には待たない。
    assert slept == [600.0, 600.0]
    assert result.fetched_categories == ["politics", "business", "national"]


def test_collect_ceek_subtracts_elapsed_fetch_time_from_delay():
    slept = []
    clock = iter([0.0, 30.0, 30.0, 60.0])

    result = collect_ceek(
        make_config(categories=["politics", "business"]),
        collected_at="x",
        date="2026-07-28",
        newspaper_index=build_newspaper_index(NEWSPAPER_CONFIGS),
        fetch_feed=fake_fetch,
        sleep=slept.append,
        monotonic=lambda: next(clock),
    )
    # 1回目のfetch完了が t=0 -> next_allowed_at=600、待機判定時に t=30 なので 570 待つ。
    assert slept == [570.0]
    assert len(result.fetched_categories) == 2


def test_collect_ceek_isolates_failing_category():
    def flaky_fetch(url, user_agent, timeout):
        if "business" in url:
            raise RuntimeError("boom")
        return FIXTURE.read_bytes()

    result = collect_ceek(
        make_config(categories=["politics", "business"]),
        collected_at="x",
        date="2026-07-28",
        newspaper_index=build_newspaper_index(NEWSPAPER_CONFIGS),
        fetch_feed=flaky_fetch,
        sleep=lambda _: None,
    )
    assert result.fetched_categories == ["politics"]
    assert len(result.failures) == 1
    assert result.failures[0].category_id == "business"
    # 失敗はArticleにしない(架空の新聞社が出力へ混入しないこと)。
    assert all(a.status == STATUS_OK for a in result.articles)
    assert result.articles


def test_collect_ceek_records_robots_disallow_as_skipped(monkeypatch):
    monkeypatch.setattr(robots_guard, "is_allowed", lambda *args, **kwargs: False)
    result = collect_ceek(
        make_config(respect_robots=True),
        collected_at="x",
        date="2026-07-28",
        newspaper_index=build_newspaper_index(NEWSPAPER_CONFIGS),
        fetch_feed=fake_fetch,
        sleep=lambda _: None,
    )
    assert result.articles == []
    assert result.failures == []
    assert len(result.skipped) == 1


@pytest.fixture(autouse=True)
def _clear_robots_cache():
    robots_guard._fetch_robots_parser.cache_clear()
    yield
    robots_guard._fetch_robots_parser.cache_clear()
