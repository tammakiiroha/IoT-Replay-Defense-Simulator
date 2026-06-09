"""Attacker control fields flow through the contract surface (Phase 5 P5).

Contract sync only: attacker_strategy / attacker_position / attacker_inject_strength
must traverse SimulationSpec -> to_runtime_config -> SimulationSpecPublic -> TS/JSON
-> static fallback / web DEFAULT_SPEC. Attribution semantics are untouched.
"""
from pathlib import Path

from replay.contracts.models import SimulationSpec, SimulationSpecPublic
from replay.contracts.typescript import render_typescript_contracts

_ATTACKER_FIELDS = ("attacker_position", "attacker_inject_strength", "attacker_strategy")


def test_simulation_spec_attacker_fields_round_trip_to_config():
    spec = SimulationSpec(
        attacker_position="rx",
        attacker_inject_strength="weak",
        attacker_strategy="adaptive_lostframe",
    )
    cfg = spec.to_runtime_config()
    assert cfg.attacker_position == "rx"
    assert cfg.attacker_inject_strength == "weak"
    assert cfg.attacker_strategy == "adaptive_lostframe"
    # defaults preserve legacy behaviour
    default = SimulationSpec()
    assert default.attacker_position == "ind"
    assert default.attacker_inject_strength == "strong"
    assert default.attacker_strategy == "random"


def test_public_spec_includes_attacker_fields():
    spec = SimulationSpec(
        attacker_position="tx",
        attacker_inject_strength="weak",
        attacker_strategy="adaptive_resync",
    )
    public = SimulationSpecPublic.from_spec(spec)
    assert public.attacker_position == "tx"
    assert public.attacker_inject_strength == "weak"
    assert public.attacker_strategy == "adaptive_resync"
    dumped = public.model_dump()
    assert "shared_key" not in dumped  # still secret-free
    for field in _ATTACKER_FIELDS:
        assert field in dumped


def test_typescript_contract_includes_attacker_fields():
    ts = render_typescript_contracts()
    for field in _ATTACKER_FIELDS:
        assert field in ts, f"contracts TS missing {field}"
    assert "AttackerPosition" in ts
    assert "AttackerStrength" in ts
    assert "AttackerStrategy" in ts


def test_static_simulator_default_spec_has_attacker_fields():
    panel = Path("web/components/simulator-panel.tsx").read_text(encoding="utf-8")
    static_sim = Path("web/lib/static-simulator.ts").read_text(encoding="utf-8")
    for field in _ATTACKER_FIELDS:
        assert field in panel, f"web DEFAULT_SPEC missing {field}"
        assert field in static_sim, f"static-simulator missing {field}"
