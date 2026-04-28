from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol

from nsa.schemas.domain import PersonEvidence


class PersonLike(Protocol):
    id: int


class CompanyContextLike(Protocol):
    ...


@dataclass(frozen=True)
class FetchOutcome:
    person_id: int
    evidence: tuple[PersonEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if isinstance(self.evidence, tuple):
            items = self.evidence
        else:
            items = tuple(self.evidence)

        for item in items:
            if not isinstance(item, PersonEvidence):
                raise TypeError("evidence items must be PersonEvidence instances")

        object.__setattr__(self, "evidence", items)


class BasePersonFetcher(ABC):
    source_kind = "base"

    @abstractmethod
    def fetch(self, person: PersonLike, company_context: CompanyContextLike) -> FetchOutcome:
        raise NotImplementedError
