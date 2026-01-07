"""
Tests for Experiment module

验证：
- 蒙特卡洛统计计算正确性
- 固定种子可重现性
- 平均值/标准差计算
- 实验参数边界条件
"""

import pytest
from sim.experiment import run_many_experiments, simulate_one_run
from sim.types import SimulationConfig, Mode, AttackMode


# ============================================================================
# Test: Basic Experiment Execution
# ============================================================================

def test_single_experiment_no_defense():
    """测试单次实验（无防御）"""
    config = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    result = simulate_one_run(config)
    
    assert result is not None
    assert result.legit_sent == 10
    assert result.legit_accepted >= 0
    assert result.attack_attempts >= 0


def test_single_experiment_rolling():
    """测试单次实验（滚动计数器）"""
    config = SimulationConfig(
        mode=Mode.ROLLING_MAC,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    result = simulate_one_run(config)
    assert result is not None


def test_single_experiment_window():
    """测试单次实验（滑动窗口）"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    result = simulate_one_run(config)
    assert result is not None


def test_single_experiment_challenge():
    """测试单次实验（挑战-响应）"""
    config = SimulationConfig(
        mode=Mode.CHALLENGE,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    result = simulate_one_run(config)
    assert result is not None


# ============================================================================
# Test: Monte Carlo Statistics
# ============================================================================

def test_multiple_runs_statistical_properties():
    """测试多次运行的统计特性"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=10,
        p_loss=0.1,
        p_reorder=0.1,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.WINDOW], runs=50, show_progress=False)
    
    assert len(results) > 0
    result = results[0]
    
    # 验证值的合理范围
    assert 0.0 <= result.avg_legit_rate <= 1.0
    assert 0.0 <= result.std_legit_rate <= 1.0
    assert 0.0 <= result.avg_attack_rate <= 1.0
    assert 0.0 <= result.std_attack_rate <= 1.0


def test_average_calculation():
    """测试平均值计算正确性"""
    config = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    # 理想信道+无防御：合法包应该100%接受
    results = run_many_experiments(config, modes=[Mode.NO_DEFENSE], runs=20, show_progress=False)
    
    assert len(results) > 0
    # 无丢包无乱序，合法包接受率应该接近1.0
    assert results[0].avg_legit_rate > 0.95


def test_standard_deviation_calculation():
    """测试标准差计算"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=10,
        num_replay=5,
        p_loss=0.2,  # 较高丢包率，增加方差
        p_reorder=0.2,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.WINDOW], runs=50, show_progress=False)
    
    assert len(results) > 0
    result = results[0]
    
    # 标准差应该>=0
    assert result.std_legit_rate >= 0.0
    assert result.std_attack_rate >= 0.0


def test_zero_variance_in_ideal_conditions():
    """测试理想条件下的零方差"""
    config = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.NO_DEFENSE], runs=20, show_progress=False)
    
    assert len(results) > 0
    # 理想条件下，结果应该一致，标准差接近0
    assert results[0].std_legit_rate < 0.01  # 允许浮点误差


# ============================================================================
# Test: Reproducibility (Seed)
# ============================================================================

def test_reproducibility_with_fixed_seed():
    """测试固定种子的完全可重现性"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=10,
        p_loss=0.1,
        p_reorder=0.1,
        attacker_record_loss=0.1,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    # 第一次运行
    results1 = run_many_experiments(config, modes=[Mode.WINDOW], runs=30, seed=42, show_progress=False)
    
    # 第二次运行（相同配置）
    results2 = run_many_experiments(config, modes=[Mode.WINDOW], runs=30, seed=42, show_progress=False)
    
    assert len(results1) > 0
    assert len(results2) > 0
    
    # 应该完全相同
    assert results1[0].avg_legit_rate == results2[0].avg_legit_rate
    assert results1[0].std_legit_rate == results2[0].std_legit_rate
    assert results1[0].avg_attack_rate == results2[0].avg_attack_rate
    assert results1[0].std_attack_rate == results2[0].std_attack_rate


def test_different_seeds_different_results():
    """测试不同种子产生不同结果"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=10,
        p_loss=0.2,
        p_reorder=0.2,
        attacker_record_loss=0.1,
        window_size=5,
        attack_mode=AttackMode.POST_RUN
    )
    
    results1 = run_many_experiments(config, modes=[Mode.WINDOW], runs=30, seed=42, show_progress=False)
    results2 = run_many_experiments(config, modes=[Mode.WINDOW], runs=30, seed=99, show_progress=False)
    
    # 不同种子应该产生不同结果（至少有一个不同）
    assert (results1[0].avg_legit_rate != results2[0].avg_legit_rate or
            results1[0].avg_attack_rate != results2[0].avg_attack_rate)


# ============================================================================
# Test: Defense Effectiveness
# ============================================================================

def test_no_defense_accepts_all_replays():
    """测试无防御接受所有重放"""
    config = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=10,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.NO_DEFENSE], runs=20, show_progress=False)
    
    # 无防御：攻击成功率应该接近1.0（理想信道）
    assert results[0].avg_attack_rate > 0.95


def test_rolling_rejects_old_replays():
    """测试滚动计数器拒绝旧重放"""
    config = SimulationConfig(
        mode=Mode.ROLLING_MAC,
        num_legit=20,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN  # post模式：重放的帧计数器都是旧的
    )
    
    results = run_many_experiments(config, modes=[Mode.ROLLING_MAC], runs=20, show_progress=False)
    
    # 滚动计数器：post模式下攻击应该全部失败
    assert results[0].avg_attack_rate < 0.1


def test_window_handles_reordering():
    """测试滑动窗口处理乱序"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=0,  # 不测试攻击，只测试合法包
        p_loss=0.0,
        p_reorder=0.3,  # 高乱序
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.WINDOW], runs=30, show_progress=False)
    
    # 滑动窗口应该能处理乱序，合法包接受率高
    assert results[0].avg_legit_rate > 0.85


def test_challenge_blocks_replays():
    """测试挑战-响应阻止重放"""
    config = SimulationConfig(
        mode=Mode.CHALLENGE,
        num_legit=10,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.CHALLENGE], runs=20, show_progress=False)
    
    # 挑战-响应：旧nonce应该失效，攻击失败
    assert results[0].avg_attack_rate < 0.1


# ============================================================================
# Test: Parameter Effects
# ============================================================================

def test_packet_loss_reduces_legit_acceptance():
    """测试丢包率降低合法包接受率"""
    # 无丢包
    config_no_loss = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    # 高丢包
    config_high_loss = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.3,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results_no_loss = run_many_experiments(config_no_loss, modes=[Mode.WINDOW], runs=20, show_progress=False)
    results_high_loss = run_many_experiments(config_high_loss, modes=[Mode.WINDOW], runs=20, show_progress=False)
    
    # 高丢包应该降低接受率
    assert results_high_loss[0].avg_legit_rate < results_no_loss[0].avg_legit_rate


def test_window_size_effect():
    """测试窗口大小的影响"""
    # 小窗口
    config_small = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.3,
        attacker_record_loss=0.0,
        window_size=3,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    # 大窗口
    config_large = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.3,
        attacker_record_loss=0.0,
        window_size=10,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results_small = run_many_experiments(config_small, modes=[Mode.WINDOW], runs=30, show_progress=False)
    results_large = run_many_experiments(config_large, modes=[Mode.WINDOW], runs=30, show_progress=False)
    
    # 大窗口应该更好地处理乱序
    assert results_large[0].avg_legit_rate >= results_small[0].avg_legit_rate


def test_attacker_loss_reduces_attack_success():
    """测试攻击者丢包降低攻击成功率"""
    # 攻击者无丢包
    config_no_loss = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=10,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    # 攻击者高丢包
    config_high_loss = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=10,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.5,  # 攻击者记录50%丢失
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results_no_loss = run_many_experiments(config_no_loss, modes=[Mode.NO_DEFENSE], runs=20, show_progress=False)
    results_high_loss = run_many_experiments(config_high_loss, modes=[Mode.NO_DEFENSE], runs=20, show_progress=False)
    
    # 攻击者丢包应该降低攻击成功率
    assert results_high_loss[0].avg_attack_rate <= results_no_loss[0].avg_attack_rate


# ============================================================================
# Test: Attack Modes
# ============================================================================

def test_post_attack_mode():
    """测试post攻击模式"""
    config = SimulationConfig(
        mode=Mode.ROLLING_MAC,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN  # 合法传输后重放
    )
    
    results = run_many_experiments(config, modes=[Mode.ROLLING_MAC], runs=20, show_progress=False)
    
    # post模式下，滚动计数器应该能阻止重放
    assert results[0].avg_attack_rate < 0.1


def test_inline_attack_mode():
    """测试inline攻击模式"""
    config = SimulationConfig(
        mode=Mode.ROLLING_MAC,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.INLINE  # 合法传输中插入重放
    )
    
    results = run_many_experiments(config, modes=[Mode.ROLLING_MAC], runs=20, show_progress=False)
    
    # inline模式更难防御（取决于具体实现）
    assert results is not None


def test_inline_attack_respects_replay_cap():
    """测试inline模式遵守重放次数上限"""
    config = SimulationConfig(
        mode=Mode.ROLLING_MAC,
        num_legit=5,
        num_replay=2,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.INLINE,
        inline_attack_probability=1.0,
        inline_attack_burst=5
    )

    result = simulate_one_run(config)
    assert result.attack_attempts == 2


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_zero_legit_frames():
    """测试零合法帧"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=0,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.WINDOW], runs=10, show_progress=False)
    
    # 没有合法帧时应该正常处理
    assert results is not None


def test_zero_replay_frames():
    """测试零重放帧"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=10,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.WINDOW], runs=10, show_progress=False)
    
    # 没有重放时应该正常处理
    assert results is not None


def test_large_number_of_runs():
    """测试大量运行次数"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=10,
        num_replay=5,
        p_loss=0.1,
        p_reorder=0.1,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    # 运行200次（测试性能和稳定性）
    results = run_many_experiments(config, modes=[Mode.WINDOW], runs=200, show_progress=False)
    
    assert results is not None
    # 大量运行应该使标准差更小（更稳定的估计）
    assert results[0].std_legit_rate < 0.2


def test_extreme_packet_loss():
    """测试极端丢包率"""
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.9,  # 90%丢包
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    results = run_many_experiments(config, modes=[Mode.WINDOW], runs=20, show_progress=False)
    
    # 极端丢包，接受率应该很低
    assert results[0].avg_legit_rate < 0.3


# ============================================================================
# Test: Multiple Modes Comparison
# ============================================================================

def test_run_multiple_modes():
    """测试同时运行多个模式"""
    config = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    modes = [Mode.NO_DEFENSE, Mode.ROLLING_MAC, Mode.WINDOW, Mode.CHALLENGE]
    results = run_many_experiments(config, modes=modes, runs=10, show_progress=False)
    
    # 应该返回4个结果（每个模式一个）
    assert len(results) == 4
    
    # 验证每个结果对应正确的模式
    result_modes = [r.mode for r in results]
    for mode in modes:
        assert mode in result_modes
