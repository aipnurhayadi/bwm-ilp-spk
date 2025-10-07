"""Import all SQLAlchemy models here for Alembic autogeneration."""

from app.models.base import Base
from app.models.user import User

__all__ = ["Base", "User"]
