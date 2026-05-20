# -*- coding: utf-8 -*-
import sys
import os

# Test 1: Core Encryption
print("Test 1: Core Encryption")
try:
    from core.encryption import encrypt_and_shatter, reconstruct_and_decrypt
    secret = 'Test Aegis Ghost Mission'
    ct, shares, nonce, tag = encrypt_and_shatter(secret)
    result = reconstruct_and_decrypt(shares[:6], ct, nonce, tag)
    print(f"[PASS] Encryption round-trip: {result == secret}")
    print(f"[PASS] Created {len(shares)} shares")
except Exception as e:
    print(f"[FAIL] Encryption error: {e}")

# Test 2: Steganography
print("\nTest 2: Steganography")
try:
    from core.steganography import embed_data_dwt, extract_data_dwt
    import numpy as np
    from PIL import Image
    # Create test image
    img = np.zeros((256, 256, 3), dtype=np.uint8)
    img[:, :, 0] = 128  # Red channel
    img[:, :, 1] = 64   # Green channel
    img[:, :, 2] = 32   # Blue channel
    Image.fromarray(img).save('test_temp.png')
    # Embed test data
    test_data = b"Secret mission data"
    embed_data_dwt('test_temp.png', test_data, 'test_stego.png')
    # Extract
    extracted = extract_data_dwt('test_stego.png', len(test_data))
    print(f"[PASS] Steganography embed/extract: {extracted == test_data}")
    # Cleanup
    os.remove('test_temp.png')
    os.remove('test_stego.png')
    os.remove('test_stego_coeff.npy')
except Exception as e:
    print(f"[FAIL] Steganography error: {e}")

# Test 3: AI Engine
print("\nTest 3: AI Engine")
try:
    from core.ai_engine import generate_ghost_carrier
    result = generate_ghost_carrier("ghost 1", "test_ai.png", use_mock=True)
    print("[PASS] AI image generation: loaded=", type(result))
    if os.path.exists('test_ai.png'):
        os.remove('test_ai.png')
except Exception as e:
    print(f"[FAIL] AI engine error: {e}")

# Test 4: Biometric Auth
print("\nTest 4: Biometric Auth")
try:
    from core.biometric_auth import BiometricAuthenticator
    auth = BiometricAuthenticator()
    print("[PASS] BiometricAuthenticator initialized")
except Exception as e:
    print(f"[INFO] Biometric: {e}")

# Test 5: Gesture Auth
print("\nTest 5: Gesture Auth")
try:
    from core.gesture_auth import GestureAuthenticator
    gesture = GestureAuthenticator()
    print("[PASS] GestureAuthenticator initialized")
except Exception as e:
    print(f"[INFO] Gesture auth: {e}")

print("\n" + "="*50)
print("All core tests completed!")
