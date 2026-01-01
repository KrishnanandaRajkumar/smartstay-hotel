import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "hotel_booking"),
    "user": os.getenv("DB_USER", "hotel_user"),
    "password": os.getenv("DB_PASSWORD", "hotel123"),
    "port": int(os.getenv("DB_PORT", 5432))
}

SECRET_KEY = os.getenv("SECRET_KEY", "smartstay_fallback_secret")