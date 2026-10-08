"""スケジューラー実行スクリプト

使用方法:
    python scripts/scheduler_runner.py
    python scripts/scheduler_runner.py --run-once weekly_reminder

機能:
    - 週次催促（月曜9時）
    - 日次ダッシュボード更新（毎日6時）
    - 月次請求書生成（毎月1日10時）

停止方法:
    Ctrl+C
"""
import argparse
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.scheduler import get_scheduler, initialize_default_jobs
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VANZAI スケジューラー実行")
    parser.add_argument(
        "--run-once",
        choices=["weekly_reminder", "daily_update", "monthly_invoice"],
        help="指定したジョブを1回だけ実行して終了します",
    )
    return parser.parse_args()


def main():
    """スケジューラーを起動してバックグラウンドで実行"""
    args = parse_args()
    
    logger.info("=" * 60)
    logger.info("VANZAIスケジューラー起動")
    logger.info("=" * 60)
    
    try:
        # スケジューラー取得
        scheduler = get_scheduler()

        if args.run_once:
            logger.info("単発実行モード: %s", args.run_once)
            logger.info(
                "EMAIL_DRY_RUN=%s EMAIL_PROVIDER=%s LOOKAHEAD_DAYS=%s",
                os.getenv("EMAIL_DRY_RUN", "true"),
                os.getenv("EMAIL_PROVIDER", "gmail"),
                os.getenv("SCHEDULER_WEEKLY_LOOKAHEAD_DAYS", "14"),
            )
            scheduler.run_job_once(args.run_once)
            scheduler.shutdown()
            logger.info("✅ 単発実行が完了しました")
            return
        
        # デフォルトジョブを登録
        logger.info("\nデフォルトジョブを登録中...")
        initialize_default_jobs()
        logger.info("✅ スケジューラー初期化完了\n")
        
        # 登録済みジョブを表示
        jobs = scheduler.list_jobs()
        if jobs:
            logger.info("登録済みジョブ:")
            for job in jobs:
                next_run = job.get('next_run')
                if next_run:
                    next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    next_run_str = "未設定"
                logger.info(f"  - {job['id']}: 次回実行 {next_run_str}")
        else:
            logger.warning("  ジョブが登録されていません")
        
        logger.info("\nスケジューラーを実行中... (停止: Ctrl+C)\n")
        logger.info("=" * 60)
        
        # メインループ（1分ごとに状態確認）
        while True:
            time.sleep(60)
            
            # 1時間ごとにステータス出力
            now = datetime.now()
            if now.minute == 0:
                logger.info(f"[{now.strftime('%Y-%m-%d %H:%M')}] スケジューラー稼働中")
                
                # 実行中のジョブを確認
                running_jobs = [j for j in scheduler.scheduler.get_jobs() if j.next_run_time]
                if running_jobs:
                    logger.info(f"  稼働中のジョブ: {len(running_jobs)} 件")
    
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("停止シグナルを受信しました")
        logger.info("=" * 60)
        
        # スケジューラーを停止
        scheduler.shutdown()
        logger.info("✅ スケジューラーを停止しました")
        
    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {e}", exc_info=True)
        
        # エラー時もスケジューラーを停止
        try:
            get_scheduler().shutdown()
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
