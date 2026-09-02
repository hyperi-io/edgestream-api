"""
Project:   edgestream-api
File:      edgestream/tests/test_status.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

# edgestream/tests/test_status.py
from edgestream.core.config import settings

def test_status_all(client):
    r = client.get(f"{settings.API_V1_STR}/status/all")
    assert r.status_code in (200, 204)
    if r.status_code == 200:
        assert isinstance(r.json(), dict)
