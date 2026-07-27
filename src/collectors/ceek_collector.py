"""ニュースアグリゲーター news.ceek.jp からの横断収集。

各紙のトップページ/RSSを個別に叩く既存コレクターと違い、ceek.jpのカテゴリ別RSSは
1フィードに多数の媒体の記事が混在する。そのため1回の呼び出しで複数の新聞社の
Articleを返す点が rss_collector / html_collector と異なる。

方針:
- 見出しとURLのみを取り込む。<description>には本文抜粋が入っているが、本プロジェクトの
  「記事本文は保存しない」方針に従い**読まない**(Articleに格納先も作らない)。
- robots.txtの Crawl-Delay を守るため、カテゴリ取得の間隔をあける。設定値と
  robots.txtの申告値のうち**厳しい方**を採用する。
- 媒体名は<title>末尾の括弧から取り出し、config/newspapers.yml に同名の紙があれば
  その category / region を継承する(既存の紙とidentityを揃えるため)。一致しなければ
  「その他メディア」として扱い、READMEの全国紙/地方紙テーブルには載せない。
- **status=okのArticleしか返さない。** 取得失敗は CeekResult.failures として別に返す。
  失敗を status=error のArticleにしてしまうと、架空の新聞社名が紙別テーブルや
  取得失敗通知Issueに混入するため(src/outputs/issue_notifier.py は newspaper単位で
  集計している)。
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests

from src.collectors import robots_guard
from src.models.article import CATEGORY_OTHER_MEDIA, STATUS_OK, Article

DEFAULT_REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_MAX_ITEMS_PER_CATEGORY = 100
DEFAULT_CRAWL_DELAY_SECONDS = 600

# "見出し (媒体名)" の末尾括弧。媒体名自体には括弧が入らない前提で、最後の括弧組を取る。
_TITLE_OUTLET_PATTERN = re.compile(r"^(?P<headline>.+?)\s*[(（]\s*(?P<outlet>[^(（)）]+?)\s*[)）]\s*$")

# "47NEWS : 共同通信" のような "サイト名 : 運営組織" 表記の分割。
_OUTLET_SPLIT_PATTERN = re.compile(r"\s*[:：]\s*")

_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class AggregatorFailure:
    """アグリゲーターのカテゴリ単位の取得失敗/スキップ。"""

    aggregator: str
    category_id: str
    url: str
    reason: str


@dataclass
class CeekResult:
    articles: list[Article] = field(default_factory=list)
    failures: list[AggregatorFailure] = field(default_factory=list)
    skipped: list[AggregatorFailure] = field(default_factory=list)
    fetched_categories: list[str] = field(default_factory=list)


def _default_fetch_feed(url: str, user_agent: str, timeout: float) -> bytes:
    """RSSを取得する。textではなくbytesを返し、XML宣言のエンコーディングをfeedparserに任せる。"""
    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
    response.raise_for_status()
    return response.content


def build_newspaper_index(newspaper_configs: list[dict]) -> dict[str, dict]:
    """新聞社名 -> {category, region} の索引を作る(ceekの媒体名照合用)。"""
    return {
        entry["name"]: {
            "category": entry.get("category", ""),
            "region": entry.get("region", ""),
        }
        for entry in newspaper_configs
        if entry.get("name")
    }


def parse_title(raw_title: str) -> tuple[str, str]:
    """ceekの<title>を (見出し, 媒体名) に分解する。末尾括弧が無ければ媒体名は空文字。"""
    stripped = raw_title.strip()
    match = _TITLE_OUTLET_PATTERN.match(stripped)
    if not match:
        return stripped, ""
    return match.group("headline").strip(), match.group("outlet").strip()


def normalize_outlet_name(raw_outlet: str, aliases: dict[str, str] | None = None) -> str:
    """媒体名をNFKC正規化・空白圧縮し、別名表があれば正式名称へ寄せる。"""
    normalized = _WHITESPACE_PATTERN.sub(" ", unicodedata.normalize("NFKC", raw_outlet)).strip()
    if not normalized:
        return ""
    return (aliases or {}).get(normalized, normalized)


def resolve_outlet(
    outlet: str,
    newspaper_index: dict[str, dict],
    aliases: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    """媒体名を (新聞社名, category, region) に解決する。

    "47NEWS : 共同通信" のような表記は、全体で照合したあと区切りの後半(運営組織)を
    優先して照合する。既存紙に一致すればその category / region を継承し、
    一致しなければ「その他メディア」扱いにする。
    """
    normalized = normalize_outlet_name(outlet, aliases)
    if not normalized:
        return "", "", ""

    candidates = [normalized]
    parts = [p.strip() for p in _OUTLET_SPLIT_PATTERN.split(normalized) if p.strip()]
    if len(parts) > 1:
        # 後半(運営組織)の方が正式名称に近いことが多いので先に照合する。
        for part in reversed(parts):
            candidates.append(normalize_outlet_name(part, aliases))

    for candidate in candidates:
        matched = newspaper_index.get(candidate)
        if matched:
            return candidate, matched["category"], matched["region"]

    # 一致しない媒体は表示名だけ整えて「その他メディア」に寄せる。
    display = normalize_outlet_name(parts[-1], aliases) if len(parts) > 1 else normalized
    return display, CATEGORY_OTHER_MEDIA, ""


def _strip_query(url: str) -> str:
    """robots.txt照合用にクエリを落としたURLを返す。"""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _resolve_delay(
    config: dict,
    sample_url: str,
    user_agent: str,
    robots_txt_url: str | None,
    consult_robots: bool,
) -> float:
    """設定値とrobots.txtの申告値のうち厳しい(長い)方を採用する。

    consult_robots=False でも設定値の待機は必ず効かせる(robots判定を切ることと、
    相手サーバーへ連続アクセスしてよいことは別問題のため)。
    """
    configured = float(config.get("crawl_delay_seconds", DEFAULT_CRAWL_DELAY_SECONDS))
    if not consult_robots:
        return configured
    declared = robots_guard.get_crawl_delay(sample_url, user_agent, robots_txt_url)
    return max(configured, declared) if declared is not None else configured


def collect_ceek(
    config: dict,
    collected_at: str,
    date: str,
    newspaper_index: dict[str, dict] | None = None,
    fetch_feed=None,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> CeekResult:
    """ceek.jpのカテゴリ別RSSを順に取得し、全媒体のArticleをまとめて返す。

    fetch_feed は (url, user_agent, timeout) -> RSS文字列/bytes の差し替え用フック。
    sleep / monotonic も差し替え可能で、テストでは待機を飛ばして即座に検証する。
    カテゴリ単位の失敗は例外にせず CeekResult.failures へ積み、他カテゴリの収集は続行する。
    """
    index = newspaper_index or {}
    name = config.get("name", "ceek")
    user_agent = config["user_agent"]
    robots_txt_url = config.get("robots_txt_url")
    url_template = config["feed_url_template"]
    categories = config.get("categories") or []
    max_items = config.get("max_items_per_category", DEFAULT_MAX_ITEMS_PER_CATEGORY)
    timeout = config.get("request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS)
    aliases = config.get("outlet_aliases") or {}
    respect_robots = config.get("respect_robots", True)

    getter = fetch_feed or _default_fetch_feed
    result = CeekResult()
    if not categories:
        return result

    first_url = url_template.format(category_id=categories[0])
    delay = _resolve_delay(config, _strip_query(first_url), user_agent, robots_txt_url, respect_robots)

    next_allowed_at: float | None = None

    for category_id in categories:
        feed_url = url_template.format(category_id=category_id)

        # Crawl-Delay遵守。実フェッチの直後にのみ次回可能時刻を更新するため、
        # 最初の取得前は待たず、robotsでスキップしたカテゴリは待機予算を消費しない。
        if next_allowed_at is not None:
            remaining = next_allowed_at - monotonic()
            if remaining > 0:
                sleep(remaining)

        if respect_robots:
            try:
                robots_guard.assert_allowed(_strip_query(feed_url), user_agent, robots_txt_url)
            except robots_guard.RobotsDisallowedError as exc:
                result.skipped.append(AggregatorFailure(name, category_id, feed_url, str(exc)))
                continue

        try:
            raw = getter(feed_url, user_agent, timeout)
            feed = feedparser.parse(raw)
            if feed.bozo and not feed.entries:
                raise ValueError(f"RSSのパースに失敗しました ({feed.bozo_exception})")
        except Exception as exc:  # noqa: BLE001 - 1カテゴリの失敗を他カテゴリに波及させない
            result.failures.append(AggregatorFailure(name, category_id, feed_url, str(exc)))
            next_allowed_at = monotonic() + delay
            continue

        next_allowed_at = monotonic() + delay
        result.fetched_categories.append(category_id)
        result.articles.extend(
            _entries_to_articles(feed.entries[:max_items], feed_url, collected_at, date, index, aliases)
        )

    return result


def _entries_to_articles(
    entries,
    feed_url: str,
    collected_at: str,
    date: str,
    index: dict[str, dict],
    aliases: dict[str, str],
) -> list[Article]:
    articles: list[Article] = []
    for entry in entries:
        headline, outlet = parse_title(entry.get("title", ""))
        url = entry.get("link", "")
        if not headline or not url:
            continue

        newspaper, category, region = resolve_outlet(outlet, index, aliases)
        if not newspaper:
            # 媒体名が取れない記事は出所を示せないため取り込まない。
            continue

        articles.append(
            Article(
                date=date,
                collected_at=collected_at,
                category=category,
                region=region,
                newspaper=newspaper,
                headline=headline,
                url=url,
                source_url=feed_url,
                status=STATUS_OK,
                # ceekの<category>(政治/経済など)。本文抜粋<description>は意図的に読まない。
                topic=_extract_topic(entry),
            )
        )
    return articles


def _extract_topic(entry) -> str:
    tags = entry.get("tags")
    if not tags:
        return ""
    return tags[0].get("term", "") or ""
