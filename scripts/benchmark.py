"""
性能基准测试脚本
Performance Benchmark Script

用途：
- 测量不同实验配置的运行时间
- 生成性能报告
- 验证蒙特卡洛实验的统计收敛性
"""

import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.experiment import run_many_experiments
from sim.types import SimulationConfig, Mode, AttackMode


def benchmark_single_run():
    """基准测试：单次实验运行"""
    print("\n" + "="*80)
    print("📊 Benchmark 1: Single Run Performance")
    print("="*80 + "\n")
    
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=100,
        p_loss=0.1,
        p_reorder=0.1,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    modes = [Mode.NO_DEFENSE, Mode.ROLLING_MAC, Mode.WINDOW, Mode.CHALLENGE]
    
    print("Running 1 trial for each mode...")
    start = time.time()
    results = run_many_experiments(config, modes, runs=1, seed=42, show_progress=False)
    elapsed = time.time() - start
    
    print(f"\n✓ Completed in {elapsed:.3f} seconds")
    print(f"  Average per mode: {elapsed/len(modes):.3f} seconds")
    

def benchmark_monte_carlo_scaling():
    """基准测试：蒙特卡洛实验的规模扩展性"""
    print("\n" + "="*80)
    print("📊 Benchmark 2: Monte Carlo Scaling")
    print("="*80 + "\n")
    
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=100,
        p_loss=0.1,
        p_reorder=0.1,
        attacker_record_loss=0.0,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    modes = [Mode.WINDOW]
    run_counts = [10, 50, 100, 200, 500]
    
    print(f"{'Runs':<10} {'Time (s)':<12} {'Time/Run (ms)':<15} {'Throughput (runs/s)'}")
    print("-" * 60)
    
    for runs in run_counts:
        start = time.time()
        results = run_many_experiments(config, modes, runs=runs, seed=42, show_progress=False)
        elapsed = time.time() - start
        
        time_per_run = elapsed / runs * 1000  # ms
        throughput = runs / elapsed
        
        print(f"{runs:<10} {elapsed:<12.3f} {time_per_run:<15.2f} {throughput:.1f}")
    
    print("\n✓ Scaling test completed")


def benchmark_parameter_effects():
    """基准测试：不同参数对性能的影响"""
    print("\n" + "="*80)
    print("📊 Benchmark 3: Parameter Effects on Performance")
    print("="*80 + "\n")
    
    base_config = {
        'mode': Mode.WINDOW,
        'num_legit': 20,
        'num_replay': 100,
        'p_loss': 0.1,
        'p_reorder': 0.1,
        'attacker_record_loss': 0.0,
        'window_size': 5,
        'rng_seed': 42,
        'attack_mode': AttackMode.POST_RUN
    }
    
    modes = [Mode.WINDOW]
    runs = 100
    
    # Test 1: Varying num_legit
    print("\n--- Effect of num_legit ---")
    print(f"{'num_legit':<12} {'Time (s)':<12} {'Time/Run (ms)'}")
    print("-" * 40)
    
    for num_legit in [10, 20, 50, 100]:
        config = SimulationConfig(**{**base_config, 'num_legit': num_legit})
        start = time.time()
        results = run_many_experiments(config, modes, runs=runs, seed=42, show_progress=False)
        elapsed = time.time() - start
        time_per_run = elapsed / runs * 1000
        print(f"{num_legit:<12} {elapsed:<12.3f} {time_per_run:.2f}")
    
    # Test 2: Varying num_replay
    print("\n--- Effect of num_replay ---")
    print(f"{'num_replay':<12} {'Time (s)':<12} {'Time/Run (ms)'}")
    print("-" * 40)
    
    for num_replay in [10, 50, 100, 200]:
        config = SimulationConfig(**{**base_config, 'num_replay': num_replay})
        start = time.time()
        results = run_many_experiments(config, modes, runs=runs, seed=42, show_progress=False)
        elapsed = time.time() - start
        time_per_run = elapsed / runs * 1000
        print(f"{num_replay:<12} {elapsed:<12.3f} {time_per_run:.2f}")
    
    # Test 3: Varying defense mode
    print("\n--- Effect of Defense Mode ---")
    print(f"{'Mode':<15} {'Time (s)':<12} {'Time/Run (ms)'}")
    print("-" * 40)
    
    for mode in [Mode.NO_DEFENSE, Mode.ROLLING_MAC, Mode.WINDOW, Mode.CHALLENGE]:
        config = SimulationConfig(**{**base_config, 'mode': mode})
        start = time.time()
        results = run_many_experiments(config, [mode], runs=runs, seed=42, show_progress=False)
        elapsed = time.time() - start
        time_per_run = elapsed / runs * 1000
        print(f"{mode.value:<15} {elapsed:<12.3f} {time_per_run:.2f}")
    
    print("\n✓ Parameter effects test completed")


def benchmark_statistical_convergence():
    """基准测试：验证统计收敛性"""
    print("\n" + "="*80)
    print("📊 Benchmark 4: Statistical Convergence")
    print("="*80 + "\n")
    
    config = SimulationConfig(
        mode=Mode.WINDOW,
        num_legit=20,
        num_replay=100,
        p_loss=0.2,  # Higher variance
        p_reorder=0.2,
        attacker_record_loss=0.1,
        window_size=5,
        rng_seed=42,
        attack_mode=AttackMode.POST_RUN
    )
    
    modes = [Mode.WINDOW]
    run_counts = [10, 20, 50, 100, 200, 500]
    
    print(f"{'Runs':<10} {'Avg Legit':<12} {'Std Legit':<12} {'Avg Attack':<12} {'Std Attack'}")
    print("-" * 60)
    
    for runs in run_counts:
        results = run_many_experiments(config, modes, runs=runs, seed=42, show_progress=False)
        stats = results[0]
        
        print(f"{runs:<10} "
              f"{stats.avg_legit_rate*100:>10.2f}% "
              f"{stats.std_legit_rate*100:>10.2f}% "
              f"{stats.avg_attack_rate*100:>10.2f}% "
              f"{stats.std_attack_rate*100:>10.2f}%")
    
    print("\n✓ Convergence test completed")
    print("   Note: As runs increase, std should stabilize (not necessarily decrease)")


def generate_performance_report():
    """生成完整的性能报告"""
    print("\n" + "="*80)
    print("🎯 GENERATING COMPLETE PERFORMANCE REPORT")
    print("="*80)
    
    overall_start = time.time()
    
    benchmark_single_run()
    benchmark_monte_carlo_scaling()
    benchmark_parameter_effects()
    benchmark_statistical_convergence()
    
    overall_elapsed = time.time() - overall_start
    
    print("\n" + "="*80)
    print("✅ BENCHMARK SUITE COMPLETED")
    print("="*80)
    print(f"\nTotal benchmark time: {overall_elapsed:.2f} seconds")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════╗
║          重放攻击仿真 - 性能基准测试                              ║
║    Replay Attack Simulation - Performance Benchmark            ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    generate_performance_report()

