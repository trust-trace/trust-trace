from __future__ import annotations

from eem._types import _EventRow

SYSTEM_PROMPT = """\
You are an AML (Anti-Money Laundering) event analyst.
Given a corporate event, return a JSON object with exactly these fields:

{
  "sentiment":   <float -1.0..1.0  — overall tone for the company>,
  "impact":      <float -10.0..10.0 — signed trust impact; negative = harmful>,
  "source_tier": <"tier-1" | "tier-2" | "tier-3">,
  "keywords":    [<3 to 6 short Polish keyword strings>],
  "excerpt":     "<2 to 4 sentence Polish summary for display on a risk dashboard>",
  "entities":    [<names of people and organisations involved>]
}

source_tier:
  tier-1 — major national press (Rzeczpospolita, Parkiet, Puls Biznesu, Gazeta Wyborcza)
  tier-2 — online business portals (Bankier.pl, Onet Biznes, TVN24 BiS, Money.pl)
  tier-3 — financial data aggregators, forums, secondary sources

Rules:
- Return ONLY the JSON object. No markdown fences, no explanation.
- excerpt must be in Polish, factual, suitable for a compliance dashboard.
- keywords must be in Polish.\
"""


def build_user_message(event: _EventRow, firm_name: str) -> str:
    def _fmt_date(value):
        if value is None:
            return "unknown date"
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)

    lines = [
        f'Analyze this AML event for company "{firm_name}":',
        "",
        f"Event type: {event.event_type}",
        f"Title: {event.title}",
        f"Original risk level: {event.risk_level}/10",
        f"Event date: {_fmt_date(event.occurred_at)}",
    ]

    if event.source_text_quote:
        lines += ["", f'Source quote: "{event.source_text_quote}"']

    if event.sources:
        lines += ["", "Sources:"]
        for s in event.sources:
            date_str = _fmt_date(s.published_at)
            title = s.title or s.url
            lines.append(f"- [{title}, {date_str}] {s.content_excerpt}")

    if event.people:
        lines += ["", "People involved:"]
        for p in event.people:
            role_str = p.role or "unknown role"
            role_in_event = p.role_in_event or "involved"
            lines.append(f"- {p.name} ({role_str}) — {role_in_event}")

    lines += ["", "Return your JSON analysis now."]
    return "\n".join(lines)
