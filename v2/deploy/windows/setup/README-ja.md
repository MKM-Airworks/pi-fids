# Windows セミインストーラー（ZIP版）

日英の見やすい手順書は [START-HERE.html](START-HERE.html) をブラウザーで開いてください。日本語・英語の切替と印刷に対応しています。

管理PCは `Install-Manager.cmd`、表示端末は `Install-Display.cmd` を、設置に使うWindowsアカウントで「管理者として実行」します。端末専用接続ファイルは管理PCの `Prepare-Display.cmd` で発行します。詳しい準備・順序・検収・保守は手順書に記載しています。

初回は管理画面で管理者を登録します。⑥ユーザー管理でオペレーター・管理者を追加できます。オペレーターは①・②のみ、管理者は全項目を操作できます。⑦は時刻同期・修正、⑧は監査ログです。便の更新者と変更前後、Web取り込み元・実行ユーザーを記録します。

旧未署名EXE方式は廃止しました。ZIP方式でもWindowsの実行制限が適用される場合があります。保護設定を変更せず、ブロック内容を確認してください。新規PCでの一括導入・再起動検収は未完了です。

## 配布ZIPの作成

Windows用の検証済みPythonランタイムZIP（`runtime/` 配下のみ）と、tzdataを導入したビルド環境を用意します。

```sh
python Build-Payload.py --runtime windows-runtime.zip --output PiFids-Semi-Setup-Windows-x64.zip
```

ビルダーはアプリ・セットアップ・日英HTML手順書・タイムゾーンデータをまとめます。認証情報・端末接続ファイル・運用DBを配布ZIPへ含めません。

## MKM Flight Web — 自動／手動

①のWeb欄で管理者がモードを選択して保存します。初期設定は手動。連携には別途契約・接続設定が必要です。接続状態と確認日時、最終受信・Web公開日時を表示します。自動では画面を閉じても毎分確認し、新しい配信・運航日の便を受信・公開します。同じ配信・運航日は再公開しません。通信・認証・検証失敗や対象期間外では最後の公開を保持します。未公開の手動変更があれば確認・公開を待ちます。同一運航日の遅延・ゲート・実績時刻などは再取り込みでも保持します。自動処理も監査ログに記録します。

An administrator chooses Manual or Automatic reception & publication in section 1. Manual is the default. A separate subscription and connection settings are required. Automatic mode checks every minute even with the browser closed and publishes new versions or service dates. Repeated versions are not republished. Connection, credential, validation or applicability failures preserve the last published data. Unpublished manual edits pause publication until reviewed and published. Same-day local operational overrides are preserved. Automatic changes are audited.
