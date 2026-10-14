import pytest

from rules import categorize


@pytest.mark.parametrize(
    "description, expected",
    [
        ("SQ *BLUE BOTTLE 0423 SF", "Dining"),
        ("STARBUCKS STORE 12345", "Dining"),
        ("WHOLE FOODS MKT #123", "Groceries"),
        ("SHELL OIL 5521", "Gas"),
        ("NETFLIX.COM", "Subscriptions"),
        ("PAYROLL ACME INC", "Income"),
    ],
)
def test_known_merchants(description, expected):
    assert categorize(description)[0] == expected


def test_longest_keyword_wins():
    # 'UBER EATS' (Dining) must beat plain 'UBER' (Transport)
    assert categorize("UBER EATS ORDER 8841")[0] == "Dining"
    assert categorize("UBER TRIP HELP.UBER.COM")[0] == "Transport"


def test_case_and_whitespace_insensitive():
    assert categorize("  trader   joe's #44 ")[0] == "Groceries"


def test_word_boundaries_prevent_partial_matches():
    # 'CAFE' must not match inside 'CAFETERIA-NOTES' style tokens, 'ARCO' not inside 'MARCO'
    assert categorize("MARCO POLO IMPORTS")[0] == "Other"


def test_unknown_falls_back_to_other():
    assert categorize("ZZZ UNKNOWN MERCHANT 9") == ("Other", None)
