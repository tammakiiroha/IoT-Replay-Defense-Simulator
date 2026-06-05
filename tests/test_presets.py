from replay.core.presets import load_preset


def test_smart_lock_preset_loads_and_marks_unlock_high_risk():
    spec = load_preset("smart_lock")

    assert "UNLOCK" in (spec.command_set or [])
    assert (spec.command_risk or {}).get("UNLOCK", 0) >= 0.9
    assert spec.modes == ["hsw_cr"]
    assert spec.channel_model == "gilbert_elliott"
