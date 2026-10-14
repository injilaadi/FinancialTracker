"""Tests for the training pipeline. Data here is tiny and invented: it checks the plumbing
(mapping, dropping, saving, reloading), NOT model quality."""
import csv
import json

import joblib
import pytest

import train
from metrics import macro_f1

ROWS = [
    ("SHELL OIL 1234", "fuel"), ("CHEVRON 0042", "fuel"), ("ARCO AMPM 77", "fuel"),
    ("EXXON MOBIL 555", "fuel"), ("SHELL SERVICE STATION", "fuel"), ("CHEVRON GAS 9", "fuel"),
    ("RALPHS #02", "food"), ("SAFEWAY STORE 12", "food"), ("TRADER JOES 3", "food"),
    ("WHOLE FOODS 8", "food"), ("RALPHS FRESH 9", "food"), ("SAFEWAY 44", "food"),
    ("MYSTERY CORP", "misc"), ("", "fuel"),
]
MAPPING = {"fuel": "Gas", "food": "Groceries"}


@pytest.fixture
def public_csv(tmp_path):
    path = tmp_path / "public.csv"
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Desc", "Cat"])
        writer.writerows(ROWS)
    return path


def test_load_dataset_maps_and_drops(public_csv):
    texts, labels, dropped = train.load_dataset(public_csv, "Desc", "Cat", MAPPING)
    assert len(texts) == len(labels) == 12
    assert set(labels) == {"Gas", "Groceries"}
    assert dropped["misc"] == 1 and dropped["fuel"] == 1  # unmapped category; blank description


def test_load_dataset_without_mapping_keeps_only_our_categories(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("Desc,Cat\nA,Gas\nB,Whatever\n")
    texts, labels, dropped = train.load_dataset(path, "Desc", "Cat")
    assert texts == ["A"] and labels == ["Gas"] and dropped["Whatever"] == 1


def test_bad_column_and_bad_mapping_are_errors(public_csv):
    with pytest.raises(ValueError, match="not in"):
        train.load_dataset(public_csv, "Nope", "Cat", MAPPING)
    with pytest.raises(ValueError, match="valid categories"):
        train.load_dataset(public_csv, "Desc", "Cat", {"fuel": "Petrol"})


def test_split_is_deterministic_and_disjoint():
    texts = [f"t{i}" for i in range(20)]
    labels = ["a"] * 20
    first = train.split(texts, labels, 0.25, seed=1)
    assert first == train.split(texts, labels, 0.25, seed=1)
    assert len(first[0]) == 15 and len(first[2]) == 5
    assert not set(first[0]) & set(first[2])


def test_pipeline_learns_obvious_pattern():
    X = [r[0] for r in ROWS[:12]]
    y = [MAPPING[r[1]] for r in ROWS[:12]]
    model = train.build_pipeline().fit(X, y)
    assert list(model.predict(["SHELL OIL 9999", "SAFEWAY #7"])) == ["Gas", "Groceries"]


def test_cli_saves_model_and_scores_labeled_file(public_csv, tmp_path, capsys):
    mapping_path = tmp_path / "map.json"
    mapping_path.write_text(json.dumps(MAPPING))
    labeled = tmp_path / "labeled.csv"
    labeled.write_text("date,description,amount,true_category\n"
                       "2026-01-01,SHELL OIL 77,-30.00,Gas\n2026-01-02,SAFEWAY 9,-20.00,Groceries\n")
    out = tmp_path / "model.joblib"
    code = train.main(["--data", str(public_csv), "--desc-col", "Desc", "--cat-col", "Cat",
                       "--mapping", str(mapping_path), "--eval", str(labeled), "--out", str(out)])
    assert code == 0
    saved = joblib.load(out)
    assert saved["labels"] == ["Gas", "Groceries"]
    assert list(saved["pipeline"].predict(["CHEVRON 12"])) == ["Gas"]
    assert "rules baseline macro-F1" in capsys.readouterr().out


def test_macro_f1_basic():
    assert macro_f1(["a", "b"], ["a", "b"]) == 1.0
    assert macro_f1(["a", "b"], ["a", "a"]) == pytest.approx(1 / 3)


def test_mapping_ignores_underscore_comment_keys(public_csv):
    texts, labels, _ = train.load_dataset(public_csv, "Desc", "Cat", {"_comment": "note", **MAPPING})
    assert set(labels) == {"Gas", "Groceries"}


def test_cli_trains_from_seed_data_alone(tmp_path):
    seed = tmp_path / "seed.csv"
    seed.write_text("description,category\n" + "\n".join(
        f"{d},{c}" for d, c in [("SHELL OIL 1", "Gas"), ("CHEVRON 2", "Gas"), ("ARCO 3", "Gas"),
                               ("SAFEWAY 4", "Groceries"), ("ALDI 5", "Groceries"), ("VONS 6", "Groceries")]) + "\n")
    out = tmp_path / "m.joblib"
    assert train.main(["--seed-data", str(seed), "--out", str(out)]) == 0
    assert joblib.load(out)["labels"] == ["Gas", "Groceries"]


def test_cli_requires_some_data(tmp_path):
    with pytest.raises(SystemExit):
        train.main(["--out", str(tmp_path / "m.joblib")])
