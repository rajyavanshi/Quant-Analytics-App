# db_connection.py
# --------------------------------------------
# Helper module for database connections and sessions.
# Import this wherever database access is needed.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "quant_data.db")
DB_URL = f"sqlite:///{DB_PATH}"

# SQLAlchemy engine and session factory
engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

def get_db_session():
    """Return a new SQLAlchemy session."""
    return SessionLocal()

