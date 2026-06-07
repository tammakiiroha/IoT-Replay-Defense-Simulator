from replay.contracts import SimulationSpec, SimulationSpecPublic


def test_spec_accepts_g_hard():
    spec = SimulationSpec(modes=["window"], runs=2, window_size=5, g_hard=32)
    assert spec.g_hard == 32
    assert spec.to_runtime_config().g_hard == 32


def test_spec_accepts_sw_resync_and_public_preserves_it():
    # 修审查 P2：baseline 分流 mode 必须贯通契约 + public 视图（仅断言 g_hard 不够）
    spec = SimulationSpec(modes=["window", "sw_resync"], runs=2, window_size=5, g_hard=32)
    assert "sw_resync" in [str(m) for m in spec.modes]
    pub = SimulationSpecPublic.from_spec(spec)
    assert "sw_resync" in [str(m) for m in pub.modes]
    assert pub.g_hard == 32


def test_sw_resync_requires_window_size():
    # SW_RESYNC 走 window 验证路径，window_size=0 必须被拒（WINDOW_SIZED_MODES 覆盖）
    import pytest

    with pytest.raises(ValueError):
        SimulationSpec(modes=["sw_resync"], runs=2, window_size=0)
