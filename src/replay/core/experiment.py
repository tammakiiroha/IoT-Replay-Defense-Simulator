"""Experiment runner that stitches together all simulation components."""
from __future__ import annotations

import dataclasses
import statistics
import sys
import time
from collections.abc import Callable, Sequence

from .attacker import Attacker, AttackerStrategy, RandomReplay
from .auth import AsconAeadAuthenticator, Authenticator, HmacAuthenticator
from .channel import Channel
from .channel_models import GilbertElliottLoss, IidLoss, LossModel, ReorderDelay, TraceLoss
from .cost import CostModel, CostStats, estimate_energy
from .kernel.critical_commit import payload_digest, pid_for
from .policy import PolicyTable
from .receiver import Receiver
from .rng import DeterministicRNG, RandomLike
from .scheduler import EventScheduler
from .sender import Sender
from .stats import wilson_ci
from .trace import ScenarioTrace, generate_trace
from .types import (
    WINDOW_SIZED_MODES,
    AggregateStats,
    AttackMode,
    Frame,
    Mode,
    SimulationConfig,
    SimulationRunResult,
)


def _resolve_rng(rng: RandomLike | None, seed: int | None) -> RandomLike:
    if rng is not None:
        return rng
    return DeterministicRNG(seed)


def _choose_command(config: SimulationConfig, index: int, rng: RandomLike) -> str:
    if config.command_sequence:
        sequence = config.command_sequence
        if not sequence:
            raise ValueError("Provided command sequence is empty")
        return sequence[index % len(sequence)]
    command_space = config.effective_command_set()
    if not command_space:
        raise ValueError("Command set is empty")
    return rng.choice(list(command_space))


def _tag_bits(config: SimulationConfig) -> int:
    return config.mac_tag_bits or config.mac_length * 4


def _authenticator(config: SimulationConfig) -> Authenticator:
    tag_bits = _tag_bits(config)
    if config.auth_profile == "ascon":
        return AsconAeadAuthenticator(config.shared_key, tag_bits=tag_bits)
    return HmacAuthenticator(config.shared_key, tag_bits=tag_bits)


def _loss_model(config: SimulationConfig) -> LossModel:
    if config.channel_model == "gilbert_elliott":
        return GilbertElliottLoss(
            p_good_to_bad=config.burst_p_good_to_bad,
            p_bad_to_good=config.burst_p_bad_to_good,
            loss_good=config.loss_good,
            loss_bad=config.loss_bad,
        )
    if config.channel_model == "trace":
        return TraceLoss(list(config.loss_trace or []))
    return IidLoss(config.p_loss)


def _frame_bytes(frame: Frame, tag_bits: int, nonce_bits: int) -> int:
    size = len(frame.command.encode("utf-8"))
    if frame.counter is not None:
        size += 4
    if frame.nonce is not None:
        size += max(1, (nonce_bits + 7) // 8)
    if frame.mac is not None:
        size += max(1, (tag_bits + 7) // 8)
    return size


def _state_bytes(config: SimulationConfig, receiver: Receiver) -> int:
    window_bytes = max(1, (max(config.window_size, 1) + 7) // 8)
    nonce_bytes = len(receiver.state.outstanding_nonces) * max(
        1,
        (config.challenge_nonce_bits + 7) // 8,
    )
    return window_bytes + nonce_bytes


def _should_challenge(config: SimulationConfig, command: str) -> bool:
    # 单阶段 challenge 仅用于 CHALLENGE baseline；HSW_CR 高风险改走两阶段 critical（D5）。
    return config.mode is Mode.CHALLENGE


def _should_record_paired(position: str, *, legit_dropped: bool, record_dropped: bool) -> bool:
    """Paired-path attacker recording policy by capture position (Phase 5 D2).

    - ind: record unless the eavesdrop draw dropped it (legacy default).
    - tx:  P_record=1.0 — always record (sender side), even when lost/record-dropped.
    - rx:  only frames the receiver actually got, and not eavesdrop-dropped.
    """
    if position == "tx":
        return True
    if position == "rx":
        return (not legit_dropped) and (not record_dropped)
    return not record_dropped


def _is_two_phase_critical(
    config: SimulationConfig, command: str, policy_table: PolicyTable
) -> bool:
    """HSW_CR critical 命令走两阶段 commit（§4.4，D5）；其余走 window/单阶段。
    分类经预构建 policy_table（G5/G9, P1/P3：运行时 O(1)，不逐帧调 classify_critical）。"""
    if config.mode is not Mode.HSW_CR:
        return False
    return policy_table.is_critical(command)


def _build_policy_table(config: SimulationConfig) -> PolicyTable:
    """每次运行预构建一次 policy_table（与 Receiver 内的同源同构）。"""
    return PolicyTable.from_config(
        policy_source=config.policy_source,
        profile=config.profile,
        command_impact=config.command_impact,
        command_risk=config.command_risk,
        risk_high=config.risk_high,
    )


def _roll_drop_delay(rng: RandomLike, p_loss: float, p_reorder: float) -> tuple[bool, int]:
    """单跳 drop/delay 决策（与 trace._dropped/_delay 同语义），用于 live 路径的 resync 信道。"""
    dropped = p_loss > 0.0 and rng.random() < p_loss
    delay = rng.randint(1, 3) if (p_reorder > 0.0 and rng.random() < p_reorder) else 0
    return dropped, delay


def _resolve_resync(
    receiver: Receiver,
    sender: Sender,
    cost_stats: CostStats,
    *,
    rng: RandomLike,
    now_tick: int,
    ttl_ticks: int,
    rtt_ticks: int,
    transport: Callable[[], tuple[bool, int, bool, int]],
) -> None:
    """有界 resync 子泵（§4.3, Option A）：触发帧那步内解算 challenge->confirm 往返。
    仅首次进 PENDING（nonce_r==""）才发起；transport 决定 challenge/confirm 的 loss/delay/TTL。"""
    pending = receiver.state.resync_pending
    if pending is None or pending.nonce_r != "":
        return
    challenge = receiver.issue_resync_challenge(rng, now_tick=now_tick, ttl_ticks=ttl_ticks)
    cost_stats.resync_initiated += 1
    ch_dropped, ch_delay, cf_dropped, cf_delay = transport()
    if ch_dropped or cf_dropped:               # challenge 或 confirm 丢失 -> 超时
        receiver.time_out_resync()
        cost_stats.resync_timeout += 1
        return
    confirm = sender.respond_resync_challenge(challenge)
    arrival = now_tick + rtt_ticks + ch_delay + cf_delay
    result = receiver.process_resync_confirm(confirm, now_tick=arrival)
    if result.reason == "resync_committed":
        cost_stats.resync_completed += 1
    else:                                       # ttl_expired（pending 已清）或其它 -> 超时
        receiver.time_out_resync()
        cost_stats.resync_timeout += 1


def _resolve_critical(
    receiver: Receiver,
    sender: Sender,
    cost_stats: CostStats,
    *,
    frame: Frame,
    rng: RandomLike,
    now_tick: int,
    ttl_ticks: int,
    rtt_ticks: int,
    tau_intent: int,
    transport: Callable[[], tuple[bool, int, bool, int]],
) -> bool:
    """有界 critical 两阶段子泵（§4.4/§4.5, Option A）。返回是否 commit（命令执行一次）。
    prepare 受理 -> R2T challenge -> sender 用户意图门控 confirm -> 反向送回 -> 原子 commit。
    attacker 重放 prepare 走同路径但无匹配意图（或已 committed）-> 不 commit。
    transport 决定 challenge/confirm 的 loss/delay（与 resync 同源建模）。"""
    if frame.counter is None:
        return False
    prep = receiver.process_crit_prepare(frame, rng, now_tick=now_tick)
    if prep.reason != "critical_prepared":
        if prep.reason == "locked_safe_reject":   # 评审注记：critical 路径也计 locked_safe_rejects
            cost_stats.locked_safe_rejects += 1
        cost_stats.crit_rejected += 1   # not_critical/mac/full/already_committed/locked_safe
        return False
    cost_stats.crit_prepared += 1
    ph = payload_digest(frame.payload)
    pid = pid_for(epoch=frame.epoch, ctr=frame.counter, cmd=frame.command, payload_hash=ph)
    challenge = receiver.issue_crit_challenge(pid)
    ch_dropped, ch_delay, cf_dropped, cf_delay = transport()
    if ch_dropped or cf_dropped:        # challenge/confirm 丢失 -> 放弃、清 pending
        receiver.time_out_critical(pid)
        cost_stats.crit_rejected += 1
        return False
    arrival = now_tick + rtt_ticks + ch_delay + cf_delay
    confirm = sender.confirm_critical_challenge(challenge, now_tick=arrival, tau_intent=tau_intent)
    if confirm is None:                 # 无意图/洗白/过期 -> 不 confirm（attacker 重放落此）
        receiver.time_out_critical(pid)
        cost_stats.crit_rejected += 1
        return False
    result = receiver.process_crit_confirm(confirm, now_tick=arrival)
    if result.accepted:
        cost_stats.crit_committed += 1
        return True
    cost_stats.crit_rejected += 1       # ttl/sw_reject（pending 已在 confirm 内清理）
    return False


def _resolve_reboot_recovery(
    receiver: Receiver,
    sender: Sender,
    *,
    rng: RandomLike,
    now_tick: int,
    ttl_ticks: int,
    rtt_ticks: int,
    transport: Callable[[], tuple[bool, int, bool, int]],
) -> bool:
    """reboot 后认证重建子泵（§8.5, R6）：LOCKED_SAFE 唯一恢复入口往返。
    begin_locked_safe_resync -> challenge -> sender confirm(新 epoch, new_h=tx_counter) -> commit。
    成功 -> sender.adopt_epoch + 退出 LOCKED_SAFE；失败(丢包/TTL) -> 清 pending、保持 LOCKED_SAFE。
    返回是否恢复成功。"""
    if not receiver.state.locked_safe:
        return False
    challenge = receiver.begin_locked_safe_resync(rng, now_tick=now_tick, ttl_ticks=ttl_ticks)
    ch_dropped, ch_delay, cf_dropped, cf_delay = transport()
    if ch_dropped or cf_dropped:
        receiver.time_out_resync()
        return False
    confirm = sender.respond_resync_challenge(challenge)
    arrival = now_tick + rtt_ticks + ch_delay + cf_delay
    result = receiver.process_resync_confirm(confirm, now_tick=arrival)
    if result.reason == "resync_committed":
        sender.adopt_epoch(receiver.state.epoch)
        return True
    receiver.time_out_resync()
    return False


def simulate_one_run(
    config: SimulationConfig,
    rng: RandomLike | None = None,
) -> SimulationRunResult:
    """Simulate one round of legitimate traffic followed by replay attempts."""

    local_rng = _resolve_rng(rng, config.rng_seed)
    tag_bits = _tag_bits(config)
    authenticator = _authenticator(config)

    sender = Sender(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=max(1, tag_bits // 4),
        authenticator=authenticator,
    )
    receiver = Receiver(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=max(1, tag_bits // 4),
        window_size=config.window_size or 1,
        g_hard=config.g_hard,
        authenticator=authenticator,
        max_outstanding_challenges=config.max_outstanding_challenges,
        challenge_ttl_ticks=config.challenge_ttl_ticks,
        command_risk=config.command_risk,
        risk_high=config.risk_high,
        critical_pending_capacity=config.critical_pending_capacity,
        critical_ttl_ticks=config.critical_ttl_ticks,
        policy_source=config.policy_source,
        profile=config.profile,
        command_impact=config.command_impact,
    )
    policy_table = _build_policy_table(config)
    # tx: P_record=1.0 -> always record (ignore record_loss); ind/rx keep configured loss.
    _live_record_loss = 0.0 if config.attacker_position == "tx" else config.attacker_record_loss
    attacker = Attacker(
        record_loss=_live_record_loss,
        target_commands=config.target_commands,
    )
    channel = Channel(
        p_loss=config.p_loss,
        p_reorder=config.p_reorder,
        rng=local_rng,
        loss_model=_loss_model(config),
        delay_model=ReorderDelay(config.p_reorder),
    )

    legit_sent = 0
    legit_accepted = 0
    attack_attempts = 0
    attack_success = 0
    remaining_replays = config.num_replay
    cost_stats = CostStats()

    _resync_rng = local_rng

    def _resync_now_tick() -> int:
        return channel.current_tick

    def _resync_transport() -> tuple[bool, int, bool, int]:
        ch_dropped, ch_delay = _roll_drop_delay(local_rng, config.p_loss, config.p_reorder)
        cf_dropped, cf_delay = _roll_drop_delay(local_rng, config.p_loss, config.p_reorder)
        return ch_dropped, ch_delay, cf_dropped, cf_delay

    def _critical_transport() -> tuple[bool, int, bool, int]:
        ch_dropped, ch_delay = _roll_drop_delay(local_rng, config.p_loss, config.p_reorder)
        cf_dropped, cf_delay = _roll_drop_delay(local_rng, config.p_loss, config.p_reorder)
        return ch_dropped, ch_delay, cf_dropped, cf_delay

    def _reboot_transport() -> tuple[bool, int, bool, int]:
        ch_dropped, ch_delay = _roll_drop_delay(local_rng, config.p_loss, config.p_reorder)
        cf_dropped, cf_delay = _roll_drop_delay(local_rng, config.p_loss, config.p_reorder)
        return ch_dropped, ch_delay, cf_dropped, cf_delay

    def record_tx(frame: Frame) -> None:
        size = _frame_bytes(frame, tag_bits, config.challenge_nonce_bits)
        cost_stats.tx_bytes += size
        if frame.mac is not None:
            if authenticator.profile == "ascon":
                cost_stats.ascon_ops += 1
            else:
                cost_stats.hmac_ops += 1
        cost_stats.state_bytes_peak = max(
            cost_stats.state_bytes_peak,
            _state_bytes(config, receiver),
        )

    def process_arrived(frames: list[Frame]) -> None:
        nonlocal attack_success, legit_accepted
        for frame in frames:
            if config.attacker_position == "rx" and not frame.is_attack:
                attacker.observe(frame, local_rng)  # rx: record only delivered legit frames
            cost_stats.rx_bytes += _frame_bytes(frame, tag_bits, config.challenge_nonce_bits)
            if frame.mac is not None:
                if authenticator.profile == "ascon":
                    cost_stats.ascon_ops += 1
                else:
                    cost_stats.hmac_ops += 1
            cost_stats.state_bytes_peak = max(
                cost_stats.state_bytes_peak,
                _state_bytes(config, receiver),
            )
            if frame.flags == Frame.FLAG_CRIT_PREPARE:   # 两阶段 critical 路由（D2）
                committed = _resolve_critical(
                    receiver,
                    sender,
                    cost_stats,
                    frame=frame,
                    rng=local_rng,
                    now_tick=_resync_now_tick(),
                    ttl_ticks=config.critical_ttl_ticks,
                    rtt_ticks=config.resync_rtt_ticks,
                    tau_intent=config.tau_intent_ticks,
                    transport=_critical_transport,
                )
                if committed:
                    cost_stats.accepted_frames += 1
                    if frame.is_attack:
                        attack_success += 1
                    else:
                        legit_accepted += 1
                continue
            result = receiver.process(frame)
            if result.accepted:
                cost_stats.accepted_frames += 1
                if frame.is_attack:
                    attack_success += 1
                else:
                    legit_accepted += 1
            elif result.reason == "locked_safe_reject":
                cost_stats.locked_safe_rejects += 1
            elif result.reason == "resync_required":
                _resolve_resync(
                    receiver,
                    sender,
                    cost_stats,
                    rng=_resync_rng,
                    now_tick=_resync_now_tick(),
                    ttl_ticks=config.resync_ttl_ticks,
                    rtt_ticks=config.resync_rtt_ticks,
                    transport=_resync_transport,
                )

    for index in range(config.num_legit):
        if (
            config.mode is Mode.HSW_CR
            and config.reboot_at_legit_index is not None
            and index == config.reboot_at_legit_index
        ):
            # §8.5 reboot 注入（仅 HSW_CR）：易失态丢失 + bump epoch + 烧 lease，随后认证重建
            receiver.reboot()
            sender.begin_boot()
            cost_stats.reboots += 1
            if _resolve_reboot_recovery(
                receiver,
                sender,
                rng=local_rng,
                now_tick=channel.current_tick,
                ttl_ticks=config.resync_ttl_ticks,
                rtt_ticks=config.resync_rtt_ticks,
                transport=_reboot_transport,
            ):
                cost_stats.epoch_recoveries += 1
        command = _choose_command(config, index, local_rng)
        if _is_two_phase_critical(config, command, policy_table):
            cost_stats.critical_command_count += 1   # D6：legit 两阶段命令单点计数
            frame = sender.begin_critical_intent(
                command,
                command.encode("utf-8"),
                key_id=0,
                now_tick=channel.current_tick,
            )
        else:
            nonce = None
            if _should_challenge(config, command):
                nonce = receiver.issue_nonce(
                    local_rng,
                    bits=config.challenge_nonce_bits,
                    tick=index + 1,
                )
                cost_stats.challenge_round_trips += 1
            frame = sender.next_frame(command, nonce=nonce)

        record_tx(frame)
        legit_sent += 1
        if config.attacker_position != "rx":
            attacker.observe(frame, local_rng)  # ind/tx: record at send time
        process_arrived(channel.send(frame))

        if config.attack_mode is AttackMode.INLINE:
            for _ in range(max(1, config.inline_attack_burst)):
                if remaining_replays <= 0:
                    break
                if local_rng.random() >= config.inline_attack_probability:
                    break
                attack_frame = attacker.pick_frame(local_rng)
                if attack_frame is None:
                    break

                attack_attempts += 1
                remaining_replays -= 1
                attack_frame.is_attack = True
                record_tx(attack_frame)
                if config.attacker_inject_strength == "weak" and local_rng.random() < 0.5:
                    continue  # weak: attack-only extra drop (transmitted, not delivered)
                process_arrived(channel.send(attack_frame))

    if config.attack_mode is AttackMode.POST_RUN:
        process_arrived(channel.flush())
        for _ in range(remaining_replays):
            attack_frame = attacker.pick_frame(local_rng)
            if attack_frame is None:
                break
            attack_attempts += 1
            attack_frame.is_attack = True
            record_tx(attack_frame)
            if config.attacker_inject_strength == "weak" and local_rng.random() < 0.5:
                continue  # weak: attack-only extra drop (transmitted, not delivered)
            process_arrived(channel.send(attack_frame))

    process_arrived(channel.flush())

    energy = estimate_energy(cost_stats, CostModel())
    legit_rate = legit_accepted / legit_sent if legit_sent else 0.0
    crypto_ops = cost_stats.hmac_ops + cost_stats.ascon_ops
    return SimulationRunResult(
        legit_sent=legit_sent,
        legit_accepted=legit_accepted,
        attack_attempts=attack_attempts,
        attack_success=attack_success,
        mode=config.mode,
        frr=1.0 - legit_rate,
        energy_proxy=energy,
        bytes_overhead=float(cost_stats.tx_bytes + cost_stats.rx_bytes),
        state_bytes=float(cost_stats.state_bytes_peak),
        latency_ticks=(
            cost_stats.latency_ticks_sum / cost_stats.accepted_frames
            if cost_stats.accepted_frames
            else 0.0
        ),
        crypto_ops=float(crypto_ops),
        challenge_round_trips=float(cost_stats.challenge_round_trips),
        resync_initiated=cost_stats.resync_initiated,
        resync_completed=cost_stats.resync_completed,
        resync_timeout=cost_stats.resync_timeout,
        crit_prepared=cost_stats.crit_prepared,
        crit_committed=cost_stats.crit_committed,
        crit_rejected=cost_stats.crit_rejected,
        reboots=cost_stats.reboots,
        locked_safe_rejects=cost_stats.locked_safe_rejects,
        epoch_recoveries=cost_stats.epoch_recoveries,
        critical_command_count=cost_stats.critical_command_count,
        metadata={
            "p_loss": config.p_loss,
            "p_reorder": config.p_reorder,
            "window_size": config.window_size,
            "attack_mode": config.attack_mode.value,
            "auth_profile": authenticator.profile,
        },
    )


def _aggregate_results(
    config: SimulationConfig,
    mode: Mode,
    results: list[SimulationRunResult],
    metadata: dict[str, object],
) -> AggregateStats:
    legit_rates = [result.legit_accept_rate for result in results]
    attack_rates = [result.attack_success_rate for result in results]
    legit_accepted = sum(result.legit_accepted for result in results)
    legit_total = sum(result.legit_sent for result in results)
    attack_accepted = sum(result.attack_success for result in results)
    attack_total = sum(result.attack_attempts for result in results)
    lar_ci = wilson_ci(legit_accepted, legit_total)
    asr_ci = wilson_ci(attack_accepted, attack_total)
    window_value = config.window_size if mode in WINDOW_SIZED_MODES else 0
    return AggregateStats(
        mode=mode,
        runs=len(results),
        avg_legit_rate=_mean(legit_rates),
        std_legit_rate=_std(legit_rates),
        avg_attack_rate=_mean(attack_rates),
        std_attack_rate=_std(attack_rates),
        p_loss=config.p_loss,
        p_reorder=config.p_reorder,
        window_size=window_value,
        num_legit=config.num_legit,
        num_replay=config.num_replay,
        attack_mode=config.attack_mode,
        legit_accepted=legit_accepted,
        legit_total=legit_total,
        attack_accepted=attack_accepted,
        attack_total=attack_total,
        lar_ci_low=lar_ci.lower,
        lar_ci_high=lar_ci.upper,
        asr_ci_low=asr_ci.lower,
        asr_ci_high=asr_ci.upper,
        frr=_mean([result.frr for result in results]),
        energy_proxy=_mean([result.energy_proxy for result in results]),
        bytes_overhead=_mean([result.bytes_overhead for result in results]),
        state_bytes=_mean([result.state_bytes for result in results]),
        latency_ticks=_mean([result.latency_ticks for result in results]),
        crypto_ops=_mean([result.crypto_ops for result in results]),
        challenge_round_trips=_mean([result.challenge_round_trips for result in results]),
        resync_initiated=sum(result.resync_initiated for result in results),
        resync_completed=sum(result.resync_completed for result in results),
        resync_timeout=sum(result.resync_timeout for result in results),
        crit_prepared=sum(result.crit_prepared for result in results),
        crit_committed=sum(result.crit_committed for result in results),
        crit_rejected=sum(result.crit_rejected for result in results),
        reboots=sum(result.reboots for result in results),
        locked_safe_rejects=sum(result.locked_safe_rejects for result in results),
        epoch_recoveries=sum(result.epoch_recoveries for result in results),
        critical_command_count=sum(result.critical_command_count for result in results),
        mac_tag_bits=_tag_bits(config),
        auth_profile=config.auth_profile,
        metadata=metadata,
    )


def run_many_experiments(
    base_config: SimulationConfig,
    modes: Sequence[Mode],
    runs: int,
    seed: int | None = None,
    show_progress: bool = True,
) -> list[AggregateStats]:
    """Run multiple Monte Carlo trials for each requested mode with visual progress."""

    start_time = time.time()
    per_mode_configs = {mode: dataclasses.replace(base_config, mode=mode) for mode in modes}
    per_mode_results: dict[Mode, list[SimulationRunResult]] = {mode: [] for mode in modes}

    if show_progress:
        print("\n" + "=" * 80)
        print("STARTING MONTE CARLO SIMULATION")
        print("=" * 80 + "\n")

    for mode in modes:
        mode_rng = DeterministicRNG(seed)
        for run_idx in range(runs):
            scenario_seed = mode_rng.randint(0, 2**31 - 1)
            scenario_rng = DeterministicRNG(scenario_seed)
            result = simulate_one_run(per_mode_configs[mode], rng=scenario_rng)
            per_mode_results[mode].append(result)

            if show_progress and ((run_idx + 1) % 10 == 0 or run_idx == runs - 1):
                bar_length = 50
                filled = int(bar_length * (run_idx + 1) / runs)
                bar = "#" * filled + "." * (bar_length - filled)
                sys.stdout.write(f"\r   Progress: [{bar}] {run_idx + 1}/{runs} runs")
                sys.stdout.flush()
        if show_progress:
            print()

    total_time = time.time() - start_time
    perf_metadata = {
        "total_time": total_time,
        "time_per_run": total_time / (len(modes) * runs) if runs > 0 else 0,
        "total_runs": len(modes) * runs,
    }
    return [
        _aggregate_results(config, mode, per_mode_results[mode], dict(perf_metadata))
        for mode, config in per_mode_configs.items()
    ]


def run_until_precision(
    config: SimulationConfig,
    *,
    mode: Mode,
    target_half_width: float,
    max_runs: int,
    seed: int | None,
    min_runs: int = 30,
    metric: str = "asr",
) -> tuple[AggregateStats, int]:
    cfg = dataclasses.replace(config, mode=mode)
    mode_rng = DeterministicRNG(seed)
    results: list[SimulationRunResult] = []
    for _ in range(max_runs):
        scenario_seed = mode_rng.randint(0, 2**31 - 1)
        results.append(simulate_one_run(cfg, rng=DeterministicRNG(scenario_seed)))
        if len(results) >= min_runs:
            legit_accepted = sum(result.legit_accepted for result in results)
            legit_total = sum(result.legit_sent for result in results)
            attack_accepted = sum(result.attack_success for result in results)
            attack_total = sum(result.attack_attempts for result in results)
            ci = (
                wilson_ci(attack_accepted, attack_total)
                if metric == "asr"
                else wilson_ci(legit_accepted, legit_total)
            )
            if ci.half_width <= target_half_width:
                break
    stats = _aggregate_results(
        cfg,
        mode,
        results,
        {"stopping": "sequential", "target_half_width": target_half_width},
    )
    return stats, len(results)


def simulate_one_run_with_trace(
    config: SimulationConfig,
    trace: ScenarioTrace,
    *,
    nonce_seed: int | None = None,
) -> SimulationRunResult:
    """Simulate one run while consuming a pre-generated channel/attacker trace."""

    tag_bits = _tag_bits(config)
    authenticator = _authenticator(config)
    nonce_rng = DeterministicRNG(nonce_seed)
    sender = Sender(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=max(1, tag_bits // 4),
        authenticator=authenticator,
    )
    receiver = Receiver(
        mode=config.mode,
        shared_key=config.shared_key,
        mac_length=max(1, tag_bits // 4),
        window_size=config.window_size or 1,
        g_hard=config.g_hard,
        authenticator=authenticator,
        max_outstanding_challenges=config.max_outstanding_challenges,
        challenge_ttl_ticks=config.challenge_ttl_ticks,
        command_risk=config.command_risk,
        risk_high=config.risk_high,
        critical_pending_capacity=config.critical_pending_capacity,
        critical_ttl_ticks=config.critical_ttl_ticks,
        policy_source=config.policy_source,
        profile=config.profile,
        command_impact=config.command_impact,
    )
    policy_table = _build_policy_table(config)

    scheduler = EventScheduler()
    recorded: list[Frame] = []
    # Paired path delegates frame selection to a strategy (P1). RandomReplay
    # reproduces the legacy pick_replay byte-for-byte; P3 swaps in adaptive ones.
    replay_strategy: AttackerStrategy = RandomReplay(target_commands=config.target_commands)
    # rx records at DELIVERY, not at send: map engine frame id -> record decision, consumed
    # in process_arrived when the frame is actually delivered (handles legit_delay > 0).
    rx_pending: dict[int, bool] = {}
    legit_sent = 0
    legit_accepted = 0
    attack_attempts = 0
    attack_success = 0
    remaining_replays = config.num_replay
    replay_index = 0
    inline_slot = 0
    cost_stats = CostStats()

    _resync_rng = nonce_rng
    resync_index = 0
    critical_index = 0

    def _resync_now_tick() -> int:
        return scheduler.current_tick

    def _resync_transport() -> tuple[bool, int, bool, int]:
        nonlocal resync_index
        i = resync_index
        resync_index += 1
        if i >= len(trace.resync_challenge_dropped):
            return False, 0, False, 0
        return (
            trace.resync_challenge_dropped[i],
            trace.resync_challenge_delay[i],
            trace.resync_confirm_dropped[i],
            trace.resync_confirm_delay[i],
        )

    def _critical_transport() -> tuple[bool, int, bool, int]:
        nonlocal critical_index
        i = critical_index
        critical_index += 1
        if i >= len(trace.critical_challenge_dropped):
            return False, 0, False, 0
        return (
            trace.critical_challenge_dropped[i],
            trace.critical_challenge_delay[i],
            trace.critical_confirm_dropped[i],
            trace.critical_confirm_delay[i],
        )

    def _reboot_transport() -> tuple[bool, int, bool, int]:
        if not trace.reboot_challenge_dropped:
            return False, 0, False, 0
        return (
            trace.reboot_challenge_dropped[0],
            trace.reboot_challenge_delay[0],
            trace.reboot_confirm_dropped[0],
            trace.reboot_confirm_delay[0],
        )

    def record_tx(frame: Frame) -> None:
        size = _frame_bytes(frame, tag_bits, config.challenge_nonce_bits)
        cost_stats.tx_bytes += size
        if frame.mac is not None:
            if authenticator.profile == "ascon":
                cost_stats.ascon_ops += 1
            else:
                cost_stats.hmac_ops += 1
        cost_stats.state_bytes_peak = max(
            cost_stats.state_bytes_peak,
            _state_bytes(config, receiver),
        )

    def process_arrived(frames: list[Frame]) -> None:
        nonlocal attack_success, legit_accepted
        for frame in frames:
            if not frame.is_attack and rx_pending.pop(id(frame), False):
                recorded.append(frame.clone())  # rx: record at actual delivery
            cost_stats.rx_bytes += _frame_bytes(frame, tag_bits, config.challenge_nonce_bits)
            if frame.mac is not None:
                if authenticator.profile == "ascon":
                    cost_stats.ascon_ops += 1
                else:
                    cost_stats.hmac_ops += 1
            cost_stats.state_bytes_peak = max(
                cost_stats.state_bytes_peak,
                _state_bytes(config, receiver),
            )
            if frame.flags == Frame.FLAG_CRIT_PREPARE:   # 两阶段 critical 路由（D2）
                committed = _resolve_critical(
                    receiver,
                    sender,
                    cost_stats,
                    frame=frame,
                    rng=nonce_rng,
                    now_tick=_resync_now_tick(),
                    ttl_ticks=config.critical_ttl_ticks,
                    rtt_ticks=config.resync_rtt_ticks,
                    tau_intent=config.tau_intent_ticks,
                    transport=_critical_transport,
                )
                if committed:
                    cost_stats.accepted_frames += 1
                    if frame.is_attack:
                        attack_success += 1
                    else:
                        legit_accepted += 1
                continue
            result = receiver.process(frame)
            if result.accepted:
                cost_stats.accepted_frames += 1
                if frame.is_attack:
                    attack_success += 1
                else:
                    legit_accepted += 1
            elif result.reason == "locked_safe_reject":
                cost_stats.locked_safe_rejects += 1
            elif result.reason == "resync_required":
                _resolve_resync(
                    receiver,
                    sender,
                    cost_stats,
                    rng=_resync_rng,
                    now_tick=_resync_now_tick(),
                    ttl_ticks=config.resync_ttl_ticks,
                    rtt_ticks=config.resync_rtt_ticks,
                    transport=_resync_transport,
                )

    def send_traced(frame: Frame, *, dropped: bool, delay: int) -> list[Frame]:
        tick = scheduler.tick()
        if not dropped:
            scheduler.submit(frame, delivery_tick=tick + delay)
        return scheduler.pop_due()

    def flush_traced() -> list[Frame]:
        return scheduler.flush()

    def pick_replay(raw_pick: int) -> Frame | None:
        # Delegate to the strategy (P1). RandomReplay == legacy logic byte-for-byte.
        return replay_strategy.pick_recorded(raw_pick, recorded)

    def attempt_replay() -> bool:
        nonlocal attack_attempts, attack_success, remaining_replays, replay_index
        if remaining_replays <= 0 or replay_index >= len(trace.replay_pick):
            return False
        attack_frame = pick_replay(trace.replay_pick[replay_index])
        if attack_frame is None:
            return False
        attack_frame.is_attack = True
        attack_attempts += 1
        remaining_replays -= 1
        record_tx(attack_frame)
        extra_dropped = (
            config.attacker_inject_strength == "weak"
            and trace.attack_extra_dropped[replay_index]
        )
        process_arrived(
            send_traced(
                attack_frame,
                dropped=trace.replay_dropped[replay_index] or extra_dropped,
                delay=trace.replay_delay[replay_index],
            )
        )
        replay_index += 1
        return True

    for index, command in enumerate(trace.commands[: config.num_legit]):
        if (
            config.mode is Mode.HSW_CR
            and config.reboot_at_legit_index is not None
            and index == config.reboot_at_legit_index
        ):
            # §8.5 reboot 注入（仅 HSW_CR）：易失态丢失 + bump epoch + 烧 lease，随后认证重建
            receiver.reboot()
            sender.begin_boot()
            cost_stats.reboots += 1
            if _resolve_reboot_recovery(
                receiver,
                sender,
                rng=nonce_rng,
                now_tick=scheduler.current_tick,
                ttl_ticks=config.resync_ttl_ticks,
                rtt_ticks=config.resync_rtt_ticks,
                transport=_reboot_transport,
            ):
                cost_stats.epoch_recoveries += 1
        if _is_two_phase_critical(config, command, policy_table):
            cost_stats.critical_command_count += 1   # D6：legit 两阶段命令单点计数
            frame = sender.begin_critical_intent(
                command,
                command.encode("utf-8"),
                key_id=0,
                now_tick=scheduler.current_tick,
            )
        else:
            nonce = None
            if _should_challenge(config, command):
                nonce = receiver.issue_nonce(
                    nonce_rng,
                    bits=config.challenge_nonce_bits,
                    tick=index + 1,
                )
                cost_stats.challenge_round_trips += 1
            frame = sender.next_frame(command, nonce=nonce)

        record_tx(frame)
        legit_sent += 1
        if config.attacker_position == "rx":
            # defer: record only once the frame is actually delivered (process_arrived)
            if not trace.legit_dropped[index]:
                rx_pending[id(frame)] = not trace.attacker_record_dropped[index]
        elif _should_record_paired(
            config.attacker_position,
            legit_dropped=trace.legit_dropped[index],
            record_dropped=trace.attacker_record_dropped[index],
        ):
            recorded.append(frame.clone())
        process_arrived(
            send_traced(
                frame,
                dropped=trace.legit_dropped[index],
                delay=trace.legit_delay[index],
            )
        )

        if config.attack_mode is AttackMode.INLINE:
            for _ in range(max(1, config.inline_attack_burst)):
                if inline_slot >= len(trace.inline_attempt):
                    break
                should_attempt = trace.inline_attempt[inline_slot]
                inline_slot += 1
                if not should_attempt:
                    break
                if not attempt_replay():
                    break

    if config.attack_mode is AttackMode.POST_RUN:
        process_arrived(flush_traced())
        for _ in range(remaining_replays):
            if not attempt_replay():
                break

    process_arrived(flush_traced())

    energy = estimate_energy(cost_stats, CostModel())
    legit_rate = legit_accepted / legit_sent if legit_sent else 0.0
    crypto_ops = cost_stats.hmac_ops + cost_stats.ascon_ops
    return SimulationRunResult(
        legit_sent=legit_sent,
        legit_accepted=legit_accepted,
        attack_attempts=attack_attempts,
        attack_success=attack_success,
        mode=config.mode,
        frr=1.0 - legit_rate,
        energy_proxy=energy,
        bytes_overhead=float(cost_stats.tx_bytes + cost_stats.rx_bytes),
        state_bytes=float(cost_stats.state_bytes_peak),
        latency_ticks=(
            cost_stats.latency_ticks_sum / cost_stats.accepted_frames
            if cost_stats.accepted_frames
            else 0.0
        ),
        crypto_ops=float(crypto_ops),
        challenge_round_trips=float(cost_stats.challenge_round_trips),
        resync_initiated=cost_stats.resync_initiated,
        resync_completed=cost_stats.resync_completed,
        resync_timeout=cost_stats.resync_timeout,
        crit_prepared=cost_stats.crit_prepared,
        crit_committed=cost_stats.crit_committed,
        crit_rejected=cost_stats.crit_rejected,
        reboots=cost_stats.reboots,
        locked_safe_rejects=cost_stats.locked_safe_rejects,
        epoch_recoveries=cost_stats.epoch_recoveries,
        critical_command_count=cost_stats.critical_command_count,
        metadata={
            "p_loss": config.p_loss,
            "p_reorder": config.p_reorder,
            "window_size": config.window_size,
            "attack_mode": config.attack_mode.value,
            "auth_profile": authenticator.profile,
            "trace_digest": trace.digest(),
            "legit_drop_count": trace.legit_drop_count,
        },
    )


def run_paired_experiments(
    base_config: SimulationConfig,
    modes: Sequence[Mode],
    runs: int,
    seed: int | None = None,
    show_progress: bool = True,
) -> list[AggregateStats]:
    trace_rng = DeterministicRNG(seed)
    trace_seeds = [trace_rng.randint(0, 2**31 - 1) for _ in range(runs)]
    traces = [generate_trace(base_config, trace_seed) for trace_seed in trace_seeds]
    trace_digests = [trace.digest() for trace in traces]
    legit_drop_counts = [trace.legit_drop_count for trace in traces]
    per_mode_configs = {mode: dataclasses.replace(base_config, mode=mode) for mode in modes}
    per_mode_results: dict[Mode, list[SimulationRunResult]] = {mode: [] for mode in modes}

    if show_progress:
        print("\n" + "=" * 80)
        print("STARTING PAIRED MONTE CARLO SIMULATION")
        print("=" * 80 + "\n")

    for run_idx, (trace_seed, trace) in enumerate(zip(trace_seeds, traces)):
        for mode, config in per_mode_configs.items():
            mode_seed = trace_seed + sum(mode.value.encode("utf-8"))
            per_mode_results[mode].append(
                simulate_one_run_with_trace(config, trace, nonce_seed=mode_seed)
            )
        if show_progress and ((run_idx + 1) % 10 == 0 or run_idx == runs - 1):
            bar_length = 50
            filled = int(bar_length * (run_idx + 1) / runs)
            bar = "#" * filled + "." * (bar_length - filled)
            sys.stdout.write(f"\r   Progress: [{bar}] {run_idx + 1}/{runs} runs")
            sys.stdout.flush()

    if show_progress:
        print()

    stats: list[AggregateStats] = []
    for mode, config in per_mode_configs.items():
        stats.append(
            _aggregate_results(
                config,
                mode,
                per_mode_results[mode],
                {
                    "paired": True,
                    "trace_digests": trace_digests,
                    "legit_drop_counts_by_run": legit_drop_counts,
                },
            )
        )
    return stats


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.fmean(values)


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return statistics.stdev(values)
