"""README.mdの自動生成。"""

from __future__ import annotations

import os

from src.models.article import STATUS_ERROR, STATUS_OK, Article

DEFAULT_TEMPLATE_PATH = "templates/README.template.md"
DEFAULT_README_PATH = "README.md"

_JP_WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


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

    grouped = _group_by_newspaper_preserving_order(articles)
    order = list(grouped.keys())
    national_rows = "\n".join(_representative_row(name, grouped[name]) for name in order)

    if archive_dates:
        archive_list = "\n".join(
            f"- [{_format_date_jp(d)}](data/{d[:4]}/{d[5:7]}/{d}.csv)" for d in archive_dates
        )
    else:
        archive_list = "(まだデータがありません)"

    status_summary = _build_status_summary(articles)

    rendered = template.replace("{{LAST_UPDATED}}", generated_at)
    rendered = rendered.replace("{{NATIONAL_TABLE_ROWS}}", national_rows or "(データがありません)")
    rendered = rendered.replace("{{ARCHIVE_LIST}}", archive_list)
    rendered = rendered.replace("{{STATUS_SUMMARY}}", status_summary)
    return rendered


def write_readme(rendered: str, readme_path: str = DEFAULT_README_PATH) -> None:
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(rendered)
