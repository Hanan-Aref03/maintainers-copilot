from pathlib import Path
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .classifiers import RuleClassifier, GeminiZeroShotClassifier, GeminiFewShotClassifier


def load_repo_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_repo_env()

app = FastAPI(title="Model Server")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

rule_clf = RuleClassifier()


@lru_cache(maxsize=1)
def get_zero_clf() -> GeminiZeroShotClassifier | None:
    if not GEMINI_API_KEY:
        return None
    return GeminiZeroShotClassifier(GEMINI_API_KEY, GEMINI_MODEL)


@lru_cache(maxsize=1)
def get_few_clf() -> GeminiFewShotClassifier | None:
    if not GEMINI_API_KEY:
        return None
    return GeminiFewShotClassifier(GEMINI_API_KEY, GEMINI_MODEL)


class ClassifyRequest(BaseModel):
    title: str
    body: str
    model: str = "rule"  # rule, zero, few


@app.post("/classify")
async def classify(req: ClassifyRequest):
    if req.model == "rule":
        label = rule_clf.predict(req.title, req.body)
    elif req.model == "zero":
        zero_clf = get_zero_clf()
        if not zero_clf:
            raise HTTPException(500, "Gemini API key missing")
        label = zero_clf.predict(req.title, req.body)
    elif req.model == "few":
        few_clf = get_few_clf()
        if not few_clf:
            raise HTTPException(500, "Gemini API key missing")
        label = few_clf.predict(req.title, req.body)
    else:
        raise HTTPException(400, "model must be rule/zero/few")
    return {"label": label}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gemini_ready": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL,
    }
