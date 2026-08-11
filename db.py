"""
Shared DB connection helper, used by both projects' load.py scripts.
Reads connection details from a .env file (copy .env.example -> .env and
fill in your Supabase/Postgres credentials -- see README for how to get
those from the Supabase dashboard).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(Path(__file__).parent / ".env")


def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "postgres")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD")
        if not host or not password:
            raise RuntimeError(
                "No DB credentials found. Copy .env.example to .env and fill it in."
            )
        url = f"postgresql://{user}:{password}@{host}:{port}/{name}"
    return create_engine(url)


def run_sql_file(engine, path):
    """Run a .sql file containing multiple ; separated statements."""
    sql = Path(path).read_text(encoding="utf-8")
    with engine.begin() as conn:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.exec_driver_sql(statement)
