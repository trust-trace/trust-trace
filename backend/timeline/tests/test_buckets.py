"""Tests for timeline bucket computation."""

from datetime import datetime, timedelta

import pytest

from timeline.buckets import TimelineBucket, compute_timeline_buckets


class TestComputeTimelineBuckets:
    def test_returns_8_buckets_by_default(self):
        created = datetime(2018, 3, 15)
        as_of = datetime(2026, 4, 28)
        buckets = compute_timeline_buckets(created, as_of)
        assert len(buckets) == 8

    def test_bucket_indices_are_sequential(self):
        buckets = compute_timeline_buckets(datetime(2020, 1, 1), datetime(2026, 1, 1))
        for i, b in enumerate(buckets):
            assert b.index == i

    def test_first_bucket_starts_near_created_at(self):
        created = datetime(2018, 3, 15)
        as_of = datetime(2026, 4, 28)
        buckets = compute_timeline_buckets(created, as_of)
        diff = abs((buckets[0].start - created).total_seconds())
        assert diff < 86400  # within 1 day (rounding)

    def test_last_bucket_ends_at_as_of(self):
        created = datetime(2020, 1, 1)
        as_of = datetime(2026, 4, 28)
        buckets = compute_timeline_buckets(created, as_of)
        assert buckets[-1].end == as_of

    def test_buckets_cover_full_period(self):
        created = datetime(2018, 1, 1)
        as_of = datetime(2026, 1, 1)
        buckets = compute_timeline_buckets(created, as_of)
        # Each bucket's start should be <= prev bucket's end
        for i in range(1, len(buckets)):
            assert buckets[i].start <= buckets[i - 1].end + timedelta(days=1)

    def test_custom_n_buckets(self):
        buckets = compute_timeline_buckets(
            datetime(2020, 1, 1), datetime(2026, 1, 1), n_buckets=4
        )
        assert len(buckets) == 4

    def test_very_short_lifetime(self):
        """A firm created 2 days ago should still produce 8 buckets."""
        as_of = datetime(2026, 4, 28)
        created = as_of - timedelta(days=2)
        buckets = compute_timeline_buckets(created, as_of)
        assert len(buckets) == 8

    def test_future_created_at_clamps(self):
        """If created_at is in the future, we still get valid buckets."""
        buckets = compute_timeline_buckets(
            datetime(2027, 1, 1), datetime(2026, 4, 28)
        )
        assert len(buckets) == 8
        assert buckets[-1].end > buckets[0].start

    def test_label_format(self):
        buckets = compute_timeline_buckets(datetime(2020, 1, 1), datetime(2026, 1, 1))
        for b in buckets:
            assert "→" in b.label

    def test_bucket_is_frozen_dataclass(self):
        buckets = compute_timeline_buckets(datetime(2020, 1, 1), datetime(2026, 1, 1))
        with pytest.raises(AttributeError):
            buckets[0].index = 99
