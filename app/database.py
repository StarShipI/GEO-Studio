"""数据库引擎与会话。整个项目只用同步 SQLAlchemy，保持最简单。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_engine_kwargs = {}
if settings.database_url.startswith("sqlite"):
    # SQLite 多线程访问 + 写锁重试（uvicorn 服务与采样脚本并发写入时避免 database is locked）
    _engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": 60,
    }

engine = create_engine(settings.database_url, **_engine_kwargs)


def _enable_wal(dbapi_connection, connection_record):
    """每个新连接开启 WAL：读写不互斥，显著降低并发写冲突。"""
    try:
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=60000")
        cur.close()
    except Exception:
        pass


if settings.database_url.startswith("sqlite"):
    from sqlalchemy import event

    event.listen(engine, "connect", _enable_wal)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI 依赖：每个请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表（幂等）。模型必须先被导入注册。"""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
