"""Train the transaction categorizer (TF-IDF character n-grams + logistic regression).

Example:
  python train.py --seed-data ../data/seed/seed_merchants.csv --eval ../data/private/labeled.csv
  python train.py --data ../data/public/transactions.csv \
      --desc-col "Description" --cat-col "Category" \
      --mapping ../data/public/mapping.json \
      --eval ../data/private/test.csv --out models/model.joblib

--mapping is a JSON object {"public category": "one of our 13 categories"}. Public
categories not in the mapping are DROPPED (and counted), never guessed.

The headline number is --eval: your own hand-labeled statements, which the model never
trains on. The "validation" score on the public data is only a sanity check; it is
usually much higher than the real-world score.
"""
import argparse
import csv
import json
import random
import sys
from collections import Counter

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from convert_labels import CATEGORIES
from features import prepare_text
from metrics import macro_f1, print_report
from rules import categorize


def load_dataset(path, desc_col, cat_col, mapping=None):
    """Read (descriptions, labels, dropped) from a CSV, mapping labels to our categories."""
    if mapping is not None:
        mapping = {k: v for k, v in mapping.items() if not k.startswith("_")}  # allow "_comment"
        bad = {v for v in mapping.values() if v not in CATEGORIES}
        if bad:
            raise ValueError(f"mapping targets are not valid categories: {sorted(bad)}")
    texts, labels, dropped = [], [], Counter()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for column in (desc_col, cat_col):
            if column not in (reader.fieldnames or []):
                raise ValueError(f"column {column!r} not in {reader.fieldnames}")
        for row in reader:
            description, raw = (row[desc_col] or "").strip(), (row[cat_col] or "").strip()
            label = mapping.get(raw) if mapping is not None else (raw if raw in CATEGORIES else None)
            if not description or label is None:
                dropped[raw or "<blank>"] += 1
                continue
            texts.append(description)
            labels.append(label)
    return texts, labels, dropped


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=prepare_text, analyzer="char_wb",
                                  ngram_range=(2, 5), sublinear_tf=True)),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=1000)),
    ])


def split(texts, labels, val_frac, seed=0):
    """Shuffled hold-out split; deterministic for a given seed."""
    order = list(range(len(texts)))
    random.Random(seed).shuffle(order)
    cut = int(len(order) * (1 - val_frac))
    train, val = order[:cut], order[cut:]
    return ([texts[i] for i in train], [labels[i] for i in train],
            [texts[i] for i in val], [labels[i] for i in val])


def load_labeled(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [r["description"] for r in rows], [r["true_category"] for r in rows]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", help="public training CSV (needs --desc-col and --cat-col)")
    parser.add_argument("--desc-col")
    parser.add_argument("--cat-col")
    parser.add_argument("--seed-data", help="seed CSV with columns description,category (see make_seed.py)")
    parser.add_argument("--mapping", help="JSON file mapping public categories to ours")
    parser.add_argument("--extra-train", help="your labeled DEV csv (never the test csv) to add to training")
    parser.add_argument("--eval", help="your hand-labeled CSV (date,description,amount,true_category)")
    parser.add_argument("--val-frac", type=float, default=0.2)
    parser.add_argument("--out", default="models/model.joblib")
    args = parser.parse_args(argv)

    if not args.data and not args.seed_data:
        parser.error("give --data and/or --seed-data")
    if args.data and not (args.desc_col and args.cat_col):
        parser.error("--data needs --desc-col and --cat-col")

    texts, labels, dropped = [], [], Counter()
    if args.data:
        mapping = json.load(open(args.mapping, encoding="utf-8")) if args.mapping else None
        texts, labels, dropped = load_dataset(args.data, args.desc_col, args.cat_col, mapping)
    if args.seed_data:
        seed_texts, seed_labels, seed_dropped = load_dataset(args.seed_data, "description", "category")
        texts, labels, dropped = texts + seed_texts, labels + seed_labels, dropped + seed_dropped
    if args.extra_train:
        extra_x, extra_y = load_labeled(args.extra_train)
        texts, labels = texts + extra_x, labels + extra_y
        print(f"added {len(extra_x)} of your labeled dev rows to training")
    if len(set(labels)) < 2:
        sys.exit("need at least 2 categories after mapping")
    print(f"loaded {len(texts)} rows, dropped {sum(dropped.values())} unmapped")
    if dropped:
        print("  dropped categories:", dict(dropped.most_common(10)))
    print("  rows per category:", dict(Counter(labels)))

    # Sanity check only: same distribution as the training data, so optimistic.
    tr_x, tr_y, va_x, va_y = split(texts, labels, args.val_frac)
    check = build_pipeline().fit(tr_x, tr_y)
    print(f"\npublic-data validation macro-F1 (sanity check only): "
          f"{macro_f1(va_y, list(check.predict(va_x))):.3f}")

    model = build_pipeline().fit(texts, labels)  # final model uses all public rows
    joblib.dump({"pipeline": model, "labels": sorted(set(labels)), "sklearn": sklearn.__version__}, args.out)
    print(f"saved {args.out}")

    if args.eval:
        ev_x, ev_y = load_labeled(args.eval)
        print("\n=== MODEL on your labeled statements ===")
        print_report(ev_y, list(model.predict(ev_x)), ev_x)
        rules_pred = [categorize(d)[0] for d in ev_x]
        print(f"\nrules baseline macro-F1 on the same rows: {macro_f1(ev_y, rules_pred):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
