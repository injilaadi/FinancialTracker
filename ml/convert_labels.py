"""Convert hand-labeled lines like `09/22 HEYTEA-US-LA Irvine CA 13.48 Dining`
into a proper CSV (date,description,amount,true_category).

Usage: python convert_labels.py IN.txt OUT.csv --year 2026

Amounts are written negative (spending), matching the API's convention.
Lines that don't parse are reported, never silently dropped.
"""
import argparse
import csv
import re
import sys

CATEGORIES = {
    "Groceries", "Dining", "Transport", "Gas", "Subscriptions", "Shopping", "Rent",
    "Utilities", "Health", "Entertainment", "Travel", "Income", "Other",
}
LINE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})\s+(.+?)\s+(-?[\d,]*\.\d{2})\s+([A-Za-z]+)$")


def convert_line(line: str, year: int) -> list[str]:
    match = LINE_RE.match(line.strip())
    if not match:
        raise ValueError("expected: MM/DD description amount Category")
    month, day, description, amount, category = match.groups()
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}")
    cents = abs(float(amount.replace(",", "")))
    return [f"{year}-{int(month):02d}-{int(day):02d}", description, f"-{cents:.2f}", category]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    rows, bad = [], 0
    with open(args.src, encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(convert_line(line, args.year))
            except ValueError as exc:
                bad += 1
                print(f"line {number}: {exc}", file=sys.stderr)
    with open(args.dst, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "description", "amount", "true_category"])
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.dst} ({bad} skipped)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
