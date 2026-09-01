"""
Project:   edgestream-api
File:      edgestream/services/port_manager.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from fastapi import HTTPException

from edgestream import crud
from edgestream.core.config import settings


def find_mode(items):
    for item in (items or []):
        try:
            if item.key == "mode":
                return item.value
        except Exception:
            pass
    return None


def extract_port(address):
    if address and ":" in address:
        try:
            return int(address.split(":")[1])
        except Exception:
            return None
    return None


def find_port(items):
    for item in (items or []):
        try:
            if item.key == "port":
                return int(item.value)
            if item.key == "address":
                return extract_port(item.value)
        except (ValueError, TypeError, Exception):
            pass
    return None


def port_in_use(db, port: int, protocol: str = None):
    try:
        if port in settings.RESERVED_PORTS:
            return {"inuse": True, "service": "System Reserved Port"}

        if protocol is None or protocol.lower() == "tcp":
            advanced_services = [
                "system.ssh.listen_port",
                "dashboard.remote.listen_port",
            ]
            for service in advanced_services:
                advanced_setting = crud.advanced_setting.get(db=db, label=service)
                if advanced_setting is not None:
                    if len(advanced_setting.value) > 0 and int(advanced_setting.value) == port:
                        return {"inuse": True, "service": advanced_setting.label}
                    elif len(advanced_setting.default_value) > 0 and int(advanced_setting.default_value) == port:
                        return {"inuse": True, "service": advanced_setting.label}

        sources = crud.source.get_all_sources_full(db=db)
        for source in sources:
            source_settings = getattr(source, "settings", None) or getattr(source, "parameters", [])

            mode = find_mode(source_settings)
            source_port = find_port(source_settings)

            if protocol is None or mode is None or protocol.lower() == mode:
                if source_port is not None and int(source_port) == int(port):
                    return {"inuse": True, "service": source.name}

        return {"inuse": False, "service": None}
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to determine if port in use {error}.",
        )


def get_settings_value(key, settings):
    for setting in (settings or []):
        try:
            if setting.key == key:
                return setting.value
        except AttributeError:
            pass
    return None
