import shutil
from pathlib import Path
from unittest.mock import MagicMock

import src.main as main_module
from src.collectors.robots_guard import RobotsDisallowedError
from src.models.article import STATUS_ERROR, STATUS_OK, STATUS_SKIPPED, Article

RSS_CONFIG = {
    "name": "朝日新聞",
    "key": "asahi",
    "category": "全国紙",
    "region": "全国",
    "source_type": "rss",
    "rss_url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf",
}

FAILING_RSS_CONFIG = {
    "name": "毎日新聞",
    "key": "mainichi",
    "category": "全国紙",
    "region": "全国",
    "source_type": "rss",
    "rss_url": "https://mainichi.jp/rss/etc/mainichi-flash.rss",
}

HTML_DISALLOWED_CONFIG = {
    "name": "東京新聞",
    "key": "tokyo",
    "category": "全国紙",
    "region": "全国",
    "source_type": "html",
    "top_page_url": "https://www.tokyo-np.co.jp/",
    "user_agent": "test-bot/1.0",
}

MANUAL_CONFIG = {
    "name": "読売新聞",
    "key": "yomiuri",
    "category": "全国紙",
    "region": "全国",
    "source_type": "manual",
    "reason": "robots.txtで自動収集禁止",
}


def _sample_article(newspaper: str) -> Article:
    return Article(
        date="2026-07-21",
        collected_at="2026-07-21T07:05:00+09:00",
        category="全国紙",
        region="全国",
        newspaper=newspaper,
        headline="見出し",
        url=f"https://example.com/{newspaper}",
        source_url="https://example.com/",
        status=STATUS_OK,
    )


def test_collect_all_one_rss_failure_does_not_block_others(monkeypatch):
    def fake_collect_rss(config, collected_at, date):
        if config["key"] == "mainichi":
            raise ValueError("network timeout")
        return [_sample_article(config["name"])]

    monkeypatch.setattr(main_module, "collect_rss", fake_collect_rss)

    articles = main_module.collect_all(
        [RSS_CONFIG, FAILING_RSS_CONFIG], collected_at="2026-07-21T07:05:00+09:00", date="2026-07-21"
    )

    by_newspaper = {a.newspaper: a for a in articles}
    assert by_newspaper["朝日新聞"].status == STATUS_OK
    assert by_newspaper["毎日新聞"].status == STATUS_ERROR
    assert "network timeout" in by_newspaper["毎日新聞"].error_message


def test_collect_all_manual_newspaper_is_skipped(monkeypatch):
    articles = main_module.collect_all(
        [MANUAL_CONFIG], collected_at="2026-07-21T07:05:00+09:00", date="2026-07-21"
    )
    assert len(articles) == 1
    assert articles[0].status == STATUS_SKIPPED
    assert articles[0].error_message == "robots.txtで自動収集禁止"


def test_collect_all_html_robots_disallowed_is_skipped_not_error(monkeypatch):
    def fake_collect_html(config, collected_at, date):
        raise RobotsDisallowedError("disallowed by robots.txt")

    monkeypatch.setattr(main_module, "collect_html", fake_collect_html)

    articles = main_module.collect_all(
        [HTML_DISALLOWED_CONFIG], collected_at="2026-07-21T07:05:00+09:00", date="2026-07-21"
    )
    assert len(articles) == 1
    assert articles[0].status == STATUS_SKIPPED


def test_run_end_to_end_writes_csv_with_all_statuses(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_load_config():
        return [RSS_CONFIG, FAILING_RSS_CONFIG, MANUAL_CONFIG]

    def fake_collect_rss(config, collected_at, date):
        if config["key"] == "mainichi":
            raise ValueError("network timeout")
        return [_sample_article(config["name"])]

    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module, "collect_rss", fake_collect_rss)

    main_module.run(date="2026-07-21")

    daily_csv = tmp_path / "data" / "2026" / "07" / "2026-07-21.csv"
    latest_csv = tmp_path / "data" / "latest.csv"
    index_csv = tmp_path / "data" / "2026" / "07" / "index.csv"
    assert daily_csv.exists()
    assert latest_csv.exists()
    assert index_csv.exists()

    content = daily_csv.read_text(encoding="utf-8")
    assert "朝日新聞" in content
    assert "毎日新聞" in content
    assert "読売新聞" in content


def test_run_end_to_end_updates_readme(monkeypatch, tmp_path):
    repo_root = Path(__file__).parent.parent
    shutil.copytree(repo_root / "templates", tmp_path / "templates")
    monkeypatch.chdir(tmp_path)

    def fake_load_config():
        return [RSS_CONFIG, MANUAL_CONFIG]

    def fake_collect_rss(config, collected_at, date):
        return [_sample_article(config["name"])]

    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module, "collect_rss", fake_collect_rss)

    main_module.run(date="2026-07-21")

    readme_path = tmp_path / "README.md"
    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")
    assert "{{" not in content
    assert "朝日新聞" in content
    assert "読売新聞" in content


def test_run_creates_failure_issue_when_error_and_env_configured(monkeypatch, tmp_path):
    repo_root = Path(__file__).parent.parent
    shutil.copytree(repo_root / "templates", tmp_path / "templates")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "groundcobra009/japan-news-frontpage-index")

    def fake_load_config():
        return [FAILING_RSS_CONFIG]

    def fake_collect_rss(config, collected_at, date):
        raise ValueError("network timeout")

    mock_create_issue = MagicMock(return_value={"number": 99})
    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module, "collect_rss", fake_collect_rss)
    monkeypatch.setattr(main_module, "create_github_issue", mock_create_issue)

    main_module.run(date="2026-07-21")

    mock_create_issue.assert_called_once()
    args, kwargs = mock_create_issue.call_args
    title, body = args[0], args[1]
    assert "2026-07-21" in title
    assert "毎日新聞" in body


def test_run_skips_failure_issue_when_env_not_configured(monkeypatch, tmp_path):
    repo_root = Path(__file__).parent.parent
    shutil.copytree(repo_root / "templates", tmp_path / "templates")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    def fake_load_config():
        return [FAILING_RSS_CONFIG]

    def fake_collect_rss(config, collected_at, date):
        raise ValueError("network timeout")

    mock_create_issue = MagicMock()
    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module, "collect_rss", fake_collect_rss)
    monkeypatch.setattr(main_module, "create_github_issue", mock_create_issue)

    main_module.run(date="2026-07-21")

    mock_create_issue.assert_not_called()
