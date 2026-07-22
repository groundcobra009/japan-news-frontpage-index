"""README.mdの自動生成。"""

from __future__ import annotations

import os

from src.models.article import STATUS_ERROR, STATUS_OK, Article
from src.processors.keywords import rank_top_articles, top_keywords

DEFAULT_TEMPLATE_PATH = "templates/README.template.md"
DEFAULT_README_PATH = "README.md"

_JP_WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

CATEGORY_LOCAL = "地方紙"

PREFECTURE_TO_BLOCK = {
    "北海道": "北海道・東北",
    "宮城": "北海道・東北",
    "新潟": "甲信越・東海",
    "長野": "甲信越・東海",
    "静岡": "甲信越・東海",
    "京都": "近畿",
    "兵庫": "近畿",
    "広島": "中国",
    "福岡": "九州・沖縄",
    "熊本": "九州・沖縄",
    "鹿児島": "九州・沖縄",
    "沖縄": "九州・沖縄",
}

BLOCK_ORDER = ["北海道・東北", "甲信越・東海", "近畿", "中国", "九州・沖縄"]


def list_archive_dates(data_dir: str = "data", limit: int = 14) -> list[str]:
    """data/YYYY/MM/YYYY-MM-DD.csv を新しい順に走査し、日付文字列のリストを返す。"""
    dates: list[str] = []
    if not os.path.isdir(data_dir):
        return dates

    for year in os.listdir(data_dir):
        year_path = os.path.join(data_dir, year)
        if not year.isdigit() or not os.path.isdir(year_path):
            continue
        for month in os.listdir(year_path):
            month_path = os.path.join(year_path, month)
            if not os.path.isdir(month_path):
                continue
            for fname in os.listdir(month_path):
                if fname.endswith(".csv") and fname != "index.csv":
                    dates.append(fname[: -len(".csv")])

    dates.sort(reverse=True)
    return dates[:limit]


def _representative_row(newspaper: str, articles_for_paper: list[Article]) -> str:
    ok_articles = [a for a in articles_for_paper if a.status == STATUS_OK]
    if ok_articles:
        headline = ok_articles[0].headline.replace("|", "｜")
        url = ok_articles[0].url
        return f"| {newspaper} | {headline} | [記事を読む]({url}) |"
    return f"| {newspaper} | (取得できませんでした) | - |"


def _representative_row_with_region(newspaper: str, region: str, articles_for_paper: list[Article]) -> str:
    ok_articles = [a for a in articles_for_paper if a.status == STATUS_OK]
    if ok_articles:
        headline = ok_articles[0].headline.replace("|", "｜")
        url = ok_articles[0].url
        return f"| {newspaper} | {region} | {headline} | [記事を読む]({url}) |"
    return f"| {newspaper} | {region} | (取得できませんでした) | - |"


def _build_local_tables(articles: list[Article]) -> str:
    local_articles = [a for a in articles if a.category == CATEGORY_LOCAL]
    if not local_articles:
        return "(まだ地方紙のデータがありません)"

    grouped_by_block: dict[str, dict[str, list[Article]]] = {}
    for article in local_articles:
        block = PREFECTURE_TO_BLOCK.get(article.region, "その他")
        grouped_by_block.setdefault(block, {}).setdefault(article.newspaper, []).append(article)

    ordered_blocks = [b for b in BLOCK_ORDER if b in grouped_by_block]
    ordered_blocks += [b for b in grouped_by_block if b not in ordered_blocks]

    sections = []
    for block in ordered_blocks:
        rows = [
            _representative_row_with_region(newspaper, rows_for_paper[0].region, rows_for_paper)
            for newspaper, rows_for_paper in grouped_by_block[block].items()
        ]
        table = "| 新聞社 | 地域 | 一面・主要見出し | URL |\n|---|---|---|---|\n" + "\n".join(rows)
        sections.append(f"#### {block}\n\n{table}")

    return "\n\n".join(sections)


def _group_by_newspaper_preserving_order(articles: list[Article]) -> dict[str, list[Article]]:
    grouped: dict[str, list[Article]] = {}
    for article in articles:
        grouped.setdefault(article.newspaper, []).append(article)
    return grouped


def _classify_newspaper_status(articles_for_paper: list[Article]) -> str:
    if any(a.status == STATUS_OK for a in articles_for_paper):
        return "ok"
    if any(a.status == STATUS_ERROR for a in articles_for_paper):
        return "error"
    return "skipped"


def _build_status_summary(articles: list[Article]) -> str:
    grouped = _group_by_newspaper_preserving_order(articles)
    ok_count = skipped_count = error_count = 0
    for rows in grouped.values():
        status = _classify_newspaper_status(rows)
        if status == "ok":
            ok_count += 1
        elif status == "error":
            error_count += 1
        else:
            skipped_count += 1
    return f"- 成功：{ok_count}紙\n- スキップ：{skipped_count}紙\n- 失敗：{error_count}紙"


def _format_date_jp(date: str) -> str:
    year, month, day = date.split("-")
    return f"{int(year)}年{int(month)}月{int(day)}日"


def _build_extra_stopwords(articles: list[Article]) -> frozenset[str]:
    names = {a.newspaper for a in articles if a.newspaper}
    regions = {a.region for a in articles if a.region}
    return frozenset(names | regions)


def _build_top_articles_section(articles: list[Article]) -> str:
    extra_stopwords = _build_extra_stopwords(articles)
    top_articles = rank_top_articles(articles, extra_stopwords=extra_stopwords)
    if not top_articles:
        return "(本日は対象記事がありません)"
    lines = [
        f"{i}. **{a.newspaper}**: {a.headline.replace('|', '｜')} ([記事を読む]({a.url}))"
        for i, a in enumerate(top_articles, start=1)
    ]
    return "\n".join(lines)


def _build_keywords_section(articles: list[Article]) -> str:
    extra_stopwords = _build_extra_stopwords(articles)
    keywords = top_keywords(articles, extra_stopwords=extra_stopwords)
    if not keywords:
        return "(本日は抽出できるキーワードがありません)"
    return "\n".join(f"- {word}" for word in keywords)


def render_readme(
    articles: list[Article],
    date: str,
    generated_at: str,
    archive_dates: list[str],
    template_path: str = DEFAULT_TEMPLATE_PATH,
) -> str:
    """テンプレートのプレースホルダを当日データで置換した文字列を返す(純粋関数)。"""
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    national_articles = [a for a in articles if a.category != CATEGORY_LOCAL]
    grouped = _group_by_newspaper_preserving_order(national_articles)
    order = list(grouped.keys())
    national_rows = "\n".join(_representative_row(name, grouped[name]) for name in order)

    local_tables = _build_local_tables(articles)
    top_articles_section = _build_top_articles_section(articles)
    keywords_section = _build_keywords_section(articles)

    if archive_dates:
        archive_list = "\n".join(
            f"- [{_format_date_jp(d)}](data/{d[:4]}/{d[5:7]}/{d}.csv)" for d in archive_dates
        )
    else:
        archive_list = "(まだデータがありません)"

    status_summary = _build_status_summary(articles)

    rendered = template.replace("{{LAST_UPDATED}}", generated_at)
    rendered = rendered.replace("{{NATIONAL_TABLE_ROWS}}", national_rows or "(データがありません)")
    rendered = rendered.replace("{{LOCAL_TABLES}}", local_tables)
    rendered = rendered.replace("{{TOP_ARTICLES}}", top_articles_section)
    rendered = rendered.replace("{{KEYWORDS}}", keywords_section)
    rendered = rendered.replace("{{ARCHIVE_LIST}}", archive_list)
    rendered = rendered.replace("{{STATUS_SUMMARY}}", status_summary)
    return rendered


def write_readme(rendered: str, readme_path: str = DEFAULT_README_PATH) -> None:
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(rendered)
