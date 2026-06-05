"""Receiver-side verification logic for each defense mode."""
from __future__ import annotations

from dataclasses import dataclass

from .auth import Authenticator, HmacAuthenticator
from .defaults import DEFAULT_CHALLENGE_TTL_TICKS, DEFAULT_MAX_OUTSTANDING_CHALLENGES
from .rng import RandomLike
from .types import Frame, Mode, ReceiverState


@dataclass
class VerificationResult:
    accepted: bool
    reason: str
    state: ReceiverState


def verify_no_defense(frame: Frame, state: ReceiverState, **_: object) -> VerificationResult:
    return VerificationResult(True, "no_defense_accept", state)


def verify_with_rolling_mac(
    frame: Frame,
    state: ReceiverState,
    *,
    shared_key: str,
    mac_length: int,
    authenticator: Authenticator | None = None,
) -> VerificationResult:
    if frame.counter is None or frame.mac is None:
        return VerificationResult(False, "missing_security_fields", state)

    auth = authenticator or HmacAuthenticator(shared_key, mac_length * 4)
    if not auth.verify(frame.counter, frame.command, frame.mac):
        return VerificationResult(False, "mac_mismatch", state)

    if frame.counter <= state.last_counter:
        return VerificationResult(False, "counter_replay", state)

    state.last_counter = frame.counter
    return VerificationResult(True, "rolling_accept", state)


def verify_with_window(
    frame: Frame,
    state: ReceiverState,
    *,
    shared_key: str,
    mac_length: int,
    window_size: int,
    authenticator: Authenticator | None = None,
) -> VerificationResult:
    if window_size < 1:
        raise ValueError("window_size must be >= 1 for window mode")
    mask_limit = (1 << window_size) - 1

    if frame.counter is None or frame.mac is None:
        return VerificationResult(False, "missing_security_fields", state)

    auth = authenticator or HmacAuthenticator(shared_key, mac_length * 4)
    if not auth.verify(frame.counter, frame.command, frame.mac):
        return VerificationResult(False, "mac_mismatch", state)

    if state.last_counter < 0:
        state.last_counter = frame.counter
        state.received_mask = 1
        return VerificationResult(True, "window_accept_initial", state)

    diff = frame.counter - state.last_counter
    if diff > 0:
        if diff >= window_size:
            state.received_mask = 1
        else:
            state.received_mask = ((state.received_mask << diff) | 1) & mask_limit
        state.last_counter = frame.counter
        return VerificationResult(True, "window_accept_new", state)

    offset = -diff
    if offset >= window_size:
        return VerificationResult(False, "counter_too_old", state)
    if (state.received_mask >> offset) & 1:
        return VerificationResult(False, "counter_replay", state)

    state.received_mask |= 1 << offset
    state.received_mask &= mask_limit
    return VerificationResult(True, "window_accept_old", state)


def verify_challenge_response(
    frame: Frame,
    state: ReceiverState,
    *,
    shared_key: str,
    mac_length: int,
    authenticator: Authenticator | None = None,
) -> VerificationResult:
    if frame.nonce is None or frame.mac is None:
        return VerificationResult(False, "missing_challenge_fields", state)
    if frame.nonce in state.used_nonces:
        return VerificationResult(False, "challenge_replay", state)

    auth = authenticator or HmacAuthenticator(shared_key, mac_length * 4)

    if state.outstanding_nonces:
        if frame.nonce not in state.outstanding_nonces:
            return VerificationResult(False, "challenge_mismatch", state)
        if not auth.verify(frame.nonce, frame.command, frame.mac):
            return VerificationResult(False, "mac_mismatch", state)
        del state.outstanding_nonces[frame.nonce]
        state.used_nonces.add(frame.nonce)
        if frame.nonce == state.expected_nonce:
            state.expected_nonce = None
        return VerificationResult(True, "challenge_accept", state)

    if state.expected_nonce is None:
        return VerificationResult(False, "no_outstanding_challenge", state)
    if frame.nonce != state.expected_nonce:
        return VerificationResult(False, "challenge_mismatch", state)

    if not auth.verify(frame.nonce, frame.command, frame.mac):
        return VerificationResult(False, "mac_mismatch", state)

    state.used_nonces.add(frame.nonce)
    state.expected_nonce = None
    return VerificationResult(True, "challenge_accept", state)


def verify_hsw_cr(
    frame: Frame,
    state: ReceiverState,
    *,
    shared_key: str,
    mac_length: int,
    window_size: int,
    command_risk: dict[str, float] | None,
    risk_high: float,
    authenticator: Authenticator | None = None,
) -> VerificationResult:
    is_high_risk = (command_risk or {}).get(frame.command, 0.0) >= risk_high
    if is_high_risk or frame.nonce is not None:
        return verify_challenge_response(
            frame,
            state,
            shared_key=shared_key,
            mac_length=mac_length,
            authenticator=authenticator,
        )
    return verify_with_window(
        frame,
        state,
        shared_key=shared_key,
        mac_length=mac_length,
        window_size=window_size,
        authenticator=authenticator,
    )


class Receiver:
    """Unified receiver that dispatches to the correct verification routine."""

    def __init__(
        self,
        mode: Mode,
        *,
        shared_key: str,
        mac_length: int,
        window_size: int = 0,
        authenticator: Authenticator | None = None,
        max_outstanding_challenges: int = DEFAULT_MAX_OUTSTANDING_CHALLENGES,
        challenge_ttl_ticks: int = DEFAULT_CHALLENGE_TTL_TICKS,
        command_risk: dict[str, float] | None = None,
        risk_high: float = 0.8,
    ):
        self.mode = mode
        self.shared_key = shared_key
        self.mac_length = mac_length
        self.window_size = window_size
        self.authenticator = authenticator or HmacAuthenticator(shared_key, mac_length * 4)
        self.max_outstanding_challenges = max_outstanding_challenges
        self.challenge_ttl_ticks = challenge_ttl_ticks
        self.command_risk = command_risk
        self.risk_high = risk_high
        self._issue_tick = 0
        self.state = ReceiverState()

    def process(self, frame: Frame) -> VerificationResult:
        if self.mode is Mode.NO_DEFENSE:
            return verify_no_defense(frame, self.state)
        if self.mode is Mode.ROLLING_MAC:
            return verify_with_rolling_mac(
                frame,
                self.state,
                shared_key=self.shared_key,
                mac_length=self.mac_length,
                authenticator=self.authenticator,
            )
        if self.mode in {Mode.WINDOW, Mode.OSCORE_LIKE}:
            return verify_with_window(
                frame,
                self.state,
                shared_key=self.shared_key,
                mac_length=self.mac_length,
                window_size=self.window_size,
                authenticator=self.authenticator,
            )
        if self.mode is Mode.CHALLENGE:
            return verify_challenge_response(
                frame,
                self.state,
                shared_key=self.shared_key,
                mac_length=self.mac_length,
                authenticator=self.authenticator,
            )
        if self.mode is Mode.HSW_CR:
            return verify_hsw_cr(
                frame,
                self.state,
                shared_key=self.shared_key,
                mac_length=self.mac_length,
                window_size=self.window_size,
                command_risk=self.command_risk,
                risk_high=self.risk_high,
                authenticator=self.authenticator,
            )
        raise ValueError(f"Unsupported mode: {self.mode}")

    def issue_nonce(self, rng: RandomLike, bits: int = 32, *, tick: int | None = None) -> str:
        if self.mode not in {Mode.CHALLENGE, Mode.HSW_CR}:
            raise RuntimeError("Nonce issuance is only supported in challenge-capable modes")
        nonce_int = rng.getrandbits(bits)
        hex_len = (bits + 3) // 4
        nonce_hex = f"{nonce_int:0{hex_len}x}"
        self._issue_tick = tick if tick is not None else self._issue_tick + 1
        cutoff = self._issue_tick - self.challenge_ttl_ticks
        for stale in [n for n, t in self.state.outstanding_nonces.items() if t < cutoff]:
            del self.state.outstanding_nonces[stale]
        while len(self.state.outstanding_nonces) >= self.max_outstanding_challenges:
            oldest = min(
                self.state.outstanding_nonces,
                key=lambda nonce: self.state.outstanding_nonces[nonce],
            )
            del self.state.outstanding_nonces[oldest]
        self.state.outstanding_nonces[nonce_hex] = self._issue_tick
        self.state.expected_nonce = nonce_hex
        return nonce_hex

    def reset(self) -> None:
        self.state = ReceiverState()
