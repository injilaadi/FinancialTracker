"""Keyword rules baseline for transaction categorization.

This is the baseline the ML model must beat. Measure it on your hand-labeled
test set first, so the model's F1 has something honest to be compared against.

Matching: the description is upper-cased and punctuation like '*' is turned into
spaces; a keyword matches on word boundaries; the LONGEST matching keyword wins,
so 'UBER EATS' (Dining) beats 'UBER' (Transport) regardless of dict order.
"""
import re

RULES: dict[str, list[str]] = {
    "Groceries": ["WHOLE FOODS", "TRADER JOE", "SAFEWAY", "KROGER", "ALDI", "COSTCO", "RALPHS", "VONS"],
    "Dining": ["STARBUCKS", "BLUE BOTTLE", "MCDONALD", "CHIPOTLE", "DOORDASH", "UBER EATS",
               "GRUBHUB", "PIZZA", "CAFE", "RESTAURANT"],
    "Transport": ["UBER", "LYFT", "BART", "CLIPPER", "PARKING", "TRANSIT"],
    "Gas": ["SHELL", "CHEVRON", "ARCO", "EXXON"],
    "Subscriptions": ["NETFLIX", "SPOTIFY", "HULU", "ADOBE", "ICLOUD", "YOUTUBE PREMIUM", "OPENAI"],
    "Shopping": ["AMAZON", "TARGET", "WALMART", "BEST BUY", "IKEA"],
    "Rent": ["RENT", "APARTMENT", "PROPERTY MGMT"],
    "Utilities": ["PG&E", "COMCAST", "XFINITY", "VERIZON", "AT&T", "WATER BILL", "ELECTRIC"],
    "Health": ["CVS", "WALGREENS", "PHARMACY", "DENTAL", "CLINIC"],
    "Entertainment": ["AMC", "CINEMA", "TICKETMASTER", "STEAM"],
    "Travel": ["AIRLINES", "DELTA", "UNITED", "AIRBNB", "HOTEL"],
    "Income": ["PAYROLL", "DIRECT DEP", "SALARY"],
}

FALLBACK = "Other"


def normalize(description: str) -> str:
    text = description.upper().replace("*", " ")
    return re.sub(r"\s+", " ", text).strip()


# Pre-compile (category, keyword, regex) once, longest keywords first.
_COMPILED = sorted(
    (
        (category, kw, re.compile(r"(?<![A-Z0-9])" + re.escape(kw) + r"(?![A-Z0-9])"))
        for category, kws in RULES.items()
        for kw in kws
    ),
    key=lambda item: len(item[1]),
    reverse=True,
)


def categorize(description: str) -> tuple[str, str | None]:
    """Return (category, matched_keyword). Unmatched descriptions -> ('Other', None)."""
    text = normalize(description)
    for category, kw, pattern in _COMPILED:
        if pattern.search(text):
            return category, kw
    return FALLBACK, None
