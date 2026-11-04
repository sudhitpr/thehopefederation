"""Database module for MongoDB connection and indexing."""
from app.database.connection import get_db, init_db, close_db, get_client
from app.database.indexes import create_indexes

__all__ = ["get_db", "init_db", "close_db", "get_client", "create_indexes"]
