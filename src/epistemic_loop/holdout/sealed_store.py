from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SealedScoreStore:
    """Authenticated encryption for final scores; plaintext is never written to disk."""

    FORMAT_VERSION = 1

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_token(token: str) -> None:
        if len(token) < 16:
            raise ValueError("unseal token must contain at least 16 characters")

    @staticmethod
    def _derive_key(token: str, salt: bytes) -> bytes:
        SealedScoreStore.validate_token(token)
        return hashlib.scrypt(token.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)

    def seal(self, score_id: str, payload: dict[str, Any], token: str) -> Path:
        destination = self.root / f"{score_id}.sealed"
        if destination.exists():
            raise FileExistsError(f"sealed score already exists: {score_id}")
        salt = os.urandom(16)
        nonce = os.urandom(12)
        aad = f"erl-sealed-score:{self.FORMAT_VERSION}:{score_id}".encode()
        ciphertext = AESGCM(self._derive_key(token, salt)).encrypt(
            nonce,
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
            aad,
        )
        envelope = {
            "version": self.FORMAT_VERSION,
            "score_id": score_id,
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
        }
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(destination)
        return destination

    def unseal(self, score_id: str, token: str) -> dict[str, Any]:
        source = self.root / f"{score_id}.sealed"
        envelope = json.loads(source.read_text(encoding="utf-8"))
        version = int(envelope["version"])
        aad = f"erl-sealed-score:{version}:{score_id}".encode()
        plaintext = AESGCM(self._derive_key(token, bytes.fromhex(envelope["salt"]))).decrypt(
            bytes.fromhex(envelope["nonce"]),
            bytes.fromhex(envelope["ciphertext"]),
            aad,
        )
        value = json.loads(plaintext)
        if not isinstance(value, dict):
            raise ValueError("sealed score payload must be an object")
        return value

    def status(self, score_id: str) -> dict[str, Any]:
        path = self.root / f"{score_id}.sealed"
        return {"score_id": score_id, "sealed": path.exists(), "path": str(path) if path.exists() else None}
