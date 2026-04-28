"""Tests for the score merger."""

from datetime import datetime, timedelta

import pytest

from pipeline.score_merger import ScoreMerger, _classify, _pad
from timeline.buckets import TimelineBucket


def _make_buckets(n: int = 8) -> list[TimelineBucket]:
    start = datetime(2020, 1, 1)
    end = datetime(2026, 1, 1)
    total = (end - start).total_seconds()
    inc = total / n
    return [
        TimelineBucket(
            index=i,
            start=start + timedelta(seconds=inc * i),
            end=start + timedelta(seconds=inc * (i + 1)),
            label=f"T{i}",
        )
        for i in range(n)
    ]


class TestClassify:
    def test_high(self):
        assert _classify(0.8) == "high"
        assert _classify(0.6) == "high"

    def test_medium(self):
        assert _classify(0.5) == "medium"
        assert _classify(0.3) == "medium"

    def test_low(self):
        assert _classify(0.1) == "low"
        assert _classify(0.0) == "low"


class TestPad:
    def test_pad_shorter(self):
        assert _pad([1.0, 2.0], 4) == [1.0, 2.0, None, None]

    def test_truncate_longer(self):
        assert _pad([1.0, 2.0, 3.0], 2) == [1.0, 2.0]

    def test_exact_length(self):
        assert _pad([1.0, 2.0], 2) == [1.0, 2.0]


class TestScoreMerger:
    def test_merge_all_modules(self):
        merger = ScoreMerger()
        buckets = _make_buckets()
        eem = [50.0] * 8       # 50/100 → normalised to 0.5 risk
        tw = [0.4] * 8
        nsa = 0.3

        merged = merger.merge(buckets, eem, tw, nsa)
        assert len(merged) == 8
        for b in merged:
            assert 0.0 <= b.final_score <= 1.0
            assert b.risk_level in ("high", "medium", "low")
            assert b.eem_score is not None
            assert b.trustweb_score is not None
            assert b.nsa_score is not None

    def test_merge_no_nsa(self):
        merger = ScoreMerger()
        buckets = _make_buckets()
        eem = [80.0] * 8
        tw = [0.2] * 8

        merged = merger.merge(buckets, eem, tw, None)
        assert len(merged) == 8
        for b in merged:
            assert b.nsa_score is None
            assert 0.0 <= b.final_score <= 1.0

    def test_merge_eem_only(self):
        merger = ScoreMerger()
        buckets = _make_buckets()
        eem = [20.0] * 8  # high risk: (1 - 20/100) = 0.8

        merged = merger.merge(buckets, eem, [None] * 8, None)
        assert len(merged) == 8
        for b in merged:
            assert b.eem_score == 0.8
            assert b.final_score == 0.8

    def test_merge_empty(self):
        merger = ScoreMerger()
        buckets = _make_buckets()
        merged = merger.merge(buckets, [None] * 8, [None] * 8, None)
        for b in merged:
            assert b.final_score == 0.5  # neutral

    def test_eem_normalisation(self):
        """EEM 100 = safe → normalised risk 0.0; EEM 0 = risky → 1.0."""
        merger = ScoreMerger()
        result = merger._normalise_eem([100.0, 0.0, 50.0, None])
        assert result == [0.0, 1.0, 0.5, None]

    def test_to_db_rows(self):
        merger = ScoreMerger()
        buckets = _make_buckets()
        merged = merger.merge(buckets, [50.0] * 8, [0.5] * 8, 0.5)
        rows = merger.to_db_rows(1, "run-abc", merged)
        assert len(rows) == 8
        assert all(r.firm_id == 1 for r in rows)
        assert all(r.run_id == "run-abc" for r in rows)

    def test_custom_weights(self):
        merger = ScoreMerger(weights={"eem": 1.0, "trustweb": 0.0, "nsa": 0.0})
        buckets = _make_buckets()
        eem = [0.0] * 8  # normalised risk = 1.0
        tw = [0.0] * 8
        merged = merger.merge(buckets, eem, tw, 0.0)
        for b in merged:
            assert b.final_score == pytest.approx(1.0, abs=0.01)
