"""Combines the keyword rules with the trained model.

Order for each description:
  1. A rules keyword matches            -> source "rules" (explicit, deterministic)
  2. No keyword, model confident enough -> source "model"
  3. Otherwise                          -> "Other", source "rules"

If no model file is present (or it cannot be loaded) the service runs on rules alone.
"""
import logging
import os

from rules import FALLBACK, categorize

logger = logging.getLogger("ml")


class Categorizer:
    def __init__(self, model_path: str | None = None, threshold: float = 0.0):
        self.threshold = threshold
        self.pipeline = None
        if model_path and os.path.exists(model_path):
            self.pipeline = self._load(model_path)
        elif model_path:
            logger.info("no model at %s; serving rules only", model_path)

    @staticmethod
    def _load(path: str):
        try:
            import joblib
            import sklearn

            saved = joblib.load(path)
            if saved.get("sklearn") != sklearn.__version__:
                logger.warning("model trained with scikit-learn %s, running %s",
                               saved.get("sklearn"), sklearn.__version__)
            logger.info("loaded model from %s (%d labels)", path, len(saved["labels"]))
            return saved["pipeline"]
        except Exception:  # noqa: BLE001 - a bad model file must not take the service down
            logger.exception("could not load model at %s; serving rules only", path)
            return None

    @classmethod
    def from_env(cls) -> "Categorizer":
        return cls(os.environ.get("MODEL_PATH", "models/model.joblib"),
                   float(os.environ.get("MODEL_THRESHOLD", "0.0")))

    @property
    def model_loaded(self) -> bool:
        return self.pipeline is not None

    def predict(self, descriptions: list[str]) -> list[dict]:
        results = []
        for description in descriptions:
            category, matched = categorize(description)
            results.append({"description": description, "category": category, "source": "rules",
                            "matched": matched, "confidence": None})

        if self.pipeline is None:
            return results
        pending = [i for i, r in enumerate(results) if r["matched"] is None]
        if pending:
            probabilities = self.pipeline.predict_proba([descriptions[i] for i in pending])
            classes = list(self.pipeline.classes_)
            for i, row in zip(pending, probabilities):
                best = int(row.argmax())
                results[i]["confidence"] = float(row[best])
                if row[best] >= self.threshold:
                    results[i].update(category=classes[best], source="model")
                else:
                    results[i]["category"] = FALLBACK
        return results
