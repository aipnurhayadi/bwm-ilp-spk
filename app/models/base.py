from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for SQLAlchemy models using dataclass support."""

    __abstract__ = True
