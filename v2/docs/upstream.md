# MKM Flight Webからの取得と下書き取込み

MKM Flight WebのDBサーバーは習志野の本宅にある。DB移転を前提にせず、FIDSはDBへ直接接続しない。本宅DBへのmigrationと、APIサーバーからの接続・権限確認は本宅環境を利用できる段階で行う。

管理PCがWebの認証付きmanifest・releaseをGETし、検証済みの原本をSQLiteへ保存する。表示端末はWebへ接続せず、管理PCの公開版だけ受信する。資格情報をブラウザや表示端末へ渡さない。

## 二つの配信プロファイル

| 目的 | 契約 / product | 更新確認 |
| --- | --- | --- |
| 出発・到着のFIDS専用 | mkm-fids-distribution/1 / pi-fids | /v1/fids-receiver/manifest |
| 既存の出発ダイヤのみ | mkm-flight-distribution/1 / inspection-record | /v1/receiver/manifest |

推奨はFIDS専用。Web本体には到着とSTA/ETAが保存されているが、既存inspection-record公開処理はDEPだけを抽出する。既存API・スキーマは変更せず、Webリポジトリに別API・別公開版テーブル・別資格情報を追加した。Web側の追加機能は本番未配置なので、配置と資格情報発行後に接続する。既存inspection-recordも互換受信できるが、到着は得られない。

## 接続設定

ソース・Web公開領域・Gitの外に管理者用のJSONファイルを保存する。値は実際の空港マスターに基づく。以下のUUIDは構造を示すための架空値。

```json
{
  "baseUrl": "https://api.mkmairworks.online",
  "credentialFile": "fids-credential.json",
  "expected": {
    "organizationId": "11111111-1111-4111-8111-111111111111",
    "airportId": "22222222-2222-4222-8222-222222222222",
    "product": "pi-fids",
    "stationAirport": "ROR",
    "timezone": "Pacific/Palau",
    "allowPreview": false
  }
}
```

credentialFileは設定ファイルからの相対パス、または絶対パス。資格情報ファイルは `{ "token": "発行された秘密値" }` の形式。SHIはstationAirport=SHI、timezone=Asia/Tokyo。接続設定と管理ログインの空港は一致させる。

```sh
python3 -m pifids --auth-config /private/path/manager-auth.json --upstream-config /private/path/web-connection.json --lan-port 8803
```

通常のWeb取得はHTTPS必須。CA不要のHTTP配信は空港LANの端末配信部分だけ。ローカル試験ではbaseUrlをhttp://127.0.0.1:PORTにし、allowLoopback=trueを明示した場合だけHTTPを許可する。転送は拒否し、プロキシを経由せず同一originへだけ秘密を送る。

## 管理画面の操作

1. MKM Flight Webパネルで「Webの更新を確認」。取得だけでは下書き・公開・端末表示を変更しない。
2. 運航日を指定し、便名・出発／到着・定刻・予定時刻・ゲート・備考を確認する。運航期間とISO曜日から当日便へ展開する。
3. 「Webの便を下書きへ取込み」。前回Webから取り込んだ便を置換し、手入力の便を保持する。手入力便に同方向・同便名がある場合は競合として拒否する。
4. ロゴ・表示言語や必要な変更を設定し、下書きを確認して公開する。

出発の相手空港はdestination、到着はorigin。FIDSのscheduledTime/estimatedTimeを方向に応じたSTD/ETD・STA/ETAへ表示する。到着時刻を出発時刻から推測しない。欠航は便を消さずCancelledで表示する。内部備考は取得しない。コードシェアは原本に保持するが、今回の表示では別便行に展開しない。

同一運航日の再取込みではロゴ・言語を保持し、ゲート・予定時刻・備考は前回取込み以降に手動変更した値だけを保持する。日が変わった場合は当日のゲート・予定時刻・備考を新しいWeb値へ戻し、ロゴ・言語は保持する。Webで欠航になった場合はCancelledを優先する。

公開済みと下書きは分離する。取込み中に別画面で下書きが変更された場合と、確認したWeb版が更新された場合は競合を拒否する。原本の組織・空港・製品変更は別保存領域で設定し直す。版番号を他の範囲と比較して自動切替しない。

## 受信検証

同梱した既存／FIDSのJSONスキーマ、期待する対象範囲、previewフラグ、manifestと本文の一致、生バイト長とSHA-256、期間、ISO曜日、空港、重複スケジュール、版の巻戻し・同版本文の変更を確認する。原本は検証成功後だけ原子的に保存する。期限切れ・有効期間前・有効定義なしを区別し、対象日の有効性を毎回再計算する。

運航便なしの明示公開と、運航曜日に該当する便なしは別表示。失効した資格情報・通信障害・破損本文は最後の正常原本と公開表示を保持する。失敗状態と最終取得時刻を管理画面に表示する。空港日付は端末OSのタイムゾーンに依存せずSHI/RORのUTC+09:00を使う。

## 日付切替と保存済みダイヤによる自動公開 / Daily publication

管理PCは空港のタイムゾーンで日付を確認し、現地0時を過ぎた後、通常1分以内に最後に検証・保存したシーズナルダイヤから当日便を生成・公開する。最初の手動取込み・公開後に動作し、運航期間と運航曜日に従う。PCが停止していた場合は起動後に当日分へ追いつく。停止中の各日を順に公開しない。

この処理はWebの受信モードとは独立している。Webを手動のままにしても日次公開は動作する。Web通信・資格情報を使わず保存済み原本を再検証するので、Web未接続や予備PCへのバックアップ復元後でも、有効期間内なら当日便を作れる。シーズナルダイヤを最初から保存していないPCでは生成できない。期限切れ、原本破損、未公開の編集、同日の手入力便との競合、合計100件超過時は公開を変更せず状態を管理画面へ表示する。

前日以前の便は運航日を変えず、表示期限内なら当日便と併せて引き継ぐ。期限は表示と同じく実績時刻（ATD/ATA）を優先し、なければETD/ETA、さらに未設定なら定刻を使う。日付は実績日・予定日を尊重する。複数端末で消去までの時間が異なる場合、管理PCは最も長い期限まで保持し、各端末は自身の設定時刻に消去する。

例：10月11日のBC618（定刻17:10）が10月12日00:30へ遅延した場合、10月12日0時の日次公開にその便を残し、10月12日定刻17:10のBC618も別IDで追加する。出発の消去時間10分なら前日の便は00:40に消える。ATDを00:35に設定して公開すると00:45に消える。翌日までの遅延入力にはETD/ETAと併せて予定日も入力する。同じ運航日のWeb再取込みでも引継ぎ便を保持する。

日次公開は監査ログに `schedule.daily-publish`、更新元「Saved seasonal schedule」として記録する。管理画面に日次更新の説明と、期限切れ・確認が必要な状態を表示する。Webの新しいダイヤを取得する処理は引き続き選択した手動／自動モードに従う。

The management PC publishes today's services from its last verified seasonal release within one minute after airport-local midnight. This works independently of manual/automatic Web retrieval, without network access or Web credentials. After a restart it catches up to the current day. A saved release and an initial import/publication are required; valid dates and operating weekdays apply. Expired or corrupt schedules, pending drafts, same-day manual conflicts and the 100-row limit keep the current publication and require review.

Previous-day flights retain their original service date and their estimated/actual dates, gate and remarks while any display still needs them. Each day's flight has a distinct ID, so a delayed previous-day flight and today's flight with the same flight number coexist. Actual time takes precedence for expiry, followed by estimated and scheduled time. Individual screens continue to hide flights using their own configured retention. Enter the estimated date as well as ETD/ETA for an overnight delay. Daily publications are audited as `schedule.daily-publish` with source `Saved seasonal schedule`.

## 残作業

正本世代による自動切替、クラウドバックアップは未実装。現在の管理PC切替は主系の配信を停止してから予備側へ接続先を変更する手動手順で行う。

## 配信認証・権限制限の確認記録

SHI実機で受信と書き込み拒否を確認した。認証は配信サーバーで毎回行い、受信資格情報は組織・空港・製品に固定される。詳細と確認範囲は[確認記録](web-feed-security-20261009.md)を参照。
