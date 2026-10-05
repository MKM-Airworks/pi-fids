# Windows表示端末のKiosk起動

表示端末はEdgeのデジタルサイネージ用Kioskモードで起動する。Web画面の全画面ボタンを操作する運用にはしない。管理・設定は管理用PCで行う。

## 起動試作

ローカル受信・表示サーバーを起動した状態で実行する。

```powershell
.\Start-PiFidsKiosk.ps1 -Airport ROR -DisplayId gate-01
```

localhostの表示画面をEdgeのKiosk全画面で開く。画面内の操作リンク・設定・版情報を隠し、画面全体に表示する。`kiosk=1` は表示UIの指定で、Windowsの操作制限そのものではない。x86/x64のEdgeインストール先を検出する。OS設定、自動ログイン、タスク登録、プロセス監視を変更しない。Windows実機ではまだ未検証。

## 本番構成

電源投入 → 表示専用アカウントでログイン → ローカル受信サービス開始 → Edge Kiosk開始。通常利用用のEdgeと表示用セッションを分ける。既存OSのエディション・更新状況を確認し、Assigned Accessを利用できる場合は表示専用アカウントへ割り当てる。利用できない端末ではログオン時の起動タスクと監視で全画面起動を実現するが、これは同じ強度のWindows操作制限ではない。自動ログイン・スリープ抑制・異常終了からの再起動・保守時の解除は実機検証後に導入手順として実装する。

重要：Edge KioskはInPrivateセッションで動作する。前段の通常ブラウザ試験で確認したCache Storage/localStorageの保存を、ブラウザ終了やOS再起動後の保持として当てにしない。本番では受信サービスが画像と公開版を端末ディスクへ保存し、通信断時もlocalhostで配信する必要がある。独立した受信サービスは未実装で、現在の試作サーバーは管理DBから表示するまで。

Microsoft公式仕様：[Edge Kiosk構成](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-configure-kiosk-mode)。EdgeのKiosk指定だけでは電源投入時の自動起動や異常終了後の再起動は完了しない。
