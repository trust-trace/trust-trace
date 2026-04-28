from eem._pipeline import EEMTimelineEntry, _run
from eem._types import FirmNotFoundError


def enrich_firm(*args, **kwargs):
    from eem._pipeline import _run

    return _run(*args, **kwargs)


__all__ = ["enrich_firm", "EEMTimelineEntry", "FirmNotFoundError"]
