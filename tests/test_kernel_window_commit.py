from replay.core.kernel.window_commit import window_commit


def test_forward_jump_updates_bitmap_exactly():
    # W=5, H=10, 仅顶位已置（counter 10 已收）
    new_h, new_mask = window_commit(12, 10, [1, 0, 0, 0, 0], 5)
    assert new_h == 12
    # 新顶 counter12 -> offset0；旧 counter10 -> offset (12-10)=2
    assert new_mask == [1, 0, 1, 0, 0]


def test_in_window_accept_marks_only_target_bit():
    new_h, new_mask = window_commit(11, 12, [1, 0, 1, 0, 0], 5)
    assert new_h == 12                      # H 不前移
    assert new_mask == [1, 1, 1, 0, 0]      # 仅 offset(12-11)=1 置位


def test_forward_jump_beyond_window_resets():
    new_h, new_mask = window_commit(100, 10, [1, 1, 1, 1, 1], 5)
    assert new_h == 100
    assert new_mask == [1, 0, 0, 0, 0]      # jump>=W，旧位全部移出


def test_duplicate_or_old_leaves_state_unchanged():
    assert window_commit(11, 12, [1, 1, 1, 0, 0], 5) == (12, [1, 1, 1, 0, 0])  # dup
    assert window_commit(2, 12, [1, 0, 0, 0, 0], 5) == (12, [1, 0, 0, 0, 0])   # old
