# edgestream/tests/conftest.py
import os
import pytest
from fastapi.testclient import TestClient

# The version check is on by default and TestClient runs the lifespan --
# opt the whole suite out so no test phones home.
os.environ.setdefault("VERSION_CHECK_ENABLED", "false")

# Make sure these are set BEFORE importing the app/config
@pytest.fixture(scope="session", autouse=True)
def _env_setup(tmp_path_factory):
    base = tmp_path_factory.mktemp("edgetests")
    os.environ.setdefault("EDGESTREAM_SQLALCHEMY_DATABASE_URI", f"sqlite:///{(base / 'test.db')}")
    os.environ.setdefault("EDGESTREAM_RUN_DIR", str(base / "run"))
    os.environ.setdefault("EDGESTREAM_ANSIBLE_QUEUE", str(base / "ansible-queue"))
    os.environ.setdefault("EDGESTREAM_CONFIGURATION_DIR", str(base / "export"))
    os.environ.setdefault("EDGESTREAM_CONFIGURATION", "edgestream-test.yaml")
    os.environ.setdefault("EDGESTREAM_TASK_DIR", str(base / "playbooks"))
    os.environ.setdefault("EDGESTREAM_TASK", "00_noop.yml")
    # dirs
    for d in ("run", "ansible-queue", "export", "playbooks"):
        (base / d).mkdir(parents=True, exist_ok=True)
    return base

# import after env is set
from edgestream.main import app
from edgestream.db.init_db import init_db
from edgestream.services.auth import auth as auth_mod

class _FakeUser:
    id = 1
    email = "test@example.com"
    is_active = True
    is_approved = True
    is_superuser = True

@pytest.fixture
def client(_env_setup):
    # ensure DB/tables/seed
    init_db()
    # bypass JWT for tests
    app.dependency_overrides[auth_mod.get_current_user] = lambda: _FakeUser()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(auth_mod.get_current_user, None)
