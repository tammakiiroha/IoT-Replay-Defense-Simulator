import pytest

from replay.core.security import compute_mac_bits


def test_compute_mac_bits_length():
    tag = compute_mac_bits(5, "CMD", key="k", tag_bits=80)

    assert len(tag) == 20
    with pytest.raises(ValueError):
        compute_mac_bits(5, "CMD", key="k", tag_bits=81)
