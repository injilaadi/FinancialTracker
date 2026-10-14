"""Parsing helpers: dates, money, and bank-statement CSVs."""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

MAX_ROW_ERRORS = 20
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")

# Accepted header names (case-insensitive) for each required column.
HEADER_ALIASES = {
    "date": ("date", "posted date", "transaction date", "posted_on"),
    "description": ("description", "details", "memo", "name"),
    "amount": ("amount",),
}
REQUIRED = ("date", "description", "amount")

_AMOUNT_RE = re.compile(r"^([0-9]*)(?:\.([0-9]*))?$")


class CSVFormatError(ValueError):
    """The file as a whole cannot be used (empty, bad encoding, missing columns)."""


def parse_date(text: str) -> date:
    """Accept YYYY-MM-DD and the common US bank formats M/D/YYYY and M/D/YY."""
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date {text!r} (use YYYY-MM-DD or M/D/YYYY)")


def parse_cents(text: str) -> int:
    """Convert a money string to integer cents without floating point.

    Accepts '12.34', '-4.5', '$1,234.00', '(5.00)' (accounting negative), '.5', '+3.10'.
    """
    s = text.strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "")
    if s.startswith("-"):
        negative = True
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]

    match = _AMOUNT_RE.match(s)
    if not s or match is None:
        raise ValueError(f"invalid amount {text!r}")
    whole, frac = match.group(1) or "", match.group(2) or ""
    if not whole and not frac:
        raise ValueError(f"invalid amount {text!r}")
    if len(frac) > 2:
        raise ValueError(f"too many decimal places in {text!r}")

    cents = int(whole or "0") * 100 + int(frac.ljust(2, "0"))
    return -cents if negative else cents


@dataclass
class CsvRow:
    posted_on: date
    amount_cents: int
    description: str


@dataclass
class RowError:
    line: int
    message: str


@dataclass
class ParseResult:
    rows: list[CsvRow] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)  # capped at MAX_ROW_ERRORS
    skipped: int = 0  # total bad rows, including ones not listed in errors

    def add_error(self, line: int, message: str) -> None:
        self.skipped += 1
        if len(self.errors) < MAX_ROW_ERRORS:
            self.errors.append(RowError(line, message))


def map_header(header: list[str]) -> dict[str, int]:
    index: dict[str, int] = {}
    for position, raw in enumerate(header):
        name = raw.strip().lower()
        for column, aliases in HEADER_ALIASES.items():
            if name in aliases and column not in index:
                index[column] = position
    for column in REQUIRED:
        if column not in index:
            accepted = ", ".join(HEADER_ALIASES[column])
            raise CSVFormatError(f"missing required column {column!r} (accepted names: {accepted})")
    return index


def _build_row(record: list[str], columns: dict[str, int]) -> CsvRow:
    values: dict[str, str] = {}
    for column in REQUIRED:
        position = columns[column]
        if position >= len(record):
            raise ValueError(f"row has no {column} value")
        values[column] = record[position].strip()
    if not values["description"]:
        raise ValueError("empty description")
    return CsvRow(
        posted_on=parse_date(values["date"]),
        amount_cents=parse_cents(values["amount"]),
        description=values["description"],
    )


def parse_csv(content: bytes) -> ParseResult:
    """Read a bank-statement CSV. Bad rows are skipped and reported, not fatal."""
    try:
        text = content.decode("utf-8-sig")  # also strips a leading byte-order mark
    except UnicodeDecodeError as exc:
        raise CSVFormatError("file is not valid UTF-8 text") from exc

    reader = csv.reader(io.StringIO(text, newline=""), skipinitialspace=True)
    try:
        header = next(reader)
    except StopIteration:
        raise CSVFormatError("file is empty") from None
    columns = map_header(header)

    result = ParseResult()
    while True:
        try:
            record = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            result.add_error(reader.line_num, str(exc))
            continue
        if not record:  # blank line
            continue
        try:
            result.rows.append(_build_row(record, columns))
        except ValueError as exc:
            result.add_error(reader.line_num, str(exc))
    return result
