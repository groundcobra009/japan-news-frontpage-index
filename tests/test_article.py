from src.models.article import Article, STATUS_OK


def make_article(**overrides) -> Article:
    defaults = dict(
        date="2026-07-21",
        collected_at="2026-07-21T07:01:20+09:00",
        category="全国紙",
        region="全国",
        newspaper="朝日新聞",
        headline="見出しサンプル",
        url="https://www.asahi.com/articles/ABC123.html",
        source_url="https://www.asahi.com/rss/asahi/newsheadlines.rdf",
        status=STATUS_OK,
    )
    defaults.update(overrides)
    return Article(**defaults)


def test_dedup_key_uses_normalized_url_when_present():
    a = make_article(url="https://www.asahi.com/articles/ABC123.html?utm_source=x")
    b = make_article(url="https://www.asahi.com/articles/ABC123.html")
    assert a.dedup_key() == b.dedup_key()


def test_dedup_key_differs_across_newspapers_even_with_same_url_path():
    a = make_article(newspaper="朝日新聞", url="https://example.com/a")
    b = make_article(newspaper="毎日新聞", url="https://example.com/a")
    assert a.dedup_key() != b.dedup_key()


def test_dedup_key_falls_back_to_headline_when_url_missing():
    a = make_article(url="", headline="  同じ 見出し  ")
    b = make_article(url="", headline="同じ見出し")
    assert a.dedup_key() == b.dedup_key()


def test_to_csv_row_returns_all_fields():
    a = make_article()
    row = a.to_csv_row()
    assert row["newspaper"] == "朝日新聞"
    assert row["status"] == STATUS_OK
    assert row["error_message"] == ""
