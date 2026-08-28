from __future__ import annotations

import hashlib
import json
import platform
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from edgestream.core.config import Logger, settings

PRODUCT = "edgestream-api"

# UUIDv5 namespace for platform-derived instance ids, shared across HyperI
# products (uuid5(NAMESPACE_DNS, "scalo.hyperi.io")) so one host derives one
# id whichever product reports first.
INSTANCE_ID_NS = uuid.UUID("10ada713-52f0-5b77-aab7-7792712f92a0")

_K8S_SA = Path("/var/run/secrets/kubernetes.io/serviceaccount")


def check_on_startup() -> threading.Thread | None:
    """Fire-and-forget check for a newer version. Never blocks, never raises.

    On by default; VERSION_CHECK_ENABLED=false is the opt-out and always
    wins. Any failure (unreachable endpoint, firewall, air-gapped host)
    costs one warning log line and nothing else.

    Returns the daemon thread when a check was kicked off, else None; tests
    join() it instead of sleeping.
    """
    if not settings.VERSION_CHECK_ENABLED:
        Logger.logger.debug("version check disabled (VERSION_CHECK_ENABLED=false)")
        return None
    if not settings.VERSION_CHECK_API_URL:
        Logger.logger.debug("version check skipped: VERSION_CHECK_API_URL not set")
        return None
    if urllib.parse.urlsplit(settings.VERSION_CHECK_API_URL).scheme not in ("http", "https"):
        Logger.logger.warning("version check skipped: VERSION_CHECK_API_URL must be http(s)")
        return None

    thread = threading.Thread(target=_run_check, name="version-check", daemon=True)
    thread.start()
    return thread


def _run_check() -> None:
    try:
        _do_check()
    except Exception as exc:  # one log line, never a failure
        Logger.logger.warning(f"version check failed (non-fatal): {exc}")


def _do_check() -> None:
    payload: dict[str, str] = {
        "product": PRODUCT,
        "current_version": settings.VERSION,
        "os": platform.system(),
        "arch": platform.machine(),
    }
    if settings.VERSION_CHECK_SEND_INSTANCE_ID:
        payload["instance_id"] = resolve_instance_id()

    request = urllib.request.Request(
        settings.VERSION_CHECK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        request, timeout=settings.VERSION_CHECK_TIMEOUT
    ) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data.get("update_available") and data.get("latest_version"):
        url = data.get("release_url") or ""
        Logger.logger.info(
            f"new version available: {PRODUCT} "
            f"(current: {settings.VERSION}, latest: {data['latest_version']})"
            + (f" -- {url}" if url else "")
        )
    else:
        Logger.logger.debug(f"{PRODUCT} {settings.VERSION} is the latest version")

    if data.get("message"):
        Logger.logger.info(f"[{PRODUCT}] {data['message']}")


def resolve_instance_id() -> str:
    """Stable per-install id derived from what the app is running on.

    First hit wins: VERSION_CHECK_INSTANCE_ID verbatim; Kubernetes (UUIDv5
    over the serviceaccount cluster CA + namespace); /etc/machine-id as an
    app-scoped UUIDv5 outside containers (a machine-id baked into a container
    image would make every install report as one); a UUID persisted under
    ~/.config/edgestream/; an ephemeral UUID. Derived forms are one-way --
    nothing about the host can be recovered from them.
    """
    if settings.VERSION_CHECK_INSTANCE_ID:
        return settings.VERSION_CHECK_INSTANCE_ID
    return (
        _k8s_instance_id()
        or _machine_instance_id()
        or _persisted_instance_id()
        or str(uuid.uuid4())
    )


def _uuid5_bytes(material: bytes) -> uuid.UUID:
    digest = hashlib.sha1(INSTANCE_ID_NS.bytes + material).digest()  # noqa: S324  # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
    return uuid.UUID(bytes=digest[:16], version=5)


def _k8s_instance_id() -> str | None:
    try:
        ca = (_K8S_SA / "ca.crt").read_bytes()
        namespace = (_K8S_SA / "namespace").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return str(_uuid5_bytes(b"k8s:" + ca + b":" + namespace.encode("utf-8")))


def _machine_instance_id() -> str | None:
    if _in_container():
        return None
    for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            machine_id = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if len(machine_id) >= 32 and set(machine_id) != {"0"}:
            return str(_uuid5_bytes(f"machine:{machine_id}".encode()))
    return None


def _in_container() -> bool:
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8")
    except OSError:
        return False
    return any(marker in cgroup for marker in ("docker", "containerd", "kubepods"))


def _persisted_instance_id() -> str | None:
    directory = Path.home() / ".config" / "edgestream"
    path = directory / "instance_id"
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    new_id = str(uuid.uuid4())
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(new_id, encoding="utf-8", newline="\n")
    except OSError:
        return None
    return new_id
