import logging
from sqlalchemy import inspect
from app.core.database import Base, engine, SessionLocal, ensure_database_exists
from app.core.security import get_password_hash
from app.models.user import User
from app.models.room import Room
from app.models.contract import Contract
from app.models.utility_reading import UtilityReading
from app.models.invoice import Invoice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    # 1. Ensure database exists
    logger.info("Ensuring database exists...")
    ensure_database_exists()

    # 2. Create tables
    logger.info("Creating all tables in MySQL...")
    Base.metadata.create_all(bind=engine)

    # 3. Seed default admin landlord
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            logger.info("Seeding default landlord user (admin / admin123)...")
            admin_user = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="Quản Trị Viên",
                phone="0901234567",
                email="admin@phongtro.vn",
                role="LANDLORD",
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
