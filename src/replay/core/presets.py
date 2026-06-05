"""Benchmark preset loader for common low-cost IoT replay-defense scenarios."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

import yaml

from replay.contracts import SimulationSpec
from replay.core.types import Mode

ChannelModelName = Literal["iid", "gilbert_elliott", "trace"]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _preset_path(name: str) -> Path:
    candidate = Path(name)
    if candidate.suffix in {".yaml", ".yml"}:
        if candidate.is_absolute():
            return candidate
        cwd_candidate = Path.cwd() / candidate
        return cwd_candidate if cwd_candidate.exists() else _project_root() / candidate

    cwd_preset = Path.cwd() / "presets" / f"{name}.yaml"
    if cwd_preset.exists():
        return cwd_preset
    return _project_root() / "presets" / f"{name}.yaml"


def load_preset(name: str) -> SimulationSpec:
    """Load a YAML device preset and convert it to the public simulation spec."""

    path = _preset_path(name)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid preset payload: {path}")
    return spec_from_preset_payload(payload)


def spec_from_preset_payload(payload: dict[str, Any]) -> SimulationSpec:
    commands = list(payload.get("commands") or [])
    risk = dict(payload.get("risk") or {})
    channel = dict(payload.get("channel") or {})
    defense = dict(payload.get("defense") or {})
    mode = Mode(defense.get("mode", "window"))
    channel_model = cast(ChannelModelName, str(channel.get("model", "iid")))

    return SimulationSpec(
        modes=[mode],
        command_set=commands or None,
        command_risk={str(key): float(value) for key, value in risk.items()} or None,
        target_commands=list(defense.get("challenge_for") or []) or None,
        channel_model=channel_model,
        loss_good=float(channel.get("loss_good", 0.01)),
        loss_bad=float(channel.get("loss_bad", 0.60)),
        burst_p_good_to_bad=float(channel.get("p_good_to_bad", 0.05)),
        burst_p_bad_to_good=float(channel.get("p_bad_to_good", 0.30)),
        window_size=int(defense.get("window_size", 5)),
        mac_tag_bits=int(defense.get("mac_tag_bits", 80)),
        paired=True,
    )
