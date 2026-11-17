import os
from pathlib import Path
from dotenv import load_dotenv

# Path to backend directory and .env file
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Quản Lý Phòng Trọ")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:123456@localhost:3306/quanlyphongtro_db"
    )
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "quanlyphongtro_super_secret_jwt_key_2026_very_secure_and_reliable"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


settings = Settings()
