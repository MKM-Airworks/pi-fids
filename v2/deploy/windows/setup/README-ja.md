# 表示端末セットアップ（Windows 64bit）

管理PCで登録・接続ファイルを発行し、表示PCで初期設定します。Windows 10/11の64bitとMicrosoft Edge用です。Raspberry Pi用ではありません。

## 1. 管理PCで端末を追加

管理PCの管理・配信サービスを起動しておきます。端末ごとに固有のIDを使います（例 counter-02 / gate-01 / departure-02）。

1. ZIPを管理PCのローカルフォルダーへ展開します。
2. `Prepare-Display.cmd` をダブルクリックします。PowerShellから実行する場合は次のとおりです。パスは展開先に合わせます。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\PiFids-Setup\Prepare-Display.ps1"
```

3. 空港、端末ID、端末名、用途を入力します。画像表示では登録済みの画面を番号で選びます。
4. 完了時に表示された `端末ID.connection.json` を対象の表示PCだけに渡します。

現在の管理PCでは配信先は `http://192.168.11.20:8805`、管理画面は `http://127.0.0.1:8800/` です。別の設置場所では `-Source` と、必要に応じて `-Root` を指定します。管理PCのIPは固定または予約し、LAN配信とNTP時刻サーバーを先に用意します。

端末の登録は管理画面の③、画像切替は②から確認できます。既存の端末IDや名前は上書きしません。発行に失敗した場合は③で途中の登録を確認・削除してからやり直します。

## 2. 表示PCにセットアップ

1. 管理PCと通信できるネットワークに接続し、表示に使うWindowsユーザーでログインします。
2. ZIPを表示PCのローカルフォルダーへ展開し、端末専用の接続ファイルをコピーします。
3. `Install-Display.cmd` を右クリックして「管理者として実行」します。接続ファイルのパスを入力します。PowerShellから実行する場合は、**同じユーザーでWindows PowerShellを「管理者として実行」**し、次を実行します。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\PiFids-Setup\Install-Display.ps1" -ConnectionFile "C:\PiFids-Setup\counter-02.connection.json"
```

別の管理者アカウントで実行すると、そのアカウントのログインに対して設定されます。必ず表示に使うアカウントで実行してください。

セットアップは接続を先に確認し、受信環境、端末専用の接続設定、ログイン時の受信・全画面自動起動、タスクバー自動非表示、管理PCへの時刻同期を設定します。接続キーは画面URLに含めません。既存のインストールは上書きしません。途中で失敗した場合は表示されたエラーを確認し、再実行前に途中のファイル・タスクを確認してください。

初期設定ではWindowsのスリープ設定・自動ログイン・Windows全体の操作制限は変更しません。設置時に電源接続中のスリープと画面消灯を運用に合わせて設定します。電源投入後の表示はWindowsログイン後に始まります。

## 3. 検収

- 表示PCを再起動し、同じユーザーでログインすると全画面が開くこと。
- 管理画面②から表示を切り替え、対象端末だけに反映されること。
- 便一覧では出発・到着、空港名、ロゴ、HH:MMの時計を確認すること。
- `w32tm /query /status` で時刻同期先が管理PCであること。
- 管理PCとの通信を一時的に切っても、保存済みの画面が残ること。

古いHDD端末はログイン後に数分かかる場合があります。画像がない登録や、公開便がない便一覧では内容が出ません。

## 保守

保存先：`%LOCALAPPDATA%\MKM\PiFidsDisplay`。ログは receiver.log と receiver-error.log。元の時刻設定は data\time-before.reg、サービス状態は data\time-service-before.json、タスクバー状態は data\taskbar-before.txt に保存します。

全画面を閉じるときは Alt+F4。受信・自動起動を止めるときはタスクスケジューラで MKM-PiFidsDisplay-Receiver / MKM-PiFidsDisplay-Screen を停止・無効化します。③で登録を削除すると新規受信は止まりますが、端末に保存済みの画像を遠隔消去する操作ではありません。

接続ファイルは端末専用の鍵です。Git、共有資料フォルダー、配布ZIPには入れません。USB等で渡したコピーは設置後に回収します。管理PCの data\lan-auth.json は表示PCへ渡しません。

## 検証範囲

新規セットアップの事前確認モード `-CheckOnly` は登録・接続を確認するだけでOS・タスク・ファイルを変更しません。現在使用中のWin10端末ではこの事前確認を試し、受信・全画面・ログイン自動起動は既存構成で実機確認済みです。新規端末への一括インストールと、その再起動確認は追加端末の設置時に実施します。
