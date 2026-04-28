from __future__ import annotations

from datetime import datetime

from eem.database.models import FirmScore, FirmScoreTimeline
from pipeline.models import FinalScoreTimeline
from tarkov.database.models import Firm
from tarkov.frontend_graph_api import FrontendGraphService

from .test_frontend_graph_api import build_config, build_session


def _service_with_company(monkeypatch: object) -> tuple[FrontendGraphService, object]:
    session = build_session()
    service = FrontendGraphService(build_config())
    monkeypatch.setattr(
        service,
        "_query_company_nodes",
        lambda: [{"company_id": "1", "name": "Acme Holdings S.A."}],
    )
    return service, session


def test_company_history_prefers_final_score_timeline(monkeypatch):
    service, session = _service_with_company(monkeypatch)
    session.add(Firm(id=1, full_name="Acme Holdings S.A.", country="PL"))
    session.add(
        FirmScore(
            firm_id=1,
            score=82,
            risk="low",
            trend=4,
            score_history="[70, 71, 72]",
            keywords="[]",
            computed_at=datetime(2026, 4, 27, 12, 0, 0),
        )
    )
    session.add_all(
        [
            FinalScoreTimeline(
                firm_id=1,
                run_id="run-1",
                bucket_index=2,
                bucket_start=datetime(2026, 3, 1),
                bucket_end=datetime(2026, 3, 31),
                eem_score=60,
                trustweb_score=65,
                nsa_score=70,
                final_score=66,
                risk_level="medium",
            ),
            FinalScoreTimeline(
                firm_id=1,
                run_id="run-1",
                bucket_index=0,
                bucket_start=datetime(2026, 1, 1),
                bucket_end=datetime(2026, 1, 31),
                eem_score=55,
                trustweb_score=60,
                nsa_score=65,
                final_score=61,
                risk_level="medium",
            ),
            FinalScoreTimeline(
                firm_id=1,
                run_id="run-1",
                bucket_index=1,
                bucket_start=datetime(2026, 2, 1),
                bucket_end=datetime(2026, 2, 28),
                eem_score=58,
                trustweb_score=63,
                nsa_score=68,
                final_score=64,
                risk_level="medium",
            ),
        ]
    )
    session.commit()

    company = service.list_companies(session)[0]

    assert company["history"] == [61, 64, 66]
    assert company["historyByRange"]["3M"] == [61, 64, 66]


def test_company_history_falls_back_to_firm_score_timeline(monkeypatch):
    service, session = _service_with_company(monkeypatch)
    session.add(Firm(id=1, full_name="Acme Holdings S.A.", country="PL"))
    session.add(
        FirmScore(
            firm_id=1,
            score=82,
            risk="low",
            trend=4,
            score_history="[70, 71, 72]",
            keywords="[]",
            computed_at=datetime(2026, 4, 27, 12, 0, 0),
        )
    )
    session.add_all(
        [
            FirmScoreTimeline(
                firm_id=1,
                run_id="run-1",
                bucket_index=1,
                bucket_start=datetime(2026, 2, 1),
                bucket_end=datetime(2026, 2, 28),
                score=62,
                risk="medium",
                event_count=3,
                keywords="[]",
                computed_at=datetime(2026, 4, 27, 12, 0, 0),
            ),
            FirmScoreTimeline(
                firm_id=1,
                run_id="run-1",
                bucket_index=0,
                bucket_start=datetime(2026, 1, 1),
                bucket_end=datetime(2026, 1, 31),
                score=59,
                risk="medium",
                event_count=2,
                keywords="[]",
                computed_at=datetime(2026, 4, 27, 12, 0, 0),
            ),
        ]
    )
    session.commit()

    company = service.list_companies(session)[0]

    assert company["history"] == [59, 62]


def test_company_history_falls_back_to_score_history(monkeypatch):
    service, session = _service_with_company(monkeypatch)
    session.add(Firm(id=1, full_name="Acme Holdings S.A.", country="PL"))
    session.add(
        FirmScore(
            firm_id=1,
            score=82,
            risk="low",
            trend=4,
            score_history="[70, 76, 82]",
            keywords="[]",
            computed_at=datetime(2026, 4, 27, 12, 0, 0),
        )
    )
    session.commit()

    company = service.list_companies(session)[0]

    assert company["history"] == [70, 76, 82]
    assert company["historyByRange"]["6M"] == [70, 76, 82]


def test_company_history_falls_back_to_safe_generated_series(monkeypatch):
    service, session = _service_with_company(monkeypatch)
    session.add(Firm(id=1, full_name="Acme Holdings S.A.", country="PL"))
    session.commit()

    company = service.list_companies(session)[0]

    assert company["score"] == 50
    assert company["history"] == [50] * 12
    assert company["historyByRange"]["30D"] == [50] * 30


def test_company_payload_includes_tradingview_symbol_when_exchange_and_ticker_exist(
    monkeypatch,
):
    service, session = _service_with_company(monkeypatch)
    session.add(
        Firm(
            id=1,
            full_name="Acme Holdings S.A.",
            country="PL",
            market_ticker="ACME",
            market_exchange="NASDAQ",
        )
    )
    session.commit()

    company = service.list_companies(session)[0]

    assert company["tradingViewSymbol"] == "NASDAQ:ACME"
    assert company["hasTradingView"] is True


def test_company_payload_blocks_tradingview_when_market_fields_missing(monkeypatch):
    service, session = _service_with_company(monkeypatch)
    session.add(Firm(id=1, full_name="Acme Holdings S.A.", country="PL"))
    session.commit()

    company = service.list_companies(session)[0]

    assert company["tradingViewSymbol"] == ""
    assert company["hasTradingView"] is False
