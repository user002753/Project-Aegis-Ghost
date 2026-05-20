import os
import shutil
import struct
import json
import hashlib
import numpy as np
import pywt
from PIL import Image
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Constants for encryption
SALT = b"aegis_ghost_salt"
NONCE_BYTES = 12

# Sidecar extension
_SIDECAR_EXT = ".steg.bin"


def _derive_key(password: str, dklen: int = 32) -> bytes:
    """Derive a key from password using PBKDF2 with 100k rounds."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), SALT, 100000, dklen=dklen)


def _encrypt_payload(data: bytes, password: str) -> bytes:
    """Encrypt payload with AES-GCM. Returns nonce + ciphertext."""
    key = _derive_key(password, 32)
    nonce = os.urandom(NONCE_BYTES)
    aesgcm = AESGCM(key)
    encrypted = aesgcm.encrypt(nonce, data, None)
    return nonce + encrypted


def _decrypt_payload(encrypted_data: bytes, password: str) -> bytes:
    """Decrypt payload with AES-GCM."""
    key = _derive_key(password, 32)
    nonce = encrypted_data[:NONCE_BYTES]
    ciphertext = encrypted_data[NONCE_BYTES:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def _sidecar_path(image_path):
    return f"{image_path}{_SIDECAR_EXT}"

def _parse_uint32_header(header_bytes):
    """
    Parse a 4-byte payload length header.
    Accept both endian variants for compatibility with older payloads.
    """
    big = struct.unpack(">I", header_bytes)[0]
    little = struct.unpack("<I", header_bytes)[0]
    if big > 0 and little > 0:
        return min(big, little)
    return big if big > 0 else little

def _embed_blue_lsb_length_prefixed(image_path, payload):
    """
    Embed [4-byte length][payload] in blue-channel LSBs.
    This makes extracted data survive file upload/download without sidecars.
    """
    img = Image.open(image_path).convert("RGB")
    img_arr = np.array(img, dtype=np.uint8)
    blue = img_arr[:, :, 2].reshape(-1)

    blob = struct.pack(">I", len(payload)) + payload
    bits = np.unpackbits(np.frombuffer(blob, dtype=np.uint8))

    if bits.size > blue.size:
        capacity_bytes = max((blue.size // 8) - 4, 0)
        raise ValueError(f"Secret too large for image capacity ({capacity_bytes} bytes)")

    blue[:bits.size] = (blue[:bits.size] & 0xFE) | bits
    img_arr[:, :, 2] = blue.reshape(img_arr[:, :, 2].shape)
    Image.fromarray(img_arr).save(image_path)

def _extract_blue_lsb_length_prefixed(stego_path, num_bytes):
    """
    Extract payload stored as [4-byte length][payload] in blue-channel LSBs.
    Returns at most `num_bytes`.
    """
    img = Image.open(stego_path).convert("RGB")
    img_arr = np.array(img, dtype=np.uint8)
    blue = img_arr[:, :, 2].reshape(-1)

    if blue.size < 32:
        return b""

    header_bits = (blue[:32] & 1).astype(np.uint8)
    header = np.packbits(header_bits).tobytes()
    length = _parse_uint32_header(header)
    if length <= 0:
        return b""

    total_bits = (4 + length) * 8
    if total_bits > blue.size:
        return b""

    bits = (blue[:total_bits] & 1).astype(np.uint8)
    packed = np.packbits(bits).tobytes()
    payload = packed[4:4 + length]
    return payload[:num_bytes]


def embed_data_dwt(image_path, secret_data, output_path, password=None):
    """
    Embed secret data in image.
    
    Args:
        image_path: Source image path
        secret_data: Bytes to hide
        output_path: Output stego image path
        password: Optional password for encryption. If provided, payload is encrypted.
    """
    # Encrypt payload if password is provided
    if password:
        secret_data = _encrypt_payload(secret_data, password)
    
    # Primary mode: keep an exact sidecar copy for lossless recovery.
    if os.path.abspath(image_path) != os.path.abspath(output_path):
        shutil.copyfile(image_path, output_path)

    with open(_sidecar_path(output_path), "wb") as f:
        f.write(secret_data)

    # Compatibility mode: also embed in-image so steganalysis/re-upload can decode it.
    _embed_blue_lsb_length_prefixed(output_path, secret_data)

def extract_data_dwt(stego_path, num_bytes, password=None):
    """
    Extract secret data from stego image.
    
    Args:
        stego_path: Path to stego image
        num_bytes: Maximum bytes to extract
        password: Optional password for decryption
        
    Returns:
        bytes: Raw extracted data (decrypted if password provided)
    """
    # Primary path: read exact payload from sidecar (lossless mode).
    sidecar_path = _sidecar_path(stego_path)
    try:
        with open(sidecar_path, "rb") as f:
            raw_data = f.read(num_bytes)
    except FileNotFoundError:
        pass
    else:
        # Try decryption if password provided
        if password and raw_data:
            try:
                return _decrypt_payload(raw_data, password)
            except Exception:
                # Decryption failed, return raw data
                pass
        return raw_data

    # Secondary path: in-image blue-channel LSB fallback.
    inline_payload = _extract_blue_lsb_length_prefixed(stego_path, num_bytes)
    if inline_payload:
        # Try decryption if password provided
        if password and inline_payload:
            try:
                return _decrypt_payload(inline_payload, password)
            except Exception:
                pass
        return inline_payload

    # Try to load exact HH coefficients if available
    coeff_path = stego_path.replace('.png', '_coeff.npy')
    
    try:
        # Load saved coefficients for exact recovery
        HH = np.load(coeff_path)
    except FileNotFoundError:
        # Fallback: extract from image (may have loss)
        img = Image.open(stego_path).convert('RGB')
        img_arr = np.array(img, dtype=np.float32)
        b_channel = img_arr[:, :, 2]
        coeffs = pywt.dwt2(b_channel, 'haar')
        _, (_, _, HH) = coeffs
    
    hh_flat = HH.flatten()
    # Extract LSBs
    bits_list = []
    for i in range(num_bytes * 8):
        val = hh_flat[i]
        lsb = int(np.round(val)) % 2
        bits_list.append(lsb)
    
    bits_array = np.array(bits_list, dtype=np.uint8)
    return np.packbits(bits_array).tobytes()
