"""Kintone API連携サービス（非推奨・レガシー）

本番運用は VPS（FastAPI + PostgreSQL + admin-web / staff-mobile）のみで完結する。
このモジュールは過去のデータ移行スクリプト（scripts/sync_db_to_kintone.py 等）向けに残置している。

新規機能では使用しないこと。
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


logger = logging.getLogger(__name__)


class KintoneConfig:
    """Kintone接続設定"""
    
    def __init__(
        self,
        subdomain: Optional[str] = None,
        guest_space_id: Optional[str] = None,
        api_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.subdomain = subdomain or os.getenv("KINTONE_SUBDOMAIN", "")
        self.guest_space_id = guest_space_id or os.getenv("KINTONE_GUEST_SPACE_ID", "")
        self.api_token = api_token or os.getenv("KINTONE_API_TOKEN", "")
        self.username = username or os.getenv("KINTONE_USERNAME", "")
        self.password = password or os.getenv("KINTONE_PASSWORD", "")
    
    @property
    def base_url(self) -> str:
        if self.guest_space_id:
            return f"https://{self.subdomain}.cybozu.com/k/guest/{self.guest_space_id}/v1"
        return f"https://{self.subdomain}.cybozu.com/k/v1"


class KintoneService:
    """
    Kintone API連携サービス
    
    requests ライブラリで直接REST APIを使用
    """
    
    def __init__(self, config: KintoneConfig, api_token: Optional[str] = None):
        self.config = config
        self.api_token = api_token or config.api_token

    def _build_kintone_error_hint(self, text: str) -> str | None:
        """よくある失敗原因をベストエフォートで推測する。"""
        lowered = text.lower()

        # UPSERT(updateKey)で頻出: キー項目が重複禁止ではない/型が対象外
        if "updatekey" in lowered or "upsert" in lowered:
            return (
                "UPSERT(updateKey)の要件未満の可能性: キー項目が『重複禁止』でない、"
                "またはキー項目の型が対象外。Kintoneのフィールド設定で重複禁止を有効化し、"
                "文字列(1行) or 数値のフィールドをキーにしてください"
            )

        if "unique" in lowered or "duplicate" in lowered or "重複" in text:
            return (
                "キー項目の重複禁止（ユニーク）設定が原因の可能性。"
                "Kintone側で該当フィールドの『重複禁止』を有効化してください"
            )

        if "permission" in lowered or "権限" in text:
            return "APIトークンの権限不足の可能性（レコード閲覧/追加/編集、アプリ管理など）"

        if "does not exist" in lowered or "存在し" in text:
            return "フィールドコード不一致の可能性（Kintoneフォームのフィールドコードを確認）"

        return None

    def _raise_kintone_error(self, response: requests.Response, *, action: str) -> None:
        """kintoneのエラーレスポンスを解析して、原因のヒント付きで例外化する。"""
        status = response.status_code
        raw_text = response.text

        try:
            data = response.json()
        except Exception:
            data = None

        message_parts: List[str] = [f"Kintone API Error ({action}): {status}"]

        if isinstance(data, dict):
            msg = data.get("message")
            if isinstance(msg, str) and msg:
                message_parts.append(f"message={msg}")
            errors = data.get("errors")
            if errors is not None:
                message_parts.append(f"errors={errors}")
            code = data.get("code")
            if isinstance(code, str) and code:
                message_parts.append(f"code={code}")
            id_ = data.get("id")
            if isinstance(id_, str) and id_:
                message_parts.append(f"id={id_}")
        else:
            if isinstance(raw_text, str) and raw_text:
                message_parts.append(raw_text)

        hint = self._build_kintone_error_hint(raw_text if isinstance(raw_text, str) else "")
        if hint:
            message_parts.append(f"hint={hint}")

        raise Exception(" | ".join(message_parts))
    
    def _get_headers(self) -> Dict[str, str]:
        """APIリクエスト用ヘッダーを取得"""
        return {
            "X-Cybozu-API-Token": self.api_token,
            "Content-Type": "application/json"
        }
    
    def _build_url(self, endpoint: str) -> str:
        """エンドポイントURLを構築"""
        return f"{self.config.base_url}/{endpoint}"
    
    def get_records(
        self,
        app_id: int,
        query: Optional[str] = None,
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        レコード取得（汎用）
        
        Args:
            app_id: KintoneアプリID
            query: クエリ文字列（例: "work_date >= '2026-01-01'"）
            fields: 取得するフィールドのリスト
        
        Returns:
            レコードリスト
        """
        url = self._build_url("records.json")
        params = {"app": str(app_id)}
        
        if query:
            params["query"] = query
        if fields:
            params["fields"] = fields
        
        # デバッグ情報
        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] Params: {params}")
        
        response = requests.get(
            url,
            headers=self._get_headers(),
            params=params,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[DEBUG] Response: {response.text}")
            self._raise_kintone_error(response, action="get_records")
        
        data = response.json()
        return data.get("records", [])

    def get_form_fields(self, app_id: int) -> Dict[str, Any]:
        """アプリのフォームフィールド定義を取得する。

        Note:
            UPSERTのupdateKey要件（フィールド型/重複禁止設定）を確認する用途。
        """
        url = self._build_url("app/form/fields.json")
        params = {"app": str(app_id)}

        response = requests.get(
            url,
            headers=self._get_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            self._raise_kintone_error(response, action="get_form_fields")

        data = response.json()
        properties = data.get("properties", {})
        if not isinstance(properties, dict):
            return {}
        return properties
    
    def add_records(
        self,
        app_id: int,
        records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        レコード追加（複数件一括）
        
        Args:
            app_id: KintoneアプリID
            records: 追加するレコードのリスト
                    形式: [{"field1": {"value": "val1"}, ...}, ...]
        
        Returns:
            追加結果（ids, revisions）
        """
        url = self._build_url("records.json")

        # kintone は一括追加の上限がある（通常100件）。安全のためバッチ送信する。
        all_ids: List[str] = []
        all_revisions: List[str] = []

        for i in range(0, len(records), 100):
            batch = records[i : i + 100]
            payload = {
                "app": app_id,
                "records": batch,
            }

            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                self._raise_kintone_error(response, action="add_records")

            data = response.json()
            all_ids.extend(data.get("ids", []))
            all_revisions.extend(data.get("revisions", []))

        return {"ids": all_ids, "revisions": all_revisions}
    
    def update_records(
        self,
        app_id: int,
        records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        レコード更新（複数件一括）
        
        Args:
            app_id: KintoneアプリID
            records: 更新するレコードのリスト
                    形式: [{"id": 1, "record": {"field1": {"value": "val1"}}}, ...]
        
        Returns:
            更新結果（records）
        """
        url = self._build_url("records.json")

        all_records: List[Dict[str, Any]] = []
        for i in range(0, len(records), 100):
            batch = records[i : i + 100]
            payload = {
                "app": app_id,
                "records": batch,
            }

            response = requests.put(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                self._raise_kintone_error(response, action="update_records")

            data = response.json()
            all_records.extend(data.get("records", []))

        return {"records": all_records}

    def upsert_records(
        self,
        app_id: int,
        records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """レコードUPSERT（複数件一括）

        - updateKey を指定した場合、存在すれば更新・存在しなければ追加。
        - `?upsert=true` を付与する。

        Args:
            app_id: KintoneアプリID
            records: 形式: [{"updateKey": {"field": "worker_id", "value": "..."}, "record": {...}}, ...]

        Returns:
            結果（records）
        """
        url = self._build_url("records.json")

        all_records: List[Dict[str, Any]] = []
        for i in range(0, len(records), 100):
            batch = records[i : i + 100]
            payload = {
                "app": app_id,
                "records": batch,
            }

            response = requests.put(
                url,
                headers=self._get_headers(),
                params={"upsert": "true"},
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                self._raise_kintone_error(response, action="upsert_records")

            data = response.json()
            all_records.extend(data.get("records", []))

        return {"records": all_records}
    
    def sync_workers(self, app_id: int) -> List[Dict]:
        """
        稼働者マスタを同期（Kintone→DB用）
        
        Args:
            app_id: KintoneアプリID
        
        Returns:
            レコードリスト
        """
        return self.get_records(app_id)
    
    def sync_projects(self, app_id: int) -> List[Dict]:
        """
        案件マスタを同期（Kintone→DB用）
        
        Args:
            app_id: KintoneアプリID
        
        Returns:
            レコードリスト
        """
        return self.get_records(app_id)
    
    def get_actuals(
        self,
        app_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict]:
        """
        実績データ取得
        
        Args:
            app_id: KintoneアプリID
            date_from: 開始日（YYYY-MM-DD）
            date_to: 終了日（YYYY-MM-DD）
        
        Returns:
            レコードリスト
        """
        query = None
        if date_from and date_to:
            query = f'work_date >= "{date_from}" and work_date <= "{date_to}"'
        elif date_from:
            query = f'work_date >= "{date_from}"'
        elif date_to:
            query = f'work_date <= "{date_to}"'
        
        return self.get_records(app_id, query=query)
    
    def write_back_errors(
        self,
        app_id: int,
        record_id: int,
        error_message: str
    ) -> bool:
        """
        エラーメッセージをKintoneレコードに書き戻し
        
        Args:
            app_id: KintoneアプリID
            record_id: レコードID
            error_message: エラーメッセージ
        
        Returns:
            成功したかどうか
        """
        try:
            records = [{
                "id": record_id,
                "record": {
                    "error_message": {"value": error_message},
                    "error_at": {"value": datetime.now().isoformat()}
                }
            }]
            self.update_records(app_id, records)
            return True
        except Exception as e:
            logger.error(f"Failed to write back error to Kintone: {e}")
            return False
    
    def export_to_csv(self, app_id: int, output_path: str) -> bool:
        """
        KintoneアプリからCSVエクスポート
        
        Args:
            app_id: KintoneアプリID
            output_path: 出力ファイルパス
        
        Returns:
            成功: True, 失敗: False
        """
        try:
            import pandas as pd
            
            records = self.get_records(app_id)
            if not records:
                return False
            
            # レコードをフラット化（Kintone形式 -> dict形式）
            flat_records = []
            for record in records:
                flat_record = {}
                for key, value in record.items():
                    if isinstance(value, dict) and "value" in value:
                        flat_record[key] = value["value"]
                    else:
                        flat_record[key] = value
                flat_records.append(flat_record)
            
            df = pd.DataFrame(flat_records)
            df.to_csv(output_path, index=False, encoding="shift-jis")
            return True
        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            return False


def get_default_kintone_service() -> KintoneService:
    """デフォルトのKintoneServiceを取得"""
    config = KintoneConfig()
    return KintoneService(config)


# アプリID定数（環境変数から取得）
KINTONE_APP_IDS = {
    "workers": int(os.getenv("KINTONE_APP_WORKERS", "1")),
    "projects": int(os.getenv("KINTONE_APP_PROJECTS", "2")),
    "actuals": int(os.getenv("KINTONE_APP_ACTUALS", "3")),
    "sites": int(os.getenv("KINTONE_APP_SITES", "4")),
}
