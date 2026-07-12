"""Test configuration: force fixture mode + an isolated temp SQLite DB.

Set env BEFORE any app module imports so the settings singleton and DB engine
pick these up.
"""
import os
import tempfile
from pathlib import Path

_tmp_db = Path(tempfile.gettempdir()) / "mlg_test.db"
if _tmp_db.exists():
    _tmp_db.unlink()

os.environ["DATAHUB_MODE"] = "fixture"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.as_posix()}"
os.environ["GEMINI_API_KEY"] = ""

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    # TestClient(app) at module scope does not run the lifespan startup, so
    # create tables explicitly against the temp DB.
    from backend.app.db import init_db

    init_db()


@pytest.fixture(autouse=True)
def _reset_overrides():
    # The fixture client's simulation overrides live in a module global; clear
    # them around every test so cases stay isolated.
    from backend.app.services.datahub.fixture_client import clear_overrides

    clear_overrides()
    yield
    clear_overrides()
