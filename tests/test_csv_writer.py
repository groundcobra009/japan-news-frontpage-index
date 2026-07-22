import csv
import json
import os

from src.models.article import STATUS_ERROR, STATUS_OK, Article
from src.outputs.csv_writer import append_index_csv, write_archive_manifest, write_daily_csv, write_latest_csv


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


def test_write_daily_csv_creates_file_with_expected_rows(tmp_path):
    articles = [make_article(), make_article(newspaper="毎日新聞", status=STATUS_ERROR, error_message="timeout")]
    path = write_daily_csv(articles, date="2026-07-21", data_dir=str(tmp_path))

    assert path == str(tmp_path / "2026" / "07" / "2026-07-21.csv")
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["newspaper"] == "朝日新聞"
    assert rows[1]["status"] == STATUS_ERROR
    assert rows[1]["error_message"] == "timeout"


def test_write_daily_csv_overwrites_on_rerun(tmp_path):
    write_daily_csv([make_article()], date="2026-07-21", data_dir=str(tmp_path))
    path = write_daily_csv([make_article(), make_article()], date="2026-07-21", data_dir=str(tmp_path))
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2


def test_write_latest_csv(tmp_path):
    path = write_latest_csv([make_article()], data_dir=str(tmp_path))
    assert path == str(tmp_path / "latest.csv")
    assert os.path.exists(path)


def test_append_index_csv_adds_new_date(tmp_path):
    path = append_index_csv(
        date="2026-07-21",
        article_count=10,
        ok_count=8,
        skipped_count=1,
        error_count=1,
        data_dir=str(tmp_path),
    )
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-07-21"
    assert rows[0]["article_count"] == "10"


def test_append_index_csv_replaces_same_date_on_rerun(tmp_path):
    append_index_csv("2026-07-21", 10, 8, 1, 1, data_dir=str(tmp_path))
    path = append_index_csv("2026-07-21", 12, 9, 2, 1, data_dir=str(tmp_path))
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["article_count"] == "12"


def test_append_index_csv_accumulates_multiple_dates_sorted(tmp_path):
    append_index_csv("2026-07-22", 5, 5, 0, 0, data_dir=str(tmp_path))
    path = append_index_csv("2026-07-21", 10, 8, 1, 1, data_dir=str(tmp_path))
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["date"] for r in rows] == ["2026-07-21", "2026-07-22"]


def test_write_archive_manifest_writes_json_with_dates(tmp_path):
    path = write_archive_manifest(["2026-07-22", "2026-07-21"], data_dir=str(tmp_path))
    assert path == str(tmp_path / "archive-index.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"dates": ["2026-07-22", "2026-07-21"]}


def test_write_archive_manifest_overwrites_on_rerun(tmp_path):
    write_archive_manifest(["2026-07-20"], data_dir=str(tmp_path))
    path = write_archive_manifest(["2026-07-22", "2026-07-21"], data_dir=str(tmp_path))
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["dates"] == ["2026-07-22", "2026-07-21"]
