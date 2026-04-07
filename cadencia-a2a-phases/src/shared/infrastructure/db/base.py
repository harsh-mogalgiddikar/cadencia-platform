"""
SQLAlchemy DeclarativeBase with constraint naming conventions.
All ORM models across bounded contexts inherit from Base defined here.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# context.md §11: consistent naming conventions for all DB constraints.
# Alembic uses these to auto-generate constraint names in migrations.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Shared declarative base for all Cadencia ORM models.

    All bounded context infrastructure/models.py files import this Base
    and all models are registered on its metadata, which Alembic reads
    via env.py to generate migrations.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
