"""CSV出力(日付別CSV・latest.csv・月次index.csv・アーカイブ一覧JSON)。"""

from __future__ import annotations

import csv
import json
import os

from src.models.article import CSV_FIELDNAMES, STATUS_OK, Article
from src.processors.deduplicate import deduplicate


def _write_csv(path: str, articles: list[Article]) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for article in articles:
            writer.writerow(article.to_csv_row())
    return path


def daily_csv_path(date: str, data_dir: str = "data") -> str:
    year, month, _ = date.split("-")
    return os.path.join(data_dir, year, month, f"{date}.csv")


def read_articles_csv(path: str) -> list[Article]:
    """既存CSVをArticleに読み戻す。列が欠けている旧CSVにも耐える。"""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [Article(**{key: (row.get(key) or "") for key in CSV_FIELDNAMES}) for row in rows]


def merge_daily_articles(existing: list[Article], new: list[Article]) -> list[Article]:
    """同日の既存CSVと今回の実行結果をマージする。

    1日3回実行するため、単純な上書きだと後の実行が前の実行の記事を消してしまう。
    - 既存のstatus=ok行は残す(初出のcollected_atを保持する)
    - 今回登場した新聞社の非ok行は捨てる(復旧済みなら古い失敗行を残さない)
    - 重複判定は deduplicate() と同じ Article.dedup_key()
    """
    newspapers_in_new = {a.newspaper for a in new}
    retained = [a for a in existing if a.status == STATUS_OK or a.newspaper not in newspapers_in_new]
    return deduplicate(retained + new)


def build_daily_articles(new_articles: list[Article], date: str, data_dir: str = "data") -> list[Article]:
    """その日のCSVに書くべき最終リストを返す(読み取りのみで書き込みはしない)。"""
    existing = read_articles_csv(daily_csv_path(date, data_dir))
    return merge_daily_articles(existing, new_articles)


def write_daily_csv(
    articles: list[Article], date: str, data_dir: str = "data", merge_existing: bool = True
) -> str:
    """data/YYYY/MM/YYYY-MM-DD.csv を書く。

    既定では同日の既存CSVとマージする。build_daily_articles で先にマージ済みの
    リストを渡す場合は merge_existing=False にして二重マージを避ける。
    """
    path = daily_csv_path(date, data_dir)
    rows = build_daily_articles(articles, date, data_dir) if merge_existing else articles
    return _write_csv(path, rows)


def write_latest_csv(articles: list[Article], data_dir: str = "data") -> str:
    """data/latest.csv を上書きする。"""
    path = os.path.join(data_dir, "latest.csv")
    return _write_csv(path, articles)


def append_index_csv(
    date: str,
    article_count: int,
    ok_count: int,
    skipped_count: int,
    error_count: int,
    data_dir: str = "data",
) -> str:
    """data/YYYY/MM/index.csv に日次サマリ行を追記/更新する(再実行時は同日行を置換)。"""
    year, month, _ = date.split("-")
    path = os.path.join(data_dir, year, month, "index.csv")
    fieldnames = ["date", "article_count", "ok_count", "skipped_count", "error_count"]

    rows: list[dict] = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

    rows = [r for r in rows if r["date"] != date]
    rows.append(
        {
            "date": date,
            "article_count": article_count,
            "ok_count": ok_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
        }
    )
    rows.sort(key=lambda r: r["date"])

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _summary_payload(summary: str, date: str, source: str, generated_at: str) -> dict:
    return {"date": date, "summary": summary, "source": source, "generated_at": generated_at}


def _write_summary_json(path: str, payload: dict) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def write_daily_summary(
    summary: str,
    date: str,
    source: str = "extractive",
    generated_at: str = "",
    data_dir: str = "data",
) -> str:
    """data/YYYY/MM/YYYY-MM-DD.summary.json を書く(既存は上書き、再実行に対応)。

    日付別に持つことで、GitHub Pagesの過去日付表示でもその日のまとめを出せる。
    list_archive_dates は .csv だけを拾うため、このファイルはアーカイブ一覧に混入しない。
    """
    year, month, _ = date.split("-")
    path = os.path.join(data_dir, year, month, f"{date}.summary.json")
    return _write_summary_json(path, _summary_payload(summary, date, source, generated_at))


def write_latest_summary(
    summary: str,
    date: str,
    source: str = "extractive",
    generated_at: str = "",
    data_dir: str = "data",
) -> str:
    """data/summary-latest.json を上書きする(GitHub Pagesの「本日のまとめ」用)。"""
    path = os.path.join(data_dir, "summary-latest.json")
    return _write_summary_json(path, _summary_payload(summary, date, source, generated_at))


def write_archive_manifest(archive_dates: list[str], data_dir: str = "data") -> str:
    """docs/(GitHub Pages)がfetchするdata/archive-index.jsonを書く。

    新しい順に並んだ日付文字列のリストをそのままJSONにする単純なマニフェスト。
    """
    path = os.path.join(data_dir, "archive-index.json")
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"dates": archive_dates}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path
