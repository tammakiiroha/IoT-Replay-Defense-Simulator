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

    # Initial state
    if state.last_counter < 0:
        state.last_counter = frame.counter
        state.received_mask = 1  # Mark this counter as received (bit 0)
        return VerificationResult(True, "window_accept_initial", state)

    diff = frame.counter - state.last_counter

    # Case 1: New highest counter (Advance window)
    if diff > 0:
        # Check lookahead limit (optional, but preserves original behavior of preventing huge jumps)
        # We use window_size as the lookahead limit as well.
        if diff > window_size:
            return VerificationResult(False, "counter_out_of_window", state)
        
        # Shift mask to the left by diff
        state.received_mask <<= diff
        # Set bit 0 (the new last_counter)
        state.received_mask |= 1
        # Update last_counter
        state.last_counter = frame.counter
        return VerificationResult(True, "window_accept_new", state)

    # Case 2: Old or current counter (Check replay window)
    else:
        offset = -diff  # Positive distance from last_counter
        
        # Check if it fell off the left edge of the window
        if offset >= window_size:
            return VerificationResult(False, "counter_too_old", state)
        
        # Check if already received
        if (state.received_mask >> offset) & 1:
            return VerificationResult(False, "counter_replay", state)
        
        # Mark as received
        state.received_mask |= (1 << offset)
        return VerificationResult(True, "window_accept_old", state)


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
