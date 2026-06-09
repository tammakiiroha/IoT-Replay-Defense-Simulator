'use client';

import { startTransition, useState } from 'react';
import { AlertTriangle, Cpu, ShieldCheck } from 'lucide-react';
import { useLocale } from './locale-context';
import { SCHEMA_VERSION, type SimulationBatchResult, type SimulationSpec } from '../lib/contracts';
import type { LocalizedText } from '../lib/i18n';
import { runSimulation } from '../lib/data';

type Mode = SimulationSpec['modes'][number];
type Copy = (typeof COPY)['en'];

const MODES: Array<{ value: Mode; label: LocalizedText }> = [
  { value: 'no_def', label: { en: 'No Defense', ja: '防御なし', zh: '无防御' } },
  {
    value: 'rolling',
    label: { en: 'Rolling Counter + MAC', ja: 'ローリングカウンタ + MAC', zh: '滚动计数器 + MAC' },
  },
  {
    value: 'window',
    label: { en: 'RFC Sliding Window', ja: 'RFC 風スライディングウィンドウ', zh: 'RFC 风格滑动窗口' },
  },
  {
    value: 'challenge',
    label: { en: 'Challenge-Response', ja: 'チャレンジレスポンス', zh: '挑战-响应' },
  },
  { value: 'hsw_cr', label: { en: 'HSW-CR Adaptive', ja: 'HSW-CR 適応型', zh: 'HSW-CR 自适应' } },
  {
    value: 'oscore_like',
    label: { en: 'OSCORE-like Window', ja: 'OSCORE-like ウィンドウ', zh: 'OSCORE-like 窗口' },
  },
];

const DEVICE_PRESETS = {
  smart_lock: {
    label: { en: 'Smart lock', ja: 'スマートロック', zh: '智能门锁' },
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
    label: { en: 'Toy robot', ja: '玩具ロボット', zh: '玩具机器人' },
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
} satisfies Record<string, Partial<SimulationSpec> & { label: LocalizedText }>;

const COPY = {
  en: {
    eyebrow: 'Runtime',
    title: 'Run replay-defense simulation',
    run: 'Run',
    running: 'Running...',
    preset: 'Device preset',
    custom: 'Custom',
    attackMode: 'Attack mode',
    post: 'Post-run replay',
    inline: 'Inline replay',
    channelModel: 'Channel model',
    iid: 'IID loss',
    gilbert: 'Gilbert-Elliott burst',
    trace: 'Boolean trace',
    runs: 'Monte Carlo runs',
    packetLoss: 'Packet loss',
    packetReorder: 'Packet reorder',
    windowSize: 'Window size',
    macBits: 'MAC tag bits',
    riskThreshold: 'Risk threshold',
    seed: 'Seed',
    defenseModes: 'Defense modes',
    staticTitle: 'Static deploy behavior',
    staticBody:
      'This page first tries the Python API. If no backend exists, it runs a browser-side demo model so GitHub Pages remains interactive.',
    metricsTitle: 'Returned metrics',
    metricsBody:
      'LAR/ASR include Wilson 95% intervals. Browser demo results are usable for exploration; use Python for final research numbers.',
    errorTitle: 'Simulation unavailable',
    lastRun: 'Last run',
    source: 'Source',
    pythonSource: 'Python API authoritative run',
    browserSource: 'Browser demo fallback',
    asr: 'ASR',
    lar: 'LAR',
    asrCi: 'ASR CI',
    energy: 'Energy',
    stateBytes: 'State bytes',
    bytesOverhead: 'Bytes overhead',
    challengeRtt: 'Challenge RTT',
    securityCostChart: 'Security cost chart',
    energyProxy: 'energy proxy',
    oneMinusAsr: '1 - ASR',
    ciPrefix: '95% CI',
  },
  ja: {
    eyebrow: '実行環境',
    title: 'リプレイ防御シミュレーションを実行',
    run: '実行',
    running: '実行中...',
    preset: 'デバイス設定',
    custom: 'カスタム',
    attackMode: '攻撃モード',
    post: '実行後リプレイ',
    inline: 'インラインリプレイ',
    channelModel: 'チャネルモデル',
    iid: 'IID 損失',
    gilbert: 'Gilbert-Elliott バースト',
    trace: 'Boolean trace',
    runs: 'モンテカルロ回数',
    packetLoss: 'パケット損失',
    packetReorder: 'パケット順序入れ替え',
    windowSize: 'ウィンドウサイズ',
    macBits: 'MAC タグ bit',
    riskThreshold: 'リスクしきい値',
    seed: 'シード',
    defenseModes: '防御方式',
    staticTitle: '静的デプロイでの動作',
    staticBody:
      'まず Python API を試します。バックエンドがない場合はブラウザ内デモモデルで実行し、GitHub Pages でも操作できます。',
    metricsTitle: '返される指標',
    metricsBody:
      'LAR/ASR は Wilson 95% 信頼区間を含みます。ブラウザ結果は探索用で、正式な研究値は Python を使用してください。',
    errorTitle: 'シミュレーションを実行できません',
    lastRun: '直近の実行',
    source: '実行元',
    pythonSource: 'Python API 正式実行',
    browserSource: 'ブラウザデモ fallback',
    asr: 'ASR',
    lar: 'LAR',
    asrCi: 'ASR CI',
    energy: 'エネルギー',
    stateBytes: '状態 bytes',
    bytesOverhead: 'バイト overhead',
    challengeRtt: 'Challenge RTT',
    securityCostChart: 'Security cost chart',
    energyProxy: 'energy proxy',
    oneMinusAsr: '1 - ASR',
    ciPrefix: '95% CI',
  },
  zh: {
    eyebrow: '运行环境',
    title: '运行重放防御模拟',
    run: '运行',
    running: '运行中...',
    preset: '设备预设',
    custom: '自定义',
    attackMode: '攻击模式',
    post: '运行后重放',
    inline: '在线重放',
    channelModel: '信道模型',
    iid: 'IID 丢包',
    gilbert: 'Gilbert-Elliott 突发',
    trace: '布尔 trace',
    runs: '蒙特卡洛次数',
    packetLoss: '丢包率',
    packetReorder: '乱序率',
    windowSize: '窗口大小',
    macBits: 'MAC 标签位数',
    riskThreshold: '风险阈值',
    seed: '随机种子',
    defenseModes: '防御模式',
    staticTitle: '静态部署行为',
    staticBody:
      '页面会先尝试 Python API。没有后端时自动使用浏览器端演示模型，因此 GitHub Pages 上也能直接交互。',
    metricsTitle: '返回指标',
    metricsBody:
      'LAR/ASR 包含 Wilson 95% 置信区间。浏览器结果适合探索；正式研究数值请使用 Python 运行。',
    errorTitle: '模拟不可用',
    lastRun: '最近一次运行',
    source: '来源',
    pythonSource: 'Python API 权威运行',
    browserSource: '浏览器演示 fallback',
    asr: 'ASR',
    lar: 'LAR',
    asrCi: 'ASR CI',
    energy: '能量',
    stateBytes: '状态字节',
    bytesOverhead: '字节开销',
    challengeRtt: '挑战 RTT',
    securityCostChart: '安全-成本图',
    energyProxy: '能量代理',
    oneMinusAsr: '1 - ASR',
    ciPrefix: '95% CI',
  },
};

const DEFAULT_SPEC: SimulationSpec = {
  schema_version: SCHEMA_VERSION,
  modes: ['no_def', 'rolling', 'window', 'challenge'],
  runs: 50,
  seed: 42,
  p_loss: 0.1,
  p_reorder: 0.05,
  window_size: 5,
  g_hard: 16,
  num_legit: 20,
  num_replay: 50,
  attack_mode: 'post',
  mac_length: 8,
  mac_tag_bits: 80,
  shared_key: 'sim_shared_key',
  attacker_record_loss: 0,
  attacker_position: 'ind',
  attacker_inject_strength: 'strong',
  attacker_strategy: 'random',
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
  policy_source: 'legacy',
  profile: 'standard',
};

export function SimulatorPanel() {
  const { locale } = useLocale();
  const copy = COPY[locale];
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
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="eyebrow">{copy.eyebrow}</p>
            <h2 className="text-2xl font-semibold">{copy.title}</h2>
          </div>
          <button className="action-button" disabled={loading || spec.modes.length === 0} onClick={handleRun}>
            {loading ? copy.running : copy.run}
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="field">
            <span>{copy.preset}</span>
            <select value={selectedPreset} onChange={(event) => applyPreset(event.target.value)}>
              <option value="custom">{copy.custom}</option>
              {Object.entries(DEVICE_PRESETS).map(([key, preset]) => (
                <option key={key} value={key}>
                  {preset.label[locale]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{copy.attackMode}</span>
            <select
              value={spec.attack_mode}
              onChange={(event) =>
                setSpec({ ...spec, attack_mode: event.target.value as SimulationSpec['attack_mode'] })
              }
            >
              <option value="post">{copy.post}</option>
              <option value="inline">{copy.inline}</option>
            </select>
          </label>
          <label className="field">
            <span>{copy.channelModel}</span>
            <select
              value={spec.channel_model}
              onChange={(event) =>
                setSpec({ ...spec, channel_model: event.target.value as SimulationSpec['channel_model'] })
              }
            >
              <option value="iid">{copy.iid}</option>
              <option value="gilbert_elliott">{copy.gilbert}</option>
              <option value="trace">{copy.trace}</option>
            </select>
          </label>
          <label className="field">
            <span>{copy.runs}</span>
            <input
              type="number"
              min={1}
              value={spec.runs}
              onChange={(event) => setSpec({ ...spec, runs: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>{copy.packetLoss}</span>
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
            <span>{copy.packetReorder}</span>
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
            <span>{copy.windowSize}</span>
            <input
              type="number"
              min={1}
              value={spec.window_size}
              onChange={(event) => setSpec({ ...spec, window_size: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>{copy.macBits}</span>
            <input
              type="number"
              min={32}
              step={16}
              value={spec.mac_tag_bits}
              onChange={(event) => setSpec({ ...spec, mac_tag_bits: Number(event.target.value) })}
            />
          </label>
          <label className="field">
            <span>{copy.riskThreshold}</span>
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
            <span>{copy.seed}</span>
            <input
              type="number"
              min={0}
              value={spec.seed ?? 0}
              onChange={(event) => setSpec({ ...spec, seed: Number(event.target.value) })}
            />
          </label>
        </div>

        <div className="mt-6">
          <p className="mb-3 text-xs font-semibold uppercase text-stone-500">
            {copy.defenseModes}
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
                  {mode.label[locale]}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <BoundaryNotice copy={copy} />
        {error ? <ErrorNotice copy={copy} message={error} /> : null}
        {result ? <RunResults copy={copy} locale={locale} result={result} /> : null}
      </div>
    </div>
  );
}

function BoundaryNotice({ copy }: { copy: Copy }) {
  return (
    <div className="grid gap-6">
      <div className="panel">
        <div className="flex items-start gap-3">
          <Cpu className="mt-1 h-5 w-5 text-amber-600" />
          <div>
            <h3 className="text-lg font-semibold">{copy.staticTitle}</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              {copy.staticBody}
            </p>
          </div>
        </div>
      </div>
      <div className="panel">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-1 h-5 w-5 text-emerald-600" />
          <div>
            <h3 className="text-lg font-semibold">{copy.metricsTitle}</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              {copy.metricsBody}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorNotice({ copy, message }: { copy: Copy; message: string }) {
  return (
    <div className="panel border-rose-300/60 bg-rose-50/70">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-1 h-5 w-5 text-rose-600" />
        <div>
          <h3 className="text-lg font-semibold text-rose-950">{copy.errorTitle}</h3>
          <p className="mt-2 text-sm leading-6 text-rose-900">{message}</p>
        </div>
      </div>
    </div>
  );
}

function RunResults({
  copy,
  locale,
  result,
}: {
  copy: Copy;
  locale: 'en' | 'ja' | 'zh';
  result: SimulationBatchResult;
}) {
  const source = result.metadata.runtime === 'browser_static_fallback' ? copy.browserSource : copy.pythonSource;
  return (
    <div className="panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="eyebrow">{copy.lastRun}</p>
        <p className="rounded-full border border-stone-900/10 bg-white/70 px-3 py-1 text-xs font-semibold text-stone-600">
          {copy.source}: {source}
        </p>
      </div>
      <CostChart copy={copy} locale={locale} result={result} />
      <div className="mt-5 space-y-4">
        {result.results.map((entry) => (
          <div key={entry.mode} className="rounded border border-stone-900/10 bg-white/70 p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold">{modeLabel(entry.mode, locale)}</h3>
                <p className="text-xs uppercase text-stone-500">
                  {entry.runs} runs · {entry.attack_mode}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-stone-500">{copy.asr}</p>
                <p className="text-2xl font-semibold text-rose-700">
                  {percent(entry.avg_attack_rate)}
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Metric
                label={copy.lar}
                value={percent(entry.avg_legit_rate)}
                hint={`${percent(entry.lar_ci_low)}-${percent(entry.lar_ci_high)}`}
                hintPrefix={copy.ciPrefix}
              />
              <Metric
                label={copy.asrCi}
                value={`${percent(entry.asr_ci_low)}-${percent(entry.asr_ci_high)}`}
              />
              <Metric label={copy.energy} value={entry.energy_proxy.toFixed(1)} />
              <Metric label={copy.stateBytes} value={entry.state_bytes.toFixed(1)} />
              <Metric label={copy.bytesOverhead} value={entry.bytes_overhead.toFixed(1)} />
              <Metric label={copy.challengeRtt} value={entry.challenge_round_trips.toFixed(1)} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CostChart({
  copy,
  locale,
  result,
}: {
  copy: Copy;
  locale: 'en' | 'ja' | 'zh';
  result: SimulationBatchResult;
}) {
  const maxEnergy = Math.max(...result.results.map((entry) => entry.energy_proxy), 1);
  return (
    <div className="mt-4 rounded border border-stone-900/10 bg-stone-50/80 p-4">
      <svg viewBox="0 0 320 180" className="h-44 w-full" role="img" aria-label={copy.securityCostChart}>
        <line x1="30" y1="150" x2="300" y2="150" stroke="#a8a29e" />
        <line x1="30" y1="20" x2="30" y2="150" stroke="#a8a29e" />
        {result.results.map((entry, index) => {
          const x = 30 + (entry.energy_proxy / maxEnergy) * 260;
          const y = 150 - (1 - entry.avg_attack_rate) * 120;
          return (
            <g key={entry.mode}>
              <circle cx={x} cy={y} r="5" fill={chartColor(index)} />
              <text x={x + 7} y={y - 7} fontSize="9" fill="#44403c">
                {modeLabel(entry.mode, locale)}
              </text>
            </g>
          );
        })}
        <text x="30" y="172" fontSize="10" fill="#78716c">
          {copy.energyProxy}
        </text>
        <text x="36" y="16" fontSize="10" fill="#78716c">
          {copy.oneMinusAsr}
        </text>
      </svg>
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
  hintPrefix,
}: {
  label: string;
  value: string;
  hint?: string;
  hintPrefix?: string;
}) {
  return (
    <div className="rounded border border-stone-900/10 bg-stone-50/80 p-3">
      <p className="text-xs uppercase text-stone-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-stone-950">{value}</p>
      {hint ? <p className="mt-1 text-xs text-stone-500">{hintPrefix ?? '95% CI'} {hint}</p> : null}
    </div>
  );
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function modeLabel(mode: Mode, locale: 'en' | 'ja' | 'zh') {
  const modeCopy = MODES.find((entry) => entry.value === mode);
  if (!modeCopy) {
    return mode;
  }
  return modeCopy.label[locale];
}

function chartColor(index: number) {
  return ['#0f766e', '#b45309', '#be123c', '#4338ca', '#15803d', '#7c2d12'][index % 6];
}
