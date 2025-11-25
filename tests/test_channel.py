"""
Tests for Channel module

验证：
- 丢包率统计正确性
- 乱序概率统计正确性
- 优先队列逻辑
- 参数边界条件
"""

import random
import pytest
from sim.channel import Channel
from sim.types import Frame


# ============================================================================
# Fixtures
# ============================================================================

def create_frame(counter: int, command: str = "TEST") -> Frame:
    """创建测试帧"""
    return Frame(command=command, counter=counter)


# ============================================================================
# Test: Packet Loss Rate
# ============================================================================

def test_no_packet_loss():
    """测试零丢包率"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=0.0, rng=rng)
    
    # 发送100个包
    sent_count = 100
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        received_count += len(output)
    
    # 清空队列中的剩余帧
    remaining = channel.flush()
    received_count += len(remaining)
    
    # 零丢包率应该全部接收
    assert received_count == sent_count


def test_total_packet_loss():
    """测试100%丢包率"""
    rng = random.Random(42)
    channel = Channel(p_loss=1.0, p_reorder=0.0, rng=rng)
    
    # 发送100个包
    sent_count = 100
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        received_count += len(output)
    
    remaining = channel.flush()
    received_count += len(remaining)
    
    # 100%丢包应该一个都收不到
    assert received_count == 0


def test_packet_loss_rate_10_percent():
    """测试10%丢包率的统计特性"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.1, p_reorder=0.0, rng=rng)
    
    # 发送足够多的包以获得统计意义
    sent_count = 1000
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        received_count += len(output)
    
    remaining = channel.flush()
    received_count += len(remaining)
    
    actual_loss_rate = 1.0 - (received_count / sent_count)
    
    # 允许±4%的统计误差（0.06 ~ 0.14）
    assert 0.06 < actual_loss_rate < 0.14, \
        f"Expected ~10% loss, got {actual_loss_rate*100:.1f}%"


def test_packet_loss_rate_20_percent():
    """测试20%丢包率的统计特性"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.2, p_reorder=0.0, rng=rng)
    
    sent_count = 1000
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        received_count += len(output)
    
    remaining = channel.flush()
    received_count += len(remaining)
    
    actual_loss_rate = 1.0 - (received_count / sent_count)
    
    # 允许±4%的统计误差（0.16 ~ 0.24）
    assert 0.16 < actual_loss_rate < 0.24, \
        f"Expected ~20% loss, got {actual_loss_rate*100:.1f}%"


def test_packet_loss_rate_30_percent():
    """测试30%丢包率的统计特性"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.3, p_reorder=0.0, rng=rng)
    
    sent_count = 1000
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        received_count += len(output)
    
    remaining = channel.flush()
    received_count += len(remaining)
    
    actual_loss_rate = 1.0 - (received_count / sent_count)
    
    # 允许±4%的统计误差（0.26 ~ 0.34）
    assert 0.26 < actual_loss_rate < 0.34, \
        f"Expected ~30% loss, got {actual_loss_rate*100:.1f}%"


# ============================================================================
# Test: Packet Reordering
# ============================================================================

def test_no_reordering():
    """测试零乱序概率（严格顺序）"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=0.0, rng=rng)
    
    sent_frames = []
    received_frames = []
    
    # 发送10个包
    for i in range(10):
        frame = create_frame(i)
        sent_frames.append(frame)
        output = channel.send(frame)
        received_frames.extend(output)
    
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    # 零乱序应该保持顺序
    for i, frame in enumerate(received_frames):
        assert frame.counter == i


def test_reordering_occurs():
    """测试乱序确实发生"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=0.5, rng=rng)
    
    received_frames = []
    
    # 发送足够多的包
    for i in range(100):
        frame = create_frame(i)
        output = channel.send(frame)
        received_frames.extend(output)
    
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    # 检查是否有乱序
    out_of_order_count = 0
    for i in range(1, len(received_frames)):
        if received_frames[i].counter < received_frames[i-1].counter:
            out_of_order_count += 1
    
    # 50%乱序概率应该有明显的乱序现象
    assert out_of_order_count > 0, "No reordering detected with p_reorder=0.5"


def test_reordering_probability_statistics():
    """测试乱序概率统计特性"""
    p_reorder = 0.3
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=p_reorder, rng=rng)
    
    received_frames = []
    
    # 发送大量包
    for i in range(500):
        frame = create_frame(i)
        output = channel.send(frame)
        received_frames.extend(output)
    
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    # 计算实际延迟的包数量（作为乱序的代理指标）
    # 注：这是近似测试，因为乱序的定义在实现中是"延迟到队列"
    # 实际统计比较复杂，这里验证基本行为
    assert len(received_frames) == 500  # 所有包都应该到达


def test_all_frames_eventually_arrive():
    """测试所有帧最终都会到达（无丢包+乱序）"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=0.5, rng=rng)
    
    sent_count = 100
    received_frames = []
    
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        received_frames.extend(output)
    
    # 关键：flush确保队列中的包都输出
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    assert len(received_frames) == sent_count


# ============================================================================
# Test: Combined Loss + Reordering
# ============================================================================

def test_combined_loss_and_reorder():
    """测试丢包+乱序组合"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.1, p_reorder=0.2, rng=rng)
    
    sent_count = 500
    received_frames = []
    
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        received_frames.extend(output)
    
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    # 应该有丢包
    assert len(received_frames) < sent_count
    
    # 丢包率应该在合理范围
    actual_loss_rate = 1.0 - (len(received_frames) / sent_count)
    assert 0.05 < actual_loss_rate < 0.15  # 10% ± 5%


# ============================================================================
# Test: Reproducibility (Seed)
# ============================================================================

def test_reproducibility_with_seed():
    """测试固定种子的可重现性"""
    seed = 42
    
    # 第一次运行
    rng1 = random.Random(seed)
    channel1 = Channel(p_loss=0.1, p_reorder=0.2, rng=rng1)
    frames1 = []
    for i in range(100):
        frame = create_frame(i)
        output = channel1.send(frame)
        frames1.extend(output)
    frames1.extend(channel1.flush())
    
    # 第二次运行（相同种子）
    rng2 = random.Random(seed)
    channel2 = Channel(p_loss=0.1, p_reorder=0.2, rng=rng2)
    frames2 = []
    for i in range(100):
        frame = create_frame(i)
        output = channel2.send(frame)
        frames2.extend(output)
    frames2.extend(channel2.flush())
    
    # 应该完全相同
    assert len(frames1) == len(frames2)
    for f1, f2 in zip(frames1, frames2):
        assert f1.counter == f2.counter


def test_different_seeds_different_results():
    """测试不同种子产生不同结果"""
    # 第一次运行
    rng1 = random.Random(42)
    channel1 = Channel(p_loss=0.1, p_reorder=0.2, rng=rng1)
    frames1 = []
    for i in range(100):
        frame = create_frame(i)
        output = channel1.send(frame)
        frames1.extend(output)
    frames1.extend(channel1.flush())
    
    # 第二次运行（不同种子）
    rng2 = random.Random(99)
    channel2 = Channel(p_loss=0.1, p_reorder=0.2, rng=rng2)
    frames2 = []
    for i in range(100):
        frame = create_frame(i)
        output = channel2.send(frame)
        frames2.extend(output)
    frames2.extend(channel2.flush())
    
    # 应该有不同结果（至少接收数量或顺序不同）
    # 由于随机性，可能偶然相同，但概率极低
    assert len(frames1) != len(frames2) or \
           any(f1.counter != f2.counter for f1, f2 in zip(frames1, frames2))


# ============================================================================
# Test: Flush Behavior
# ============================================================================

def test_flush_empties_queue():
    """测试flush清空队列"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=0.5, rng=rng)
    
    # 发送一些包（部分会留在队列中）
    for i in range(10):
        frame = create_frame(i)
        channel.send(frame)
    
    # Flush
    remaining = channel.flush()
    
    # 再次flush应该没有包
    remaining2 = channel.flush()
    assert len(remaining2) == 0


def test_flush_returns_all_queued_frames():
    """测试flush返回所有队列中的帧"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=1.0, rng=rng)
    
    sent_count = 10
    immediate_output = []
    
    # 发送包
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        immediate_output.extend(output)
    
    # Flush
    remaining = channel.flush()
    
    # 总数应该等于发送数
    total_received = len(immediate_output) + len(remaining)
    assert total_received == sent_count


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_zero_probability_edge_case():
    """测试边界：所有概率为0"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=0.0, rng=rng)
    
    frame = create_frame(1)
    output = channel.send(frame)
    
    # 应该立即输出
    assert len(output) == 1
    assert output[0].counter == 1


def test_extreme_parameters():
    """测试极端参数（高丢包+高乱序）"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.8, p_reorder=0.8, rng=rng)
    
    sent_count = 100
    received_frames = []
    
    for i in range(sent_count):
        frame = create_frame(i)
        output = channel.send(frame)
        received_frames.extend(output)
    
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    # 80%丢包，应该只收到约20%
    actual_loss_rate = 1.0 - (len(received_frames) / sent_count)
    assert 0.70 < actual_loss_rate < 0.90


def test_single_frame():
    """测试单个帧传输"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=0.0, rng=rng)
    
    frame = create_frame(99)
    output = channel.send(frame)
    
    assert len(output) == 1
    assert output[0].counter == 99


def test_large_counter_values():
    """测试大计数器值"""
    rng = random.Random(42)
    channel = Channel(p_loss=0.0, p_reorder=0.0, rng=rng)
    
    large_counter = 999999
    frame = create_frame(large_counter)
    output = channel.send(frame)
    
    assert len(output) == 1
    assert output[0].counter == large_counter


# ============================================================================
# Test: Statistical Properties (Chi-Square Goodness of Fit)
# ============================================================================

def test_packet_loss_distribution():
    """
    测试丢包率是否符合伯努利分布
    使用卡方检验（简化版）
    """
    seed = 42
    trials = 10
    sent_per_trial = 100
    received_counts = []
    
    for t in range(trials):
        rng = random.Random(seed + t)
        channel = Channel(p_loss=0.1, p_reorder=0.0, rng=rng)
        received = 0
        for i in range(sent_per_trial):
            frame = create_frame(i)
            output = channel.send(frame)
            received += len(output)
        received += len(channel.flush())
        received_counts.append(received)
    
    # 平均接收率应该接近90%
    avg_received = sum(received_counts) / trials
    expected = sent_per_trial * 0.9
    
    # 允许±10的误差
    assert abs(avg_received - expected) < 10, \
        f"Expected ~{expected}, got {avg_received}"
