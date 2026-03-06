#!/usr/bin/env python3
"""
Test script to diagnose steganalysis hidden data extraction issues.
"""

import sys
import os
import numpy as np
from PIL import Image
import io

# Add core to path
sys.path.insert(0, 'core')

from steganalysis import (
    _extract_russian_doll_dwt, 
    _extract_russian_doll_lsb,
    _extract_blue_lsb_length_prefixed,
    _extract_rgb_lsb_stream,
    decode_hidden_data,
    _load_image_array
)

def create_test_image_with_data():
    """Create a test image with embedded data to test extraction."""
    # Create a simple test image
    img = Image.new('RGB', (512, 512), color='red')
    img_array = np.array(img, dtype=np.uint8)
    
    # Test data to embed
    test_data = b"SECRET_TEST_DATA_12345"
    
    # Embed in blue channel LSB (like Russian Doll DWT)
    flat = img_array[:, :, 2].flatten()
    
    # Store length in first 32 bits
    length_bits = np.unpackbits(np.array([len(test_data)], dtype=np.uint32).view(np.uint8))
    
    # Convert data to bits
    data_bits = np.unpackbits(np.frombuffer(test_data, dtype=np.uint8))
    
    # Total bits = length (32) + data
    total_bits = np.concatenate([length_bits, data_bits])
    
    # Embed
    for i in range(len(total_bits)):
        if i >= len(flat):
            break
        if total_bits[i] == 1:
            flat[i] = flat[i] | 1  # Set LSB to 1
        else:
            flat[i] = flat[i] & 0xFE  # Set LSB to 0
    
    img_array[:, :, 2] = flat.reshape(img_array[:, :, 2].shape)
    
    # Save test image
    test_img = Image.fromarray(img_array)
    test_img.save('test_stego_image.png')
    
    return 'test_stego_image.png', test_data

def test_extraction_functions():
    """Test all extraction functions."""
    print("=== Testing Steganalysis Extraction Functions ===\n")
    
    # Create test image
    image_path, original_data = create_test_image_with_data()
    print(f"Created test image: {image_path}")
    print(f"Original data: {original_data}")
    print()
    
    # Load image
    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    
    img_arr = _load_image_array(image_bytes)
    
    # Test 1: Russian Doll DWT extraction
    print("1. Testing Russian Doll DWT extraction...")
    try:
        result1 = _extract_russian_doll_dwt(img_arr)
        print(f"   Result: {result1}")
        print(f"   Length: {len(result1) if result1 else 0}")
        print(f"   Matches original: {result1 == original_data}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Test 2: Russian Doll LSB extraction
    print("2. Testing Russian Doll LSB extraction...")
    try:
        result2 = _extract_russian_doll_lsb(img_arr)
        print(f"   Result: {result2}")
        print(f"   Length: {len(result2) if result2 else 0}")
        print(f"   Matches original: {result2 == original_data}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Test 3: Blue LSB length-prefixed extraction
    print("3. Testing Blue LSB length-prefixed extraction...")
    try:
        result3 = _extract_blue_lsb_length_prefixed(img_arr)
        print(f"   Result: {result3}")
        print(f"   Length: {len(result3) if result3 else 0}")
        print(f"   Matches original: {result3 == original_data}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Test 4: Raw RGB LSB stream extraction
    print("4. Testing Raw RGB LSB stream extraction...")
    try:
        result4 = _extract_rgb_lsb_stream(img_arr)
        print(f"   Result: {result4}")
        print(f"   Length: {len(result4) if result4 else 0}")
        print(f"   Contains original: {original_data in result4 if result4 else False}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Test 5: Full decode_hidden_data function
    print("5. Testing full decode_hidden_data function...")
    try:
        result5 = decode_hidden_data(image_bytes, img_arr, image_path=image_path)
        print(f"   Found: {result5.get('found', False)}")
        print(f"   Method: {result5.get('method', 'None')}")
        print(f"   Decoded text: {result5.get('decoded_text', '')}")
        print(f"   Bytes decoded: {result5.get('bytes_decoded', 0)}")
        print(f"   Attempts: {len(result5.get('attempts', []))}")
        
        # Print attempt details
        for i, attempt in enumerate(result5.get('attempts', [])):
            print(f"   Attempt {i+1}: {attempt.get('method', 'Unknown')} - Success: {attempt.get('success', False)}")
            if attempt.get('details'):
                details = attempt['details']
                print(f"     Details: {details}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Clean up
    if os.path.exists(image_path):
        os.remove(image_path)
    
    print("=== Test Complete ===")

if __name__ == "__main__":
    test_extraction_functions()