"""Score the rules categorizer against a hand-labeled CSV.

Usage: python eval.py ../data/private/labeled.csv
"""
import csv
import sys

from metrics import print_report
from rules import categorize


def evaluate(path: str) -> None:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    truth = [r["true_category"] for r in rows]
    descriptions = [r["description"] for r in rows]
    pred = [categorize(d)[0] for d in descriptions]
    print_report(truth, pred, descriptions)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python eval.py LABELED.csv")
    evaluate(sys.argv[1])
