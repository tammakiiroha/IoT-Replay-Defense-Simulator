from physical_experiment.analysis.compare_sim_vs_hw import (
    parse_hardware_results,
    parse_simulation_sweep,
)


def test_parse_simulation_sweep_prefers_canonical_schema_keys():
    series = parse_simulation_sweep(
        [
            {
                "mode": "window",
                "p_loss": 0.1,
                "avg_legit_rate": 0.91,
                "std_legit_rate": 0.03,
                "avg_legit_accept_rate": 0.12,
                "std_legit_accept_rate": 0.11,
                "avg_attack_rate": 0.07,
                "std_attack_rate": 0.02,
                "avg_attack_success_rate": 0.66,
                "std_attack_success_rate": 0.55,
                "runs": 10,
            }
        ],
        sweep_type="p_loss",
    )

    legit = series["window_legit"].points[0]
    attack = series["window_attack"].points[0]

    assert legit.mean == 0.91
    assert legit.std == 0.03
    assert attack.mean == 0.07
    assert attack.std == 0.02


def test_parse_hardware_results_prefers_canonical_schema_keys():
    series = parse_hardware_results(
        [
            {
                "results": [
                    {
                        "config_name": "window_w5",
                        "mode": "window",
                        "window_size": 5,
                        "avg_legit_rate": 0.88,
                        "avg_legit_accept_rate": 0.10,
                        "avg_attack_rate": 0.04,
                        "avg_attack_success_rate": 0.90,
                    }
                ]
            }
        ]
    )

    legit = series["window_w5_legit"].points[0]
    attack = series["window_w5_attack"].points[0]

    assert legit.mean == 0.88
    assert attack.mean == 0.04
