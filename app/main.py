#FastAPI main application setup with routers and exception handlers (layered)
from fastapi import FastAPI
from app.api import routes_auth, routes_chat, routes_widgets, routes_memory
from app.core.exceptions import register_exception_handlers
from app.infra.tracing import setup_tracing
from app.infra.vault_client import VaultClient
from app.core.config import settings

setup_tracing(app_name="copilot-api")

app = FastAPI(title="Maintainer's Copilot")

@app.on_event("startup")
async def startup_event():
    # Load secrets from Vault into environment
    VaultClient.load_secrets()
    # Override settings with Vault values
    settings.gemini_api_key = VaultClient.get_gemini_api_key()
    settings.jwt_secret = VaultClient.get_secret("jwt_secret")
    print("✅ Vault secrets loaded")

@app.get("/health")
async def health():
    return {"status": "ok", "vault_loaded": bool(settings.gemini_api_key)}

# Register routers
app.include_router(routes_auth.router, prefix="/auth", tags=["auth"])
app.include_router(routes_chat.router, prefix="/chat", tags=["chat"])
app.include_router(routes_widgets.router, prefix="/widgets", tags=["widgets"])
app.include_router(routes_memory.router, prefix="/memory", tags=["memory"])

register_exception_handlers(app)
