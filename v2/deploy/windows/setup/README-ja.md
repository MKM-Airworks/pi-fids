# Windows セミインストーラー（ZIP版）

日英の見やすい手順書は [START-HERE.html](START-HERE.html) をブラウザーで開いてください。日本語・英語の切替と印刷に対応しています。

管理PCは `Install-Manager.cmd`、表示端末は `Install-Display.cmd` を、設置に使うWindowsアカウントで「管理者として実行」します。端末専用接続ファイルは管理PCの `Prepare-Display.cmd` で発行します。詳しい準備・順序・検収・保守は手順書に記載しています。

旧未署名EXE方式は廃止しました。ZIP方式でもWindowsの実行制限が適用される場合があります。保護設定を変更せず、ブロック内容を確認してください。新規PCでの一括導入・再起動検収は未完了です。

## 配布ZIPの作成

Windows用の検証済みPythonランタイムZIP（`runtime/` 配下のみ）と、tzdataを導入したビルド環境を用意します。

```sh
python Build-Payload.py --runtime windows-runtime.zip --output PiFids-Semi-Setup-Windows-x64.zip
```

ビルダーはアプリ・セットアップ・日英HTML手順書・タイムゾーンデータをまとめます。認証情報・端末接続ファイル・運用DBを配布ZIPへ含めません。
