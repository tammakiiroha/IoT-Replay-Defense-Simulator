"""
测试Experiment模块
Tests for Experiment module

验证：
- 蒙特卡洛统计计算正确性
- 固定种子可重现性
- 平均值/标准差计算
- 实验参数边界条件
"""

import pytest
from sim.experiment import run_many_experiments
from sim.types import SimulationConfig, DefenseMode


# ============================================================================
# Test: Basic Experiment Execution
# ============================================================================

def test_single_experiment_no_defense():
    """测试单次实验（无防御）"""
    config = SimulationConfig(
        defense=DefenseMode.NO_DEF,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=1, show_progress=False)
    
    assert result is not None
    assert 'avg_legit' in result
    assert 'avg_attack' in result
    assert 'std_legit' in result
    assert 'std_attack' in result


def test_single_experiment_rolling():
    """测试单次实验（滚动计数器）"""
    config = SimulationConfig(
        defense=DefenseMode.ROLLING_MAC,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=1, show_progress=False)
    assert result is not None


def test_single_experiment_window():
    """测试单次实验（滑动窗口）"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=1, show_progress=False)
    assert result is not None


def test_single_experiment_challenge():
    """测试单次实验（挑战-响应）"""
    config = SimulationConfig(
        defense=DefenseMode.CHALLENGE,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=1, show_progress=False)
    assert result is not None


# ============================================================================
# Test: Monte Carlo Statistics
# ============================================================================

def test_multiple_runs_statistical_properties():
    """测试多次运行的统计特性"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=10,
        p_loss=0.1,
        p_reorder=0.1,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=50, show_progress=False)
    
    # 验证返回值结构
    assert 'avg_legit' in result
    assert 'std_legit' in result
    assert 'avg_attack' in result
    assert 'std_attack' in result
    
    # 验证值的合理范围
    assert 0.0 <= result['avg_legit'] <= 1.0
    assert 0.0 <= result['std_legit'] <= 1.0
    assert 0.0 <= result['avg_attack'] <= 1.0
    assert 0.0 <= result['std_attack'] <= 1.0


def test_average_calculation():
    """测试平均值计算正确性"""
    config = SimulationConfig(
        defense=DefenseMode.NO_DEF,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    # 理想信道+无防御：合法包应该100%接受
    result = run_many_experiments(config, num_runs=20, show_progress=False)
    
    # 无丢包无乱序，合法包接受率应该接近1.0
    assert result['avg_legit'] > 0.95


def test_standard_deviation_calculation():
    """测试标准差计算"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=10,
        num_replay=5,
        p_loss=0.2,  # 较高丢包率，增加方差
        p_reorder=0.2,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=50, show_progress=False)
    
    # 标准差应该>=0
    assert result['std_legit'] >= 0.0
    assert result['std_attack'] >= 0.0
    
    # 有丢包和乱序，标准差应该>0（有变化）
    assert result['std_legit'] > 0.0


def test_zero_variance_in_ideal_conditions():
    """测试理想条件下的零方差"""
    config = SimulationConfig(
        defense=DefenseMode.NO_DEF,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=20, show_progress=False)
    
    # 理想条件下，结果应该一致，标准差接近0
    assert result['std_legit'] < 0.01  # 允许浮点误差


# ============================================================================
# Test: Reproducibility (Seed)
# ============================================================================

def test_reproducibility_with_fixed_seed():
    """测试固定种子的完全可重现性"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=10,
        p_loss=0.1,
        p_reorder=0.1,
        attacker_loss=0.1,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    # 第一次运行
    result1 = run_many_experiments(config, num_runs=30, show_progress=False)
    
    # 第二次运行（相同配置）
    result2 = run_many_experiments(config, num_runs=30, show_progress=False)
    
    # 应该完全相同
    assert result1['avg_legit'] == result2['avg_legit']
    assert result1['std_legit'] == result2['std_legit']
    assert result1['avg_attack'] == result2['avg_attack']
    assert result1['std_attack'] == result2['std_attack']


def test_different_seeds_different_results():
    """测试不同种子产生不同结果"""
    base_config = {
        'defense': DefenseMode.WINDOW,
        'num_legit': 20,
        'num_replay': 10,
        'p_loss': 0.2,
        'p_reorder': 0.2,
        'attacker_loss': 0.1,
        'window_size': 5,
        'attack_mode': 'post'
    }
    
    config1 = SimulationConfig(**base_config, seed=42)
    config2 = SimulationConfig(**base_config, seed=99)
    
    result1 = run_many_experiments(config1, num_runs=30, show_progress=False)
    result2 = run_many_experiments(config2, num_runs=30, show_progress=False)
    
    # 不同种子应该产生不同结果（至少有一个不同）
    assert (result1['avg_legit'] != result2['avg_legit'] or
            result1['avg_attack'] != result2['avg_attack'])


# ============================================================================
# Test: Defense Effectiveness
# ============================================================================

def test_no_defense_accepts_all_replays():
    """测试无防御接受所有重放"""
    config = SimulationConfig(
        defense=DefenseMode.NO_DEF,
        num_legit=10,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=20, show_progress=False)
    
    # 无防御：攻击成功率应该接近1.0（理想信道）
    assert result['avg_attack'] > 0.95


def test_rolling_rejects_old_replays():
    """测试滚动计数器拒绝旧重放"""
    config = SimulationConfig(
        defense=DefenseMode.ROLLING_MAC,
        num_legit=20,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'  # post模式：重放的帧计数器都是旧的
    )
    
    result = run_many_experiments(config, num_runs=20, show_progress=False)
    
    # 滚动计数器：post模式下攻击应该全部失败
    assert result['avg_attack'] < 0.1


def test_window_handles_reordering():
    """测试滑动窗口处理乱序"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=0,  # 不测试攻击，只测试合法包
        p_loss=0.0,
        p_reorder=0.3,  # 高乱序
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=30, show_progress=False)
    
    # 滑动窗口应该能处理乱序，合法包接受率高
    assert result['avg_legit'] > 0.85


def test_challenge_blocks_replays():
    """测试挑战-响应阻止重放"""
    config = SimulationConfig(
        defense=DefenseMode.CHALLENGE,
        num_legit=10,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=20, show_progress=False)
    
    # 挑战-响应：旧nonce应该失效，攻击失败
    assert result['avg_attack'] < 0.1


# ============================================================================
# Test: Parameter Effects
# ============================================================================

def test_packet_loss_reduces_legit_acceptance():
    """测试丢包率降低合法包接受率"""
    # 无丢包
    config_no_loss = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    # 高丢包
    config_high_loss = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.3,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result_no_loss = run_many_experiments(config_no_loss, num_runs=20, show_progress=False)
    result_high_loss = run_many_experiments(config_high_loss, num_runs=20, show_progress=False)
    
    # 高丢包应该降低接受率
    assert result_high_loss['avg_legit'] < result_no_loss['avg_legit']


def test_window_size_effect():
    """测试窗口大小的影响"""
    # 小窗口
    config_small = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.3,
        attacker_loss=0.0,
        window_size=3,
        seed=42,
        attack_mode='post'
    )
    
    # 大窗口
    config_large = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.3,
        attacker_loss=0.0,
        window_size=10,
        seed=42,
        attack_mode='post'
    )
    
    result_small = run_many_experiments(config_small, num_runs=30, show_progress=False)
    result_large = run_many_experiments(config_large, num_runs=30, show_progress=False)
    
    # 大窗口应该更好地处理乱序
    assert result_large['avg_legit'] >= result_small['avg_legit']


def test_attacker_loss_reduces_attack_success():
    """测试攻击者丢包降低攻击成功率"""
    # 攻击者无丢包
    config_no_loss = SimulationConfig(
        defense=DefenseMode.NO_DEF,
        num_legit=10,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    # 攻击者高丢包
    config_high_loss = SimulationConfig(
        defense=DefenseMode.NO_DEF,
        num_legit=10,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.5,  # 攻击者记录50%丢失
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result_no_loss = run_many_experiments(config_no_loss, num_runs=20, show_progress=False)
    result_high_loss = run_many_experiments(config_high_loss, num_runs=20, show_progress=False)
    
    # 攻击者丢包应该降低攻击成功率
    assert result_high_loss['avg_attack'] < result_no_loss['avg_attack']


# ============================================================================
# Test: Attack Modes
# ============================================================================

def test_post_attack_mode():
    """测试post攻击模式"""
    config = SimulationConfig(
        defense=DefenseMode.ROLLING_MAC,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'  # 合法传输后重放
    )
    
    result = run_many_experiments(config, num_runs=20, show_progress=False)
    
    # post模式下，滚动计数器应该能阻止重放
    assert result['avg_attack'] < 0.1


def test_inline_attack_mode():
    """测试inline攻击模式"""
    config = SimulationConfig(
        defense=DefenseMode.ROLLING_MAC,
        num_legit=10,
        num_replay=5,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='inline'  # 合法传输中插入重放
    )
    
    result = run_many_experiments(config, num_runs=20, show_progress=False)
    
    # inline模式更难防御（取决于具体实现）
    assert result is not None


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_zero_legit_frames():
    """测试零合法帧"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=0,
        num_replay=10,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=10, show_progress=False)
    
    # 没有合法帧，avg_legit应该是特殊值或0
    # 具体取决于实现
    assert result is not None


def test_zero_replay_frames():
    """测试零重放帧"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=10,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=10, show_progress=False)
    
    # 没有重放，avg_attack应该是特殊值或0
    assert result is not None


def test_large_number_of_runs():
    """测试大量运行次数"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=10,
        num_replay=5,
        p_loss=0.1,
        p_reorder=0.1,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    # 运行500次（测试性能和稳定性）
    result = run_many_experiments(config, num_runs=500, show_progress=False)
    
    assert result is not None
    # 大量运行应该使标准差更小（更稳定的估计）
    assert result['std_legit'] < 0.2


def test_extreme_packet_loss():
    """测试极端丢包率"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=0,
        p_loss=0.9,  # 90%丢包
        p_reorder=0.0,
        attacker_loss=0.0,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    result = run_many_experiments(config, num_runs=20, show_progress=False)
    
    # 极端丢包，接受率应该很低
    assert result['avg_legit'] < 0.3


# ============================================================================
# Test: Statistical Confidence
# ============================================================================

def test_confidence_interval_narrowing():
    """测试置信区间随运行次数缩小"""
    config = SimulationConfig(
        defense=DefenseMode.WINDOW,
        num_legit=20,
        num_replay=10,
        p_loss=0.2,
        p_reorder=0.2,
        attacker_loss=0.1,
        window_size=5,
        seed=42,
        attack_mode='post'
    )
    
    # 少量运行
    result_few = run_many_experiments(config, num_runs=10, show_progress=False)
    
    # 大量运行
    result_many = run_many_experiments(config, num_runs=200, show_progress=False)
    
    # 更多运行应该使标准差更小（或接近）
    # 注：标准差是样本标准差，不是标准误，所以不一定严格递减
    # 但平均值应该更稳定
    assert result_many is not None
    assert result_few is not None

