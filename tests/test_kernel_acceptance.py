from replay.core.kernel.acceptance import SwDecision, classify


def test_accept_forward():
    assert classify(13, 10, [1, 0, 0, 0, 0], 5) is SwDecision.ACCEPT_FORWARD


def test_accept_in_window():
    assert classify(11, 12, [1, 0, 0, 0, 0], 5) is SwDecision.ACCEPT_IN_WINDOW


def test_reject_dup():
    assert classify(11, 12, [1, 1, 0, 0, 0], 5) is SwDecision.REJECT_DUP


def test_reject_old():
    assert classify(7, 12, [1, 0, 0, 0, 0], 5) is SwDecision.REJECT_OLD
