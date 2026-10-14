"""ML service: transaction categorization.

Keyword rules first, then the trained scikit-learn model for anything the rules do not
recognize (see categorizer.py). Without a model file it serves rules only.

Settings (environment): MODEL_PATH (default models/model.joblib), MODEL_THRESHOLD
(minimum model confidence, default 0.0 = always trust the model for unmatched rows).
"""
from fastapi import FastAPI
from pydantic import BaseModel, Field

from categorizer import Categorizer

app = FastAPI(title="FinancialTracker ML service")
categorizer = Categorizer.from_env()


class CategorizeRequest(BaseModel):
    # Batch endpoint on purpose: the importer sends many rows per call.
    descriptions: list[str] = Field(min_length=1, max_length=1000)


class Prediction(BaseModel):
    description: str
    category: str
    source: str  # "rules" or "model"
    matched: str | None = None  # the rules keyword, when source is "rules" and one matched
    confidence: float | None = None  # model probability, when the model was consulted


class CategorizeResponse(BaseModel):
    predictions: list[Prediction]


@app.get("/healthz")
def healthz() -> dict[str, str | bool]:
    return {"status": "ok", "model_loaded": categorizer.model_loaded}


@app.post("/categorize", response_model=CategorizeResponse)
def categorize_batch(req: CategorizeRequest) -> CategorizeResponse:
    return CategorizeResponse(predictions=categorizer.predict(req.descriptions))
