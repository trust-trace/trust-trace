from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..keywords.risk_keywords import RISK_KEYWORDS
from .models import RiskKeyword


def seed_risk_keywords(session: Session) -> int:
    """Insert all hardcoded keywords into risk_keywords table.

    Uses ON CONFLICT DO NOTHING so re-runs are safe.
    Returns the number of newly inserted rows.
    """
    inserted = 0
    for kw in RISK_KEYWORDS:
        stmt = (
            insert(RiskKeyword)
            .values(
                keyword=kw["phrase"],
                category=kw["category"],
                base_weight=kw["weight"],
            )
            .on_conflict_do_nothing(index_elements=["keyword"])
        )
        result = session.execute(stmt)
        inserted += result.rowcount
    session.commit()
    return inserted


def get_keyword_id_map(session: Session) -> dict[str, int]:
    """Return {phrase: db_id} for all risk_keywords rows.

    Tarkov uses this map to write sentiment_keywords FK references
    without a second lookup per article.
    """
    rows = session.query(RiskKeyword.keyword, RiskKeyword.id).all()
    return {row.keyword: row.id for row in rows}
