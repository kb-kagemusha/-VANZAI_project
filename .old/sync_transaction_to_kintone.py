#!/usr/bin/env python
"""
トランザクションデータ Kintone同期（Projects, ShiftSlots, Assignments, Actuals）

DB → Kintone同期（動的ドロップダウンオプション追加）
"""
import sys
from pathlib import Path
import os
import requests
import time
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.deps import SessionLocal
from src.models.transaction import Project, ShiftSlot, Assignment, Actual
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Kintone設定
SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN", "xtf5wpxp3gk2")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID", "3")
BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"

# アプリIDとトークン（実際の値に置き換え）
APPS = {
    "projects": {"app_id": "160", "token": "evJngvB7sRXq3wAIX3A4KMNO5OrzmWQysIpP1Ec6"},
    "shift_slots": {"app_id": "159", "token": "V8qeyfZrqZJ48iJEbz3LPDDOpltsQzoxh9mJ0ubG"},
    "assignments": {"app_id": "158", "token": "T77pVQSfpYExBDREyI7gUGi4e2hXvwTJWRO9VXha"},
    "actuals": {"app_id": "168", "token": "AhtQVqUqKEv7NuiZVkIyDLh3cyojWeucFno24wEA"},
}


def add_dropdown_options(app_id, token, field_code, new_options):
    """ドロップダウンフィールドに選択肢を動的追加"""
    if not new_options:
        return
    
    # 既存フィールド取得
    url = f"{BASE_URL}/preview/app/form/fields.json"
    headers = {"X-Cybozu-API-Token": token}
    params = {"app": app_id}
    
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    fields = resp.json()["properties"]
    
    if field_code not in fields:
        logger.info(f"フィールド {field_code} が存在しません（スキップ）")
        return
    
    field = fields[field_code]
    if field["type"] not in ["DROP_DOWN", "RADIO_BUTTON"]:
        logger.info(f"フィールド {field_code} はドロップダウン型ではありません（スキップ）")
        return
    
    # 既存選択肢を取得
    existing_options = {opt for opt in field.get("options", {})}
    
    # 追加すべき選択肢を抽出
    to_add = [opt for opt in new_options if opt and opt not in existing_options]
    
    if not to_add:
        logger.info(f"  → {field_code}: 追加不要（既存）")
        return
    
    # 選択肢追加
    updated_options = list(existing_options) + to_add
    field["options"] = {opt: {"label": opt, "index": str(i)} for i, opt in enumerate(updated_options)}
    
    update_url = f"{BASE_URL}/preview/app/form/fields.json"
    update_data = {
        "app": app_id,
        "properties": {field_code: field}
    }
    
    resp = requests.put(update_url, headers=headers, json=update_data)
    resp.raise_for_status()
    logger.info(f"  → {field_code}: {len(to_add)}件追加")
    
    # デプロイ
    deploy_url = f"{BASE_URL}/preview/app/deploy.json"
    deploy_data = {"apps": [{"app": app_id}]}
    resp = requests.post(deploy_url, headers=headers, json=deploy_data)
    resp.raise_for_status()
    logger.info(f"  → デプロイ完了")
    
    time.sleep(3)


def sync_projects():
    """Projects同期"""
    logger.info("\n[1/4] Projects同期...")
    
    db = SessionLocal()
    try:
        projects = db.query(Project).all()
        
        if not projects:
            logger.info("  → 同期対象なし")
            return
        
        app_id = APPS["projects"]["app_id"]
        token = APPS["projects"]["token"]
        headers = {"X-Cybozu-API-Token": token, "Content-Type": "application/json"}
        
        # ドロップダウンオプション追加（project_id, client_id, site_id, project_type_id）
        project_ids = list(set(p.id for p in projects if p.id))
        client_ids = list(set(p.client_id for p in projects if p.client_id))
        site_ids = list(set(p.site_id for p in projects if p.site_id))
        project_type_ids = list(set(p.project_type_id for p in projects if p.project_type_id))
        
        add_dropdown_options(app_id, token, "project_id", project_ids)
        add_dropdown_options(app_id, token, "client_id", client_ids)
        add_dropdown_options(app_id, token, "site_id", site_ids)
        add_dropdown_options(app_id, token, "project_type_id", project_type_ids)
        
        # レコード投入
        records = []
        for proj in projects:
            record = {
                "project_id": {"value": proj.id},
                "client_id": {"value": proj.client_id or ""},
                "site_id": {"value": proj.site_id or ""},
                "project_type_id": {"value": proj.project_type_id or ""},
                "start_date": {"value": proj.start_date.isoformat() if proj.start_date else ""},
                "end_date": {"value": proj.end_date.isoformat() if proj.end_date else ""},
                "notes": {"value": proj.notes or ""}
            }
            records.append(record)
        
        url = f"{BASE_URL}/records.json"
        data = {"app": app_id, "records": records}
        resp = requests.post(url, headers=headers, json=data)
        
        if resp.status_code == 200:
            logger.info(f"✅ Projects: {len(projects)}件同期完了")
        else:
            logger.error(f"❌ エラー: {resp.status_code} - {resp.text}")
    
    finally:
        db.close()


def sync_shift_slots():
    """ShiftSlots同期"""
    logger.info("\n[2/4] ShiftSlots同期...")
    
    db = SessionLocal()
    try:
        slots = db.query(ShiftSlot).all()
        
        if not slots:
            logger.info("  → 同期対象なし")
            return
        
        app_id = APPS["shift_slots"]["app_id"]
        token = APPS["shift_slots"]["token"]
        headers = {"X-Cybozu-API-Token": token, "Content-Type": "application/json"}
        
        # ドロップダウンオプション追加
        project_ids = list(set(s.project_id for s in slots))
        shift_labels = list(set(s.shift_label for s in slots if s.shift_label))
        
        add_dropdown_options(app_id, token, "project_id", project_ids)
        add_dropdown_options(app_id, token, "shift_label", shift_labels)
        
        # レコード投入
        records = []
        for slot in slots:
            record = {
                "slot_id": {"value": slot.id},
                "project_id": {"value": slot.project_id},
                "shift_label": {"value": slot.shift_label or ""},
                "work_date": {"value": slot.work_date.isoformat()},
                "start_time": {"value": slot.start_time.strftime("%H:%M") if slot.start_time else ""},
                "end_time": {"value": slot.end_time.strftime("%H:%M") if slot.end_time else ""}
            }
            records.append(record)
        
        url = f"{BASE_URL}/records.json"
        data = {"app": app_id, "records": records}
        resp = requests.post(url, headers=headers, json=data)
        
        if resp.status_code == 200:
            logger.info(f"✅ ShiftSlots: {len(slots)}件同期完了")
        else:
            logger.error(f"❌ エラー: {resp.status_code} - {resp.text}")
    
    finally:
        db.close()


def sync_assignments():
    """Assignments同期"""
    logger.info("\n[3/4] Assignments同期...")
    
    db = SessionLocal()
    try:
        assignments = db.query(Assignment).all()
        
        if not assignments:
            logger.info("  → 同期対象なし")
            return
        
        app_id = APPS["assignments"]["app_id"]
        token = APPS["assignments"]["token"]
        headers = {"X-Cybozu-API-Token": token, "Content-Type": "application/json"}
        
        # ドロップダウンオプション追加
        shift_slot_ids = list(set(a.shift_slot_id for a in assignments))
        worker_ids = list(set(a.worker_id for a in assignments))
        role_ids = list(set(a.role_id for a in assignments))
        statuses = list(set(a.status for a in assignments if a.status))
        
        add_dropdown_options(app_id, token, "shift_slot_id", shift_slot_ids)
        add_dropdown_options(app_id, token, "worker_id", worker_ids)
        add_dropdown_options(app_id, token, "role_id", role_ids)
        add_dropdown_options(app_id, token, "status", statuses)
        
        # レコード投入
        records = []
        for asg in assignments:
            record = {
                "assignment_id": {"value": asg.id},
                "shift_slot_id": {"value": asg.shift_slot_id},
                "worker_id": {"value": asg.worker_id},
                "role_id": {"value": asg.role_id},
                "status": {"value": asg.status or ""}
            }
            records.append(record)
        
        url = f"{BASE_URL}/records.json"
        data = {"app": app_id, "records": records}
        resp = requests.post(url, headers=headers, json=data)
        
        if resp.status_code == 200:
            logger.info(f"✅ Assignments: {len(assignments)}件同期完了")
        else:
            logger.error(f"❌ エラー: {resp.status_code} - {resp.text}")
    
    finally:
        db.close()


def sync_actuals():
    """Actuals同期"""
    logger.info("\n[4/4] Actuals同期...")
    
    db = SessionLocal()
    try:
        actuals = db.query(Actual).all()
        
        if not actuals:
            logger.info("  → 同期対象なし")
            return
        
        app_id = APPS["actuals"]["app_id"]
        token = APPS["actuals"]["token"]
        headers = {"X-Cybozu-API-Token": token, "Content-Type": "application/json"}
        
        # ドロップダウンオプション追加
        project_ids = list(set(a.project_id for a in actuals))
        worker_ids = list(set(a.worker_id for a in actuals))
        role_ids = list(set(a.role_id for a in actuals))
        statuses = list(set(a.status for a in actuals if a.status))
        period_keys = list(set(a.period_key for a in actuals if a.period_key))
        
        add_dropdown_options(app_id, token, "project_id", project_ids)
        add_dropdown_options(app_id, token, "worker_id", worker_ids)
        add_dropdown_options(app_id, token, "role_id", role_ids)
        add_dropdown_options(app_id, token, "status", statuses)
        add_dropdown_options(app_id, token, "period_key", period_keys)
        
        # レコード投入
        records = []
        for act in actuals:
            record = {
                "actual_id": {"value": act.id},
                "project_id": {"value": act.project_id},
                "worker_id": {"value": act.worker_id},
                "role_id": {"value": act.role_id},
                "assignment_id": {"value": act.assignment_id or ""},
                "work_date": {"value": act.work_date.isoformat()},
                "period_key": {"value": act.period_key or ""},
                "status": {"value": act.status or ""},
                "start_time": {"value": act.start_time.strftime("%H:%M") if act.start_time else ""},
                "end_time": {"value": act.end_time.strftime("%H:%M") if act.end_time else ""},
                "calc_minutes_total": {"value": str(act.calc_minutes_total)},
                "calc_minutes_billable": {"value": str(act.calc_minutes_billable)},
                "applied_price_sales": {"value": str(act.applied_price_sales)},
                "applied_price_outsource": {"value": str(act.applied_price_outsource)}
            }
            records.append(record)
        
        url = f"{BASE_URL}/records.json"
        data = {"app": app_id, "records": records}
        resp = requests.post(url, headers=headers, json=data)
        
        if resp.status_code == 200:
            logger.info(f"✅ Actuals: {len(actuals)}件同期完了")
        else:
            logger.error(f"❌ エラー: {resp.status_code} - {resp.text}")
    
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("============================================================")
    logger.info("トランザクションデータ Kintone同期開始")
    logger.info("============================================================")
    
    try:
        sync_projects()
        sync_shift_slots()
        sync_assignments()
        sync_actuals()
        
        logger.info("\n✅ 全トランザクションデータ同期完了")
    except Exception as e:
        logger.error(f"\n❌ 同期失敗: {e}")
        import traceback
        traceback.print_exc()
