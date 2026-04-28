from eem._pipeline import _run
from eem._types import FirmNotFoundError

enrich_firm = _run

__all__ = ["enrich_firm", "FirmNotFoundError"]
