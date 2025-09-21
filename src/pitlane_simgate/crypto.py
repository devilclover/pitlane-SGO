from __future__ import annotations

import json
from pathlib import Path

from nacl import signing

KEY_PATH = Path.home() / ".pitlane" / "simgate_keys.json"


def ensure_keys() -> dict[str, str]:
    if KEY_PATH.exists():
        return json.loads(KEY_PATH.read_text(encoding="utf-8"))
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    sk = signing.SigningKey.generate()
    vk = sk.verify_key
    data = {"ed25519_secret_hex": sk.encode().hex(), "ed25519_public_hex": vk.encode().hex()}
    KEY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def sign_payload(payload: dict, secret_hex: str) -> str:
    sk = signing.SigningKey(bytes.fromhex(secret_hex))
    msg = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    sig = sk.sign(msg).signature.hex()
    return sig
