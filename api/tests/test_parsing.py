import codecs
from datetime import date

import pytest

from app.parsing import MAX_ROW_ERRORS, CSVFormatError, parse_cents, parse_csv, parse_date


@pytest.mark.parametrize(
    "text, expected",
    [
        ("12.34", 1234),
        ("-4.5", -450),
        ("$1,234.00", 123400),
        ("(5.00)", -500),
        (".5", 50),
        ("7", 700),
        ("+3.10", 310),
        ("5.", 500),
    ],
)
def test_parse_cents_valid(text, expected):
    assert parse_cents(text) == expected


@pytest.mark.parametrize("text", ["abc", "1.234", "", "--5", "1.2.3", ".", "$"])
def test_parse_cents_invalid(text):
    with pytest.raises(ValueError):
        parse_cents(text)


def test_parse_date_formats():
    assert parse_date("2026-10-13") == date(2026, 10, 13)
    assert parse_date("10/13/2026") == date(2026, 10, 13)
    assert parse_date("1/2/26") == date(2026, 1, 2)


@pytest.mark.parametrize("text", ["13/45/2026", "yesterday", ""])
def test_parse_date_invalid(text):
    with pytest.raises(ValueError):
        parse_date(text)


def test_csv_header_aliases_bom_and_bad_rows():
    text = (
        "Transaction Date,Details,Amount\n"
        "2026-10-01,SHELL OIL 5521,-40.25\n"
        "not-a-date,BAD ROW,-1.00\n"
        '10/02/2026,PAYROLL ACME,"1,500.00"\n'
    )
    result = parse_csv(codecs.BOM_UTF8 + text.encode())
    assert [r.amount_cents for r in result.rows] == [-4025, 150000]
    assert result.skipped == 1
    assert len(result.errors) == 1
    assert result.errors[0].line == 3  # header is line 1


def test_csv_missing_column():
    with pytest.raises(CSVFormatError, match="description"):
        parse_csv(b"date,amount\n2026-10-01,5.00\n")


def test_csv_blank_lines_are_ignored():
    result = parse_csv(b"date,description,amount\n\n2026-10-01,COFFEE,-3.00\n\n")
    assert len(result.rows) == 1
    assert result.skipped == 0


def test_csv_error_list_is_capped_but_all_skips_counted():
    bad_rows = "".join(f"nope,ROW {i},1.00\n" for i in range(MAX_ROW_ERRORS + 5))
    result = parse_csv(("date,description,amount\n" + bad_rows).encode())
    assert result.skipped == MAX_ROW_ERRORS + 5
    assert len(result.errors) == MAX_ROW_ERRORS


def test_csv_empty_file():
    with pytest.raises(CSVFormatError):
        parse_csv(b"")


def test_csv_invalid_encoding():
    with pytest.raises(CSVFormatError):
        parse_csv(bytes([0xFF, 0xFE, 0xFD]))


def test_parse_date_month_day_with_explicit_year():
    assert parse_date("09/29", year=2025) == date(2025, 9, 29)
    assert parse_date("9-5", year=2025) == date(2025, 9, 5)


def test_parse_date_month_day_infers_most_recent_past_date():
    today = date(2026, 1, 10)
    assert parse_date("01/05", today=today) == date(2026, 1, 5)
    assert parse_date("12/28", today=today) == date(2025, 12, 28)  # not next December
    assert parse_date("01/10", today=today) == date(2026, 1, 10)  # today itself is allowed


def test_parse_date_month_day_leap_day_and_invalid():
    assert parse_date("02/29", today=date(2026, 3, 1)) == date(2024, 2, 29)
    with pytest.raises(ValueError):
        parse_date("02/30", year=2025)
    with pytest.raises(ValueError):
        parse_date("13/01", year=2025)
    with pytest.raises(ValueError):
        parse_date("02/29", year=2025)


def test_parse_csv_month_day_dates_use_year():
    result = parse_csv(b"date,description,amount\n09/29,SQ *. TUSTIN CA,-5.00\n", year=2025)
    assert result.skipped == 0
    assert result.rows[0].posted_on == date(2025, 9, 29)
