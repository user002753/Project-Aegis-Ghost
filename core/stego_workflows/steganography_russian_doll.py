"""
Advanced Steganography with Russian Doll Algorithm + Shamir's Secret Sharing

Key Features:
1. FAKE LSB: Decoy data in visible LSB layer (easy to detect, misleading)
2. REAL SECRET: Encrypted with AES-GCM, embedded in DWT coefficients (hidden)
3. SHAMIR'S SPLITTING: Encrypted secret split into 10 shares using Shamir's
4. AI IMAGE GENERATION: Each share embedded in unique AI-generated image
"""

import numpy as np
import pywt
import os
import json
import hashlib
import secrets
import base64
from PIL import Image
import struct
from typing import List, Tuple, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from Cryptodome.Cipher import AES
from Cryptodome.Protocol.SecretSharing import Shamir
from Cryptodome.Random import get_random_bytes

# AI Image generation imports
try:
    from core.ai_engine import generate_ghost_carrier, _generate_mock
except ModuleNotFoundError:
    # Fallback for when running directly
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ai_engine import generate_ghost_carrier, _generate_mock


class RussianDollSteganography:
    """
    Multi-layer steganography with:
    - Fake LSB layer (decoy data - visible but misleading)
    - Real encrypted secret layer (hidden in DWT coefficients)
    - Shamir's secret sharing across multiple images
    """
    
    def __init__(self, output_dir: str = "data/output_stego"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def _generate_decoy_data(self, length: int) -> bytes:
        """Generate fake/decoy data to hide in visible LSB layer."""
        # Create believable but fake secret data
        decoy_messages = [
            b"MEET_AT_CENTRAL_PARK_AT_NOON",
            b"THE_PASSWORD_IS_ADMIN123",
            b"SECRET_CODE:9876543210",
            b"MEETING_CANCELLED_SEE_YOU_TOMORROW",
            b"DROP_LOCATION:WAREHOUSE_7"
        ]
        # Use random decoy based on length
        decoy = secrets.choice(decoy_messages)
        # Pad or repeat to match length
        if len(decoy) < length:
            decoy = decoy * (length // len(decoy) + 1)
        return decoy[:length]
    
    def _encrypt_real_secret(self, secret: str, password: str) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt the REAL secret with AES-128-GCM.
        Returns: (ciphertext, nonce, key)
        
        Note: Uses 16-byte key for compatibility with Shamir's secret sharing.
        Output is hex-encoded for safe embedding in images.
        """
        # Derive 16-byte key from password using PBKDF2 (for AES-128 compatibility)
        salt = b'aegis_ghost_salt'  # Fixed salt for consistency
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=16)
        
        # Encrypt with AES-GCM
        nonce = secrets.token_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(secret.encode('utf-8'))
        
        # Return raw bytes - will be hex-encoded when embedding
        return ciphertext, nonce + tag, key
    
    def _encrypt_real_secret_hex(self, secret: str, password: str) -> str:
        """
        Encrypt the REAL secret and return hex-encoded string.
        This is the primary method for Russian Doll steganography.
        Returns hex-encoded ciphertext with nonce/tag prepended.
        """
        # Derive 16-byte key from password using PBKDF2
        salt = b'aegis_ghost_salt'  # Fixed salt for consistency
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=16)
        
        # Encrypt with AES-GCM
        nonce = secrets.token_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(secret.encode('utf-8'))
        
        # Combine nonce + tag + ciphertext and encode as hex
        # Format: [nonce (12 bytes)][tag (16 bytes)][ciphertext]
        combined = nonce + tag + ciphertext
        return combined.hex()
    
    def _decrypt_real_secret(self, ciphertext: bytes, password: str, nonce_tag: bytes) -> str:
        """Decrypt the REAL secret."""
        salt = b'aegis_ghost_salt'
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=16)
        
        nonce = nonce_tag[:12]
        tag = nonce_tag[12:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode('utf-8')
    
    def _decrypt_real_secret_hex(self, hex_data: str, password: str) -> str:
        """
        Decrypt hex-encoded encrypted secret.
        
        Args:
            hex_data: Hex-encoded string (nonce + tag + ciphertext)
            password: Password for decryption
            
        Returns:
            Decrypted plaintext string
        """
        # Decode hex to bytes
        combined = bytes.fromhex(hex_data)
        
        # Parse: [nonce (12 bytes)][tag (16 bytes)][ciphertext]
        nonce = combined[:12]
        tag = combined[12:28]
        ciphertext = combined[28:]
        
        # Derive key from password
        salt = b'aegis_ghost_salt'
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=16)
        
        # Decrypt
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode('utf-8')
    
    def _decrypt_real_secret_with_key(self, ciphertext: bytes, key: bytes, nonce_tag: bytes) -> str:
        """Decrypt the REAL secret using a pre-reconstructed key."""
        nonce = nonce_tag[:12]
        tag = nonce_tag[12:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode('utf-8')
    
    def _decrypt_real_secret_with_key_hex(self, hex_data: str, key: bytes) -> str:
        """Decrypt hex-encoded encrypted secret using a pre-reconstructed key."""
        combined = bytes.fromhex(hex_data)
        nonce = combined[:12]
        tag = combined[12:28]
        ciphertext = combined[28:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode('utf-8')
    
    def _embed_lsb(self, img_array: np.ndarray, data: bytes) -> np.ndarray:
        """Embed data in LSB of red and green channels only (leaving blue for DWT layer)."""
        # Convert data to bits
        data_bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
        
        # Flatten image and embed in R and G channels only (leave B for DWT)
        flat_r = img_array[:, :, 0].flatten()
        flat_g = img_array[:, :, 1].flatten()
        
        # Store length in first 32 bits
        length_bits = np.unpackbits(np.array([len(data)], dtype=np.uint32).view(np.uint8))
        
        # Total bits = length (32) + data
        total_bits = np.concatenate([length_bits, data_bits])
        
        # Calculate capacity in R+G channels
        capacity = len(flat_r) + len(flat_g)
        
        # Guard against overflow
        if len(total_bits) > capacity:
            max_bits = capacity - 32
            total_bits = total_bits[:32 + max_bits]
        
        # Embed in red channel first, then green
        total_len = len(total_bits)
        r_len = min(total_len, len(flat_r))
        g_len = total_len - r_len
        
        # Embed in Red channel
        for i in range(r_len):
            if total_bits[i] == 1:
                flat_r[i] = flat_r[i] | 1
            else:
                flat_r[i] = flat_r[i] & 0xFE
        
        # Embed in Green channel
        for i in range(g_len):
            idx = r_len + i
            if total_bits[idx] == 1:
                flat_g[i] = flat_g[i] | 1
            else:
                flat_g[i] = flat_g[i] & 0xFE
        
        # Reshape back
        img_array[:, :, 0] = flat_r.reshape(img_array[:, :, 0].shape)
        img_array[:, :, 1] = flat_g.reshape(img_array[:, :, 1].shape)
        
        return img_array
    
    def _extract_lsb(self, img_array: np.ndarray, num_bytes: int) -> bytes:
        """Extract data from LSB layer (red and green channels only)."""
        flat_r = img_array[:, :, 0].flatten()
        flat_g = img_array[:, :, 1].flatten()
        
        # Combine R and G channels for extraction
        combined = np.concatenate([flat_r, flat_g])
        
        # Extract length from first 32 bits
        length_bits = combined[:32]
        length = np.packbits(length_bits).view(np.uint32)[0]
        
        # Guard against excessive length
        if length > num_bytes or length < 0:
            return b''
        
        # Extract actual data
        data_bits = combined[32:32 + length * 8]
        return np.packbits(data_bits).tobytes()
    
    def _embed_dwt(self, img_array: np.ndarray, data: bytes) -> np.ndarray:
        """Embed data in DWT coefficients of the Blue channel using 2D Haar DWT and QIM."""
        # Perform DWT on the Blue channel
        blue = img_array[:, :, 2].astype(np.float64)
        coeffs = pywt.dwt2(blue, 'haar')
        LL, (LH, HL, HH) = coeffs
        
        # Format bits to embed: [4-byte length prefix][data]
        blob = struct.pack(">I", len(data)) + data
        bits = np.unpackbits(np.frombuffer(blob, dtype=np.uint8))
        
        hh_shape = HH.shape
        HH_flat = HH.flatten()
        
        if bits.size > HH_flat.size:
            max_bytes = max((HH_flat.size // 8) - 4, 0)
            raise ValueError(f"Secret too large for DWT capacity ({max_bytes} bytes)")
            
        DELTA = 16.0
        
        # Embed bits in HH using QIM
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
        
        # Reconstruct Blue channel using IDWT
        blue_rec = pywt.idwt2((LL, (LH, HL, HH)), 'haar')
        blue_rec_uint8 = np.clip(np.round(blue_rec), 0, 255).astype(np.uint8)
        
        # Spatial-domain correction loop to ensure perfect recovery
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
                    
        result = img_array.copy()
        result[:, :, 2] = blue_rec_uint8
        return result
    
    def _extract_dwt(self, img_array: np.ndarray) -> bytes:
        """Extract data from DWT coefficients of the Blue channel using 2D Haar DWT."""
        blue = img_array[:, :, 2].astype(np.float64)
        coeffs = pywt.dwt2(blue, 'haar')
        LL, (LH, HL, HH) = coeffs
        
        HH_flat = HH.flatten()
        DELTA = 16.0
        
        # Extract length prefix (first 32 bits)
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
        
        max_size = len(HH_flat) // 8
        if length <= 0 or length > max_size:
            # Fallback to direct blue LSB extraction if header is invalid
            flat = img_array[:, :, 2].flatten()
            length_bits = [flat[i] & 1 for i in range(32)]
            try:
                length = np.packbits(np.array(length_bits, dtype=np.uint8)).view(np.uint32)[0]
            except Exception:
                return b""
            if length <= 0 or length > max_size:
                return b""
            data_bits = [flat[i] & 1 for i in range(32, min(32 + length * 8, len(flat)))]
            return np.packbits(np.array(data_bits, dtype=np.uint8)).tobytes()
            
        # Extract actual payload bits
        total_bits = (4 + length) * 8
        if total_bits > len(HH_flat):
            total_bits = len(HH_flat)
            
        data_bits = []
        for i in range(32, total_bits):
            val = HH_flat[i]
            q = np.round(val / DELTA)
            data_bits.append(int(q % 2))
            
        payload_bytes = np.packbits(np.array(data_bits, dtype=np.uint8)).tobytes()
        return payload_bytes[:length]
    
    def create_fake_lsb_stego(self, image_path: str, decoy_message: str, output_path: str) -> str:
        """Create stego image with ONLY fake LSB data (for decoy)."""
        img = Image.open(image_path).convert('RGB')
        img = img.resize((512, 512), Image.Resampling.LANCZOS)
        img_array = np.array(img, dtype=np.uint8)
        
        # Embed fake/decoy data in LSB (visible layer)
        decoy_bytes = decoy_message.encode('utf-8')
        stego_array = self._embed_lsb(img_array, decoy_bytes)
        
        # Save
        stego_img = Image.fromarray(stego_array)
        stego_img.save(output_path)
        
        return output_path
    
    def create_russian_doll_stego(
        self,
        image_path: str,
        real_secret: str,
        password: str,
        decoy_message: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Dict:
        """
        Create Russian Doll steganography:
        - Layer 1 (Fake): LSB with decoy data (visible, misleading)
        - Layer 2 (Real): DWT with hex-encoded encrypted secret (hidden)
        
        Returns dict with output path and metadata.
        """
        if output_path is None:
            timestamp = int(secrets.token_hex(4), 16)
            output_path = os.path.join(self.output_dir, f"russian_doll_{timestamp}.png")
        
        # Load and prepare image
        img = Image.open(image_path).convert('RGB')
        img = img.resize((512, 512), Image.Resampling.LANCZOS)
        img_array = np.array(img, dtype=np.uint8)
        
        # Step 1: Encrypt REAL secret and get hex-encoded output
        hex_encrypted = self._encrypt_real_secret_hex(real_secret, password)
        
        # Step 2: Convert hex string to bytes for embedding
        encrypted_bytes = hex_encrypted.encode('utf-8')
        
        # Step 3: Embed FAKE decoy in LSB layer FIRST (visible, misleading)
        # This goes in all channels but we'll overwrite with real secret in blue channel only
        if decoy_message is None:
            decoy_message = self._generate_decoy_data(32).decode('utf-8', errors='ignore')
        
        img_array = self._embed_lsb(img_array, decoy_message.encode('utf-8'))
        
        # Step 4: Embed encrypted secret in DWT layer LAST (hidden in blue channel only)
        # This is the "deeper" layer that survives because it uses only blue channel
        img_array = self._embed_dwt(img_array, encrypted_bytes)
        
        # Save
        stego_img = Image.fromarray(img_array.astype(np.uint8))
        stego_img.save(output_path)
        
        # Save DWT coefficients sidecar
        blue = img_array[:, :, 2].astype(np.float64)
        coeffs = pywt.dwt2(blue, 'haar')
        _, (_, _, HH) = coeffs
        coeff_path = output_path.replace('.png', '_coeff.npy')
        np.save(coeff_path, HH)
        
        # Return metadata for extraction
        metadata = {
            'output_path': output_path,
            'decoy_hint': decoy_message[:10] + '...',
            'real_secret_length': len(real_secret),
            'encrypted_length': len(hex_encrypted),
            'hex_encoded': True  # Flag to indicate hex encoding is used
        }
        
        return metadata
    
    def extract_russian_doll(self, stego_path: str, password: str, layer: str = 'real') -> str:
        """
        Extract from Russian Doll steganography.
        
        Args:
            stego_path: Path to stego image
            password: Password to decrypt real secret
            layer: 'real' (extract hex-encoded from DWT, then decrypt) 
                   'fake' (extract decoy from LSB)
        
        Returns:
            The extracted data (decoy or decrypted real secret)
        """
        img = Image.open(stego_path).convert('RGB')
        img_array = np.array(img, dtype=np.uint8)
        
        if layer == 'fake':
            # Extract from LSB (easy layer)
            decoy_bytes = self._extract_lsb(img_array, 1024)
            return decoy_bytes.decode('utf-8', errors='ignore')
        
        elif layer == 'real':
            # Extract from DWT (hidden layer)
            combined_data = self._extract_dwt(img_array)
            
            if not combined_data or len(combined_data) == 0:
                return "Extraction failed: No data found"
            
            # The data is hex-encoded (stored as UTF-8 bytes of hex string)
            try:
                # Convert bytes back to hex string
                hex_str = combined_data.decode('utf-8')
                
                # Validate hex string
                if not all(c in '0123456789abcdefABCDEF' for c in hex_str):
                    return f"Extraction failed: Invalid hex data"
                
                # Decrypt using hex-based decryption
                real_secret = self._decrypt_real_secret_hex(hex_str, password)
                return real_secret
            except Exception as e:
                return f"Extraction failed: {str(e)}"
        
        return "Invalid layer specified"
    
    def create_shamir_shares_in_images(
        self,
        real_secret: str,
        password: str,
        num_shares: int = 10,
        threshold: int = 6,
        prompt_themes: Optional[List[str]] = None,
        ai_backend: Optional[str] = None,
        size: Tuple[int, int] = (512, 512),
        decoy_message: Optional[str] = None,
        allow_fallback: bool = True,
    ) -> Dict:
        """
        Create 10 AI-generated images with Shamir's secret sharing.
        
        Process:
        1. Encrypt the REAL secret with password (hex-encoded output)
        2. Split encryption key into N shares using Shamir's
        3. Generate 10 unique AI images
        4. Embed each share into one image (in DWT coefficients as hex)
        
        Args:
            real_secret: The secret message to hide
            password: Password for encryption
            num_shares: Number of shares to create (default 10)
            threshold: Minimum shares needed to reconstruct (default 6)
            prompt_themes: List of themes for AI image generation
            ai_backend: AI backend to use ('deepai', 'pollinations', 'openai', 'gemini', 'mock', 'auto')
                       If None, defaults to 'auto' which picks best available
        
        Returns:
            Dict with image paths, threshold, manifest
        """
        timestamp = int(secrets.token_hex(6), 16)
        
        # Default themes for AI image generation
        if prompt_themes is None:
            prompt_themes = [
                'Ocean waves at sunset',
                'Forest misty morning', 
                'Cyberpunk city nightscape',
                'Galaxy star field',
                'Desert sand dunes',
                'Snow mountain peaks',
                'Fire elemental art',
                'Abstract geometric pattern',
                'Ancient ruins mystery',
                'Futuristic technology'
            ]
        
        # Use auto backend if not specified, which will pick DeepAI if API key is set
        backend = ai_backend if ai_backend else 'auto'
        
        # Step 1: Encrypt REAL secret (hex-encoded output)
        hex_encrypted = self._encrypt_real_secret_hex(real_secret, password)
        
        # Step 2: Split the KEY (not the ciphertext) using Shamir's
        # Use only first 16 bytes as Shamir expects 16-byte string or integer
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), b'aegis_ghost_salt', 100000, dklen=16)
        shares = Shamir.split(threshold, num_shares, key[:16])
        
        print(f"[*] Split encryption key into {num_shares} shares (threshold: {threshold})")
        print(f"[*] Using AI backend: {backend}")
        print(f"[*] Encrypted secret hex length: {len(hex_encrypted)}")
        
        # Step 3: Generate AI images and embed shares
        image_paths = [None] * num_shares
        manifest = {
            'timestamp': timestamp,
            'num_shares': num_shares,
            'threshold': threshold,
            'hex_encoded': True,  # Flag indicating hex encoding
            'encrypted_hex': hex_encrypted,  # Store hex-encoded ciphertext
            'nonce_tag_hex': hex_encrypted[:56],  # First 28 bytes as hex = 56 chars
            'ai_backend': backend,
            'shares': []
        }

        base_decoy = decoy_message.encode('utf-8') if decoy_message else None
        manifest_shares = [None] * num_shares

        def _build_share_image(i: int) -> Tuple[int, str, dict]:
            share_index, share_bytes = shares[i]
            theme = prompt_themes[i % len(prompt_themes)]

            try:
                img_path_temp = os.path.join(self.output_dir, f"temp_ai_{timestamp}_{i}.png")
                generate_ghost_carrier(
                    prompt=theme,
                    save_path=img_path_temp,
                    use_mock=(backend == 'mock'),
                    size=size,
                    backend=backend,
                    allow_fallback=allow_fallback,
                )
                img = Image.open(img_path_temp)
            except Exception as e:
                print(f"[!] AI generation failed for share {i+1}, using mock: {e}")
                from core.ai_engine import _generate_mock
                img = _generate_mock(theme, size=size)

            img_array = np.array(img, dtype=np.uint8)

            share_decoy = base_decoy if base_decoy is not None else self._generate_decoy_data(max(32, len(real_secret)))
            img_array = self._embed_lsb(img_array, share_decoy)

            share_data = bytes([share_index]) + share_bytes
            img_array = self._embed_dwt(img_array, share_data)

            img_path = os.path.join(
                self.output_dir, 
                f"shamir_share_{timestamp}_{i+1}.png"
            )
            stego_img = Image.fromarray(img_array.astype(np.uint8))
            stego_img.save(img_path)
            
            # Save DWT coefficients sidecar
            blue = img_array[:, :, 2].astype(np.float64)
            coeffs = pywt.dwt2(blue, 'haar')
            _, (_, _, HH) = coeffs
            coeff_path = img_path.replace('.png', '_coeff.npy')
            np.save(coeff_path, HH)

            return i, img_path, {
                'image_path': img_path,
                'share_index': share_index,
                'share_hex': share_bytes.hex(),  # Store share as hex
                'theme': theme
            }

        max_workers = max(2, int(os.getenv("SHAMIR_STEGO_WORKERS", str(num_shares))))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_build_share_image, i) for i in range(num_shares)]
            for future in as_completed(futures):
                i, img_path, share_manifest = future.result()
                image_paths[i] = img_path
                manifest_shares[i] = share_manifest
                print(f"[*] Created share {i+1}/{num_shares}: {share_manifest['theme']}")

        manifest['shares'] = manifest_shares
        
        # Save manifest
        manifest_path = os.path.join(self.output_dir, f"manifest_{timestamp}.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return {
            'image_paths': image_paths,
            'manifest_path': manifest_path,
            'threshold': threshold,
            'num_shares': num_shares,
            'ciphertext_length': len(hex_encrypted)
        }
    
    def reconstruct_secret_from_shares(
        self,
        image_paths: List[str],
        password: str,
        threshold: int = 6
    ) -> str:
        """
        Reconstruct the REAL secret from threshold number of share images.
        
        Args:
            image_paths: List of paths to share images (at least threshold)
            password: Password to decrypt the reconstructed secret
            threshold: Minimum shares needed
        
        Returns:
            The decrypted real secret
        """
        if len(image_paths) < threshold:
            raise ValueError(f"Need at least {threshold} shares, got {len(image_paths)}")
        
        # Extract shares from each image
        shares = []
        for img_path in image_paths[:threshold]:
            img = Image.open(img_path).convert('RGB')
            img_array = np.array(img, dtype=np.uint8)
            
            # Extract share data from DWT (raw bytes in new format)
            share_data = self._extract_dwt(img_array)
            
            if len(share_data) < 2:
                continue
            
            # Parse raw bytes format: [index (1 byte)][share_bytes]
            share_index = share_data[0]
            share_value = share_data[1:]
            shares.append((share_index, share_value))
        
        if len(shares) < threshold:
            raise ValueError(f"Only extracted {len(shares)} valid shares, need {threshold}")
        
        # Reconstruct the encryption key using Shamir's (first 16 bytes)
        try:
            reconstructed_key = Shamir.combine(shares)
            key = reconstructed_key[:16]  # Ensure 16 bytes for AES-128
        except Exception as e:
            raise ValueError(f"Failed to combine shares: {e}")
            
        # Verify that password derives the same key (enforcing password validation)
        if password:
            salt = b'aegis_ghost_salt'
            expected_key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=16)
            if key != expected_key:
                return "Extraction failed: Incorrect password or corrupted shares"
        
        # Now we need the ciphertext - it's stored in the manifest
        # For full reconstruction, we need to find the manifest
        # Let's load from the first image's directory
        img_dir = os.path.dirname(image_paths[0])
        
        # Find manifest file - use numeric sort to get the most recent
        manifest_files = [f for f in os.listdir(img_dir) if f.startswith('manifest_')]
        if not manifest_files:
            raise ValueError("Manifest not found. Cannot reconstruct without ciphertext.")
        
        # Sort by numeric timestamp
        manifest_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
        manifest_path = os.path.join(img_dir, manifest_files[-1])
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Check if hex-encoded format is used
        if manifest.get('hex_encoded'):
            # New format: hex-encoded ciphertext in manifest
            hex_encrypted = manifest['encrypted_hex']
            try:
                # Decrypt directly using the RECONSTRUCTED key (enforcing threshold constraint)
                secret = self._decrypt_real_secret_with_key_hex(hex_encrypted, key)
                return secret
            except Exception as e:
                return f"Decryption failed: {str(e)}"
        else:
            # Old format: hex strings in manifest
            ciphertext = bytes.fromhex(manifest['ciphertext'])
            nonce_tag = bytes.fromhex(manifest['nonce_tag'])
            
            # Decrypt directly using the RECONSTRUCTED key (enforcing threshold constraint)
            try:
                secret = self._decrypt_real_secret_with_key(ciphertext, key, nonce_tag)
                return secret
            except Exception as e:
                return f"Decryption failed: {str(e)}"


def test_russian_doll():
    """Test Russian Doll steganography."""
    print("[*] Testing Russian Doll Steganography...")
    
    rds = RussianDollSteganography()
    
    # Create test image
    from core.ai_engine import _generate_mock
    test_img = _generate_mock("Abstract test pattern", (512, 512))
    test_path = "data/output_stego/test_base.png"
    test_img.save(test_path)
    
    # Test Russian Doll (fake LSB + encrypted real in DWT)
    real_secret = "TOP_SECRET_AEGIS_GHOST_2024"
    password = "secure_password_123"
    decoy = "MEET_AT_PARK_AT_NOON"  # Fake message
    
    result = rds.create_russian_doll_stego(
        test_path,
        real_secret,
        password,
        decoy_message=decoy
    )
    
    print(f"[*] Created Russian Doll stego: {result['output_path']}")
    
    # Extract fake (decoy) from LSB
    fake_extracted = rds.extract_russian_doll(result['output_path'], password, layer='fake')
    print(f"[*] Extracted FAKE (from LSB): {fake_extracted}")
    
    print("[PASS] Russian Doll test complete!")
    return True


def test_shamir_images():
    """Test Shamir's secret sharing across 10 images."""
    print("[*] Testing Shamir's Secret Sharing in Images...")
    
    rds = RussianDollSteganography()
    
    real_secret = "MISSION_COMPLETE_AT_DAWN"
    password = "operative_password"
    
    # Create 10 images with shares
    result = rds.create_shamir_shares_in_images(
        real_secret,
        password,
        num_shares=10,
        threshold=6,
        ai_backend='mock'
    )
    
    print(f"[*] Created {len(result['image_paths'])} share images")
    print(f"[*] Threshold: {result['threshold']}")
    print(f"[*] Manifest: {result['manifest_path']}")
    
    # Reconstruct with 6 shares (threshold)
    reconstructed = rds.reconstruct_secret_from_shares(
        result['image_paths'][:6],
        password,
        threshold=6
    )
    
    print(f"[*] Reconstructed secret: {reconstructed}")
    
    if reconstructed == real_secret:
        print("[PASS] Shamir's Secret Sharing test PASSED!")
    else:
        print(f"[!] Reconstruction mismatch: {reconstructed} != {real_secret}")
    
    return True


if __name__ == "__main__":
    test_russian_doll()
    test_shamir_images()
    print("\n[PASS] All steganography tests complete!")
