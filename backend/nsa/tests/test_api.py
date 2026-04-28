from nsa.api import StubNSAService, create_app
from nsa.database.session import get_db
from fastapi.testclient import TestClient
from tarkov.database.models import Firm, Person


def test_score_company_endpoint_returns_stub_response() -> None:
    app = create_app(service=StubNSAService())

    with TestClient(app) as client:
        response = client.post(
            "/score/company",
            json={"firm_id": 42, "correlation_id": "cid-1"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "firm_id": 42,
        "company_risk_score": 0.62,
        "people_scored": 3,
        "evidence_count": 11,
    }


def test_score_company_endpoint_uses_real_service_when_database_url_is_supplied() -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    app = create_app(service=None, database_url=database_url)

    with TestClient(app) as client:
        with get_db() as session:
            firm = Firm(full_name="Acme Sp. z o.o.", country="PL")
            session.add(firm)
            session.flush()
            session.add(Person(name="Jane Doe", firm_id=firm.id))
            session.commit()

        response = client.post(
            "/score/company",
            json={"firm_id": firm.id, "correlation_id": "cid-real"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "firm_id": firm.id,
        "company_risk_score": 0.0,
        "people_scored": 1,
        "evidence_count": 0,
    }


def test_score_company_endpoint_returns_404_for_missing_firm() -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    app = create_app(service=None, database_url=database_url)

    with TestClient(app) as client:
        response = client.post(
            "/score/company",
            json={"firm_id": 999, "correlation_id": "cid-missing"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Firm 999 not found"}


def test_score_company_endpoint_handles_known_firm_with_zero_people() -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    app = create_app(service=None, database_url=database_url)

    with TestClient(app) as client:
        with get_db() as session:
            firm = Firm(full_name="Solo Sp. z o.o.", country="PL")
            session.add(firm)
            session.commit()

        response = client.post(
            "/score/company",
            json={"firm_id": firm.id, "correlation_id": "cid-zero"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "firm_id": firm.id,
        "company_risk_score": 0.0,
        "people_scored": 0,
        "evidence_count": 0,
    }
