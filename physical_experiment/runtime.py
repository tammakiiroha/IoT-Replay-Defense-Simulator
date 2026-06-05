"""Shared runtime helpers for physical experiment scripts."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "physical_experiment" / "configs" / "experiment_config.yaml"


def resolve_config_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve a config path against the project root."""
    if config_path is None:
        return DEFAULT_CONFIG_PATH

    path = Path(config_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def load_experiment_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load the physical experiment YAML config."""
    resolved = resolve_config_path(config_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {resolved}")

    with open(resolved, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve_output_path(config: Mapping[str, Any], key: str, default: str) -> Path:
    """Resolve configured output paths relative to the project root."""
    output_config = config.get("output", {})
    raw_value = output_config.get(key, default)
    path = Path(raw_value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def build_hackrf_device_args(device_args: str = "", serial: Optional[str] = None) -> str:
    """Compose an osmosdr device-args string."""
    parts = []
    if serial:
        parts.append(f"hackrf={serial}")
    if device_args:
        parts.append(device_args.strip())
    return " ".join(part for part in parts if part).strip()


def resolve_hackrf_device_args(
    config: Mapping[str, Any],
    role: str,
    *,
    device_args_override: str = "",
    serial_override: str = "",
) -> str:
    """Resolve HackRF device args from config with CLI overrides."""
    hardware_config = config.get("hardware", {})
    role_config = hardware_config.get(role, {})

    serial = serial_override or role_config.get("device_serial") or ""
    device_args = device_args_override or role_config.get("device_args") or ""
    return build_hackrf_device_args(device_args=device_args, serial=serial)


def save_runtime_config(config: Mapping[str, Any], output_path: Union[str, Path]) -> Path:
    """Persist the resolved runtime config used by orchestrators."""
    path = Path(output_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(dict(config), fh, allow_unicode=True, sort_keys=False)
    return path
