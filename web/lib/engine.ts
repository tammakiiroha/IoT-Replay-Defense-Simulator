// Client-side simulation engine (ported from python sim/)

// --- Types ---
export type Mode = 'no_def' | 'rolling' | 'window' | 'challenge';

export interface SimulationConfig {
    modes: Mode[];
    runs: number;
    p_loss: number;
    p_reorder: number;
    window_size: number;
    num_legit: number;
    num_replay: number;
    attack_mode: 'post' | 'inline';
}

export interface SimulationResult {
    mode: Mode;
    runs: number;
    avg_legit_rate: number;
    std_legit_rate: number;
    avg_attack_rate: number;
    std_attack_rate: number;
}

interface Frame {
    seq: number;
    command: string;
    mac: string;
    nonce?: string;
    counter?: number;
    is_attack: boolean;
}

// --- Security Primitives ---
// Simple string hash for simulation purposes (faster than async crypto.subtle for this use case)
// We assume HMAC is perfect, so we just need a unique signature for (key + message)
function computeMac(token: number | string, command: string, _key: string): string {
    // const input = `${key}:${token}:${command}`;
    // Simple DJB2-like hash for demo speed, or use SHA256 if strictness needed.
    // For simulation logic correctness (replay vs fresh), uniqueness is what matters.
    // Let's use a simple distinct string generation to mimic a hash.
    return `SIG[${token}-${command}]`;
}

// --- Classes ---

class Receiver {
    mode: Mode;
    key: string;
    window_size: number;

    // State
    last_counter: number = -1;
    received_mask: number = 0; // for window
    expected_nonce: string | null = null; // for challenge

    constructor(mode: Mode, key: string, window_size: number) {
        this.mode = mode;
        this.key = key;
        this.window_size = window_size;
    }

    process(frame: Frame): { accepted: boolean; reason: string } {
        if (this.mode === 'no_def') {
            return { accepted: true, reason: 'no_defense' };
        }

        // Common security check
        const token = this.mode === 'challenge' ? frame.nonce : frame.counter;
        if (token === undefined || frame.mac === undefined) return { accepted: false, reason: 'missing_fields' };

        // Verify MAC
        const expected = computeMac(token, frame.command, this.key);
        if (frame.mac !== expected) return { accepted: false, reason: 'mac_mismatch' };

        if (this.mode === 'rolling') {
            const ctr = frame.counter as number;
            if (ctr <= this.last_counter) return { accepted: false, reason: 'replay' };
            this.last_counter = ctr;
            return { accepted: true, reason: 'ok' };
        }

        if (this.mode === 'window') {
            const ctr = frame.counter as number;
            if (this.last_counter < 0) {
                this.last_counter = ctr;
                this.received_mask = 1;
                return { accepted: true, reason: 'ok_init' };
            }

            const diff = ctr - this.last_counter;
            if (diff > 0) {
                // Advance window
                if (diff > this.window_size) return { accepted: false, reason: 'out_of_window_future' };
                this.received_mask = (this.received_mask << diff) | 1;
                // Cap mask size to avoid overflow if window is huge (JS bitwise is 32-bit safe, window=20 is fine)
                const mask_limit = (1 << this.window_size) - 1;
                this.received_mask &= mask_limit;
                this.last_counter = ctr;
                return { accepted: true, reason: 'ok_new' };
            } else {
                // Old frame
                const offset = -diff;
                if (offset >= this.window_size) return { accepted: false, reason: 'too_old' };
                if ((this.received_mask >> offset) & 1) return { accepted: false, reason: 'replay' };

                this.received_mask |= (1 << offset);
                return { accepted: true, reason: 'ok_old' };
            }
        }

        if (this.mode === 'challenge') {
            if (frame.nonce !== this.expected_nonce) return { accepted: false, reason: 'nonce_mismatch' };
            this.expected_nonce = null; // consume nonce
            return { accepted: true, reason: 'ok' };
        }

        return { accepted: false, reason: 'unknown_mode' };
    }

    issueNonce(): string {
        // Simple random nonce string
        const nonce = Math.random().toString(36).substring(2, 10);
        this.expected_nonce = nonce;
        return nonce;
    }
}

class Sender {
    seq: number = 0;
    key: string;
    mode: Mode;

    constructor(mode: Mode, key: string) {
        this.mode = mode;
        this.key = key;
    }

    nextFrame(command: string, nonce?: string): Frame {
        this.seq++;
        const frame: Frame = {
            seq: this.seq,
            command,
            mac: '',
            counter: this.seq, // used mainly for rolling/window
            is_attack: false,
        };

        if (this.mode === 'challenge') {
            frame.nonce = nonce;
            frame.mac = computeMac(nonce!, command, this.key);
            delete frame.counter; // counter not used in challenge
        } else if (this.mode !== 'no_def') {
            frame.mac = computeMac(this.seq, command, this.key);
        }

        return frame;
    }
}

class Attacker {
    observed: Frame[] = [];

    observe(frame: Frame) {
        // Deep copy to store the exact frame state at capture time
        this.observed.push(JSON.parse(JSON.stringify(frame)));
    }

    pickFrame(): Frame | null {
        if (this.observed.length === 0) return null;
        const idx = Math.floor(Math.random() * this.observed.length);
        const f = JSON.parse(JSON.stringify(this.observed[idx]));
        return f;
    }
}

class Channel {
    p_loss: number;
    p_reorder: number;
    buffer: Frame[] = []; // for reordering

    constructor(p_loss: number, p_reorder: number) {
        this.p_loss = p_loss;
        this.p_reorder = p_reorder;
    }

    send(frame: Frame): Frame[] {
        // 1. Loss
        if (Math.random() < this.p_loss) return [];

        // 2. Reordering
        // If reorder, hold in buffer. 
        // Simplified logic: p_reorder chance to hold, else flush buffer + current.
        if (Math.random() < this.p_reorder) {
            this.buffer.push(frame);
            return [];
        } else {
            const output = [...this.buffer, frame];
            this.buffer = [];
            return output;
        }
    }

    flush(): Frame[] {
        const out = [...this.buffer];
        this.buffer = [];
        return out;
    }
}

// --- Runner ---

async function simulateOneRun(config: SimulationConfig, mode: Mode): Promise<{ legit_acc: number; attack_succ: number }> {
    // Config
    const KEY = "secret";
    const sender = new Sender(mode, KEY);
    const receiver = new Receiver(mode, KEY, config.window_size);
    const attacker = new Attacker();
    const channel = new Channel(config.p_loss, config.p_reorder);

    let legit_acc = 0;
    let attack_succ = 0;
    // let remaining_replays = config.num_replay;

    const processArrived = (frames: Frame[]) => {
        for (const f of frames) {
            const res = receiver.process(f);
            if (res.accepted) {
                if (f.is_attack) attack_succ++;
                else legit_acc++;
            }
        }
    };

    // 1. Legitimate Phase
    for (let i = 0; i < config.num_legit; i++) {
        const cmd = "CMD_A"; // simple command
        let nonce: string | undefined;

        if (mode === 'challenge') {
            nonce = receiver.issueNonce();
        }

        const frame = sender.nextFrame(cmd, nonce);
        attacker.observe(frame);

        const arrived = channel.send(frame);
        processArrived(arrived);

        // INLINE attack not implemented for simplicity in this demo port, 
        // mirroring default 'post' behavior usually preferred.
    }

    // Flush before attacks (if POST mode)
    processArrived(channel.flush());

    // 2. Replay Phase (POST)
    for (let i = 0; i < config.num_replay; i++) {
        const attackFrame = attacker.pickFrame();
        if (attackFrame) {
            attackFrame.is_attack = true;
            const arrived = channel.send(attackFrame);
            processArrived(arrived);
        }
    }
    processArrived(channel.flush());

    return { legit_acc, attack_succ };
}

// Main helper
function calcMean(vals: number[]) {
    if (vals.length === 0) return 0;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function calcStd(vals: number[]) {
    if (vals.length < 2) return 0;
    const mean = calcMean(vals);
    const variance = vals.reduce((a, b) => a + (b - mean) ** 2, 0) / (vals.length - 1);
    return Math.sqrt(variance);
}

export async function runSimulation(config: SimulationConfig): Promise<SimulationResult[]> {
    const results: SimulationResult[] = [];

    for (const mode of config.modes) {
        const legit_rates: number[] = [];
        const attack_rates: number[] = [];

        for (let r = 0; r < config.runs; r++) {
            const res = await simulateOneRun(config, mode);

            // Calculate rates
            // Legit rate = accepted / sent
            // Attack success = success / attempts (assuming config.num_replay attempts)

            legit_rates.push(res.legit_acc / config.num_legit);
            attack_rates.push(res.attack_succ / config.num_replay);
        }

        results.push({
            mode,
            runs: config.runs,
            avg_legit_rate: calcMean(legit_rates),
            std_legit_rate: calcStd(legit_rates),
            avg_attack_rate: calcMean(attack_rates),
            std_attack_rate: calcStd(attack_rates),
        });
    }

    return results;
}
