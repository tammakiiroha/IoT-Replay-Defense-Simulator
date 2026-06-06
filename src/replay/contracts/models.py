"""Typed API and artifact contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from replay.core import (
    DEFAULT_ATTACK_MODE,
    DEFAULT_ATTACKER_RECORD_LOSS,
    DEFAULT_CHALLENGE_NONCE_BITS,
    DEFAULT_COMMANDS,
    DEFAULT_G_HARD,
    DEFAULT_INLINE_ATTACK_BURST,
    DEFAULT_INLINE_ATTACK_PROBABILITY,
    DEFAULT_MAC_LENGTH,
    DEFAULT_MAC_TAG_BITS,
    DEFAULT_NUM_LEGIT,
    DEFAULT_NUM_REPLAY,
    DEFAULT_P_LOSS,
    DEFAULT_P_REORDER,
    DEFAULT_RUNS,
    DEFAULT_SHARED_KEY,
    DEFAULT_WINDOW_SIZE,
    WINDOW_SIZED_MODES,
    AggregateStats,
    AttackMode,
    Mode,
    SimulationConfig,
)

SCHEMA_VERSION = "2026-03-16"
SchemaVersion = Literal["2026-03-16"]
MAX_WORK_UNITS = 2_000_000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReplayBaseModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class SimulationSpec(ReplayBaseModel):
    schema_version: SchemaVersion = "2026-03-16"
    modes: list[Mode] = Field(default_factory=lambda: list(Mode))
    runs: int = Field(default=DEFAULT_RUNS, ge=1, le=10_000)
    seed: int | None = Field(default=None, ge=0)
    p_loss: float = Field(default=DEFAULT_P_LOSS, ge=0.0, le=1.0)
    p_reorder: float = Field(default=DEFAULT_P_REORDER, ge=0.0, le=1.0)
    window_size: int = Field(default=DEFAULT_WINDOW_SIZE, ge=0)
    g_hard: int = Field(default=DEFAULT_G_HARD, ge=0)
    num_legit: int = Field(default=DEFAULT_NUM_LEGIT, ge=0, le=10_000)
    num_replay: int = Field(default=DEFAULT_NUM_REPLAY, ge=0, le=10_000)
    attack_mode: AttackMode = DEFAULT_ATTACK_MODE
    mac_length: int = Field(default=DEFAULT_MAC_LENGTH, ge=1)
    mac_tag_bits: int = Field(default=DEFAULT_MAC_TAG_BITS, ge=32, le=256)
    shared_key: str = Field(default=DEFAULT_SHARED_KEY, min_length=1)
    attacker_record_loss: float = Field(
        default=DEFAULT_ATTACKER_RECORD_LOSS,
        ge=0.0,
        le=1.0,
    )
    inline_attack_probability: float = Field(
        default=DEFAULT_INLINE_ATTACK_PROBABILITY,
        ge=0.0,
        le=1.0,
    )
    inline_attack_burst: int = Field(default=DEFAULT_INLINE_ATTACK_BURST, ge=1)
    challenge_nonce_bits: int = Field(default=DEFAULT_CHALLENGE_NONCE_BITS, ge=1)
    target_commands: list[str] | None = None
    command_sequence: list[str] | None = None
    command_set: list[str] | None = Field(default_factory=lambda: list(DEFAULT_COMMANDS))
    target_ci_half_width: float | None = Field(default=None, gt=0.0, le=1.0)
    max_runs: int = Field(default=2000, ge=1, le=20_000)
    paired: bool = False
    channel_model: Literal["iid", "gilbert_elliott", "trace"] = "iid"
    burst_p_good_to_bad: float = Field(default=0.05, ge=0.0, le=1.0)
    burst_p_bad_to_good: float = Field(default=0.30, ge=0.0, le=1.0)
    loss_good: float = Field(default=0.01, ge=0.0, le=1.0)
    loss_bad: float = Field(default=0.60, ge=0.0, le=1.0)
    loss_trace: list[bool] | None = None
    command_risk: dict[str, float] | None = None
    risk_high: float = Field(default=0.8, ge=0.0, le=1.0)
    auth_profile: Literal["hmac", "ascon"] = "hmac"

    @model_validator(mode="after")
    def _validate_window_size(self) -> SimulationSpec:
        if any(Mode(mode) in WINDOW_SIZED_MODES for mode in self.modes) and self.window_size <= 0:
            raise ValueError("window_size must be >= 1 when window mode is enabled")
        run_bound = (
            max(self.runs, self.max_runs)
            if self.target_ci_half_width is not None
            else self.runs
        )
        work_units = run_bound * max(1, len(self.modes)) * (self.num_legit + self.num_replay)
        if work_units > MAX_WORK_UNITS:
            raise ValueError(f"simulation too large: work_units={work_units} > {MAX_WORK_UNITS}")
        return self

    def to_runtime_config(self) -> SimulationConfig:
        return SimulationConfig(
            mode=Mode.NO_DEFENSE,
            attack_mode=AttackMode(self.attack_mode),
            num_legit=self.num_legit,
            num_replay=self.num_replay,
            p_loss=self.p_loss,
            p_reorder=self.p_reorder,
            window_size=self.window_size,
            g_hard=self.g_hard,
            command_sequence=self.command_sequence,
            command_set=self.command_set,
            target_commands=self.target_commands,
            rng_seed=self.seed,
            mac_length=self.mac_length,
            mac_tag_bits=self.mac_tag_bits,
            shared_key=self.shared_key,
            attacker_record_loss=self.attacker_record_loss,
            inline_attack_probability=self.inline_attack_probability,
            inline_attack_burst=self.inline_attack_burst,
            challenge_nonce_bits=self.challenge_nonce_bits,
            channel_model=self.channel_model,
            burst_p_good_to_bad=self.burst_p_good_to_bad,
            burst_p_bad_to_good=self.burst_p_bad_to_good,
            loss_good=self.loss_good,
            loss_bad=self.loss_bad,
            loss_trace=self.loss_trace,
            paired=self.paired,
            target_ci_half_width=self.target_ci_half_width,
            max_runs=self.max_runs,
            command_risk=self.command_risk,
            risk_high=self.risk_high,
            auth_profile=self.auth_profile,
        )


class SimulationSpecPublic(ReplayBaseModel):
    """Public, secret-free view of a SimulationSpec for API/Web responses."""

    schema_version: SchemaVersion = "2026-03-16"
    modes: list[Mode]
    runs: int
    seed: int | None = None
    p_loss: float
    p_reorder: float
    window_size: int
    g_hard: int
    num_legit: int
    num_replay: int
    attack_mode: AttackMode
    mac_length: int
    mac_tag_bits: int
    attacker_record_loss: float
    inline_attack_probability: float
    inline_attack_burst: int
    challenge_nonce_bits: int
    target_commands: list[str] | None = None
    command_sequence: list[str] | None = None
    command_set: list[str] | None = None
    target_ci_half_width: float | None = None
    max_runs: int
    paired: bool
    channel_model: str
    burst_p_good_to_bad: float
    burst_p_bad_to_good: float
    loss_good: float
    loss_bad: float
    loss_trace: list[bool] | None = None
    command_risk: dict[str, float] | None = None
    risk_high: float
    auth_profile: str

    @classmethod
    def from_spec(cls, spec: SimulationSpec) -> SimulationSpecPublic:
        return cls.model_validate(spec.model_dump(exclude={"shared_key"}))


class SimulationResultRecord(ReplayBaseModel):
    mode: Mode
    runs: int
    avg_legit_rate: float
    std_legit_rate: float
    avg_attack_rate: float
    std_attack_rate: float
    p_loss: float
    p_reorder: float
    window_size: int
    num_legit: int
    num_replay: int
    attack_mode: AttackMode
    legit_accepted: int = 0
    legit_total: int = 0
    attack_accepted: int = 0
    attack_total: int = 0
    lar_ci_low: float = 0.0
    lar_ci_high: float = 0.0
    asr_ci_low: float = 0.0
    asr_ci_high: float = 0.0
    frr: float = 0.0
    energy_proxy: float = 0.0
    bytes_overhead: float = 0.0
    state_bytes: float = 0.0
    latency_ticks: float = 0.0
    crypto_ops: float = 0.0
    challenge_round_trips: float = 0.0
    mac_tag_bits: int = DEFAULT_MAC_TAG_BITS
    auth_profile: str = "hmac"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_aggregate(cls, entry: AggregateStats) -> SimulationResultRecord:
        metadata = dict(entry.metadata)
        return cls(
            mode=entry.mode,
            runs=entry.runs,
            avg_legit_rate=entry.avg_legit_rate,
            std_legit_rate=entry.std_legit_rate,
            avg_attack_rate=entry.avg_attack_rate,
            std_attack_rate=entry.std_attack_rate,
            p_loss=entry.p_loss,
            p_reorder=entry.p_reorder,
            window_size=entry.window_size,
            num_legit=entry.num_legit,
            num_replay=entry.num_replay,
            attack_mode=entry.attack_mode,
            legit_accepted=entry.legit_accepted,
            legit_total=entry.legit_total,
            attack_accepted=entry.attack_accepted,
            attack_total=entry.attack_total,
            lar_ci_low=entry.lar_ci_low,
            lar_ci_high=entry.lar_ci_high,
            asr_ci_low=entry.asr_ci_low,
            asr_ci_high=entry.asr_ci_high,
            frr=entry.frr,
            energy_proxy=entry.energy_proxy,
            bytes_overhead=entry.bytes_overhead,
            state_bytes=entry.state_bytes,
            latency_ticks=entry.latency_ticks,
            crypto_ops=entry.crypto_ops,
            challenge_round_trips=entry.challenge_round_trips,
            mac_tag_bits=entry.mac_tag_bits,
            auth_profile=entry.auth_profile,
            metadata=metadata,
        )


class SimulationBatchResult(ReplayBaseModel):
    schema_version: SchemaVersion = "2026-03-16"
    generated_at: datetime = Field(default_factory=_utc_now)
    config: SimulationSpecPublic
    results: list[SimulationResultRecord]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SweepSpec(ReplayBaseModel):
    schema_version: SchemaVersion = "2026-03-16"
    sweep_type: Literal["p_loss", "p_reorder", "window", "mac_tag_bits"]
    values: list[float | int]
    simulation: SimulationSpec
    fixed_p_loss: float | None = None
    fixed_p_reorder: float | None = None


class SweepPoint(ReplayBaseModel):
    sweep_type: str
    sweep_value: float | int
    result: SimulationResultRecord


class ArtifactSummary(ReplayBaseModel):
    artifact_id: str
    title: str
    kind: str
    path: str
    description: str | None = None
    updated_at: datetime = Field(default_factory=_utc_now)


class ExperimentArtifact(ReplayBaseModel):
    schema_version: SchemaVersion = "2026-03-16"
    artifact_id: str
    kind: str
    title: str
    description: str
    generated_at: datetime = Field(default_factory=_utc_now)
    source_path: str | None = None
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LabValidationSpec(ReplayBaseModel):
    schema_version: SchemaVersion = "2026-03-16"
    loopback: bool = True
    quick: bool = True
    loss_samples: list[float] = Field(default_factory=lambda: [0.0])
    goal_check: bool = True
    output_path: str | None = None
    extra_args: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=600, ge=1, le=7200)


class LabValidationArtifact(ReplayBaseModel):
    schema_version: SchemaVersion = "2026-03-16"
    artifact_id: str
    title: str
    generated_at: datetime = Field(default_factory=_utc_now)
    source_path: str
    summary: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    results: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimVsHardwareArtifact(LabValidationArtifact):
    title: str = "Simulation vs Hardware Validation"


class ArtifactManifest(ReplayBaseModel):
    schema_version: SchemaVersion = "2026-03-16"
    generated_at: datetime = Field(default_factory=_utc_now)
    title: str
    description: str
    runtime_mode: Literal["hybrid"] = "hybrid"
    artifacts: list[ArtifactSummary]
    highlights: list[dict[str, Any]] = Field(default_factory=list)
    navigation: list[dict[str, str]] = Field(default_factory=list)


def normalize_artifact_id(path: Path) -> str:
    name = path.stem.replace(" ", "-").replace("_", "-")
    return name.lower()
