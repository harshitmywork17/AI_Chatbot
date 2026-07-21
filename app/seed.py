"""Entrypoint: create the schema and seed dummy data.

Usage:
    python -m app.seed
"""

from app.services.seed_service import seed_database

if __name__ == "__main__":
    seed_database()
