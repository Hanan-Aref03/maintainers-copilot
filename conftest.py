from __future__ import annotations

import shutil
from uuid import uuid4
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path() -> Path:
    root = Path.cwd() / ".local-tmp"
    root.mkdir(exist_ok=True)
    path = root / f"pytest-{uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
