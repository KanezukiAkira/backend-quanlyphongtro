import logging
from sqlalchemy import inspect, text
from app.core.database import Base, engine, SessionLocal, ensure_database_exists
from app.core.security import get_password_hash
from app.models import (
    User,
    Room,
    ArchivedTenant,
    Contract,
    UtilityReading,
    Invoice,
    Feedback,
    Notification,
    EmailLog,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _upgrade_existing_tables():
    """Ensure all newly added columns exist on existing MySQL tables."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    alter_statements = {
        "rooms": [
            ("floor", "INT NOT NULL DEFAULT 1"),
            ("room_seq", "INT NOT NULL DEFAULT 1"),
            ("electricity_rate", "DOUBLE NOT NULL DEFAULT 3500"),
            ("water_rate", "DOUBLE NOT NULL DEFAULT 20000"),
            ("parking_fee", "DOUBLE NOT NULL DEFAULT 100000"),
            ("trash_fee", "DOUBLE NOT NULL DEFAULT 30000"),
            ("wifi_fee", "DOUBLE NOT NULL DEFAULT 50000"),
            ("maintenance_fee", "DOUBLE NOT NULL DEFAULT 20000"),
        ],
        "users": [
            ("gender", "VARCHAR(30) NULL"),
            ("birth_date", "DATE NULL"),
            ("cccd", "VARCHAR(50) NULL"),
            ("hometown", "VARCHAR(255) NULL"),
            ("room_id", "INT NULL"),
            ("is_profile_completed", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("token_version", "INT NOT NULL DEFAULT 1"),
        ],
        "contracts": [
            ("parking_fee", "DOUBLE NOT NULL DEFAULT 100000"),
            ("trash_fee", "DOUBLE NOT NULL DEFAULT 30000"),
            ("wifi_fee", "DOUBLE NOT NULL DEFAULT 50000"),
            ("maintenance_fee", "DOUBLE NOT NULL DEFAULT 20000"),
            ("payment_due_day", "INT NOT NULL DEFAULT 10"),
            ("landlord_name", "VARCHAR(255) NOT NULL DEFAULT 'Nguyễn Minh Hoàng'"),
            ("landlord_cccd", "VARCHAR(50) NOT NULL DEFAULT '079085001234'"),
            ("landlord_phone", "VARCHAR(50) NOT NULL DEFAULT '0901234567'"),
            ("landlord_address", "VARCHAR(500) NOT NULL DEFAULT 'Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh'"),
        ],
        "invoices": [
            ("overdue_date", "DATE NULL"),
            ("old_electricity", "DOUBLE NOT NULL DEFAULT 0"),
            ("new_electricity", "DOUBLE NOT NULL DEFAULT 0"),
            ("old_water", "DOUBLE NOT NULL DEFAULT 0"),
            ("new_water", "DOUBLE NOT NULL DEFAULT 0"),
            ("parking_fee", "DOUBLE NOT NULL DEFAULT 100000"),
            ("trash_fee", "DOUBLE NOT NULL DEFAULT 30000"),
            ("wifi_fee", "DOUBLE NOT NULL DEFAULT 50000"),
            ("maintenance_fee", "DOUBLE NOT NULL DEFAULT 20000"),
            ("paid_at", "DATETIME NULL"),
            ("transaction_ref", "VARCHAR(100) NULL"),
            ("bill_image_url", "LONGTEXT NULL"),
            ("bill_uploaded_at", "DATETIME NULL"),
            ("is_reconciled", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("email_sent", "TINYINT(1) NOT NULL DEFAULT 0"),
            ("email_sent_at", "DATETIME NULL"),
        ],
    }

    with engine.begin() as conn:
        for table_name, columns in alter_statements.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            for col_name, col_def in columns:
                if col_name not in existing_cols:
                    logger.info(f"Adding missing column '{col_name}' to table '{table_name}'...")
                    conn.execute(text(f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_def};"))


def init_db():
    # 1. Ensure database exists
    logger.info("Ensuring database exists...")
    ensure_database_exists()

    # 2. Create tables & upgrade any older columns
    logger.info("Creating all tables in MySQL...")
    Base.metadata.create_all(bind=engine)
    _upgrade_existing_tables()

    # 3. Seed default admin landlord
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            logger.info("Seeding default landlord user (admin / admin123)...")
            admin_user = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="Nguyễn Minh Hoàng (Chủ trọ)",
                phone="0901234567",
                email="admin@phongtro.vn",
                cccd="079085001234",
                hometown="TP. Hồ Chí Minh",
                role="LANDLORD",
                is_profile_completed=True,
                token_version=1,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            logger.info(f"Default landlord created with ID: {admin_user.id}")
        else:
            logger.info("Landlord admin user already exists.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

    # 4. Verify created tables
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Database initialized successfully. Tables found: {tables}")
    return tables


if __name__ == "__main__":
    init_db()
