# 端末ごとの便一覧 / Terminal flight boards

③端末の設定で登録端末を選び、用途を「便一覧」にします。出発／到着、国内・国際の表示（すべて／国内線／国際線）、ディスプレイの向き（横置き／縦置き）を選び、保存してください。12通りを端末ごとに選択できます。

縦置きは1ページ6便のカード表示です。Windowsの「ディスプレイ設定」でも画面の向きを縦にしてください。横置きは既存の表形式を使います。

国内・国際はCSVまたはWeb配信のgeo区分（DOM／INTL）を使用します。①の便編集でも変更できます。未設定の便は「すべて」でのみ表示されます。Web側が区分を配信していない場合は編集で指定してください。表示開始・終了時間や遅延便の翌日繰越は引き続き適用されます。

In ③ Terminal settings, select a registered terminal and choose Flight board. Set departure/arrival, traffic (All/Domestic/International), and orientation (Landscape/Portrait), then save. Each terminal supports all 12 combinations.

Portrait uses six flight cards per page. Also set the Windows display orientation to Portrait. Landscape retains the existing table layout.

Classification uses the optional geo field from CSV or Web releases: DOM or INTL. It can also be edited in ① Flight information. Unclassified flights appear only under All. If the Web feed omits geo, set it in the flight editor. Display windows, expiry, and delayed-flight carryover still apply.

## コードシェア便 / Codeshares

①フライト情報管理の便編集に「コードシェア便」を入力します（例：NH6467, PR999）。追加・変更後は保存し、下書きを公開してください。空欄で保存・公開するとコードシェア便を削除できます。運航便の行自体は残ります。

③端末の設定の「コードシェア便を表示」で有効／無効を選び、切替間隔を3～60秒で設定できます（初期値5秒・有効）。運航便→コードシェア便の順でロゴと便名を同時に切り替え、時刻・行先・ゲート・備考は固定します。言語切替とは独立して動きます。登録済みの航空会社ロゴを使用し、ロゴがない場合は登録済み航空会社名、名称もない場合は航空会社コードを表示します。

In ① Flight information, edit a flight and enter comma-separated codeshare flight numbers (for example NH6467, PR999). Save and publish the draft. Clear the field, save and publish to remove codeshares while retaining the operating flight.

In ③ Terminal settings, enable/disable Show codeshare flights and set a 3–60 second interval (enabled, 5 seconds by default). The airline logo and flight number rotate together, operating flight first and then codeshares. Time, route, gate and remarks remain unchanged. Language rotation is independent. Registered airline logos are used; missing logos fall back to the registered airline name, or the airline code if no name is registered.

## 到着便のベルト / Arrival baggage belt
①便の編集でベルト番号（20文字まで）を入力し、公開します。空欄で保存・公開すると削除します。③端末の設定の「到着便の表示列」で「ベルト」を選び保存すると、その端末の横置き・縦置き到着便画面に表示します。既存端末は非表示のままです。
Edit the baggage belt in Flight information (up to 20 characters), then publish. Clear and publish to remove it. Enable Belt under the terminal's Arrival columns to show it on landscape or portrait arrivals. Existing terminals keep it hidden.
Web配信契約の任意項目 `belt` を受信します。Web配信サーバーのコード更新は別途必要です。DBテーブル変更は不要です。
The receiver accepts optional `belt` metadata. The Web distribution server needs a separate code update; no database table migration is needed.
