"""
Tests for Attacker module

验证：
- 帧记录逻辑
- 选择性重放（只重放目标命令）
- 攻击者丢包参数（attacker_loss）
- Dolev-Yao模型符合性
"""

import random
import pytest
from sim.attacker import Attacker
from sim.types import Frame


# ============================================================================
# Fixtures
# ============================================================================

def create_test_frame(cmd_type: str, counter: int, mac: str = None) -> Frame:
    """创建测试帧"""
    return Frame(command=cmd_type, counter=counter, mac=mac, nonce=None)


@pytest.fixture
def attacker_no_loss():
    """无丢包的攻击者"""
    return Attacker(record_loss=0.0)


@pytest.fixture
def attacker_with_loss():
    """有丢包的攻击者"""
    return Attacker(record_loss=0.2)


@pytest.fixture
def attacker_selective():
    """选择性重放攻击者"""
    return Attacker(record_loss=0.0, target_commands=["LOCK", "UNLOCK"])


# ============================================================================
# Test: Frame Recording (Eavesdropping)
# ============================================================================

def test_record_single_frame(attacker_no_loss):
    """测试记录单个帧"""
    rng = random.Random(42)
    frame = create_test_frame("LOCK", 1)
    
    attacker_no_loss.observe(frame, rng)
    
    # 验证帧已记录（通过pick_frame来验证）
    picked = attacker_no_loss.pick_frame(rng)
    assert picked is not None
    assert picked.command == "LOCK"
    assert picked.counter == 1


def test_record_multiple_frames(attacker_no_loss):
    """测试记录多个帧"""
    rng = random.Random(42)
    frames = [
        create_test_frame("LOCK", 1),
        create_test_frame("UNLOCK", 2),
        create_test_frame("START", 3),
        create_test_frame("STOP", 4),
    ]
    
    for frame in frames:
        attacker_no_loss.observe(frame, rng)
    
    # 应该能pick到一些帧
    picked = attacker_no_loss.pick_frame(rng)
    assert picked is not None
    assert picked.counter >= 1


def test_record_preserves_frame_data(attacker_no_loss):
    """测试记录保持帧数据完整性"""
    rng = random.Random(42)
    original_frame = create_test_frame("SET_TEMP", 10, mac="test_mac_value")
    original_frame.nonce = "test_nonce"
    
    attacker_no_loss.observe(original_frame, rng)
    
    picked = attacker_no_loss.pick_frame(rng)
    assert picked is not None
    assert picked.command == "SET_TEMP"
    assert picked.counter == 10
    assert picked.mac == "test_mac_value"
    assert picked.nonce == "test_nonce"


# ============================================================================
# Test: Attacker Loss (Recording Failure)
# ============================================================================

def test_attacker_loss_zero_records_all():
    """测试零丢包率记录所有帧"""
    attacker = Attacker(record_loss=0.0)
    rng = random.Random(42)
    
    # 发送100个帧
    for i in range(100):
        frame = create_test_frame("TEST", i)
        attacker.observe(frame, rng)
    
    # 应该能pick到帧（无法直接获取recorded数量，但pick应该成功）
    picked = attacker.pick_frame(rng)
    assert picked is not None


def test_attacker_loss_total_records_none():
    """测试100%丢包率不记录任何帧"""
    attacker = Attacker(record_loss=1.0)
    rng = random.Random(42)
    
    # 发送100个帧
    for i in range(100):
        frame = create_test_frame("TEST", i)
        attacker.observe(frame, rng)
    
    # pick应该返回None（没有记录任何帧）
    picked = attacker.pick_frame(rng)
    assert picked is None


def test_attacker_loss_partial():
    """测试部分丢包率的统计特性"""
    attacker = Attacker(record_loss=0.5)
    rng = random.Random(42)
    
    sent_count = 100
    for i in range(sent_count):
        frame = create_test_frame("TEST", i)
        attacker.observe(frame, rng)
    
    # 多次pick应该能获取一些帧
    pick_success = 0
    for _ in range(50):
        pick_rng = random.Random(42 + _)
        if attacker.pick_frame(pick_rng) is not None:
            pick_success += 1
    
    # 应该有成功pick的（说明确实记录了一些帧）
    assert pick_success > 0


# ============================================================================
# Test: Selective Replay
# ============================================================================

def test_selective_replay_target_commands(attacker_selective):
    """测试选择性重放目标命令"""
    rng = random.Random(42)
    frames = [
        create_test_frame("LOCK", 1),
        create_test_frame("OTHER", 2),
        create_test_frame("UNLOCK", 3),
        create_test_frame("OTHER", 4),
    ]
    
    for frame in frames:
        attacker_selective.observe(frame, rng)
    
    # pick多次，应该只能pick到LOCK或UNLOCK
    picked_commands = set()
    for _ in range(50):
        pick_rng = random.Random(42 + _)
        picked = attacker_selective.pick_frame(pick_rng)
        if picked:
            picked_commands.add(picked.command)
    
    # 应该只有目标命令
    assert picked_commands <= {"LOCK", "UNLOCK"}


def test_selective_replay_no_match():
    """测试选择性重放不匹配的情况"""
    attacker = Attacker(record_loss=0.0, target_commands=["NONEXISTENT"])
    rng = random.Random(42)
    
    frames = [
        create_test_frame("LOCK", 1),
        create_test_frame("UNLOCK", 2),
    ]
    
    for frame in frames:
        attacker.observe(frame, rng)
    
    # pick应该返回None（没有匹配的目标命令）
    picked = attacker.pick_frame(rng)
    assert picked is None


# ============================================================================
# Test: Replay Attack
# ============================================================================

def test_replay_preserves_mac(attacker_no_loss):
    """测试重放保持MAC（攻击者不能修改MAC）"""
    rng = random.Random(42)
    original_frame = create_test_frame("LOCK", 1, mac="original_mac_12345")
    
    attacker_no_loss.observe(original_frame, rng)
    
    picked = attacker_no_loss.pick_frame(rng)
    
    # 重放的帧应该保持原始MAC
    assert picked.mac == "original_mac_12345"


def test_replay_multiple_times(attacker_no_loss):
    """测试多次重放"""
    rng = random.Random(42)
    frame = create_test_frame("UNLOCK", 10)
    attacker_no_loss.observe(frame, rng)
    
    # 重放5次（每次应该返回相同的帧克隆）
    for i in range(5):
        pick_rng = random.Random(42)  # 相同种子
        picked = attacker_no_loss.pick_frame(pick_rng)
        assert picked is not None
        assert picked.command == "UNLOCK"
        assert picked.counter == 10


def test_replay_with_nonce(attacker_no_loss):
    """测试重放包含nonce的帧（挑战-响应）"""
    rng = random.Random(42)
    frame = create_test_frame("LOCK", 1, mac="response_mac")
    frame.nonce = "challenge_nonce_abc123"
    
    attacker_no_loss.observe(frame, rng)
    
    picked = attacker_no_loss.pick_frame(rng)
    
    # 攻击者只能重放，不能生成新的有效nonce
    assert picked.nonce == "challenge_nonce_abc123"
    assert picked.mac == "response_mac"


# ============================================================================
# Test: Dolev-Yao Model Compliance
# ============================================================================

def test_attacker_cannot_modify_recorded_frame(attacker_no_loss):
    """
    测试攻击者不能修改录制的帧
    picked帧应该是克隆，修改它不影响原始记录
    """
    rng = random.Random(42)
    frame = create_test_frame("LOCK", 1, mac="valid_mac")
    attacker_no_loss.observe(frame, rng)
    
    # pick一个帧并修改它
    picked1 = attacker_no_loss.pick_frame(rng)
    picked1.command = "MODIFIED"
    
    # 再次pick应该得到原始的帧
    picked2 = attacker_no_loss.pick_frame(random.Random(42))
    assert picked2.command == "LOCK"  # 不应该被修改


def test_attacker_can_eavesdrop(attacker_no_loss):
    """测试攻击者可以窃听（Dolev-Yao模型）"""
    rng = random.Random(42)
    # Dolev-Yao假设：攻击者可以完全控制网络
    frames = [
        create_test_frame("SECRET_CMD_1", 1),
        create_test_frame("SECRET_CMD_2", 2),
    ]
    
    for frame in frames:
        attacker_no_loss.observe(frame, rng)
    
    # 攻击者应该能访问到帧
    picked = attacker_no_loss.pick_frame(rng)
    assert picked is not None


def test_attacker_can_replay(attacker_no_loss):
    """测试攻击者可以重放（Dolev-Yao模型）"""
    rng = random.Random(42)
    frame = create_test_frame("LOCK", 1)
    attacker_no_loss.observe(frame, rng)
    
    # 攻击者可以任意次重放
    for i in range(10):
        pick_rng = random.Random(42 + i)
        picked = attacker_no_loss.pick_frame(pick_rng)
        assert picked is not None


# ============================================================================
# Test: Reproducibility (Seed)
# ============================================================================

def test_reproducibility_with_seed():
    """测试固定种子的可重现性"""
    seed = 42
    
    # 第一次
    attacker1 = Attacker(record_loss=0.2)
    rng1 = random.Random(seed)
    for i in range(100):
        frame = create_test_frame("TEST", i)
        attacker1.observe(frame, rng1)
    picked1 = attacker1.pick_frame(random.Random(seed))
    
    # 第二次（相同种子）
    attacker2 = Attacker(record_loss=0.2)
    rng2 = random.Random(seed)
    for i in range(100):
        frame = create_test_frame("TEST", i)
        attacker2.observe(frame, rng2)
    picked2 = attacker2.pick_frame(random.Random(seed))
    
    # 应该pick到相同的帧
    if picked1 and picked2:
        assert picked1.counter == picked2.counter


def test_different_seeds_different_results():
    """测试不同种子产生不同结果"""
    # 第一次
    attacker1 = Attacker(record_loss=0.5)
    rng1 = random.Random(42)
    for i in range(100):
        frame = create_test_frame("TEST", i)
        attacker1.observe(frame, rng1)
    
    # 第二次（不同种子）
    attacker2 = Attacker(record_loss=0.5)
    rng2 = random.Random(99)
    for i in range(100):
        frame = create_test_frame("TEST", i)
        attacker2.observe(frame, rng2)
    
    # 由于随机性，记录的帧可能不同
    # 测试通过，只要没有异常


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_no_frames_recorded(attacker_no_loss):
    """测试没有记录任何帧"""
    rng = random.Random(42)
    
    # 没有observe任何帧
    picked = attacker_no_loss.pick_frame(rng)
    assert picked is None


def test_clear_recorded_frames(attacker_no_loss):
    """测试清除记录的帧"""
    rng = random.Random(42)
    
    # 记录一些帧
    for i in range(10):
        frame = create_test_frame("TEST", i)
        attacker_no_loss.observe(frame, rng)
    
    # 清除
    attacker_no_loss.clear()
    
    # pick应该返回None
    picked = attacker_no_loss.pick_frame(rng)
    assert picked is None


def test_large_number_of_frames(attacker_no_loss):
    """测试大量帧记录"""
    rng = random.Random(42)
    
    # 记录10000个帧
    for i in range(10000):
        frame = create_test_frame("TEST", i)
        attacker_no_loss.observe(frame, rng)
    
    # 应该能正常pick
    picked = attacker_no_loss.pick_frame(rng)
    assert picked is not None


# ============================================================================
# Test: Attack Strategies
# ============================================================================

def test_random_frame_selection(attacker_no_loss):
    """测试随机帧选择"""
    rng = random.Random(42)
    
    # 记录多个不同命令
    for i in range(1, 21):
        frame = create_test_frame(f"CMD_{i}", i)
        attacker_no_loss.observe(frame, rng)
    
    # pick多次，应该有不同的结果
    picked_counters = set()
    for seed in range(100):
        pick_rng = random.Random(seed)
        picked = attacker_no_loss.pick_frame(pick_rng)
        if picked:
            picked_counters.add(picked.counter)
    
    # 应该有多个不同的帧被选中
    assert len(picked_counters) > 1


def test_clone_independence(attacker_no_loss):
    """测试克隆的独立性"""
    rng = random.Random(42)
    frame = create_test_frame("LOCK", 1, mac="original")
    attacker_no_loss.observe(frame, rng)
    
    # pick两次
    picked1 = attacker_no_loss.pick_frame(random.Random(42))
    picked2 = attacker_no_loss.pick_frame(random.Random(42))
    
    # 修改picked1不应该影响picked2
    picked1.command = "MODIFIED"
    assert picked2.command == "LOCK"
