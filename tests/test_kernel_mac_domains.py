from replay.core.kernel.mac_domains import (
    crit_confirm_tag,
    crit_prepare_tag,
    hmac96,
    normal_req_tag,
    resync_confirm_tag,
)

KEY = "k"


def test_hmac96_is_24_hex_chars():
    assert len(hmac96(KEY, b"DOMAIN", b"X", 1)) == 24


def test_length_prefix_no_delimiter_collision():
    # ("a","bc") 与 ("ab","c") 朴素拼接会碰撞；长度前缀必须区分
    assert hmac96(KEY, b"a", b"bc") != hmac96(KEY, b"ab", b"c")


def test_bytes_payload_with_pipe_unambiguous():
    assert hmac96(KEY, b"D", b"x|y", b"z") != hmac96(KEY, b"D", b"x", b"y|z")


def test_type_tag_distinguishes_int_from_equal_bytes():
    # 修审查 P1-2：int 1 与其 8 字节大端表示必须产生不同 tag（类型语义歧义）
    assert hmac96(KEY, 1) != hmac96(KEY, (1).to_bytes(8, "big", signed=True))
    assert hmac96(KEY, True) != hmac96(KEY, b"\x01")


def test_all_four_domains_distinct():
    tags = {
        normal_req_tag(KEY, 1, 0, 0, 7, "OPEN", b"p", 0),
        crit_prepare_tag(KEY, 1, 0, 0, 7, "OPEN", b"ph", 0),
        crit_confirm_tag(KEY, 1, 0, 0, 7, "OPEN", b"ph", 1, 2, "nr", 5, 0),
        resync_confirm_tag(KEY, 1, 0, 0, 1, 10, 200, "nr", 5, 0),
    }
    assert len(tags) == 4


def test_resync_tag_changes_with_new_h():
    assert resync_confirm_tag(KEY, 1, 0, 0, 1, 10, 200, "nr", 5, 0) \
        != resync_confirm_tag(KEY, 1, 0, 0, 1, 10, 999, "nr", 5, 0)
