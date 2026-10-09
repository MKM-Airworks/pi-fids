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

## 今回の範囲と残作業

手動取得・手動取込み・手動公開の接続を実装した。取得の自動周期、運航日の日次自動展開と公開日制約、Webメインでの自動適用・編集禁止、正本世代の切替、クラウドバックアップは後続実装。未来日の取込みは下書き準備用であり、日付に合わせた自動公開はまだ行わない。公開後に運航日が変わっても表示が自動更新される段階ではない。

FIDS側は25件のPythonテストを確認。新WebプロファイルのAPI・資格情報・DBはまだ本番へ設置していない。Macの試験用FastAPI（DBスタブ）→HTTP取得→管理画面から取込み／公開→端末受信→到着STA/ETA表示を確認した。Windows、実PostgreSQL、実HTTPSとWixの検証は残る。

## 配信認証・権限制限の確認記録

SHI実機で受信と書き込み拒否を確認した。認証は配信サーバーで毎回行い、受信資格情報は組織・空港・製品に固定される。詳細と確認範囲は[確認記録](web-feed-security-20261009.md)を参照。
