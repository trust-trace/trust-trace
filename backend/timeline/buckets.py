"""Date-bucketing logic shared by EEM and TrustWeb timeline scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True)
class TimelineBucket:
    index: int            # 0–(n_buckets-1)
    start: datetime       # inclusive
    end: datetime         # exclusive (except last bucket: inclusive of today)
    label: str            # human-readable, e.g. "2019-03 → 2020-03"


def compute_timeline_buckets(
    firm_created_at: datetime,
    as_of: datetime | None = None,
    n_buckets: int = 8,
) -> list[TimelineBucket]:
    """Divide the firm's lifetime into *n_buckets* equal buckets.

    Returns exactly ``n_buckets`` :class:`TimelineBucket` objects.
    Bucket boundaries are rounded to the nearest day.
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    # Strip timezone info for consistent arithmetic when input is naive
    start = _strip_tz(firm_created_at)
    end = _strip_tz(as_of)

    if end <= start:
        end = start + timedelta(days=1)

    total_seconds = (end - start).total_seconds()
    increment = total_seconds / n_buckets

    buckets: list[TimelineBucket] = []
    for i in range(n_buckets):
        b_start = start + timedelta(seconds=increment * i)
        if i < n_buckets - 1:
            b_end = start + timedelta(seconds=increment * (i + 1))
        else:
            b_end = end

        # Round to nearest day
        b_start = _round_to_day(b_start)
        b_end = _round_to_day(b_end) if i < n_buckets - 1 else end

        label = f"{b_start.strftime('%Y-%m')} → {b_end.strftime('%Y-%m')}"
        buckets.append(TimelineBucket(index=i, start=b_start, end=b_end, label=label))

    return buckets


def _strip_tz(dt: datetime | str) -> datetime:
    # Handle string inputs by converting to datetime first
    if isinstance(dt, str):
        from datetime import datetime as dt_class
        dt = dt_class.fromisoformat(dt)
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _round_to_day(dt: datetime) -> datetime:
    """Round a datetime to the nearest day boundary."""
    if dt.hour >= 12:
        return (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)
