"""Experiment runner that stitches together all simulation components."""
from __future__ import annotations

import dataclasses
import heapq
import statistics
import sys
import time
from collections.abc import Sequence

from .attacker import Attacker
from .auth import AsconAeadAuthenticator, Authenticator, HmacAuthenticator
from .channel import Channel
from .channel_models import GilbertElliottLoss, IidLoss, LossModel, ReorderDelay, TraceLoss
from .cost import CostModel, CostStats, estimate_energy
from .receiver import Receiver
from .rng import DeterministicRNG, RandomLike
from .sender import Sender
from .stats import wilson_ci
from .trace import ScenarioTrace, generate_trace
from .types import (
    WINDOW_SIZED_MODES,
    AggregateStats,
    AttackMode,
    Frame,
    Mode,
    SimulationConfig,
    SimulationRunResult,
)


def _resolve_rng(rng: RandomLike | None, seed: int | None) -> RandomLike:
    if rng is not None:
        return rng
    return DeterministicRNG(seed)


def _choose_command(config: SimulationConfig, index: int, rng: RandomLike) -> str:
    if config.command_sequence:
        sequence = config.command_sequence
        if not sequence:
            raise ValueError("Provided command sequence is empty")
        return sequence[index % len(sequence)]
    command_space = config.effective_command_set()
    if not command_space:
        raise ValueError("Command set is empty")
    return rng.choice(list(command_space))


def _tag_bits(config: SimulationConfig) -> int:
    return config.mac_tag_bits or config.mac_length * 4


def _authenticator(config: SimulationConfig) -> Authenticator:
    tag_bits = _tag_bits(config)
    if config.auth_profile == "ascon":
        return AsconAeadAuthenticator(config.shared_key, tag_bits=tag_bits)
    return HmacAuthenticator(config.shared_key, tag_bits=tag_bits)


def _loss_model(config: SimulationConfig) -> LossModel:
    if config.channel_model == "gilbert_elliott":
        return GilbertElliottLoss(
            p_good_to_bad=config.burst_p_good_to_bad,
            p_bad_to_good=config.burst_p_bad_to_good,
            loss_good=config.loss_good,
            loss_bad=config.loss_bad,
        )
    if config.channel_model == "trace":
        return TraceLoss(list(config.loss_trace or []))
    return IidLoss(config.p_loss)


def _frame_bytes(frame: Frame, tag_bits: int, nonce_bits: int) -> int:
    size = len(frame.command.encode("utf-8"))
    if frame.counter is not None:
        size += 4
    if frame.nonce is not None:
        size += max(1, (nonce_bits + 7) // 8)
    if frame.mac is not None:
        size += max(1, (tag_bits + 7) // 8)
    return size


def _state_bytes(config: SimulationConfig, receiver: Receiver) -> int:
    window_bytes = max(1, (max(config.window_size, 1) + 7) // 8)
    nonce_bytes = len(receiver.state.outstanding_nonces) * max(
        1,
        (config.challenge_nonce_bits + 7) // 8,
    )
    return window_bytes + nonce_bytes


def _should_challenge(config: SimulationConfig, command: str) -> bool:
    if config.mode is Mode.CHALLENGE:
        return True
    if config.mode is Mode.HSW_CR:
        return (config.command_risk or {}).get(command, 0.0) >= config.risk_high
    return False


def simulate_one_run(
    config: SimulationConfig,
    rng: RandomLike | None = None,
) -> SimulationRunResult:
    """Simulate one round of legitimate traffic followed by replay attempts."""

    local_rng = _resolve_rng(rng, config.rng_seed)
    tag_bits = _tag_bits(config)
    authenticator = _authenticator(config)

    sender = Sender(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=max(1, tag_bits // 4),
        authenticator=authenticator,
    )
    receiver = Receiver(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=max(1, tag_bits // 4),
        window_size=config.window_size or 1,
        g_hard=config.g_hard,
        authenticator=authenticator,
        max_outstanding_challenges=config.max_outstanding_challenges,
        challenge_ttl_ticks=config.challenge_ttl_ticks,
        command_risk=config.command_risk,
        risk_high=config.risk_high,
    )
    attacker = Attacker(
        record_loss=config.attacker_record_loss,
        target_commands=config.target_commands,
    )
    channel = Channel(
        p_loss=config.p_loss,
        p_reorder=config.p_reorder,
        rng=local_rng,
        loss_model=_loss_model(config),
        delay_model=ReorderDelay(config.p_reorder),
    )

    legit_sent = 0
    legit_accepted = 0
    attack_attempts = 0
    attack_success = 0
    remaining_replays = config.num_replay
    cost_stats = CostStats()

    def record_tx(frame: Frame) -> None:
        size = _frame_bytes(frame, tag_bits, config.challenge_nonce_bits)
        cost_stats.tx_bytes += size
        if frame.mac is not None:
            if authenticator.profile == "ascon":
                cost_stats.ascon_ops += 1
            else:
                cost_stats.hmac_ops += 1
        cost_stats.state_bytes_peak = max(
            cost_stats.state_bytes_peak,
            _state_bytes(config, receiver),
        )

    def process_arrived(frames: list[Frame]) -> None:
        nonlocal attack_success, legit_accepted
        for frame in frames:
            cost_stats.rx_bytes += _frame_bytes(frame, tag_bits, config.challenge_nonce_bits)
            result = receiver.process(frame)
            if frame.mac is not None:
                if authenticator.profile == "ascon":
                    cost_stats.ascon_ops += 1
                else:
                    cost_stats.hmac_ops += 1
            cost_stats.state_bytes_peak = max(
                cost_stats.state_bytes_peak,
                _state_bytes(config, receiver),
            )
            if result.accepted:
                cost_stats.accepted_frames += 1
                if frame.is_attack:
                    attack_success += 1
                else:
                    legit_accepted += 1

    for index in range(config.num_legit):
        command = _choose_command(config, index, local_rng)
        nonce = None
        if _should_challenge(config, command):
            nonce = receiver.issue_nonce(
                local_rng,
                bits=config.challenge_nonce_bits,
                tick=index + 1,
            )
            cost_stats.challenge_round_trips += 1

        frame = sender.next_frame(command, nonce=nonce)
        record_tx(frame)
        legit_sent += 1
        attacker.observe(frame, local_rng)
        process_arrived(channel.send(frame))

        if config.attack_mode is AttackMode.INLINE:
            for _ in range(max(1, config.inline_attack_burst)):
                if remaining_replays <= 0:
                    break
                if local_rng.random() >= config.inline_attack_probability:
                    break
                attack_frame = attacker.pick_frame(local_rng)
                if attack_frame is None:
                    break

                attack_attempts += 1
                remaining_replays -= 1
                attack_frame.is_attack = True
                record_tx(attack_frame)
                process_arrived(channel.send(attack_frame))

    if config.attack_mode is AttackMode.POST_RUN:
        process_arrived(channel.flush())
        for _ in range(remaining_replays):
            attack_frame = attacker.pick_frame(local_rng)
            if attack_frame is None:
                break
            attack_attempts += 1
            attack_frame.is_attack = True
            record_tx(attack_frame)
            process_arrived(channel.send(attack_frame))

    process_arrived(channel.flush())

    energy = estimate_energy(cost_stats, CostModel())
    legit_rate = legit_accepted / legit_sent if legit_sent else 0.0
    crypto_ops = cost_stats.hmac_ops + cost_stats.ascon_ops
    return SimulationRunResult(
        legit_sent=legit_sent,
        legit_accepted=legit_accepted,
        attack_attempts=attack_attempts,
        attack_success=attack_success,
        mode=config.mode,
        frr=1.0 - legit_rate,
        energy_proxy=energy,
        bytes_overhead=float(cost_stats.tx_bytes + cost_stats.rx_bytes),
        state_bytes=float(cost_stats.state_bytes_peak),
        latency_ticks=(
            cost_stats.latency_ticks_sum / cost_stats.accepted_frames
            if cost_stats.accepted_frames
            else 0.0
        ),
        crypto_ops=float(crypto_ops),
        challenge_round_trips=float(cost_stats.challenge_round_trips),
        metadata={
            "p_loss": config.p_loss,
            "p_reorder": config.p_reorder,
            "window_size": config.window_size,
            "attack_mode": config.attack_mode.value,
            "auth_profile": authenticator.profile,
        },
    )


def _aggregate_results(
    config: SimulationConfig,
    mode: Mode,
    results: list[SimulationRunResult],
    metadata: dict[str, object],
) -> AggregateStats:
    legit_rates = [result.legit_accept_rate for result in results]
    attack_rates = [result.attack_success_rate for result in results]
    legit_accepted = sum(result.legit_accepted for result in results)
    legit_total = sum(result.legit_sent for result in results)
    attack_accepted = sum(result.attack_success for result in results)
    attack_total = sum(result.attack_attempts for result in results)
    lar_ci = wilson_ci(legit_accepted, legit_total)
    asr_ci = wilson_ci(attack_accepted, attack_total)
    window_value = config.window_size if mode in WINDOW_SIZED_MODES else 0
    return AggregateStats(
        mode=mode,
        runs=len(results),
        avg_legit_rate=_mean(legit_rates),
        std_legit_rate=_std(legit_rates),
        avg_attack_rate=_mean(attack_rates),
        std_attack_rate=_std(attack_rates),
        p_loss=config.p_loss,
        p_reorder=config.p_reorder,
        window_size=window_value,
        num_legit=config.num_legit,
        num_replay=config.num_replay,
        attack_mode=config.attack_mode,
        legit_accepted=legit_accepted,
        legit_total=legit_total,
        attack_accepted=attack_accepted,
        attack_total=attack_total,
        lar_ci_low=lar_ci.lower,
        lar_ci_high=lar_ci.upper,
        asr_ci_low=asr_ci.lower,
        asr_ci_high=asr_ci.upper,
        frr=_mean([result.frr for result in results]),
        energy_proxy=_mean([result.energy_proxy for result in results]),
        bytes_overhead=_mean([result.bytes_overhead for result in results]),
        state_bytes=_mean([result.state_bytes for result in results]),
        latency_ticks=_mean([result.latency_ticks for result in results]),
        crypto_ops=_mean([result.crypto_ops for result in results]),
        challenge_round_trips=_mean([result.challenge_round_trips for result in results]),
        mac_tag_bits=_tag_bits(config),
        auth_profile=config.auth_profile,
        metadata=metadata,
    )


def run_many_experiments(
    base_config: SimulationConfig,
    modes: Sequence[Mode],
    runs: int,
    seed: int | None = None,
    show_progress: bool = True,
) -> list[AggregateStats]:
    """Run multiple Monte Carlo trials for each requested mode with visual progress."""

    start_time = time.time()
    per_mode_configs = {mode: dataclasses.replace(base_config, mode=mode) for mode in modes}
    per_mode_results: dict[Mode, list[SimulationRunResult]] = {mode: [] for mode in modes}

    if show_progress:
        print("\n" + "=" * 80)
        print("STARTING MONTE CARLO SIMULATION")
        print("=" * 80 + "\n")

    for mode in modes:
        mode_rng = DeterministicRNG(seed)
        for run_idx in range(runs):
            scenario_seed = mode_rng.randint(0, 2**31 - 1)
            scenario_rng = DeterministicRNG(scenario_seed)
            result = simulate_one_run(per_mode_configs[mode], rng=scenario_rng)
            per_mode_results[mode].append(result)

            if show_progress and ((run_idx + 1) % 10 == 0 or run_idx == runs - 1):
                bar_length = 50
                filled = int(bar_length * (run_idx + 1) / runs)
                bar = "#" * filled + "." * (bar_length - filled)
                sys.stdout.write(f"\r   Progress: [{bar}] {run_idx + 1}/{runs} runs")
                sys.stdout.flush()
        if show_progress:
            print()

    total_time = time.time() - start_time
    perf_metadata = {
        "total_time": total_time,
        "time_per_run": total_time / (len(modes) * runs) if runs > 0 else 0,
        "total_runs": len(modes) * runs,
    }
    return [
        _aggregate_results(config, mode, per_mode_results[mode], dict(perf_metadata))
        for mode, config in per_mode_configs.items()
    ]


def run_until_precision(
    config: SimulationConfig,
    *,
    mode: Mode,
    target_half_width: float,
    max_runs: int,
    seed: int | None,
    min_runs: int = 30,
    metric: str = "asr",
) -> tuple[AggregateStats, int]:
    cfg = dataclasses.replace(config, mode=mode)
    mode_rng = DeterministicRNG(seed)
    results: list[SimulationRunResult] = []
    for _ in range(max_runs):
        scenario_seed = mode_rng.randint(0, 2**31 - 1)
        results.append(simulate_one_run(cfg, rng=DeterministicRNG(scenario_seed)))
        if len(results) >= min_runs:
            legit_accepted = sum(result.legit_accepted for result in results)
            legit_total = sum(result.legit_sent for result in results)
            attack_accepted = sum(result.attack_success for result in results)
            attack_total = sum(result.attack_attempts for result in results)
            ci = (
                wilson_ci(attack_accepted, attack_total)
                if metric == "asr"
                else wilson_ci(legit_accepted, legit_total)
            )
            if ci.half_width <= target_half_width:
                break
    stats = _aggregate_results(
        cfg,
        mode,
        results,
        {"stopping": "sequential", "target_half_width": target_half_width},
    )
    return stats, len(results)


def simulate_one_run_with_trace(
    config: SimulationConfig,
    trace: ScenarioTrace,
    *,
    nonce_seed: int | None = None,
) -> SimulationRunResult:
    """Simulate one run while consuming a pre-generated channel/attacker trace."""

    tag_bits = _tag_bits(config)
    authenticator = _authenticator(config)
    nonce_rng = DeterministicRNG(nonce_seed)
    sender = Sender(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=max(1, tag_bits // 4),
        authenticator=authenticator,
    )
    receiver = Receiver(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=max(1, tag_bits // 4),
        window_size=config.window_size or 1,
        g_hard=config.g_hard,
        authenticator=authenticator,
        max_outstanding_challenges=config.max_outstanding_challenges,
        challenge_ttl_ticks=config.challenge_ttl_ticks,
        command_risk=config.command_risk,
        risk_high=config.risk_high,
    )

    tick = 0
    seq = 0
    scheduled: list[tuple[int, int, Frame]] = []
    recorded: list[Frame] = []
    legit_sent = 0
    legit_accepted = 0
    attack_attempts = 0
    attack_success = 0
    remaining_replays = config.num_replay
    replay_index = 0
    inline_slot = 0
    cost_stats = CostStats()

    def record_tx(frame: Frame) -> None:
        size = _frame_bytes(frame, tag_bits, config.challenge_nonce_bits)
        cost_stats.tx_bytes += size
        if frame.mac is not None:
            if authenticator.profile == "ascon":
                cost_stats.ascon_ops += 1
            else:
                cost_stats.hmac_ops += 1
        cost_stats.state_bytes_peak = max(
            cost_stats.state_bytes_peak,
            _state_bytes(config, receiver),
        )

    def process_arrived(frames: list[Frame]) -> None:
        nonlocal attack_success, legit_accepted
        for frame in frames:
            cost_stats.rx_bytes += _frame_bytes(frame, tag_bits, config.challenge_nonce_bits)
            result = receiver.process(frame)
            if frame.mac is not None:
                if authenticator.profile == "ascon":
                    cost_stats.ascon_ops += 1
                else:
                    cost_stats.hmac_ops += 1
            cost_stats.state_bytes_peak = max(
                cost_stats.state_bytes_peak,
                _state_bytes(config, receiver),
            )
            if result.accepted:
                cost_stats.accepted_frames += 1
                if frame.is_attack:
                    attack_success += 1
                else:
                    legit_accepted += 1

    def send_traced(frame: Frame, *, dropped: bool, delay: int) -> list[Frame]:
        nonlocal tick, seq
        tick += 1
        if not dropped:
            heapq.heappush(scheduled, (tick + delay, seq, frame))
            seq += 1
        arrived: list[Frame] = []
        while scheduled and scheduled[0][0] <= tick:
            arrived.append(heapq.heappop(scheduled)[2])
        return arrived

    def flush_traced() -> list[Frame]:
        arrived: list[Frame] = []
        while scheduled:
            arrived.append(heapq.heappop(scheduled)[2])
        return arrived

    def pick_replay(raw_pick: int) -> Frame | None:
        if config.target_commands:
            targets = set(config.target_commands)
            candidates = [frame for frame in recorded if frame.command in targets]
        else:
            candidates = recorded
        if not candidates:
            return None
        return candidates[raw_pick % len(candidates)].clone()

    def attempt_replay() -> bool:
        nonlocal attack_attempts, attack_success, remaining_replays, replay_index
        if remaining_replays <= 0 or replay_index >= len(trace.replay_pick):
            return False
        attack_frame = pick_replay(trace.replay_pick[replay_index])
        if attack_frame is None:
            return False
        attack_frame.is_attack = True
        attack_attempts += 1
        remaining_replays -= 1
        record_tx(attack_frame)
        process_arrived(
            send_traced(
                attack_frame,
                dropped=trace.replay_dropped[replay_index],
                delay=trace.replay_delay[replay_index],
            )
        )
        replay_index += 1
        return True

    for index, command in enumerate(trace.commands[: config.num_legit]):
        nonce = None
        if _should_challenge(config, command):
            nonce = receiver.issue_nonce(
                nonce_rng,
                bits=config.challenge_nonce_bits,
                tick=index + 1,
            )
            cost_stats.challenge_round_trips += 1

        frame = sender.next_frame(command, nonce=nonce)
        record_tx(frame)
        legit_sent += 1
        if not trace.attacker_record_dropped[index]:
            recorded.append(frame.clone())
        process_arrived(
            send_traced(
                frame,
                dropped=trace.legit_dropped[index],
                delay=trace.legit_delay[index],
            )
        )

        if config.attack_mode is AttackMode.INLINE:
            for _ in range(max(1, config.inline_attack_burst)):
                if inline_slot >= len(trace.inline_attempt):
                    break
                should_attempt = trace.inline_attempt[inline_slot]
                inline_slot += 1
                if not should_attempt:
                    break
                if not attempt_replay():
                    break

    if config.attack_mode is AttackMode.POST_RUN:
        process_arrived(flush_traced())
        for _ in range(remaining_replays):
            if not attempt_replay():
                break

    process_arrived(flush_traced())

    energy = estimate_energy(cost_stats, CostModel())
    legit_rate = legit_accepted / legit_sent if legit_sent else 0.0
    crypto_ops = cost_stats.hmac_ops + cost_stats.ascon_ops
    return SimulationRunResult(
        legit_sent=legit_sent,
        legit_accepted=legit_accepted,
        attack_attempts=attack_attempts,
        attack_success=attack_success,
        mode=config.mode,
        frr=1.0 - legit_rate,
        energy_proxy=energy,
        bytes_overhead=float(cost_stats.tx_bytes + cost_stats.rx_bytes),
        state_bytes=float(cost_stats.state_bytes_peak),
        latency_ticks=(
            cost_stats.latency_ticks_sum / cost_stats.accepted_frames
            if cost_stats.accepted_frames
            else 0.0
        ),
        crypto_ops=float(crypto_ops),
        challenge_round_trips=float(cost_stats.challenge_round_trips),
        metadata={
            "p_loss": config.p_loss,
            "p_reorder": config.p_reorder,
            "window_size": config.window_size,
            "attack_mode": config.attack_mode.value,
            "auth_profile": authenticator.profile,
            "trace_digest": trace.digest(),
            "legit_drop_count": trace.legit_drop_count,
        },
    )


def run_paired_experiments(
    base_config: SimulationConfig,
    modes: Sequence[Mode],
    runs: int,
    seed: int | None = None,
    show_progress: bool = True,
) -> list[AggregateStats]:
    trace_rng = DeterministicRNG(seed)
    trace_seeds = [trace_rng.randint(0, 2**31 - 1) for _ in range(runs)]
    traces = [generate_trace(base_config, trace_seed) for trace_seed in trace_seeds]
    trace_digests = [trace.digest() for trace in traces]
    legit_drop_counts = [trace.legit_drop_count for trace in traces]
    per_mode_configs = {mode: dataclasses.replace(base_config, mode=mode) for mode in modes}
    per_mode_results: dict[Mode, list[SimulationRunResult]] = {mode: [] for mode in modes}

    if show_progress:
        print("\n" + "=" * 80)
        print("STARTING PAIRED MONTE CARLO SIMULATION")
        print("=" * 80 + "\n")

    for run_idx, (trace_seed, trace) in enumerate(zip(trace_seeds, traces)):
        for mode, config in per_mode_configs.items():
            mode_seed = trace_seed + sum(mode.value.encode("utf-8"))
            per_mode_results[mode].append(
                simulate_one_run_with_trace(config, trace, nonce_seed=mode_seed)
            )
        if show_progress and ((run_idx + 1) % 10 == 0 or run_idx == runs - 1):
            bar_length = 50
            filled = int(bar_length * (run_idx + 1) / runs)
            bar = "#" * filled + "." * (bar_length - filled)
            sys.stdout.write(f"\r   Progress: [{bar}] {run_idx + 1}/{runs} runs")
            sys.stdout.flush()

    if show_progress:
        print()

    stats: list[AggregateStats] = []
    for mode, config in per_mode_configs.items():
        stats.append(
            _aggregate_results(
                config,
                mode,
                per_mode_results[mode],
                {
                    "paired": True,
                    "trace_digests": trace_digests,
                    "legit_drop_counts_by_run": legit_drop_counts,
                },
            )
        )
    return stats


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.fmean(values)


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return statistics.stdev(values)
