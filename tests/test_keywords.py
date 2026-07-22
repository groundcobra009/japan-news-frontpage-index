from src.models.article import STATUS_ERROR, STATUS_OK, STATUS_SKIPPED, Article
from src.processors.keywords import count_keywords, rank_top_articles, top_keywords


def make_article(**overrides) -> Article:
    defaults = dict(
        date="2026-07-21",
        collected_at="2026-07-21T07:05:00+09:00",
        category="全国紙",
        region="全国",
        newspaper="朝日新聞",
        headline="見出し",
        url="https://example.com/1",
        source_url="https://example.com/",
        status=STATUS_OK,
    )
    defaults.update(overrides)
    return Article(**defaults)


def test_count_keywords_counts_repeated_nouns_across_headlines():
    articles = [
        make_article(headline="台風接近で交通機関に影響"),
        make_article(headline="台風の進路予想を発表"),
    ]
    counts = count_keywords(articles)
    assert counts["台風"] == 2


def test_count_keywords_ignores_non_ok_articles():
    articles = [
        make_article(headline="台風接近で被害拡大", status=STATUS_SKIPPED),
        make_article(headline="台風接近で被害拡大", status=STATUS_ERROR),
    ]
    counts = count_keywords(articles)
    assert counts["台風"] == 0


def test_count_keywords_respects_extra_stopwords():
    articles = [make_article(headline="朝日新聞が特集を掲載")]
    counts = count_keywords(articles, extra_stopwords=frozenset({"朝日新聞"}))
    assert "朝日新聞" not in counts


def test_top_keywords_returns_most_frequent_first():
    articles = [
        make_article(headline="台風接近で影響拡大"),
        make_article(headline="台風の進路情報を発表"),
        make_article(headline="物価上昇が続く"),
    ]
    keywords = top_keywords(articles, limit=3)
    assert keywords[0] == "台風"


def test_top_keywords_empty_articles_returns_empty_list():
    assert top_keywords([]) == []


def test_count_keywords_excludes_punctuation_only_tokens():
    articles = [make_article(headline="支持率下落で痛烈批判...立憲・水岡代表")]
    counts = count_keywords(articles)
    assert "..." not in counts
    assert "・" not in counts


def test_rank_top_articles_prioritizes_articles_matching_pool_keywords():
    articles = [
        make_article(newspaper="朝日新聞", headline="台風接近で交通機関に影響拡大", url="https://example.com/1"),
        make_article(newspaper="毎日新聞", headline="台風の進路予想を発表", url="https://example.com/2"),
        make_article(newspaper="産経新聞", headline="猫の写真展が人気", url="https://example.com/3"),
    ]
    top = rank_top_articles(articles, limit=2)
    assert len(top) == 2
    headlines = [a.headline for a in top]
    assert "猫の写真展が人気" not in headlines


def test_rank_top_articles_respects_per_newspaper_cap():
    articles = [
        make_article(newspaper="朝日新聞", headline=f"台風速報{i}台風進路情報", url=f"https://example.com/{i}")
        for i in range(5)
    ]
    top = rank_top_articles(articles, limit=10, per_newspaper_cap=2)
    assert len(top) == 2


def test_rank_top_articles_empty_when_no_ok_articles():
    articles = [make_article(status=STATUS_SKIPPED, headline="")]
    assert rank_top_articles(articles) == []
