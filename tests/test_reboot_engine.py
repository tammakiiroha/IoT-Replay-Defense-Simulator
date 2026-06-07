import dataclasses
import random

from replay.core.experiment import (
    _resolve_reboot_recovery,
    simulate_one_run,
    simulate_one_run_with_trace,
)
from replay.core.receiver import Receiver
from replay.core.sender import Sender
from replay.core.trace import generate_trace
from replay.core.types import AttackMode, Mode, SimulationConfig

KEY = "sim_shared_key"


def _cfg(**kw) -> SimulationConfig:
    base = SimulationConfig(
        mode=Mode.HSW_CR,
        attack_mode=AttackMode.POST_RUN,
        num_legit=6,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.0,
        window_size=8,
        g_hard=16,
        rng_seed=7,
        command_sequence=["PING"],
        command_set=["PING", "OPEN"],
        command_risk={"OPEN": 1.0},
        risk_high=0.8,
    )
    return dataclasses.replace(base, **kw)


def _rebooted_pair() -> tuple[Receiver, Sender]:
    rcv = Receiver(
        Mode.HSW_CR, shared_key=KEY, mac_length=8, window_size=8,
        command_risk={"OPEN": 1.0}, risk_high=0.8,
    )
    sender = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8)
    sender.tx_counter = 30
    rcv.reboot()          # epoch 0->1, locked_safe
    sender.begin_boot()   # 烧旧 lease
    return rcv, sender


def test_resolve_reboot_recovery_clean_succeeds():
    rcv, sender = _rebooted_pair()
    ok = _resolve_reboot_recovery(
        rcv, sender, rng=random.Random(1), now_tick=0,
        ttl_ticks=16, rtt_ticks=1, transport=lambda: (False, 0, False, 0),
    )
    assert ok is True
    assert rcv.state.locked_safe is False
    assert sender.current_epoch == rcv.state.epoch == 1


def test_resolve_reboot_recovery_confirm_drop_stays_locked():
    rcv, sender = _rebooted_pair()
    ok = _resolve_reboot_recovery(
        rcv, sender, rng=random.Random(1), now_tick=0,
        ttl_ticks=16, rtt_ticks=1, transport=lambda: (False, 0, True, 0),
    )
    assert ok is False
    assert rcv.state.locked_safe is True


def test_hsw_cr_reboot_then_recover_resumes_traffic():
    res = simulate_one_run(_cfg(reboot_at_legit_index=3))
    assert res.legit_sent == 6
    assert res.legit_accepted == 6   # 前 3 + 恢复 + 后 3 全 accept（clean channel）


def test_paired_reboot_recovery_drop_blocks_post_reboot_traffic():
    # 强制恢复信道丢失 -> recovery 失败 -> 后 reboot 帧 LOCKED_SAFE 被拒（区分接线是否生效）
    cfg = _cfg(reboot_at_legit_index=3)
    trace = generate_trace(cfg, seed=7)
    trace = dataclasses.replace(
        trace, reboot_challenge_dropped=[True], reboot_confirm_dropped=[True],
    )
    res = simulate_one_run_with_trace(cfg, trace, nonce_seed=7)
    assert res.legit_sent == 6
    assert res.legit_accepted == 3   # 仅 reboot 前 3 帧


def test_replayed_old_epoch_frame_after_reboot_does_not_commit():
    res = simulate_one_run(_cfg(command_sequence=["OPEN"], reboot_at_legit_index=2, num_replay=5))
    assert res.attack_success == 0
    assert res.attack_attempts >= 1


def test_baseline_stable_modes_unchanged_with_reboot_engine():
    cfg_no = _cfg(mode=Mode.WINDOW, command_sequence=["PING"], command_set=["PING"])
    cfg_reboot = dataclasses.replace(cfg_no, reboot_at_legit_index=2)
    r1 = simulate_one_run(cfg_no)
    r2 = simulate_one_run(cfg_reboot)
    assert (r1.legit_accepted, r1.attack_success) == (r2.legit_accepted, r2.attack_success)
    assert (r1.legit_sent, r1.bytes_overhead) == (r2.legit_sent, r2.bytes_overhead)
