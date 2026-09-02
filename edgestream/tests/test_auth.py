"""
Project:   edgestream-api
File:      edgestream/tests/test_auth.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

# edgestream/tests/test_auth.py
from edgestream.core.config import settings

def test_access_token_requires_body(client):
    r = client.post(f"{settings.API_V1_STR}/auth/login", data={})
    assert r.status_code in (400, 422)

def test_whoami_with_override(client):
    r = client.get(f"{settings.API_V1_STR}/auth/whoami")
    assert r.status_code == 200
    j = r.json()
    assert "email" in j and "id" in j
