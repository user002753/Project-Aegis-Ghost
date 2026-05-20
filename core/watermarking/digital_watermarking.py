"""
Digital Watermarking Module for Project Aegis Ghost
Provides visible and invisible watermarking capabilities
"""

import numpy as np
import pywt
import hashlib
import json
import base64
import struct
import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime
import secrets
import core.encryption as crypto


class DigitalWatermarker:
    """
    Military-grade digital watermarking system
    Supports visible, invisible, and robust watermarks
    """
    
    def __init__(self, key_path='data/watermark.key'):
        self.key_path = key_path
        self.watermark_key = self._load_or_create_key()

    def _load_or_create_key(self):
        """Load a persistent watermark key so verification survives restarts."""
        try:
            key_dir = os.path.dirname(self.key_path)
            if key_dir:
                os.makedirs(key_dir, exist_ok=True)
            if os.path.exists(self.key_path):
                with open(self.key_path, 'rb') as f:
                    key = f.read()
                if len(key) == 32:
                    return key
            key = secrets.token_bytes(32)
            with open(self.key_path, 'wb') as f:
                f.write(key)
            return key
        except Exception:
            # Safe fallback: keep runtime behavior even if filesystem is restricted.
            return secrets.token_bytes(32)

    def _embed_payload_lsb(self, image_path, output_path, payload: bytes):
        """Embed bytes in blue-channel LSBs with deterministic recovery."""
        img = Image.open(image_path).convert('RGB')
        arr = np.array(img, dtype=np.uint8)
        h, w, _ = arr.shape
        capacity_bits = h * w  # one bit per pixel (blue channel)
        payload_bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
        if len(payload_bits) > capacity_bits:
            raise ValueError(
                f"Watermark payload too large: need {len(payload_bits)} bits, capacity is {capacity_bits} bits"
            )

        blue_flat = arr[:, :, 2].reshape(-1)
        blue_flat[:len(payload_bits)] = (blue_flat[:len(payload_bits)] & 0xFE) | payload_bits
        arr[:, :, 2] = blue_flat.reshape(h, w)
        Image.fromarray(arr).save(output_path, 'PNG')

    def _extract_payload_lsb(self, image_path):
        """Extract length-prefixed payload from blue-channel LSBs."""
        img = Image.open(image_path).convert('RGB')
        arr = np.array(img, dtype=np.uint8)
        blue_flat = arr[:, :, 2].reshape(-1)

        # First 32 bits = big-endian payload length (encrypted bytes length)
        if blue_flat.size < 32:
            raise ValueError("Image too small for watermark header")

        header_bits = (blue_flat[:32] & 1).astype(np.uint8)
        header_bytes = np.packbits(header_bits).tobytes()
        encrypted_length = struct.unpack(">I", header_bytes)[0]
        if encrypted_length < 16 or encrypted_length > 65536:
            raise ValueError("Invalid watermark length header")

        total_bits = (4 + encrypted_length) * 8
        if blue_flat.size < total_bits:
            raise ValueError("Image does not contain full watermark payload")

        payload_bits = (blue_flat[:total_bits] & 1).astype(np.uint8)
        payload = np.packbits(payload_bits).tobytes()
        return payload, encrypted_length

    def _parse_color(self, color):
        """Accept RGB tuple/list or hex color string."""
        if isinstance(color, (tuple, list)) and len(color) >= 3:
            return (int(color[0]), int(color[1]), int(color[2]))
        if isinstance(color, str):
            c = color.strip()
            if c.startswith("#") and len(c) in (4, 7):
                if len(c) == 4:
                    c = "#" + "".join(ch * 2 for ch in c[1:])
                return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
            if "," in c:
                parts = [p.strip() for p in c.split(",")]
                if len(parts) >= 3:
                    return (int(parts[0]), int(parts[1]), int(parts[2]))
        return (255, 255, 255)

    def _load_font(self, font_family, font_size, font_style="normal", font_weight="normal"):
        """Load a scalable font with graceful fallbacks across platforms."""
        family = (font_family or "Arial").strip().lower().replace(" ", "")
        style = (font_style or "normal").strip().lower()
        weight = (font_weight or "normal").strip().lower()
        candidates = []
        if family in ("arial", "helvetica", "verdana", "tahoma"):
            if weight == "bold" and style == "italic":
                candidates += ["arialbi.ttf", "Arial Bold Italic.ttf"]
            elif weight == "bold":
                candidates += ["arialbd.ttf", "Arial Bold.ttf"]
            elif style == "italic":
                candidates += ["ariali.ttf", "Arial Italic.ttf"]
            candidates += ["arial.ttf", "Arial.ttf"]
        elif family in ("timesnewroman", "times"):
            if weight == "bold" and style == "italic":
                candidates += ["timesbi.ttf"]
            elif weight == "bold":
                candidates += ["timesbd.ttf"]
            elif style == "italic":
                candidates += ["timesi.ttf"]
            candidates += ["times.ttf", "Times New Roman.ttf"]
        elif family in ("georgia",):
            candidates += ["georgiab.ttf" if weight == "bold" else "georgia.ttf"]
        elif family in ("couriernew", "courier"):
            candidates += ["courbd.ttf" if weight == "bold" else "cour.ttf", "Courier New.ttf"]
        elif family in ("impact",):
            candidates += ["impact.ttf"]

        # Reliable scalable fallback bundled by Pillow.
        candidates += ["DejaVuSans-Bold.ttf" if weight == "bold" else "DejaVuSans.ttf"]
        for name in candidates:
            try:
                return ImageFont.truetype(name, int(font_size))
            except Exception:
                continue
        return ImageFont.load_default()
    
    def create_visible_watermark(
        self,
        image_path,
        output_path,
        watermark_text,
        position='bottom-right',
        opacity=0.5,
        font_size=24,
        color=(255, 255, 255),
        font_family="Arial",
        font_style="normal",
        font_weight="normal",
        text_shadow=True,
        rotation=0.0,
        logo_path=None,
        logo_position="top-right",
        logo_size=50,
        logo_opacity=0.8,
        doodle_path=None,
    ):
        """
        Add visible watermark to image
        
        Args:
            image_path: Path to input image
            output_path: Path to save watermarked image
            watermark_text: Text to display as watermark
            position: Position (top-left, top-right, bottom-left, bottom-right, center)
            opacity: Opacity of watermark (0-1)
            font_size: Size of watermark text
            color: RGB tuple for text color
        """
        img = Image.open(image_path).convert('RGBA')
        
        # Create watermark layer
        watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)
        font = self._load_font(font_family, font_size, font_style=font_style, font_weight=font_weight)
        rgb = self._parse_color(color)

        # Measure text and prepare a dedicated text layer so rotation is preserved.
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Calculate position
        padding = 20
        if position == 'top-left':
            x, y = padding, padding
        elif position == 'top-right':
            x, y = img.size[0] - text_width - padding, padding
        elif position == 'bottom-left':
            x, y = padding, img.size[1] - text_height - padding
        elif position == 'bottom-right':
            x, y = img.size[0] - text_width - padding, img.size[1] - text_height - padding
        else:  # center
            x, y = (img.size[0] - text_width) // 2, (img.size[1] - text_height) // 2
        
        text_layer = Image.new('RGBA', (max(1, text_width + 8), max(1, text_height + 8)), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)
        if text_shadow:
            shadow_offset = max(1, int(math.ceil(font_size * 0.08)))
            shadow_color = (0, 0, 0, int(255 * opacity))
            text_draw.text((shadow_offset, shadow_offset), watermark_text, font=font, fill=shadow_color)
        text_color = (rgb[0], rgb[1], rgb[2], int(255 * opacity))
        text_draw.text((0, 0), watermark_text, font=font, fill=text_color)

        rot = float(rotation or 0.0)
        if abs(rot) > 0.001:
            text_layer = text_layer.rotate(rot, expand=True, resample=Image.Resampling.BICUBIC)
        watermark.alpha_composite(text_layer, (x, y))

        # Optional logo overlay
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                target = max(8, int(logo_size))
                logo.thumbnail((target, target), Image.Resampling.LANCZOS)
                if logo_opacity < 1:
                    alpha = logo.getchannel("A").point(lambda px: int(px * max(0.0, min(1.0, float(logo_opacity)))))
                    logo.putalpha(alpha)
                lw, lh = logo.size
                pad = 20
                if logo_position == "top-left":
                    lx, ly = pad, pad
                elif logo_position == "top-right":
                    lx, ly = img.size[0] - lw - pad, pad
                elif logo_position == "bottom-left":
                    lx, ly = pad, img.size[1] - lh - pad
                elif logo_position == "bottom-right":
                    lx, ly = img.size[0] - lw - pad, img.size[1] - lh - pad
                else:
                    lx, ly = (img.size[0] - lw) // 2, (img.size[1] - lh) // 2
                watermark.alpha_composite(logo, (int(lx), int(ly)))
            except Exception:
                pass

        # Optional doodle/canvas overlay
        if doodle_path and os.path.exists(doodle_path):
            try:
                doodle = Image.open(doodle_path).convert("RGBA")
                if doodle.size != img.size:
                    doodle = doodle.resize(img.size, Image.Resampling.LANCZOS)
                watermark.alpha_composite(doodle, (0, 0))
            except Exception:
                pass
        
        # Composite watermark onto image
        watermarked = Image.alpha_composite(img, watermark)
        watermarked = watermarked.convert('RGB')
        watermarked.save(output_path, 'PNG')
        
        return {
            'status': 'success',
            'message': 'Visible watermark added',
            'position': position,
            'opacity': opacity,
            'text': watermark_text,
            'font_size': int(font_size),
            'font_family': font_family,
            'font_style': font_style,
            'font_weight': font_weight,
            'text_shadow': bool(text_shadow),
            'rotation': float(rotation),
            'color': rgb,
        }
    
    def create_invisible_watermark(self, image_path, output_path, secret_data, 
                                   owner_id="AEGIS-GHOST"):
        """
        Add invisible watermark using DWT steganography
        
        Args:
            image_path: Path to input image
            output_path: Path to save watermarked image
            secret_data: Data to embed (will be encrypted)
            owner_id: Owner identifier
            
        Returns:
            Watermark metadata for verification
        """
        # Create watermark metadata
        metadata = {
            'owner_id': owner_id,
            'timestamp': datetime.utcnow().isoformat(),
            'data_hash': hashlib.sha256(secret_data.encode()).hexdigest(),
            'version': '1.0'
        }
        
        # Encrypt the watermark data
        encrypted_watermark = crypto.encrypt_aes_gcm(
            json.dumps(metadata).encode(), 
            self.watermark_key
        )

        # Prefix encrypted payload with 4-byte length for deterministic extraction.
        payload = struct.pack(">I", len(encrypted_watermark)) + encrypted_watermark
        
        # Embed using pixel LSB for robust decode after upload/download cycles.
        self._embed_payload_lsb(image_path, output_path, payload)
        
        # Save metadata for verification
        metadata_path = output_path.replace('.png', '_watermark.json')
        with open(metadata_path, 'w') as f:
            json.dump({
                'metadata': metadata,
                'key_hash': hashlib.sha256(self.watermark_key).hexdigest()[:16],
                'encrypted_length': len(encrypted_watermark),
                'payload_length': len(payload)
            }, f, indent=2)
        
        return {
            'status': 'success',
            'message': 'Invisible watermark embedded',
            'owner_id': owner_id,
            'timestamp': metadata['timestamp'],
            'metadata_path': metadata_path
        }
    
    def verify_watermark(self, image_path, expected_owner=None):
        """
        Verify invisible watermark in image
        
        Args:
            image_path: Path to watermarked image
            expected_owner: Expected owner ID (optional)
            
        Returns:
            Verification result
        """
        try:
            from core.steganography import extract_data_dwt

            # Primary path: robust blue-channel LSB extraction.
            try:
                payload, encrypted_length = self._extract_payload_lsb(image_path)
                encrypted_data = payload[4:4 + encrypted_length]
                decrypted = crypto.decrypt_aes_gcm(encrypted_data, self.watermark_key)
                metadata = json.loads(decrypted.decode())
                result = {
                    'verified': True,
                    'owner_id': metadata['owner_id'],
                    'timestamp': metadata['timestamp'],
                    'data_hash': metadata['data_hash'],
                    'version': metadata['version']
                }
                if expected_owner and metadata['owner_id'] != expected_owner:
                    result['verified'] = False
                    result['warning'] = 'Owner ID mismatch'
                return result
            except Exception:
                pass

            # Primary path: read length-prefixed encrypted payload.
            try:
                header = extract_data_dwt(image_path, 4)
                encrypted_length = struct.unpack(">I", header[:4])[0]
                if 16 <= encrypted_length <= 65536:
                    payload = extract_data_dwt(image_path, 4 + encrypted_length)
                    encrypted_data = payload[4:4 + encrypted_length]
                    decrypted = crypto.decrypt_aes_gcm(encrypted_data, self.watermark_key)
                    metadata = json.loads(decrypted.decode())
                    result = {
                        'verified': True,
                        'owner_id': metadata['owner_id'],
                        'timestamp': metadata['timestamp'],
                        'data_hash': metadata['data_hash'],
                        'version': metadata['version']
                    }
                    if expected_owner and metadata['owner_id'] != expected_owner:
                        result['verified'] = False
                        result['warning'] = 'Owner ID mismatch'
                    return result
            except Exception:
                pass

            # Backward-compatibility fallback for older images without length prefix.
            for length in [128, 144, 160, 176, 192, 208]:
                try:
                    encrypted_data = extract_data_dwt(image_path, length)
                    decrypted = crypto.decrypt_aes_gcm(encrypted_data, self.watermark_key)
                    metadata = json.loads(decrypted.decode())
                    result = {
                        'verified': True,
                        'owner_id': metadata['owner_id'],
                        'timestamp': metadata['timestamp'],
                        'data_hash': metadata['data_hash'],
                        'version': metadata['version']
                    }
                    if expected_owner and metadata['owner_id'] != expected_owner:
                        result['verified'] = False
                        result['warning'] = 'Owner ID mismatch'
                    return result
                except Exception:
                    continue

            return {
                'verified': False,
                'message': 'No valid watermark found'
            }
            
        except Exception as e:
            return {
                'verified': False,
                'message': f'Verification failed: {str(e)}'
            }
    
    def create_robust_watermark(self, image_path, output_path, watermark_data, 
                                strength=1.0):
        """
        Create robust watermark resistant to attacks
        Uses multiple embedding techniques
        
        Args:
            image_path: Input image path
            output_path: Output path
            watermark_data: Data to embed
            strength: Embedding strength (0.1 - 2.0)
        """
        img = Image.open(image_path).convert('RGB')
        img_arr = np.array(img, dtype=np.float32)
        
        # Create a robust watermark using DCT
        # Divide image into blocks and embed in frequency domain
        h, w = img_arr.shape[:2]
        block_size = 8
        
        # Convert watermark to binary
        data_bytes = watermark_data.encode('utf-8')
        bits = np.unpackbits(np.frombuffer(data_bytes, dtype=np.uint8))
        
        # Create binary watermark pattern
        watermark_pattern = np.zeros((h, w), dtype=np.float32)
        
        # Embed in DCT domain of image blocks
        bit_idx = 0
        for i in range(0, h - block_size + 1, block_size):
            for j in range(0, w - block_size + 1, block_size):
                if bit_idx >= len(bits):
                    break
                    
                block = img_arr[i:i+block_size, j:j+block_size, 0]
                
                # Apply 2D DCT
                from scipy.fftpack import dct, idct
                dct_block = dct(dct(block.T, norm='ortho').T, norm='ortho')
                
                # Modify mid-frequency coefficients
                mid_freq_idx = 3
                if bits[bit_idx] == 1:
                    dct_block[mid_freq_idx, mid_freq_idx] *= (1 + 0.1 * strength)
                else:
                    dct_block[mid_freq_idx, mid_freq_idx] *= (1 - 0.1 * strength)
                
                # Inverse DCT
                block_reconstructed = idct(idct(dct_block.T, norm='ortho').T, norm='ortho')
                img_arr[i:i+block_size, j:j+block_size, 0] = block_reconstructed
                
                bit_idx += 1
            
            if bit_idx >= len(bits):
                break
        
        # Clip values and save
        img_arr = np.clip(img_arr, 0, 255)
        watermarked = Image.fromarray(np.uint8(img_arr))
        watermarked.save(output_path, 'PNG')
        
        return {
            'status': 'success',
            'message': 'Robust watermark embedded',
            'strength': strength,
            'bits_embedded': bit_idx
        }
    
    def extract_robust_watermark(self, image_path, num_bits):
        """
        Extract robust watermark from image
        
        Args:
            image_path: Path to watermarked image
            num_bits: Number of bits to extract
            
        Returns:
            Extracted watermark data
        """
        try:
            from scipy.fftpack import dct, idct
            
            img = Image.open(image_path).convert('RGB')
            img_arr = np.array(img, dtype=np.float32)
            h, w = img_arr.shape[:2]
            block_size = 8
            
            extracted_bits = []
            mid_freq_idx = 3
            
            for i in range(0, h - block_size + 1, block_size):
                for j in range(0, w - block_size + 1, block_size):
                    if len(extracted_bits) >= num_bits:
                        break
                        
                    block = img_arr[i:i+block_size, j:j+block_size, 0]
                    dct_block = dct(dct(block.T, norm='ortho').T, norm='ortho')
                    
                    # Extract bit from mid-frequency coefficient
                    coeff = dct_block[mid_freq_idx, mid_freq_idx]
                    bit = 1 if coeff > 128 else 0
                    extracted_bits.append(bit)
            
            # Convert bits to bytes
            bits_array = np.array(extracted_bits[:num_bits], dtype=np.uint8)
            padding = (8 - (num_bits % 8)) % 8
            if padding > 0:
                bits_array = np.concatenate([np.zeros(padding, dtype=np.uint8), bits_array])
            
            return np.packbits(bits_array).tobytes().decode('utf-8', errors='ignore').strip()
            
        except Exception as e:
            return f"Extraction failed: {str(e)}"
    
    def batch_watermark(self, image_paths, output_dir, watermark_text, 
                        visible=True, invisible=True):
        """
        Apply watermarks to multiple images
        
        Args:
            image_paths: List of image paths
            output_dir: Output directory
            watermark_text: Text for visible watermark
            visible: Add visible watermark
            invisible: Add invisible watermark
            
        Returns:
            Processing results
        """
        results = []
        
        for idx, image_path in enumerate(image_paths):
            filename = f"watermarked_{idx}_{hashlib.md5(image_path.encode()).hexdigest()[:8]}.png"
            output_path = os.path.join(output_dir, filename)
            
            result = {
                'input': image_path,
                'output': output_path,
                'status': 'pending'
            }
            
            try:
                if visible:
                    self.create_visible_watermark(
                        image_path, output_path, watermark_text
                    )
                
                if invisible:
                    # Use same output path for invisible if visible not applied
                    if not visible:
                        self.create_invisible_watermark(
                            image_path, output_path, watermark_text
                        )
                    else:
                        # Create invisible watermark in separate file
                        invisible_path = output_path.replace('.png', '_invisible.png')
                        self.create_invisible_watermark(
                            image_path, invisible_path, watermark_text
                        )
                        result['invisible_output'] = invisible_path
                
                result['status'] = 'success'
                
            except Exception as e:
                result['status'] = 'failed'
                result['error'] = str(e)
            
            results.append(result)
        
        return results


# Utility functions
def generate_watermark_signature(user_id, file_hash, timestamp):
    """
    Generate cryptographic signature for watermark
    
    Args:
        user_id: User identifier
        file_hash: Hash of protected file
        timestamp: Creation timestamp
        
    Returns:
        Base64 encoded signature
    """
    data = f"{user_id}:{file_hash}:{timestamp}"
    signature = hashlib.sha256(data.encode()).hexdigest()
    return base64.b64encode(signature.encode()).decode()


def analyze_image_forensic(image_path):
    """
    Perform forensic analysis on image
    
    Args:
        image_path: Path to image
        
    Returns:
        Forensic analysis report
    """
    img = Image.open(image_path)
    img_arr = np.array(img)
    
    report = {
        'dimensions': img.size,
        'mode': img.mode,
        'format': img.format,
        'color_channels': len(img.getbands()),
        'has_alpha': img.mode in ('RGBA', 'LA'),
        'file_hash': hashlib.sha256(img_arr.tobytes()).hexdigest()[:16],
        'noise_level': np.std(img_arr).item(),
        'brightness': np.mean(img_arr).item(),
        'anomalies': []
    }
    
    # Check for manipulation
    if report['noise_level'] < 1:
        report['anomalies'].append('Unusually low noise - possible editing')
    
    # Check for aspect ratio
    if img.size[0] / img.size[1] > 4 or img.size[1] / img.size[0] > 4:
        report['anomalies'].append('Unusual aspect ratio')
    
    return report
