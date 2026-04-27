import re
from dataclasses import dataclass

from ..keywords.risk_keywords import RISK_KEYWORDS, KeywordDef

_CONTEXT_WINDOW = 60


@dataclass
class _CompiledKeyword:
    phrase: str
    pattern: re.Pattern
    category: str
    weight: float
    lang: str


@dataclass
class EngineMatch:
    keyword: str
    category: str
    weight: float
    in_title: bool
    context: str
    occurrences: int


class RegexEngine:
    def __init__(self, keywords: list[KeywordDef] | None = None) -> None:
        source = keywords if keywords is not None else RISK_KEYWORDS
        self._compiled: list[_CompiledKeyword] = [
            _CompiledKeyword(
                phrase=kw["phrase"],
                pattern=re.compile(kw["pattern"], re.IGNORECASE | re.UNICODE),
                category=kw["category"],
                weight=kw["weight"],
                lang=kw["lang"],
            )
            for kw in source
        ]

    def scan(self, text: str, title: str = "") -> list[EngineMatch]:
        matches: list[EngineMatch] = []

        for ck in self._compiled:
            title_hits = list(ck.pattern.finditer(title)) if title else []
            text_hits = list(ck.pattern.finditer(text))
            all_hits = title_hits + text_hits

            if not all_hits:
                continue

            in_title = len(title_hits) > 0
            first_hit = all_hits[0]
            source = title if in_title else text
            start = max(0, first_hit.start() - _CONTEXT_WINDOW)
            end = min(len(source), first_hit.end() + _CONTEXT_WINDOW)
            context = source[start:end].strip()

            matches.append(
                EngineMatch(
                    keyword=ck.phrase,
                    category=ck.category,
                    weight=ck.weight,
                    in_title=in_title,
                    context=context,
                    occurrences=len(all_hits),
                )
            )

        return matches
