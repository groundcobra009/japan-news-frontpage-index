from src.models.article import STATUS_OK, Article
from src.processors.normalize import normalize_article, normalize_headline, normalize_url


def test_normalize_headline_collapses_whitespace_and_fullwidth():
    assert normalize_headline("　見出し\n\tサンプル　") == "見出し サンプル"


def test_normalize_headline_converts_fullwidth_alnum():
    assert normalize_headline("ＡＢＣ１２３") == "ABC123"


def test_normalize_headline_empty_returns_empty():
    assert normalize_headline("") == ""


def test_normalize_url_removes_tracking_params():
    result = normalize_url("https://example.com/articles/123.html?ref=rss&utm_source=x&foo=bar")
    assert result == "https://example.com/articles/123.html?foo=bar"


def test_normalize_url_resolves_relative_with_base():
    result = normalize_url("/article/123", base_url="https://www.tokyo-np.co.jp/")
    assert result == "https://www.tokyo-np.co.jp/article/123"


def test_normalize_url_keeps_absolute_url_even_with_base():
    result = normalize_url(
        "https://www.asahi.com/articles/ABC.html", base_url="https://www.asahi.com/rss/asahi/newsheadlines.rdf"
    )
    assert result == "https://www.asahi.com/articles/ABC.html"


def test_normalize_url_empty_returns_empty():
    assert normalize_url("") == ""


def test_normalize_article_applies_both_normalizations():
    article = Article(
        date="2026-07-21",
        collected_at="2026-07-21T07:05:00+09:00",
        category="全国紙",
        region="全国",
        newspaper="東京新聞",
        headline="　見出し　サンプル　",
        url="/article/123?ref=top_mainnews_pc_list",
        source_url="https://www.tokyo-np.co.jp/",
        status=STATUS_OK,
    )
    normalized = normalize_article(article)
    assert normalized.headline == "見出し サンプル"
    assert normalized.url == "https://www.tokyo-np.co.jp/article/123"
    # 元のarticleは変更されない
    assert article.headline == "　見出し　サンプル　"
