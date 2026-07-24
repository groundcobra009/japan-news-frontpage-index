"""見出し集合からのキーワード抽出と、重要ニュースTOP10のスコアリング。

記事全文は保存しない方針のため、当日収集した見出しのみを入力とする。外部AI APIは
使わず、janome(Pure Python形態素解析)による名詞頻度ベースのヒューリスティックで
実装する。
"""

from __future__ import annotations

import re
from collections import Counter

from janome.tokenizer import Tokenizer

from src.models.article import STATUS_OK, Article

_TOKENIZER = Tokenizer()

_ALLOWED_POS_SUBCATEGORIES = {"一般", "固有名詞", "サ変接続"}
_MIN_SURFACE_LENGTH = 2
_HAS_WORD_CHAR = re.compile(r"[ぁ-んァ-ヶー一-龠a-zA-Z0-9]")

STOPWORDS = frozenset(
    {
        "こと",
        "もの",
        "とき",
        "ため",
        "よう",
        "これ",
        "それ",
        "あれ",
        "そう",
        "うち",
        "ところ",
        "そのもの",
    }
)

DEFAULT_KEYWORD_DISPLAY_COUNT = 5
DEFAULT_KEYWORD_POOL_SIZE = 30
DEFAULT_TOP_ARTICLE_COUNT = 10
DEFAULT_PER_NEWSPAPER_CAP = 3


def _extract_nouns(text: str) -> list[str]:
    nouns = []
    for token in _TOKENIZER.tokenize(text):
        pos_parts = token.part_of_speech.split(",")
        if pos_parts[0] != "名詞" or pos_parts[1] not in _ALLOWED_POS_SUBCATEGORIES:
            continue
        surface = token.base_form if token.base_form != "*" else token.surface
        if len(surface) < _MIN_SURFACE_LENGTH:
            continue
        if not _HAS_WORD_CHAR.search(surface):
            continue
        nouns.append(surface)
    return nouns


def _ok_headlines(articles: list[Article]) -> list[Article]:
    return [a for a in articles if a.status == STATUS_OK and a.headline]


def build_extra_stopwords(articles: list[Article]) -> frozenset[str]:
    """新聞社名・地域名を動的にストップワード化する(見出しに紙名等が含まれてもノイズにしない)。"""
    names = {a.newspaper for a in articles if a.newspaper}
    regions = {a.region for a in articles if a.region}
    return frozenset(names | regions)


def count_keywords(articles: list[Article], extra_stopwords: frozenset[str] = frozenset()) -> Counter:
    """当日の見出し(status=okのみ)から名詞の出現回数を集計する。"""
    stopwords = STOPWORDS | extra_stopwords
    counter: Counter = Counter()
    for article in _ok_headlines(articles):
        for noun in _extract_nouns(article.headline):
            if noun in stopwords:
                continue
            counter[noun] += 1
    return counter


def top_keywords(
    articles: list[Article],
    extra_stopwords: frozenset[str] = frozenset(),
    limit: int = DEFAULT_KEYWORD_DISPLAY_COUNT,
) -> list[str]:
    """出現頻度上位のキーワードを返す(表示用)。"""
    counts = count_keywords(articles, extra_stopwords)
    return [word for word, _ in counts.most_common(limit)]


def build_keyword_pool(
    articles: list[Article],
    extra_stopwords: frozenset[str] = frozenset(),
    pool_size: int = DEFAULT_KEYWORD_POOL_SIZE,
) -> set[str]:
    """当日の見出し全体から頻出語上位pool_size件の集合を作る(代表記事選定・TOP10で共用)。"""
    counts = count_keywords(articles, extra_stopwords)
    return {word for word, _ in counts.most_common(pool_size)}


def pick_representative_article(
    articles_for_paper: list[Article],
    keyword_pool: set[str],
    extra_stopwords: frozenset[str] = frozenset(),
) -> Article | None:
    """新聞社内で、当日の頻出キーワードとの一致数が最も高い記事を代表として返す。

    全記事が同点(0件一致を含む)の場合は最初に取得できた記事を優先する
    (Python の max() はタイ時に最初の要素を保持するため、追加の分岐は不要)。
    status=okの記事が1件もなければNoneを返す。
    """
    ok_articles = _ok_headlines(articles_for_paper)
    if not ok_articles:
        return None

    stopwords = STOPWORDS | extra_stopwords
    scored = []
    for article in ok_articles:
        nouns = {n for n in _extract_nouns(article.headline) if n not in stopwords}
        score = len(nouns & keyword_pool)
        scored.append((score, article))

    _, best_article = max(scored, key=lambda pair: pair[0])
    return best_article


def rank_top_articles(
    articles: list[Article],
    extra_stopwords: frozenset[str] = frozenset(),
    keyword_pool_size: int = DEFAULT_KEYWORD_POOL_SIZE,
    limit: int = DEFAULT_TOP_ARTICLE_COUNT,
    per_newspaper_cap: int = DEFAULT_PER_NEWSPAPER_CAP,
) -> list[Article]:
    """頻出語(上位keyword_pool_size件)を多く含む見出しほど重要度が高いとみなしてランキングする。

    1新聞社あたりper_newspaper_cap件までに制限し、見出し数の多い新聞社に偏らないようにする。
    """
    stopwords = STOPWORDS | extra_stopwords
    pool = build_keyword_pool(articles, extra_stopwords, keyword_pool_size)

    scored: list[tuple[int, Article]] = []
    for article in _ok_headlines(articles):
        nouns = {n for n in _extract_nouns(article.headline) if n not in stopwords}
        score = len(nouns & pool)
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    result: list[Article] = []
    per_newspaper_count: dict[str, int] = {}
    for _, article in scored:
        count = per_newspaper_count.get(article.newspaper, 0)
        if count >= per_newspaper_cap:
            continue
        result.append(article)
        per_newspaper_count[article.newspaper] = count + 1
        if len(result) >= limit:
            break
    return result
