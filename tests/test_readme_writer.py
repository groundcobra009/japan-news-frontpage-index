from src.models.article import STATUS_ERROR, STATUS_OK, STATUS_SKIPPED, Article
from src.outputs.readme_writer import list_archive_dates, render_readme, write_readme

TEMPLATE = """# Title
最終更新：{{LAST_UPDATED}}

{{NATIONAL_TABLE_ROWS}}

{{ARCHIVE_LIST}}

{{STATUS_SUMMARY}}
"""


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


def test_render_readme_includes_representative_headline(tmp_path):
    template_path = tmp_path / "README.template.md"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    articles = [make_article(newspaper="朝日新聞", headline="朝日の見出し", url="https://asahi.example/1")]
    rendered = render_readme(
        articles,
        date="2026-07-21",
        generated_at="2026年7月21日 7:05",
        archive_dates=[],
        template_path=str(template_path),
    )

    assert "最終更新：2026年7月21日 7:05" in rendered
    assert "朝日の見出し" in rendered
    assert "https://asahi.example/1" in rendered
    assert "{{" not in rendered


def test_render_readme_shows_placeholder_when_no_ok_article(tmp_path):
    template_path = tmp_path / "README.template.md"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    articles = [make_article(newspaper="読売新聞", status=STATUS_SKIPPED, headline="", url="")]
    rendered = render_readme(
        articles, date="2026-07-21", generated_at="x", archive_dates=[], template_path=str(template_path)
    )

    assert "読売新聞" in rendered
    assert "(取得できませんでした)" in rendered


def test_render_readme_status_summary_counts_by_newspaper(tmp_path):
    template_path = tmp_path / "README.template.md"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    articles = [
        make_article(newspaper="朝日新聞", status=STATUS_OK),
        make_article(newspaper="読売新聞", status=STATUS_SKIPPED, headline="", url=""),
        make_article(newspaper="毎日新聞", status=STATUS_ERROR, headline="", url="", error_message="timeout"),
    ]
    rendered = render_readme(
        articles, date="2026-07-21", generated_at="x", archive_dates=[], template_path=str(template_path)
    )

    assert "成功：1紙" in rendered
    assert "スキップ：1紙" in rendered
    assert "失敗：1紙" in rendered


def test_render_readme_archive_list_formats_dates_in_japanese(tmp_path):
    template_path = tmp_path / "README.template.md"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    rendered = render_readme(
        [], date="2026-07-21", generated_at="x", archive_dates=["2026-07-21", "2026-07-20"], template_path=str(template_path)
    )

    assert "2026年7月21日" in rendered
    assert "data/2026/07/2026-07-21.csv" in rendered


def test_write_readme_writes_file(tmp_path):
    path = tmp_path / "README.md"
    write_readme("hello", readme_path=str(path))
    assert path.read_text(encoding="utf-8") == "hello"


def test_list_archive_dates_scans_data_dir_sorted_desc(tmp_path):
    (tmp_path / "2026" / "07").mkdir(parents=True)
    (tmp_path / "2026" / "07" / "2026-07-20.csv").write_text("", encoding="utf-8")
    (tmp_path / "2026" / "07" / "2026-07-21.csv").write_text("", encoding="utf-8")
    (tmp_path / "2026" / "07" / "index.csv").write_text("", encoding="utf-8")

    dates = list_archive_dates(data_dir=str(tmp_path))
    assert dates == ["2026-07-21", "2026-07-20"]


def test_list_archive_dates_returns_empty_when_no_data_dir(tmp_path):
    assert list_archive_dates(data_dir=str(tmp_path / "does_not_exist")) == []
