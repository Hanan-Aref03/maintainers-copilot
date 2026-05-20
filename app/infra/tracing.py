def setup_tracing(app_name: str) -> None:
    # Tracing is optional in local dev; keep startup safe when exporters are absent.
    return None
