# ROR CSV試験環境 / ROR CSV lab — 2026-10-11

管理PC、予備管理PC、表示PCをSHIからRORへ切り替えました。空港現地時刻はPacific/Palau（UTC+09:00）です。既存SHIのデータと認証設定は切替前バックアップに保存しています。

MKM Flight Webからユーザーが出力したROR-flights.csvを使用。シーズナル設定26件、有効期間2026-10-01〜2026-10-31。当日10月11日は出発2便（QF166、UA142）、到着3便（PR513、QF165、UA143）。旧デモ便は除外しました。現在はCSVを日次生成元とし、SHI用Web資格情報をRORで使用していません。

便一覧端末の出発・到着表示開始は360分前。出発一覧は当日の終了時間を過ぎると空欄となり、翌日02:05のUA158は前日20:05から表示対象になります。未来便の初回準備は60秒周期です。管理PCの配信を使用し、予備管理PCのLAN配信は停止しています。

確認内容：Python 99件、表示ポリシーを含むJavaScript 11件。Windows上の実ダイヤをコピーした検証で、UA158の20:05開始、翌日への遅延到着便の持越し、翌日便の重複なしを確認。表示PCの受信APIでもROR・5便・360分前設定を確認。実端末の時計を変更していません。時刻境界の実画面観察は連続稼働試験で確認してください。

## English

The primary manager, standby manager and display PC now use ROR / Pacific/Palau (UTC+09:00). SHI data and authentication settings were backed up before switching.

The user-provided MKM Flight Web CSV contains 26 seasonal entries valid from 1 to 31 October 2026. On 11 October it generates two departures (QF166, UA142) and three arrivals (PR513, QF165, UA143). Old demo flights were removed. CSV is the offline daily schedule source; the SHI Web credential is not used for ROR.

Board terminals start displaying departures and arrivals 360 minutes before STD/STA. UA158 at 02:05 on the following day becomes eligible at 20:05 the preceding evening, with preparation checked every 60 seconds. Departures may be empty after today's operations expire. The primary manager supplies the LAN feed; the standby feed remains stopped.

Validation: 99 Python tests and 11 JavaScript tests passed. A copy of the actual Windows schedule verified the opening boundary, an overnight delayed arrival and no duplicate next-day operations. The display receiver API confirmed ROR, five current-day operations and the 360-minute settings. System clocks were not changed. Observe actual boundary rendering during the continuous operation trial.
