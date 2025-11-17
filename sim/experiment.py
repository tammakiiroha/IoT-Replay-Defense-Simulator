"""Experiment runner that stitches together all simulation components."""
from __future__ import annotations

import dataclasses
import random
import statistics
from typing import Iterable, List, Optional, Sequence

from .attacker import Attacker
from .channel import should_drop
from .receiver import Receiver
from .sender import Sender
from .types import (
    AggregateStats,
    AttackMode,
    Mode,
    SimulationConfig,
    SimulationRunResult,
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
    attacker = Attacker(record_loss=config.attacker_record_loss)

    legit_sent = 0
    legit_accepted = 0
    attack_attempts = 0
    attack_success = 0

    for i in range(config.num_legit):
        command = _choose_command(config, i, local_rng)
        nonce = None
        if config.mode is Mode.CHALLENGE:
            nonce = receiver.issue_nonce(local_rng, bits=config.challenge_nonce_bits)
        frame = sender.next_frame(command, nonce=nonce)
        legit_sent += 1
        if not should_drop(config.p_loss, local_rng):
            result = receiver.process(frame)
            if result.accepted:
                legit_accepted += 1

        if config.attack_mode is AttackMode.INLINE:
            attempts, successes = _execute_inline_attacks(attacker, receiver, config, local_rng)
            attack_attempts += attempts
            attack_success += successes

        attacker.observe(frame, local_rng)

    if config.attack_mode is AttackMode.POST_RUN:
        post_attempts, post_success = _execute_post_run_attacks(attacker, receiver, config, local_rng)
        attack_attempts += post_attempts
        attack_success += post_success

    return SimulationRunResult(
        legit_sent=legit_sent,
        legit_accepted=legit_accepted,
        attack_attempts=attack_attempts,
        attack_success=attack_success,
        mode=config.mode,
        metadata={
            "p_loss": config.p_loss,
            "window_size": config.window_size,
            "attack_mode": config.attack_mode.value,
        },
    )


def run_many_experiments(
    base_config: SimulationConfig,
    modes: Sequence[Mode],
    runs: int,
    seed: Optional[int] = None,
) -> List[AggregateStats]:
    """Run multiple Monte Carlo trials for each requested mode."""

    master_rng = random.Random(seed)
    aggregates: List[AggregateStats] = []

    for mode in modes:
        config = dataclasses.replace(base_config, mode=mode)
        legit_rates: List[float] = []
        attack_rates: List[float] = []

        for _ in range(runs):
            child_seed = master_rng.randint(0, 2**31 - 1)
            result = simulate_one_run(config, rng=random.Random(child_seed))
            legit_rates.append(result.legit_accept_rate)
            attack_rates.append(result.attack_success_rate)

        window_value = config.window_size if mode is Mode.WINDOW else 0

        aggregates.append(
            AggregateStats(
                mode=mode,
                runs=len(legit_rates),
                avg_legit_rate=_mean(legit_rates),
                std_legit_rate=_std(legit_rates),
                avg_attack_rate=_mean(attack_rates),
                std_attack_rate=_std(attack_rates),
                p_loss=config.p_loss,
                window_size=window_value,
                num_legit=config.num_legit,
                num_replay=config.num_replay,
                attack_mode=config.attack_mode,
            )
        )

    return aggregates


def _execute_inline_attacks(
    attacker: Attacker,
    receiver: Receiver,
    config: SimulationConfig,
    rng: random.Random,
) -> tuple[int, int]:
    attempts = 0
    successes = 0

    for _ in range(max(1, config.inline_attack_burst)):
        if rng.random() >= config.inline_attack_probability:
            break
        frame = attacker.pick_frame(rng)
        if frame is None:
            break
        attempts += 1
        if should_drop(config.p_loss, rng):
            continue
        result = receiver.process(frame)
        if result.accepted:
            successes += 1

    return attempts, successes


def _execute_post_run_attacks(
    attacker: Attacker,
    receiver: Receiver,
    config: SimulationConfig,
    rng: random.Random,
) -> tuple[int, int]:
    attempts = 0
    successes = 0
    for _ in range(config.num_replay):
        frame = attacker.pick_frame(rng)
        if frame is None:
            break
        attempts += 1
        if should_drop(config.p_loss, rng):
            continue
        result = receiver.process(frame)
        if result.accepted:
            successes += 1
    return attempts, successes


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
