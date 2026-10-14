"""Shared scoring so the rules baseline and the trained model are compared identically."""
from collections import Counter


def per_class_scores(truth: list[str], pred: list[str]) -> dict[str, tuple[int, float, float, float]]:
    """label -> (support, precision, recall, f1) for every label present in `truth`."""
    scores = {}
    for label in sorted(set(truth)):
        tp = sum(t == label and p == label for t, p in zip(truth, pred))
        fp = sum(t != label and p == label for t, p in zip(truth, pred))
        fn = sum(t == label and p != label for t, p in zip(truth, pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores[label] = (truth.count(label), precision, recall, f1)
    return scores


def macro_f1(truth: list[str], pred: list[str]) -> float:
    scores = per_class_scores(truth, pred)
    return sum(s[3] for s in scores.values()) / len(scores)


def accuracy(truth: list[str], pred: list[str]) -> float:
    return sum(t == p for t, p in zip(truth, pred)) / len(truth)


def print_report(truth: list[str], pred: list[str], descriptions: list[str] | None = None) -> None:
    print(f"rows: {len(truth)}   accuracy: {accuracy(truth, pred):.3f}\n")
    print(f"{'category':<14}{'support':>8}{'precision':>11}{'recall':>8}{'f1':>7}")
    for label, (support, precision, recall, f1) in per_class_scores(truth, pred).items():
        print(f"{label:<14}{support:>8}{precision:>11.2f}{recall:>8.2f}{f1:>7.2f}")
    print(f"\nmacro-F1: {macro_f1(truth, pred):.3f}")
    if descriptions is not None:
        mistakes = [(t, p, d) for t, p, d in zip(truth, pred, descriptions) if t != p]
        print(f"\nmistakes ({len(mistakes)}):")
        for t, p, d in mistakes:
            print(f"  true={t:<10} pred={p:<10} {d}")
    print("\nlabel counts:", dict(Counter(truth)))
