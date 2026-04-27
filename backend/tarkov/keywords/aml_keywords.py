"""Keyword dictionaries for deterministic extraction."""

AML_KEYWORDS: dict[str, list[str]] = {
    "money_laundering": [
        "money laundering",
        "suspicious transaction",
        "structuring",
        "smurfing",
        "illicit funds",
    ],
    "fraud": [
        "fraud",
        "embezzlement",
        "ponzi",
        "pyramid scheme",
        "misrepresentation",
    ],
    "regulatory_action": [
        "regulatory action",
        "investigation",
        "sanction",
        "fine",
        "cease and desist",
    ],
    "bankruptcy": [
        "bankruptcy",
        "insolvency",
        "liquidation",
        "restructuring",
    ],
    "sanctions": [
        "sanctions",
        "watchlist",
        "blacklist",
        "frozen assets",
    ],
}


ROLE_KEYWORDS: dict[str, list[str]] = {
    "ceo": ["chief executive officer", "ceo"],
    "cfo": ["chief financial officer", "cfo"],
    "director": ["director", "board member"],
    "owner": ["owner", "beneficial owner", "shareholder"],
    "founder": ["founder", "co-founder"],
    "compliance_officer": ["compliance officer", "aml officer"],
}
