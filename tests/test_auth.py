import pytest

from replay.core.auth import HmacAuthenticator


def test_hmac_authenticator_roundtrip():
    authenticator = HmacAuthenticator(key="k", tag_bits=80)
    tag = authenticator.tag(5, "CMD")

    assert authenticator.verify(5, "CMD", tag)
    assert not authenticator.verify(6, "CMD", tag)
    assert len(tag) == 80 // 4


def test_ascon_authenticator_roundtrip_if_available():
    pytest.importorskip("ascon")
    from replay.core.auth import AsconAeadAuthenticator

    authenticator = AsconAeadAuthenticator(key=b"0" * 16)
    tag = authenticator.tag(5, "CMD")

    assert authenticator.verify(5, "CMD", tag)
