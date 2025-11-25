"""
Tests for Sender module

验证：
- MAC计算正确性（对照RFC 2104）
- 帧生成格式
- 计数器递增逻辑
"""

import pytest
from sim.sender import Sender
from sim.types import Mode, Frame
from sim.security import compute_mac, constant_time_compare


# ============================================================================
# Fixtures
# ============================================================================

SHARED_KEY = "test_key"
MAC_LENGTH = 8


@pytest.fixture
def sender_no_def():
    """无防御的发送方"""
    return Sender(mode=Mode.NO_DEFENSE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)


@pytest.fixture
def sender_rolling():
    """滚动计数器发送方"""
    return Sender(mode=Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)


@pytest.fixture
def sender_window():
    """滑动窗口发送方"""
    return Sender(mode=Mode.WINDOW, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)


@pytest.fixture
def sender_challenge():
    """挑战-响应发送方"""
    return Sender(mode=Mode.CHALLENGE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)


# ============================================================================
# Test: Frame Generation
# ============================================================================

def test_frame_generation_no_defense(sender_no_def):
    """测试无防御模式下的帧生成"""
    frame = sender_no_def.next_frame("LOCK")
    
    assert frame is not None
    assert frame.command == "LOCK"
    assert frame.counter is None  # 无防御模式没有计数器
    assert frame.mac is None  # 无防御模式没有MAC
    assert frame.nonce is None


def test_frame_generation_rolling(sender_rolling):
    """测试滚动计数器模式下的帧生成"""
    frame = sender_rolling.next_frame("UNLOCK")
    
    assert frame is not None
    assert frame.command == "UNLOCK"
    assert frame.counter == 1  # 第一个帧
    assert frame.mac is not None  # 必须有MAC
    assert len(frame.mac) > 0
    assert frame.nonce is None  # 滚动计数器不用nonce


def test_frame_generation_window(sender_window):
    """测试滑动窗口模式下的帧生成"""
    frame = sender_window.next_frame("START")
    
    assert frame is not None
    assert frame.command == "START"
    assert frame.counter == 1
    assert frame.mac is not None
    assert frame.nonce is None


def test_frame_generation_challenge(sender_challenge):
    """测试挑战-响应模式下的帧生成"""
    nonce = "test_nonce_12345678"
    frame = sender_challenge.next_frame("STOP", nonce=nonce)
    
    assert frame is not None
    assert frame.command == "STOP"
    assert frame.counter is None  # 挑战-响应模式没有计数器
    assert frame.mac is not None  # 必须有MAC
    assert frame.nonce == nonce  # 必须包含nonce


def test_challenge_mode_requires_nonce(sender_challenge):
    """测试挑战-响应模式必须提供nonce"""
    with pytest.raises(ValueError):
        sender_challenge.next_frame("LOCK")  # 没有提供nonce


# ============================================================================
# Test: Counter Increment
# ============================================================================

def test_counter_increment(sender_rolling):
    """测试计数器递增逻辑"""
    frame1 = sender_rolling.next_frame("LOCK")
    assert frame1.counter == 1
    
    frame2 = sender_rolling.next_frame("LOCK")
    assert frame2.counter == 2
    
    frame3 = sender_rolling.next_frame("LOCK")
    assert frame3.counter == 3
    
    # 计数器必须严格递增
    assert frame2.counter == frame1.counter + 1
    assert frame3.counter == frame2.counter + 1


def test_counter_independence_per_sender():
    """测试不同sender的计数器独立性"""
    sender1 = Sender(mode=Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    sender2 = Sender(mode=Mode.ROLLING_MAC, shared_key="other_key", mac_length=MAC_LENGTH)
    
    frame1 = sender1.next_frame("LOCK")
    frame2 = sender2.next_frame("LOCK")
    
    # 两个sender的计数器应该都从1开始
    assert frame1.counter == 1
    assert frame2.counter == 1


def test_reset_resets_counter(sender_rolling):
    """测试reset重置计数器"""
    sender_rolling.next_frame("LOCK")
    sender_rolling.next_frame("LOCK")
    
    assert sender_rolling.tx_counter == 2
    
    sender_rolling.reset()
    
    assert sender_rolling.tx_counter == 0
    
    frame = sender_rolling.next_frame("LOCK")
    assert frame.counter == 1


# ============================================================================
# Test: MAC Correctness (RFC 2104)
# ============================================================================

def test_mac_correctness_basic(sender_rolling):
    """测试MAC计算正确性（基本验证）"""
    frame = sender_rolling.next_frame("LOCK")
    
    # 重新计算MAC
    expected_mac = compute_mac(frame.counter, frame.command, key=SHARED_KEY, mac_length=MAC_LENGTH)
    
    assert frame.mac == expected_mac


def test_mac_correctness_multiple_frames(sender_rolling):
    """测试多个帧的MAC计算正确性"""
    commands = ["LOCK", "UNLOCK", "START", "STOP"]
    
    for cmd in commands:
        frame = sender_rolling.next_frame(cmd)
        
        # 验证MAC
        expected_mac = compute_mac(frame.counter, frame.command, key=SHARED_KEY, mac_length=MAC_LENGTH)
        
        assert frame.mac == expected_mac


def test_mac_verification(sender_rolling):
    """测试MAC验证功能"""
    frame = sender_rolling.next_frame("LOCK")
    
    # 正确的MAC应该验证通过
    expected_mac = compute_mac(frame.counter, frame.command, key=SHARED_KEY, mac_length=MAC_LENGTH)
    assert constant_time_compare(expected_mac, frame.mac)
    
    # 错误的MAC应该验证失败
    wrong_mac = "0" * len(frame.mac)
    assert not constant_time_compare(wrong_mac, frame.mac)


def test_mac_uniqueness():
    """测试不同数据生成不同MAC"""
    sender = Sender(mode=Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    
    frame1 = sender.next_frame("LOCK")
    frame2 = sender.next_frame("UNLOCK")
    
    # 不同命令应该生成不同MAC
    assert frame1.mac != frame2.mac


def test_mac_deterministic():
    """测试相同输入生成相同MAC（确定性）"""
    sender1 = Sender(mode=Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    sender2 = Sender(mode=Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    
    frame1 = sender1.next_frame("LOCK")
    frame2 = sender2.next_frame("LOCK")
    
    # 相同密钥、相同命令、相同计数器应该生成相同MAC
    assert frame1.mac == frame2.mac


# ============================================================================
# Test: Challenge-Response Nonce
# ============================================================================

def test_challenge_nonce_in_frame(sender_challenge):
    """测试nonce正确包含在帧中"""
    nonce = "challenge_nonce_xyz"
    frame = sender_challenge.next_frame("LOCK", nonce=nonce)
    
    assert frame.nonce == nonce


def test_challenge_mac_includes_nonce(sender_challenge):
    """测试MAC计算包含nonce"""
    nonce = "test_nonce_123"
    frame = sender_challenge.next_frame("LOCK", nonce=nonce)
    
    # MAC应该基于nonce计算
    expected_mac = compute_mac(nonce, frame.command, key=SHARED_KEY, mac_length=MAC_LENGTH)
    assert frame.mac == expected_mac


def test_different_nonces_different_macs(sender_challenge):
    """测试不同nonce生成不同MAC"""
    frame1 = sender_challenge.next_frame("LOCK", nonce="nonce_1")
    
    sender2 = Sender(mode=Mode.CHALLENGE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    frame2 = sender2.next_frame("LOCK", nonce="nonce_2")
    
    # 不同nonce应该生成不同MAC
    assert frame1.mac != frame2.mac


# ============================================================================
# Test: Command Parameters
# ============================================================================

def test_various_commands(sender_rolling):
    """测试各种命令"""
    commands = ["FWD", "BACK", "LEFT", "RIGHT", "STOP", "FIRE", "SET_TEMP", "LOCK", "UNLOCK"]
    
    for cmd in commands:
        frame = sender_rolling.next_frame(cmd)
        assert frame.command == cmd
        assert frame.mac is not None


def test_empty_command(sender_rolling):
    """测试空命令（边界条件）"""
    frame = sender_rolling.next_frame("")
    
    assert frame is not None
    assert frame.command == ""
    # MAC应该仍然能正确计算
    assert frame.mac is not None


def test_long_command(sender_rolling):
    """测试长命令"""
    long_cmd = "A" * 1000
    frame = sender_rolling.next_frame(long_cmd)
    
    assert frame is not None
    assert frame.command == long_cmd
    assert frame.mac is not None


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_high_counter_values():
    """测试大计数器值"""
    sender = Sender(mode=Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    
    # 发送大量命令，测试计数器是否正确递增
    for i in range(1, 101):
        frame = sender.next_frame("LOCK")
        assert frame.counter == i


def test_mac_length_variations():
    """测试不同MAC长度"""
    for mac_len in [4, 8, 16, 32]:
        sender = Sender(mode=Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=mac_len)
        frame = sender.next_frame("LOCK")
        
        assert len(frame.mac) == mac_len


# ============================================================================
# Test: Defense Mode Comparison
# ============================================================================

def test_all_defense_modes_generate_frames():
    """测试所有防御模式都能生成帧"""
    modes = [Mode.NO_DEFENSE, Mode.ROLLING_MAC, Mode.WINDOW]
    
    for mode in modes:
        sender = Sender(mode=mode, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
        frame = sender.next_frame("LOCK")
        assert frame is not None
        assert frame.command == "LOCK"
    
    # 挑战-响应模式需要nonce
    sender = Sender(mode=Mode.CHALLENGE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    frame = sender.next_frame("LOCK", nonce="test_nonce")
    assert frame is not None
    assert frame.command == "LOCK"


def test_mode_specific_behaviors():
    """测试各模式特定行为"""
    # NO_DEFENSE: 没有计数器和MAC
    sender_no_def = Sender(mode=Mode.NO_DEFENSE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    frame = sender_no_def.next_frame("LOCK")
    assert frame.counter is None
    assert frame.mac is None
    
    # ROLLING_MAC: 有计数器和MAC
    sender_rolling = Sender(mode=Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    frame = sender_rolling.next_frame("LOCK")
    assert frame.counter is not None
    assert frame.mac is not None
    
    # WINDOW: 有计数器和MAC（同ROLLING）
    sender_window = Sender(mode=Mode.WINDOW, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    frame = sender_window.next_frame("LOCK")
    assert frame.counter is not None
    assert frame.mac is not None
    
    # CHALLENGE: 有nonce和MAC，没有计数器
    sender_challenge = Sender(mode=Mode.CHALLENGE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    frame = sender_challenge.next_frame("LOCK", nonce="test")
    assert frame.counter is None
    assert frame.nonce is not None
    assert frame.mac is not None


# ============================================================================
# Test: Key Sensitivity
# ============================================================================

def test_different_keys_different_macs():
    """测试不同密钥生成不同MAC"""
    sender1 = Sender(mode=Mode.ROLLING_MAC, shared_key="key1", mac_length=MAC_LENGTH)
    sender2 = Sender(mode=Mode.ROLLING_MAC, shared_key="key2", mac_length=MAC_LENGTH)
    
    frame1 = sender1.next_frame("LOCK")
    frame2 = sender2.next_frame("LOCK")
    
    # 不同密钥应该生成不同MAC
    assert frame1.mac != frame2.mac


def test_same_key_same_mac():
    """测试相同密钥生成相同MAC"""
    sender1 = Sender(mode=Mode.ROLLING_MAC, shared_key="same_key", mac_length=MAC_LENGTH)
    sender2 = Sender(mode=Mode.ROLLING_MAC, shared_key="same_key", mac_length=MAC_LENGTH)
    
    frame1 = sender1.next_frame("LOCK")
    frame2 = sender2.next_frame("LOCK")
    
    # 相同密钥、命令、计数器应该生成相同MAC
    assert frame1.mac == frame2.mac
