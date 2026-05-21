from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.infra.redaction import redact_text
from shared.observability import get_request_id

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = 500

    def __str__(self) -> str:  # pragma: no cover - defensive convenience
        return self.message


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(code="not_found", message=message, status_code=404)


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(code="permission_denied", message=message, status_code=403)


class ToolFailure(AppError):
    def __init__(self, message: str = "Tool failure") -> None:
        super().__init__(code="tool_failure", message=message, status_code=502)


def _structured_error(code: str, message: str, request_id: str, detail: object | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
        },
        "request_id": request_id,
    }
    if detail is not None:
        payload["detail"] = detail
    return payload


def _request_id(request: Request | None = None) -> str:
    if request is not None:
        request_id = getattr(request.state, "request_id", "")
        if request_id:
            return request_id
    return get_request_id() or ""


def _http_code(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "permission_denied",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        502: "tool_failure",
        503: "service_unavailable",
    }
    return mapping.get(status_code, "internal_error")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = _request_id(request)
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            code = str(detail.get("code") or _http_code(exc.status_code))
            message = redact_text(detail.get("message") or detail)
        else:
            code = _http_code(exc.status_code)
            message = redact_text(detail if isinstance(detail, str) else "Request failed")
        return JSONResponse(
            status_code=exc.status_code,
            content=_structured_error(code, message, request_id, detail=detail),
        )

    @app.exception_handler(AppError)
    async def domain_exception_handler(request: Request, exc: AppError):
        request_id = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=_structured_error(exc.code, redact_text(exc.message), request_id),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = _request_id(request)
        logger.exception(
            "Unhandled exception request_id=%s: %s",
            request_id or "-",
            redact_text(exc),
        )
        return JSONResponse(
            status_code=500,
            content=_structured_error("internal_error", "Internal server error", request_id),
        )
