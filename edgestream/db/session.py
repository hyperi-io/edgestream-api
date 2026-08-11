from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from edgestream.core.config import settings

DB_URI = settings.SQLALCHEMY_DATABASE_URI
IS_SQLITE = DB_URI.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(
        DB_URI,
        connect_args={"check_same_thread": False},   # critical for background tasks
        pool_pre_ping=True,
        poolclass=QueuePool,
        pool_size=5,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")     # concurrent readers during writes
        cur.execute("PRAGMA synchronous=NORMAL;")   # good durability/perf with WAL
        cur.execute("PRAGMA busy_timeout=5000;")    # wait up to 5s on locks
        cur.execute("PRAGMA foreign_keys=ON;")      # enforce FKs
        cur.close()
else:
    engine = create_engine(
        DB_URI,
        poolclass=QueuePool,
        pool_size=10,
        pool_pre_ping=True,
        future=True,
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,   # keeps objects usable after commit
    future=True,
)

Base = declarative_base()
