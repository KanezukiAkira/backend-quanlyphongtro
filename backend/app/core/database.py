import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings


def ensure_database_exists(database_url: str = settings.DATABASE_URL) -> None:
    """Ensure that the MySQL database specified in DATABASE_URL exists."""
    url = make_url(database_url)
    if "mysql" in url.drivername:
        db_name = url.database
        if db_name:
            # Connect to MySQL server without specifying the target database
            host = url.host or "localhost"
            port = url.port or 3306
            user = url.username or "root"
            password = url.password or ""
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                autocommit=True
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                    )
            finally:
                conn.close()


# Ensure database exists before creating the SQLAlchemy engine
ensure_database_exists()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
