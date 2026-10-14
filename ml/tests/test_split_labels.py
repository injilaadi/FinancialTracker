import csv

import split_labels


def _rows(items):
    return [{"date": "2026-01-01", "description": d, "amount": "-1.00", "true_category": c} for d, c in items]


def test_dedupe_collapses_digit_variants_and_flags_conflicts():
    rows = _rows([("STORE #101 IRVINE CA", "Dining"), ("STORE #202 IRVINE CA", "Dining"),
                  ("OTHER 5", "Gas"), ("OTHER 6", "Shopping")])
    kept, conflicts = split_labels.dedupe(rows)
    assert [r["description"] for r in kept] == ["STORE #101 IRVINE CA", "OTHER 5"]
    assert conflicts == [("OTHER 6", "Gas", "Shopping")]


def test_stratified_split_is_disjoint_deterministic_and_single_rows_stay_in_dev():
    rows = _rows([(f"A{i}", "Dining") for i in range(6)] + [("G", "Gas")] + [(f"S{i}", "Shopping") for i in range(3)])
    dev, test = split_labels.stratified_split(rows, seed=3)
    assert (dev, test) == split_labels.stratified_split(rows, seed=3)
    assert len(test) == 3 + 0 + 1  # Dining 3, Gas 0, Shopping 1
    assert {r["description"] for r in dev}.isdisjoint(r["description"] for r in test)
    assert any(r["description"] == "G" for r in dev)


def test_cli_writes_files(tmp_path):
    src = tmp_path / "l.csv"
    with open(src, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "description", "amount", "true_category"])
        writer.writeheader()
        writer.writerows(_rows([(name, "Dining") for name in ["ALPHA", "BRAVO", "CHARLIE", "DELTA"]]))
    assert split_labels.main([str(src), "--out-dir", str(tmp_path)]) == 0
    assert len(list(csv.DictReader(open(tmp_path / "test.csv")))) == 2
