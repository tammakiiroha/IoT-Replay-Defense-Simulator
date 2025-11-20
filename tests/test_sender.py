"""
测试Sender模块
Tests for Sender module

验证：
- MAC计算正确性（对照RFC 2104）
- 帧生成格式
- 计数器递增逻辑
"""

import pytest
from sim.sender import Sender
from sim.types import Command, DefenseMode
from sim.security import compute_mac, verify_mac


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sender_no_def():
    """无防御的发送方"""
    return Sender(defense=DefenseMode.NO_DEF, seed=42)


@pytest.fixture
def sender_rolling():
    """滚动计数器发送方"""
    return Sender(defense=DefenseMode.ROLLING_MAC, seed=42)


@pytest.fixture
def sender_window():
    """滑动窗口发送方"""
    return Sender(defense=DefenseMode.WINDOW, seed=42)


@pytest.fixture
def sender_challenge():
    """挑战-响应发送方"""
    return Sender(defense=DefenseMode.CHALLENGE, seed=42)


# ============================================================================
# Test: Frame Generation
# ============================================================================

def test_frame_generation_no_defense(sender_no_def):
    """测试无防御模式下的帧生成"""
    cmd = Command(cmd_type="LOCK", param=0)
    frame = sender_no_def.send_command(cmd)
    
    assert frame is not None
    assert frame.command == cmd
    assert frame.counter == 1  # 第一个帧
    assert frame.mac is None  # 无防御模式没有MAC
    assert frame.nonce is None


def test_frame_generation_rolling(sender_rolling):
    """测试滚动计数器模式下的帧生成"""
    cmd = Command(cmd_type="UNLOCK", param=0)
    frame = sender_rolling.send_command(cmd)
    
    assert frame is not None
    assert frame.command == cmd
    assert frame.counter == 1
    assert frame.mac is not None  # 必须有MAC
    assert len(frame.mac) > 0
    assert frame.nonce is None  # 滚动计数器不用nonce


def test_frame_generation_window(sender_window):
    """测试滑动窗口模式下的帧生成"""
    cmd = Command(cmd_type="START", param=0)
    frame = sender_window.send_command(cmd)
    
    assert frame is not None
    assert frame.command == cmd
    assert frame.counter == 1
    assert frame.mac is not None
    assert frame.nonce is None


def test_frame_generation_challenge(sender_challenge):
    """测试挑战-响应模式下的帧生成"""
    cmd = Command(cmd_type="STOP", param=0)
    
    # 挑战-响应需要先请求challenge
    nonce = sender_challenge.request_challenge()
    assert nonce is not None
    assert len(nonce) > 0
    
    frame = sender_challenge.send_command(cmd)
    assert frame is not None
    assert frame.command == cmd
    assert frame.counter == 1
    assert frame.mac is not None
    assert frame.nonce == nonce  # 必须包含nonce


# ============================================================================
# Test: Counter Increment
# ============================================================================

def test_counter_increment(sender_rolling):
    """测试计数器递增逻辑"""
    cmd = Command(cmd_type="LOCK", param=0)
    
    frame1 = sender_rolling.send_command(cmd)
    assert frame1.counter == 1
    
    frame2 = sender_rolling.send_command(cmd)
    assert frame2.counter == 2
    
    frame3 = sender_rolling.send_command(cmd)
    assert frame3.counter == 3
    
    # 计数器必须严格递增
    assert frame2.counter == frame1.counter + 1
    assert frame3.counter == frame2.counter + 1


def test_counter_independence_per_sender():
    """测试不同sender的计数器独立性"""
    sender1 = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    sender2 = Sender(defense=DefenseMode.ROLLING_MAC, seed=43)
    
    cmd = Command(cmd_type="LOCK", param=0)
    
    frame1 = sender1.send_command(cmd)
    frame2 = sender2.send_command(cmd)
    
    # 两个sender的计数器应该都从1开始
    assert frame1.counter == 1
    assert frame2.counter == 1


# ============================================================================
# Test: MAC Correctness (RFC 2104)
# ============================================================================

def test_mac_correctness_basic(sender_rolling):
    """测试MAC计算正确性（基本验证）"""
    cmd = Command(cmd_type="LOCK", param=0)
    frame = sender_rolling.send_command(cmd)
    
    # 重新计算MAC
    data = f"{frame.command.cmd_type}:{frame.command.param}:{frame.counter}"
    expected_mac = compute_mac(data, sender_rolling.key, sender_rolling.mac_length)
    
    assert frame.mac == expected_mac


def test_mac_correctness_multiple_frames(sender_rolling):
    """测试多个帧的MAC计算正确性"""
    commands = [
        Command(cmd_type="LOCK", param=0),
        Command(cmd_type="UNLOCK", param=0),
        Command(cmd_type="START", param=100),
        Command(cmd_type="STOP", param=0),
    ]
    
    for cmd in commands:
        frame = sender_rolling.send_command(cmd)
        
        # 验证MAC
        data = f"{frame.command.cmd_type}:{frame.command.param}:{frame.counter}"
        expected_mac = compute_mac(data, sender_rolling.key, sender_rolling.mac_length)
        
        assert frame.mac == expected_mac


def test_mac_verification(sender_rolling):
    """测试MAC验证功能"""
    cmd = Command(cmd_type="LOCK", param=0)
    frame = sender_rolling.send_command(cmd)
    
    # 正确的MAC应该验证通过
    data = f"{frame.command.cmd_type}:{frame.command.param}:{frame.counter}"
    assert verify_mac(data, frame.mac, sender_rolling.key)
    
    # 错误的MAC应该验证失败
    wrong_mac = "0" * len(frame.mac)
    assert not verify_mac(data, wrong_mac, sender_rolling.key)


def test_mac_uniqueness():
    """测试不同数据生成不同MAC"""
    sender = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    
    cmd1 = Command(cmd_type="LOCK", param=0)
    cmd2 = Command(cmd_type="UNLOCK", param=0)
    
    frame1 = sender.send_command(cmd1)
    frame2 = sender.send_command(cmd2)
    
    # 不同命令应该生成不同MAC
    assert frame1.mac != frame2.mac


def test_mac_deterministic():
    """测试相同输入生成相同MAC（确定性）"""
    sender1 = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    sender2 = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    
    cmd = Command(cmd_type="LOCK", param=0)
    
    frame1 = sender1.send_command(cmd)
    frame2 = sender2.send_command(cmd)
    
    # 相同种子、相同命令应该生成相同MAC
    assert frame1.mac == frame2.mac


# ============================================================================
# Test: Challenge-Response Nonce
# ============================================================================

def test_challenge_nonce_generation(sender_challenge):
    """测试挑战nonce生成"""
    nonce1 = sender_challenge.request_challenge()
    nonce2 = sender_challenge.request_challenge()
    
    # Nonce必须存在
    assert nonce1 is not None
    assert nonce2 is not None
    
    # Nonce必须不同（防止重放）
    assert nonce1 != nonce2
    
    # Nonce长度合理
    assert len(nonce1) >= 16  # 至少128位


def test_challenge_nonce_in_frame(sender_challenge):
    """测试nonce正确包含在帧中"""
    nonce = sender_challenge.request_challenge()
    cmd = Command(cmd_type="LOCK", param=0)
    frame = sender_challenge.send_command(cmd)
    
    assert frame.nonce == nonce


def test_challenge_without_request():
    """测试未请求challenge时发送命令"""
    sender = Sender(defense=DefenseMode.CHALLENGE, seed=42)
    cmd = Command(cmd_type="LOCK", param=0)
    
    # 未请求challenge时，应该自动请求
    frame = sender.send_command(cmd)
    assert frame.nonce is not None


# ============================================================================
# Test: Reproducibility (Seed)
# ============================================================================

def test_reproducibility_with_seed():
    """测试固定种子的可重现性"""
    cmd = Command(cmd_type="LOCK", param=0)
    
    # 相同种子应该生成相同序列
    sender1 = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    sender2 = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    
    frames1 = [sender1.send_command(cmd) for _ in range(5)]
    frames2 = [sender2.send_command(cmd) for _ in range(5)]
    
    for f1, f2 in zip(frames1, frames2):
        assert f1.counter == f2.counter
        assert f1.mac == f2.mac


def test_different_seeds_different_results():
    """测试不同种子生成不同结果"""
    cmd = Command(cmd_type="LOCK", param=0)
    
    sender1 = Sender(defense=DefenseMode.CHALLENGE, seed=42)
    sender2 = Sender(defense=DefenseMode.CHALLENGE, seed=99)
    
    nonce1 = sender1.request_challenge()
    nonce2 = sender2.request_challenge()
    
    # 不同种子应该生成不同nonce
    assert nonce1 != nonce2


# ============================================================================
# Test: Command Parameters
# ============================================================================

def test_command_with_parameters(sender_rolling):
    """测试带参数的命令"""
    cmd = Command(cmd_type="SET_TEMP", param=25)
    frame = sender_rolling.send_command(cmd)
    
    assert frame.command.cmd_type == "SET_TEMP"
    assert frame.command.param == 25
    
    # MAC应该包含参数
    data = f"{frame.command.cmd_type}:{frame.command.param}:{frame.counter}"
    assert verify_mac(data, frame.mac, sender_rolling.key)


def test_different_parameters_different_mac(sender_rolling):
    """测试不同参数生成不同MAC"""
    cmd1 = Command(cmd_type="SET_TEMP", param=20)
    cmd2 = Command(cmd_type="SET_TEMP", param=25)
    
    frame1 = sender_rolling.send_command(cmd1)
    frame2 = sender_rolling.send_command(cmd2)
    
    # 相同命令但不同参数应该生成不同MAC
    assert frame1.mac != frame2.mac


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_high_counter_values():
    """测试大计数器值"""
    sender = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    cmd = Command(cmd_type="LOCK", param=0)
    
    # 发送大量命令，测试计数器是否正确递增
    for i in range(1, 101):
        frame = sender.send_command(cmd)
        assert frame.counter == i


def test_empty_command_type():
    """测试空命令类型（边界条件）"""
    sender = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    cmd = Command(cmd_type="", param=0)
    
    frame = sender.send_command(cmd)
    assert frame is not None
    assert frame.command.cmd_type == ""
    # MAC应该仍然能正确计算
    assert frame.mac is not None


# ============================================================================
# Test: Defense Mode Comparison
# ============================================================================

def test_all_defense_modes_generate_frames():
    """测试所有防御模式都能生成帧"""
    cmd = Command(cmd_type="LOCK", param=0)
    
    modes = [
        DefenseMode.NO_DEF,
        DefenseMode.ROLLING_MAC,
        DefenseMode.WINDOW,
        DefenseMode.CHALLENGE,
    ]
    
    for mode in modes:
        sender = Sender(defense=mode, seed=42)
        if mode == DefenseMode.CHALLENGE:
            sender.request_challenge()
        
        frame = sender.send_command(cmd)
        assert frame is not None
        assert frame.command == cmd
        assert frame.counter >= 1

