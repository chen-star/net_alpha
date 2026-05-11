"""AES-256-GCM bundle encryption with scrypt KDF.

Envelope layout (single binary file):
  [16 bytes] magic = b"WASHALPHA-BAK\x00\x00\x00"
  [1 byte]   envelope format version = 1
  [16 bytes] scrypt salt
  [12 bytes] AES-GCM nonce
  [N bytes]  ciphertext (includes 16-byte GCM tag appended by AESGCM.encrypt)

AAD: 32-byte prefix passed in by caller.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

ENVELOPE_MAGIC = b"WASHALPHA-BAK\x00\x00\x00"
ENVELOPE_VERSION = 1
SALT_LEN = 16
NONCE_LEN = 12
KEY_LEN = 32
HEADER_LEN = len(ENVELOPE_MAGIC) + 1 + SALT_LEN + NONCE_LEN

_SCRYPT_N = 2**17
_SCRYPT_R = 8
_SCRYPT_P = 1


class BadPassphraseError(Exception):
    """Decryption failed: wrong passphrase, tampered ciphertext, or AAD mismatch."""


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_LEN, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_bundle(plaintext: bytes, *, passphrase: str, aad: bytes) -> bytes:
    if len(aad) != 32:
        raise ValueError(f"aad must be 32 bytes, got {len(aad)}")
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(passphrase, salt)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return (
        ENVELOPE_MAGIC
        + bytes([ENVELOPE_VERSION])
        + salt
        + nonce
        + ct
    )


def decrypt_bundle(envelope: bytes, *, passphrase: str, aad: bytes) -> bytes:
    if len(aad) != 32:
        raise ValueError(f"aad must be 32 bytes, got {len(aad)}")
    if not envelope.startswith(ENVELOPE_MAGIC):
        raise ValueError("not a wash-alpha backup bundle (missing magic)")
    if len(envelope) < HEADER_LEN + 16:
        raise ValueError("bundle is truncated (smaller than header + tag)")
    version = envelope[len(ENVELOPE_MAGIC)]
    if version != ENVELOPE_VERSION:
        raise ValueError(f"unsupported envelope version {version}")
    salt = envelope[len(ENVELOPE_MAGIC) + 1 : len(ENVELOPE_MAGIC) + 1 + SALT_LEN]
    nonce = envelope[len(ENVELOPE_MAGIC) + 1 + SALT_LEN : HEADER_LEN]
    ct = envelope[HEADER_LEN:]
    key = _derive_key(passphrase, salt)
    try:
        return AESGCM(key).decrypt(nonce, ct, aad)
    except InvalidTag as e:
        raise BadPassphraseError("decryption failed: wrong passphrase or corrupted bundle") from e
