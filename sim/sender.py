"""Sender-side helpers for constructing frames."""
from __future__ import annotations

from dataclasses import dataclass

from .security import compute_mac
from .types import Frame, Mode


@dataclass
class Sender:
    mode: Mode
    shared_key: str
    mac_length: int = 8
    tx_counter: int = 0

    def next_frame(self, command: str, *, nonce: str | None = None) -> Frame:
        if self.mode is Mode.NO_DEFENSE:
            return Frame(command=command)

        if self.mode is Mode.CHALLENGE:
            if nonce is None:
                raise ValueError("Challenge mode requires a nonce for each frame")
            mac = compute_mac(nonce, command, key=self.shared_key, mac_length=self.mac_length)
            return Frame(command=command, nonce=nonce, mac=mac)

        self.tx_counter += 1
        mac = compute_mac(self.tx_counter, command, key=self.shared_key, mac_length=self.mac_length)
        return Frame(command=command, counter=self.tx_counter, mac=mac)

    def reset(self) -> None:
        self.tx_counter = 0
