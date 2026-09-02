"""
Project:   edgestream-api
File:      edgestream/tests/test_system.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

# edgestream/tests/test_system.py
from edgestream.core.config import settings

def test_fetch_hostname(client):
    r = client.get(f"{settings.API_V1_STR}/system/hostname")
    assert r.status_code == 200
    assert "hostname" in r.json()

def test_update_hostname_validation(client):
    r = client.put(f"{settings.API_V1_STR}/system/hostname", json={"hostname": "bad host!"})
    assert r.status_code == 400

def test_update_org_id_validation(client):
    r = client.put(f"{settings.API_V1_STR}/system/org_id", json={"org_id": "!not-valid"})
    assert r.status_code == 400
