# Japan News Frontpage Index

毎日3回(6時・12時・19時、JST)に全国紙・地方紙の一面・主要見出しを自動収集し、CSV保存・メール・Discordへ配信するGitHub Actionsプロジェクトです。

Web版(過去ニュース検索): https://groundcobra009.github.io/japan-news-frontpage-index/

最終更新：{{LAST_UPDATED}}

## 本日のまとめ

{{DAILY_SUMMARY}}

## 本日の主要ニュース

### 全国紙

| 新聞社 | 一面・主要見出し | URL |
|---|---|---|
{{NATIONAL_TABLE_ROWS}}

### 地方紙

{{LOCAL_TABLES}}

## 本日の重要ニュースTOP10

{{TOP_ARTICLES}}

## 今日の主要キーワード

{{KEYWORDS}}

## アーカイブ

{{ARCHIVE_LIST}}

全データは [data/latest.csv](data/latest.csv) からも参照できます。

## 取得状況

{{STATUS_SUMMARY}}

## 定期実行スケジュール

| ジョブ | 頻度 | 内容 |
|---|---|---|
| 全国紙・地方紙の収集(`daily-news.yml`) | 毎日6時・12時・19時(JST) | ニュース収集・CSV保存・README更新・メール/Discord配信 |
| 週次ヘルスチェック(`claude-code-scheduled-health-check.yml`) | 毎週月曜9時(JST) | テスト実行・取得失敗の傾向確認をClaude(Sonnet)が行い、[Issue #21](https://github.com/groundcobra009/japan-news-frontpage-index/issues/21)へのコメントとメールで報告 |

いずれも`workflow_dispatch`で手動実行・再実行が可能です。

## 収集方針について

各新聞社のrobots.txt・利用規約を確認したうえで、公式RSSまたはrobots.txtで許可された範囲のトップページのみを低頻度で取得しています(1日3回、各紙へのアクセスは1回あたり1リクエスト)。新聞紙面そのものの画像や記事全文は保存せず、新聞社名・見出し・公式URL・取得日時のみを扱います。robots.txtで自動収集が許可されていない、または利用規約で自動収集が明示的に禁止されている新聞社は取得対象から除外しています(manual扱いの新聞社は取得対象外)。

### アグリゲーターからの横断収集

上記の紙別収集に加えて、ニュースアグリゲーター [Ceek.jp News](https://news.ceek.jp/) のカテゴリ別RSSからも横断的に収集しています([config/aggregators.yml](config/aggregators.yml))。取得するのは**見出しと元記事URLのみ**で、フィードに含まれる本文抜粋(`<description>`)はパース時点で破棄し保存しません。ceek.jpのrobots.txtが指定する `Crawl-Delay: 600` を守るため、カテゴリ取得の間に600秒の待機を挟みます(設定値とrobots.txtの申告値のうち長い方を採用)。

アグリゲーター経由で入る通信社・放送局など、`config/newspapers.yml` に登録のない媒体は「その他メディア」として扱い、CSVとWeb版の検索対象には含めますが、本ページの全国紙/地方紙テーブルには並べません。

### 本日のまとめについて

冒頭の「本日のまとめ」は、収集した**見出し(新聞社名と見出し文字列)のみ**をAnthropic社の[Claude API](https://www.anthropic.com/api)へ送信して生成しています。記事全文・紙面画像は送信しません。APIキー未設定時やAPI障害時は、外部送信を一切行わない抽出型のまとめへ自動的にフォールバックします。

取得エラー(ネットワーク障害・パース失敗等)が発生した場合は、自動でGitHub Issueが起票されます(manual紙やrobots.txt Disallowによるスキップは想定内の挙動のため対象外)。

## セットアップ

1. `pip install -r requirements.txt`
2. `.env.example` を参考に環境変数(またはGitHub Secrets)を設定する
3. 手動実行: `python -m src.main`(日付を指定する場合は `src.main.run(date="YYYY-MM-DD")` を呼び出す)
4. テスト実行: `pytest -q`(fixtureベースで実サイトへのネットワークアクセスは行わない)

### 必要なGitHub Secrets

| Secret名 | 用途 |
|---|---|
| `MAIL_TO` | メール送信先 |
| `MAIL_FROM` | メール送信元(例: `Japan News Frontpage Index <onboarding@resend.dev>`) |
| `RESEND_API_KEY` | [Resend](https://resend.com/)のAPIキー |
| `DISCORD_WEBHOOK_URL` | Discord配信先のWebhook URL |
| `ANTHROPIC_API_KEY` | 「本日のまとめ」の生成([Claude API](https://www.anthropic.com/api))。未設定時は抽出型へ自動フォールバック |

いずれかが未設定の場合、該当チャネルへの配信はスキップされ(ログに記録)、他の処理は継続します。

## 新聞社の追加・削除

コード修正不要で [config/newspapers.yml](config/newspapers.yml) の編集のみで行えます。`source_type` は `rss` / `html` / `manual` のいずれかです。`html` を追加する場合は、実装前に対象サイトのrobots.txtと利用規約を確認し、汎用UA(`User-agent: *`)に対して取得対象パスが許可されていることを確認してください。

## Claude Code Actionについて

IssueやPRのコメントで `@claude` とメンションすると、Claude Code(Sonnet)が自動で応答・作業します(`.github/workflows/claude-code-action.yml`)。Anthropic APIキー課金(サブスクリプション不要)で運用しており、`ANTHROPIC_API_KEY` をGitHub Secretsに設定する必要があります。週次ヘルスチェックについては上記「定期実行スケジュール」を参照してください。

## ライセンス

[MIT License](LICENSE)
