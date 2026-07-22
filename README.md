# Japan News Frontpage Index

毎朝7時(JST)に全国紙・地方紙の一面・主要見出しを自動収集し、CSV保存・メール・Discordへ配信するGitHub Actionsプロジェクトです。

最終更新：2026年07月22日 11:36

## 本日の主要ニュース

### 全国紙

| 新聞社 | 一面・主要見出し | URL |
|---|---|---|
| 読売新聞 | (取得できませんでした) | - |
| 朝日新聞 | 緑ナンバーで偽装し「白タク営業」疑い、名義貸しか 会社代表ら逮捕 | [記事を読む](http://www.asahi.com/articles/ASV7P52Z7V7PUTIL021M.html) |
| 毎日新聞 | 漬物石を滑らせて カーリングならぬスライドストーンの魅力 | [記事を読む](https://mainichi.jp/articles/20260719/k00/00m/040/269000c) |
| 日本経済新聞 | (取得できませんでした) | - |
| 産経新聞 | 次期戦闘機にカナダ参加 日英伊、初のオブザーバー 機密共有、輸出先確保へ | [記事を読む](https://www.sankei.com/article/20260722-VU66ELHE3VPW5AVZ5WRXVQLC6U/) |
| 東京新聞 | 政府「骨太方針」で弾薬工場の「公設民営化」検討へ 「平和ブランドを掲げてきた国が...」識者から疑問の声 | [記事を読む](https://www.tokyo-np.co.jp/article/502750) |
| 中日新聞 | 酷暑日はほとんどの人が経験したことがない別世界 不要不急の外出やめクーラーの効いた屋内に退避を | [記事を読む](https://www.chunichi.co.jp/article/1284557) |

### 地方紙

(まだ地方紙のデータがありません)

## 本日の重要ニュースTOP10

1. **東京新聞**: 〈動画〉望月衣塑子が行く 高市政権の「終わりの始まり」? 支持率下落で痛烈批判...立憲・水岡代表 ([記事を読む](https://www.tokyo-np.co.jp/article/502700))
2. **朝日新聞**: 下ろされた「健全化の旗」 高市政権で転換した財政運営 骨太の方針 ([記事を読む](http://www.asahi.com/articles/ASV7P2FSSV7PULFA047M.html))
3. **毎日新聞**: 日英伊の次期戦闘機、カナダが初のオブザーバー 開発費低減狙う ([記事を読む](https://mainichi.jp/articles/20260721/k00/00m/030/409000c))
4. **産経新聞**: 次期戦闘機にカナダ参加 日英伊、初のオブザーバー 機密共有、輸出先確保へ ([記事を読む](https://www.sankei.com/article/20260722-VU66ELHE3VPW5AVZ5WRXVQLC6U/))
5. **産経新聞**: 政府が外国と疑われる不審アカウント把握 高市首相「選挙への影... ([記事を読む](https://www.sankei.com/article/20260318-U6PW4754BNE3XKFYBTQWPKM65A/))
6. **東京新聞**: 日英伊の次期戦闘機にカナダ参加 初のオブザーバー ([記事を読む](https://www.tokyo-np.co.jp/article/502803))
7. **朝日新聞**: 緑ナンバーで偽装し「白タク営業」疑い、名義貸しか 会社代表ら逮捕 ([記事を読む](http://www.asahi.com/articles/ASV7P52Z7V7PUTIL021M.html))
8. **朝日新聞**: 殺人事件の被告から「口止め料」脅し取った疑い 無職の男を逮捕 ([記事を読む](http://www.asahi.com/articles/ASV7P34Q4V7PUTIL01XM.html))
9. **東京新聞**: 政府「骨太方針」で弾薬工場の「公設民営化」検討へ 「平和ブランドを掲げてきた国が...」識者から疑問の声 ([記事を読む](https://www.tokyo-np.co.jp/article/502750))
10. **毎日新聞**: やまゆり園事件10年:やまゆり園で重傷の息子、今は地域で 父が感じる障害者の幸せ ([記事を読む](https://mainichi.jp/articles/20260721/k00/00m/040/119000c))

## 今日の主要キーワード

- 代表
- 動画
- 疑い
- 政権
- 高市

## アーカイブ

- [2026年7月22日](data/2026/07/2026-07-22.csv)

全データは [data/latest.csv](data/latest.csv) からも参照できます。

## 取得状況

- 成功：5紙
- スキップ：2紙
- 失敗：0紙

## 収集方針について

各新聞社のrobots.txt・利用規約を確認したうえで、公式RSSまたはrobots.txtで許可された範囲のトップページのみを低頻度(1日1回)で取得しています。新聞紙面そのものの画像や記事全文は保存せず、新聞社名・見出し・公式URL・取得日時のみを扱います。robots.txtで自動収集が許可されていない、または利用規約で自動収集が明示的に禁止されている新聞社は取得対象から除外しています(manual扱いの新聞社は取得対象外)。

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
| `MAIL_FROM` | メール送信元(Gmailアドレス) |
| `SMTP_HOST` | SMTPホスト(Gmailの場合 `smtp.gmail.com`) |
| `SMTP_PORT` | SMTPポート(Gmailの場合 `465`) |
| `SMTP_USERNAME` | SMTPユーザー名(Gmailアドレス) |
| `SMTP_PASSWORD` | SMTPパスワード(Gmailの場合はアプリパスワード) |
| `DISCORD_WEBHOOK_URL` | Discord配信先のWebhook URL |

いずれかが未設定の場合、該当チャネルへの配信はスキップされ(ログに記録)、他の処理は継続します。

## 新聞社の追加・削除

コード修正不要で [config/newspapers.yml](config/newspapers.yml) の編集のみで行えます。`source_type` は `rss` / `html` / `manual` のいずれかです。`html` を追加する場合は、実装前に対象サイトのrobots.txtと利用規約を確認し、汎用UA(`User-agent: *`)に対して取得対象パスが許可されていることを確認してください。

## ライセンス

[MIT License](LICENSE)
