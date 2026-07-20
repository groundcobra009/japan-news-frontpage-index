# Japan News Frontpage Index

毎朝7時(JST)に全国紙・地方紙の一面・主要見出しを自動収集し、CSV保存・メール・Discordへ配信するGitHub Actionsプロジェクトです。

最終更新：{{LAST_UPDATED}}

## 本日の主要ニュース

### 全国紙

| 新聞社 | 一面・主要見出し | URL |
|---|---|---|
{{NATIONAL_TABLE_ROWS}}

### 地方紙

Phase2で追加予定です([Issue参照](https://github.com/groundcobra009/japan-news-frontpage-index/issues))。

## アーカイブ

{{ARCHIVE_LIST}}

全データは [data/latest.csv](data/latest.csv) からも参照できます。

## 取得状況

{{STATUS_SUMMARY}}

## 収集方針について

各新聞社のrobots.txt・利用規約を確認したうえで、公式RSSまたはrobots.txtで許可された範囲のトップページのみを低頻度(1日1回)で取得しています。新聞紙面そのものの画像や記事全文は保存せず、新聞社名・見出し・公式URL・取得日時のみを扱います。robots.txtで自動収集が許可されていない、または利用規約で自動収集が明示的に禁止されている新聞社は取得対象から除外しています。
