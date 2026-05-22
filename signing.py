"""
Ed25519 keypair management + canonical signing for the public ledger.

This module is intentionally small and self-contained. It exists on the
`feat/ledger-mvp` branch (which forks from `main`) so the ledger work
doesn't drag in the full Stage 2a `federation.py` surface area; once
Stage 2a lands on `main`, the two can share the same key files on disk
without any code conflict — the file format is identical (PEM-wrapped
32-byte raw Ed25519 seed / public key).

Key files live in `config.NODE_KEY_DIR` (default `~/.ubi-bot/`):

  node_private_key.pem    mode 600, this node only
  node_public_key.pem     mode 644, safe to publish

If both files exist and parse, they are reused. If neither exists, a
fresh keypair is generated. If one exists but not the other, we abort
loudly — silently regenerating would lose history.

Canonical form for signing:
  - JSON object with all fields EXCEPT `node_signature`
  - keys sorted lexicographically
  - no extra whitespace (separators=(",", ":"))
  - UTF-8 encoded

The signature is Ed25519 over those bytes, base64-encoded.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional

from nacl.signing import SigningKey, VerifyKey

import config

logger = logging.getLogger("ubi-bot.signing")

_PRIVATE_KEY_FILENAME = "node_private_key.pem"
_PUBLIC_KEY_FILENAME = "node_public_key.pem"

_PRIVATE_PEM_HEADER = "-----BEGIN UBI NODE ED25519 PRIVATE KEY-----"
_PRIVATE_PEM_FOOTER = "-----END UBI NODE ED25519 PRIVATE KEY-----"
_PUBLIC_PEM_HEADER = "-----BEGIN UBI NODE ED25519 PUBLIC KEY-----"
_PUBLIC_PEM_FOOTER = "-----END UBI NODE ED25519 PUBLIC KEY-----"


def _pem_wrap(header: str, footer: str, raw: bytes) -> str:
    body = base64.b64encode(raw).decode("ascii")
    # 64-char lines per RFC 7468.
    lines = [body[i : i + 64] for i in range(0, len(body), 64)]
    return "\n".join([header, *lines, footer]) + "\n"


def _pem_unwrap(header: str, footer: str, text: str) -> bytes:
    lines = [ln.strip() for ln in text.strip().splitlines()]
    if not lines or lines[0] != header or lines[-1] != footer:
        raise ValueError(f"PEM header/footer mismatch (expected {header!r} / {footer!r})")
    body = "".join(lines[1:-1])
    return base64.b64decode(body, validate=True)


def _ensure_key_dir(key_dir: str) -> Path:
    p = Path(key_dir).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(p, 0o700)
    except OSError as exc:
        logger.warning("Could not chmod 700 on %s: %s", p, exc)
    return p


def public_key_fingerprint(public_key_bytes: bytes) -> str:
    """Short stable fingerprint — first 16 hex chars, colon-separated in 4s.

    Matches the format Stage 2a's `federation.py` uses, so a fingerprint
    printed by one module is interchangeable with the other.
    """
    hexed = public_key_bytes.hex()
    chunks = [hexed[i : i + 4] for i in range(0, 16, 4)]
    return ":".join(chunks)


# Cached on first load. Process-local; cheap to reload but no need to.
_cached_keypair: Optional[dict] = None


def load_or_create_keypair(key_dir: Optional[str] = None) -> dict:
    """Load the node's Ed25519 keypair, generating it on first run.

    Returns a dict::

        {
          "signing_key": SigningKey,
          "verify_key":  VerifyKey,
          "public_key_b64":  str,
          "fingerprint":     str,
          "private_key_path": str,
          "public_key_path":  str,
          "generated":       bool,
        }
    """
    global _cached_keypair

    if key_dir is None:
        key_dir = config.NODE_KEY_DIR

    dir_path = _ensure_key_dir(key_dir)
    priv_path = dir_path / _PRIVATE_KEY_FILENAME
    pub_path = dir_path / _PUBLIC_KEY_FILENAME

    if _cached_keypair is not None and _cached_keypair["private_key_path"] == str(priv_path):
        return _cached_keypair

    if priv_path.exists() and pub_path.exists():
        priv_bytes = _pem_unwrap(_PRIVATE_PEM_HEADER, _PRIVATE_PEM_FOOTER, priv_path.read_text())
        pub_bytes = _pem_unwrap(_PUBLIC_PEM_HEADER, _PUBLIC_PEM_FOOTER, pub_path.read_text())
        if len(priv_bytes) != 32 or len(pub_bytes) != 32:
            raise ValueError(
                f"Existing keys at {dir_path} have wrong byte length "
                f"(priv={len(priv_bytes)}, pub={len(pub_bytes)}); expected 32. "
                f"Refusing to overwrite."
            )
        derived_pub = SigningKey(priv_bytes).verify_key.encode()
        if derived_pub != pub_bytes:
            raise ValueError(
                f"Key files at {dir_path} don't match (private doesn't derive "
                f"the saved public). Refusing to overwrite — move them aside."
            )
        sk = SigningKey(priv_bytes)
        generated = False
    elif priv_path.exists() or pub_path.exists():
        raise ValueError(
            f"Asymmetric key state at {dir_path}: only one of the pair exists. "
            f"Refusing to regenerate — move the lone file aside or delete it."
        )
    else:
        sk = SigningKey.generate()
        priv_bytes = sk.encode()
        pub_bytes = sk.verify_key.encode()
        priv_path.write_text(_pem_wrap(_PRIVATE_PEM_HEADER, _PRIVATE_PEM_FOOTER, priv_bytes))
        pub_path.write_text(_pem_wrap(_PUBLIC_PEM_HEADER, _PUBLIC_PEM_FOOTER, pub_bytes))
        try:
            os.chmod(priv_path, 0o600)
        except OSError as exc:
            logger.warning("Could not chmod 600 on %s: %s", priv_path, exc)
        logger.info("Generated new Ed25519 keypair at %s", dir_path)
        generated = True

    vk = sk.verify_key
    out = {
        "signing_key": sk,
        "verify_key": vk,
        "public_key_b64": base64.b64encode(vk.encode()).decode("ascii"),
        "fingerprint": public_key_fingerprint(vk.encode()),
        "private_key_path": str(priv_path),
        "public_key_path": str(pub_path),
        "generated": generated,
    }
    _cached_keypair = out
    return out


def canonical_json(obj: dict) -> bytes:
    """Canonical JSON bytes used as the signing payload.

    - drops `node_signature` if present
    - sorts keys lexicographically
    - no extra whitespace
    - UTF-8, no BOM
    - ensure_ascii=False so non-ASCII handles round-trip cleanly
    """
    payload = {k: v for k, v in obj.items() if k != "node_signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_entry(entry: dict, signing_key: Optional[SigningKey] = None) -> str:
    """Sign a ledger entry and return the base64 signature.

    The caller is responsible for storing the signature back into the
    entry dict under `node_signature` and writing the file.
    """
    if signing_key is None:
        signing_key = load_or_create_keypair()["signing_key"]
    msg = canonical_json(entry)
    sig = signing_key.sign(msg).signature  # 64 bytes
    return base64.b64encode(sig).decode("ascii")


def verify_entry(entry: dict, public_key_b64: str) -> bool:
    """Verify a signed ledger entry against a base64 public key."""
    sig_b64 = entry.get("node_signature")
    if not sig_b64:
        return False
    try:
        sig = base64.b64decode(sig_b64, validate=True)
        pub = base64.b64decode(public_key_b64, validate=True)
        vk = VerifyKey(pub)
        vk.verify(canonical_json(entry), sig)
        return True
    except Exception as exc:
        logger.debug("Signature verification failed: %s", exc)
        return False
