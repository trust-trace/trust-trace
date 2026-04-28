from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tarkov.database.models import Event, Firm, Person, Source
from tarkov.database.session import Base


class NsaCompanyAssessment(Base):
    __tablename__ = "nsa_company_assessment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("firm.id", ondelete="CASCADE"), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(50), nullable=False)
    company_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    people_scored: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NsaPersonAssessment(Base):
    __tablename__ = "nsa_person_assessment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_assessment_id: Mapped[int] = mapped_column(ForeignKey("nsa_company_assessment.id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), nullable=False)
    person_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    analysis: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NsaEvidence(Base):
    __tablename__ = "nsa_evidence"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_assessment_id: Mapped[int] = mapped_column(ForeignKey("nsa_person_assessment.id", ondelete="CASCADE"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
