import {
  SCHEMA_VERSION,
  type Mode,
  type SimulationBatchResult,
  type SimulationResultRecord,
  type SimulationSpec,
  type SimulationSpecPublic,
} from './contracts';

type Frame = {
  command: string;
  counter: number;
  nonce: number | null;
  isAttack: boolean;
};

type ReceiverState = {
  lastCounter: number;
  seenCounters: Set<number>;
  outstandingNonces: Set<number>;
  usedNonces: Set<number>;
};

type RunCounters = {
  legitAccepted: number;
  attackAccepted: number;
  attackAttempts: number;
  challengeRoundTrips: number;
};

type CostProfile = {
  bytes: number;
  state: number;
  latency: number;
  cryptoOps: number;
  challengeRtt: number;
};

class DeterministicRng {
  private state: number;

  constructor(seed: number) {
    this.state = seed >>> 0 || 0x6d2b79f5;
  }

  next(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let value = this.state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  }

  int(maxExclusive: number): number {
    return Math.floor(this.next() * maxExclusive);
  }
}

class StaticChannel {
  private readonly buffer: Frame[] = [];
  private badState = false;
  private traceIndex = 0;

  constructor(
    private readonly spec: SimulationSpec,
    private readonly rng: DeterministicRng,
  ) {}

  send(frame: Frame): Frame[] {
    if (this.isLost()) {
      return [];
    }
    if (this.rng.next() < this.spec.p_reorder) {
      this.buffer.push(frame);
      return [];
    }
    const delivered = [...this.buffer, frame];
    this.buffer.length = 0;
    return delivered;
  }

  flush(): Frame[] {
    const delivered = [...this.buffer];
    this.buffer.length = 0;
    return delivered;
  }

  private isLost(): boolean {
    if (this.spec.channel_model === 'trace' && this.spec.loss_trace?.length) {
      const lost = this.spec.loss_trace[this.traceIndex % this.spec.loss_trace.length];
      this.traceIndex += 1;
      return lost;
    }

    if (this.spec.channel_model === 'gilbert_elliott') {
      if (this.badState) {
        this.badState = this.rng.next() >= this.spec.burst_p_bad_to_good;
      } else {
        this.badState = this.rng.next() < this.spec.burst_p_good_to_bad;
      }
      return this.rng.next() < (this.badState ? this.spec.loss_bad : this.spec.loss_good);
    }

    return this.rng.next() < this.spec.p_loss;
  }
}

export function runStaticSimulation(spec: SimulationSpec): SimulationBatchResult {
  const startedAt = performance.now();
  const results = spec.modes.map((mode) => aggregateMode(spec, mode));
  return {
    schema_version: SCHEMA_VERSION,
    generated_at: new Date().toISOString(),
    config: publicSpec(spec),
    results,
    metadata: {
      runtime: 'browser_static_fallback',
      authoritative: false,
      note: 'Static GitHub Pages fallback. Use the Python API or CLI for authoritative research runs.',
      elapsed_ms: Math.round((performance.now() - startedAt) * 10) / 10,
    },
  };
}

function aggregateMode(spec: SimulationSpec, mode: Mode): SimulationResultRecord {
  const legitRates: number[] = [];
  const attackRates: number[] = [];
  const runs: RunCounters[] = [];
  const baseSeed = spec.seed ?? 42;

  for (let run = 0; run < spec.runs; run += 1) {
    const rng = new DeterministicRng(hashSeed(baseSeed, mode, run));
    const counters = simulateOneRun(spec, mode, rng);
    legitRates.push(safeDiv(counters.legitAccepted, spec.num_legit));
    attackRates.push(safeDiv(counters.attackAccepted, counters.attackAttempts));
    runs.push(counters);
  }

  const legitAccepted = runs.reduce((total, run) => total + run.legitAccepted, 0);
  const attackAccepted = runs.reduce((total, run) => total + run.attackAccepted, 0);
  const attackAttempts = runs.reduce((total, run) => total + run.attackAttempts, 0);
  const legitTotal = spec.runs * spec.num_legit;
  const larCi = wilsonCi(legitAccepted, legitTotal);
  const asrCi = wilsonCi(attackAccepted, attackAttempts);
  const cost = costProfile(spec, mode);
  const acceptedFrames = legitAccepted + attackAccepted;

  return {
    mode,
    runs: spec.runs,
    avg_legit_rate: mean(legitRates),
    std_legit_rate: std(legitRates),
    avg_attack_rate: mean(attackRates),
    std_attack_rate: std(attackRates),
    p_loss: spec.p_loss,
    p_reorder: spec.p_reorder,
    window_size: isWindowMode(mode) ? spec.window_size : 0,
    num_legit: spec.num_legit,
    num_replay: spec.num_replay,
    attack_mode: spec.attack_mode,
    legit_accepted: legitAccepted,
    legit_total: legitTotal,
    attack_accepted: attackAccepted,
    attack_total: attackAttempts,
    lar_ci_low: larCi.low,
    lar_ci_high: larCi.high,
    asr_ci_low: asrCi.low,
    asr_ci_high: asrCi.high,
    frr: 1 - safeDiv(legitAccepted, legitTotal),
    energy_proxy: cost.cryptoOps * (legitTotal + attackAttempts) + acceptedFrames * (1 + cost.bytes / 64),
    bytes_overhead: cost.bytes,
    state_bytes: cost.state,
    latency_ticks: cost.latency,
    crypto_ops: cost.cryptoOps,
    challenge_round_trips: mean(runs.map((run) => run.challengeRoundTrips)),
    mac_tag_bits: spec.mac_tag_bits,
    auth_profile: spec.auth_profile,
    metadata: {
      runtime: 'browser_static_fallback',
      approximation: true,
    },
  };
}

function simulateOneRun(spec: SimulationSpec, mode: Mode, rng: DeterministicRng): RunCounters {
  const receiver: ReceiverState = {
    lastCounter: -1,
    seenCounters: new Set<number>(),
    outstandingNonces: new Set<number>(),
    usedNonces: new Set<number>(),
  };
  const channel = new StaticChannel(spec, rng);
  const observed: Frame[] = [];
  let legitAccepted = 0;
  let attackAccepted = 0;
  let attackAttempts = 0;
  let challengeRoundTrips = 0;

  const processDelivered = (frames: Frame[]) => {
    for (const frame of frames) {
      if (acceptFrame(mode, frame, receiver, spec)) {
        if (frame.isAttack) {
          attackAccepted += 1;
        } else {
          legitAccepted += 1;
        }
      }
    }
  };

  for (let index = 0; index < spec.num_legit; index += 1) {
    const command = commandFor(spec, index, rng);
    const nonce = needsChallenge(mode, command, spec) ? nextNonce(rng, spec.challenge_nonce_bits) : null;
    if (nonce !== null) {
      receiver.outstandingNonces.add(nonce);
      challengeRoundTrips += 1;
    }
    const frame: Frame = { command, counter: index + 1, nonce, isAttack: false };
    if (rng.next() >= spec.attacker_record_loss && shouldRecord(command, spec)) {
      observed.push({ ...frame });
    }
    processDelivered(channel.send(frame));

    if (spec.attack_mode === 'inline' && rng.next() < spec.inline_attack_probability) {
      for (let burst = 0; burst < spec.inline_attack_burst; burst += 1) {
        const replay = pickReplay(observed, rng);
        if (replay) {
          attackAttempts += 1;
          processDelivered(channel.send(replay));
        }
      }
    }
  }

  processDelivered(channel.flush());

  if (spec.attack_mode === 'post') {
    for (let index = 0; index < spec.num_replay; index += 1) {
      const replay = pickReplay(observed, rng);
      if (replay) {
        attackAttempts += 1;
        processDelivered(channel.send(replay));
      }
    }
    processDelivered(channel.flush());
  }

  return { legitAccepted, attackAccepted, attackAttempts, challengeRoundTrips };
}

function acceptFrame(mode: Mode, frame: Frame, state: ReceiverState, spec: SimulationSpec): boolean {
  if (mode === 'no_def') {
    return true;
  }

  if (needsChallenge(mode, frame.command, spec)) {
    if (frame.nonce === null || state.usedNonces.has(frame.nonce) || !state.outstandingNonces.has(frame.nonce)) {
      return false;
    }
    state.outstandingNonces.delete(frame.nonce);
    state.usedNonces.add(frame.nonce);
  }

  if (mode === 'challenge') {
    return true;
  }

  if (mode === 'rolling') {
    if (frame.counter <= state.lastCounter) {
      return false;
    }
    state.lastCounter = frame.counter;
    return true;
  }

  const lowerBound = state.lastCounter - Math.max(0, spec.window_size - 1);
  if (state.lastCounter >= 0 && frame.counter < lowerBound) {
    return false;
  }
  if (state.seenCounters.has(frame.counter)) {
    return false;
  }
  state.seenCounters.add(frame.counter);
  state.lastCounter = Math.max(state.lastCounter, frame.counter);
  for (const seen of [...state.seenCounters]) {
    if (seen < state.lastCounter - Math.max(0, spec.window_size - 1)) {
      state.seenCounters.delete(seen);
    }
  }
  return true;
}

function commandFor(spec: SimulationSpec, index: number, rng: DeterministicRng): string {
  if (spec.command_sequence?.length) {
    return spec.command_sequence[index % spec.command_sequence.length];
  }
  const commands = spec.command_set?.length ? spec.command_set : ['FWD', 'BACK', 'LEFT', 'RIGHT', 'STOP'];
  return commands[rng.int(commands.length)];
}

function shouldRecord(command: string, spec: SimulationSpec): boolean {
  return !spec.target_commands?.length || spec.target_commands.includes(command);
}

function needsChallenge(mode: Mode, command: string, spec: SimulationSpec): boolean {
  if (mode === 'challenge') {
    return true;
  }
  if (mode !== 'hsw_cr') {
    return false;
  }
  const risk = spec.command_risk?.[command] ?? 0;
  return risk >= spec.risk_high || Boolean(spec.target_commands?.includes(command));
}

function pickReplay(observed: Frame[], rng: DeterministicRng): Frame | null {
  if (observed.length === 0) {
    return null;
  }
  return { ...observed[rng.int(observed.length)], isAttack: true };
}

function nextNonce(rng: DeterministicRng, bits: number): number {
  const max = Math.max(2, Math.min(2 ** Math.min(bits, 30), 2 ** 30));
  return rng.int(max);
}

function publicSpec(spec: SimulationSpec): SimulationSpecPublic {
  return {
    schema_version: spec.schema_version,
    modes: spec.modes,
    runs: spec.runs,
    seed: spec.seed,
    p_loss: spec.p_loss,
    p_reorder: spec.p_reorder,
    window_size: spec.window_size,
    num_legit: spec.num_legit,
    num_replay: spec.num_replay,
    attack_mode: spec.attack_mode,
    mac_length: spec.mac_length,
    mac_tag_bits: spec.mac_tag_bits,
    attacker_record_loss: spec.attacker_record_loss,
    inline_attack_probability: spec.inline_attack_probability,
    inline_attack_burst: spec.inline_attack_burst,
    challenge_nonce_bits: spec.challenge_nonce_bits,
    target_commands: spec.target_commands,
    command_sequence: spec.command_sequence,
    command_set: spec.command_set,
    target_ci_half_width: spec.target_ci_half_width,
    max_runs: spec.max_runs,
    paired: spec.paired,
    channel_model: spec.channel_model,
    burst_p_good_to_bad: spec.burst_p_good_to_bad,
    burst_p_bad_to_good: spec.burst_p_bad_to_good,
    loss_good: spec.loss_good,
    loss_bad: spec.loss_bad,
    loss_trace: spec.loss_trace,
    command_risk: spec.command_risk,
    risk_high: spec.risk_high,
    auth_profile: spec.auth_profile,
  };
}

function costProfile(spec: SimulationSpec, mode: Mode): CostProfile {
  const tagBytes = spec.mac_tag_bits / 8;
  const windowBytes = Math.ceil(Math.max(1, spec.window_size) / 8);
  const profiles: Record<Mode, CostProfile> = {
    no_def: { bytes: 0, state: 0, latency: 1, cryptoOps: 0, challengeRtt: 0 },
    rolling: { bytes: 4 + tagBytes, state: 8, latency: 1.1, cryptoOps: 2, challengeRtt: 0 },
    window: { bytes: 4 + tagBytes, state: 8 + windowBytes, latency: 1.15, cryptoOps: 2, challengeRtt: 0 },
    challenge: {
      bytes: 4 + tagBytes + spec.challenge_nonce_bits / 8,
      state: 64,
      latency: 2.2,
      cryptoOps: 2,
      challengeRtt: 1,
    },
    hsw_cr: {
      bytes: 4 + tagBytes + spec.challenge_nonce_bits / 16,
      state: 16 + windowBytes + 32,
      latency: 1.5,
      cryptoOps: 2.5,
      challengeRtt: 0.4,
    },
    oscore_like: { bytes: 5 + tagBytes, state: 16 + windowBytes, latency: 1.25, cryptoOps: 2, challengeRtt: 0 },
  };
  return profiles[mode];
}

function isWindowMode(mode: Mode): boolean {
  return mode === 'window' || mode === 'hsw_cr' || mode === 'oscore_like';
}

function wilsonCi(successes: number, total: number): { low: number; high: number } {
  if (total === 0) {
    return { low: 0, high: 0 };
  }
  const z = 1.96;
  const p = successes / total;
  const denom = 1 + (z * z) / total;
  const center = (p + (z * z) / (2 * total)) / denom;
  const margin = (z * Math.sqrt((p * (1 - p)) / total + (z * z) / (4 * total * total))) / denom;
  return {
    low: Math.max(0, center - margin),
    high: Math.min(1, center + margin),
  };
}

function mean(values: number[]): number {
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : 0;
}

function std(values: number[]): number {
  if (values.length < 2) {
    return 0;
  }
  const avg = mean(values);
  return Math.sqrt(values.reduce((total, value) => total + (value - avg) ** 2, 0) / (values.length - 1));
}

function safeDiv(value: number, total: number): number {
  return total > 0 ? value / total : 0;
}

function hashSeed(seed: number, mode: Mode, run: number): number {
  let hash = (seed + run * 0x9e3779b1) >>> 0;
  for (let index = 0; index < mode.length; index += 1) {
    hash = Math.imul(hash ^ mode.charCodeAt(index), 16777619) >>> 0;
  }
  return hash;
}
