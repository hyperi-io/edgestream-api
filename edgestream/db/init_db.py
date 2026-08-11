from __future__ import annotations

import os
from pathlib import Path
from filelock import FileLock
from sqlalchemy import select, delete, func, inspect
from sqlalchemy.exc import IntegrityError

from edgestream.core.config import settings, Logger
from edgestream.db.session import Base, engine, SessionLocal
from edgestream.services.auth.security import hash_password

# --- Essential: Import all models to register them with Base.metadata ---
from edgestream.models.event.destination import Destination, DestinationParameter, DestinationRoute
from edgestream.models.event.source import Source, SourceParameter
from edgestream.models.event.transform import Transform
from edgestream.models.network.dns_client import DNS
from edgestream.models.network.dns_forwarder import DNSForwarder
from edgestream.models.network.ip_management import IPManagement
from edgestream.models.network.ntp_client import NTP
from edgestream.models.network.static_host import StaticHost
from edgestream.models.network.static_route import StaticRoute
from edgestream.models.network.vpn_client import VPNConfig
from edgestream.models.system.advanced_setting import AdvancedSetting
from edgestream.models.system.audit import AuditEvent
from edgestream.models.system.backup import Backup
from edgestream.models.system.certificate_store import Certificate
from edgestream.models.system.log_viewer import LogViewer
from edgestream.models.system.system import System
from edgestream.models.system.user import User

from edgestream.models.system.task import Task


def _lock_path_for_engine() -> str:
    # Force lockfile into /tmp to avoid permission denied errors in /opt
    return "/tmp/edgestreamhub.db.init.lock"


def init_db() -> None:
    """
    Hardened Database Initialization.
    Ensures schema creation is isolated from data seeding to prevent SQLite lock contention.
    """
    lock_file = _lock_path_for_engine()
    Path(os.path.dirname(lock_file) or ".").mkdir(parents=True, exist_ok=True)

    with FileLock(lock_file, timeout=120):
        registered_tables = list(Base.metadata.tables.keys())
        Logger.logger.info(f"Synchronizing schema for: {', '.join(registered_tables)}")

        Base.metadata.create_all(bind=engine)

        inspector = inspect(engine)
        physical_tables = inspector.get_table_names()
        Logger.logger.debug(f"Physical tables confirmed: {physical_tables}")

        with SessionLocal() as db:
            try:
                # Seed Admin
                admin_email = settings.EDGESTREAM_DEFAULT_ADMIN_EMAIL.lower()
                if not db.execute(select(User).where(User.email == admin_email)).scalar_one_or_none():
                    Logger.logger.info(f"Seeding default admin: {admin_email}")
                    db.add(User(
                        full_name=settings.EDGESTREAM_DEFAULT_ADMIN_FULL_NAME,
                        email=admin_email,
                        is_superuser=True,
                        is_approved=True,
                        hashed_password=hash_password(settings.EDGESTREAM_DEFAULT_ADMIN_PASSWORD),
                    ))

                if db.execute(select(func.count(System.id))).scalar() == 0:
                    db.add(System())

                advanced_settings_defaults = [
                    {'label': 'webui.enabled', 'value': 'True',
                     'description': 'Enable remote access to admin webui', 'default_value': 'True'},
                    {'label': 'webui.listen_port', 'value': '443', 'description': 'Admin webui listen port',
                     'default_value': '443'},
                    {'label': 'apt.repository.url', 'value': 'https://apt.repo.hyperi.io/edgestream/testing',
                     'description': 'EdgeStream Hub APT Repository URL',
                     'default_value': 'https://apt.repo.hyperi.io/edgestream/testing'},
                    {'label': 'apt.repository.release', 'value': 'trixie',
                     'description': 'EdgeStream Hub APT Repository Release', 'default_value': 'trixie'},
                    {'label': 'apt.repository.branch', 'value': 'main',
                     'description': 'EdgeStream Hub APT Repository Branch', 'default_value': 'main'},
                    {'label': 'apt.repository.key', 'value': '',
                     'description': 'EdgeStream Hub APT Repository Key File', 'default_value': ''},
                    {'label': 'apt.repository.proxy', 'value': '', 'description': 'APT Proxy URL',
                     'default_value': ''},
                    {'label': 'ssh.listen_port', 'value': '22',
                     'description': 'Local EdgeStream Hub port to listen on for OpenSSH Server', 'default_value': '22'},
                    {'label': 'ssh.password_authentication', 'value': 'True',
                     'description': 'Permit password authentication for SSH access', 'default_value': 'True'},
                    {'label': 'ssh.google_auth', 'value': 'False',
                     'description': 'Require google authentication for SSH access', 'default_value': 'False'},
                    {'label': 'webui.chart.threshold', 'value': '2G',
                     'description': 'Maximum overview webui database usage before purging old entries', 'default_value': '2G'},
                    {'label': 'destination.multiplex', 'value': '1',
                     'description': 'Load balance each destination across 1-4 instances (can improve throughput)',
                     'default_value': '1'},
                ]
                for item in advanced_settings_defaults:
                    if not db.execute(select(AdvancedSetting).where(AdvancedSetting.label == item["label"])).scalar():
                        db.add(AdvancedSetting(**item))

                log_defaults = [
                    "/var/log/syslog",
                    "/var/log/auth.log",
                    "/var/log/edgestream-api/access.log",
                    "/var/log/edgestream-api/error.log",
                    "/var/log/edgestream-api/queue-runner.log"
                ]
                for fn in log_defaults:
                    if not db.execute(select(LogViewer).where(LogViewer.filename == fn)).scalar():
                        db.add(LogViewer(filename=fn))

                db.commit()
                Logger.logger.info("Core seeding complete.")

            except Exception as e:
                db.rollback()
                Logger.logger.error(f"Seeding failed: {e}")
                raise

        if "tasks" in physical_tables:
            with SessionLocal() as housekeeping_db:
                try:
                    housekeeping_db.execute(delete(Task))
                    housekeeping_db.commit()
                    Logger.logger.info("Cleaned transient task records.")
                except Exception as e:
                    housekeeping_db.rollback()
                    Logger.logger.warning(f"Housekeeping deferred: {e}")
