# Google Mapsの住所・施設名取得：設定と費用

確認日: 2026-10-14（日本向けのグローバル料金表）

今回は共有URL・所在地住所・施設名を手入力のままにする。Google Cloudの設定変更、課金の有効化、APIキーの作成や変更は行わない。

## 取得方法と現状
共有URLは地図を開くリンクで、住所・施設名を返すAPIではない。短縮URLは地点IDを直接含むとは限らず、キーを設定するだけで自動入力が完成するわけではない。将来は会場名からPlaces API (New)で候補を検索し、確認した地点のplace_idを保存する導線が適している。短縮URL対応を追加する場合はGoogleホストだけに限定した展開と地点照合が別途必要になる。画面HTMLの読み取りに依存する実装は採用しない。[Maps URL仕様](https://developers.google.com/maps/documentation/urls/get-started)、[Place Details](https://developers.google.com/maps/documentation/places/web-service/place-details)

現行コードには会場名のText Searchと地点ID保存の準備がある。キー未設定では表示しない。取得住所は参照表示だけで、登録住所への転記・施設名の自動変更はまだ行わない。

## 主な料金
無料枠は月ごと・SKUごと。超過料金は最初の有料ボリューム帯（100,000件まで）、米ドル/1,000件で示す。施設名のdisplayNameを取得するPlace DetailsはProになる。

| API / 取得内容 | 月間無料枠 | 超過単価 |
| --- | ---: | ---: |
| Text Search Pro：会場名から施設名・住所を検索 | 5,000件 | $32 / 1,000件 |
| Place Details Pro：地点IDから施設名・住所を取得 | 5,000件 | $17 / 1,000件 |
| Place Details Essentials：地点IDから住所のみ取得 | 10,000件 | $5 / 1,000件 |

例えばText Search Proが月6,000件なら、無料枠を超えた1,000件分が$32。別のDetailsも呼ぶ場合は、そのSKUの無料枠と料金で別計算する。回数は会場数ではなくAPI呼び出し数。取得フィールドと呼び出し方法で課金区分が変わるため、実装時に再確認する。税・通貨換算などはGoogleの請求条件で確認する。[公式料金表](https://developers.google.com/maps/billing-and-pricing/pricing)、[Detailsの取得フィールドと課金区分](https://developers.google.com/maps/documentation/places/web-service/place-details#fieldmask)

## 設定手順
1. 所有者のGoogle Cloudプロジェクトに請求先を関連付け、Places API (New)を有効化する。無料枠内でも請求先の設定は必要。
2. APIキーを作り、利用APIをPlaces API (New)だけに制限する。サーバー側で使うキーはVPSの送信元IPで制限する。
3. 所有者がサーバーの安全な設定経路でGOOGLE_MAPS_API_KEYを設定する。キーをチャット・ブラウザ・Gitに出さない。既存の秘密情報ファイルをこの作業で閲覧・上書きしない。
4. APIの利用クォータとアプリ側の呼び出し上限を決め、Cloud Billingの予算アラートも設定する。予算アラートだけでは利用・課金は自動停止しない。無料枠を超えない運用を保証するには呼び出し制限と監視が必要。
5. 公開の利用規約・プライバシーポリシー、Google Mapsと第三者の出典表示を整備し、テストしてから有効化する。

[Googleの設定手順](https://developers.google.com/maps/documentation/places/web-service/get-api-key)、[キー制限](https://developers.google.com/maps/api-security-best-practices)、[費用制御](https://developers.google.com/maps/billing-and-pricing/manage-costs)

## 保存に関する確認点
Places APIの取得情報には保存制限がある。place_idは無期限保存の例外だが、施設名・住所を案件DBや確定PDFへ恒久的に複製できるとは限らない。利用者が選択した街路住所のAutocompleteに関する例外は、施設検索で得た施設名・住所の保存を包括的に許すものではない。

導入前に、契約・適用条件を確認し、取得情報を一時的に参照する方式と、主催者が提供した住所・施設名を正本にする方式を分ける。画面で確認ボタンを押したことだけでGoogle情報を自由に保存できるとは扱わない。[Places APIの保存・出典ルール](https://developers.google.com/maps/documentation/places/web-service/policies)
