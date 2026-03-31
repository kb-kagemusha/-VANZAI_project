"""
銀行振込データ生成サービス

全銀協標準フォーマット（固定長レコード）で振込データを生成
支払確定後の振込手続きを自動化
"""
from datetime import date, datetime
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional

from src.models.transaction import Payout
from src.models.master import Worker


@dataclass
class BankTransferRecord:
    """銀行振込レコード"""
    recipient_name: str  # 受取人名（カナ）
    bank_code: str  # 銀行コード（4桁）
    branch_code: str  # 支店コード（3桁）
    account_type: str  # 口座種別（1:普通, 2:当座）
    account_number: str  # 口座番号（7桁）
    amount: int  # 振込金額（円）
    customer_code: str  # 顧客コード（20桁）
    transfer_date: date  # 振込日
    
    def to_zengin_format(self, sequence_no: int) -> str:
        """
        全銀フォーマット変換（固定長120バイト）
        
        Args:
            sequence_no: シーケンス番号
        
        Returns:
            固定長120バイトの文字列
        """
        # データレコード（2）
        record_type = "2"  # データレコード
        
        # 銀行コード（4桁）
        bank_code = self.bank_code.zfill(4)
        
        # 支店コード（3桁）
        branch_code = self.branch_code.zfill(3)
        
        # 口座種別（1桁: 1=普通, 2=当座）
        account_type = self.account_type
        
        # 口座番号（7桁）
        account_number = self.account_number.zfill(7)
        
        # 受取人名（カナ、30バイト、左詰め空白埋め）
        recipient_name = self.recipient_name.ljust(30)[:30]
        
        # 振込金額（10桁、右詰めゼロ埋め）
        amount_str = str(self.amount).zfill(10)
        
        # 顧客コード（20桁、左詰め空白埋め）
        customer_code = self.customer_code.ljust(20)[:20]
        
        # 振込日（MMDD、4桁）
        transfer_date_str = self.transfer_date.strftime("%m%d")
        
        # 予備（9バイト）
        reserve1 = " " * 9
        
        # シーケンス番号（6桁）
        seq_no = str(sequence_no).zfill(6)
        
        # 予備（26バイト）
        reserve2 = " " * 26
        
        # 固定長120バイトに組み立て
        line = (
            record_type +
            bank_code +
            branch_code +
            account_type +
            account_number +
            recipient_name +
            amount_str +
            customer_code +
            transfer_date_str +
            reserve1 +
            seq_no +
            reserve2
        )
        
        return line


@dataclass
class BankTransferBatch:
    """銀行振込バッチ"""
    batch_id: str  # バッチID
    transfer_date: date  # 振込日
    records: List[BankTransferRecord]
    company_name: str = "VANZAI"  # 委託者名
    company_code: str = "0000000001"  # 委託者コード（10桁）
    
    def generate_zengin_file(self) -> str:
        """
        全銀フォーマットファイル生成
        
        Returns:
            全銀フォーマットの文字列（改行区切り）
        """
        lines = []
        
        # ヘッダレコード（1）
        header = self._generate_header()
        lines.append(header)
        
        # データレコード（2）
        total_amount = 0
        for i, record in enumerate(self.records, start=1):
            data_line = record.to_zengin_format(sequence_no=i)
            lines.append(data_line)
            total_amount += record.amount
        
        # トレーラレコード（8）
        trailer = self._generate_trailer(
            total_count=len(self.records),
            total_amount=total_amount
        )
        lines.append(trailer)
        
        # 改行区切りで結合
        return "\n".join(lines)
    
    def _generate_header(self) -> str:
        """
        ヘッダレコード生成（120バイト）
        
        Returns:
            固定長120バイトの文字列
        """
        # レコード区分（1桁）
        record_type = "1"
        
        # 種別コード（2桁: 21=総合振込）
        type_code = "21"
        
        # コード区分（1桁: 0=JIS）
        code_type = "0"
        
        # 委託者コード（10桁）
        company_code = self.company_code.zfill(10)
        
        # 委託者名（40バイト、カナ、左詰め空白埋め）
        company_name = self.company_name.ljust(40)[:40]
        
        # 振込日（MMDD、4桁）
        transfer_date_str = self.transfer_date.strftime("%m%d")
        
        # 仕向銀行コード・支店コード（予備、7バイト）
        bank_info = " " * 7
        
        # 予備（56バイト）
        reserve = " " * 56
        
        # 固定長120バイトに組み立て
        line = (
            record_type +
            type_code +
            code_type +
            company_code +
            company_name +
            transfer_date_str +
            bank_info +
            reserve
        )
        
        return line
    
    def _generate_trailer(self, total_count: int, total_amount: int) -> str:
        """
        トレーラレコード生成（120バイト）
        
        Args:
            total_count: 総件数
            total_amount: 総金額
        
        Returns:
            固定長120バイトの文字列
        """
        # レコード区分（1桁）
        record_type = "8"
        
        # 総件数（6桁、右詰めゼロ埋め）
        count_str = str(total_count).zfill(6)
        
        # 総金額（12桁、右詰めゼロ埋め）
        amount_str = str(total_amount).zfill(12)
        
        # 予備（101バイト）
        reserve = " " * 101
        
        # 固定長120バイトに組み立て
        line = (
            record_type +
            count_str +
            amount_str +
            reserve
        )
        
        return line
    
    def save_to_file(self, file_path: str) -> None:
        """
        全銀フォーマットファイルをディスクに保存
        
        Args:
            file_path: 保存先ファイルパス
        """
        content = self.generate_zengin_file()
        
        # Shift-JISで保存（全銀フォーマットの標準）
        with open(file_path, "w", encoding="shift-jis") as f:
            f.write(content)


class BankTransferService:
    """
    銀行振込データ生成サービス
    
    支払明細（Payout）から全銀フォーマットの振込データを生成
    """
    
    @staticmethod
    def create_transfer_record_from_payout(
        payout: Payout,
        transfer_date: date
    ) -> Optional[BankTransferRecord]:
        """
        支払明細から振込レコードを生成
        
        Args:
            payout: 支払明細
            transfer_date: 振込日
        
        Returns:
            BankTransferRecord（銀行情報がない場合はNone）
        """
        worker = payout.worker
        
        # 銀行情報の検証
        if not all([
            worker.bank_name,
            worker.bank_code,
            worker.branch_name,
            worker.branch_code,
            worker.account_type,
            worker.account_number
        ]):
            return None
        
        # 受取人名（カナ）
        recipient_name = worker.bank_account_name or worker.name_kana or worker.name
        
        # 口座種別（1:普通, 2:当座）
        account_type_map = {"普通": "1", "当座": "2"}
        account_type = account_type_map.get(worker.account_type, "1")
        
        return BankTransferRecord(
            recipient_name=recipient_name,
            bank_code=worker.bank_code,
            branch_code=worker.branch_code,
            account_type=account_type,
            account_number=worker.account_number,
            amount=int(payout.total_amount),  # 円単位に変換
            customer_code=str(worker.id).zfill(20),  # Worker IDを顧客コードとして使用
            transfer_date=transfer_date
        )
    
    @staticmethod
    def generate_batch_from_payouts(
        payouts: List[Payout],
        transfer_date: date,
        batch_id: Optional[str] = None
    ) -> BankTransferBatch:
        """
        複数の支払明細から振込バッチを生成
        
        Args:
            payouts: 支払明細リスト
            transfer_date: 振込日
            batch_id: バッチID（省略時は自動生成）
        
        Returns:
            BankTransferBatch
        """
        if not batch_id:
            batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        records = []
        for payout in payouts:
            record = BankTransferService.create_transfer_record_from_payout(
                payout, transfer_date
            )
            if record:
                records.append(record)
        
        return BankTransferBatch(
            batch_id=batch_id,
            transfer_date=transfer_date,
            records=records
        )
    
    @staticmethod
    def validate_bank_info(worker: Worker) -> List[str]:
        """
        稼働者の銀行情報を検証
        
        Args:
            worker: 稼働者
        
        Returns:
            エラーメッセージリスト（問題なければ空リスト）
        """
        errors = []
        
        if not worker.bank_name:
            errors.append("銀行名が未設定")
        if not worker.bank_code or len(worker.bank_code) != 4:
            errors.append("銀行コード（4桁）が未設定または不正")
        if not worker.branch_name:
            errors.append("支店名が未設定")
        if not worker.branch_code or len(worker.branch_code) != 3:
            errors.append("支店コード（3桁）が未設定または不正")
        if not worker.account_type:
            errors.append("口座種別が未設定")
        if not worker.account_number or len(worker.account_number) != 7:
            errors.append("口座番号（7桁）が未設定または不正")
        
        return errors
