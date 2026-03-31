"""初期マスタデータ投入スクリプト

使用方法:
    python scripts/import_master_data.py

前提:
    - alembic upgrade head 実行済み
    
機能:
    - 最低限のマスタデータをDBに直接投入（テスト用）
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from src.api.deps import engine, SessionLocal
from src.models.master import Client, Worker, Role, Site, ProjectType
from src.models.transaction import Project
from src.models.base import generate_ulid
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def import_all_master_data():
    """すべてのマスタデータを直接投入（最小限）"""
    
    logger.info("=" * 60)
    logger.info("マスタデータ投入開始")
    logger.info("=" * 60)
    
    db = SessionLocal()
    try:
        # 既存データ確認
        existing_clients = db.query(Client).count()
        if existing_clients > 0:
            logger.info(f"既存データあり（クライアント: {existing_clients}件）")
            logger.info("スキップします（削除する場合は手動で vanzai.db を削除してください）")
            return
        
        # 1. クライアント
        logger.info("\n[1/6] クライアントを作成中...")
        clients = [
            Client(
                id=generate_ulid(),
                code="CL001",
                name="テストクライアント株式会社",
                address="東京都渋谷区1-1-1",
                contact_name="経理部 田中",
                contact_email="keiri@test-client.co.jp",
                notes="月末締め翌月末払い",
            ),
            Client(
                id=generate_ulid(),
                code="CL002",
                name="サンプル企業合同会社",
                address="大阪府大阪市2-2-2",
                contact_name="管理部 佐藤",
                contact_email="info@sample-corp.jp",
                notes="月末締め翌々月10日払い",
            ),
        ]
        db.add_all(clients)
        db.flush()
        logger.info(f"  ✅ {len(clients)} 件作成")
        
        # 2. ロール
        logger.info("\n[2/6] ロールを作成中...")
        roles = [
            Role(id=generate_ulid(), code="MGR", name="マネージャー"),
            Role(id=generate_ulid(), code="STAFF", name="スタッフ"),
            Role(id=generate_ulid(), code="PART", name="パートタイマー"),
        ]
        db.add_all(roles)
        db.flush()
        logger.info(f"  ✅ {len(roles)} 件作成")
        
        # 3. 稼働者
        logger.info("\n[3/6] 稼働者を作成中...")
        workers = [
            Worker(
                id=generate_ulid(),
                name="山田太郎",
                email="yamada@example.com",
                phone="090-1234-5678",
            ),
            Worker(
                id=generate_ulid(),
                name="佐藤花子",
                email="sato@example.com",
                phone="090-2345-6789",
            ),
            Worker(
                id=generate_ulid(),
                name="鈴木次郎",
                email="suzuki@example.com",
                phone="090-3456-7890",
            ),
        ]
        db.add_all(workers)
        db.flush()
        logger.info(f"  ✅ {len(workers)} 件作成")
        
        # 4. 案件タイプ
        logger.info("\n[4/6] 案件タイプを作成中...")
        project_types = [
            ProjectType(id=generate_ulid(), code="TYPE_A", name="通常案件"),
            ProjectType(id=generate_ulid(), code="TYPE_B", name="定期案件"),
        ]
        db.add_all(project_types)
        db.flush()
        logger.info(f"  ✅ {len(project_types)} 件作成")
        
        # 5. サイト
        logger.info("\n[5/6] サイトを作成中...")
        sites = [
            Site(
                id=generate_ulid(),
                code="SITE001",
                name="本社",
                address="東京都千代田区1-1-1",
            ),
            Site(
                id=generate_ulid(),
                code="SITE002",
                name="支社A",
                address="神奈川県横浜市2-2-2",
            ),
        ]
        db.add_all(sites)
        db.flush()
        logger.info(f"  ✅ {len(sites)} 件作成")
        
        # 6. 案件
        logger.info("\n[6/6] 案件を作成中...")
        projects = [
            Project(
                id=generate_ulid(),
                code="PRJ001",
                name="テストプロジェクト1",
                client_id=clients[0].id,
                project_type_id=project_types[0].id,
                start_date=datetime(2026, 1, 1).date(),
                end_date=datetime(2026, 12, 31).date(),
            ),
        ]
        db.add_all(projects)
        db.flush()
        logger.info(f"  ✅ {len(projects)} 件作成")
        
        # コミット
        db.commit()
        
        # データ確認
        logger.info("\n" + "=" * 60)
        logger.info("データ投入完了 - 確認")
        logger.info("=" * 60)
        
        counts = {
            "クライアント": db.query(Client).count(),
            "稼働者": db.query(Worker).count(),
            "ロール": db.query(Role).count(),
            "案件": db.query(Project).count(),
            "サイト": db.query(Site).count(),
            "案件タイプ": db.query(ProjectType).count(),
        }
        
        for name, count in counts.items():
            logger.info(f"  {name}: {count} 件")
        
        logger.info("\n✅ マスタデータの投入が完了しました")
        
    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    import_all_master_data()
