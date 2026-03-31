#!/usr/bin/env python
"""CSV直接取り込みスクリプト（マスタデータ用）

kintone_app/*.csv からマスタデータをDBに取り込む
"""
import sys
import csv
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from src.api.deps import SessionLocal
from src.models.master import Client, Worker, Role, Site, ProjectType
from src.models.base import generate_ulid
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def import_workers_from_csv(db: Session, csv_path: str):
    """Workers CSVを取り込む"""
    logger.info(f"[Workers] {csv_path} から取り込み開始")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            # 空行スキップ
            if not row.get('worker_id'):
                continue
            
            # 既存チェック（emailで）
            existing = db.query(Worker).filter(Worker.email == row.get('email')).first()
            if existing:
                logger.info(f"  スキップ（既存）: {row['worker_id']} {row['name']}")
                continue
            
            worker = Worker(
                id=generate_ulid(),
                name=row['name'],
                email=row.get('email') or None,
                phone=row.get('phone') or None,
                is_active=(row.get('is_active', '有効') == '有効'),
                notes=row.get('notes') or None
            )
            db.add(worker)
            count += 1
            logger.info(f"  追加: {row['worker_id']} {worker.name}")
        
        db.commit()
        logger.info(f"[Workers] {count}件 取り込み完了\n")
        return count


def import_clients_from_csv(db: Session, csv_path: str):
    """Clients CSVを取り込む"""
    logger.info(f"[Clients] {csv_path} から取り込み開始")
    
    # まずCSVを確認
    with open(csv_path, 'r', encoding='shift_jis') as f:
        content = f.read()
        if not content.strip():
            logger.warning(f"[Clients] CSVファイルが空です")
            return 0
    
    with open(csv_path, 'r', encoding='shift_jis') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if not row.get('client_id'):
                continue
            
            existing = db.query(Client).filter(Client.code == row['client_id']).first()
            if existing:
                logger.info(f"  スキップ（既存）: {row['client_id']} {row['name']}")
                continue
            
            client = Client(
                id=generate_ulid(),
                code=row['client_id'],
                name=row['name'],
                address=row.get('address') or None,
                contact_name=row.get('contact_name') or None,
                contact_email=row.get('contact_email') or None,
                notes=row.get('notes') or None
            )
            db.add(client)
            count += 1
            logger.info(f"  追加: {client.code} {client.name}")
        
        db.commit()
        logger.info(f"[Clients] {count}件 取り込み完了\n")
        return count


def import_sites_from_csv(db: Session, csv_path: str):
    """Sites CSVを取り込む"""
    logger.info(f"[Sites] {csv_path} から取り込み開始")
    
    with open(csv_path, 'r', encoding='shift_jis') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if not row.get('site_id'):
                continue
            
            existing = db.query(Site).filter(Site.code == row['site_id']).first()
            if existing:
                logger.info(f"  スキップ（既存）: {row['site_id']} {row['name']}")
                continue
            
            site = Site(
                id=generate_ulid(),
                code=row['site_id'],
                name=row['name'],
                address=row.get('address') or None,
                notes=row.get('notes') or None
            )
            db.add(site)
            count += 1
            logger.info(f"  追加: {site.code} {site.name}")
        
        db.commit()
        logger.info(f"[Sites] {count}件 取り込み完了\n")
        return count


def import_roles_from_csv(db: Session, csv_path: str):
    """Roles CSVを取り込む"""
    logger.info(f"[Roles] {csv_path} から取り込み開始")
    
    with open(csv_path, 'r', encoding='shift_jis') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if not row.get('role_id'):
                continue
            
            existing = db.query(Role).filter(Role.code == row['role_id']).first()
            if existing:
                logger.info(f"  スキップ（既存）: {row['role_id']} {row['name']}")
                continue
            
            role = Role(
                id=generate_ulid(),
                code=row['role_id'],
                name=row['name'],
                description=row.get('description') or None
            )
            db.add(role)
            count += 1
            logger.info(f"  追加: {role.code} {role.name}")
        
        db.commit()
        logger.info(f"[Roles] {count}件 取り込み完了\n")
        return count


def import_project_types_from_csv(db: Session, csv_path: str):
    """ProjectTypes CSVを取り込む"""
    logger.info(f"[ProjectTypes] {csv_path} から取り込み開始")
    
    with open(csv_path, 'r', encoding='shift_jis') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if not row.get('project_type_id'):
                continue
            
            existing = db.query(ProjectType).filter(ProjectType.code == row['project_type_id']).first()
            if existing:
                logger.info(f"  スキップ（既存）: {row['project_type_id']} {row['name']}")
                continue
            
            ptype = ProjectType(
                id=generate_ulid(),
                code=row['project_type_id'],
                name=row['name'],
                description=row.get('description') or None
            )
            db.add(ptype)
            count += 1
            logger.info(f"  追加: {ptype.code} {ptype.name}")
        
        db.commit()
        logger.info(f"[ProjectTypes] {count}件 取り込み完了\n")
        return count


def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使用法: python scripts/csv_import_master.py <app_name>")
        print("app_name: workers, clients, sites, roles, project_types, all")
        sys.exit(1)
    
    app_name = sys.argv[1].lower()
    
    logger.info("=" * 60)
    logger.info("CSVマスタデータ取り込み")
    logger.info("=" * 60)
    
    db = SessionLocal()
    try:
        csv_dir = Path('kintone_app')
        total = 0
        
        if app_name in ['workers', 'all']:
            total += import_workers_from_csv(db, csv_dir / 'workers_utf8.csv')
        
        if app_name in ['clients', 'all']:
            total += import_clients_from_csv(db, csv_dir / 'clients_sjis.csv')
        
        if app_name in ['sites', 'all']:
            total += import_sites_from_csv(db, csv_dir / 'sites_sjis.csv')
        
        if app_name in ['roles', 'all']:
            total += import_roles_from_csv(db, csv_dir / 'roles_sjis.csv')
        
        if app_name in ['project_types', 'all']:
            total += import_project_types_from_csv(db, csv_dir / 'project_types_sjis.csv')
        
        logger.info("=" * 60)
        logger.info(f"取り込み完了: 合計 {total}件")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"エラー: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
