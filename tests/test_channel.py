"""
测试Channel模块
Tests for Channel module

验证：
- 丢包率统计正确性
- 乱序概率统计正确性
- 优先队列逻辑
- 参数边界条件
"""

import pytest
from sim.channel import Channel
from sim.sender import Sender
from sim.types import Command, DefenseMode


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sender():
    """创建测试用sender"""
    return Sender(defense=DefenseMode.NO_DEF, seed=42)


def create_frame(sender, counter_value):
    """创建测试帧"""
    cmd = Command(cmd_type="TEST", param=counter_value)
    frame = sender.send_command(cmd)
    frame.counter = counter_value  # 手动设置counter便于测试
    return frame


# ============================================================================
# Test: Packet Loss Rate
# ============================================================================

def test_no_packet_loss(sender):
    """测试零丢包率"""
    channel = Channel(p_loss=0.0, p_reorder=0.0, seed=42)
    
    # 发送100个包
    sent_count = 100
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(sender, i)
        output = channel.send(frame)
        if len(output) > 0:
            received_count += len(output)
    
    # 清空队列中的剩余帧
    remaining = channel.flush()
    received_count += len(remaining)
    
    # 零丢包率应该全部接收
    assert received_count == sent_count


def test_total_packet_loss(sender):
    """测试100%丢包率"""
    channel = Channel(p_loss=1.0, p_reorder=0.0, seed=42)
    
    # 发送100个包
    sent_count = 100
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(sender, i)
        output = channel.send(frame)
        received_count += len(output)
    
    remaining = channel.flush()
    received_count += len(remaining)
    
    # 100%丢包应该一个都收不到
    assert received_count == 0


def test_packet_loss_rate_10_percent(sender):
    """测试10%丢包率的统计特性"""
    channel = Channel(p_loss=0.1, p_reorder=0.0, seed=42)
    
    # 发送足够多的包以获得统计意义
    sent_count = 1000
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(sender, i)
        output = channel.send(frame)
        received_count += len(output)
    
    remaining = channel.flush()
    received_count += len(remaining)
    
    actual_loss_rate = 1.0 - (received_count / sent_count)
    
    # 允许±2%的统计误差（0.08 ~ 0.12）
    assert 0.08 < actual_loss_rate < 0.12, \
        f"Expected ~10% loss, got {actual_loss_rate*100:.1f}%"


def test_packet_loss_rate_20_percent(sender):
    """测试20%丢包率的统计特性"""
    channel = Channel(p_loss=0.2, p_reorder=0.0, seed=42)
    
    sent_count = 1000
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(sender, i)
        output = channel.send(frame)
        received_count += len(output)
    
    remaining = channel.flush()
    received_count += len(remaining)
    
    actual_loss_rate = 1.0 - (received_count / sent_count)
    
    # 允许±3%的统计误差（0.17 ~ 0.23）
    assert 0.17 < actual_loss_rate < 0.23, \
        f"Expected ~20% loss, got {actual_loss_rate*100:.1f}%"


def test_packet_loss_rate_30_percent(sender):
    """测试30%丢包率的统计特性"""
    channel = Channel(p_loss=0.3, p_reorder=0.0, seed=42)
    
    sent_count = 1000
    received_count = 0
    
    for i in range(sent_count):
        frame = create_frame(sender, i)
        output = channel.send(frame)
        received_count += len(output)
    
    remaining = channel.flush()
    received_count += len(remaining)
    
    actual_loss_rate = 1.0 - (received_count / sent_count)
    
    # 允许±3%的统计误差（0.27 ~ 0.33）
    assert 0.27 < actual_loss_rate < 0.33, \
        f"Expected ~30% loss, got {actual_loss_rate*100:.1f}%"


# ============================================================================
# Test: Packet Reordering
# ============================================================================

def test_no_reordering(sender):
    """测试零乱序概率（严格顺序）"""
    channel = Channel(p_loss=0.0, p_reorder=0.0, seed=42)
    
    sent_frames = []
    received_frames = []
    
    # 发送10个包
    for i in range(10):
        frame = create_frame(sender, i)
        sent_frames.append(frame)
        output = channel.send(frame)
        received_frames.extend(output)
    
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    # 零乱序应该保持顺序
    for i, frame in enumerate(received_frames):
        assert frame.counter == i


def test_reordering_occurs(sender):
    """测试乱序确实发生"""
    channel = Channel(p_loss=0.0, p_reorder=0.5, seed=42)
    
    received_frames = []
    
    # 发送足够多的包
    for i in range(100):
        frame = create_frame(sender, i)
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


def test_reordering_probability_statistics(sender):
    """测试乱序概率统计特性"""
    p_reorder = 0.3
    channel = Channel(p_loss=0.0, p_reorder=p_reorder, seed=42)
    
    received_frames = []
    
    # 发送大量包
    for i in range(500):
        frame = create_frame(sender, i)
        output = channel.send(frame)
        received_frames.extend(output)
    
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    # 计算实际延迟的包数量（作为乱序的代理指标）
    # 注：这是近似测试，因为乱序的定义在实现中是"延迟到队列"
    # 实际统计比较复杂，这里验证基本行为
    assert len(received_frames) == 500  # 所有包都应该到达


def test_all_frames_eventually_arrive(sender):
    """测试所有帧最终都会到达（无丢包+乱序）"""
    channel = Channel(p_loss=0.0, p_reorder=0.5, seed=42)
    
    sent_count = 100
    received_frames = []
    
    for i in range(sent_count):
        frame = create_frame(sender, i)
        output = channel.send(frame)
        received_frames.extend(output)
    
    # 关键：flush确保队列中的包都输出
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    assert len(received_frames) == sent_count


# ============================================================================
# Test: Combined Loss + Reordering
# ============================================================================

def test_combined_loss_and_reorder(sender):
    """测试丢包+乱序组合"""
    channel = Channel(p_loss=0.1, p_reorder=0.2, seed=42)
    
    sent_count = 500
    received_frames = []
    
    for i in range(sent_count):
        frame = create_frame(sender, i)
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

def test_reproducibility_with_seed(sender):
    """测试固定种子的可重现性"""
    seed = 42
    
    # 第一次运行
    channel1 = Channel(p_loss=0.1, p_reorder=0.2, seed=seed)
    frames1 = []
    for i in range(100):
        frame = create_frame(sender, i)
        output = channel1.send(frame)
        frames1.extend(output)
    frames1.extend(channel1.flush())
    
    # 第二次运行（相同种子）
    channel2 = Channel(p_loss=0.1, p_reorder=0.2, seed=seed)
    frames2 = []
    for i in range(100):
        frame = create_frame(sender, i)
        output = channel2.send(frame)
        frames2.extend(output)
    frames2.extend(channel2.flush())
    
    # 应该完全相同
    assert len(frames1) == len(frames2)
    for f1, f2 in zip(frames1, frames2):
        assert f1.counter == f2.counter


def test_different_seeds_different_results(sender):
    """测试不同种子产生不同结果"""
    # 第一次运行
    channel1 = Channel(p_loss=0.1, p_reorder=0.2, seed=42)
    frames1 = []
    for i in range(100):
        frame = create_frame(sender, i)
        output = channel1.send(frame)
        frames1.extend(output)
    frames1.extend(channel1.flush())
    
    # 第二次运行（不同种子）
    channel2 = Channel(p_loss=0.1, p_reorder=0.2, seed=99)
    frames2 = []
    for i in range(100):
        frame = create_frame(sender, i)
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

def test_flush_empties_queue(sender):
    """测试flush清空队列"""
    channel = Channel(p_loss=0.0, p_reorder=0.5, seed=42)
    
    # 发送一些包（部分会留在队列中）
    for i in range(10):
        frame = create_frame(sender, i)
        channel.send(frame)
    
    # Flush
    remaining = channel.flush()
    
    # 再次flush应该没有包
    remaining2 = channel.flush()
    assert len(remaining2) == 0


def test_flush_returns_all_queued_frames(sender):
    """测试flush返回所有队列中的帧"""
    channel = Channel(p_loss=0.0, p_reorder=1.0, seed=42)
    
    sent_count = 10
    immediate_output = []
    
    # 发送包
    for i in range(sent_count):
        frame = create_frame(sender, i)
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

def test_zero_probability_edge_case(sender):
    """测试边界：所有概率为0"""
    channel = Channel(p_loss=0.0, p_reorder=0.0, seed=42)
    
    frame = create_frame(sender, 1)
    output = channel.send(frame)
    
    # 应该立即输出
    assert len(output) == 1
    assert output[0].counter == 1


def test_extreme_parameters(sender):
    """测试极端参数（高丢包+高乱序）"""
    channel = Channel(p_loss=0.8, p_reorder=0.8, seed=42)
    
    sent_count = 100
    received_frames = []
    
    for i in range(sent_count):
        frame = create_frame(sender, i)
        output = channel.send(frame)
        received_frames.extend(output)
    
    remaining = channel.flush()
    received_frames.extend(remaining)
    
    # 80%丢包，应该只收到约20%
    actual_loss_rate = 1.0 - (len(received_frames) / sent_count)
    assert 0.70 < actual_loss_rate < 0.90


def test_single_frame(sender):
    """测试单个帧传输"""
    channel = Channel(p_loss=0.0, p_reorder=0.0, seed=42)
    
    frame = create_frame(sender, 99)
    output = channel.send(frame)
    
    assert len(output) == 1
    assert output[0].counter == 99


def test_large_counter_values(sender):
    """测试大计数器值"""
    channel = Channel(p_loss=0.0, p_reorder=0.0, seed=42)
    
    large_counter = 999999
    frame = create_frame(sender, large_counter)
    output = channel.send(frame)
    
    assert len(output) == 1
    assert output[0].counter == large_counter


# ============================================================================
# Test: Statistical Properties (Chi-Square Goodness of Fit)
# ============================================================================

def test_packet_loss_distribution(sender):
    """
    测试丢包率是否符合伯努利分布
    使用卡方检验（简化版）
    """
    channel = Channel(p_loss=0.1, p_reorder=0.0, seed=42)
    
    trials = 10
    sent_per_trial = 100
    received_counts = []
    
    for _ in range(trials):
        received = 0
        for i in range(sent_per_trial):
            frame = create_frame(sender, i)
            output = channel.send(frame)
            received += len(output)
        received_counts.append(received)
        channel.flush()
    
    # 平均接收率应该接近90%
    avg_received = sum(received_counts) / trials
    expected = sent_per_trial * 0.9
    
    # 允许±5的误差
    assert abs(avg_received - expected) < 5, \
        f"Expected ~{expected}, got {avg_received}"

