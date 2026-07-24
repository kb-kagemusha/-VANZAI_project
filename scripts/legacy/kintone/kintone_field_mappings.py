"""
Kintoneフィールドコードマッピング（非推奨・レガシー）

本番運用は VPS のみ。過去の Kintone 移行スクリプト向けに残置。

2026/01/28 更新: フィールドコードを英語に変更済み
    - Workers (165), Clients (167), Sites (166), Roles (163), Project Types (164)
    - これらのアプリはマッピング不要（DBとKintoneで同じコード）

注意:
- 既にフィールドコードを英語に変更したアプリはマッピング不要
- 新規作成するアプリ（invoices, payoutsなど）も英語コードで作成すること
"""

# DBフィールドコード → Kintoneフィールドコード
FIELD_MAPPINGS = {
    # Workers (165) - ✅ フィールドコード英語化済み（マッピング不要）
    # 165: {},
    
    # Clients (167) - ✅ フィールドコード英語化済み（マッピング不要）
    # 167: {},
    
    # Sites (166) - ✅ フィールドコード英語化済み（マッピング不要）
    # 166: {},
    
    # Roles (163) - ✅ フィールドコード英語化済み（マッピング不要）
    # 163: {},
    
    # Project Types (164) - ✅ フィールドコード英語化済み（マッピング不要）
    # 164: {},
}

# Kintoneフィールドコード → DBフィールドコード（逆マッピング）
REVERSE_MAPPINGS = {}
for app_id, mapping in FIELD_MAPPINGS.items():
    REVERSE_MAPPINGS[app_id] = {v: k for k, v in mapping.items()}


def db_to_kintone(db_field: str, app_id: int) -> str:
    """
    DBフィールドコードをKintoneフィールドコードに変換
    
    Args:
        db_field: DBのフィールドコード (例: "worker_id")
        app_id: KintoneアプリID (例: 165)
    
    Returns:
        Kintoneフィールドコード (例: "ドロップダウン")
        マッピングがない場合はそのまま返す
    """
    mapping = FIELD_MAPPINGS.get(app_id, {})
    return mapping.get(db_field, db_field)


def kintone_to_db(kintone_field: str, app_id: int) -> str:
    """
    KintoneフィールドコードをDBフィールドコードに変換
    
    Args:
        kintone_field: Kintoneのフィールドコード (例: "ドロップダウン")
        app_id: KintoneアプリID (例: 165)
    
    Returns:
        DBフィールドコード (例: "worker_id")
        マッピングがない場合はそのまま返す
    """
    mapping = REVERSE_MAPPINGS.get(app_id, {})
    return mapping.get(kintone_field, kintone_field)


def format_kintone_record(data: dict, app_id: int) -> dict:
    """
    DBデータをKintone形式に変換（フィールドコードマッピング適用）
    
    Args:
        data: DBからのデータ辞書 (例: {"worker_id": "W001", "name": "山田太郎"})
        app_id: KintoneアプリID
    
    Returns:
        Kintone形式のレコード (例: {"ドロップダウン": {"value": "W001"}, ...})
    """
    record = {}
    
    for db_field, value in data.items():
        # マッピングがあればKintoneコードに変換、なければそのまま
        kintone_field = db_to_kintone(db_field, app_id)
        
        # Kintone形式に変換
        if value is None:
            value = ""
        elif isinstance(value, bool):
            value = "有効" if value else "無効"
        else:
            value = str(value)
        
        record[kintone_field] = {"value": value}
    
    return record


def parse_kintone_record(record: dict, app_id: int) -> dict:
    """
    Kintone形式のレコードをDBデータに変換
    
    Args:
        record: Kintone形式のレコード (例: {"ドロップダウン": {"value": "W001"}, ...})
        app_id: KintoneアプリID
    
    Returns:
        DBデータ辞書 (例: {"worker_id": "W001", "name": "山田太郎"})
    """
    data = {}
    
    for kintone_field, field_data in record.items():
        # マッピングがあればDBコードに変換、なければそのまま
        db_field = kintone_to_db(kintone_field, app_id)
        
        # 値を取得
        value = field_data.get("value", "")
        
        # 型変換（必要に応じて）
        if value == "":
            value = None
        elif value in ("有効", "無効"):
            value = (value == "有効")
        
        data[db_field] = value
    
    return data
