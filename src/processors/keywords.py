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
    counts = count_keywords(articles, extra_stopwords)
    pool = {word for word, _ in counts.most_common(keyword_pool_size)}

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
