# 案件依頼サンプル → projects 反映マッピング

対象サンプル: [kintone_app/sample/案件サンプル.csv](../../kintone_app/sample/%E6%A1%88%E4%BB%B6%E3%82%B5%E3%83%B3%E3%83%97%E3%83%AB.csv)

## 目的
案件依頼の入力項目を、Kintone「案件マスタ (projects)」へ取り込めるようにするための追加フィールド定義とマッピング。

## 既存必須フィールド（不足）
サンプルには以下が含まれていないため、取り込み時に追加が必要です。
- `project_id`（案件ID）
- `client_id`（クライアントID）
- `site_id`（現場ID）
- `project_type_id`（案件種別ID）
- `start_date` / `end_date`（実施日を設定）
- `status`（operating/completed/canceled）

## 追加フィールド（projectsへ追加）
| サンプル列 | 追加フィールドコード | 種別 | 備考 |
|---|---|---|---|
| タイトル | request_title | 文字列(1行) | サンプルのタイトルを保持 |
| 案件種別 | request_project_type | 文字列(1行) | `project_type_id` の参照用（名称） |
| 実施日 | request_date | 日付 | `start_date`/`end_date` にも同値を設定 |
| 曜日 | request_weekday | 文字列(1行) | |
| 施設名 | request_facility | 文字列(1行) | site_id とは別に名称を保持 |
| イベント名 | request_event_name | 文字列(1行) | |
| 住所 | request_address | 文字列(複数行) | |
| 内容 | request_content | 文字列(複数行) | |
| ディレクター人数 | director_count | 数値 | |
| ディレクター日数 | director_days | 数値 | |
| スタッフ人数 | staff_count | 数値 | |
| スタッフ日数 | staff_days | 数値 | |
| 集合時間 | meeting_time | 時刻 | |
| 稼働開始 | work_start_time | 時刻 | |
| 稼働終了 | work_end_time | 時刻 | |
| 稼働時間(時間) | work_hours | 数値 | |
| 解散時間 | dismissal_time | 時刻 | |
| ギャラ_ディレクター(円/日/人) | director_unit_price | 数値 | |
| ギャラ_スタッフ(円/日/人) | staff_unit_price | 数値 | |
| 人件費合計_ディレクター(円) | director_labor_cost | 数値 | |
| 人件費合計_スタッフ(円) | staff_labor_cost | 数値 | |
| 人件費合計(円) | total_labor_cost | 数値 | |
| 備考 | notes | 文字列(複数行) | 既存フィールド |

## 取り込み時の運用メモ
- `request_project_type` は案件種別の名称として保持し、`project_type_id` はマスタのコードで入力する。
- `request_facility` は施設名の入力欄として保持し、`site_id` は現場マスタのIDで入力する。
- 単一日案件は `start_date` = `end_date` = `request_date` を推奨。
