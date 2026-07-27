import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import src.main as main_module
from src.collectors.ceek_collector import AggregatorFailure, CeekResult
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


def _sample_article(newspaper: str, url: str | None = None) -> Article:
    return Article(
        date="2026-07-21",
        collected_at="2026-07-21T07:05:00+09:00",
        category="全国紙",
        region="全国",
        newspaper=newspaper,
        headline="見出し",
        url=url or f"https://example.com/{newspaper}",
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
    # 同名のopen Issueが無い状態を模す(実APIを叩かせない)。
    monkeypatch.setattr(main_module, "find_open_issue_by_title", MagicMock(return_value=None))

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


AGGREGATOR_CONFIG = {
    "name": "Ceek.jp News",
    "key": "ceek",
    "source_type": "ceek",
    "feed_url_template": "https://news.ceek.jp/search.cgi?category_id={category_id}&feed=1",
    "user_agent": "test-bot/1.0",
    "categories": ["politics"],
}


def _setup_repo(monkeypatch, tmp_path):
    repo_root = Path(__file__).parent.parent
    shutil.copytree(repo_root / "templates", tmp_path / "templates")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(main_module, "load_config", lambda: [RSS_CONFIG, MANUAL_CONFIG])
    monkeypatch.setattr(
        main_module, "collect_rss", lambda config, collected_at, date: [_sample_article(config["name"])]
    )


def test_run_end_to_end_writes_summary_files(monkeypatch, tmp_path):
    _setup_repo(monkeypatch, tmp_path)
    main_module.run(date="2026-07-21")

    latest = json.loads((tmp_path / "data" / "summary-latest.json").read_text(encoding="utf-8"))
    daily = json.loads((tmp_path / "data" / "2026" / "07" / "2026-07-21.summary.json").read_text(encoding="utf-8"))
    # conftestがANTHROPIC_API_KEYを外すため、必ず抽出型になる。
    assert latest["source"] == "extractive"
    assert daily["date"] == "2026-07-21"
    assert latest["summary"]

    content = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "## 本日のまとめ" in content
    assert "{{" not in content


def test_run_does_not_call_anthropic_when_key_missing(monkeypatch, tmp_path):
    _setup_repo(monkeypatch, tmp_path)
    post = MagicMock()
    monkeypatch.setattr("requests.post", post)

    main_module.run(date="2026-07-21")
    post.assert_not_called()


def test_run_calls_anthropic_when_key_set(monkeypatch, tmp_path):
    _setup_repo(monkeypatch, tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    response = MagicMock()
    response.json.return_value = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "まとめ本文。"}]}
    post = MagicMock(return_value=response)
    monkeypatch.setattr("requests.post", post)

    main_module.run(date="2026-07-21")

    assert post.call_args.args[0] == "https://api.anthropic.com/v1/messages"
    latest = json.loads((tmp_path / "data" / "summary-latest.json").read_text(encoding="utf-8"))
    assert latest["source"] == "claude"
    assert latest["summary"] == "まとめ本文。"


def test_run_survives_summarizer_exception(monkeypatch, tmp_path):
    _setup_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(main_module, "build_summary", MagicMock(side_effect=RuntimeError("boom")))

    main_module.run(date="2026-07-21")

    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "data" / "latest.csv").exists()


def test_run_includes_aggregator_articles(monkeypatch, tmp_path):
    _setup_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(main_module, "load_aggregator_config", lambda: [AGGREGATOR_CONFIG])

    def fake_collect_ceek(config, collected_at, date, newspaper_index=None):
        return CeekResult(
            articles=[
                Article(
                    date=date,
                    collected_at=collected_at,
                    category="その他メディア",
                    region="",
                    newspaper="共同通信",
                    headline="通信社の見出し",
                    url="https://www.47news.jp/1.html",
                    source_url="https://news.ceek.jp/search.cgi?category_id=politics&feed=1",
                    status=STATUS_OK,
                )
            ],
            fetched_categories=["politics"],
        )

    monkeypatch.setattr(main_module, "collect_ceek", fake_collect_ceek)
    main_module.run(date="2026-07-21")

    csv_text = (tmp_path / "data" / "latest.csv").read_text(encoding="utf-8")
    assert "共同通信" in csv_text
    # 紙別テーブルには出さない。
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| 共同通信 |" not in readme


def test_run_does_not_open_issue_when_only_aggregator_fails(monkeypatch, tmp_path):
    """アグリゲーターの失敗で架空の新聞社名のIssueが起票されないこと。"""
    _setup_repo(monkeypatch, tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "groundcobra009/japan-news-frontpage-index")
    monkeypatch.setattr(main_module, "load_aggregator_config", lambda: [AGGREGATOR_CONFIG])

    def failing_collect_ceek(config, collected_at, date, newspaper_index=None):
        return CeekResult(
            failures=[AggregatorFailure("Ceek.jp News", "politics", "https://news.ceek.jp/x", "boom")]
        )

    create_issue = MagicMock()
    monkeypatch.setattr(main_module, "collect_ceek", failing_collect_ceek)
    monkeypatch.setattr(main_module, "create_github_issue", create_issue)

    main_module.run(date="2026-07-21")
    create_issue.assert_not_called()


def test_run_merges_daily_csv_across_runs(monkeypatch, tmp_path):
    """1日3回実行で、後の実行が前の実行の記事を消さないこと。"""
    _setup_repo(monkeypatch, tmp_path)

    monkeypatch.setattr(
        main_module,
        "collect_rss",
        lambda config, collected_at, date: [_sample_article(config["name"], url="https://example.com/朝")],
    )
    main_module.run(date="2026-07-21")

    monkeypatch.setattr(
        main_module,
        "collect_rss",
        lambda config, collected_at, date: [_sample_article(config["name"], url="https://example.com/昼")],
    )
    main_module.run(date="2026-07-21")

    csv_text = (tmp_path / "data" / "2026" / "07" / "2026-07-21.csv").read_text(encoding="utf-8")
    assert "https://example.com/%E6%9C%9D" in csv_text or "https://example.com/朝" in csv_text
    assert "https://example.com/%E6%98%BC" in csv_text or "https://example.com/昼" in csv_text


def test_run_comments_on_existing_failure_issue_instead_of_duplicating(monkeypatch, tmp_path):
    """同一原因で毎回Issueを起票せず、既存のopen Issueへコメントすること。"""
    repo_root = Path(__file__).parent.parent
    shutil.copytree(repo_root / "templates", tmp_path / "templates")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "groundcobra009/japan-news-frontpage-index")

    def fake_collect_rss(config, collected_at, date):
        raise ValueError("network timeout")

    mock_create_issue = MagicMock()
    mock_comment = MagicMock()
    monkeypatch.setattr(main_module, "load_config", lambda: [FAILING_RSS_CONFIG])
    monkeypatch.setattr(main_module, "collect_rss", fake_collect_rss)
    monkeypatch.setattr(main_module, "create_github_issue", mock_create_issue)
    monkeypatch.setattr(main_module, "find_open_issue_by_title", MagicMock(return_value={"number": 42}))
    monkeypatch.setattr(main_module, "add_issue_comment", mock_comment)

    main_module.run(date="2026-07-21")

    mock_create_issue.assert_not_called()
    mock_comment.assert_called_once()
    assert mock_comment.call_args.args[0] == 42
