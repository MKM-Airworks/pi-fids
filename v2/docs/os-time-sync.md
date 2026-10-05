# 空港内LANでOS時計を同期する

管理PCをローカルNTPサーバーにし、Windows 10/11とRaspberry PiのOS時計を同期する。インターネットへの接続は不要。基準時計は管理PCのOS時計とする。管理PC自体がインターネットへ接続しない場合は、正しい時刻を運用で確認して修正する。

## Windows管理PC

初回のみ管理者権限で `scripts/windows/Setup-Time-Server.ps1 -OperatorAccount "PC名\運用ユーザー"` を実行する。Windows TimeサービスのNTPサーバーを有効にし、空港LANからのUDP 123を許可する。既定はPrivate/DomainネットワークのLocalSubnetだけに限定する。別サブネットは `-AllowedSubnet` で指定する。ドメイン参加PCはこのスクリプトでは変更せず、既存ドメインの時刻管理方針に従う。

この初期設定はオフライン基準時計（NoSync）用。外部NTPへ同期する管理PCでは、その既存設定を保つ方式を別途調整する。

OS時刻修正のため、SYSTEM権限の小さな補助プロセスを起動時タスクに登録する。通常のFIDS管理画面は管理者権限で動かさない。補助プロセスは127.0.0.1だけで待受し、秘密キーを要求する。できる操作は状態取得とUTC時刻の設定だけ。スクリプト・秘密キーの保存先をSYSTEM／Administratorsだけが変更できるようにし、指定した運用ユーザーには読み取りを許可する。

FIDS管理サーバーはログイン認証（`--auth-config`）を必須とし、`--clock-service "C:\ProgramData\PiFIDS-Clock\connection.json"` を指定する。5番の画面はOS時刻修正サービス、Windows Timeサービス、NTPサーバーの設定状態を表示する。サービスへ接続できる場合だけ「管理PCのOS時刻を修正」を有効にする。空港現地時刻（SHI/RORともUTC+09:00）をUTCへ変換してOS時計を修正する。時刻修正は便一覧の表示終了・ログ・セッション時刻に影響し、大きな変更時は再ログインが必要になる場合がある。

## Windows表示端末

初回のみ管理者権限で `scripts/windows/Setup-Time-Client.ps1 -TimeServer 管理PCのIPアドレス` を実行する。Windows Timeサービスを自動起動にし、LAN管理PCをNTP接続先として設定する。ポーリングは64秒を指定する。同期元と状態は `w32tm /query /source`、`w32tm /query /status` で確認する。スクリプトは32bit／64bit共通で、OSの入替は不要。

## Raspberry Pi表示端末

systemd-timesyncdがある端末で `sudo sh scripts/pi/setup-time-client.sh 管理PCのIPアドレス` を実行する。LAN管理PCだけをNTP接続先にし、ポーリングは32～64秒とする。chrony等が既に動いている端末は停止せず、その既存サービスの同期先を変更する。スクリプトは既存NTPデーモンが稼働していれば変更を中止する。

## FIDSの表示用時計

便情報取得時にも管理PCのUTC時刻を送り、表示用時計を補助的に合わせる。これはOS同期の代わりではなく、NTP同期までの表示のずれを抑える処理。OSの時刻同期設定は上記の手順で行う。OS修正後に表示端末が追従するタイミングはNTPの次回ポーリングとなる。

5番で確認できるのは管理PCの時刻サービス状態。全端末のNTP同期成功を確認する監視機能は含まれず、導入時に各端末の同期元・同期結果を確認する。

MacのプレビューではOS修正サービスがなく、OS時刻変更は無効。Windows実機でのPowerShellの実行、再起動後のサービス起動、NTP配信、32bit／64bit端末の同期、Webからの時刻修正は本宅で検証する。現時点の自動試験はサービス連携を模擬し、実際のPC時計は変更していない。

参考: [Windows Time Service Tools and Settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings)、[Configure an authoritative time server](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/configure-authoritative-time-server)。
