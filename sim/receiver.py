"""Receiver-side verification logic for each defense mode."""
from __future__ import annotations

from dataclasses import dataclass
import random

from .security import compute_mac, constant_time_compare
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
) -> VerificationResult:
    if frame.counter is None or frame.mac is None:
        return VerificationResult(False, "missing_security_fields", state)

    expected_mac = compute_mac(frame.counter, frame.command, key=shared_key, mac_length=mac_length)
    if not constant_time_compare(expected_mac, frame.mac):
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
) -> VerificationResult:
    if window_size < 1:
        raise ValueError("window_size must be >= 1 for window mode")

    if frame.counter is None or frame.mac is None:
        return VerificationResult(False, "missing_security_fields", state)

    expected_mac = compute_mac(frame.counter, frame.command, key=shared_key, mac_length=mac_length)
    if not constant_time_compare(expected_mac, frame.mac):
        return VerificationResult(False, "mac_mismatch", state)

    if state.last_counter < 0:
        state.last_counter = frame.counter
        return VerificationResult(True, "window_accept_initial", state)

    if frame.counter <= state.last_counter:
        return VerificationResult(False, "counter_replay", state)

    upper_bound = state.last_counter + window_size
    if frame.counter > upper_bound:
        return VerificationResult(False, "counter_out_of_window", state)

    if frame.counter > state.last_counter:
        state.last_counter = frame.counter
    return VerificationResult(True, "window_accept", state)


def verify_challenge_response(
    frame: Frame,
    state: ReceiverState,
    *,
    shared_key: str,
    mac_length: int,
) -> VerificationResult:
    if frame.nonce is None or frame.mac is None:
        return VerificationResult(False, "missing_challenge_fields", state)

    if state.expected_nonce is None:
        return VerificationResult(False, "no_outstanding_challenge", state)

    if frame.nonce != state.expected_nonce:
        return VerificationResult(False, "challenge_mismatch", state)

    expected_mac = compute_mac(frame.nonce, frame.command, key=shared_key, mac_length=mac_length)
    if not constant_time_compare(expected_mac, frame.mac):
        return VerificationResult(False, "mac_mismatch", state)

    state.expected_nonce = None
    return VerificationResult(True, "challenge_accept", state)


class Receiver:
    """Unified receiver that dispatches to the correct verification routine."""

    def __init__(self, mode: Mode, *, shared_key: str, mac_length: int, window_size: int = 0):
        self.mode = mode
        self.shared_key = shared_key
        self.mac_length = mac_length
        self.window_size = window_size
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
            )
        if self.mode is Mode.WINDOW:
            return verify_with_window(
                frame,
                self.state,
                shared_key=self.shared_key,
                mac_length=self.mac_length,
                window_size=self.window_size,
            )
        if self.mode is Mode.CHALLENGE:
            return verify_challenge_response(
                frame,
                self.state,
                shared_key=self.shared_key,
                mac_length=self.mac_length,
            )
        raise ValueError(f"Unsupported mode: {self.mode}")

    def issue_nonce(self, rng: random.Random, bits: int = 32) -> str:
        if self.mode is not Mode.CHALLENGE:
            raise RuntimeError("Nonce issuance is only supported in challenge mode")
        nonce_int = rng.getrandbits(bits)
        nonce_hex = f"{nonce_int:0{bits // 4}x}"
        self.state.expected_nonce = nonce_hex
        return nonce_hex

    def reset(self) -> None:
        self.state = ReceiverState()
