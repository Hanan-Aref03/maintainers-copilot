from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_auth, routes_chat, routes_widgets, routes_memory
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.infra.database import get_session_local
from app.infra.vault_client import VaultClient
from app.services.bootstrap_service import bootstrap_demo_data
from shared.observability import install_fastapi_observability

logger = logging.getLogger(__name__)


app = FastAPI(title="Maintainer's Copilot")
install_fastapi_observability(app, "copilot-api")

cors_allow_origins = [
    origin.strip()
    for origin in settings.cors_allow_origins.split(",")
    if origin.strip()
]

if cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
async def startup_event():
    # Load secrets from Vault into environment
    vault_secrets = VaultClient.load_secrets()
    # Override settings with Vault values
    if vault_secrets:
        settings.gemini_api_key = VaultClient.get_gemini_api_key() or settings.gemini_api_key
        settings.voyage_api_key = VaultClient.get_voyage_api_key() or settings.voyage_api_key
        settings.jwt_secret = VaultClient.get_secret("jwt_secret") or settings.jwt_secret
        logger.info("Vault secrets loaded")
    else:
        logger.warning("Vault secrets unavailable; using local settings")

    if settings.bootstrap_demo_data:
        session_local = get_session_local()
        db = session_local()
        try:
            bootstrap_demo_data(db)
        except Exception:
            logger.exception("Demo bootstrap failed")
        finally:
            db.close()
    else:
        logger.info("Demo bootstrap disabled")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "vault_loaded": bool(VaultClient._secrets),
        "gemini_ready": bool(settings.gemini_api_key),
        "voyage_ready": bool(settings.voyage_api_key),
        "gemini_model": settings.gemini_model,
        "voyage_embedding_model": settings.voyage_embedding_model,
    }


# Register routers
app.include_router(routes_auth.router, prefix="/auth", tags=["auth"])
app.include_router(routes_chat.router, prefix="/chat", tags=["chat"])
app.include_router(routes_widgets.router, prefix="/widgets", tags=["widgets"])
app.include_router(routes_memory.router, prefix="/memory", tags=["memory"])

register_exception_handlers(app)
