"""一次性脚本：用迁移前的引擎冻结两套路径的数值基线到 tests/fixtures/engine_baseline.json。
迁移完成后此脚本不再运行（基线已提交）；如需重生成必须在 Task 1.5.0 提交点的代码上运行。"""
from __future__ import annotations

import json
from pathlib import Path

from replay.core import Mode, SimulationConfig, run_many_experiments, run_paired_experiments
from replay.core.types import AttackMode

SEED = 42
RUNS = 8
MODES = [
    Mode.NO_DEFENSE,
    Mode.ROLLING_MAC,
    Mode.WINDOW,
    Mode.SW_RESYNC,
    Mode.CHALLENGE,
    Mode.HSW_CR,
    Mode.OSCORE_LIKE,
]
RISK = {"UNLOCK": 1.0}  # 让 HSW_CR/CHALLENGE 路径产生高风险分支


def _base(attack_mode: AttackMode) -> SimulationConfig:
    return SimulationConfig(
        mode=Mode.NO_DEFENSE,            # 占位，run_* 会按 mode 替换
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


def main() -> None:
    baseline: dict = {"seed": SEED, "runs": RUNS, "cases": {}}
    for attack_mode in (AttackMode.POST_RUN, AttackMode.INLINE):
        cfg = _base(attack_mode)
        baseline["cases"][f"normal/{attack_mode.value}"] = _snap(
            run_many_experiments(cfg, modes=MODES, runs=RUNS, seed=SEED, show_progress=False)
        )
        baseline["cases"][f"paired/{attack_mode.value}"] = _snap(
            run_paired_experiments(cfg, modes=MODES, runs=RUNS, seed=SEED, show_progress=False)
        )
    out = Path("tests/fixtures/engine_baseline.json")
    out.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} with {len(baseline['cases'])} cases")


if __name__ == "__main__":
    main()
