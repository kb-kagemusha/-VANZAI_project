"""
JWT認証

FastAPI JWT認証の実装
- Access Token / Refresh Token
- パスワードハッシュ化
- トークン検証

仕様参照: DESIGN_SPEC_v0.3.md「5. ロールと権限」
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os

from src.models.master import User
from src.api.deps import get_db


# 環境変数から設定取得
_raw_secret = os.getenv("JWT_SECRET_KEY", "")
if not _raw_secret:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set. "
        "Set it to a long random string before starting the server."
    )
SECRET_KEY = _raw_secret
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# OAuth2スキーマ（トークンURL指定）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    パスワード検証
    
    Args:
        plain_password: 平文パスワード
        hashed_password: ハッシュ化パスワード
    
    Returns:
        True: パスワード一致, False: 不一致
    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """
    パスワードハッシュ化
    
    Args:
        password: 平文パスワード
    
    Returns:
        ハッシュ化パスワード
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    アクセストークン生成
    
    Args:
        data: トークンに含めるペイロード（例: {"sub": "username"}）
        expires_delta: 有効期限（Noneの場合は30分）
    
    Returns:
        JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    リフレッシュトークン生成
    
    Args:
        data: トークンに含めるペイロード（例: {"sub": "username"}）
        expires_delta: 有効期限（Noneの場合は7日）
    
    Returns:
        JWT refresh token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    現在のユーザー取得（JWT検証）
    
    Args:
        token: JWT access token
        db: データベースセッション
    
    Returns:
        Userオブジェクト
    
    Raises:
        HTTPException: トークン無効、ユーザー不在、非アクティブ
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # データベースからユーザー取得
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    アクティブユーザー取得（冗長性のため残す）
    
    Args:
        current_user: 現在のユーザー
    
    Returns:
        Userオブジェクト
    """
    return current_user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    ユーザー認証
    
    Args:
        db: データベースセッション
        username: ユーザー名
        password: 平文パスワード
    
    Returns:
        認証成功: Userオブジェクト, 失敗: None
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not user.is_active:
        return None
    if not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ===========================
# ユーティリティ関数
# ===========================

def create_user_with_hashed_password(
    db: Session,
    username: str,
    email: str,
    password: str,
    role: str = "worker"
) -> User:
    """
    新規ユーザー作成（パスワードハッシュ化）
    
    Args:
        db: データベースセッション
        username: ユーザー名
        email: メールアドレス
        password: 平文パスワード
        role: ロール（admin/ops/accounting/site_manager/worker）
    
    Returns:
        作成したUserオブジェクト
    """
    from src.models.enums import UserRole
    
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=UserRole[role.upper()].value,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
