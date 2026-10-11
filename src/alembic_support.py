"""改訂IDが32文字を超えるため、PostgreSQLの版管理列だけを広げる。"""
from sqlalchemy import text


def widen_existing_version_num(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    width = connection.execute(
        text(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'alembic_version'
              AND column_name = 'version_num'
            """
        )
    ).scalar()
    if width is not None and width < 128:
        connection.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"))
    if connection.in_transaction():
        connection.commit()
