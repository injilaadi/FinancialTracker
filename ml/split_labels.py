"""Split your hand-labeled CSV into dev.csv (usable for training/tuning) and test.csv (score once).

Usage: python split_labels.py ../data/private/labeled.csv --out-dir ../data/private

- Near-duplicates (same text once digits are blurred) are collapsed to one row, so the same
  merchant can't land on both sides of the split.
- Stratified: each category is split about half and half. A category with a single row goes
  to dev, since a one-row test class says nothing.
- Deterministic for a given --seed.
"""
import argparse
import csv
import os
import random
import sys
from collections import defaultdict

from features import prepare_text


def dedupe(rows):
    seen, kept, conflicts = {}, [], []
    for row in rows:
        key = prepare_text(row["description"])
        if key in seen:
            if seen[key] != row["true_category"]:
                conflicts.append((row["description"], seen[key], row["true_category"]))
            continue
        seen[key] = row["true_category"]
        kept.append(row)
    return kept, conflicts


def stratified_split(rows, seed=0):
    by_category = defaultdict(list)
    for row in rows:
        by_category[row["true_category"]].append(row)
    rng = random.Random(seed)
    dev, test = [], []
    for category in sorted(by_category):
        group = by_category[category][:]
        rng.shuffle(group)
        n_test = len(group) // 2  # 1 row -> 0 in test; 2 -> 1; 3 -> 1; 5 -> 2
        test.extend(group[:n_test])
        dev.extend(group[n_test:])
    return dev, test


def write(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("labeled")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    with open(args.labeled, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames, rows = reader.fieldnames, list(reader)
    kept, conflicts = dedupe(rows)
    for description, first, second in conflicts:
        print(f"WARNING: same text labeled {first!r} and {second!r}: {description}", file=sys.stderr)
    dev, test = stratified_split(kept, args.seed)
    write(os.path.join(args.out_dir, "dev.csv"), dev, fieldnames)
    write(os.path.join(args.out_dir, "test.csv"), test, fieldnames)
    print(f"{len(rows)} rows -> {len(kept)} after removing {len(rows) - len(kept)} duplicates; "
          f"dev={len(dev)} test={len(test)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
