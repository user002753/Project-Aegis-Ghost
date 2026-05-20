#!/usr/bin/env python3
"""
Test script to understand the exact bit extraction pattern used in Russian Doll steganography.
"""

import numpy as np
from PIL import Image
import struct

def test_bit_extraction():
    """Test the exact bit extraction pattern."""
    
    # Create a simple test image
    img = Image.new('RGB', (512, 512), color='white')
    img_array = np.array(img, dtype=np.uint8)
    
    # Test data to embed
    test_data = b"SECRET_TEST_DATA_12345"
    print(f"Original data: {test_data}")
    print(f"Original length: {len(test_data)}")
    
    # Embed using the same method as Russian Doll
    result = embed_dwt_test(img_array, test_data)
    
    # Extract using the same method
    extracted = extract_dwt_test(result)
    
    print(f"Extracted data: {extracted}")
    print(f"Extracted length: {len(extracted)}")
    print(f"Match: {test_data == extracted}")
    
    return test_data == extracted

def embed_dwt_test(img_array, data):
    """Embed data using the same method as Russian Doll."""
    result = img_array.copy()
    
    # Convert data to bits
    data_bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    
    # Store length in first 32 bits
    length_bits = np.unpackbits(np.array([len(data)], dtype=np.uint32).view(np.uint8))
    
    # Total bits to embed
    total_bits = np.concatenate([length_bits, data_bits])
    
    # Embed in blue channel's LSB
    flat = result[:, :, 2].flatten()
    
    for i in range(len(total_bits)):
        if i >= len(flat):
            break  # Don't overflow
        
        if total_bits[i] == 1:
            flat[i] = flat[i] | 1  # Set LSB to 1
        else:
            flat[i] = flat[i] & 0xFE  # Set LSB to 0
    
    result[:, :, 2] = flat.reshape(result[:, :, 2].shape)
    
    return result

def extract_dwt_test(img_array):
    """Extract data using the same method as Russian Doll."""
    flat = img_array[:, :, 2].flatten()
    
    # Extract length from first 32 bits
    length_bits = []
    for i in range(32):
        if i >= len(flat):
            break
        length_bits.append(flat[i] & 1)
    
    length = np.packbits(np.array(length_bits, dtype=np.uint8)).view(np.uint32)[0]
    
    print(f"Extracted length: {length}")
    
    # Guard against excessively large lengths
    max_size = len(flat) // 8
    if length > max_size:
        return b''
    
    # Extract data
    data_bits = []
    for i in range(32, min(32 + length * 8, len(flat))):
        data_bits.append(flat[i] & 1)
    
    return np.packbits(np.array(data_bits, dtype=np.uint8)).tobytes()

if __name__ == "__main__":
    success = test_bit_extraction()
    print(f"Test {'PASSED' if success else 'FAILED'}")