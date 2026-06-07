"""Generate web-facing contract files from Python models."""
from __future__ import annotations

import json
from pathlib import Path

from .models import (
    SCHEMA_VERSION,
    ArtifactManifest,
    ExperimentArtifact,
    LabValidationArtifact,
    SimulationBatchResult,
    SimulationSpec,
    SimulationSpecPublic,
    SimVsHardwareArtifact,
    SweepSpec,
)


def _schema_bundle() -> dict[str, object]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "SimulationSpec": SimulationSpec.model_json_schema(),
        "SimulationSpecPublic": SimulationSpecPublic.model_json_schema(),
        "SimulationBatchResult": SimulationBatchResult.model_json_schema(),
        "SweepSpec": SweepSpec.model_json_schema(),
        "ExperimentArtifact": ExperimentArtifact.model_json_schema(),
        "LabValidationArtifact": LabValidationArtifact.model_json_schema(),
        "SimVsHardwareArtifact": SimVsHardwareArtifact.model_json_schema(),
        "ArtifactManifest": ArtifactManifest.model_json_schema(),
    }


def render_typescript_contracts() -> str:
    schemas = json.dumps(_schema_bundle(), indent=2, ensure_ascii=False)
    return f"""// AUTO-GENERATED. Do not edit by hand.
// Source: replay.contracts.typescript

export const SCHEMA_VERSION = "{SCHEMA_VERSION}" as const;

export type Mode =
  | 'no_def'
  | 'rolling'
  | 'window'
  | 'sw_resync'
  | 'challenge'
  | 'hsw_cr'
  | 'oscore_like';
export type AttackMode = 'post' | 'inline';
export type ChannelModel = 'iid' | 'gilbert_elliott' | 'trace';
export type AuthProfile = 'hmac' | 'ascon';

export interface SimulationSpec {{
  schema_version: typeof SCHEMA_VERSION;
  modes: Mode[];
  runs: number;
  seed?: number | null;
  p_loss: number;
  p_reorder: number;
  window_size: number;
  g_hard: number;
  num_legit: number;
  num_replay: number;
  attack_mode: AttackMode;
  mac_length: number;
  mac_tag_bits: number;
  shared_key: string;
  attacker_record_loss: number;
  inline_attack_probability: number;
  inline_attack_burst: number;
  challenge_nonce_bits: number;
  target_commands?: string[] | null;
  command_sequence?: string[] | null;
  command_set?: string[] | null;
  target_ci_half_width?: number | null;
  max_runs: number;
  paired: boolean;
  channel_model: ChannelModel;
  burst_p_good_to_bad: number;
  burst_p_bad_to_good: number;
  loss_good: number;
  loss_bad: number;
  loss_trace?: boolean[] | null;
  command_risk?: Record<string, number> | null;
  risk_high: number;
  auth_profile: AuthProfile;
}}

export interface SimulationSpecPublic {{
  schema_version: typeof SCHEMA_VERSION;
  modes: Mode[];
  runs: number;
  seed?: number | null;
  p_loss: number;
  p_reorder: number;
  window_size: number;
  g_hard: number;
  num_legit: number;
  num_replay: number;
  attack_mode: AttackMode;
  mac_length: number;
  mac_tag_bits: number;
  attacker_record_loss: number;
  inline_attack_probability: number;
  inline_attack_burst: number;
  challenge_nonce_bits: number;
  target_commands?: string[] | null;
  command_sequence?: string[] | null;
  command_set?: string[] | null;
  target_ci_half_width?: number | null;
  max_runs: number;
  paired: boolean;
  channel_model: ChannelModel;
  burst_p_good_to_bad: number;
  burst_p_bad_to_good: number;
  loss_good: number;
  loss_bad: number;
  loss_trace?: boolean[] | null;
  command_risk?: Record<string, number> | null;
  risk_high: number;
  auth_profile: AuthProfile;
}}

export interface SimulationResultRecord {{
  mode: Mode;
  runs: number;
  avg_legit_rate: number;
  std_legit_rate: number;
  avg_attack_rate: number;
  std_attack_rate: number;
  p_loss: number;
  p_reorder: number;
  window_size: number;
  num_legit: number;
  num_replay: number;
  attack_mode: AttackMode;
  legit_accepted: number;
  legit_total: number;
  attack_accepted: number;
  attack_total: number;
  lar_ci_low: number;
  lar_ci_high: number;
  asr_ci_low: number;
  asr_ci_high: number;
  frr: number;
  energy_proxy: number;
  bytes_overhead: number;
  state_bytes: number;
  latency_ticks: number;
  crypto_ops: number;
  challenge_round_trips: number;
  resync_initiated: number;
  resync_completed: number;
  resync_timeout: number;
  crit_prepared: number;
  crit_committed: number;
  crit_rejected: number;
  reboots: number;
  locked_safe_rejects: number;
  epoch_recoveries: number;
  mac_tag_bits: number;
  auth_profile: string;
  metadata: Record<string, unknown>;
}}

export interface SimulationBatchResult {{
  schema_version: typeof SCHEMA_VERSION;
  generated_at: string;
  config: SimulationSpecPublic;
  results: SimulationResultRecord[];
  metadata: Record<string, unknown>;
}}

export interface SweepSpec {{
  schema_version: typeof SCHEMA_VERSION;
  sweep_type: 'p_loss' | 'p_reorder' | 'window' | 'mac_tag_bits';
  values: Array<number>;
  simulation: SimulationSpec;
  fixed_p_loss?: number | null;
  fixed_p_reorder?: number | null;
}}

export interface ExperimentArtifact {{
  schema_version: typeof SCHEMA_VERSION;
  artifact_id: string;
  kind: string;
  title: string;
  description: string;
  generated_at: string;
  source_path?: string | null;
  config_snapshot: Record<string, unknown>;
  summary: Record<string, unknown>;
  metrics: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
}}

export interface LabValidationArtifact {{
  schema_version: typeof SCHEMA_VERSION;
  artifact_id: string;
  title: string;
  generated_at: string;
  source_path: string;
  summary: Record<string, unknown>;
  environment: Record<string, unknown>;
  config: Record<string, unknown>;
  results: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
}}

export type SimVsHardwareArtifact = LabValidationArtifact;

export interface ArtifactSummary {{
  artifact_id: string;
  title: string;
  kind: string;
  path: string;
  description?: string | null;
  updated_at: string;
}}

export interface ArtifactManifest {{
  schema_version: typeof SCHEMA_VERSION;
  generated_at: string;
  title: string;
  description: string;
  runtime_mode: 'hybrid';
  artifacts: ArtifactSummary[];
  highlights: Array<Record<string, unknown>>;
  navigation: Array<Record<string, string>>;
}}

export const jsonSchemas = {schemas} as const;
"""


def write_contract_artifacts(project_root: Path) -> None:
    contracts_path = project_root / "web" / "lib" / "contracts.ts"
    schema_path = project_root / "web" / "public" / "data" / "contracts.json"
    contracts_path.write_text(render_typescript_contracts(), encoding="utf-8")
    schema_path.write_text(
        json.dumps(_schema_bundle(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
