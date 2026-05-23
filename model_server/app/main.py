from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.infra.blob_store import get_blob_store
from .classifiers import (
    FineTunedClassifier,
    GeminiEntityExtractor,
    GeminiFewShotClassifier,
    GeminiSummarizer,
    GeminiZeroShotClassifier,
    RuleClassifier,
    RuleEntityExtractor,
    RuleSummarizer,
)
from shared.observability import install_fastapi_observability, trace_span

logger = logging.getLogger(__name__)


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
app.state.model_artifacts_ready = False
install_fastapi_observability(app, "copilot-model-server")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FINE_TUNED_MODEL_DIR = os.getenv("FINE_TUNED_MODEL_DIR", "artifacts/classification")

rule_clf = RuleClassifier()
rule_ner = RuleEntityExtractor()
rule_summarizer = RuleSummarizer()


@app.on_event("startup")
async def startup_event():
    try:
        get_blob_store(settings.minio_model_bucket).ensure_bucket()
        app.state.model_artifacts_ready = True
    except Exception:
        logger.exception("Failed to bootstrap the model artifact bucket")
        app.state.model_artifacts_ready = False


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


@lru_cache(maxsize=1)
def get_fine_clf() -> FineTunedClassifier | None:
    try:
        return FineTunedClassifier(FINE_TUNED_MODEL_DIR)
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_gemini_ner() -> GeminiEntityExtractor | None:
    if not GEMINI_API_KEY:
        return None
    return GeminiEntityExtractor(GEMINI_API_KEY, GEMINI_MODEL)


@lru_cache(maxsize=1)
def get_gemini_summarizer() -> GeminiSummarizer | None:
    if not GEMINI_API_KEY:
        return None
    return GeminiSummarizer(GEMINI_API_KEY, GEMINI_MODEL)


class ClassifyRequest(BaseModel):
    title: str
    body: str
    model: str = "rule"  # rule, fine, zero, few


class NerRequest(BaseModel):
    text: str
    model: str = "rule"  # rule, gemini


class SummarizeRequest(BaseModel):
    text: str
    model: str = "rule"  # rule, gemini
    max_sentences: int = 3


def _predict_classifier_with_metadata(model: str, title: str, body: str) -> dict[str, object]:
    if model == "rule":
        label, metadata = rule_clf.predict_with_metadata(title, body)
    elif model in {"fine", "fine-tuned"}:
        fine_clf = get_fine_clf()
        if not fine_clf:
            raise HTTPException(500, "Fine-tuned classifier unavailable")
        label, metadata = fine_clf.predict_with_metadata(title, body)
    elif model == "zero":
        zero_clf = get_zero_clf()
        if not zero_clf:
            raise HTTPException(500, "Gemini API key missing")
        label, metadata = zero_clf.predict_with_metadata(title, body)
    elif model == "few":
        few_clf = get_few_clf()
        if not few_clf:
            raise HTTPException(500, "Gemini API key missing")
        label, metadata = few_clf.predict_with_metadata(title, body)
    else:
        raise HTTPException(400, "model must be rule/fine/zero/few")

    return {
        "label": label,
        "classifier_source": metadata.get("classifier_source"),
        "used_fallback": bool(metadata.get("used_fallback", False)),
        "fallback_reason": metadata.get("fallback_reason"),
    }


@app.post("/classify")
async def classify(req: ClassifyRequest):
    with trace_span(
        "model_server.classify",
        {"model": req.model, "title_preview": req.title[:200], "body_preview": req.body[:300]},
    ):
        return _predict_classifier_with_metadata(req.model, req.title, req.body)


@app.post("/ner")
async def ner(req: NerRequest):
    with trace_span("model_server.ner", {"model": req.model, "text_preview": req.text[:300]}):
        if req.model == "rule":
            entities = rule_ner.predict(req.text)
        elif req.model == "gemini":
            extractor = get_gemini_ner()
            if not extractor:
                raise HTTPException(500, "Gemini API key missing")
            entities = extractor.predict(req.text)
        else:
            raise HTTPException(400, "model must be rule/gemini")

        return {"entities": entities}


@app.post("/summarize")
async def summarize(req: SummarizeRequest):
    with trace_span(
        "model_server.summarize",
        {"model": req.model, "text_preview": req.text[:300], "max_sentences": req.max_sentences},
    ):
        if req.model == "rule":
            summary = rule_summarizer.predict(req.text, max_sentences=req.max_sentences)
        elif req.model == "gemini":
            summarizer = get_gemini_summarizer()
            if not summarizer:
                raise HTTPException(500, "Gemini API key missing")
            summary = summarizer.predict(req.text, max_sentences=req.max_sentences)
        else:
            raise HTTPException(400, "model must be rule/gemini")

        return {"summary": summary}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gemini_ready": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL,
        "model_artifacts_ready": bool(getattr(app.state, "model_artifacts_ready", False)),
        "model_artifacts_bucket": settings.minio_model_bucket,
        "classification_ready": True,
        "fine_tuned_ready": bool(get_fine_clf()),
        "ner_ready": True,
        "summarizer_ready": True,
    }
