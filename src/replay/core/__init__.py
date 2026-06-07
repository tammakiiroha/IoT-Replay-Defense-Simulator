"""Simulation core copied into the new package boundary."""
from __future__ import annotations

from .attacker import Attacker
from .auth import AsconAeadAuthenticator, Authenticator, HmacAuthenticator
from .channel import Channel, should_drop
from .channel_models import GilbertElliottLoss, IidLoss, ReorderDelay, TraceLoss
from .commands import DEFAULT_COMMANDS, load_command_sequence
from .cost import CostModel, CostStats, estimate_energy
from .defaults import (
    DEFAULT_ATTACK_MODE,
    DEFAULT_ATTACKER_RECORD_LOSS,
    DEFAULT_CHALLENGE_NONCE_BITS,
    DEFAULT_CHALLENGE_TTL_TICKS,
    DEFAULT_G_HARD,
    DEFAULT_INLINE_ATTACK_BURST,
    DEFAULT_INLINE_ATTACK_PROBABILITY,
    DEFAULT_MAC_LENGTH,
    DEFAULT_MAC_TAG_BITS,
    DEFAULT_MAX_OUTSTANDING_CHALLENGES,
    DEFAULT_NUM_LEGIT,
    DEFAULT_NUM_REPLAY,
    DEFAULT_P_LOSS,
    DEFAULT_P_REORDER,
    DEFAULT_RUNS,
    DEFAULT_SHARED_KEY,
    DEFAULT_WINDOW_SIZE,
)
from .experiment import (
    run_many_experiments,
    run_paired_experiments,
    run_until_precision,
    simulate_one_run,
    simulate_one_run_with_trace,
)
from .receiver import Receiver, VerificationResult
from .rng import DeterministicRNG, RandomLike
from .security import compute_mac, compute_mac_bits, constant_time_compare
from .sender import Sender
from .trace import ScenarioTrace, generate_trace
from .types import (
    WINDOW_SIZED_MODES,
    WINDOW_VERIFY_MODES,
    AggregateStats,
    AttackMode,
    Frame,
    Mode,
    ReceiverState,
    SimulationConfig,
    SimulationRunResult,
)

__all__ = [
    "AggregateStats",
    "AsconAeadAuthenticator",
    "AttackMode",
    "Attacker",
    "Authenticator",
    "Channel",
    "CostModel",
    "CostStats",
    "DEFAULT_ATTACK_MODE",
    "DEFAULT_ATTACKER_RECORD_LOSS",
    "DEFAULT_CHALLENGE_NONCE_BITS",
    "DEFAULT_CHALLENGE_TTL_TICKS",
    "DEFAULT_COMMANDS",
    "DEFAULT_G_HARD",
    "DEFAULT_INLINE_ATTACK_BURST",
    "DEFAULT_INLINE_ATTACK_PROBABILITY",
    "DEFAULT_MAC_LENGTH",
    "DEFAULT_MAC_TAG_BITS",
    "DEFAULT_MAX_OUTSTANDING_CHALLENGES",
    "DEFAULT_NUM_LEGIT",
    "DEFAULT_NUM_REPLAY",
    "DEFAULT_P_LOSS",
    "DEFAULT_P_REORDER",
    "DEFAULT_RUNS",
    "DEFAULT_SHARED_KEY",
    "DEFAULT_WINDOW_SIZE",
    "DeterministicRNG",
    "Frame",
    "GilbertElliottLoss",
    "HmacAuthenticator",
    "IidLoss",
    "Mode",
    "RandomLike",
    "Receiver",
    "ReceiverState",
    "ReorderDelay",
    "Sender",
    "ScenarioTrace",
    "SimulationConfig",
    "SimulationRunResult",
    "VerificationResult",
    "WINDOW_SIZED_MODES",
    "WINDOW_VERIFY_MODES",
    "compute_mac",
    "compute_mac_bits",
    "constant_time_compare",
    "estimate_energy",
    "load_command_sequence",
    "run_many_experiments",
    "run_paired_experiments",
    "run_until_precision",
    "should_drop",
    "simulate_one_run",
    "simulate_one_run_with_trace",
    "generate_trace",
    "TraceLoss",
]
