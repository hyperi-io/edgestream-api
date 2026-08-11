#!/usr/bin/env python3
"""
EdgeStream Ansible Queue Runner (stdlib + requests + subprocess)

Runs ansible-playbook from EDGESTREAM_TASK_DIR (so local ansible.cfg is used).

Job JSON (back/forward compatible):
- id: str (optional)                    -> used for status updates
- playbook: str (optional)              -> playbook file name or absolute path
- config: str (optional)                -> settings vars file name or absolute path
- inventory: str (optional)             -> inventory path
- extra_vars: dict (optional)           -> written to extra_vars.yml and passed via -e @file
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests

# -------------------------- Config / Env --------------------------
API_URL = os.environ.get("EDGESTREAM_API_URL", "http://127.0.0.1:3001/api/v1").rstrip("/")
API_TOKEN = os.environ.get("EDGESTREAM_QUEUE_TOKEN")

QUEUE_DIR = os.environ.get("EDGESTREAM_ANSIBLE_QUEUE", "/var/lib/edgestream/ansible-queue")
PRIVATE_DIR = os.environ.get("EDGESTREAM_RUNNER_PRIVATE", "/var/lib/edgestream/runner")
ARTIFACTS_DIR = os.path.join(PRIVATE_DIR, "artifacts")
DEFAULT_INVENTORY = os.path.join(PRIVATE_DIR, "inventory", "hosts.ini")

LOG_FILE = os.environ.get("EDGESTREAM_QUEUE_LOG", "/var/log/edgestream-api/queue-runner.log")
POLL_INTERVAL = float(os.environ.get("EDGESTREAM_QUEUE_POLL_SEC", "1.0"))

PROCESSED_DIR = os.path.join(QUEUE_DIR, "processed")
FAILED_DIR = os.path.join(QUEUE_DIR, "failed")

DEFAULT_USER = "cli_access@edgestream.local"
DEFAULT_SECRETS = "/etc/edgestream/edgestream-api.secrets"

LOGIN_PATH = "/auth/login"
LOGIN_REQUIRED_DEFAULT = False

DEFAULTS_FILE = os.environ.get("EDGESTREAM_DEFAULTS_FILE", "/etc/default/edgestream-api")

_running = True
_bearer: Optional[str] = None
_login_user: str = DEFAULT_USER
_secrets_path: str = DEFAULT_SECRETS
_no_login: bool = False

_RE_RECAP_KV = re.compile(r"(\w+)=([0-9]+)")

# -------------------------- Logging --------------------------
def _setup_logging() -> logging.Logger:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logger = logging.getLogger("ansible-queue")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    sh = logging.StreamHandler(stream=sys.stderr)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S%z")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

log = _setup_logging()

# -------------------------- Defaults file parsing --------------------------
def _read_env_file(path: str) -> dict[str, str]:
    """
    Parse /etc/default style KEY=VALUE file and ignores comments/blank lines.
    """
    out: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                # strip surrounding quotes
                if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                    v = v[1:-1]
                out[k] = v
    except FileNotFoundError:
        return out
    except Exception as e:
        log.warning("Could not parse defaults file %s: %s", path, e)
        return out
    return out

_DEFAULTS = _read_env_file(DEFAULTS_FILE)

def _cfg(key: str, fallback: str) -> str:
    # priority: real env > defaults file > fallback
    return os.environ.get(key) or _DEFAULTS.get(key) or fallback

PLAYBOOK_DIR = _cfg("EDGESTREAM_TASK_DIR", "/opt/edgestream-core/playbooks/")
DEFAULT_PLAYBOOK = _cfg("EDGESTREAM_TASK", "configure.yml")

SETTINGS_DIR = _cfg("EDGESTREAM_CONFIGURATION_DIR", "/var/lib/edgestream/export/")
SETTINGS_FILE = _cfg("EDGESTREAM_CONFIGURATION", "settings.yml")

# -------------------------- Paths / FS --------------------------
def _ensure_paths() -> None:
    for p in (QUEUE_DIR, PRIVATE_DIR, ARTIFACTS_DIR, os.path.dirname(DEFAULT_INVENTORY), PROCESSED_DIR, FAILED_DIR):
        os.makedirs(p, exist_ok=True)

    if not os.path.exists(DEFAULT_INVENTORY):
        with open(DEFAULT_INVENTORY, "w", encoding="utf-8") as f:
            f.write("[local]\nlocalhost ansible_connection=local\n")

    home_dir = os.environ.setdefault("HOME", "/var/lib/edgestream/ansible-home")
    local_tmp = os.environ.setdefault("ANSIBLE_LOCAL_TEMP", os.path.join(PRIVATE_DIR, "tmp"))
    remote_tmp = os.environ.setdefault("ANSIBLE_REMOTE_TMP", local_tmp)
    for p in (home_dir, local_tmp, remote_tmp):
        try:
            os.makedirs(p, exist_ok=True)
        except Exception as e:
            log.warning("Could not create path %s: %s", p, e)

# -------------------------- Job helpers --------------------------
def _claim_job(path: str) -> Optional[str]:
    base, name = os.path.split(path)
    claimed = os.path.join(base, f".working.{name}")
    try:
        os.replace(path, claimed)
        return claimed
    except FileNotFoundError:
        return None
    except Exception as e:
        log.warning("Failed to claim %s: %s", path, e)
        return None

def _finalize_job(claimed_path: str, success: bool) -> None:
    target_dir = PROCESSED_DIR if success else FAILED_DIR
    name = os.path.basename(claimed_path).replace(".working.", "", 1)
    target = os.path.join(target_dir, name)
    try:
        os.replace(claimed_path, target)
    except Exception as e:
        log.warning("Failed to move %s -> %s: %s", claimed_path, target, e)
        try:
            os.remove(claimed_path)
        except Exception:
            pass

def _load_job(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("Invalid job JSON %s: %s", path, e)
        return None

def _resolve_inventory(job: dict) -> str:
    return job.get("inventory") or DEFAULT_INVENTORY

def _resolve_playbook(job: dict) -> str:
    """
    playbook can be:
      - absolute path
      - relative to PLAYBOOK_DIR
    """
    pb = job.get("playbook") or DEFAULT_PLAYBOOK
    if os.path.isabs(pb):
        return pb
    return os.path.join(PLAYBOOK_DIR, pb)

def _resolve_settings(job: dict) -> str:
    """
    config/settings can be:
      - absolute path
      - relative to SETTINGS_DIR
    """
    cfg = job.get("config") or SETTINGS_FILE
    if os.path.isabs(cfg):
        return cfg
    return os.path.join(SETTINGS_DIR, cfg)

def _write_extravars(job: dict, job_art_dir: str) -> Optional[str]:
    extra = job.get("extra_vars") or {}
    if not isinstance(extra, dict) or not extra:
        return None
    path = os.path.join(job_art_dir, "extra_vars.yml")
    import yaml  # present in env
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(extra, f, sort_keys=False)
    return path

# -------------------------- Auth helpers --------------------------
def _read_cli_auth_token(secrets_path: str) -> Optional[str]:
    env_tok = os.environ.get("CLI_AUTH_TOKEN")
    if env_tok:
        return env_tok.strip()
    try:
        with open(secrets_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.split("=", 1)[0].strip() == "CLI_AUTH_TOKEN":
                    val = line.split("=", 1)[1].strip().strip("'").strip('"')
                    if val:
                        return val
    except FileNotFoundError:
        return None
    except Exception:
        return None
    return None

def _login() -> Optional[str]:
    base = API_URL
    url = f"{base}{LOGIN_PATH}"
    pw = _read_cli_auth_token(_secrets_path)
    if not pw:
        if LOGIN_REQUIRED_DEFAULT and not API_TOKEN:
            log.error("Required CLI identity details missing (check env or %s) and no polling auth found.", _secrets_path)
        else:
            log.warning("CLI identity details not found in env or %s.", _secrets_path)
        return None

    s = requests.Session()

    try:
        r = s.post(url, data={"username": _login_user, "password": pw}, timeout=10)
        if r.status_code < 400:
            data = r.json()
            tok = data.get("access_token") or data.get("token")
            if tok:
                return tok
    except Exception as e:
        log.warning("Login (form) error: %s", e)

    try:
        r = s.post(url, json={"username": _login_user, "password": pw}, timeout=10)
        if r.status_code < 400:
            data = r.json()
            tok = data.get("access_token") or data.get("token")
            if tok:
                return tok
    except Exception as e:
        log.warning("Login (json username) error: %s", e)

    try:
        r = s.post(url, json={"email": _login_user, "password": pw}, timeout=10)
        if r.status_code < 400:
            data = r.json()
            tok = data.get("access_token") or data.get("token")
            if tok:
                return tok
        else:
            log.error("Login failed (%s): %s", r.status_code, r.text[:300])
    except Exception as e:
        log.error("Login (json email) error: %s", e)

    return None

def _auth_header() -> Dict[str, str]:
    token = API_TOKEN or _bearer
    return {"Authorization": f"Bearer {token}"} if token else {}

def _post_update(job_id: str, payload: Dict[str, Any]) -> None:
    url = f"{API_URL}/task_status/id/{job_id}/update"
    headers = _auth_header()
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 401 and not API_TOKEN and not _no_login:
            global _bearer
            new_tok = _login()
            if new_tok:
                _bearer = new_tok
                headers = _auth_header()
                r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code >= 400:
            raise requests.HTTPError(f"{r.status_code} {r.text[:300]}")
    except Exception as e:
        log.warning("Failed to post status update for %s: %s", job_id, e)

def _parse_ansible_counts_from_log(log_path: str) -> dict[str, int]:
    counts = {"processed": 0, "skipped": 0, "failed": 0}
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        log.warning("Could not read ansible log %s: %s", log_path, e)
        return counts

    saw_recap = False
    for line in reversed(lines):
        line = line.rstrip("\n")
        if not line.strip():
            continue

        if not saw_recap:
            if "PLAY RECAP" in line:
                saw_recap = True
            continue

        if ":" not in line:
            continue

        _, _, tail = line.partition(":")
        kv_counts = dict(_RE_RECAP_KV.findall(tail))

        try:
            ok = int(kv_counts.get("ok", 0))
            changed = int(kv_counts.get("changed", 0))
            skipped = int(kv_counts.get("skipped", 0))
            failed = int(kv_counts.get("failed", 0))
        except ValueError:
            log.warning("Failed to parse recap numbers from line: %s", line)
            return counts

        counts["processed"] = ok + changed
        counts["skipped"] = skipped
        counts["failed"] = failed
        return counts

    log.info("No PLAY RECAP found in %s; leaving counts at 0", log_path)
    return counts

# -------------------------- Runner --------------------------
def _run_task(job: dict) -> int:
    job_id = job.get("id") or "no-id"
    playbook_path = _resolve_playbook(job)
    settings_path = _resolve_settings(job)
    inventory = _resolve_inventory(job)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job_art_dir = os.path.join(ARTIFACTS_DIR, f"{job_id}_{ts}")
    os.makedirs(job_art_dir, exist_ok=True)

    extravars_file = _write_extravars(job, job_art_dir)

    # Build ansible-playbook command
    cmd = ["ansible-playbook", playbook_path, "-i", inventory]

    if settings_path and os.path.exists(settings_path):
        cmd.extend(["-e", f"@{settings_path}"])
    else:
        log.warning("Settings file does not exist: %s", settings_path)

    if extravars_file:
        cmd.extend(["-e", f"@{extravars_file}"])

    if "ANSIBLE_ARGS" in os.environ and os.environ["ANSIBLE_ARGS"].strip():
        cmd.extend(shlex.split(os.environ["ANSIBLE_ARGS"]))

    env = os.environ.copy()

    # Ensure we run inside the playbooks directory so its ansible.cfg is used
    cwd = PLAYBOOK_DIR.rstrip("/")  # safe for join in logs

    cfg_path = os.path.join(cwd, "ansible.cfg")
    if os.path.exists(cfg_path):
        env["ANSIBLE_CONFIG"] = cfg_path

    run_log = os.path.join(job_art_dir, "run.log")
    with open(run_log, "wb") as logf:
        if job.get("id"):
            _post_update(job["id"], {
                "state": "running",
                "detail": f"playbook started: {os.path.basename(playbook_path)}"
            })

        proc = subprocess.Popen(
            cmd,
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=cwd,
        )
        rc = proc.wait()

    counts = _parse_ansible_counts_from_log(run_log)

    status_payload = {
        "state": "completed" if rc == 0 else "failed",
        "status": "success" if rc == 0 else "failed",
        "detail": f"playbook finished (rc={rc})",
        "completed": datetime.now(timezone.utc).isoformat(),
        "artifacts": {"dir": job_art_dir, "log": run_log},
        "processed": counts.get("processed", 0),
        "skipped": counts.get("skipped", 0),
        "failed": counts.get("failed", 0),
    }
    if job.get("id"):
        _post_update(job["id"], status_payload)

    return int(rc)

# -------------------------- Signals / Main --------------------------
def _handle_signal(signum, frame):  # noqa: ARG001
    global _running
    _running = False
    log.info("Received signal %s, shutting down...", signum)

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="EdgeStream Ansible Queue Runner")
    p.add_argument("--user", default=DEFAULT_USER, help=f"Login username (default: {DEFAULT_USER})")
    p.add_argument("--secrets", default=DEFAULT_SECRETS, help=f"Secrets file path (default: {DEFAULT_SECRETS})")
    p.add_argument("--no-login", action="store_true", help="Do NOT perform login flow (use EDGESTREAM_QUEUE_TOKEN or anonymous)")
    return p.parse_args(argv)

def main() -> int:
    global _login_user, _secrets_path, _no_login, _bearer

    args = _parse_args(sys.argv[1:])
    _login_user = args.user
    _secrets_path = args.secrets
    _no_login = args.no_login

    # Validate ansible-playbook
    try:
        subprocess.run(["ansible-playbook", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception as e:
        log.error("ansible-playbook not available or not working: %s", e)
        return 1

    _ensure_paths()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    if not API_TOKEN and not _no_login:
        _bearer = _login()
        if LOGIN_REQUIRED_DEFAULT and not _bearer:
            log.error("Login required but failed; exiting.")
            return 1
        if _bearer:
            log.info("Login succeeded for %s", _login_user)
        else:
            log.warning("Proceeding without login token (updates may be unauthorized).")

    log.info(
        "Watching %s (poll=%.2fs), playbook_dir=%s, default_playbook=%s, settings=%s/%s, artifacts=%s",
        QUEUE_DIR, POLL_INTERVAL, PLAYBOOK_DIR, DEFAULT_PLAYBOOK, SETTINGS_DIR, SETTINGS_FILE, ARTIFACTS_DIR
    )

    while _running:
        try:
            for name in sorted(os.listdir(QUEUE_DIR)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(QUEUE_DIR, name)
                if not os.path.isfile(path) or name.startswith(".working."):
                    continue

                claimed = _claim_job(path)
                if not claimed:
                    continue

                job = _load_job(claimed)
                if not job:
                    _finalize_job(claimed, success=False)
                    continue

                rc = 1
                try:
                    rc = _run_task(job)
                except Exception as e:
                    log.warning("Runner error for %s: %s", claimed, e)
                finally:
                    _finalize_job(claimed, success=(rc == 0))

            time.sleep(POLL_INTERVAL)
        except Exception as loop_err:
            log.warning("Loop error: %s", loop_err)
            time.sleep(2.0)

    log.info("Exited.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
