from replay.core.cost import CostModel, CostStats, estimate_energy


def test_estimate_energy_sums_components():
    model = CostModel()
    stats = CostStats(tx_bytes=100, rx_bytes=100, hmac_ops=10, state_bytes_peak=8)

    energy = estimate_energy(stats, model)
    more_tx_energy = estimate_energy(
        CostStats(tx_bytes=200, rx_bytes=100, hmac_ops=10, state_bytes_peak=8),
        model,
    )

    assert energy > 0
    assert more_tx_energy > energy
