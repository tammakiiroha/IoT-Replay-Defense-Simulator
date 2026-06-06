from replay.core import Mode, SimulationConfig
from replay.core.experiment import simulate_one_run
from replay.core.rng import DeterministicRNG


def _resync_cfg():
    # 高丢包 + 小 g_hard：连续丢包制造前跳越闸，触发 resync 子泵
    return SimulationConfig(
        mode=Mode.SW_RESYNC,
        num_legit=60,
        num_replay=0,
        p_loss=0.5,
        p_reorder=0.0,
        window_size=3,
        g_hard=2,
        rng_seed=7,
        command_set=["A"],
        resync_ttl_ticks=16,
        resync_rtt_ticks=1,
    )


def test_resync_sub_pump_initiates_and_resolves():
    res = simulate_one_run(_resync_cfg(), rng=DeterministicRNG(7))
    md = res.metadata
    assert md["resync_initiated"] >= 1
    # 每个发起的 resync 必须解析为 completed 或 timeout（无悬挂）
    assert md["resync_initiated"] == md["resync_completed"] + md["resync_timeout"]


def test_resync_completes_at_least_once_in_engine():
    # 引擎内确实完成过重同步（challenge+confirm 存活 -> 封窗恢复）
    res = simulate_one_run(_resync_cfg(), rng=DeterministicRNG(7))
    assert res.metadata["resync_completed"] >= 1
