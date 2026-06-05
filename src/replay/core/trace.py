"""Pre-generated scenario traces for paired common-random-number experiments."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .rng import DeterministicRNG, RandomLike
from .types import SimulationConfig


@dataclass(frozen=True)
class ScenarioTrace:
    commands: list[str]
    legit_dropped: list[bool]
    legit_delay: list[int]
    attacker_record_dropped: list[bool]
    inline_attempt: list[bool]
    replay_pick: list[int]
    replay_dropped: list[bool]
    replay_delay: list[int]

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    @property
    def legit_drop_count(self) -> int:
        return sum(1 for dropped in self.legit_dropped if dropped)


def _dropped(rng: RandomLike, probability: float) -> bool:
    return probability > 0.0 and rng.random() < probability


def _delay(rng: RandomLike, probability: float) -> int:
    return rng.randint(1, 3) if _dropped(rng, probability) else 0


def generate_trace(config: SimulationConfig, seed: int) -> ScenarioTrace:
    """Generate channel and attacker-randomness decisions independent of mode RNG."""

    rng = DeterministicRNG(seed)
    command_space = list(config.effective_command_set())
    commands: list[str] = []
    legit_dropped: list[bool] = []
    legit_delay: list[int] = []
    attacker_record_dropped: list[bool] = []

    for index in range(config.num_legit):
        if config.command_sequence:
            command = config.command_sequence[index % len(config.command_sequence)]
        else:
            command = rng.choice(command_space)
        commands.append(command)
        legit_dropped.append(_dropped(rng, config.p_loss))
        legit_delay.append(_delay(rng, config.p_reorder))
        attacker_record_dropped.append(_dropped(rng, config.attacker_record_loss))

    inline_slots = config.num_legit * max(1, config.inline_attack_burst)
    inline_attempt = [
        _dropped(rng, config.inline_attack_probability) for _ in range(inline_slots)
    ]

    replay_pick: list[int] = []
    replay_dropped: list[bool] = []
    replay_delay: list[int] = []
    for _ in range(config.num_replay):
        replay_pick.append(rng.getrandbits(31))
        replay_dropped.append(_dropped(rng, config.p_loss))
        replay_delay.append(_delay(rng, config.p_reorder))

    return ScenarioTrace(
        commands=commands,
        legit_dropped=legit_dropped,
        legit_delay=legit_delay,
        attacker_record_dropped=attacker_record_dropped,
        inline_attempt=inline_attempt,
        replay_pick=replay_pick,
        replay_dropped=replay_dropped,
        replay_delay=replay_delay,
    )
