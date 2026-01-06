"""Initialize database schema."""

import asyncio
from sqlalchemy import create_engine
from src.config import get_settings
from src.db.models import Base


def init_database():
    """Initialize database schema."""
    settings = get_settings()
    engine = create_engine(settings.database_url)

    print(f"Creating database schema at {settings.database_url}")
    Base.metadata.create_all(engine)
    print("✅ Database initialized successfully")


if __name__ == "__main__":
    init_database()
