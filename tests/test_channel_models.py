from replay.core.channel_models import GilbertElliottLoss, IidLoss, TraceLoss
from replay.core.rng import DeterministicRNG


def test_iid_loss_is_deterministic_under_seed():
    rng_a, rng_b = DeterministicRNG(1), DeterministicRNG(1)

    a = [IidLoss(0.5).dropped(rng_a) for _ in range(50)]
    b = [IidLoss(0.5).dropped(rng_b) for _ in range(50)]

    assert a == b


def test_gilbert_elliott_bursts_more_than_iid_mean():
    rng = DeterministicRNG(2)
    ge = GilbertElliottLoss(
        p_good_to_bad=0.05,
        p_bad_to_good=0.3,
        loss_good=0.0,
        loss_bad=1.0,
    )

    drops = [ge.dropped(rng) for _ in range(2000)]

    assert any(drops)
    assert max(_run_lengths(drops)) >= 2


def test_trace_loss_follows_provided_sequence():
    trace = TraceLoss([True, False, True])
    rng = DeterministicRNG(0)

    assert [trace.dropped(rng) for _ in range(4)] == [True, False, True, True]


def _run_lengths(flags: list[bool]) -> list[int]:
    runs: list[int] = []
    current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        runs.append(current)
    return runs
