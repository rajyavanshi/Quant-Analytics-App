"""Database initialization compatibility layer.

The application uses ``database/quant_data.db`` as its single runtime database.
This module keeps the historical ``backend.data_storage.init_db`` entry point
working while delegating schema creation to the canonical database module.
"""

from database.database_setup import init_db

__all__ = ["init_db"]
