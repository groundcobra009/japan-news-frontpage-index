import csv
import json
import os

from src.models.article import STATUS_ERROR, STATUS_OK, Article
from src.outputs.csv_writer import (
    append_index_csv,
    read_articles_csv,
    write_archive_manifest,
    write_daily_csv,
    write_daily_summary,
    write_latest_csv,
    write_latest_summary,
)


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


def _read_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_write_daily_csv_merges_articles_from_later_runs(tmp_path):
    """1日3回実行するため、後の実行が前の実行の記事を消してはいけない。"""
    write_daily_csv([make_article(url="https://example.com/1")], date="2026-07-21", data_dir=str(tmp_path))
    path = write_daily_csv(
        [make_article(url="https://example.com/2")], date="2026-07-21", data_dir=str(tmp_path)
    )
    rows = _read_rows(path)
    assert len(rows) == 2
    assert {r["url"] for r in rows} == {"https://example.com/1", "https://example.com/2"}


def test_write_daily_csv_keeps_first_collected_at_for_duplicate(tmp_path):
    write_daily_csv(
        [make_article(collected_at="2026-07-21T06:00:00+09:00")], date="2026-07-21", data_dir=str(tmp_path)
    )
    path = write_daily_csv(
        [make_article(collected_at="2026-07-21T12:00:00+09:00")], date="2026-07-21", data_dir=str(tmp_path)
    )
    rows = _read_rows(path)
    assert len(rows) == 1
    assert rows[0]["collected_at"] == "2026-07-21T06:00:00+09:00"


def test_write_daily_csv_replaces_stale_error_row_when_paper_recovers(tmp_path):
    """朝の失敗行が復旧後も残り続けてerror_countを膨らませないこと。"""
    write_daily_csv(
        [make_article(newspaper="毎日新聞", headline="", url="", status=STATUS_ERROR, error_message="timeout")],
        date="2026-07-21",
        data_dir=str(tmp_path),
    )
    path = write_daily_csv(
        [make_article(newspaper="毎日新聞", headline="復旧後の見出し", url="https://example.com/m1")],
        date="2026-07-21",
        data_dir=str(tmp_path),
    )
    rows = _read_rows(path)
    assert len(rows) == 1
    assert rows[0]["status"] == STATUS_OK


def test_write_daily_csv_merge_existing_false_overwrites(tmp_path):
    write_daily_csv([make_article(url="https://example.com/1")], date="2026-07-21", data_dir=str(tmp_path))
    path = write_daily_csv(
        [make_article(url="https://example.com/2")],
        date="2026-07-21",
        data_dir=str(tmp_path),
        merge_existing=False,
    )
    rows = _read_rows(path)
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/2"


def test_read_articles_csv_tolerates_missing_topic_column(tmp_path):
    """topic列導入以前のアーカイブCSVも読み戻せること。"""
    path = tmp_path / "old.csv"
    path.write_text(
        "date,collected_at,category,region,newspaper,headline,url,source_url,status,error_message\n"
        "2026-07-21,x,全国紙,全国,朝日新聞,見出し,https://example.com/1,https://example.com/,ok,\n",
        encoding="utf-8",
    )
    articles = read_articles_csv(str(path))
    assert len(articles) == 1
    assert articles[0].topic == ""


def test_write_daily_summary_and_latest_summary(tmp_path):
    daily = write_daily_summary(
        "本日のまとめ本文", "2026-07-21", source="claude", generated_at="x", data_dir=str(tmp_path)
    )
    assert daily == str(tmp_path / "2026" / "07" / "2026-07-21.summary.json")
    payload = json.loads(open(daily, encoding="utf-8").read())
    assert payload == {
        "date": "2026-07-21",
        "summary": "本日のまとめ本文",
        "source": "claude",
        "generated_at": "x",
    }
    # 日本語がエスケープされずそのまま書かれること(archive-index.jsonと同じ流儀)。
    assert "本日のまとめ本文" in open(daily, encoding="utf-8").read()

    latest = write_latest_summary("あとの内容", "2026-07-21", data_dir=str(tmp_path))
    assert latest == str(tmp_path / "summary-latest.json")
    assert json.loads(open(latest, encoding="utf-8").read())["summary"] == "あとの内容"


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
