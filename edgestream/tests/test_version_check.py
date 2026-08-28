from __future__ import annotations

import http.server
import json
import threading
import uuid

from edgestream.core.config import settings
from edgestream.services import version_check


def _serve(received: list[dict]):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append(json.loads(body))
            resp = json.dumps(
                {"update_available": True, "latest_version": "99.0.0"}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_on_by_default():
    # Class defaults, not the singleton: conftest opts the suite out.
    fields = type(settings).model_fields
    assert fields["VERSION_CHECK_ENABLED"].default is True
    assert (
        fields["VERSION_CHECK_API_URL"].default
        == "https://releases.hyperi.io/api/v1/check"
    )


def test_explicit_opt_out_spawns_nothing(monkeypatch):
    monkeypatch.setattr(settings, "VERSION_CHECK_ENABLED", False)
    assert version_check.check_on_startup() is None


def test_non_http_url_spawns_nothing(monkeypatch):
    monkeypatch.setattr(settings, "VERSION_CHECK_ENABLED", True)
    monkeypatch.setattr(settings, "VERSION_CHECK_API_URL", "file:///etc/passwd")
    assert version_check.check_on_startup() is None


def test_enabled_posts_platform_payload(monkeypatch):
    received: list[dict] = []
    server = _serve(received)
    try:
        monkeypatch.setattr(settings, "VERSION_CHECK_ENABLED", True)
        monkeypatch.setattr(
            settings,
            "VERSION_CHECK_API_URL",
            f"http://127.0.0.1:{server.server_address[1]}/",
        )
        thread = version_check.check_on_startup()
        assert thread is not None
        thread.join(timeout=10)
        assert not thread.is_alive()
    finally:
        server.shutdown()

    assert len(received) == 1
    payload = received[0]
    assert set(payload) == {"product", "current_version", "os", "arch", "instance_id"}
    assert payload["product"] == "edgestream-api"
    uuid.UUID(payload["instance_id"])
    # deployment-style fields never leave the host
    assert "deployment" not in payload


def test_send_instance_id_false_strips_the_id(monkeypatch):
    received: list[dict] = []
    server = _serve(received)
    try:
        monkeypatch.setattr(settings, "VERSION_CHECK_ENABLED", True)
        monkeypatch.setattr(settings, "VERSION_CHECK_SEND_INSTANCE_ID", False)
        monkeypatch.setattr(
            settings,
            "VERSION_CHECK_API_URL",
            f"http://127.0.0.1:{server.server_address[1]}/",
        )
        thread = version_check.check_on_startup()
        assert thread is not None
        thread.join(timeout=10)
    finally:
        server.shutdown()

    assert set(received[0]) == {"product", "current_version", "os", "arch"}


def test_explicit_instance_id_wins(monkeypatch):
    monkeypatch.setattr(settings, "VERSION_CHECK_INSTANCE_ID", "operator-chosen")
    assert version_check.resolve_instance_id() == "operator-chosen"


def test_resolved_instance_id_is_stable():
    assert version_check.resolve_instance_id() == version_check.resolve_instance_id()


def test_unreachable_endpoint_costs_one_log_line_only(monkeypatch):
    monkeypatch.setattr(settings, "VERSION_CHECK_ENABLED", True)
    # Closed port: connection refused inside the daemon thread, swallowed.
    monkeypatch.setattr(settings, "VERSION_CHECK_API_URL", "http://127.0.0.1:9/")
    thread = version_check.check_on_startup()
    assert thread is not None
    thread.join(timeout=15)
    assert not thread.is_alive()


def test_machine_derivation_is_shared_across_products():
    # The UUIDv5 namespace is shared HyperI-wide; fixture mirrored in scalo.
    derived = uuid.uuid5(version_check.INSTANCE_ID_NS, "machine:test-fixture")
    assert str(derived) == "4f9f9577-e391-5835-8236-3e88e902b11b"
