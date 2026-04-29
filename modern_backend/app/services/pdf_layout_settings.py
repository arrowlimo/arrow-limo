"""PDF layout settings loader/saver for run charter templates."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def _settings_file_path() -> Path:
    # Repo root is three levels up from modern_backend/app/services/
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "config" / "pdf_layout_settings.json"


def default_pdf_layout_settings() -> dict[str, Any]:
    return {
        "summary_client": {
            "left_width_in": 4.05,
            "gap_in": 0.12,
            "summary_font_size": 7.8,
            "client_name_font_size": 9.5,
            "client_min_height": 90,
        },
        "routing": {
            "left_width_in": 4.55,
            "gap_in": 0.12,
            "row_height": 15,
            "font_size": 6.8,
            "time_font_size": 7.8,
            "time_bold": True,
        },
        "invoicing": {
            "min_charge_rows": 4,
            "row_height": 15,
            "font_size": 7,
            "numeric_col_min_in": 0.68,
            "numeric_col_pref_in": 0.80,
            "label_padding": 10,
            "first_col_align": "RIGHT",
            "second_col_align": "CENTER",
            "third_col_align": "CENTER",
            "center_header": True,
        },
        "driver_vehicle": {
            "box_height_in": 4.6,
            "font_size": 7.9,
            "line_height": 26.0,
            "rule_font_size": 6.4,
        },
    }


def _deep_merge(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_pdf_layout_settings() -> dict[str, Any]:
    defaults = default_pdf_layout_settings()
    path = _settings_file_path()
    if not path.exists():
        return defaults

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return defaults
        return _deep_merge(defaults, raw)
    except Exception:
        return defaults


def save_pdf_layout_settings(settings_patch: dict[str, Any]) -> dict[str, Any]:
    path = _settings_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    merged = _deep_merge(load_pdf_layout_settings(), settings_patch or {})
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def reset_pdf_layout_settings() -> dict[str, Any]:
    defaults = default_pdf_layout_settings()
    path = _settings_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
    return defaults


def pdf_layout_settings_schema() -> dict[str, Any]:
    return {
        "summary_client": {
            "left_width_in": {
                "type": "number",
                "min": 3.4,
                "max": 4.9,
                "step": 0.01,
            },
            "gap_in": {
                "type": "number",
                "min": 0.05,
                "max": 0.4,
                "step": 0.01,
            },
            "summary_font_size": {
                "type": "number",
                "min": 6.5,
                "max": 10.5,
                "step": 0.1,
            },
            "client_name_font_size": {
                "type": "number",
                "min": 8.0,
                "max": 14.0,
                "step": 0.1,
            },
            "client_min_height": {
                "type": "number",
                "min": 70,
                "max": 140,
                "step": 1,
            },
        },
        "routing": {
            "left_width_in": {
                "type": "number",
                "min": 3.8,
                "max": 5.3,
                "step": 0.01,
            },
            "gap_in": {
                "type": "number",
                "min": 0.05,
                "max": 0.4,
                "step": 0.01,
            },
            "row_height": {"type": "number", "min": 12, "max": 22, "step": 1},
            "font_size": {
                "type": "number",
                "min": 6.0,
                "max": 10.0,
                "step": 0.1,
            },
            "time_font_size": {
                "type": "number",
                "min": 6.0,
                "max": 11.0,
                "step": 0.1,
            },
            "time_bold": {"type": "boolean"},
        },
        "invoicing": {
            "min_charge_rows": {
                "type": "number",
                "min": 1,
                "max": 12,
                "step": 1,
            },
            "row_height": {"type": "number", "min": 12, "max": 22, "step": 1},
            "font_size": {
                "type": "number",
                "min": 6.0,
                "max": 10.0,
                "step": 0.1,
            },
            "numeric_col_min_in": {
                "type": "number",
                "min": 0.45,
                "max": 1.2,
                "step": 0.01,
            },
            "numeric_col_pref_in": {
                "type": "number",
                "min": 0.45,
                "max": 1.4,
                "step": 0.01,
            },
            "label_padding": {
                "type": "number",
                "min": 2,
                "max": 20,
                "step": 1,
            },
            "first_col_align": {
                "type": "enum",
                "values": ["LEFT", "CENTER", "RIGHT"],
            },
            "second_col_align": {
                "type": "enum",
                "values": ["LEFT", "CENTER", "RIGHT"],
            },
            "third_col_align": {
                "type": "enum",
                "values": ["LEFT", "CENTER", "RIGHT"],
            },
            "center_header": {"type": "boolean"},
        },
        "driver_vehicle": {
            "box_height_in": {
                "type": "number",
                "min": 1.7,
                "max": 3.2,
                "step": 0.01,
            },
            "font_size": {
                "type": "number",
                "min": 6.6,
                "max": 10.5,
                "step": 0.1,
            },
            "line_height": {
                "type": "number",
                "min": 10.0,
                "max": 18.0,
                "step": 0.1,
            },
            "rule_font_size": {
                "type": "number",
                "min": 5.5,
                "max": 8.5,
                "step": 0.1,
            },
        },
    }


def apply_pdf_layout_preset(name: str) -> dict[str, Any]:
    normalized = (name or "").strip().lower()
    defaults = default_pdf_layout_settings()
    presets: dict[str, dict[str, Any]] = {
        "compact": {
            "summary_client": {
                "summary_font_size": 7.2,
                "client_name_font_size": 9.0,
                "client_min_height": 84,
            },
            "routing": {
                "row_height": 14,
                "font_size": 6.6,
                "time_font_size": 7.2,
            },
            "invoicing": {
                "row_height": 14,
                "font_size": 6.8,
                "label_padding": 8,
                "min_charge_rows": 3,
            },
            "driver_vehicle": {
                "box_height_in": 2.2,
                "font_size": 7.6,
                "line_height": 12.6,
                "rule_font_size": 6.2,
            },
        },
        "comfortable": {
            "summary_client": {
                "summary_font_size": 8.2,
                "client_name_font_size": 10.0,
                "client_min_height": 96,
            },
            "routing": {
                "row_height": 16,
                "font_size": 7.0,
                "time_font_size": 8.2,
            },
            "invoicing": {
                "row_height": 16,
                "font_size": 7.2,
                "label_padding": 12,
                "min_charge_rows": 4,
            },
            "driver_vehicle": {
                "box_height_in": 2.55,
                "font_size": 8.1,
                "line_height": 14.0,
                "rule_font_size": 6.6,
            },
        },
        "default": defaults,
    }
    if normalized not in presets:
        raise ValueError(f"Unknown preset '{name}'")
    merged = _deep_merge(defaults, presets[normalized])
    return save_pdf_layout_settings(merged)
