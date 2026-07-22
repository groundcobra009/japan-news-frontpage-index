"""CSV出力(日付別CSV・latest.csv・月次index.csv・アーカイブ一覧JSON)。"""

from __future__ import annotations

import csv
import json
import os

from src.models.article import CSV_FIELDNAMES, Article


def _write_csv(path: str, articles: list[Article]) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for article in articles:
            writer.writerow(article.to_csv_row())
    return path


def write_daily_csv(articles: list[Article], date: str, data_dir: str = "data") -> str:
    """data/YYYY/MM/YYYY-MM-DD.csv を書く(既存ファイルは上書き、再実行に対応)。"""
    year, month, _ = date.split("-")
    path = os.path.join(data_dir, year, month, f"{date}.csv")
    return _write_csv(path, articles)


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
