"""
Project:   edgestream-api
File:      edgestream/tests/test_openapi.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

# edgestream/tests/test_openapi.py
from edgestream.core.config import settings

def test_openapi_served(client):
    r = client.get(f"{settings.API_V1_STR}/openapi.json")
    assert r.status_code == 200
    j = r.json()
    assert "openapi" in j and "paths" in j
