# バックアップ・復元 / Backup & recovery

初期実装：手動バックアップ、管理者専用の検証・復元準備。自動複製・自動バックアップ・主系待機系の引継ぎは後続実装です。既存①〜⑧は変更せず、追加メニュー「バックアップ・復元」を使用します。

Initial implementation: manual backup and administrator-only validation/recovery preparation. Automatic replication, scheduled backup and primary/standby takeover are not implemented. Existing sections 1–8 remain unchanged.

## 保存 / Save

1. 管理者でログインし、「バックアップ・復元」→「バックアップを作成」。
2. 作成日時を確認し、一覧からZIPをダウンロード。USBなど管理PC外の安全な場所へコピーしてください。
3. 変更後と業務終了時に作成してください。この版は自動削除・自動世代管理を行いません。バックアップには保存時点の監査ログが残るため、稼働DBの監査ログ保存期間とは別に、媒体の保管・廃棄期限を定めます。

1. Sign in as administrator. Open **Backup & recovery → Create backup**.
2. Check the creation time, download the ZIP and keep a secure copy outside the manager PC, for example on USB.
3. Create a backup after changes and at the end of operations. This version does not schedule or prune backups. Audit retention on the live database does not erase records inside old backups; set a separate media retention/disposal policy.

保存内容：便の下書き・公開情報、画像、航空会社・空港名、端末と表示時間・Default画像・言語などの設定、ユーザーと権限・パスワードハッシュ、端末キーのハッシュ、監査ログ・保存期間、Web取得済みデータと履歴。画像はDB内にあり、SQLiteのバックアップAPIで一貫したスナップショットを作成します。ログインセッション・平文パスワード・Web受信トークン・端末側接続ファイル・OS時刻サービスの秘密情報は含めません。

Includes drafts, published flights, images, airline/airport names, terminal/display schedules/default images/languages, users/roles/password hashes, terminal key hashes, audit records/retention and cached Web data/history. Images are stored in SQLite; its backup API produces a consistent snapshot. Sessions, plaintext passwords, Web tokens, terminal-side connection files and OS clock helper secrets are excluded.

ZIPは暗号化されません。ユーザーハッシュと業務データを含む機密ファイルとして扱い、GitHub・共有資料フォルダーへ保存しないでください。生成ファイルはPOSIXで所有者限定。Windowsでは設置先フォルダーと保存媒体のアクセス権を管理者・実行アカウントに限定してください。SHA-256は破損検出であり、発行元の電子署名ではありません。自分で保管した信頼できるバックアップだけを使います。

ZIPs are not encrypted. Treat them as confidential because they include account hashes and operational data. Do not commit them or put them in shared documentation folders. POSIX files are owner-only; restrict Windows installation/media permissions to administrators and the service account. SHA-256 detects corruption, not provenance. Restore only trusted backups you retained.

## 内容の確認 / Review

「復元前の確認」でZIPを選び「内容を検証」。空港、作成日時、公開便数、画像数、端末数、ユーザー数を確認します。同じ空港・対応するDB構造、全ファイルのハッシュ、DB整合性、画像と参照、ユーザー権限を検証します。別空港・破損・画像欠落・未対応構造は拒否します。128MBが上限です。

Choose the ZIP under **Review before recovery → Validate contents**. Review the airport, creation time and counts. Checks cover matching airport/supported schema, file hashes, SQLite integrity, images/references and user roles. Other airports, corruption, missing images and unsupported schemas are rejected. Maximum size: 128 MB.

「別フォルダーへ復元を準備」を実行すると、バックアップ保存先内の新しい `recovery-…` フォルダーに展開します。稼働中のDBは上書きしません。Web自動受信・公開は手動へ戻し、旧PCの仮想時刻補正を消去します。画像・既存ユーザー・端末キーのハッシュは復元します。旧バックアップ以降に変更した端末キーは、復元後に再発行が必要です。

**Prepare recovery in a separate folder** creates a new `recovery-…` directory under the backup directory. It never overwrites the running database. Web automatic publication is reset to manual and the old virtual clock offset is cleared. Images, users and terminal key hashes are restored. Keys changed after the backup may need reissue.

## 故障したPCとは別のWindows PCで準備 / Prepare on a replacement Windows PC

同じ現行版の管理PC用セミインストーラーを導入します。復元したデータで起動するまでは、新規インストールの管理サービスを停止してください。ZIPをコピーし、同梱のPrepare-Recovery.ps1で新しいフォルダーへ検証・展開します。Windowsのファイル権限を確認します。

Install the same current manager semi-installer on the replacement PC. Stop its newly installed management service before starting recovery data. Copy the ZIP and use the bundled Prepare-Recovery.ps1 to validate/extract into a new directory. Check Windows file permissions.

```powershell
.\Prepare-Recovery.ps1 -Backup 'E:\PiFIDS-backup.zip' -Airport SHI -Output "$env:LOCALAPPDATA\MKM\Recovery-SHI"
.\Start-Recovered-Manager.ps1 -RecoveryFolder "$env:LOCALAPPDATA\MKM\Recovery-SHI"
```

既定ではLAN配信なし・localhostの8810番で起動します。`http://127.0.0.1:8810/` を開き、復元されたユーザーでログインして便・画像・端末設定を確認してください。コマンド画面を閉じると停止します。これは準備・確認用起動で、自動起動タスクを変更しません。

Default launch is localhost port 8810 without LAN feed. Open `http://127.0.0.1:8810/`, sign in with a restored user and review flights, images and terminal settings. Keep the console open. This verification launcher does not alter scheduled startup tasks.

## 配信再開前 / Before resuming distribution

1. 旧主系を電源OFFまたはLAN切離し。旧PCは後で勝手に再起動・配信させないでください。この版に自動的な二重配信防止はありません。
2. 復旧PCのLAN IP・配信ポート・ファイアウォールを確認。表示端末側の接続先を新PCへ変更し、必要な端末キーを再発行します。
3. Web連携が必要なら、復元フォルダーの `web-connection.template.json` を `web-connection.json` としてコピーし、指定された `web-credential.json` に管理者が受信トークンを安全に再設定。旧トークンが失効していれば再発行します。自動受信・公開は接続確認後に管理画面から再設定してください。
4. OS時刻サービス・表示端末のNTP接続先を再設定。PC固有の秘密情報・IPはバックアップから流用しません。
5. 確認用起動を停止。旧主系の隔離を確認した上で `Start-Recovered-Manager.ps1` に `-EnableLan -OldManagerIsolated -LanAddress '<新PCのIPv4>'` を付けて起動します。通常の8800番へ戻す場合は `-Port 8800` を指定し、他の管理サービスが停止していることを確認してください。
6. 全端末で画像・便・時刻を確認。通常の自動起動への切替は、この復元フォルダーを使う起動設定が必要です。現段階では担当者が設定・再起動試験してから無人運用へ戻します。

1. Power off or disconnect the old primary. Prevent it from resuming distribution. This version has no automatic split-brain protection.
2. Confirm the replacement PC LAN address, feed port and firewall. Update terminal connection origins and reissue keys when necessary.
3. If Web integration is required, copy `web-connection.template.json` to `web-connection.json` and securely provision the token in `web-credential.json`. Reissue expired/revoked credentials. Enable automatic publication only after verifying the connection.
4. Reconfigure the OS clock helper and terminal NTP server. Do not reuse machine-specific secrets/IP settings.
5. Stop the verification launch. After isolating the old manager, run the recovery launcher with `-EnableLan -OldManagerIsolated -LanAddress '<replacement IPv4>'`. Specify `-Port 8800` for the normal UI port only after stopping other management services.
6. Check every display's images, flights and clock. Scheduled startup must be configured to use the restored folder and tested after a reboot before returning to unattended operation.

他OSでは `python3 -m pifids.backup <ZIP> --airport SHI --output <新フォルダー>` で同じ検証・復元準備を実行できます。既存フォルダーを指定すると拒否します。

On other platforms, `python3 -m pifids.backup <ZIP> --airport SHI --output <new-folder>` provides the same validation/preparation. Existing folders are rejected.

## 表示端末の版番号 / Display revision checks

現行表示端末は、受信済みより古い便・表示設定の版を拒否します。古いバックアップを復元すると、この理由で端末が最後の画面を保持する場合があります。端末の受信済み版と復元した版を確認し、版を揃える復旧処理を実施するまでは配信再開完了としません。管理世代による正式な切替は次段階の実装です。本機能は検証済み復元フォルダーの準備までを提供します。

Current receivers reject flight/control revisions older than those already stored. An older restored backup may therefore leave a terminal on its last screen. Compare receiver and restored revisions; do not declare distribution restored until a revision reconciliation procedure has been completed. Formal manager-generation switching is the next implementation stage. This feature provides preparation of a validated recovery folder.


## 復元起動試験の記録 / Recovery startup rehearsal

2026-10-09 15:51 JST頃、SHI管理PCの通常ログイン権限で、同日15:47 JST作成のバックアップを新しい別フォルダーへ復元し、8810番のlocalhost管理画面として起動した。

- 公開便15件、画像7点、登録端末4台、ユーザー1名を検証。公開便・画像一覧・ユーザー設定は稼働データと一致した。
- 復元画面の空港SHI、ログイン必須、未認証データ取得の拒否を確認した。
- 復元側のWeb自動受信・公開は停止し、LAN配信を有効にしなかった。
- 元の8800番管理アプリの継続稼働を確認した。試験用管理アプリは確認後に停止した。
- 結果は復元フォルダー内の `rehearsal-result.json` に保存した。

これは同一PC上の隔離した復元・起動試験である。別PCへの移設、ログイン操作、表示端末の接続切替、NTP変更、主PC故障時の配信再開は未検証。管理PCと表示PCの2台のみのため、予備管理PCを用意してから別PCでの切替試験を行う。

On 9 October 2026, a SHI backup created at 15:47 JST was restored into a new folder and launched on localhost port 8810 under the ordinary Windows logon user's permissions. The rehearsal verified 15 published flights, 7 images, 4 registered displays and 1 user. Published flights, image inventory and user settings matched the live manager. The restored service required authentication and rejected unauthenticated data access. Web automatic publication remained disabled and no LAN feed was started. The live manager on port 8800 continued running; the test manager was stopped afterwards. Results were saved as `rehearsal-result.json` in the recovery folder.

This was an isolated rehearsal on the same PC. Replacement-PC migration, an actual login, display reconnection, NTP changes and distribution after primary-PC failure remain untested. A separate standby management PC is required for the next hardware takeover test.
