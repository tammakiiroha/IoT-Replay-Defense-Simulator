"""AttackerStrategy abstraction + RandomReplay baseline byte-identity (Phase 5 P1).

RandomReplay must reproduce the legacy attacker behaviour byte-for-byte on BOTH
paths: the live path (`pick_frame` via rng.choice over recorded) and the paired
path (`pick_recorded` via `candidates[raw_pick % len]`). These are the A1
zero-drift blockers.
"""
from replay.core.attacker import (
    AttackContext,
    Attacker,
    RandomReplay,
)
from replay.core.rng import DeterministicRNG
from replay.core.types import Frame


def _frame(counter: int, command: str = "CMD") -> Frame:
    return Frame(command=command, counter=counter, mac=f"m{counter}", nonce=None)


# --- live path: pick_frame byte-identical to rng.choice(recorded) ---


def test_random_replay_matches_legacy_attacker():
    frames = [_frame(i) for i in range(10)]
    strat = RandomReplay(record_loss=0.0)
    rec_rng = DeterministicRNG(1)
    for f in frames:
        strat.observe(f, rec_rng)  # record_loss=0 -> all recorded, no rng consumed

    pick_rng = DeterministicRNG(42)
    ref_rng = DeterministicRNG(42)
    recorded_ref = [f.clone() for f in frames]
    for _ in range(20):
        got = strat.pick_frame(pick_rng)
        exp = ref_rng.choice(recorded_ref)
        assert got is not None
        assert got.counter == exp.counter


def test_random_replay_observe_record_loss_byte_identical():
    frames = [_frame(i) for i in range(50)]
    strat = RandomReplay(record_loss=0.3)
    strat_rng = DeterministicRNG(7)
    ref_rng = DeterministicRNG(7)
    expected = []
    for f in frames:
        strat.observe(f, strat_rng)
        # legacy: skip iff record_loss>0 and rng.random() < record_loss
        if not (0.3 > 0 and ref_rng.random() < 0.3):
            expected.append(f.counter)
    assert [fr.counter for fr in strat._recorded] == expected


def test_random_replay_pick_frame_empty_returns_none():
    assert RandomReplay().pick_frame(DeterministicRNG(0)) is None


def test_random_replay_pick_frame_clone_independent():
    strat = RandomReplay()
    strat.observe(_frame(1, "LOCK"), DeterministicRNG(0))
    a = strat.pick_frame(DeterministicRNG(0))
    a.command = "MODIFIED"
    b = strat.pick_frame(DeterministicRNG(0))
    assert b.command == "LOCK"


# --- paired path: pick_recorded byte-identical to candidates[raw_pick % len] ---


def test_random_replay_matches_legacy_paired():
    recorded = [_frame(i) for i in range(7)]
    strat = RandomReplay()
    for raw in [0, 1, 6, 7, 13, 100, (1 << 31) - 1]:
        got = strat.pick_recorded(raw, recorded)
        assert got is not None
        ref = recorded[raw % len(recorded)]
        assert got.counter == ref.counter
        assert got is not ref  # cloned


def test_random_replay_paired_target_commands_filter():
    recorded = [_frame(i, "LOCK" if i % 2 == 0 else "OTHER") for i in range(6)]
    strat = RandomReplay(target_commands=["LOCK"])
    cands = [f for f in recorded if f.command == "LOCK"]
    for raw in [0, 1, 2, 5, 99]:
        got = strat.pick_recorded(raw, recorded)
        assert got is not None
        assert got.counter == cands[raw % len(cands)].counter


def test_random_replay_pick_recorded_empty_returns_none():
    assert RandomReplay().pick_recorded(5, []) is None


def test_random_replay_pick_recorded_no_target_match_returns_none():
    recorded = [_frame(i, "OTHER") for i in range(3)]
    assert RandomReplay(target_commands=["LOCK"]).pick_recorded(0, recorded) is None


# --- protocol surface ---


def test_attacker_is_random_replay_alias():
    a = Attacker(record_loss=0.0, target_commands=["LOCK"])
    assert isinstance(a, RandomReplay)


def test_pick_methods_accept_optional_context():
    strat = RandomReplay()
    strat.observe(_frame(1), DeterministicRNG(0))
    ctx = AttackContext(window_size=4, g_hard=16, last_counter=0)
    assert strat.pick_frame(DeterministicRNG(0), context=ctx) is not None
    assert strat.pick_recorded(0, [_frame(1)], context=ctx) is not None
