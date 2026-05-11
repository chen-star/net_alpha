from __future__ import annotations

import pytest

from net_alpha.backup.crypto import (
    BadPassphraseError,
    ENVELOPE_MAGIC,
    decrypt_bundle,
    encrypt_bundle,
)


def test_encrypt_decrypt_roundtrip():
    plaintext = b"hello backup world" * 1000
    aad = b"a" * 32
    enc = encrypt_bundle(plaintext, passphrase="hunter2", aad=aad)
    assert enc.startswith(ENVELOPE_MAGIC)
    assert decrypt_bundle(enc, passphrase="hunter2", aad=aad) == plaintext


def test_wrong_passphrase_raises():
    enc = encrypt_bundle(b"hi", passphrase="right", aad=b"x" * 32)
    with pytest.raises(BadPassphraseError):
        decrypt_bundle(enc, passphrase="wrong", aad=b"x" * 32)


def test_aad_mismatch_raises():
    enc = encrypt_bundle(b"hi", passphrase="p", aad=b"original-aad".ljust(32, b"\x00"))
    with pytest.raises(BadPassphraseError):
        decrypt_bundle(enc, passphrase="p", aad=b"different-aad".ljust(32, b"\x00"))


def test_tamper_byte_raises():
    enc = encrypt_bundle(b"hello", passphrase="p", aad=b"a" * 32)
    # Flip a byte in the ciphertext region (after the 16+1+16+12 = 45-byte header).
    tampered = bytearray(enc)
    tampered[50] ^= 0xFF
    with pytest.raises(BadPassphraseError):
        decrypt_bundle(bytes(tampered), passphrase="p", aad=b"a" * 32)


def test_bad_magic_raises():
    with pytest.raises(ValueError, match="not a wash-alpha"):
        decrypt_bundle(b"\x00" * 100, passphrase="p", aad=b"a" * 32)
