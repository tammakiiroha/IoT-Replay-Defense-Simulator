from replay.services.advisor import DeviceProfile, recommend


def test_recommend_challenges_high_risk_unlock():
    rec = recommend(
        DeviceProfile(
            commands=["PING", "STATUS", "LOCK", "UNLOCK"],
            command_risk={"PING": 0.1, "STATUS": 0.2, "LOCK": 0.7, "UNLOCK": 1.0},
            p_loss=0.05,
            p_reorder=0.05,
            ram_budget_bytes=128,
            max_latency_ticks=2,
            target_asr=0.05,
            seed=1,
        )
    )

    assert "UNLOCK" in rec.challenge_for
    assert rec.mode == "hsw_cr"
    assert rec.mac_tag_bits in {80, 96, 128}
    assert rec.predicted_asr <= 0.05 or rec.constraint_status == "best_effort"


def test_recommend_respects_tiny_state_budget():
    rec = recommend(
        DeviceProfile(
            commands=["PING", "UNLOCK"],
            command_risk={"PING": 0.1, "UNLOCK": 1.0},
            p_loss=0.0,
            p_reorder=0.0,
            ram_budget_bytes=8,
            max_latency_ticks=1,
            target_asr=0.05,
            seed=2,
        )
    )

    assert rec.state_bytes <= 8
