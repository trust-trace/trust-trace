from sqlalchemy import BigInteger, Column, Numeric, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class RiskKeyword(Base):
    """Maps to the risk_keywords table from 001_initial_schema.sql."""

    __tablename__ = "risk_keywords"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, unique=True)
    category = Column(String(100), nullable=False)
    base_weight = Column(Numeric(4, 3), nullable=False)
