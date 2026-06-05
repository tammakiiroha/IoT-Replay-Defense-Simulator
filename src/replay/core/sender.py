"""Sender-side helpers for constructing frames."""
from __future__ import annotations

from dataclasses import dataclass

from .auth import Authenticator, HmacAuthenticator
from .types import Frame, Mode


@dataclass
class Sender:
    mode: Mode
    shared_key: str
    mac_length: int = 8
    tx_counter: int = 0
    authenticator: Authenticator | None = None

    def __post_init__(self) -> None:
        if self.authenticator is None:
            self.authenticator = HmacAuthenticator(self.shared_key, self.mac_length * 4)

    def next_frame(self, command: str, *, nonce: str | None = None) -> Frame:
        auth = self.authenticator
        if auth is None:
            raise RuntimeError("Authenticator was not initialized")

        if self.mode is Mode.NO_DEFENSE:
            return Frame(command=command)

        if nonce is not None:
            mac = auth.tag(nonce, command)
            return Frame(command=command, nonce=nonce, mac=mac)

        if self.mode is Mode.CHALLENGE:
            raise ValueError("Challenge mode requires a nonce for each frame")

        self.tx_counter += 1
        mac = auth.tag(self.tx_counter, command)
        return Frame(command=command, counter=self.tx_counter, mac=mac)

    def reset(self) -> None:
        self.tx_counter = 0
