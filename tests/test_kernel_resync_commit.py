from replay.core.kernel.resync_commit import epoch_bump, resync_commit_same_epoch


def test_same_epoch_seals_full_window():
    # H2：同 epoch resync -> H=new_h，整窗封死（全 1）
    new_h, mask = resync_commit_same_epoch(200, 5)
    assert new_h == 200
    assert mask == [1, 1, 1, 1, 1]


def test_epoch_bump_resets_window():
    # reboot/brownout：epoch+1，H=new_h，M_W 清零（新窗口）
    e, h, mask = epoch_bump(old_epoch=1, new_h=0, w=5)
    assert e == 2
    assert h == 0
    assert mask == [0, 0, 0, 0, 0]
