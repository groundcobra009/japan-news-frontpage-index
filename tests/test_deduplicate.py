from src.models.article import STATUS_OK, Article
from src.processors.deduplicate import deduplicate


def make_article(**overrides) -> Article:
    defaults = dict(
        date="2026-07-21",
        collected_at="2026-07-21T07:05:00+09:00",
        category="全国紙",
        region="全国",
        newspaper="東京新聞",
        headline="見出し",
        url="https://example.com/article/1",
        source_url="https://example.com/",
        status=STATUS_OK,
    )
    defaults.update(overrides)
    return Article(**defaults)


def test_deduplicate_removes_same_url_within_same_newspaper():
    a = make_article(url="https://example.com/article/1?ref=a")
    b = make_article(url="https://example.com/article/1?ref=b")
    result = deduplicate([a, b])
    assert len(result) == 1
    assert result[0] is a  # 最初に出現したものを残す


def test_deduplicate_keeps_same_article_across_different_newspapers():
    a = make_article(newspaper="東京新聞", url="https://example.com/same")
    b = make_article(newspaper="中日新聞", url="https://example.com/same")
    result = deduplicate([a, b])
    assert len(result) == 2


def test_deduplicate_preserves_order():
    a = make_article(url="https://example.com/1")
    b = make_article(url="https://example.com/2")
    c = make_article(url="https://example.com/1")
    result = deduplicate([a, b, c])
    assert result == [a, b]
