"""Receiver-side verification logic for each defense mode."""
from __future__ import annotations

from dataclasses import dataclass

from .auth import Authenticator, HmacAuthenticator
from .defaults import DEFAULT_CHALLENGE_TTL_TICKS, DEFAULT_MAX_OUTSTANDING_CHALLENGES
from .kernel.acceptance import SwDecision, classify, needs_resync
from .kernel.critical_commit import critical_commit, payload_digest, pid_for
from .kernel.epoch import epoch_bump
from .kernel.mac_domains import crit_confirm_tag, crit_prepare_tag, resync_confirm_tag
from .kernel.resync_commit import resync_commit_same_epoch
from .kernel.window_commit import window_commit
from .rng import RandomLike
from .security import constant_time_compare
from .types import (
    WINDOW_VERIFY_MODES,
    CriticalPending,
    Frame,
    Mode,
    ReceiverState,
    ResyncPending,
)


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
    g_hard: int = 0,
    enable_resync: bool = False,
    authenticator: Authenticator | None = None,
) -> VerificationResult:
    if window_size < 1:
        raise ValueError("window_size must be >= 1 for window mode")

    if frame.counter is None or frame.mac is None:
        return VerificationResult(False, "missing_security_fields", state)

    auth = authenticator or HmacAuthenticator(shared_key, mac_length * 4)
    if not auth.verify(frame.counter, frame.command, frame.mac):
        return VerificationResult(False, "mac_mismatch", state)

    # 初始帧：空 list -> 长度 W 的位图，仅顶位置位（mask[0]=1 表示 H 已收）。
    if state.last_counter < 0:
        state.last_counter = frame.counter
        state.received_mask = [1] + [0] * (window_size - 1)
        return VerificationResult(True, "window_accept_initial", state)

    # G_hard 闸门（§5.3）：MAC 已通过，前跳越闸需认证重同步。占位——不执行命令、不改状态
    # （窗口更新留给 Phase 2 的 resync confirm）。纯 SW baseline(enable_resync=False)不受此污染。
    if enable_resync and needs_resync(frame.counter, state.last_counter, g_hard):
        if state.resync_pending is None:   # 进 PENDING（占位 nonce/ttl/expire，待 issue 填）
            state.resync_pending = ResyncPending(
                nonce_r="",
                trigger_counter=frame.counter,
                epoch=state.epoch,
                h_at_challenge=state.last_counter,
                ttl_ticks=0,
                expire_tick=-1,
            )
        return VerificationResult(False, "resync_required", state)

    # 此后 received_mask 恒为长度 W 的 list，安全交给 kernel 判定。
    decision = classify(frame.counter, state.last_counter, state.received_mask, window_size)
    if decision is SwDecision.REJECT_DUP:
        return VerificationResult(False, "counter_replay", state)
    if decision is SwDecision.REJECT_OLD:
        return VerificationResult(False, "counter_too_old", state)

    new_h, new_mask = window_commit(
        frame.counter, state.last_counter, state.received_mask, window_size
    )
    state.last_counter = new_h
    state.received_mask = new_mask
    reason = "window_accept_new" if decision is SwDecision.ACCEPT_FORWARD else "window_accept_old"
    return VerificationResult(True, reason, state)


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
    g_hard: int = 0,
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
        g_hard=g_hard,
        enable_resync=True,
        authenticator=authenticator,
    )


def verify_resync_confirm(
    frame: Frame,
    state: ReceiverState,
    *,
    shared_key: str,
    window_size: int,
    now_tick: int,
) -> VerificationResult:
    """验证 RESYNC_CONFIRM 并封窗提交（§4.3）。
    顺序 MAC→nonce→epoch→TTL（MAC-before-everything）；失败保持 PENDING，仅 TTL 过期清 pending。
    通过 → resync_commit_same_epoch（H2 封窗）、不执行命令（H1）。"""
    pending = state.resync_pending
    if pending is None:
        return VerificationResult(False, "resync_no_pending", state)
    if frame.counter is None:   # 结构性校验：confirm 必须携带 new_h（早拒，narrow 类型）
        return VerificationResult(False, "resync_missing_new_h", state)
    # ① MAC：用 pending 固化的 old_h/old_epoch/ttl + confirm 的 new_h(=frame.counter)/new_epoch
    expected = resync_confirm_tag(
        shared_key, frame.dev_id, frame.key_id, pending.epoch, frame.epoch,
        pending.h_at_challenge, frame.counter, pending.nonce_r, pending.ttl_ticks, frame.flags,
    )
    if frame.mac is None or not constant_time_compare(frame.mac, expected):
        return VerificationResult(False, "mac_mismatch", state)             # 保持 PENDING
    # ② nonce ③ epoch（同 epoch 路径）
    if frame.nonce != pending.nonce_r:
        return VerificationResult(False, "resync_nonce_mismatch", state)    # 保持 PENDING
    if frame.epoch != pending.epoch:
        return VerificationResult(False, "resync_epoch_mismatch", state)    # 保持 PENDING
    # ④ counter 不变量（防状态回退）：new_h 必须覆盖触发 resync 的 counter（§4.3 confirm 验 ctr）
    if frame.counter < pending.trigger_counter:
        return VerificationResult(False, "resync_counter_mismatch", state)  # 保持 PENDING
    # ⑤ TTL 最后：仅过期才清 pending
    if now_tick > pending.expire_tick:
        state.resync_pending = None
        return VerificationResult(False, "resync_ttl_expired", state)
    # ⑥ 封窗提交（H2），不执行命令（H1）
    new_h, new_mask = resync_commit_same_epoch(frame.counter, window_size)
    state.last_counter = new_h
    state.received_mask = new_mask
    state.resync_pending = None
    return VerificationResult(False, "resync_committed", state)


class Receiver:
    """Unified receiver that dispatches to the correct verification routine."""

    def __init__(
        self,
        mode: Mode,
        *,
        shared_key: str,
        mac_length: int,
        window_size: int = 0,
        g_hard: int = 16,
        authenticator: Authenticator | None = None,
        max_outstanding_challenges: int = DEFAULT_MAX_OUTSTANDING_CHALLENGES,
        challenge_ttl_ticks: int = DEFAULT_CHALLENGE_TTL_TICKS,
        command_risk: dict[str, float] | None = None,
        risk_high: float = 0.8,
        critical_pending_capacity: int = 2,
        critical_ttl_ticks: int = 16,
    ):
        self.mode = mode
        self.shared_key = shared_key
        self.mac_length = mac_length
        self.window_size = window_size
        self.g_hard = g_hard
        self.authenticator = authenticator or HmacAuthenticator(shared_key, mac_length * 4)
        self.max_outstanding_challenges = max_outstanding_challenges
        self.challenge_ttl_ticks = challenge_ttl_ticks
        self.command_risk = command_risk
        self.risk_high = risk_high
        self.critical_pending_capacity = critical_pending_capacity
        self.critical_ttl_ticks = critical_ttl_ticks
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
        if self.mode in WINDOW_VERIFY_MODES:
            return verify_with_window(
                frame,
                self.state,
                shared_key=self.shared_key,
                mac_length=self.mac_length,
                window_size=self.window_size,
                g_hard=self.g_hard,
                enable_resync=self.mode is Mode.SW_RESYNC,
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
            if self.state.locked_safe:   # R3：LOCKED_SAFE 拒收帧（先于 epoch 闸门）
                return VerificationResult(False, "locked_safe_reject", self.state)
            if frame.epoch != self.state.epoch:   # R2/D7：显式 epoch 守门（旧 epoch 帧不动状态拒）
                return VerificationResult(False, "epoch_mismatch", self.state)
            return verify_hsw_cr(
                frame,
                self.state,
                shared_key=self.shared_key,
                mac_length=self.mac_length,
                window_size=self.window_size,
                command_risk=self.command_risk,
                risk_high=self.risk_high,
                g_hard=self.g_hard,
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

    def process_resync_confirm(self, frame: Frame, *, now_tick: int) -> VerificationResult:
        """引擎对 flags==FLAG_RESYNC_CONFIRM 的帧专用入口（D2：now_tick 经此注入验 TTL）。"""
        if self.mode not in {Mode.SW_RESYNC, Mode.HSW_CR}:
            return VerificationResult(False, "unexpected_resync_confirm", self.state)
        result = verify_resync_confirm(
            frame,
            self.state,
            shared_key=self.shared_key,
            window_size=self.window_size,
            now_tick=now_tick,
        )
        if result.reason == "resync_committed":
            self.state.locked_safe = False   # R6：认证重建成功 -> 退出 LOCKED_SAFE
        return result

    def time_out_resync(self) -> None:
        """清空在途 RESYNC_PENDING（challenge/confirm 丢失或 TTL 到期），回 NORMAL（§4.3 异常）。"""
        self.state.resync_pending = None

    def time_out_critical(self, pid: int) -> None:
        """清理在途 critical pending（challenge/confirm 丢失或放弃），不影响已 committed。"""
        self.state.pending_critical.pop(pid, None)

    def issue_resync_challenge(
        self, rng: RandomLike, *, now_tick: int, ttl_ticks: int
    ) -> Frame:
        """生成 nonce_R + 固化 TTL，产出 R2T RESYNC_CHALLENGE（§4.3 step 3）。
        challenge 携带 counter=当前 H(old_h)、epoch、ttl，供 sender 构造 confirm。"""
        pending = self.state.resync_pending
        if pending is None:
            raise RuntimeError("issue_resync_challenge requires an active RESYNC_PENDING")
        if pending.nonce_r == "":   # 首次签发：生成 nonce + 固化 TTL
            bits = 96
            pending.nonce_r = f"{rng.getrandbits(bits):0{(bits + 3) // 4}x}"
            pending.ttl_ticks = ttl_ticks
            pending.expire_tick = now_tick + ttl_ticks
        # 已签发 → 幂等重发同一挑战（不覆盖 nonce/expire，避免后到的远跳帧使 in-flight 失效）
        return Frame(
            command="RESYNC_CHALLENGE",
            flags=Frame.FLAG_RESYNC_CHALLENGE,
            nonce=pending.nonce_r,
            epoch=self.state.epoch,
            counter=pending.h_at_challenge,
            ttl=pending.ttl_ticks,
        )

    def begin_locked_safe_resync(
        self, rng: RandomLike, *, now_tick: int, ttl_ticks: int
    ) -> Frame:
        """LOCKED_SAFE 唯一恢复入口（§8.5, R6, blocker #2）。
        普通/critical 收帧入口在 LOCKED_SAFE 已直接拒帧，不会经 verify_with_window 建 pending，
        故这里显式建 ResyncPending（新 epoch、H 丢失占位 -1、trigger=0）再发 R2T challenge。
        成功 process_resync_confirm（绑新 epoch）会清 locked_safe 回 NORMAL。"""
        if not self.state.locked_safe:
            raise RuntimeError("begin_locked_safe_resync requires LOCKED_SAFE state")
        if self.state.resync_pending is None:
            self.state.resync_pending = ResyncPending(
                nonce_r="",
                trigger_counter=0,
                epoch=self.state.epoch,
                h_at_challenge=-1,
                ttl_ticks=0,
                expire_tick=-1,
            )
        return self.issue_resync_challenge(rng, now_tick=now_tick, ttl_ticks=ttl_ticks)

    def process_crit_prepare(
        self, frame: Frame, rng: RandomLike, *, now_tick: int
    ) -> VerificationResult:
        """引擎对 flags==FLAG_CRIT_PREPARE 的帧专用入口（§4.4 阶段1）。
        登记有界 pending、不动窗口/不执行命令（C1）；MAC-before-everything（C4）；
        N_p 有界拒绝新 prepare（C3）；同 pid 幂等、committed 早拒（C2）。"""
        state = self.state
        if self.mode is not Mode.HSW_CR:
            return VerificationResult(False, "unexpected_crit_prepare", state)
        if state.locked_safe:   # R3
            return VerificationResult(False, "locked_safe_reject", state)
        if frame.epoch != state.epoch:   # R2/D7 显式 epoch 守门
            return VerificationResult(False, "epoch_mismatch", state)
        if (self.command_risk or {}).get(frame.command, 0.0) < self.risk_high:
            return VerificationResult(False, "not_critical", state)        # 策略：仅高风险走两阶段
        if frame.counter is None:
            return VerificationResult(False, "crit_missing_counter", state)
        ph = payload_digest(frame.payload)
        expected = crit_prepare_tag(
            self.shared_key, frame.dev_id, frame.key_id, frame.epoch, frame.counter,
            frame.command, ph, Frame.FLAG_CRIT_PREPARE,
        )
        if frame.mac is None or not constant_time_compare(frame.mac, expected):
            return VerificationResult(False, "mac_mismatch", state)         # C4：先 MAC
        pid = pid_for(epoch=frame.epoch, ctr=frame.counter, cmd=frame.command, payload_hash=ph)
        if pid in state.committed_critical:
            return VerificationResult(False, "critical_already_committed", state)   # C2 早拒
        if pid in state.pending_critical:
            # 幂等：不递增 seq、不刷新 nonce/TTL；引擎仍可 issue_crit_challenge(pid) 取同一挑战
            return VerificationResult(False, "critical_prepared", state)
        if len(state.pending_critical) >= self.critical_pending_capacity:
            return VerificationResult(False, "critical_pending_full", state)        # C3 拒绝新
        # 首次登记（不动 H/M_W、不执行）—— C1
        nonce_id = state.crit_nonce_seq
        state.crit_nonce_seq += 1
        bits = 96
        nonce_r = f"{rng.getrandbits(bits):0{(bits + 3) // 4}x}"
        state.pending_critical[pid] = CriticalPending(
            epoch=frame.epoch,
            ctr=frame.counter,
            cmd=frame.command,
            payload_hash=ph,
            nonce_id=nonce_id,
            nonce_r=nonce_r,
            ttl_ticks=self.critical_ttl_ticks,
            expire_tick=now_tick + self.critical_ttl_ticks,
            sender_id=frame.dev_id,
            key_id=frame.key_id,
        )
        return VerificationResult(False, "critical_prepared", state)

    def issue_crit_challenge(self, pid: int) -> Frame:
        """交付 R2T CRIT_CHALLENGE（幂等：从 pending_critical[pid] 读取，不改 pending）。
        回显 prepare 的 dev_id/key_id，使非零 key_id 的两阶段往返也能闭合（修 P1）；
        身份绑定靠 pid + MAC + confirm 端用 pending 权威 dev_id/key_id 复核。"""
        pending = self.state.pending_critical.get(pid)
        if pending is None:
            raise RuntimeError("issue_crit_challenge requires an active pending_critical entry")
        return Frame(
            command=pending.cmd,
            flags=Frame.FLAG_CRIT_CHALLENGE,
            counter=pending.ctr,
            epoch=pending.epoch,
            nonce=pending.nonce_r,
            ttl=pending.ttl_ticks,
            dev_id=pending.sender_id,
            key_id=pending.key_id,
            pid=pid,
            nonce_id=pending.nonce_id,
            payload_hash=pending.payload_hash,
        )

    def process_crit_confirm(self, frame: Frame, *, now_tick: int) -> VerificationResult:
        """引擎对 flags==FLAG_CRIT_CONFIRM 的帧专用入口（§4.4 阶段2，Accept_critical）。
        顺序 committed→pending→MAC→TTL→SW→原子 commit（MAC-before-everything, C4）；
        通过 → critical_commit 封窗 + 执行一次（accepted=True, C6）+ 删 pending + 记 committed。
        dev_id/key_id 取自 pending 权威值（prepare 时固化）而非 confirm 帧；绑定靠 pid + MAC。"""
        state = self.state
        if self.mode is not Mode.HSW_CR:
            return VerificationResult(False, "unexpected_crit_confirm", state)
        if state.locked_safe:   # R3
            return VerificationResult(False, "locked_safe_reject", state)
        if frame.epoch != state.epoch:   # R2/D7 显式 epoch 守门
            return VerificationResult(False, "epoch_mismatch", state)
        pid = frame.pid
        if pid in state.committed_critical:
            return VerificationResult(False, "critical_already_committed", state)   # C2
        pending = state.pending_critical.get(pid)
        if pending is None:
            return VerificationResult(False, "critical_no_pending", state)   # fake challenge 防线
        expected = crit_confirm_tag(
            self.shared_key, pending.sender_id, pending.key_id, pending.epoch, pending.ctr,
            pending.cmd, pending.payload_hash, pid, pending.nonce_id, pending.nonce_r,
            pending.ttl_ticks, Frame.FLAG_CRIT_CONFIRM,
        )
        if frame.mac is None or not constant_time_compare(frame.mac, expected):
            return VerificationResult(False, "mac_mismatch", state)   # C4 保留 pending
        if now_tick > pending.expire_tick:
            del state.pending_critical[pid]
            return VerificationResult(False, "critical_ttl_expired", state)
        # SW 可接受性：dup/old ctr 不得借 confirm 提交（防回退/重放）
        if state.last_counter < 0:
            # 初始帧：直接建窗（与 verify_with_window 初始一致），不调 classify（空 mask）
            state.last_counter = pending.ctr
            state.received_mask = [1] + [0] * (self.window_size - 1)
        else:
            decision = classify(
                pending.ctr, state.last_counter, state.received_mask, self.window_size
            )
            if decision in (SwDecision.REJECT_DUP, SwDecision.REJECT_OLD):
                del state.pending_critical[pid]
                return VerificationResult(False, "critical_sw_reject", state)
            new_h, new_mask = critical_commit(
                n=pending.ctr, h=state.last_counter, mask=state.received_mask, w=self.window_size
            )
            state.last_counter = new_h
            state.received_mask = new_mask
        # 原子 commit（C6）：窗口已更新 + 删 pending + 记 committed
        del state.pending_critical[pid]
        state.committed_critical.add(pid)
        return VerificationResult(True, "critical_committed", state)   # accepted=True = 执行一次

    def reboot(self) -> None:
        """模拟 reboot/brownout（§8.5, R1/R2/R4）：清易失态、单调 bump epoch、进 LOCKED_SAFE。
        接收端 NVM 持久态（bump 后 epoch、key_id、boot_counter）保留；lease 属发送端 NVM。"""
        state = self.state
        # R4：清空易失态（H/M_W + resync/critical pending + nonce 表 + committed 去重集）
        state.last_counter = -1
        state.received_mask = []
        state.resync_pending = None
        state.pending_critical = {}
        state.committed_critical = set()
        state.outstanding_nonces = {}
        state.expected_nonce = None
        state.used_nonces = set()   # P3：清易失 challenge 状态（跨 epoch 不留 stale nonce）
        state.crit_nonce_seq = 0
        self._issue_tick = 0        # P3：复位 nonce 签发 tick 计数（易失）
        # R2：单调 bump epoch（旧 epoch 帧此后被显式守门拒）；R3：进 LOCKED_SAFE
        state.epoch = epoch_bump(state.epoch)
        state.nvm_epoch = state.epoch
        state.boot_counter += 1
        state.locked_safe = True

    def reset(self) -> None:
        self.state = ReceiverState()
