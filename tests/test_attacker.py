"""
测试Attacker模块
Tests for Attacker module

验证：
- 帧记录逻辑
- 选择性重放（只重放目标命令）
- 攻击者丢包参数（attacker_loss）
- Dolev-Yao模型符合性
"""

import pytest
from sim.attacker import Attacker
from sim.sender import Sender
from sim.types import Command, DefenseMode, Frame


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sender():
    """创建测试用sender"""
    return Sender(defense=DefenseMode.NO_DEF, seed=42)


@pytest.fixture
def attacker_no_loss():
    """无丢包的攻击者"""
    return Attacker(attacker_loss=0.0, seed=42)


@pytest.fixture
def attacker_with_loss():
    """有丢包的攻击者"""
    return Attacker(attacker_loss=0.2, seed=42)


def create_test_frame(cmd_type, param, counter):
    """创建测试帧"""
    cmd = Command(cmd_type=cmd_type, param=param)
    return Frame(command=cmd, counter=counter, mac=None, nonce=None)


# ============================================================================
# Test: Frame Recording (Eavesdropping)
# ============================================================================

def test_record_single_frame(attacker_no_loss):
    """测试记录单个帧"""
    frame = create_test_frame("LOCK", 0, 1)
    
    attacker_no_loss.observe(frame)
    
    # 验证帧已记录
    recorded = attacker_no_loss.get_recorded_frames()
    assert len(recorded) == 1
    assert recorded[0].command.cmd_type == "LOCK"
    assert recorded[0].counter == 1


def test_record_multiple_frames(attacker_no_loss):
    """测试记录多个帧"""
    frames = [
        create_test_frame("LOCK", 0, 1),
        create_test_frame("UNLOCK", 0, 2),
        create_test_frame("START", 100, 3),
        create_test_frame("STOP", 0, 4),
    ]
    
    for frame in frames:
        attacker_no_loss.observe(frame)
    
    recorded = attacker_no_loss.get_recorded_frames()
    assert len(recorded) == 4
    
    # 验证顺序
    for i, frame in enumerate(recorded):
        assert frame.counter == i + 1


def test_record_preserves_frame_data(attacker_no_loss):
    """测试记录保持帧数据完整性"""
    original_frame = create_test_frame("SET_TEMP", 25, 10)
    original_frame.mac = "test_mac_value"
    original_frame.nonce = "test_nonce"
    
    attacker_no_loss.observe(original_frame)
    
    recorded = attacker_no_loss.get_recorded_frames()
    assert len(recorded) == 1
    
    recorded_frame = recorded[0]
    assert recorded_frame.command.cmd_type == "SET_TEMP"
    assert recorded_frame.command.param == 25
    assert recorded_frame.counter == 10
    assert recorded_frame.mac == "test_mac_value"
    assert recorded_frame.nonce == "test_nonce"


# ============================================================================
# Test: Attacker Loss (Recording Failure)
# ============================================================================

def test_attacker_loss_zero_records_all():
    """测试零丢包率记录所有帧"""
    attacker = Attacker(attacker_loss=0.0, seed=42)
    
    # 发送100个帧
    for i in range(100):
        frame = create_test_frame("TEST", i, i)
        attacker.observe(frame)
    
    recorded = attacker.get_recorded_frames()
    assert len(recorded) == 100


def test_attacker_loss_total_records_none():
    """测试100%丢包率不记录任何帧"""
    attacker = Attacker(attacker_loss=1.0, seed=42)
    
    # 发送100个帧
    for i in range(100):
        frame = create_test_frame("TEST", i, i)
        attacker.observe(frame)
    
    recorded = attacker.get_recorded_frames()
    assert len(recorded) == 0


def test_attacker_loss_20_percent():
    """测试20%丢包率的统计特性"""
    attacker = Attacker(attacker_loss=0.2, seed=42)
    
    sent_count = 1000
    for i in range(sent_count):
        frame = create_test_frame("TEST", i, i)
        attacker.observe(frame)
    
    recorded = attacker.get_recorded_frames()
    record_rate = len(recorded) / sent_count
    
    # 应该记录约80%（允许±5%误差）
    assert 0.75 < record_rate < 0.85, \
        f"Expected ~80% record rate, got {record_rate*100:.1f}%"


def test_attacker_loss_50_percent():
    """测试50%丢包率的统计特性"""
    attacker = Attacker(attacker_loss=0.5, seed=42)
    
    sent_count = 1000
    for i in range(sent_count):
        frame = create_test_frame("TEST", i, i)
        attacker.observe(frame)
    
    recorded = attacker.get_recorded_frames()
    record_rate = len(recorded) / sent_count
    
    # 应该记录约50%（允许±5%误差）
    assert 0.45 < record_rate < 0.55, \
        f"Expected ~50% record rate, got {record_rate*100:.1f}%"


# ============================================================================
# Test: Selective Replay
# ============================================================================

def test_select_target_command(attacker_no_loss):
    """测试选择目标命令"""
    frames = [
        create_test_frame("LOCK", 0, 1),
        create_test_frame("UNLOCK", 0, 2),
        create_test_frame("LOCK", 0, 3),
        create_test_frame("START", 100, 4),
    ]
    
    for frame in frames:
        attacker_no_loss.observe(frame)
    
    # 选择LOCK命令
    target_frames = attacker_no_loss.select_target_frames("LOCK")
    
    assert len(target_frames) == 2
    assert all(f.command.cmd_type == "LOCK" for f in target_frames)
    assert target_frames[0].counter == 1
    assert target_frames[1].counter == 3


def test_select_nonexistent_command(attacker_no_loss):
    """测试选择不存在的命令"""
    frames = [
        create_test_frame("LOCK", 0, 1),
        create_test_frame("UNLOCK", 0, 2),
    ]
    
    for frame in frames:
        attacker_no_loss.observe(frame)
    
    # 选择不存在的命令
    target_frames = attacker_no_loss.select_target_frames("NONEXISTENT")
    
    assert len(target_frames) == 0


def test_select_all_same_command(attacker_no_loss):
    """测试选择所有相同命令"""
    # 记录10个相同命令
    for i in range(10):
        frame = create_test_frame("LOCK", 0, i)
        attacker_no_loss.observe(frame)
    
    target_frames = attacker_no_loss.select_target_frames("LOCK")
    
    assert len(target_frames) == 10


def test_select_with_parameters(attacker_no_loss):
    """测试带参数的命令选择"""
    frames = [
        create_test_frame("SET_TEMP", 20, 1),
        create_test_frame("SET_TEMP", 25, 2),
        create_test_frame("SET_TEMP", 20, 3),
    ]
    
    for frame in frames:
        attacker_no_loss.observe(frame)
    
    # 选择所有SET_TEMP命令
    target_frames = attacker_no_loss.select_target_frames("SET_TEMP")
    
    assert len(target_frames) == 3
    # 验证参数保持
    assert target_frames[0].command.param == 20
    assert target_frames[1].command.param == 25
    assert target_frames[2].command.param == 20


# ============================================================================
# Test: Replay Attack
# ============================================================================

def test_replay_single_frame(attacker_no_loss):
    """测试重放单个帧"""
    original_frame = create_test_frame("LOCK", 0, 5)
    attacker_no_loss.observe(original_frame)
    
    # 选择并重放
    targets = attacker_no_loss.select_target_frames("LOCK")
    replayed = attacker_no_loss.replay_frame(targets[0])
    
    assert replayed is not None
    assert replayed.command.cmd_type == "LOCK"
    assert replayed.counter == 5  # 计数器不变（这是重放攻击的关键）


def test_replay_preserves_mac(attacker_no_loss):
    """测试重放保持MAC（攻击者不能修改MAC）"""
    original_frame = create_test_frame("LOCK", 0, 1)
    original_frame.mac = "original_mac_12345"
    
    attacker_no_loss.observe(original_frame)
    
    targets = attacker_no_loss.select_target_frames("LOCK")
    replayed = attacker_no_loss.replay_frame(targets[0])
    
    # 重放的帧应该保持原始MAC
    assert replayed.mac == "original_mac_12345"


def test_replay_multiple_times(attacker_no_loss):
    """测试多次重放同一帧"""
    frame = create_test_frame("UNLOCK", 0, 10)
    attacker_no_loss.observe(frame)
    
    targets = attacker_no_loss.select_target_frames("UNLOCK")
    
    # 重放5次
    for _ in range(5):
        replayed = attacker_no_loss.replay_frame(targets[0])
        assert replayed is not None
        assert replayed.command.cmd_type == "UNLOCK"
        assert replayed.counter == 10


def test_replay_with_nonce(attacker_no_loss):
    """测试重放包含nonce的帧（挑战-响应）"""
    frame = create_test_frame("LOCK", 0, 1)
    frame.nonce = "challenge_nonce_abc123"
    frame.mac = "response_mac"
    
    attacker_no_loss.observe(frame)
    
    targets = attacker_no_loss.select_target_frames("LOCK")
    replayed = attacker_no_loss.replay_frame(targets[0])
    
    # 攻击者只能重放，不能生成新的有效nonce
    assert replayed.nonce == "challenge_nonce_abc123"
    assert replayed.mac == "response_mac"


# ============================================================================
# Test: Dolev-Yao Model Compliance
# ============================================================================

def test_attacker_cannot_forge_mac(attacker_no_loss):
    """
    测试攻击者不能伪造MAC（Dolev-Yao模型）
    攻击者只能重放，不能创建新的有效MAC
    """
    frame = create_test_frame("LOCK", 0, 1)
    frame.mac = "valid_mac_xyz"
    
    attacker_no_loss.observe(frame)
    
    targets = attacker_no_loss.select_target_frames("LOCK")
    replayed = attacker_no_loss.replay_frame(targets[0])
    
    # 重放的MAC应该完全相同（攻击者不能修改）
    assert replayed.mac == "valid_mac_xyz"
    
    # 验证不是新生成的MAC
    # （在真实实现中，攻击者没有密钥，不能生成新MAC）


def test_attacker_can_eavesdrop(attacker_no_loss):
    """测试攻击者可以窃听（Dolev-Yao模型）"""
    # Dolev-Yao假设：攻击者可以完全控制网络
    frames = [
        create_test_frame("SECRET_CMD_1", 0, 1),
        create_test_frame("SECRET_CMD_2", 0, 2),
    ]
    
    for frame in frames:
        attacker_no_loss.observe(frame)
    
    # 攻击者应该能看到所有帧
    recorded = attacker_no_loss.get_recorded_frames()
    assert len(recorded) == 2


def test_attacker_can_replay(attacker_no_loss):
    """测试攻击者可以重放（Dolev-Yao模型）"""
    frame = create_test_frame("LOCK", 0, 1)
    attacker_no_loss.observe(frame)
    
    # 攻击者可以任意次重放
    targets = attacker_no_loss.select_target_frames("LOCK")
    for _ in range(10):
        replayed = attacker_no_loss.replay_frame(targets[0])
        assert replayed is not None


def test_attacker_can_delay(attacker_no_loss):
    """测试攻击者可以延迟消息（Dolev-Yao模型）"""
    # 记录早期帧
    early_frame = create_test_frame("LOCK", 0, 1)
    attacker_no_loss.observe(early_frame)
    
    # 记录更多帧
    for i in range(2, 11):
        frame = create_test_frame("OTHER", 0, i)
        attacker_no_loss.observe(frame)
    
    # 攻击者可以延迟重放早期帧
    targets = attacker_no_loss.select_target_frames("LOCK")
    delayed_replay = attacker_no_loss.replay_frame(targets[0])
    
    assert delayed_replay.counter == 1  # 旧计数器


# ============================================================================
# Test: Reproducibility (Seed)
# ============================================================================

def test_reproducibility_with_seed():
    """测试固定种子的可重现性"""
    seed = 42
    
    # 第一次
    attacker1 = Attacker(attacker_loss=0.2, seed=seed)
    for i in range(100):
        frame = create_test_frame("TEST", i, i)
        attacker1.observe(frame)
    recorded1 = attacker1.get_recorded_frames()
    
    # 第二次（相同种子）
    attacker2 = Attacker(attacker_loss=0.2, seed=seed)
    for i in range(100):
        frame = create_test_frame("TEST", i, i)
        attacker2.observe(frame)
    recorded2 = attacker2.get_recorded_frames()
    
    # 应该记录相同的帧
    assert len(recorded1) == len(recorded2)
    for f1, f2 in zip(recorded1, recorded2):
        assert f1.counter == f2.counter


def test_different_seeds_different_results():
    """测试不同种子产生不同结果"""
    # 第一次
    attacker1 = Attacker(attacker_loss=0.5, seed=42)
    for i in range(100):
        frame = create_test_frame("TEST", i, i)
        attacker1.observe(frame)
    recorded1 = attacker1.get_recorded_frames()
    
    # 第二次（不同种子）
    attacker2 = Attacker(attacker_loss=0.5, seed=99)
    for i in range(100):
        frame = create_test_frame("TEST", i, i)
        attacker2.observe(frame)
    recorded2 = attacker2.get_recorded_frames()
    
    # 由于随机性，记录的帧应该不同
    assert len(recorded1) != len(recorded2) or \
           any(f1.counter != f2.counter for f1, f2 in zip(recorded1, recorded2))


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_no_frames_recorded(attacker_no_loss):
    """测试没有记录任何帧"""
    recorded = attacker_no_loss.get_recorded_frames()
    assert len(recorded) == 0
    
    # 选择应该返回空列表
    targets = attacker_no_loss.select_target_frames("LOCK")
    assert len(targets) == 0


def test_replay_empty_targets():
    """测试重放空目标列表"""
    attacker = Attacker(attacker_loss=0.0, seed=42)
    
    # 没有记录任何帧
    targets = attacker.select_target_frames("NONEXISTENT")
    assert len(targets) == 0
    
    # 尝试重放空列表中的第一个（应该处理gracefully）
    # 注：实际实现中可能需要检查


def test_large_number_of_frames(attacker_no_loss):
    """测试大量帧记录"""
    # 记录10000个帧
    for i in range(10000):
        frame = create_test_frame("TEST", i % 100, i)
        attacker_no_loss.observe(frame)
    
    recorded = attacker_no_loss.get_recorded_frames()
    assert len(recorded) == 10000


def test_select_first_occurrence(attacker_no_loss):
    """测试选择第一次出现的命令"""
    frames = [
        create_test_frame("UNLOCK", 0, 1),
        create_test_frame("LOCK", 0, 2),
        create_test_frame("UNLOCK", 0, 3),
    ]
    
    for frame in frames:
        attacker_no_loss.observe(frame)
    
    targets = attacker_no_loss.select_target_frames("LOCK")
    
    # 应该只有一个LOCK
    assert len(targets) == 1
    assert targets[0].counter == 2


# ============================================================================
# Test: Attack Strategies
# ============================================================================

def test_replay_oldest_frame(attacker_no_loss):
    """测试重放最旧的帧（常见攻击策略）"""
    # 记录多个LOCK命令
    for i in range(1, 11):
        frame = create_test_frame("LOCK", 0, i)
        attacker_no_loss.observe(frame)
    
    targets = attacker_no_loss.select_target_frames("LOCK")
    
    # 重放最旧的（第一个）
    oldest = targets[0]
    replayed = attacker_no_loss.replay_frame(oldest)
    
    assert replayed.counter == 1


def test_replay_newest_frame(attacker_no_loss):
    """测试重放最新的帧（另一种攻击策略）"""
    # 记录多个LOCK命令
    for i in range(1, 11):
        frame = create_test_frame("LOCK", 0, i)
        attacker_no_loss.observe(frame)
    
    targets = attacker_no_loss.select_target_frames("LOCK")
    
    # 重放最新的（最后一个）
    newest = targets[-1]
    replayed = attacker_no_loss.replay_frame(newest)
    
    assert replayed.counter == 10


def test_replay_random_frame(attacker_no_loss):
    """测试重放随机选择的帧"""
    # 记录多个命令
    for i in range(1, 21):
        frame = create_test_frame("LOCK", 0, i)
        attacker_no_loss.observe(frame)
    
    targets = attacker_no_loss.select_target_frames("LOCK")
    
    # 重放中间的某个
    middle = targets[len(targets) // 2]
    replayed = attacker_no_loss.replay_frame(middle)
    
    assert replayed is not None
    assert 1 <= replayed.counter <= 20


# ============================================================================
# Test: Statistics
# ============================================================================

def test_record_statistics(attacker_with_loss):
    """测试记录统计信息"""
    sent_count = 1000
    
    for i in range(sent_count):
        frame = create_test_frame("TEST", i, i)
        attacker_with_loss.observe(frame)
    
    recorded = attacker_with_loss.get_recorded_frames()
    record_rate = len(recorded) / sent_count
    
    # 20%丢包，应该记录约80%
    # 验证统计特性
    assert 0.75 < record_rate < 0.85


def test_selective_replay_statistics(attacker_no_loss):
    """测试选择性重放统计"""
    # 记录混合命令
    commands = ["LOCK", "UNLOCK", "START", "STOP"]
    for i in range(400):
        cmd_type = commands[i % len(commands)]
        frame = create_test_frame(cmd_type, 0, i)
        attacker_no_loss.observe(frame)
    
    # 每种命令应该有100个
    for cmd_type in commands:
        targets = attacker_no_loss.select_target_frames(cmd_type)
        assert len(targets) == 100

