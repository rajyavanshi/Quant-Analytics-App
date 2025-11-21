# database_setup.py
# --------------------------------------------
# This script creates the initial database schema for the Quant Analytics App.
# It defines tables for tick data, resampled data, and analytics results.

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# ------------------ Configuration ------------------
# Define database path inside your project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "quant_data.db")
DB_URL = f"sqlite:///{DB_PATH}"

# Initialize SQLAlchemy base and engine
Base = declarative_base()
engine = create_engine(DB_URL, echo=True)  # echo=True shows SQL logs for debugging
metadata = MetaData()

# ------------------ Table Definitions ------------------
class TickData(Base):
    __tablename__ = "tick_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

class ResampledData(Base):
    __tablename__ = "resampled_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    interval = Column(String, nullable=False)  # e.g. "1s", "1m", "5m"
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

class AnalyticsResults(Base):
    __tablename__ = "analytics_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float)
    timestamp = Column(DateTime, nullable=False)

# ------------------ Create All Tables ------------------
if __name__ == "__main__":
    print(" Creating SQLite database and tables...")
    Base.metadata.create_all(engine)
    print(f" Database created at: {DB_PATH}")
