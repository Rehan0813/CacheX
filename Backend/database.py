import os
import pymysql
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database configuration from Environment Variables
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_DB = os.getenv("MYSQL_DB", "cachex")

# Check if a custom DATABASE_URL was provided
custom_url = os.getenv("DATABASE_URL")

engine = None
Base = declarative_base()

def get_engine():
    global engine
    if engine is not None:
        return engine

    # 1. Custom URL provided (e.g. Postgres, SQLite, or preconfigured MySQL)
    if custom_url:
        connect_args = {"check_same_thread": False} if "sqlite" in custom_url else {}
        engine = create_engine(custom_url, connect_args=connect_args)
        return engine

    # 2. Attempt MySQL connection if credentials or host configured
    if MYSQL_PASSWORD:
        try:
            # Connect to MySQL server without specifying database
            connection = pymysql.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                connect_timeout=3
            )
            cursor = connection.cursor()
            clean_db = "".join(c for c in MYSQL_DB if c.isalnum() or c == "_")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{clean_db}`")
            connection.commit()
            cursor.close()
            connection.close()

            mysql_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{clean_db}"
            engine = create_engine(mysql_url, pool_pre_ping=True)
            print(f"Connected to MySQL database: {clean_db}")
            return engine
        except Exception as e:
            print(f"MySQL unavailable ({e}). Falling back to SQLite.")

    # 3. Default fallback: SQLite for zero-config reliability
    sqlite_path = os.path.join(os.path.dirname(__file__), "cachex.db")
    sqlite_url = f"sqlite:///{sqlite_path}"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    print(f"Using SQLite database: {sqlite_url}")
    return engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
