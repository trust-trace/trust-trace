"""Tests for pipeline ORM models."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tarkov.database.session import Base
from tarkov.database.models import Firm

from pipeline.models import FinalScoreTimeline, PipelineRun


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


class TestPipelineRun:
    def test_create_and_read(self, session):
        run = PipelineRun(
            id="test-run-1",
            query="Orion Capital",
            status="running",
            phase="scraping",
            article_target=30,
        )
        session.add(run)
        session.commit()

        fetched = session.get(PipelineRun, "test-run-1")
        assert fetched is not None
        assert fetched.query == "Orion Capital"
        assert fetched.status == "running"
        assert fetched.article_target == 30

    def test_update_phase(self, session):
        run = PipelineRun(id="run-2", query="Test", status="running", phase="created")
        session.add(run)
        session.commit()

        run.phase = "scoring"
        run.status = "running"
        session.commit()

        fetched = session.get(PipelineRun, "run-2")
        assert fetched.phase == "scoring"


class TestFinalScoreTimeline:
    def test_create(self, session):
        firm = Firm(full_name="TestFirm", country="PL")
        session.add(firm)
        session.flush()

        run = PipelineRun(id="run-3", query="Test", status="complete", phase="complete")
        session.add(run)
        session.flush()

        row = FinalScoreTimeline(
            firm_id=firm.id,
            run_id="run-3",
            bucket_index=0,
            bucket_start=datetime(2020, 1, 1),
            bucket_end=datetime(2021, 1, 1),
            eem_score=0.5,
            trustweb_score=0.3,
            nsa_score=0.4,
            final_score=0.4,
            risk_level="medium",
        )
        session.add(row)
        session.commit()

        fetched = session.query(FinalScoreTimeline).first()
        assert fetched.firm_id == firm.id
        assert fetched.final_score == 0.4
        assert fetched.risk_level == "medium"
