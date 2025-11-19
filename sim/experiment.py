"""Experiment runner that stitches together all simulation components."""
from __future__ import annotations

import dataclasses
import random
import statistics
import sys
import time
from typing import Iterable, List, Optional, Sequence

from .attacker import Attacker
from .channel import Channel
from .receiver import Receiver
from .sender import Sender
from .types import (
    AggregateStats,
    AttackMode,
    Mode,
    SimulationConfig,
    SimulationRunResult,
    Frame,
)


def _resolve_rng(rng: Optional[random.Random], seed: Optional[int]) -> random.Random:
    if rng is not None:
        return rng
    return random.Random(seed)


def _choose_command(config: SimulationConfig, index: int, rng: random.Random) -> str:
    if config.command_sequence:
        sequence = config.command_sequence
        if not sequence:
            raise ValueError("Provided command sequence is empty")
        return sequence[index % len(sequence)]
    command_space = config.effective_command_set()
    if not command_space:
        raise ValueError("Command set is empty")
    return rng.choice(list(command_space))


def simulate_one_run(
    config: SimulationConfig,
    rng: Optional[random.Random] = None,
) -> SimulationRunResult:
    """Simulate one round of legitimate traffic followed by replay attempts."""

    local_rng = _resolve_rng(rng, config.rng_seed)

    sender = Sender(mode=config.mode, shared_key=config.shared_key, mac_length=config.mac_length)
    receiver = Receiver(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=config.mac_length,
        window_size=config.window_size or 1,
    )
    attacker = Attacker(
        record_loss=config.attacker_record_loss,
        target_commands=config.target_commands
    )
    channel = Channel(p_loss=config.p_loss, p_reorder=config.p_reorder, rng=local_rng)

    legit_sent = 0
    legit_accepted = 0
    attack_attempts = 0
    attack_success = 0

    def process_arrived(frames: List[Frame]):
        nonlocal legit_accepted, attack_success
        for f in frames:
            result = receiver.process(f)
            if result.accepted:
                if f.is_attack:
                    attack_success += 1
                else:
                    legit_accepted += 1

    for i in range(config.num_legit):
        command = _choose_command(config, i, local_rng)
        nonce = None
        if config.mode is Mode.CHALLENGE:
            nonce = receiver.issue_nonce(local_rng, bits=config.challenge_nonce_bits)
        
        # 1. Legitimate Transmission
        frame = sender.next_frame(command, nonce=nonce)
        legit_sent += 1
        
        # Attacker observes BEFORE channel effects (assuming close proximity to sender)
        attacker.observe(frame, local_rng)

        # Send through channel
        arrived = channel.send(frame)
        process_arrived(arrived)

        # 2. Inline Attacks
        if config.attack_mode is AttackMode.INLINE:
            for _ in range(max(1, config.inline_attack_burst)):
                if local_rng.random() >= config.inline_attack_probability:
                    break
                attack_frame = attacker.pick_frame(local_rng)
                if attack_frame is None:
                    break
                
                attack_attempts += 1
                attack_frame.is_attack = True
                arrived_attack = channel.send(attack_frame)
                process_arrived(arrived_attack)

    # 3. Post-Run Attacks
    if config.attack_mode is AttackMode.POST_RUN:
        # Flush channel first? No, keep it running.
        # But usually post-run implies legitimate traffic has stopped.
        # We should probably flush the channel of legitimate frames before starting post-run?
        # Or just let them mix. Let's let them mix, but usually channel is empty by now if no delay.
        
        for _ in range(config.num_replay):
            attack_frame = attacker.pick_frame(local_rng)
            if attack_frame is None:
                break
            
            attack_attempts += 1
            attack_frame.is_attack = True
            arrived_attack = channel.send(attack_frame)
            process_arrived(arrived_attack)

    # Flush any remaining frames in the channel
    remaining = channel.flush()
    process_arrived(remaining)

    return SimulationRunResult(
        legit_sent=legit_sent,
        legit_accepted=legit_accepted,
        attack_attempts=attack_attempts,
        attack_success=attack_success,
        mode=config.mode,
        metadata={
            "p_loss": config.p_loss,
            "p_reorder": config.p_reorder,
            "window_size": config.window_size,
            "attack_mode": config.attack_mode.value,
        },
    )


def run_many_experiments(
    base_config: SimulationConfig,
    modes: Sequence[Mode],
    runs: int,
    seed: Optional[int] = None,
    show_progress: bool = True,
) -> List[AggregateStats]:
    """Run multiple Monte Carlo trials for each requested mode with visual progress."""

    master_rng = random.Random(seed)
    per_mode_stats = {
        mode: {
            "config": dataclasses.replace(base_config, mode=mode),
            "legit": [],
            "attack": [],
        }
        for mode in modes
    }

    if show_progress:
        print("\n" + "="*80)
        print("🚀 STARTING MONTE CARLO SIMULATION")
        print("="*80 + "\n")

    for mode in modes:
        buckets = per_mode_stats[mode]
        
        if show_progress:
            print(f"\n{'='*80}")
            print(f"🛡️  TESTING DEFENSE MODE: {mode.value.upper()}")
            print(f"{'='*80}\n")
        
        # Reset RNG for consistent run
        mode_rng = random.Random(seed)
        
        for run_idx in range(runs):
            scenario_seed = mode_rng.randint(0, 2**31 - 1)
            scenario_rng = random.Random(scenario_seed)
            result = simulate_one_run(buckets["config"], rng=scenario_rng)
            buckets["legit"].append(result.legit_accept_rate)
            buckets["attack"].append(result.attack_success_rate)
            
            # Show progress
            if show_progress and ((run_idx + 1) % 10 == 0 or run_idx == runs - 1):
                bar_length = 50
                filled = int(bar_length * (run_idx + 1) / runs)
                bar = "█" * filled + "░" * (bar_length - filled)
                
                sys.stdout.write(f"\r   Progress: [{bar}] {run_idx + 1}/{runs} runs")
                sys.stdout.flush()
                
                # Show interim results
                if (run_idx + 1) % 50 == 0 or run_idx == runs - 1:
                    avg_legit = _mean(buckets["legit"])
                    avg_attack = _mean(buckets["attack"])
                    print(f"\n   ├─ Legit Accept: {avg_legit*100:.1f}% | Attack Success: {avg_attack*100:.1f}%")
        
        if show_progress:
            print()  # New line after progress bar
            
            # Show final stats for this mode
            avg_legit = _mean(buckets["legit"])
            avg_attack = _mean(buckets["attack"])
            std_legit = _std(buckets["legit"])
            std_attack = _std(buckets["attack"])
            
            print(f"\n   ✓ Mode '{mode.value}' completed:")
            print(f"     ├─ Legitimate Acceptance: {avg_legit*100:.2f}% ± {std_legit*100:.2f}%")
            print(f"     └─ Attack Success Rate: {avg_attack*100:.2f}% ± {std_attack*100:.2f}%")
            time.sleep(0.2)

    aggregates: List[AggregateStats] = []
    for mode, buckets in per_mode_stats.items():
        config = buckets["config"]
        window_value = config.window_size if mode is Mode.WINDOW else 0
        aggregates.append(
            AggregateStats(
                mode=mode,
                runs=len(buckets["legit"]),
                avg_legit_rate=_mean(buckets["legit"]),
                std_legit_rate=_std(buckets["legit"]),
                avg_attack_rate=_mean(buckets["attack"]),
                std_attack_rate=_std(buckets["attack"]),
                p_loss=config.p_loss,
                p_reorder=config.p_reorder,
                window_size=window_value,
                num_legit=config.num_legit,
                num_replay=config.num_replay,
                attack_mode=config.attack_mode,
            )
        )

    if show_progress:
        print("\n" + "="*80)
        print("SIMULATION COMPLETE - FINAL RESULTS")
        print("="*80 + "\n")

    return aggregates


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return statistics.fmean(values)


def _std(values: Iterable[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)
