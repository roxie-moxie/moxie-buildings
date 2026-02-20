from moxie.config import DATABASE_URL
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False  # required for SQLite multi-threaded use

engine = create_engine(DATABASE_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_conn, connection_record):
    """Enable WAL mode for concurrent reads/writes during batch scraping."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # Wait up to 30s for write locks
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
