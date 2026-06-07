"""Sender-side helpers for constructing frames."""
from __future__ import annotations

from dataclasses import dataclass

from .auth import Authenticator, HmacAuthenticator
from .kernel.critical_commit import payload_digest, pid_for
from .kernel.mac_domains import crit_confirm_tag, crit_prepare_tag, resync_confirm_tag
from .types import Frame, Mode, PendingUserIntent


@dataclass
class Sender:
    mode: Mode
    shared_key: str
    mac_length: int = 8
    tx_counter: int = 0
    authenticator: Authenticator | None = None
    pending_intent: PendingUserIntent | None = None   # §4.5 自发 critical 意图（防洗白）
    current_epoch: int = 0   # 发送端自有 epoch 权威（§8.5, D7）；recovery 经 adopt_epoch 更新

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

    def begin_critical_intent(
        self, cmd: str, payload: bytes, *, epoch: int, key_id: int, now_tick: int
    ) -> Frame:
        """发起一次 critical 命令：记录完整身份 intent（§4.5）并产出 CRIT_PREPARE。
        只有真发送端自发命令时才走此路径；攻击者重放 prepare 不会创建 intent。"""
        self.tx_counter += 1
        ctr = self.tx_counter
        ph = payload_digest(payload)
        pid = pid_for(epoch=epoch, ctr=ctr, cmd=cmd, payload_hash=ph)
        self.pending_intent = PendingUserIntent(
            epoch=epoch, ctr=ctr, cmd=cmd, payload_hash=ph, pid=pid,
            key_id=key_id, t_intent=now_tick,
        )
        mac = crit_prepare_tag(self.shared_key, 0, key_id, epoch, ctr, cmd, ph,
                               Frame.FLAG_CRIT_PREPARE)
        return Frame(
            command=cmd,
            counter=ctr,
            epoch=epoch,
            key_id=key_id,
            flags=Frame.FLAG_CRIT_PREPARE,
            payload=payload,
            payload_hash=ph,
            mac=mac,
        )

    def confirm_critical_challenge(
        self, challenge: Frame, *, now_tick: int, tau_intent: int
    ) -> Frame | None:
        """对 R2T CRIT_CHALLENGE 应答 CRIT_CONFIRM（§4.5 防洗白闸门）。
        仅当 challenge 的 pid 与未消费 intent 完全一致（含 epoch/ctr/cmd/payload_hash）、
        key_id/epoch 合法、且未超 τ_intent 时产出 CONFIRM 并一次性消费 intent；否则返回 None。"""
        intent = self.pending_intent
        if intent is None or intent.consumed:
            return None
        if challenge.pid != intent.pid:          # ★ 绑 pid：旧 prepare 同 cmd/payload 也无法洗白
            return None
        if challenge.key_id != intent.key_id or challenge.epoch != intent.epoch:
            return None
        if challenge.nonce is None:
            return None
        if now_tick - intent.t_intent > tau_intent:
            return None
        intent.consumed = True                   # 一次性
        mac = crit_confirm_tag(
            self.shared_key, challenge.dev_id, intent.key_id, intent.epoch, intent.ctr,
            intent.cmd, intent.payload_hash, intent.pid, challenge.nonce_id, challenge.nonce,
            challenge.ttl, Frame.FLAG_CRIT_CONFIRM,
        )
        return Frame(
            command=intent.cmd,
            counter=intent.ctr,
            epoch=intent.epoch,
            key_id=intent.key_id,
            flags=Frame.FLAG_CRIT_CONFIRM,
            pid=intent.pid,
            nonce_id=challenge.nonce_id,
            nonce=challenge.nonce,
            payload_hash=intent.payload_hash,
            dev_id=challenge.dev_id,
            ttl=challenge.ttl,
            mac=mac,
        )

    def adopt_epoch(self, new_epoch: int) -> None:
        """recovery 后显式采用接收端新 epoch（D7：发送端拥有 epoch，不由 engine 偷读 receiver）。"""
        self.current_epoch = new_epoch

    def reset(self) -> None:
        self.tx_counter = 0
        self.pending_intent = None
        self.current_epoch = 0
