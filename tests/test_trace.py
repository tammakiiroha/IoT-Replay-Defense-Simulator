from replay.core import Mode, SimulationConfig
from replay.core.experiment import run_paired_experiments, simulate_one_run_with_trace
from replay.core.trace import generate_trace


def test_generated_trace_is_deterministic_under_seed():
    cfg = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=8,
        num_replay=8,
        p_loss=0.3,
        p_reorder=0.3,
    )

    first = generate_trace(cfg, seed=7)
    second = generate_trace(cfg, seed=7)

    assert first == second
    assert first.digest() == second.digest()


def test_paired_runs_share_identical_channel_trace():
    cfg = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=8,
        num_replay=8,
        p_loss=0.3,
        p_reorder=0.3,
    )

    stats = run_paired_experiments(
        cfg,
        modes=[Mode.ROLLING_MAC, Mode.WINDOW],
        runs=20,
        seed=7,
        show_progress=False,
    )
    rolling = next(entry for entry in stats if entry.mode is Mode.ROLLING_MAC)
    window = next(entry for entry in stats if entry.mode is Mode.WINDOW)

    assert rolling.metadata["paired"] is True
    assert rolling.metadata["trace_digests"] == window.metadata["trace_digests"]
    assert (
        rolling.metadata["legit_drop_counts_by_run"]
        == window.metadata["legit_drop_counts_by_run"]
    )
    assert len(rolling.metadata["trace_digests"]) == 20


def test_trace_replay_controls_legitimate_drop_count():
    cfg = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=10,
        num_replay=0,
        p_loss=0.5,
        p_reorder=0.0,
    )
    trace = generate_trace(cfg, seed=11)

    result = simulate_one_run_with_trace(cfg, trace, nonce_seed=1)

    assert result.legit_sent == 10
    assert result.legit_accepted == 10 - trace.legit_drop_count
    assert result.metadata["trace_digest"] == trace.digest()
