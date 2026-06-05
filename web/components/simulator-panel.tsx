'use client';

import { startTransition, useState } from 'react';
import { AlertTriangle, Cpu, ShieldCheck } from 'lucide-react';
import { SCHEMA_VERSION, type SimulationBatchResult, type SimulationSpec } from '../lib/contracts';
import { runSimulation } from '../lib/data';

type Mode = SimulationSpec['modes'][number];

const MODES: Array<{ value: Mode; label: string }> = [
  { value: 'no_def', label: 'No Defense' },
  { value: 'rolling', label: 'Rolling Counter + MAC' },
  { value: 'window', label: 'RFC Sliding Window' },
  { value: 'challenge', label: 'Challenge-Response' },
  { value: 'hsw_cr', label: 'HSW-CR Adaptive' },
  { value: 'oscore_like', label: 'OSCORE-like Window' },
];

const DEVICE_PRESETS = {
  smart_lock: {
    label: 'Smart lock',
    command_set: ['PING', 'STATUS', 'LOCK', 'UNLOCK'],
    command_risk: { PING: 0.1, STATUS: 0.2, LOCK: 0.7, UNLOCK: 1.0 },
    target_commands: ['UNLOCK'],
    modes: ['window', 'hsw_cr', 'oscore_like'],
    window_size: 8,
    channel_model: 'gilbert_elliott',
    loss_good: 0.01,
    loss_bad: 0.4,
    auth_profile: 'hmac',
    mac_tag_bits: 80,
  },
  toy_robot: {
    label: 'Toy robot',
    command_set: ['FWD', 'BACK', 'LEFT', 'RIGHT', 'STOP'],
    command_risk: { STOP: 0.8 },
    target_commands: ['STOP'],
    modes: ['rolling', 'window', 'hsw_cr'],
    window_size: 5,
    channel_model: 'iid',
    loss_good: 0.01,
    loss_bad: 0.6,
    auth_profile: 'hmac',
    mac_tag_bits: 80,
  },
} satisfies Record<string, Partial<SimulationSpec> & { label: string }>;

const DEFAULT_SPEC: SimulationSpec = {
  schema_version: SCHEMA_VERSION,
  modes: ['no_def', 'rolling', 'window', 'challenge'],
  runs: 50,
  seed: 42,
  p_loss: 0.1,
  p_reorder: 0.05,
  window_size: 5,
  num_legit: 20,
  num_replay: 50,
  attack_mode: 'post',
  mac_length: 8,
  mac_tag_bits: 80,
  shared_key: 'sim_shared_key',
  attacker_record_loss: 0,
  inline_attack_probability: 0.3,
  inline_attack_burst: 1,
  challenge_nonce_bits: 32,
  target_commands: null,
  command_sequence: null,
  command_set: ['FWD', 'BACK', 'LEFT', 'RIGHT', 'STOP'],
  target_ci_half_width: null,
  max_runs: 2000,
  paired: false,
  channel_model: 'iid',
  burst_p_good_to_bad: 0.05,
  burst_p_bad_to_good: 0.3,
  loss_good: 0.01,
  loss_bad: 0.6,
  loss_trace: null,
  command_risk: null,
  risk_high: 0.8,
  auth_profile: 'hmac',
};

export function SimulatorPanel() {
  const [spec, setSpec] = useState<SimulationSpec>(DEFAULT_SPEC);
  const [selectedPreset, setSelectedPreset] = useState('custom');
  const [result, setResult] = useState<SimulationBatchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const nextResult = await runSimulation(spec);
      startTransition(() => {
        setResult(nextResult);
      });
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : 'The API is unavailable. Use local full-stack mode to run authoritative simulations.';
      setError(message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  function applyPreset(key: string) {
    setSelectedPreset(key);
    if (key === 'custom') {
      return;
    }
    const preset = DEVICE_PRESETS[key as keyof typeof DEVICE_PRESETS];
    setSpec((current) => ({
      ...current,
      command_set: preset.command_set,
      command_risk: preset.command_risk,
      target_commands: preset.target_commands,
      modes: preset.modes,
      window_size: preset.window_size,
      channel_model: preset.channel_model,
      loss_good: preset.loss_good,
      loss_bad: preset.loss_bad,
      auth_profile: preset.auth_profile,
      mac_tag_bits: preset.mac_tag_bits,
    }));
  }

  function toggleMode(mode: Mode) {
    setSpec((current) => {
      const exists = current.modes.includes(mode);
      const modes = exists
        ? current.modes.filter((value) => value !== mode)
        : [...current.modes, mode];
      return { ...current, modes };
    });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="panel">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="eyebrow">Authoritative Runtime</p>
            <h2 className="text-2xl font-semibold">Run Python-backed simulation</h2>
          </div>
          <button className="action-button" disabled={loading || spec.modes.length === 0} onClick={handleRun}>
            {loading ? 'Running...' : 'Run Simulation'}
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="field">
            <span>Device preset</span>
            <select value={selectedPreset} onChange={(event) => applyPreset(event.target.value)}>
              <option value="custom">Custom</option>
              {Object.entries(DEVICE_PRESETS).map(([key, preset]) => (
                <option key={key} value={key}>
                  {preset.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Attack mode</span>
            <select
              value={spec.attack_mode}
              onChange={(event) =>
                setSpec({ ...spec, attack_mode: event.target.value as SimulationSpec['attack_mode'] })
              }
            >
              <option value="post">Post-run replay</option>
              <option value="inline">Inline replay</option>
            </select>
          </label>
          <label className="field">
            <span>Channel model</span>
            <select
              value={spec.channel_model}
              onChange={(event) =>
                setSpec({ ...spec, channel_model: event.target.value as SimulationSpec['channel_model'] })
              }
            >
              <option value="iid">IID loss</option>
              <option value="gilbert_elliott">Gilbert-Elliott burst</option>
              <option value="trace">Boolean trace</option>
            </select>
          </label>
          <label className="field">
            <span>Monte Carlo runs</span>
            <input
              type="number"
              min={1}
              value={spec.runs}
              onChange={(event) => setSpec({ ...spec, runs: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>Packet loss</span>
            <input
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={spec.p_loss}
              onChange={(event) => setSpec({ ...spec, p_loss: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>Packet reorder</span>
            <input
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={spec.p_reorder}
              onChange={(event) => setSpec({ ...spec, p_reorder: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>Window size</span>
            <input
              type="number"
              min={1}
              value={spec.window_size}
              onChange={(event) => setSpec({ ...spec, window_size: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>MAC tag bits</span>
            <input
              type="number"
              min={32}
              step={16}
              value={spec.mac_tag_bits}
              onChange={(event) => setSpec({ ...spec, mac_tag_bits: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>Risk threshold</span>
            <input
              type="number"
              min={0}
              max={1}
              step="0.05"
              value={spec.risk_high}
              onChange={(event) => setSpec({ ...spec, risk_high: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>Seed</span>
            <input
              type="number"
              min={0}
              value={spec.seed ?? 0}
              onChange={(event) => setSpec({ ...spec, seed: Number(event.target.value) })}
            />
          </label>
        </div>

        <div className="mt-6">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">
            Defense modes
          </p>
          <div className="flex flex-wrap gap-3">
            {MODES.map((mode) => {
              const active = spec.modes.includes(mode.value);
              return (
                <button
                  key={mode.value}
                  type="button"
                  className={active ? 'toggle-pill active' : 'toggle-pill'}
                  onClick={() => toggleMode(mode.value)}
                >
                  {mode.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <BoundaryNotice />
        {error ? <ErrorNotice message={error} /> : null}
        {result ? <RunResults result={result} /> : null}
      </div>
    </div>
  );
}

function BoundaryNotice() {
  return (
    <div className="grid gap-6">
      <div className="panel">
        <div className="flex items-start gap-3">
          <Cpu className="mt-1 h-5 w-5 text-amber-600" />
          <div>
            <h3 className="text-lg font-semibold">Static deploy boundary</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              Public GitHub Pages has no Python worker. Local full-stack mode is required for live runs.
            </p>
          </div>
        </div>
      </div>
      <div className="panel">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-1 h-5 w-5 text-emerald-600" />
          <div>
            <h3 className="text-lg font-semibold">Returned metrics</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              LAR/ASR include Wilson 95% intervals; cost fields come from the Python core.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="panel border-rose-300/60 bg-rose-50/70">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-1 h-5 w-5 text-rose-600" />
        <div>
          <h3 className="text-lg font-semibold text-rose-950">Backend unavailable</h3>
          <p className="mt-2 text-sm leading-6 text-rose-900">{message}</p>
        </div>
      </div>
    </div>
  );
}

function RunResults({ result }: { result: SimulationBatchResult }) {
  return (
    <div className="panel">
      <p className="eyebrow">Last run</p>
      <CostChart result={result} />
      <div className="mt-5 space-y-4">
        {result.results.map((entry) => (
          <div key={entry.mode} className="rounded border border-stone-900/10 bg-white/70 p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold">{modeLabel(entry.mode)}</h3>
                <p className="text-xs uppercase tracking-[0.2em] text-stone-500">
                  {entry.runs} runs · {entry.attack_mode}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-stone-500">ASR</p>
                <p className="text-2xl font-semibold text-rose-700">
                  {percent(entry.avg_attack_rate)}
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Metric
                label="LAR"
                value={percent(entry.avg_legit_rate)}
                hint={`${percent(entry.lar_ci_low)}-${percent(entry.lar_ci_high)}`}
              />
              <Metric
                label="ASR CI"
                value={`${percent(entry.asr_ci_low)}-${percent(entry.asr_ci_high)}`}
              />
              <Metric label="Energy" value={entry.energy_proxy.toFixed(1)} />
              <Metric label="State bytes" value={entry.state_bytes.toFixed(1)} />
              <Metric label="Bytes overhead" value={entry.bytes_overhead.toFixed(1)} />
              <Metric label="Challenge RTT" value={entry.challenge_round_trips.toFixed(1)} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CostChart({ result }: { result: SimulationBatchResult }) {
  const maxEnergy = Math.max(...result.results.map((entry) => entry.energy_proxy), 1);
  return (
    <div className="mt-4 rounded border border-stone-900/10 bg-stone-50/80 p-4">
      <svg viewBox="0 0 320 180" className="h-44 w-full" role="img" aria-label="Security cost chart">
        <line x1="30" y1="150" x2="300" y2="150" stroke="#a8a29e" />
        <line x1="30" y1="20" x2="30" y2="150" stroke="#a8a29e" />
        {result.results.map((entry, index) => {
          const x = 30 + (entry.energy_proxy / maxEnergy) * 260;
          const y = 150 - (1 - entry.avg_attack_rate) * 120;
          return (
            <g key={entry.mode}>
              <circle cx={x} cy={y} r="5" fill={chartColor(index)} />
              <text x={x + 7} y={y - 7} fontSize="9" fill="#44403c">
                {entry.mode}
              </text>
            </g>
          );
        })}
        <text x="30" y="172" fontSize="10" fill="#78716c">
          energy proxy
        </text>
        <text x="36" y="16" fontSize="10" fill="#78716c">
          1 - ASR
        </text>
      </svg>
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded border border-stone-900/10 bg-stone-50/80 p-3">
      <p className="text-xs uppercase tracking-[0.22em] text-stone-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-stone-950">{value}</p>
      {hint ? <p className="mt-1 text-xs text-stone-500">95% CI {hint}</p> : null}
    </div>
  );
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function modeLabel(mode: Mode) {
  return MODES.find((entry) => entry.value === mode)?.label ?? mode;
}

function chartColor(index: number) {
  return ['#0f766e', '#b45309', '#be123c', '#4338ca', '#15803d', '#7c2d12'][index % 6];
}
