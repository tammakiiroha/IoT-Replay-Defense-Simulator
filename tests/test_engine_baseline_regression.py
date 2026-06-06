import json
from pathlib import Path

import pytest

from replay.core import Mode, SimulationConfig, run_many_experiments, run_paired_experiments
from replay.core.types import AttackMode

_BASELINE = json.loads(Path("tests/fixtures/engine_baseline.json").read_text())
SEED = _BASELINE["seed"]
RUNS = _BASELINE["runs"]
MODES = [
    Mode.NO_DEFENSE,
    Mode.ROLLING_MAC,
    Mode.WINDOW,
    Mode.SW_RESYNC,
    Mode.CHALLENGE,
    Mode.HSW_CR,
    Mode.OSCORE_LIKE,
]
RISK = {"UNLOCK": 1.0}


def _base(attack_mode: AttackMode) -> SimulationConfig:
    return SimulationConfig(
        mode=Mode.NO_DEFENSE,
        attack_mode=attack_mode,
        num_legit=20,
        num_replay=30,
        p_loss=0.1,
        p_reorder=0.1,
        window_size=5,
        g_hard=16,
        rng_seed=SEED,
        command_set=["UNLOCK", "LOCK", "PING"],
        command_risk=RISK,
        risk_high=0.8,
    )


def _snap(stats_list) -> dict:
    return {
        str(s.mode): {
            "legit_accepted": s.legit_accepted,
            "legit_total": s.legit_total,
            "attack_accepted": s.attack_accepted,
            "attack_total": s.attack_total,
        }
        for s in stats_list
    }


@pytest.mark.parametrize("attack_mode", [AttackMode.POST_RUN, AttackMode.INLINE])
def test_normal_path_matches_baseline(attack_mode):
    got = _snap(
        run_many_experiments(_base(attack_mode), modes=MODES, runs=RUNS, seed=SEED, show_progress=False)
    )
    assert got == _BASELINE["cases"][f"normal/{attack_mode.value}"]


@pytest.mark.parametrize("attack_mode", [AttackMode.POST_RUN, AttackMode.INLINE])
def test_paired_path_matches_baseline(attack_mode):
    got = _snap(
        run_paired_experiments(_base(attack_mode), modes=MODES, runs=RUNS, seed=SEED, show_progress=False)
    )
    assert got == _BASELINE["cases"][f"paired/{attack_mode.value}"]
