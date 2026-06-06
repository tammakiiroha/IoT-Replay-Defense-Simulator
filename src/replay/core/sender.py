"""Sender-side helpers for constructing frames."""
from __future__ import annotations

from dataclasses import dataclass

from .auth import Authenticator, HmacAuthenticator
from .kernel.mac_domains import resync_confirm_tag
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

    def respond_resync_challenge(self, challenge: Frame) -> Frame:
        """对 R2T RESYNC_CHALLENGE 应答 RESYNC_CONFIRM（§4.3 step 4）。
        new_h 取发送端自己的 tx_counter（不是 challenge.counter=receiver old_h），防状态回退。"""
        old_h = challenge.counter
        nonce_r = challenge.nonce
        if old_h is None or nonce_r is None:
            raise ValueError("RESYNC_CHALLENGE missing counter/nonce")
        epoch = challenge.epoch
        new_h = self.tx_counter
        tag = resync_confirm_tag(
            self.shared_key, challenge.dev_id, challenge.key_id, epoch, epoch,
            old_h, new_h, nonce_r, challenge.ttl, Frame.FLAG_RESYNC_CONFIRM,
        )
        return Frame(
            command="RESYNC_CONFIRM",
            flags=Frame.FLAG_RESYNC_CONFIRM,
            counter=new_h,
            epoch=epoch,
            nonce=nonce_r,
            ttl=challenge.ttl,
            dev_id=challenge.dev_id,
            key_id=challenge.key_id,
            mac=tag,
        )

    def reset(self) -> None:
        self.tx_counter = 0
