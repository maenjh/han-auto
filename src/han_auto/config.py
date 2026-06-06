"""Template configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError
import yaml

from han_auto.exceptions import TemplateConfigError
from han_auto.models import TemplateConfig


def load_template_config(path: str | Path) -> TemplateConfig:
    """Load and validate a template YAML file."""

    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise TemplateConfigError(f"Template config not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise TemplateConfigError(f"Invalid template config YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise TemplateConfigError(f"Template config must be a mapping: {config_path}")

    data: dict[str, Any] = dict(raw)
    if "template_path" in data:
        template_path = Path(data["template_path"])
        if not template_path.is_absolute():
            data["template_path"] = (config_path.parent / template_path).resolve()

    try:
        return TemplateConfig.model_validate(data)
    except ValidationError as exc:
        raise TemplateConfigError(f"Invalid template config in {config_path}: {exc}") from exc
