"""ML service: transaction categorization.

Day 1: serves the keyword rules baseline.
Day 2: swap in the trained scikit-learn model (TF-IDF + logistic regression),
keep the rules as a fallback, and report source='model' vs 'rules'.
"""
from fastapi import FastAPI
from pydantic import BaseModel, Field

from rules import categorize

app = FastAPI(title="FinancialTracker ML service")


class CategorizeRequest(BaseModel):
    # Batch endpoint on purpose: the Go importer sends many rows per call.
    descriptions: list[str] = Field(min_length=1, max_length=1000)


class Prediction(BaseModel):
    description: str
    category: str
    source: str
    matched: str | None = None


class CategorizeResponse(BaseModel):
    predictions: list[Prediction]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/categorize", response_model=CategorizeResponse)
def categorize_batch(req: CategorizeRequest) -> CategorizeResponse:
    predictions = []
    for description in req.descriptions:
        category, matched = categorize(description)
        predictions.append(
            Prediction(description=description, category=category, source="rules", matched=matched)
        )
    return CategorizeResponse(predictions=predictions)
