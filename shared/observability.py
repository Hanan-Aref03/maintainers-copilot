from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import re
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Iterator
from urllib.parse import urlparse
from uuid import uuid4

try:  # pragma: no cover - optional dependency in local dev
    from opentelemetry import trace as otel_trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode
except Exception:  # pragma: no cover - graceful fallback
    otel_trace = None
    OTLPSpanExporter = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    Status = None
    StatusCode = None

REDACTION_PLACEHOLDER = "[REDACTED]"
_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
_TRACING_READY = False
_LOGGING_READY = False

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "jwt",
    "password",
    "secret",
    "token",
    "minio_access_key",
    "minio_root_user",
    "vault_token",
    "db_password",
    "minio_secret",
    "minio_password",
    "minio_secret_key",
    "minio_root_password",
}

_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), REDACTION_PLACEHOLDER),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), REDACTION_PLACEHOLDER),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTION_PLACEHOLDER),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), REDACTION_PLACEHOLDER),
    (re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)([^\s]+)"), r"\1" + REDACTION_PLACEHOLDER),
    (
        re.compile(
            r"(?i)\b((?:api[_-]?key|token|secret|password|jwt|vault_token|db_password|minio_access_key|minio_secret_key|minio_root_user|minio_root_password)\s*[:=]\s*)([^\s,;'\"`]+)"
        ),
        r"\1" + REDACTION_PLACEHOLDER,
    ),
]


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if is_dataclass(value):
        return json.dumps(asdict(value), default=str, ensure_ascii=False)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(redact_payload(value), default=str, ensure_ascii=False)
    return str(value)


def redact_text(value: Any) -> str:
    text = _stringify(value)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key).strip().lower()
            if any(sensitive in key_text for sensitive in _SENSITIVE_KEYS):
                redacted[key] = REDACTION_PLACEHOLDER
            else:
                redacted[key] = redact_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_payload(item) for item in value)
    if isinstance(value, set):
        return {redact_payload(item) for item in value}
    if isinstance(value, str):
        return redact_text(value)
    return value


def get_request_id() -> str:
    return _REQUEST_ID.get()


def get_trace_id() -> str:
    return _TRACE_ID.get()


def set_request_id(request_id: str | None = None) -> contextvars.Token[str]:
    value = request_id or uuid4().hex
    return _REQUEST_ID.set(value)


def set_trace_id(trace_id: str | None = None) -> contextvars.Token[str]:
    value = trace_id or ""
    return _TRACE_ID.set(value)


def _coerce_endpoint(endpoint: str) -> tuple[str, bool]:
    parsed = urlparse(endpoint)
    if parsed.scheme and parsed.netloc:
        target = parsed.netloc
        if parsed.path and parsed.path != "/":
            target = f"{target}{parsed.path}"
        return target, parsed.scheme == "http"
    return endpoint, False


def configure_logging(service_name: str) -> None:
    global _LOGGING_READY
    if _LOGGING_READY:
        return

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s trace_id=%(trace_id)s %(message)s",
        )

    handler_targets = list(root.handlers)
    filter_ = RedactionFilter(service_name=service_name)
    root.addFilter(filter_)
    for handler in handler_targets:
        handler.addFilter(filter_)

    _LOGGING_READY = True


def setup_tracing(service_name: str) -> None:
    global _TRACING_READY
    configure_logging(service_name)
    if _TRACING_READY or otel_trace is None or TracerProvider is None:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    resource = Resource.create({"service.name": service_name}) if Resource is not None else None
    provider = TracerProvider(resource=resource) if resource is not None else TracerProvider()
    if endpoint and OTLPSpanExporter is not None and BatchSpanProcessor is not None:
        target, insecure = _coerce_endpoint(endpoint)
        exporter = OTLPSpanExporter(endpoint=target, insecure=insecure)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    otel_trace.set_tracer_provider(provider)
    _TRACING_READY = True


@contextlib.contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
    tracer = otel_trace.get_tracer(__name__) if otel_trace is not None else None
    if tracer is None:
        start = time.perf_counter()
        try:
            yield None
        except Exception as exc:
            logging.getLogger(__name__).exception("Unhandled error in span %s: %s", name, redact_text(exc))
            raise
        finally:
            _ = time.perf_counter() - start
        return

    redacted_attributes = redact_payload(attributes or {})
    start = time.perf_counter()
    with tracer.start_as_current_span(name) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"
        token = set_trace_id(trace_id)
        try:
            for key, value in redacted_attributes.items():
                span.set_attribute(key, _attribute_value(value))
            span.set_attribute("request.id", get_request_id())
            yield span
        except Exception as exc:
            if Status is not None and StatusCode is not None:
                span.set_status(Status(StatusCode.ERROR))
            try:
                span.record_exception(exc)
            except Exception:  # pragma: no cover - defensive
                pass
            raise
        finally:
            span.set_attribute("latency_ms", round((time.perf_counter() - start) * 1000, 3))
            _TRACE_ID.reset(token)


def install_fastapi_observability(app: Any, service_name: str) -> None:
    setup_tracing(service_name)

    @app.middleware("http")
    async def _observability_middleware(request, call_next):
        request_token = set_request_id(request.headers.get("X-Request-ID"))
        request_id = get_request_id()
        request.state.request_id = request_id
        try:
            with trace_span(
                "http.request",
                {
                    "http.method": request.method,
                    "http.path": request.url.path,
                    "http.query": dict(request.query_params),
                },
            ) as span:
                response = await call_next(request)
                if span is not None:
                    try:
                        span.set_attribute("http.status_code", int(response.status_code))
                    except Exception:  # pragma: no cover - defensive
                        pass
                response.headers["X-Request-ID"] = request_id
                trace_id = get_trace_id()
                if trace_id:
                    response.headers["X-Trace-ID"] = trace_id
                return response
        finally:
            _REQUEST_ID.reset(request_token)


def _attribute_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return json.dumps(redact_payload(value), ensure_ascii=False)
    if isinstance(value, (list, tuple, set)):
        return json.dumps(redact_payload(list(value)), ensure_ascii=False)
    return redact_text(value)


class RedactionFilter(logging.Filter):
    def __init__(self, service_name: str) -> None:
        super().__init__(name=service_name)

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.trace_id = get_trace_id() or "-"
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        else:
            record.msg = redact_payload(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = redact_payload(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_payload(arg) for arg in record.args)
            else:
                record.args = redact_payload(record.args)
        return True
