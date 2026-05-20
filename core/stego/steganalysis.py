"""
Steganalysis Engine for Project Aegis Ghost
============================================
Detects hidden data in images using multiple statistical analysis techniques:
  - Chi-Square Attack (LSB frequency analysis)
  - RS (Regular-Singular) Analysis
  - Histogram Analysis (pixel value distribution anomalies)
  - Noise Level Estimation (DWT-based)
  - Sample Pair Analysis
  - Bit-Plane Analysis
"""

import numpy as np
from PIL import Image
import pywt
import io
import math
import os
import struct
import string
import base64
import binascii
import gzip
import zlib
from typing import Dict, Any, Tuple, Optional
from core.steganography import extract_data_dwt

# PyTorch imports for neural network steganalysis
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torchvision import transforms
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None
    F = None
    torch = None

try:
    from scipy.stats import chi2 as _SCIPY_CHI2, chisquare
except Exception:
    _SCIPY_CHI2 = None


# ---------------------------------------------------------------------------
# StegNet CNN Model for Steganalysis
# ----------------------------------------------------------------------------

# Type hints (work regardless of whether PyTorch is available)
if TORCH_AVAILABLE:
    class StegNet(nn.Module):
        """CNN-based steganalysis model for detecting hidden data in images."""
        
        def __init__(self, num_classes: int = 5):
            super().__init__()
            self.block1 = nn.Sequential(
                nn.Conv2d(3, 6, 3, padding=1),
                nn.ReLU(),
                nn.MaxPool2d(2, 2),
            )
            self.conv2 = nn.Conv2d(6, 16, 3, padding=1)
            self.relu = nn.ReLU()
            self.pool = nn.MaxPool2d(2, 2)
            self.fc1 = nn.Linear(16 * 64 * 64, 256)  # After 2 pooling layers from 256x256
            self.fc2 = nn.Linear(256, num_classes)
            self.dropout = nn.Dropout(0.5)
            self.softmax = nn.Softmax(dim=1)

        def forward(self, x):
            x = self.block1(x)
            x = self.relu(self.conv2(x))
            x = self.pool(x)
            x = torch.flatten(x, 1)
            x = self.relu(self.fc1(x))
            x = self.dropout(x)
            x = self.softmax(self.fc2(x))
            return x
    
    # ImageNet normalization for pretrained models
    IMAGENET_MEAN = [0.485, 0.456, 0.406]
    IMAGENET_STD = [0.229, 0.224, 0.225]
    
    # Class labels for steganalysis
    STEG_CLASSES = ['JMiPOD', 'JUNIWARD', 'MLStego', 'Normal', 'UERD']


# Use Any type when PyTorch is not available
ModelType = Any if not TORCH_AVAILABLE else Any


def _load_stegnet_model(model_path: Optional[str] = None) -> ModelType:
    """Load or create StegNet model."""
    if not TORCH_AVAILABLE:
        return None
    
    try:
        model = StegNet(num_classes=5)
        
        # Try to load pretrained weights if available
        if model_path and os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path, map_location='cpu'))
        else:
            # Initialize with random weights
            pass
            
        model.eval()
        return model
    except Exception as e:
        print(f"Warning: Could not load StegNet model: {e}")
        return None


def neural_network_steganalysis(image_bytes: bytes, model_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Perform neural network-based steganalysis on an image.
    
    Args:
        image_bytes: Raw image bytes
        model_path: Optional path to pretrained model weights
        
    Returns:
        Dictionary with detection results
    """
    if not TORCH_AVAILABLE:
        return {
            "method": "Neural Network (CNN)",
            "success": False,
            "error": "PyTorch not available",
            "verdict": "Unknown",
            "confidence": 0.0,
        }
    
    try:
        # Load model
        model = _load_stegnet_model(model_path)
        if model is None:
            return {
                "method": "Neural Network (CNN)",
                "success": False,
                "error": "Could not load model",
                "verdict": "Unknown",
                "confidence": 0.0,
            }
        
        # Load and preprocess image
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        
        # Transform for model (resize to 256x256)
        transform = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
        ])
        
        img_tensor = transform(img).unsqueeze(0)
        
        # Inference
        with torch.no_grad():
            outputs = model(img_tensor)
            probabilities = outputs[0]
            predicted_class = torch.argmax(probabilities).item()
            confidence = probabilities[predicted_class].item()
        
        # Determine verdict based on prediction
        predicted_label = STEG_CLASSES[predicted_class]
        
        # If model predicts 'Normal', likely no hidden data
        # Otherwise, hidden data may be present
        if predicted_label == 'Normal':
            verdict = "No Hidden Data (Neural Network)"
            confidence_score = confidence * 100
        else:
            verdict = f"Hidden Data Detected ({predicted_label})"
            confidence_score = confidence * 100
        
        # Get all class probabilities
        class_probs = {}
        for i, cls in enumerate(STEG_CLASSES):
            class_probs[cls] = round(probabilities[i].item() * 100, 2)
        
        return {
            "method": "Neural Network (CNN)",
            "success": True,
            "verdict": verdict,
            "confidence": round(confidence_score, 2),
            "predicted_class": predicted_label,
            "class_probabilities": class_probs,
            "description": (
                "CNN-based steganalysis using StegNet. "
                "Detects whether image contains hidden data and identifies "
                "the steganography method used (JMiPOD, JUNIWARD, MLStego, UERD)."
            ),
        }
        
    except Exception as e:
        return {
            "method": "Neural Network (CNN)",
            "success": False,
            "error": str(e),
            "verdict": "Error",
            "confidence": 0.0,
        }


# ---------------------------------------------------------------------------
# Chi-square survival function (no scipy required)
# ---------------------------------------------------------------------------

def _chi2_sf(chi2_stat: float, dof: int) -> float:
    """
    Survival function P(X > chi2_stat) for chi-square distribution with `dof`
    degrees of freedom.  Uses scipy when available; falls back to a numerical
    approximation via the regularised incomplete gamma function.
    """
    if chi2_stat <= 0:
        return 1.0
    if _SCIPY_CHI2 is not None:
        return float(1.0 - _SCIPY_CHI2.cdf(chi2_stat, df=dof))
    k = dof / 2.0
    x = chi2_stat / 2.0
    if x < k + 1.0:
        # Series expansion for lower incomplete gamma
        ap = k
        delta = 1.0 / k
        total = delta
        for _ in range(200):
            ap += 1.0
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * 1e-10:
                break
        lower = total * math.exp(-x + k * math.log(x) - math.lgamma(k))
        return max(0.0, min(1.0, 1.0 - lower))
    else:
        # Continued fraction for upper incomplete gamma (Lentz method)
        b = x + 1.0 - k
        c = 1.0 / 1e-30
        d = 1.0 / b
        h = d
        for i in range(1, 201):
            an = -i * (i - k)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            delta = d * c
            h *= delta
            if abs(delta - 1.0) < 1e-10:
                break
        upper = math.exp(-x + k * math.log(x) - math.lgamma(k)) * h
        return max(0.0, min(1.0, upper))


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _load_image_array(image_bytes: bytes) -> np.ndarray:
    """Load image bytes into a uint8 numpy array (RGB)."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return np.array(img, dtype=np.uint8)


def _channel_name(idx: int) -> str:
    return ["Red", "Green", "Blue"][idx]

def _parse_length_header(length_bytes: bytes, max_payload: int, max_size: int, available_bits: int) -> int:
    """
    Parse a 32-bit payload length from either endian format and pick a valid value.
    Russian-doll helpers in this codebase may emit host-order uint32 headers, so we
    accept both little- and big-endian during extraction for compatibility.
    """
    candidates = []
    for fmt in (">I", "<I"):
        n = struct.unpack(fmt, length_bytes)[0]
        if n <= 0:
            continue
        if n > max_payload or n > max_size:
            continue
        if n * 8 > available_bits:
            continue
        candidates.append(n)

    if not candidates:
        raise ValueError("Invalid or out-of-range payload length")

    # If both are valid, prefer the smaller practical value.
    return min(candidates)

def _extract_blue_lsb_length_prefixed(img_arr: np.ndarray, max_payload: int = 65536) -> bytes:
    """
    Extract [4-byte big-endian length][payload] from blue-channel LSBs.
    """
    blue = img_arr[:, :, 2].reshape(-1).astype(np.uint8, copy=False)
    if blue.size < 32:
        raise ValueError("Image too small for payload header")

    header_bits = (blue[:32] & 1).astype(np.uint8)
    header = np.packbits(header_bits).tobytes()
    n = _parse_length_header(
        header,
        max_payload=max_payload,
        max_size=blue.size // 8,
        available_bits=max(blue.size - 32, 0),
    )
    total_bits = (4 + n) * 8

    bits = (blue[:total_bits] & 1).astype(np.uint8)
    packed = np.packbits(bits).tobytes()
    return packed[4:4 + n]


def _extract_rgb_lsb_stream(img_arr: np.ndarray, max_bytes: int = 8192) -> bytes:
    """
    Extract a raw LSB byte stream from flattened RGB channels (best-effort).
    """
    flat = img_arr.reshape(-1).astype(np.uint8, copy=False)
    n_bits = min(flat.size, max_bytes * 8)
    bits = (flat[:n_bits] & 1).astype(np.uint8)
    return np.packbits(bits).tobytes()


def _extract_russian_doll_dwt(img_arr: np.ndarray, max_payload: int = 65536) -> bytes:
    """
    Extract data from Russian Doll DWT layer (blue channel LSBs).
    This matches the embedding format in steganography_russian_doll.py.
    """
    flat = img_arr[:, :, 2].flatten()
    
    # Extract length from first 32 bits (big-endian to match embedding)
    length_bits = []
    for i in range(32):
        if i >= len(flat):
            break
        length_bits.append(flat[i] & 1)
    
    # Decode length from either endian format for compatibility.
    length_packed = np.packbits(np.array(length_bits, dtype=np.uint8)).tobytes()
    max_size = len(flat) // 8
    length = _parse_length_header(
        length_packed,
        max_payload=max_payload,
        max_size=max_size,
        available_bits=max(len(flat) - 32, 0),
    )
    
    # Extract data
    data_bits = []
    for i in range(32, min(32 + length * 8, len(flat))):
        data_bits.append(flat[i] & 1)
    
    return np.packbits(np.array(data_bits, dtype=np.uint8)).tobytes()


def _extract_russian_doll_lsb(img_arr: np.ndarray, max_payload: int = 65536) -> bytes:
    """
    Extract data from Russian Doll LSB layer (all channels).
    """
    flat = img_arr.reshape(-1).astype(np.uint8, copy=False)
    
    # Decode length from either endian format for compatibility.
    length_bits = (flat[:32] & 1).astype(np.uint8)
    length_bytes = np.packbits(length_bits).tobytes()
    n = _parse_length_header(
        length_bytes,
        max_payload=max_payload,
        max_size=flat.size // 8,
        available_bits=max(flat.size - 32, 0),
    )
    total_bits = (4 + n) * 8

    bits = (flat[:total_bits] & 1).astype(np.uint8)
    packed = np.packbits(bits).tobytes()
    return packed[4:4 + n]


def _decode_binary_payload(data: bytes, min_len: int = 4) -> Dict[str, Any]:
    """
    Decode bytes as potential encrypted payload.
    Returns information about the binary data without requiring valid text.
    Now supports hex-encoded payloads from Russian Doll steganography.
    """
    if not data or len(data) < min_len:
        return {"ok": False, "reason": "too_short"}
    
    # Check for common encrypted data patterns first
    entropy = 0.0
    byte_freq = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256) / len(data)
    entropy = float(-np.sum(byte_freq[byte_freq > 0] * np.log2(byte_freq[byte_freq > 0])))
    
    # High entropy suggests encrypted/compressed data
    is_likely_encrypted = entropy > 7.0
    
    # Check 1: Is this a valid hex string? (Russian Doll format)
    try:
        # Check raw bytes for hex pattern - use bytes.hex() method directly
        hex_str = data.hex() if isinstance(data, bytes) else data.hex()
        if all(c in '0123456789abcdefABCDEF' for c in hex_str.strip()) and len(hex_str) >= 8:
            # Valid hex string - likely Russian Doll encrypted data
            return {
                "ok": True,
                "is_binary": True,
                "is_hex_encoded": True,
                "hex_data": hex_str,
                "decoded_bytes_length": len(data),
                "entropy": round(entropy, 4),
                "bytes_decoded": len(data),
                "hex_preview": hex_str[:64],
                "format": "hex_encoded_russian_doll"
            }
    except Exception:
        pass
    
    # Try to decode as text for fallback
    text_result = _decode_text_candidate(data, min_len=min_len)
    
    return {
        "ok": True,
        "is_binary": True,
        "is_likely_encrypted": is_likely_encrypted,
        "entropy": round(entropy, 4),
        "bytes_decoded": len(data),
        "hex_preview": data[:64].hex() if len(data) > 0 else "",
        "text_attempt": text_result.get("ok", False),
    }


def _sanitize_text(text: str, max_len: int = 4000) -> str:
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch in string.printable)
    return cleaned.strip("\x00 \t\r\n")[:max_len]


def _trim_payload_data(data: bytes, min_run: int = 8) -> bytes:
    """
    Trim extraction noise from payload bytes.
    Prefer content before long NUL-runs commonly produced when extracting beyond payload.
    """
    if not data:
        return data
    for run in (b"\x00" * 16, b"\x00" * 8):
        idx = data.find(run)
        if idx >= min_run:
            return data[:idx]
    return data.rstrip(b"\x00")


def _decode_text_candidate(data: bytes, min_len: int = 6) -> Dict[str, Any]:
    """
    Try to decode bytes as likely text and return a confidence score.
    """
    if not data:
        return {"ok": False, "reason": "empty"}

    best_text = ""
    best_encoding = ""
    for encoding in ("utf-8", "utf-16"):
        try:
            txt = data.decode(encoding, errors="strict")
            txt = _sanitize_text(txt)
            if len(txt) > len(best_text):
                best_text = txt
                best_encoding = encoding
        except Exception:
            continue

    if len(best_text) < min_len:
        return {"ok": False, "reason": "too_short"}

    printable = sum(1 for c in best_text if c in string.printable)
    ratio = printable / max(len(best_text), 1)
    letters = sum(1 for c in best_text if c.isalpha())
    alnum = sum(1 for c in best_text if c.isalnum())
    token_symbols = sum(1 for c in best_text if c in "_-:./|@#")
    spaces = sum(1 for c in best_text if c.isspace())
    letter_ratio = letters / max(len(best_text), 1)
    alnum_ratio = alnum / max(len(best_text), 1)
    token_symbol_ratio = token_symbols / max(len(best_text), 1)
    space_ratio = spaces / max(len(best_text), 1)

    looks_json = best_text.startswith("{") and best_text.endswith("}")
    looks_sentence = letter_ratio >= 0.45 and space_ratio >= 0.05
    looks_token = ratio >= 0.95 and alnum_ratio >= 0.5 and token_symbol_ratio <= 0.4
    if not (looks_json or looks_sentence or looks_token):
        return {
            "ok": False,
            "reason": "text_not_meaningful",
            "printable_ratio": round(ratio, 3),
            "letter_ratio": round(letter_ratio, 3),
            "alnum_ratio": round(alnum_ratio, 3),
            "token_symbol_ratio": round(token_symbol_ratio, 3),
            "space_ratio": round(space_ratio, 3),
        }

    score = min(max(((ratio * 0.4) + (letter_ratio * 0.5) + (space_ratio * 0.1)) * 100.0, 0.0), 100.0)

    return {
        "ok": True,
        "text": best_text,
        "encoding": best_encoding or "unknown",
        "score": round(score, 2),
        "bytes_decoded": len(data),
    }


def _decode_base64_text(data: bytes) -> Dict[str, Any]:
    """
    Decode base64 payloads and then decode resulting bytes as text.
    """
    if not data:
        return {"ok": False, "reason": "empty"}
    candidate = data.strip().replace(b"\n", b"").replace(b"\r", b"")
    if len(candidate) < 12:
        return {"ok": False, "reason": "too_short"}
    try:
        decoded_bytes = base64.b64decode(candidate, validate=True)
    except Exception:
        return {"ok": False, "reason": "invalid_base64"}
    decoded = _decode_text_candidate(_trim_payload_data(decoded_bytes), min_len=4)
    if not decoded.get("ok"):
        return {"ok": False, "reason": "base64_not_text"}
    decoded["encoding"] = f"base64->{decoded.get('encoding', 'utf-8')}"
    decoded["score"] = min(float(decoded.get("score", 0.0)) + 8.0, 100.0)
    return decoded


def _looks_base64_payload(data: bytes) -> bool:
    candidate = data.strip().replace(b"\n", b"").replace(b"\r", b"")
    if len(candidate) < 12 or (len(candidate) % 4) != 0:
        return False
    allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    return all(ch in allowed for ch in candidate)


def _decode_hex_text(data: bytes) -> Dict[str, Any]:
    """
    Decode hex-encoded payloads and then decode resulting bytes as text.
    """
    if not data:
        return {"ok": False, "reason": "empty"}
    candidate = data.strip()
    try:
        txt = candidate.decode("ascii")
    except Exception:
        return {"ok": False, "reason": "non_ascii"}
    txt = txt.strip()
    if len(txt) < 8 or len(txt) % 2 != 0:
        return {"ok": False, "reason": "invalid_len"}
    if any(ch not in string.hexdigits for ch in txt):
        return {"ok": False, "reason": "invalid_hex"}
    try:
        decoded_bytes = binascii.unhexlify(txt)
    except Exception:
        return {"ok": False, "reason": "unhex_failed"}
    decoded = _decode_text_candidate(_trim_payload_data(decoded_bytes), min_len=4)
    if not decoded.get("ok"):
        return {"ok": False, "reason": "hex_not_text"}
    decoded["encoding"] = f"hex->{decoded.get('encoding', 'utf-8')}"
    decoded["score"] = min(float(decoded.get("score", 0.0)) + 8.0, 100.0)
    return decoded


def _looks_hex_payload(data: bytes) -> bool:
    candidate = data.strip()
    if len(candidate) < 8 or (len(candidate) % 2) != 0:
        return False
    try:
        text = candidate.decode("ascii")
    except Exception:
        return False
    return all(ch in string.hexdigits for ch in text)


def _decode_compressed_text(data: bytes) -> Dict[str, Any]:
    """
    Decode zlib/gzip compressed payloads and then decode resulting bytes as text.
    """
    if not data:
        return {"ok": False, "reason": "empty"}
    for name, fn in (("zlib", zlib.decompress), ("gzip", gzip.decompress)):
        try:
            unpacked = fn(data)
        except Exception:
            continue
        decoded = _decode_text_candidate(_trim_payload_data(unpacked), min_len=4)
        if decoded.get("ok"):
            decoded["encoding"] = f"{name}->{decoded.get('encoding', 'utf-8')}"
            decoded["score"] = min(float(decoded.get("score", 0.0)) + 10.0, 100.0)
            return decoded
    return {"ok": False, "reason": "not_compressed_text"}


def _extract_printable_runs(data: bytes, min_run: int = 8) -> str:
    """
    Extract the longest contiguous run of mostly printable ASCII bytes.
    Useful for payloads that include binary headers followed by text.
    """
    best = b""
    cur = bytearray()
    for b in data:
        if b in (9, 10, 13) or 32 <= b <= 126:
            cur.append(b)
        else:
            if len(cur) > len(best):
                best = bytes(cur)
            cur.clear()
    if len(cur) > len(best):
        best = bytes(cur)
    if len(best) < min_run:
        return ""
    return _sanitize_text(best.decode("utf-8", errors="ignore"))


def _decode_length_prefixed_text(data: bytes) -> Dict[str, Any]:
    """
    Decode payloads that begin with a 4-byte length prefix followed by text/JSON.
    Accepts big/little-endian headers for compatibility.
    """
    if len(data) < 8:
        return {"ok": False, "reason": "too_short"}

    for fmt in (">I", "<I"):
        try:
            n = struct.unpack(fmt, data[:4])[0]
        except Exception:
            continue
        if n <= 0 or n > len(data) - 4:
            continue
        body = data[4:4 + n]
        decoded = _decode_text_candidate(body, min_len=4)
        if decoded.get("ok"):
            return decoded
        # If strict text decode fails, try printable run extraction.
        run = _extract_printable_runs(body, min_run=8)
        if run:
            return {
                "ok": True,
                "text": run,
                "encoding": "utf-8/printable-run",
                "score": 65.0,
                "bytes_decoded": len(body),
            }
    return {"ok": False, "reason": "invalid_length_prefix"}


def _decode_payload_text_fallback(data: bytes) -> Dict[str, Any]:
    """
    Multi-strategy text decode for mixed binary payloads.
    """
    data = _trim_payload_data(data)

    # 1) Encoded-text first when payload strongly matches an encoded form.
    if _looks_base64_payload(data):
        b64 = _decode_base64_text(data)
        if b64.get("ok"):
            return b64

    if _looks_hex_payload(data):
        hx = _decode_hex_text(data)
        if hx.get("ok"):
            return hx

    # 2) Direct decode.
    direct = _decode_text_candidate(data, min_len=4)
    if direct.get("ok"):
        return direct

    # 3) Length-prefixed text (common in this project).
    lp = _decode_length_prefixed_text(data)
    if lp.get("ok"):
        return lp

    # 4) Base64-encoded text payload.
    b64 = _decode_base64_text(data)
    if b64.get("ok"):
        return b64

    # 5) Hex-encoded text payload.
    hx = _decode_hex_text(data)
    if hx.get("ok"):
        return hx

    # 6) Compressed text payload (zlib/gzip).
    comp = _decode_compressed_text(data)
    if comp.get("ok"):
        return comp

    # 7) JSON-like slice inside binary payload.
    try:
        start = data.find(b"{")
        end = data.rfind(b"}")
        if 0 <= start < end:
            maybe_json = data[start:end + 1]
            js = _decode_text_candidate(maybe_json, min_len=4)
            if js.get("ok"):
                return js
    except Exception:
        pass

    # 8) Long printable run fallback.
    run = _extract_printable_runs(data, min_run=8)
    if run:
        return {
            "ok": True,
            "text": run,
            "encoding": "utf-8/printable-run",
            "score": 55.0,
            "bytes_decoded": len(data),
        }

    return {"ok": False, "reason": "no_text_candidate"}


def decode_hidden_data(image_bytes: bytes, img_arr: np.ndarray, image_path: str | None = None) -> Dict[str, Any]:
    """
    Attempt to decode hidden payloads using known embedding schemes + best-effort LSB decoding.
    Now includes support for Russian Doll steganography format and coefficient files.
    """
    attempts = []

    if image_path:
        # Try to extract from coefficient file first (common in this system)
        try:
            coeff_path = image_path.replace('.png', '_coeff.npy')

            if os.path.exists(coeff_path):
                hh = np.load(coeff_path)
                # Extract LSBs from HH coefficients
                hh_flat = hh.flatten()
                bits_list = []
                for i in range(min(len(hh_flat), 16384 * 8)):  # Max 16KB
                    val = hh_flat[i]
                    lsb = int(np.round(val)) % 2
                    bits_list.append(lsb)

                bits_array = np.array(bits_list, dtype=np.uint8)
                dwt_bytes = np.packbits(bits_array).tobytes()
                dwt_decoded = _decode_binary_payload(dwt_bytes)
                attempts.append({
                    "method": "DWT Coefficient Extract",
                    "success": bool(dwt_decoded.get("ok")),
                    "details": dwt_decoded,
                })
                dwt_text = _decode_payload_text_fallback(dwt_bytes)
                if dwt_text.get("ok"):
                    attempts.append({
                        "method": "DWT Coefficient Extract as Text",
                        "success": True,
                        "details": dwt_text,
                    })
            else:
                # Try sidecar file
                sidecar_path = f"{image_path}.steg.bin"
                if os.path.exists(sidecar_path):
                    h, w = img_arr.shape[:2]
                    hh_capacity_bytes = max((h // 2) * (w // 2) // 8, 64)
                    dwt_bytes = extract_data_dwt(image_path, min(hh_capacity_bytes, 16384))
                    dwt_decoded = _decode_binary_payload(dwt_bytes)
                    attempts.append({
                        "method": "DWT/Sidecar Extract",
                        "success": bool(dwt_decoded.get("ok")),
                        "details": dwt_decoded,
                    })
                    dwt_text = _decode_payload_text_fallback(dwt_bytes)
                    if dwt_text.get("ok"):
                        attempts.append({
                            "method": "DWT/Sidecar Extract as Text",
                            "success": True,
                            "details": dwt_text,
                        })
                else:
                    attempts.append({
                        "method": "DWT Coefficient/Sidecar Extract",
                        "success": False,
                        "error": f"No coefficient or sidecar file found at {image_path}",
                    })
        except Exception as e:
            attempts.append({
                "method": "DWT Coefficient Extract",
                "success": False,
                "error": str(e),
            })

        # Legacy/fallback path: try direct DWT extraction from the image bytes
        # with common payload sizes, then decode to best text candidate.
        try:
            candidate_sizes = [32, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048]
            best_text = None
            best_size = None
            best_score = -1.0
            for n in candidate_sizes:
                try:
                    raw = extract_data_dwt(image_path, n)
                except Exception:
                    continue
                txt = _decode_payload_text_fallback(raw)
                if txt.get("ok"):
                    score = float(txt.get("score", 0.0))
                    # Prefer higher text score; tie-break by longer decoded text.
                    if score > best_score or (
                        abs(score - best_score) < 1e-9
                        and len(txt.get("text", "")) > len((best_text or {}).get("text", ""))
                    ):
                        best_text = txt
                        best_size = n
                        best_score = score

            if best_text and best_text.get("ok"):
                attempts.append({
                    "method": f"DWT Direct Fallback as Text ({best_size} bytes)",
                    "success": True,
                    "details": best_text,
                })
            else:
                attempts.append({
                    "method": "DWT Direct Fallback as Text",
                    "success": False,
                    "error": "No readable text candidate found",
                })
        except Exception as e:
            attempts.append({
                "method": "DWT Direct Fallback as Text",
                "success": False,
                "error": str(e),
            })

    # Try Russian Doll DWT extraction (blue channel only)
    try:
        payload = _extract_russian_doll_dwt(img_arr)
        decoded = _decode_binary_payload(payload)
        attempts.append({
            "method": "Russian Doll DWT (Blue-LSB)",
            "success": bool(decoded.get("ok")),
            "details": decoded,
        })
        # Also try text decoding as fallback
        text_decoded = _decode_payload_text_fallback(payload)
        if text_decoded.get("ok"):
            attempts.append({
                "method": "Russian Doll DWT (Blue-LSB) as Text",
                "success": True,
                "details": text_decoded,
            })
    except Exception as e:
        attempts.append({
            "method": "Russian Doll DWT (Blue-LSB)",
            "success": False,
            "error": str(e),
        })

    # Try Russian Doll LSB extraction (all channels)
    try:
        payload = _extract_russian_doll_lsb(img_arr)
        decoded = _decode_binary_payload(payload)
        attempts.append({
            "method": "Russian Doll LSB (All Channels)",
            "success": bool(decoded.get("ok")),
            "details": decoded,
        })
        # Also try text decoding as fallback
        text_decoded = _decode_payload_text_fallback(payload)
        if text_decoded.get("ok"):
            attempts.append({
                "method": "Russian Doll LSB as Text",
                "success": True,
                "details": text_decoded,
            })
    except Exception as e:
        attempts.append({
            "method": "Russian Doll LSB (All Channels)",
            "success": False,
            "error": str(e),
        })

    try:
        payload = _extract_blue_lsb_length_prefixed(img_arr)
        decoded = _decode_binary_payload(payload)
        attempts.append({
            "method": "Blue-LSB Length-Prefixed",
            "success": bool(decoded.get("ok")),
            "details": decoded,
        })
    except Exception as e:
        attempts.append({
            "method": "Blue-LSB Length-Prefixed",
            "success": False,
            "error": str(e),
        })

    try:
        raw = _extract_rgb_lsb_stream(img_arr)
        decoded = _decode_binary_payload(raw)
        attempts.append({
            "method": "Raw RGB-LSB Stream",
            "success": bool(decoded.get("ok")),
            "details": decoded,
        })
    except Exception as e:
        attempts.append({
            "method": "Raw RGB-LSB Stream",
            "success": False,
            "error": str(e),
        })

    # Look for successful binary or text extraction
    successful = [a for a in attempts if a.get("success") and a.get("details", {}).get("ok")]
    
    if successful:
        # Prefer text results if available (more useful for users)
        text_successful = [a for a in successful if "Text" in a.get("method", "")]
        if text_successful:
            best = max(text_successful, key=lambda a: (a["details"].get("score", 0.0), len(a["details"].get("text", ""))))
            return {
                "found": True,
                "method": best["method"],
                "confidence": best["details"].get("score", 80.0),
                "encoding": best["details"].get("encoding", "unknown"),
                "decoded_text": best["details"].get("text", ""),
                "bytes_decoded": best["details"].get("bytes_decoded", 0),
                "is_binary": best["details"].get("is_binary", False),
                "is_likely_encrypted": best["details"].get("is_likely_encrypted", False),
                "entropy": best["details"].get("entropy", 0.0),
                "hex_preview": best["details"].get("hex_preview", ""),
                "pipeline": {
                    "stages": ["detect", "extract", "decode"],
                    "selected_attempt": best["method"],
                    "decode_strategy": best["details"].get("encoding", "unknown"),
                    "attempt_count": len(attempts),
                },
                "attempts": attempts,
            }
        
        # Otherwise return binary result
        best = max(successful, key=lambda a: a["details"].get("entropy", 0.0))
        # Use hex_preview as decoded_text when binary data is found
        binary_text = best["details"].get("hex_preview", "") or best["details"].get("hex_data", "")
        entropy_val = best["details"].get("entropy", 0.0)
        is_encrypted = best["details"].get("is_likely_encrypted", False)
        
        # Format output with clear indication that this is encrypted data
        if is_encrypted and entropy_val > 7.0:
            output_text = f"[ENCRYPTED DATA - {best['details'].get('bytes_decoded', 0)} bytes, entropy: {entropy_val:.2f}]\n\nHex: {binary_text[:128]}{'...' if len(binary_text) > 128 else ''}\n\nNote: This appears to be Russian Doll encrypted. Use Advanced mode with {best['details'].get('bytes_decoded', 0) // 32 + 1} or more images and correct passwords to decrypt."
        else:
            output_text = binary_text if binary_text else f"[Binary data: {best['details'].get('bytes_decoded', 0)} bytes, entropy: {entropy_val:.2f}]"
        
        return {
            "found": True,
            "method": best["method"],
            "confidence": 75.0,
            "encoding": "binary",
            "decoded_text": output_text,
            "bytes_decoded": best["details"].get("bytes_decoded", 0),
            "is_binary": True,
            "is_likely_encrypted": is_encrypted,
            "entropy": entropy_val,
            "hex_preview": best["details"].get("hex_preview", ""),
            "pipeline": {
                "stages": ["detect", "extract", "decode"],
                "selected_attempt": best["method"],
                "decode_strategy": "binary_only",
                "attempt_count": len(attempts),
            },
            "attempts": attempts,
        }

    return {
        "found": False,
        "method": None,
        "confidence": 0.0,
        "decoded_text": "[No hidden data found in image]",
        "bytes_decoded": 0,
        "pipeline": {
            "stages": ["detect", "extract", "decode"],
            "selected_attempt": None,
            "decode_strategy": None,
            "attempt_count": len(attempts),
        },
        "attempts": attempts,
    }


# ---------------------------------------------------------------------------
# 1. Chi-Square Attack
# ---------------------------------------------------------------------------

def chi_square_attack(img_arr: np.ndarray) -> Dict[str, Any]:
    """
    Chi-square test on LSB pairs.
    Compares observed frequencies of value pairs (2k, 2k+1) against the
    expected uniform distribution under the null hypothesis of random LSB
    embedding.  A low p-value (<0.05) indicates steganography.
    """
    results = {}
    p_values = []

    for c in range(3):
        channel = img_arr[:, :, c].flatten().astype(np.int32)
        hist, _ = np.histogram(channel, bins=256, range=(0, 255))

        even = hist[0::2].astype(np.float64)
        odd = hist[1::2].astype(np.float64)
        pair_sum = even + odd
        valid = pair_sum > 0

        if np.any(valid):
            expected = pair_sum[valid] / 2.0
            chi2_stat = float(
                np.sum(
                    ((even[valid] - expected) ** 2) / expected
                    + ((odd[valid] - expected) ** 2) / expected
                )
            )
            valid_pairs = int(np.count_nonzero(valid))
        else:
            chi2_stat = 0.0
            valid_pairs = 0

        dof = max(valid_pairs - 1, 1)
        p_val = _chi2_sf(chi2_stat, dof)
        p_values.append(float(p_val))
        results[_channel_name(c)] = {
            "chi2_statistic": round(float(chi2_stat), 4),
            "p_value": round(float(p_val), 6),
            "dof": dof,
        }

    overall_p = float(np.mean(p_values))
    verdict = "Suspicious" if overall_p < 0.05 else "Clean"

    return {
        "method": "Chi-Square Attack",
        "channels": results,
        "overall_p_value": round(overall_p, 6),
        "verdict": verdict,
        "confidence": round((1.0 - overall_p) * 100, 2),
        "description": (
            "Chi-square test compares LSB pair frequencies. "
            "A low p-value (<0.05) indicates non-random LSB distribution, "
            "suggesting hidden data."
        ),
    }


# ---------------------------------------------------------------------------
# 2. RS Analysis
# ---------------------------------------------------------------------------

def _rs_discriminant(group: np.ndarray) -> float:
    return float(np.sum(np.abs(np.diff(group.astype(np.int32)))))


def _flip_lsb(pixels: np.ndarray, mask: np.ndarray) -> np.ndarray:
    flipped = pixels.copy()
    flipped[mask == 1] ^= 1
    return flipped


def _rs_groups(channel: np.ndarray, group_size: int = 4) -> Tuple[float, float, float, float]:
    flat = channel.flatten()
    n = len(flat)
    n_groups = n // group_size
    if n_groups == 0:
        return 0.0, 0.0, 0.0, 0.0

    groups = flat[: n_groups * group_size].reshape(-1, group_size).astype(np.uint8, copy=False)
    mask = np.zeros(group_size, dtype=bool)
    mask[1::2] = True

    groups_i = groups.astype(np.int16, copy=False)
    f0 = np.sum(np.abs(np.diff(groups_i, axis=1)), axis=1)

    flipped = groups.copy()
    flipped[:, mask] ^= 1
    flipped_i = flipped.astype(np.int16, copy=False)
    f1 = np.sum(np.abs(np.diff(flipped_i, axis=1)), axis=1)

    neg_groups = groups_i.copy()
    neg_groups[:, mask] -= 1
    np.clip(neg_groups, 0, 255, out=neg_groups)
    f0n = np.sum(np.abs(np.diff(neg_groups, axis=1)), axis=1)

    neg_flipped = neg_groups.astype(np.uint8, copy=True)
    neg_flipped[:, mask] ^= 1
    neg_flipped_i = neg_flipped.astype(np.int16, copy=False)
    f1n = np.sum(np.abs(np.diff(neg_flipped_i, axis=1)), axis=1)

    total = float(n_groups)
    R = float(np.count_nonzero(f1 > f0)) / total
    S = float(np.count_nonzero(f1 < f0)) / total
    R_neg = float(np.count_nonzero(f1n > f0n)) / total
    S_neg = float(np.count_nonzero(f1n < f0n)) / total
    return R, S, R_neg, S_neg


def rs_analysis(img_arr: np.ndarray) -> Dict[str, Any]:
    """
    RS (Regular-Singular) steganalysis.
    Estimates the fraction of pixels carrying hidden data.
    """
    results = {}
    payloads = []

    for c in range(3):
        channel = img_arr[:, :, c]
        R, S, R_neg, S_neg = _rs_groups(channel)

        d0 = R - S
        d1 = R_neg - S_neg
        a = 2.0 * (d1 + d0)
        b = -(d1 + 3.0 * d0)
        c_coef = 2.0 * d0

        discriminant = b ** 2 - 4.0 * a * c_coef
        if abs(a) < 1e-10 or discriminant < 0:
            payload = 0.0
        else:
            sqrt_disc = np.sqrt(discriminant)
            p1 = (-b + sqrt_disc) / (2.0 * a)
            p2 = (-b - sqrt_disc) / (2.0 * a)
            candidates = [p for p in [p1, p2] if 0.0 <= p <= 1.0]
            payload = float(min(candidates)) if candidates else 0.0

        payloads.append(payload)
        results[_channel_name(c)] = {
            "R": round(R, 4),
            "S": round(S, 4),
            "R_neg": round(R_neg, 4),
            "S_neg": round(S_neg, 4),
            "estimated_payload": round(payload, 4),
        }

    avg_payload = float(np.mean(payloads))
    verdict = "Suspicious" if avg_payload > 0.05 else "Clean"

    return {
        "method": "RS Analysis",
        "channels": results,
        "average_payload_estimate": round(avg_payload, 4),
        "payload_percentage": round(avg_payload * 100, 2),
        "verdict": verdict,
        "confidence": round(min(avg_payload * 200, 100), 2),
        "description": (
            "RS analysis estimates the fraction of pixels carrying hidden data "
            "by measuring the ratio of regular to singular pixel groups. "
            "A payload estimate >5% is considered suspicious."
        ),
    }


# ---------------------------------------------------------------------------
# 3. Histogram Analysis
# ---------------------------------------------------------------------------

def histogram_analysis(img_arr: np.ndarray) -> Dict[str, Any]:
    """
    Analyse pixel value histograms for anomalies typical of LSB steganography.
    """
    results = {}
    anomaly_scores = []

    for c in range(3):
        channel = img_arr[:, :, c].flatten().astype(np.int32)
        hist, _ = np.histogram(channel, bins=256, range=(0, 255))
        hist_f = hist.astype(np.float64)

        even_bins = hist_f[0::2]
        odd_bins  = hist_f[1::2]
        pair_diff = np.abs(even_bins - odd_bins)
        mean_pair_diff = float(np.mean(pair_diff))
        max_pair_diff  = float(np.max(pair_diff))

        total_pixels = float(channel.size)
        pair_score = mean_pair_diff / (total_pixels / 256.0 + 1e-10)

        prob = hist_f / (hist_f.sum() + 1e-10)
        entropy = float(-np.sum(prob[prob > 0] * np.log2(prob[prob > 0])))

        lsb_fraction = float(np.mean(channel & 1))
        lsb_deviation = abs(lsb_fraction - 0.5)

        anomaly = min((pair_score * 0.5 + lsb_deviation * 2.0), 1.0)
        anomaly_scores.append(anomaly)

        results[_channel_name(c)] = {
            "mean_pair_difference": round(mean_pair_diff, 2),
            "max_pair_difference": round(max_pair_diff, 2),
            "histogram_entropy": round(entropy, 4),
            "lsb_fraction": round(lsb_fraction, 4),
            "lsb_deviation_from_0_5": round(lsb_deviation, 4),
            "anomaly_score": round(anomaly, 4),
        }

    avg_anomaly = float(np.mean(anomaly_scores))
    verdict = "Suspicious" if avg_anomaly > 0.15 else "Clean"

    return {
        "method": "Histogram Analysis",
        "channels": results,
        "average_anomaly_score": round(avg_anomaly, 4),
        "verdict": verdict,
        "confidence": round(min(avg_anomaly * 400, 100), 2),
        "description": (
            "Histogram analysis examines pixel value distributions. "
            "LSB steganography tends to equalise adjacent bin counts and "
            "push the LSB fraction toward 0.5."
        ),
    }


# ---------------------------------------------------------------------------
# 4. Noise Level Estimation (DWT-based)
# ---------------------------------------------------------------------------

def noise_analysis(img_arr: np.ndarray) -> Dict[str, Any]:
    """
    Estimate noise level using DWT HH sub-band (MAD estimator).
    Steganography typically increases noise in high-frequency sub-bands.
    """
    results = {}
    noise_levels = []

    for c in range(3):
        channel = img_arr[:, :, c].astype(np.float32)
        h, w = channel.shape
        if h % 2 != 0:
            channel = channel[:-1, :]
        if w % 2 != 0:
            channel = channel[:, :-1]

        LL, (LH, HL, HH) = pywt.dwt2(channel, "haar")

        mad_hh = float(np.median(np.abs(HH - np.median(HH)))) / 0.6745
        mad_lh = float(np.median(np.abs(LH - np.median(LH)))) / 0.6745
        mad_hl = float(np.median(np.abs(HL - np.median(HL)))) / 0.6745

        hh_energy = float(np.mean(HH ** 2))
        ll_energy = float(np.mean(LL ** 2)) + 1e-10
        energy_ratio = hh_energy / ll_energy

        noise_levels.append(mad_hh)
        results[_channel_name(c)] = {
            "noise_estimate_HH": round(mad_hh, 4),
            "noise_estimate_LH": round(mad_lh, 4),
            "noise_estimate_HL": round(mad_hl, 4),
            "hh_ll_energy_ratio": round(energy_ratio, 6),
        }

    avg_noise = float(np.mean(noise_levels))
    verdict = "Suspicious" if avg_noise > 6.0 else "Clean"

    return {
        "method": "Noise Level Estimation (DWT)",
        "channels": results,
        "average_noise_level": round(avg_noise, 4),
        "verdict": verdict,
        "confidence": round(min(max((avg_noise - 3.0) / 10.0, 0.0) * 100, 100), 2),
        "description": (
            "DWT-based noise estimation measures high-frequency sub-band energy. "
            "Steganographic embedding increases noise in HH coefficients. "
            "Average noise > 6.0 is considered suspicious."
        ),
    }


# ---------------------------------------------------------------------------
# 5. Sample Pair Analysis
# ---------------------------------------------------------------------------

def sample_pair_analysis(img_arr: np.ndarray) -> Dict[str, Any]:
    """
    Sample Pair Analysis (Dumitrescu et al.).
    Estimates the embedding rate by analysing horizontally adjacent pixel pairs.
    """
    results = {}
    payloads = []

    for c in range(3):
        channel = img_arr[:, :, c].astype(np.int32)
        left  = channel[:, :-1].flatten()
        right = channel[:, 1:].flatten()

        diff = right - left
        W = float(np.sum(np.abs(diff) == 1))
        Z = float(np.sum(diff == 0))
        total = float(len(left))

        if total == 0:
            payloads.append(0.0)
            results[_channel_name(c)] = {"payload_estimate": 0.0}
            continue

        w = W / total
        z = Z / total
        denom = w + z
        payload = max(0.0, min(1.0, (w - z) / denom)) if denom > 1e-10 else 0.0

        payloads.append(payload)
        results[_channel_name(c)] = {
            "W_fraction": round(w, 4),
            "Z_fraction": round(z, 4),
            "payload_estimate": round(payload, 4),
        }

    avg_payload = float(np.mean(payloads))
    verdict = "Suspicious" if avg_payload > 0.05 else "Clean"

    return {
        "method": "Sample Pair Analysis",
        "channels": results,
        "average_payload_estimate": round(avg_payload, 4),
        "payload_percentage": round(avg_payload * 100, 2),
        "verdict": verdict,
        "confidence": round(min(avg_payload * 200, 100), 2),
        "description": (
            "Sample Pair Analysis examines adjacent pixel pairs. "
            "LSB embedding changes the ratio of equal vs. differing-by-1 pairs. "
            "A payload estimate >5% is considered suspicious."
        ),
    }


# ---------------------------------------------------------------------------
# 6. Bit-Plane Analysis
# ---------------------------------------------------------------------------

def bit_plane_analysis(img_arr: np.ndarray) -> Dict[str, Any]:
    """
    Analyse each bit-plane for randomness.
    The LSB plane of a stego image tends to be nearly random (entropy ≈ 1.0).
    """
    results = {}
    lsb_entropies = []

    for c in range(3):
        channel = img_arr[:, :, c]
        plane_results = {}

        for bit in range(8):
            plane = (channel >> bit) & 1
            frac_ones = float(np.mean(plane))
            p = frac_ones
            if p <= 0 or p >= 1:
                entropy = 0.0
            else:
                entropy = float(-(p * np.log2(p) + (1 - p) * np.log2(1 - p)))

            plane_results[f"bit_{bit}"] = {
                "fraction_ones": round(frac_ones, 4),
                "entropy": round(entropy, 4),
            }

        lsb_entropy = plane_results["bit_0"]["entropy"]
        lsb_entropies.append(lsb_entropy)
        results[_channel_name(c)] = plane_results

    avg_lsb_entropy = float(np.mean(lsb_entropies))
    verdict = "Suspicious" if avg_lsb_entropy > 0.90 else "Clean"

    return {
        "method": "Bit-Plane Analysis",
        "channels": results,
        "average_lsb_entropy": round(avg_lsb_entropy, 4),
        "verdict": verdict,
        "confidence": round(min(max((avg_lsb_entropy - 0.7) / 0.3, 0.0) * 100, 100), 2),
        "description": (
            "Bit-plane analysis measures the entropy of each bit-plane. "
            "The LSB plane of a stego image is nearly random (entropy ≈ 1.0), "
            "while natural images have structured LSB planes (entropy < 0.85)."
        ),
    }


# ---------------------------------------------------------------------------
# 7. Overall Steganalysis Report
# ---------------------------------------------------------------------------

def analyze_image(image_bytes: bytes, image_path: str | None = None) -> Dict[str, Any]:
    """
    Run all steganalysis methods on the provided image bytes.

    Returns a comprehensive report with:
      - Individual method results
      - Overall verdict and confidence score
      - Image metadata
    """
    img_arr = _load_image_array(image_bytes)
    h, w = img_arr.shape[:2]
    total_pixels = h * w
    decoded_payload = decode_hidden_data(image_bytes, img_arr, image_path=image_path)

    chi2_result  = chi_square_attack(img_arr)
    rs_result    = rs_analysis(img_arr)
    hist_result  = histogram_analysis(img_arr)
    noise_result = noise_analysis(img_arr)
    sp_result    = sample_pair_analysis(img_arr)
    bp_result    = bit_plane_analysis(img_arr)
    
    # Neural Network steganalysis (if PyTorch is available)
    nn_result = neural_network_steganalysis(image_bytes)
    
    analyses = [chi2_result, rs_result, hist_result, noise_result, sp_result, bp_result]

    suspicious_count = sum(1 for a in analyses if a["verdict"] == "Suspicious")
    total_methods    = len(analyses)
    avg_confidence   = float(np.mean([a["confidence"] for a in analyses]))

    if suspicious_count >= 4:
        overall_verdict = "High Probability of Hidden Data"
        risk_level = "HIGH"
    elif suspicious_count >= 2:
        overall_verdict = "Moderate Probability of Hidden Data"
        risk_level = "MEDIUM"
    elif suspicious_count == 1:
        overall_verdict = "Low Probability of Hidden Data"
        risk_level = "LOW"
    else:
        overall_verdict = "No Hidden Data Detected"
        risk_level = "CLEAN"

    capacity_bytes = (total_pixels * 3) // 8

    return {
        "status": "success",
        "image_info": {
            "width": w,
            "height": h,
            "total_pixels": total_pixels,
            "channels": 3,
            "estimated_capacity_bytes": capacity_bytes,
            "estimated_capacity_kb": round(capacity_bytes / 1024, 2),
        },
        "overall": {
            "verdict": overall_verdict,
            "risk_level": risk_level,
            "suspicious_methods": suspicious_count,
            "total_methods": total_methods,
            "average_confidence": round(avg_confidence, 2),
        },
        "analyses": {
            "chi_square": chi2_result,
            "rs_analysis": rs_result,
            "histogram": hist_result,
            "noise": noise_result,
            "sample_pair": sp_result,
            "bit_plane": bp_result,
            "neural_network": nn_result,
        },
        "decoded_payload": decoded_payload,
    }


def decode_only_image(image_bytes: bytes, image_path: str | None = None, passwords: list | None = None) -> Dict[str, Any]:
    """
    Decode hidden payload only (no statistical steganalysis).
    Optionally accepts passwords to attempt decryption of Russian Doll layers.
    """
    img_arr = _load_image_array(image_bytes)
    h, w = img_arr.shape[:2]
    total_pixels = h * w
    capacity_bytes = (total_pixels * 3) // 8
    decoded_payload = decode_hidden_data(image_bytes, img_arr, image_path=image_path)
    
    # Attempt decryption if passwords provided and encrypted data found
    decrypted_text = None
    decryption_error = None
    if passwords and decoded_payload.get("found") and decoded_payload.get("is_binary"):
        try:
            from core.encryption import decrypt_aes_gcm, reconstruct_and_decrypt
            from Cryptodome.Protocol.SecretSharing import Shamir
            import hashlib
            import struct
            import json
            
            hex_data = decoded_payload.get("hex_preview", "") or decoded_payload.get("hex_data", "")
            if hex_data and len(hex_data) > 16:
                # Try to parse as share payload (JSON format from _unpack_share_payload)
                try:
                    # First, try raw hex as encrypted data
                    for pw in passwords:
                        try:
                            key = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), b'aegis_ghost_salt', 100000, dklen=16)
                            encrypted_bytes = bytes.fromhex(hex_data)
                            decrypted = decrypt_aes_gcm(encrypted_bytes, key)
                            decrypted_text = decrypted.decode('utf-8')
                            break
                        except:
                            pass
                    
                    # If direct decryption failed, try parsing as JSON share payload
                    if not decrypted_text:
                        data_bytes = bytes.fromhex(hex_data)
                        # Try to parse length-prefixed JSON (format from _unpack_share_payload)
                        if len(data_bytes) >= 4:
                            try:
                                payload_len = struct.unpack(">I", data_bytes[:4])[0]
                                if payload_len > 0 and payload_len < len(data_bytes) - 4:
                                    json_bytes = data_bytes[4:4+payload_len]
                                    share_info = json.loads(json_bytes.decode('utf-8'))
                                    
                                    # This is a Shamir share - return info about it
                                    decryption_error = f"This image contains Shamir share #{share_info.get('share_index', '?')}. To decrypt, you need at least 6 shares from different images."
                                    decoded_payload["share_info"] = {
                                        "share_index": share_info.get("share_index"),
                                        "is_shamir_share": True,
                                        "requires_threshold": 6,
                                        "note": "Upload all images from the batch to reconstruct the secret"
                                    }
                            except:
                                pass
                except Exception as e:
                    decryption_error = str(e)
            
            if not decrypted_text and not decryption_error:
                decryption_error = "Could not decrypt. This appears to be Shamir-shared encrypted data."
        except Exception as e:
            decryption_error = str(e)
    
    result = {
        "status": "success",
        "mode": "decode_only",
        "image_info": {
            "width": w,
            "height": h,
            "total_pixels": total_pixels,
            "channels": 3,
            "estimated_capacity_bytes": capacity_bytes,
            "estimated_capacity_kb": round(capacity_bytes / 1024, 2),
        },
        "decoded_payload": decoded_payload,
    }
    
    # Add decryption results if applicable
    if decrypted_text:
        result["decrypted_text"] = decrypted_text
        result["decryption_status"] = "success"
    elif passwords and decoded_payload.get("found"):
        result["decryption_status"] = "failed"
        result["decryption_error"] = decryption_error or "Could not decrypt with provided passwords"
    
    return result


# ==================== ADVANCED STEGANALYSIS MODULE ====================
# Advanced statistical analysis for steganography detection
# Includes Chi-square test and LSB entropy analysis
# =====================================================================

def chi_square_test(image):
    """
    Chi-square test for LSB steganography detection.
    
    This test analyzes the frequency distribution of LSB values.
    In natural images, LSBs are roughly equally distributed.
    In steganographic images, there may be statistical anomalies.
    
    Args:
        image: PIL Image or numpy array
        
    Returns:
        float: p-value (lower p-value suggests possible steganography)
    """
    img = np.array(image)
    
    # Extract LSB from all channels
    lsb = img & 1
    
    # Count zeros and ones
    zeros = np.sum(lsb == 0)
    ones = np.sum(lsb == 1)
    
    observed = [zeros, ones]
    expected = [(zeros + ones) / 2, (zeros + ones) / 2]
    
    # Perform chi-square test
    stat, p = chisquare(observed, expected)
    
    return p


def lsb_entropy(image):
    """
    Calculate LSB entropy to detect possible hidden data.
    
    High entropy in LSB plane may indicate steganography.
    Natural images typically have lower LSB entropy.
    
    Args:
        image: PIL Image or numpy array
        
    Returns:
        float: LSB entropy value (0-1 range, higher suggests possible steganography)
    """
    img = np.array(image)
    
    # Extract LSB from all channels
    lsb = img & 1
    
    # Calculate probability of 1s
    prob1 = np.mean(lsb)
    prob0 = 1 - prob1
    
    # Calculate Shannon entropy
    # Use small epsilon to avoid log(0)
    epsilon = 1e-9
    entropy = -(prob0 * np.log2(prob0 + epsilon) + prob1 * np.log2(prob1 + epsilon))
    
    # Normalize to 0-1 range (max entropy for binary is 1)
    return entropy


def extract_lsb_data(image):
    """
    Extract hidden data from an image by reading LSB of each pixel.
    
    This function extracts raw data hidden in the least significant bits
    of image pixels. It reads all channels of all pixels.
    
    Args:
        image: PIL Image or numpy array
        
    Returns:
        bytes: Extracted data from LSBs
    """
    pixels = np.array(image)
    
    bits = ""
    
    # Extract LSB from each pixel channel
    for row in pixels:
        for pixel in row:
            for c in pixel:
                bits += str(c & 1)
    
    # Convert bits to bytes
    data_bytes = []
    
    for i in range(0, len(bits), 8):
        byte = bits[i:i+8]
        
        if len(byte) == 8:
            data_bytes.append(int(byte, 2))
    
    data = bytes(data_bytes)
    
    return data


# ==================== NEURAL NETWORK STEGANALYSIS ====================
# CNN-based steganalysis model for detecting hidden data in images
# =====================================================================

if TORCH_AVAILABLE:
    class StegoCNN(nn.Module):
        """
        Convolutional Neural Network for Steganalysis.
        
        A lightweight CNN that classifies images as clean or containing
        hidden data. Uses a series of convolutional layers followed by
        fully connected layers for binary classification.
        """
        
        def __init__(self):
            super().__init__()
            
            # Convolutional feature extractor
            self.conv = nn.Sequential(
                # First conv block
                nn.Conv2d(3, 16, 3, padding=1),
                nn.ReLU(),
                
                # Second conv block
                nn.Conv2d(16, 32, 3, padding=1),
                nn.ReLU(),
                nn.MaxPool2d(2),
                
                # Third conv block
                nn.Conv2d(32, 64, 3, padding=1),
                nn.ReLU(),
                
                # Global average pooling
                nn.AdaptiveAvgPool2d((1, 1))
            )
            
            # Classification head
            self.fc = nn.Linear(64, 2)
        
        def forward(self, x):
            x = self.conv(x)
            x = x.view(x.size(0), -1)
            x = self.fc(x)
            return x
else:
    class StegoCNN:
        """Placeholder when PyTorch is unavailable."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyTorch is not available; StegoCNN cannot be instantiated.")


def show_histogram(image):
    """
    Display a histogram of pixel values for the image.
    
    Histogram analysis is useful for detecting steganography as
    some methods cause noticeable changes in pixel value distribution.
    
    Args:
        image: PIL Image or numpy array
        
    Returns:
        None: Displays matplotlib histogram plot
    """
    plt.hist(image.ravel(), 256)
    plt.title("Pixel Histogram")
    plt.xlabel("Pixel Value")
    plt.ylabel("Frequency")
    plt.show()
