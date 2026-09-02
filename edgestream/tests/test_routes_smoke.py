"""
Project:   edgestream-api
File:      edgestream/tests/test_routes_smoke.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

# edgestream/tests/test_routes_smoke.py
from fastapi.routing import APIRoute
from starlette.routing import WebSocketRoute, Mount
from edgestream.main import app

def _is_static_or_ws(r): return isinstance(r, (WebSocketRoute, Mount))
def _has_path_params(p: str): return "{" in p and "}" in p

def test_all_gettable_routes_smoke(client):
    tested = 0
    for route in app.routes:
        if _is_static_or_ws(route) or not isinstance(route, APIRoute):
            continue
        if "GET" in (route.methods or set()) and not _has_path_params(route.path):
            if route.path == "/":  # Jinja root
                continue
            r = client.get(route.path)
            assert r.status_code in (200, 201, 202, 204, 401, 403)
            tested += 1
    assert tested > 0

def test_options_on_all_routes(client):
    tested = 0
    for route in app.routes:
        if _is_static_or_ws(route) or not isinstance(route, APIRoute):
            continue
        r = client.options(route.path)
        assert r.status_code in (200, 204, 405)
        tested += 1
    assert tested > 0
