# Pi-FIDS V2 — 試験版 / Preview

空港の便一覧とチェックイン・ゲート案内を管理・表示するシステムです。
V2の開発・導入資料はこのブランチ `develop/v2` にまとめています。

Airport flight boards and check-in/gate signage management. V2 development and setup documentation are on `develop/v2`.

## 導入・ダウンロード / Setup & downloads

- **[最新版ZIP・配布ページ / Releases](https://github.com/MKM-Airworks/pi-fids/releases)**
- **[日英セットアップ手順書 / Japanese & English setup guide](v2/deploy/windows/setup/START-HERE.html)** — ZIP展開後、`START-HERE.html` をブラウザーで開いてください。言語切替・印刷に対応しています。Download/extract the ZIP and open `START-HERE.html` in your browser.
- [Windowsセットアップの概要 / Windows setup overview](v2/deploy/windows/setup/README-ja.md)
- [V2の概要 / V2 overview](v2/README.md)

## V2でできること / Features

- 管理PCから出発・到着便一覧、ロゴ、カウンター・ゲート画像を管理
- 登録済み表示端末の一覧・表示切替・設定変更・削除
- 表示端末のローカル受信、保存済み画面、Edge Kiosk表示
- 管理者・オペレーターのログインと権限管理（③以降は管理者のみ）
- 便の更新者・変更前後とMKM Flight Web取り込みを記録する監査ログ
- Windowsログイン後の自動起動と管理PCへの時刻同期
- 設置空港の3レターコード・IANAタイムゾーンを指定

Flight boards, airline logos, counter/gate signage, registered terminal management, local display receivers, cached screens, Edge kiosk, startup after Windows login, and time synchronization. Configure a three-letter airport code and IANA time zone for each installation.

## 現在の状態 / Status

**試験版です。新規PCへの一括導入と再起動検収は未完了です。** 現在稼働している試験環境への上書き導入には使わないでください。Windows用の配布はZIP形式のセミインストーラーです。旧未署名EXE形式は廃止しました。

**Preview: end-to-end installation and restart acceptance on a new PC remain to be completed.** Do not install over the existing working trial environment. Windows distribution uses ZIP setup; the previous unsigned installer EXE has been retired.

端末専用接続ファイル・認証情報・運用DBは配布物やGitへ含めません。MKM Flight Webの利用権限・接続設定は別途必要です。

Terminal credentials and operational databases are excluded from distribution and Git. MKM Flight Web permissions and connection settings are separate.

## ブランチ / Branches

- `develop/v2`：V2の開発・試験版。既定ブランチ / V2 development and preview; default branch.
- `main`：従来版。V2はまだマージしていません / Legacy version; V2 has not been merged here.
