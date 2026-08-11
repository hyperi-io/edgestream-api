
# Edgestream API Tests

## How to run

```bash
cd /path/edgestream-api
python -m pip install -r requirements.txt -r requirements-prod.txt pytest httpx
pytest -q
```

The tests:
- set a temporary SQLite database
- override auth with a fake user
- write config exports to `tests/.export/edgestream-test.yaml`
- enqueue Ansible jobs to `tests/.ansible-queue/`

Edit `tests/conftest.py` to tweak the env or dependency overrides.
