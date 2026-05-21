"""Compatibility wrapper for pgvector.

If the pgvector package is available, we use its native Vector type.
Otherwise, fall back to JSON so the codebase and Alembic can still import
cleanly in lightweight dev environments.
"""

from sqlalchemy.types import JSON, TypeDecorator

try:
    from pgvector.sqlalchemy import Vector as _Vector
except ImportError:  # pragma: no cover - exercised when pgvector is absent
    class Vector(TypeDecorator):
        impl = JSON
        cache_ok = True

        def __init__(self, dim: int):
            self.dim = dim
            super().__init__()

        def __repr__(self) -> str:
            return f"Vector({self.dim})"
else:
    Vector = _Vector

