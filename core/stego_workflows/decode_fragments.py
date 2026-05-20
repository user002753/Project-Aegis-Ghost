"""
Post-steganalysis Shamir recovery pipeline.

Methodology:
1. Run steganalysis per image to prioritize suspicious carriers.
2. Extract embedded payload bytes from candidate images.
3. Parse Shamir shares from supported payload formats.
4. Validate threshold and cryptographic metadata consistency.
5. Reconstruct key via Shamir and decrypt ciphertext.
"""

from __future__ import annotations

import json
import os
import struct
import sys
from typing import Dict, List, Optional, Tuple

from PIL import Image

from core.encryption import load_metadata, reconstruct_and_decrypt
from core.steganalysis import analyze_image
from core.steganography import extract_data_dwt


def _list_images(folder: str) -> List[str]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
    if not os.path.isdir(folder):
        return []
    out = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() in exts:
            out.append(path)
    return sorted(out)


def _is_suspicious(analysis: Dict) -> bool:
    risk = (analysis.get("overall") or {}).get("risk_level", "CLEAN")
    verdict = (analysis.get("overall") or {}).get("verdict", "")
    decoded_found = bool((analysis.get("decoded_payload") or {}).get("found"))
    return risk in {"LOW", "MEDIUM", "HIGH"} or "Hidden Data" in verdict or decoded_found


def _extract_payload_candidates(image_path: str) -> List[bytes]:
    # Try larger windows first so length-prefixed share payloads survive truncation.
    sizes = []
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        cap = max((w * h) // 8, 1024)
        sizes = [min(cap, 65536), min(cap, 32768), min(cap, 16384), min(cap, 8192), 2048]
    except Exception:
        sizes = [65536, 32768, 16384, 8192, 2048]

    tried = set()
    payloads: List[bytes] = []
    for n in sizes:
        if n <= 0 or n in tried:
            continue
        tried.add(n)
        try:
            data = extract_data_dwt(image_path, n)
            if data:
                payloads.append(data)
        except Exception:
            continue
    return payloads


def _try_parse_share_json(payload: bytes) -> Optional[Dict]:
    if len(payload) < 4:
        return None
    try:
        length = struct.unpack(">I", payload[:4])[0]
    except Exception:
        return None
    if length <= 0 or (4 + length) > len(payload):
        return None
    body = payload[4 : 4 + length]
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if "share_index" not in data or "share_hex" not in data:
        return None
    return data


def _share_from_payload(payload: bytes) -> Optional[Tuple[int, bytes, Optional[Tuple[bytes, bytes, bytes]], Optional[int]]]:
    # Format A: length-prefixed JSON share payload (advanced stego).
    share_json = _try_parse_share_json(payload)
    if share_json:
        try:
            idx = int(share_json["share_index"])
            share_bytes = bytes.fromhex(str(share_json["share_hex"]))
            threshold = int(share_json.get("threshold", 0)) or None
            meta = None
            if all(k in share_json for k in ("ciphertext_hex", "nonce_hex", "tag_hex")):
                meta = (
                    bytes.fromhex(share_json["ciphertext_hex"]),
                    bytes.fromhex(share_json["nonce_hex"]),
                    bytes.fromhex(share_json["tag_hex"]),
                )
            if idx <= 0 or not share_bytes:
                return None
            return idx, share_bytes, meta, threshold
        except Exception:
            return None

    # Format B: raw Russian-doll share bytes: [index(1 byte)] + share_bytes.
    if len(payload) >= 17:
        idx = int(payload[0])
        share_bytes = payload[1:17]
        if idx > 0 and len(share_bytes) == 16:
            return idx, share_bytes, None, None

    return None


def recover_shamir_after_steganalysis(
    image_paths: List[str],
    threshold: int = 6,
    metadata_path: Optional[str] = None,
) -> Dict:
    analyses = []
    parsed_shares: Dict[int, bytes] = {}
    metadata_candidates: List[Tuple[bytes, bytes, bytes]] = []
    threshold_candidates: List[int] = []
    extraction_errors: List[str] = []

    for path in image_paths:
        try:
            with open(path, "rb") as f:
                raw = f.read()
            analysis = analyze_image(raw, image_path=path)
            analyses.append({
                "image": path,
                "suspicious": _is_suspicious(analysis),
                "risk_level": (analysis.get("overall") or {}).get("risk_level", "CLEAN"),
                "verdict": (analysis.get("overall") or {}).get("verdict", ""),
                "decode_found": bool((analysis.get("decoded_payload") or {}).get("found")),
            })

            if not _is_suspicious(analysis):
                continue

            for payload in _extract_payload_candidates(path):
                parsed = _share_from_payload(payload)
                if not parsed:
                    continue
                idx, share_bytes, meta, candidate_threshold = parsed
                parsed_shares[idx] = share_bytes
                if meta:
                    metadata_candidates.append(meta)
                if candidate_threshold:
                    threshold_candidates.append(candidate_threshold)
                break
        except Exception as e:
            extraction_errors.append(f"{path}: {e}")

    effective_threshold = threshold
    if threshold_candidates:
        # Use most common embedded threshold if present.
        effective_threshold = max(set(threshold_candidates), key=threshold_candidates.count)

    ciphertext = nonce = tag = None
    if metadata_candidates:
        ciphertext, nonce, tag = max(set(metadata_candidates), key=metadata_candidates.count)
    else:
        # Fallback for classic flow with data/metadata.json.
        try:
            if metadata_path:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
                ciphertext = bytes.fromhex(m["ciphertext"])
                nonce = bytes.fromhex(m["nonce"])
                tag = bytes.fromhex(m["tag"])
            else:
                ciphertext, nonce, tag = load_metadata()
        except Exception:
            pass

    result = {
        "status": "partial",
        "methodology": [
            "steganalysis_filter",
            "payload_extraction",
            "share_parsing",
            "threshold_validation",
            "shamir_reconstruction",
        ],
        "total_images": len(image_paths),
        "analyzed_images": len(analyses),
        "suspicious_images": sum(1 for a in analyses if a["suspicious"]),
        "unique_shares_found": len(parsed_shares),
        "threshold": effective_threshold,
        "analyses": analyses,
        "errors": extraction_errors,
    }

    if len(parsed_shares) < effective_threshold:
        result["reason"] = f"Insufficient shares: found {len(parsed_shares)}, need {effective_threshold}"
        return result

    if not all(v is not None for v in (ciphertext, nonce, tag)):
        result["reason"] = "Shares found, but ciphertext/nonce/tag metadata is missing."
        return result

    selected = sorted(parsed_shares.items(), key=lambda x: x[0])[:effective_threshold]
    try:
        plaintext = reconstruct_and_decrypt(selected, ciphertext, nonce, tag)
        result["status"] = "success"
        result["plaintext"] = plaintext
        result["shares_used"] = len(selected)
        result["share_indices"] = [i for i, _ in selected]
        return result
    except Exception as e:
        result["reason"] = f"Reconstruction failed: {e}"
        return result


def process_fragments_directory(fragments_dir: str = "fragments", threshold: int = 6, metadata_path: Optional[str] = None) -> Dict:
    images = _list_images(fragments_dir)
    if not images:
        return {
            "status": "error",
            "reason": f"No images found in '{fragments_dir}'",
            "plaintext": None,
        }
    return recover_shamir_after_steganalysis(images, threshold=threshold, metadata_path=metadata_path)


def main() -> None:
    fragments_dir = sys.argv[1] if len(sys.argv) > 1 else "fragments"
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    metadata_path = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"Post-steganalysis recovery from: {fragments_dir}")
    print(f"Threshold: {threshold}")
    if metadata_path:
        print(f"Metadata path: {metadata_path}")
    print("-" * 60)

    report = process_fragments_directory(
        fragments_dir=fragments_dir,
        threshold=threshold,
        metadata_path=metadata_path,
    )
    print(json.dumps(report, indent=2))

    if report.get("status") == "success":
        print("-" * 60)
        print("Secret reconstructed successfully.")
    else:
        print("-" * 60)
        print("Recovery incomplete.")


if __name__ == "__main__":
    main()
