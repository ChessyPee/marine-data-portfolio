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
    # Splitting on ";" is naive -- a "--" comment line that happens to
    # contain a "." in normal English prose (e.g. "too sparse for a
    # trend; the rest of this sentence...") gets cut mid-line, turning
    # the tail into un-commented, invalid SQL. Strip "-- ..." comment
    # content per line BEFORE splitting on ";", so punctuation inside
    # comments can never influence the split (found via a real failure,
    # not guessed) -- this assumes no line has a literal "--" inside a
    # string value that must survive, true of every .sql file here.
    lines = []
    for line in sql.split("\n"):
        idx = line.find("--")
        lines.append(line[:idx] if idx != -1 else line)
    sql_no_comments = "\n".join(lines)
    with engine.begin() as conn:
        for statement in sql_no_comments.split(";"):
            statement = statement.strip()
            if statement:
                # psycopg2's cursor.execute() treats a bare "%" as a
                # pyformat parameter marker even inside SQL text --
                # escape to "%%" so a literal "%" (e.g. "50% of rows...",
                # or a LIKE 'foo%' pattern) doesn't crash with "dict is
                # not a sequence".
                conn.exec_driver_sql(statement.replace("%", "%%"))
