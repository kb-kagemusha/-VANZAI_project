"""
CSV高度処理ユーティリティ

- 自動エンコーディング検出（Shift-JIS/UTF-8）
- 大容量CSVのチャンク処理（メモリ効率化）
- 進捗表示
"""
import io
from typing import Iterator, Callable, Optional
import pandas as pd


def detect_encoding(file_content: bytes) -> str:
    """
    CSVファイルのエンコーディングを自動検出
    
    Args:
        file_content: バイト列
    
    Returns:
        エンコーディング名（"utf-8", "shift-jis"等）
    """
    try:
        import chardet
        result = chardet.detect(file_content)
        encoding = result.get("encoding", "utf-8")
        
        # Shift-JISの各種バリエーションを統一
        if encoding and encoding.lower() in ["shift_jis", "shiftjis", "cp932", "windows-31j"]:
            return "shift-jis"
        
        return encoding or "utf-8"
    except ImportError:
        # chardetがインストールされていない場合はUTF-8を試してからShift-JISへフォールバック
        try:
            file_content.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "shift-jis"


def read_csv_auto_encoding(
    file_path: Optional[str] = None,
    file_content: Optional[bytes] = None
) -> pd.DataFrame:
    """
    エンコーディング自動検出してCSVを読み込む
    
    Args:
        file_path: ファイルパス（file_contentと排他）
        file_content: バイト列（file_pathと排他）
    
    Returns:
        DataFrame
    """
    if file_path:
        with open(file_path, "rb") as f:
            content = f.read()
    elif file_content:
        content = file_content
    else:
        raise ValueError("Either file_path or file_content must be provided")
    
    # エンコーディング検出
    encoding = detect_encoding(content)
    
    # DataFrameに変換
    text_content = content.decode(encoding)
    df = pd.read_csv(io.StringIO(text_content))
    
    return df


def read_csv_chunks(
    file_path: Optional[str] = None,
    file_content: Optional[str] = None,
    chunk_size: int = 1000,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Iterator[pd.DataFrame]:
    """
    大容量CSVをチャンクごとに読み込む
    
    Args:
        file_path: ファイルパス（file_contentと排他）
        file_content: 文字列（file_pathと排他）
        chunk_size: チャンクサイズ（行数）
        progress_callback: 進捗コールバック関数 callback(processed_rows, total_rows)
    
    Yields:
        DataFrame（chunk_size行ずつ）
    """
    if file_path:
        # ファイルから読み込み
        # エンコーディング自動検出
        with open(file_path, "rb") as f:
            content_bytes = f.read()
        encoding = detect_encoding(content_bytes)
        
        # 総行数を先に計算（進捗表示用）
        total_rows = None
        if progress_callback:
            df_count = pd.read_csv(file_path, encoding=encoding)
            total_rows = len(df_count)
        
        # チャンク読み込み
        processed_rows = 0
        for chunk in pd.read_csv(file_path, encoding=encoding, chunksize=chunk_size):
            processed_rows += len(chunk)
            
            if progress_callback and total_rows:
                progress_callback(processed_rows, total_rows)
            
            yield chunk
    
    elif file_content:
        # 文字列から読み込み
        # 総行数を先に計算
        total_rows = None
        if progress_callback:
            df_count = pd.read_csv(io.StringIO(file_content))
            total_rows = len(df_count)
        
        # チャンク読み込み
        processed_rows = 0
        for chunk in pd.read_csv(io.StringIO(file_content), chunksize=chunk_size):
            processed_rows += len(chunk)
            
            if progress_callback and total_rows:
                progress_callback(processed_rows, total_rows)
            
            yield chunk
    
    else:
        raise ValueError("Either file_path or file_content must be provided")


def process_large_csv(
    file_path: Optional[str] = None,
    file_content: Optional[str] = None,
    process_func: Callable[[pd.DataFrame], None] = None,
    chunk_size: int = 1000,
    show_progress: bool = True
) -> dict:
    """
    大容量CSVを効率的に処理
    
    Args:
        file_path: ファイルパス
        file_content: 文字列
        process_func: 各チャンクを処理する関数 func(chunk_df)
        chunk_size: チャンクサイズ（行数）
        show_progress: 進捗表示
    
    Returns:
        {"total_rows": 総行数, "chunks": チャンク数}
    """
    total_rows = 0
    chunk_count = 0
    
    def progress_callback(processed, total):
        if show_progress:
            percentage = (processed / total) * 100
            print(f"Progress: {processed}/{total} ({percentage:.1f}%)")
    
    callback = progress_callback if show_progress else None
    
    for chunk in read_csv_chunks(
        file_path=file_path,
        file_content=file_content,
        chunk_size=chunk_size,
        progress_callback=callback
    ):
        if process_func:
            process_func(chunk)
        
        total_rows += len(chunk)
        chunk_count += 1
    
    if show_progress:
        print(f"✅ Completed: {total_rows} rows processed in {chunk_count} chunks")
    
    return {
        "total_rows": total_rows,
        "chunks": chunk_count
    }


# ===========================
# 使用例
# ===========================

def example_usage():
    """使用例"""
    
    # 例1: エンコーディング自動検出
    df = read_csv_auto_encoding(file_path="data.csv")
    print(f"Loaded {len(df)} rows")
    
    # 例2: 大容量CSVのチャンク処理
    def process_chunk(chunk_df):
        # 各チャンクの処理
        print(f"Processing {len(chunk_df)} rows")
        # データベース挿入などの処理
    
    result = process_large_csv(
        file_path="large_data.csv",
        process_func=process_chunk,
        chunk_size=1000,
        show_progress=True
    )
    
    print(f"Total: {result['total_rows']} rows in {result['chunks']} chunks")
    
    # 例3: メモリ効率的な処理
    total_amount = 0
    for chunk in read_csv_chunks(file_path="transactions.csv", chunk_size=5000):
        total_amount += chunk["amount"].sum()
    
    print(f"Total amount: {total_amount}")


if __name__ == "__main__":
    example_usage()
