"""Weighted score merging across EEM, TrustWeb, and NSA.

Each module produces scores on different scales:
- EEM:      0–100  (integer)
- TrustWeb: 0.0–1.0
- NSA:      0.0–1.0

The merger normalises everything to 0.0–1.0, applies configurable weights,
and produces a per-bucket final score with a risk classification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from pipeline.models import FinalScoreTimeline
from timeline.buckets import TimelineBucket

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {"eem": 0.40, "trustweb": 0.35, "nsa": 0.25}


@dataclass(frozen=True, slots=True)
class BucketScore:
    bucket_index: int
    bucket_start: datetime
    bucket_end: datetime
    eem_score: float | None       # normalised 0–1
    trustweb_score: float | None  # 0–1
    nsa_score: float | None       # 0–1
    final_score: float            # 0–1
    risk_level: str               # high / medium / low


@dataclass
class ScoreMerger:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def merge(
        self,
        buckets: list[TimelineBucket],
        eem_scores: list[float | None],
        trustweb_scores: list[float | None],
        nsa_score: float | None,
    ) -> list[BucketScore]:
        """Merge per-bucket scores from the three modules.

        *eem_scores* are on 0–100 scale and are normalised internally.
        *trustweb_scores* are per-bucket on 0–1.
        *nsa_score* is a single company-level score applied uniformly.
        """
        n = len(buckets)
        eem_normed = _pad(self._normalise_eem(eem_scores), n)
        tw = _pad(trustweb_scores, n)
        nsa = [nsa_score] * n

        results: list[BucketScore] = []
        for i, bucket in enumerate(buckets):
            final = self._weighted_merge(eem_normed[i], tw[i], nsa[i])
            risk = _classify(final)
            results.append(BucketScore(
                bucket_index=bucket.index,
                bucket_start=bucket.start,
                bucket_end=bucket.end,
                eem_score=eem_normed[i],
                trustweb_score=tw[i],
                nsa_score=nsa[i],
                final_score=round(final, 4),
                risk_level=risk,
            ))
        return results

    def to_db_rows(
        self,
        firm_id: int,
        run_id: str,
        merged: list[BucketScore],
    ) -> list[FinalScoreTimeline]:
        now = datetime.utcnow()
        return [
            FinalScoreTimeline(
                firm_id=firm_id,
                run_id=run_id,
                bucket_index=b.bucket_index,
                bucket_start=b.bucket_start,
                bucket_end=b.bucket_end,
                eem_score=b.eem_score,
                trustweb_score=b.trustweb_score,
                nsa_score=b.nsa_score,
                final_score=b.final_score,
                risk_level=b.risk_level,
                computed_at=now,
            )
            for b in merged
        ]

    # ── internals ────────────────────────────────────────────────────────

    @staticmethod
    def _normalise_eem(scores: list[float | None]) -> list[float | None]:
        """EEM 0–100 → 0.0–1.0 (inverted: lower EEM = higher risk → higher merged)."""
        # EEM score semantics: 100 = safe, 0 = risky
        # We invert so 1.0 = high risk (consistent with TrustWeb & NSA)
        result: list[float | None] = []
        for s in scores:
            if s is None:
                result.append(None)
            else:
                result.append(round(1.0 - max(0.0, min(100.0, s)) / 100.0, 4))
        return result

    def _weighted_merge(
        self,
        eem: float | None,
        tw: float | None,
        nsa: float | None,
    ) -> float:
        """Compute weighted average, re-normalising weights for missing modules."""
        components: list[tuple[str, float]] = []
        if eem is not None:
            components.append(("eem", eem))
        if tw is not None:
            components.append(("trustweb", tw))
        if nsa is not None:
            components.append(("nsa", nsa))

        if not components:
            return 0.5  # neutral when no data

        total_weight = sum(self.weights[name] for name, _ in components)
        if total_weight == 0:
            return 0.5

        return sum(self.weights[name] * val / total_weight for name, val in components)


def _classify(score: float) -> str:
    if score >= 0.6:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"


def _pad(values: list[float | None], n: int) -> list[float | None]:
    """Pad or truncate a list to length *n*."""
    if len(values) >= n:
        return values[:n]
    return values + [None] * (n - len(values))
