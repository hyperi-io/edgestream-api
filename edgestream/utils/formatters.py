"""
Project:   edgestream-api
File:      edgestream/utils/formatters.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
import json
import copy
from typing import Any
from pydantic import TypeAdapter
from edgestream.core.config import Logger, settings
from edgestream.services.port_manager import get_settings_value


def load_dynamic_templates(category: str):
    """
    category: 'source' or 'destination'
    """
    templates = []
    # Tier 1: Core (Package Managed)
    core_dir = os.path.join(settings.EDGESTREAM_TEMPLATE_CORE_BASE_PATH, category)
    # Tier 2: Contrib (User Managed)
    contrib_dir = os.path.join(settings.EDGESTREAM_TEMPLATE_CONTRIB_BASE_PATH, category, "contrib")

    def safe_load(file_path, is_core=False):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    # Inject a source flag so the UI knows which are 'System' templates
                    item["_managed_by"] = "package" if is_core else "user"
                    templates.append(item)
        except (json.JSONDecodeError, OSError) as e:
            Logger.logger.warning(f"Skipping template {file_path}: {e}")

    # Load Core
    if os.path.exists(core_dir):
        for f in os.listdir(core_dir):
            if f.endswith(".json"):
                safe_load(os.path.join(core_dir, f), is_core=True)

    # Load Contrib
    if os.path.exists(contrib_dir):
        for f in os.listdir(contrib_dir):
            if f.endswith(".json"):
                safe_load(os.path.join(contrib_dir, f), is_core=False)

    return templates


def get_formatted_entity(entity_input: Any, category: str) -> Any:
    """
    General formatter for Sources and Destinations.
    Handles both Schema objects (.settings) and Model objects (.parameters).
    """
    all_templates = load_dynamic_templates(category)

    template = next((t for t in all_templates if t["type"] == entity_input.type), None)
    if not template:
        Logger.logger.error(f"Template '{entity_input.type}' not found for {category}")
        return None

    entity_settings = getattr(entity_input, "settings", None) or getattr(entity_input, "parameters", [])

    out = copy.deepcopy(template)
    out["name"] = entity_input.name
    out["enabled"] = entity_input.enabled
    out["system"] = entity_input.system

    out["description"] = get_settings_value("description", entity_settings) or ""

    if category == "destination":
        out["fallback"] = getattr(entity_input, "fallback", False)
        out["routes"] = list({r.label for r in (getattr(entity_input, "routes", []) or [])})

    type_mapping = {"string": str, "integer": int, "float": float, "bool": bool, "boolean": bool}

    for setting in (entity_settings or []):
        for section in ["base", "tls", "optional"]:
            sect = out.get("settings", {}).get(section, {})
            field = sect.get(setting.key)
            if not field:
                continue

            cast = (field.get("cast") or "string").lower()
            caster = type_mapping.get(cast, str)

            try:
                field["value"] = TypeAdapter(caster).validate_python(setting.value)
            except Exception as e:
                Logger.logger.warning(f"Cast fail for {setting.key} in {entity_input.name}: {e}")
                field["value"] = setting.value

    return out
