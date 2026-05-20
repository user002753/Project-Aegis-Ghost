import base64
import hashlib
import json
from typing import Dict, List, Optional, Tuple

from core.encryption import decrypt_aes_gcm
from core.shamir_russian_doll import ShamirSecretSharing


def parse_share(decoded_obj) -> Optional[Dict]:
    if not isinstance(decoded_obj, dict):
        return None
    if "share_index" not in decoded_obj:
        return None
    # Supported share schemas:
    # 1) {"share_index": i, "share": {...}, "threshold": t, ...}
    # 2) {"share_index": i, "share_hex": "...", "ciphertext_hex": "...", ...}
    if "share" in decoded_obj or "share_hex" in decoded_obj:
        return decoded_obj
    return None


def validate_shares(share_objs: List[Dict]) -> Dict:
    unique = {}
    thresholds = []
    for s in share_objs:
        try:
            idx = int(s["share_index"])
            unique[idx] = s
            if "threshold" in s and int(s["threshold"]) > 0:
                thresholds.append(int(s["threshold"]))
            elif isinstance(s.get("share"), dict) and int(s["share"].get("threshold", 0)) > 0:
                thresholds.append(int(s["share"]["threshold"]))
        except Exception:
            continue
    threshold = min(thresholds) if thresholds else len(unique)
    return {
        "shares_by_index": unique,
        "valid_count": len(unique),
        "threshold": threshold,
    }


def reconstruct_secret(share_objs: List[Dict], password: str = "") -> Tuple[Optional[str], str]:
    """
    Returns (plaintext_or_none, mode).
    """
    v = validate_shares(share_objs)
    shares = v["shares_by_index"]
    threshold = v["threshold"]
    if len(shares) < threshold:
        return None, f"insufficient_shares ({len(shares)}/{threshold})"

    selected = [shares[i] for i in sorted(shares.keys())[:threshold]]

    # Path A: classic shamir_stego share objects.
    if "share" in selected[0]:
        sss = ShamirSecretSharing()
        share_payloads = [x["share"] for x in selected]
        encrypted_b64 = sss.reconstruct_secret(share_payloads)
        encrypted = base64.b64decode(encrypted_b64.encode("ascii"), validate=True)

        # Prefer embedded key for no-password recovery.
        key_hex = selected[0].get("decrypt_key_hex")
        if key_hex:
            try:
                pt = decrypt_aes_gcm(encrypted, bytes.fromhex(key_hex)).decode("utf-8")
                return pt, "shamir_stego_embedded_key"
            except Exception:
                pass

        if password:
            key = hashlib.sha256(password.encode("utf-8")).digest()
            pt = decrypt_aes_gcm(encrypted, key).decode("utf-8")
            return pt, "shamir_stego_password"
        return None, "password_required_or_invalid_embedded_key"

    # Path B: advanced shares carry direct ciphertext metadata.
    return None, "advanced_share_path_not_implemented_in_skeleton"

