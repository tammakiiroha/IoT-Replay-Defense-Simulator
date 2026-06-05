from replay.core.risk import RiskContext, choose_defense_mode, compute_risk


def test_high_value_command_forces_high_risk():
    ctx = RiskContext(
        command="UNLOCK",
        counter_gap=0,
        duplicate_rate=0.0,
        recent_loss_rate=0.0,
        recent_reorder_rate=0.0,
        is_high_value_state=True,
    )

    risk = compute_risk(ctx, command_risk={"UNLOCK": 1.0})

    assert risk >= 0.4
    assert choose_defense_mode(risk) in {"challenge", "lockdown"}


def test_low_risk_picks_window():
    ctx = RiskContext("PING", 0, 0.0, 0.0, 0.0, False)

    assert choose_defense_mode(compute_risk(ctx, {"PING": 0.1})) == "window"
