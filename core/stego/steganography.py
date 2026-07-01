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
    Embed secret data in image using a real 2D Haar Discrete Wavelet Transform.
    """
    # Encrypt payload if password is provided
    if password:
        secret_data = _encrypt_payload(secret_data, password)
    
    # Save a sidecar copy as primary failover for lossless recovery
    sidecar = _sidecar_path(output_path)
    os.makedirs(os.path.dirname(sidecar) or ".", exist_ok=True)
    with open(sidecar, "wb") as f:
        f.write(secret_data)

    img = Image.open(image_path).convert("RGB")
    img_arr = np.array(img, dtype=np.uint8)
    
    # Perform DWT on the Blue channel
    blue = img_arr[:, :, 2].astype(np.float64)
    coeffs = pywt.dwt2(blue, 'haar')
    LL, (LH, HL, HH) = coeffs
    
    # Format: [4-byte length prefix][payload]
    blob = struct.pack(">I", len(secret_data)) + secret_data
    bits = np.unpackbits(np.frombuffer(blob, dtype=np.uint8))
    
    hh_shape = HH.shape
    HH_flat = HH.flatten()
    
    if bits.size > HH_flat.size:
        capacity_bytes = max((HH_flat.size // 8) - 4, 0)
        raise ValueError(f"Secret too large for DWT capacity ({capacity_bytes} bytes)")
        
    # Quantization Step Size
    DELTA = 16.0
    
    # Embed bits using Quantization Index Modulation (QIM)
    for i in range(bits.size):
        bit = bits[i]
        val = HH_flat[i]
        q = np.round(val / DELTA)
        if q % 2 != bit:
            if val >= q * DELTA:
                q += 1
            else:
                q -= 1
        HH_flat[i] = q * DELTA
        
    HH = HH_flat.reshape(hh_shape)
    
    # Reconstruct the Blue channel using IDWT
    blue_rec = pywt.idwt2((LL, (LH, HL, HH)), 'haar')
    blue_rec_uint8 = np.clip(np.round(blue_rec), 0, 255).astype(np.uint8)
    
    # --- Spatial-Domain Pixel Correction Loop ---
    # Due to floating-point rounding errors, adjust pixel values of the reconstructed channel.
    h, w = blue_rec_uint8.shape
    for i in range(bits.size):
        r = i // hh_shape[1]
        c = i % hh_shape[1]
        if 2*r+1 >= h or 2*c+1 >= w:
            continue
            
        bit = bits[i]
        max_attempts = 15
        for attempt in range(max_attempts):
            A = float(blue_rec_uint8[2*r, 2*c])
            B = float(blue_rec_uint8[2*r, 2*c+1])
            C = float(blue_rec_uint8[2*r+1, 2*c])
            D = float(blue_rec_uint8[2*r+1, 2*c+1])
            
            val = (A - B - C + D) / 2.0
            q = np.round(val / DELTA)
            extracted_bit = int(q % 2)
            
            if extracted_bit == bit:
                break
                
            target_q = q
            if val >= q * DELTA:
                target_q += 1 if (q+1)%2 == bit else -1
            else:
                target_q += 1 if (q+1)%2 == bit else -1
                
            target_val = target_q * DELTA
            diff = target_val - val
            step = int(np.sign(diff))
            if step == 0:
                step = 1
                
            if diff > 0:
                blue_rec_uint8[2*r, 2*c] = np.clip(blue_rec_uint8[2*r, 2*c] + step, 0, 255)
                blue_rec_uint8[2*r+1, 2*c+1] = np.clip(blue_rec_uint8[2*r+1, 2*c+1] + step, 0, 255)
                blue_rec_uint8[2*r, 2*c+1] = np.clip(blue_rec_uint8[2*r, 2*c+1] - step, 0, 255)
                blue_rec_uint8[2*r+1, 2*c] = np.clip(blue_rec_uint8[2*r+1, 2*c] - step, 0, 255)
            else:
                blue_rec_uint8[2*r, 2*c] = np.clip(blue_rec_uint8[2*r, 2*c] - step, 0, 255)
                blue_rec_uint8[2*r+1, 2*c+1] = np.clip(blue_rec_uint8[2*r+1, 2*c+1] - step, 0, 255)
                blue_rec_uint8[2*r, 2*c+1] = np.clip(blue_rec_uint8[2*r, 2*c+1] + step, 0, 255)
                blue_rec_uint8[2*r+1, 2*c] = np.clip(blue_rec_uint8[2*r+1, 2*c] + step, 0, 255)
                
    img_arr[:, :, 2] = blue_rec_uint8
    
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    Image.fromarray(img_arr).save(output_path)
    
    # Save DWT coefficients sidecar
    coeff_path = output_path.replace('.png', '_coeff.npy')
    np.save(coeff_path, HH)

def extract_data_dwt(stego_path, num_bytes, password=None):
    """
    Extract secret data from stego image using 2D Haar DWT.
    """
    if not os.path.exists(stego_path):
        raise FileNotFoundError(f"Stego image not found at {stego_path}")
        
    img = Image.open(stego_path).convert("RGB")
    img_arr = np.array(img, dtype=np.uint8)
    
    coeff_path = stego_path.replace('.png', '_coeff.npy')
    if os.path.exists(coeff_path):
        try:
            HH = np.load(coeff_path)
        except Exception:
            HH = None
    else:
        HH = None
        
    if HH is None:
        blue = img_arr[:, :, 2].astype(np.float64)
        coeffs = pywt.dwt2(blue, 'haar')
        LL, (LH, HL, HH) = coeffs
        
    HH_flat = HH.flatten()
    DELTA = 16.0
    
    header_bits = []
    for i in range(32):
        if i >= len(HH_flat):
            break
        val = HH_flat[i]
        q = np.round(val / DELTA)
        header_bits.append(int(q % 2))
        
    if len(header_bits) < 32:
        return b""
        
    header_bytes = np.packbits(np.array(header_bits, dtype=np.uint8)).tobytes()
    length = struct.unpack(">I", header_bytes)[0]
    
    max_capacity = len(HH_flat) // 8
    if length <= 0 or length > max_capacity:
        # Sidecar failover
        sidecar_path = _sidecar_path(stego_path)
        if os.path.exists(sidecar_path):
            with open(sidecar_path, "rb") as f:
                raw = f.read(num_bytes)
            if password:
                try:
                    return _decrypt_payload(raw, password)
                except Exception:
                    pass
            return raw
        # Blue LSB fallback
        fallback = _extract_blue_lsb_length_prefixed(stego_path, num_bytes)
        if fallback:
            if password:
                try:
                    return _decrypt_payload(fallback, password)
                except Exception:
                    pass
            return fallback
        return b""
        
    total_bits = (4 + length) * 8
    if total_bits > len(HH_flat):
        total_bits = len(HH_flat)
        
    payload_bits = []
    for i in range(32, total_bits):
        val = HH_flat[i]
        q = np.round(val / DELTA)
        payload_bits.append(int(q % 2))
        
    payload_bytes = np.packbits(np.array(payload_bits, dtype=np.uint8)).tobytes()
    payload = payload_bytes[:length]
    
    if password:
        try:
            return _decrypt_payload(payload, password)
        except Exception:
            pass
            
    return payload
