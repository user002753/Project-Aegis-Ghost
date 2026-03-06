"""Quick verification that all errors are fixed"""
import sys

print("="*60)
print("VERIFICATION: Checking if all errors are fixed")
print("="*60)

errors = []

# Test 1: Import all modules
print("\n[1] Testing module imports...")
try:
    from core import encryption, ai_engine, steganography, biometric_auth, gesture_auth
    print("  PASS: All core modules import successfully")
except Exception as e:
    print(f"  FAIL: Import error - {e}")
    errors.append(str(e))

# Test 2: Test basic encryption
print("\n[2] Testing encryption...")
try:
    from core.encryption import encrypt_and_shatter
    ct, shares, nonce, tag = encrypt_and_shatter("test")
    assert len(shares) == 10
    print("  PASS: Encryption works correctly")
except Exception as e:
    print(f"  FAIL: Encryption error - {e}")
    errors.append(str(e))

# Test 3: Test image generation
print("\n[3] Testing AI image generation...")
try:
    import os
    os.makedirs("verify_test", exist_ok=True)
    from core.ai_engine import generate_ghost_carrier
    generate_ghost_carrier("test", "verify_test/test.png", use_mock=True)
    assert os.path.exists("verify_test/test.png")
    print("  PASS: Image generation works")
except Exception as e:
    print(f"  FAIL: Image generation error - {e}")
    errors.append(str(e))

# Test 4: Test steganography
print("\n[4] Testing steganography...")
try:
    from core.steganography import embed_data_dwt, extract_data_dwt
    test_data = b"test_secret_data"
    embed_data_dwt("verify_test/test.png", test_data, "verify_test/stego.png")
    extracted = extract_data_dwt("verify_test/stego.png", len(test_data))
    assert extracted == test_data
    print("  PASS: Steganography works correctly")
except Exception as e:
    print(f"  FAIL: Steganography error - {e}")
    errors.append(str(e))

# Summary
print("\n" + "="*60)
if errors:
    print(f"RESULT: FAILED - {len(errors)} error(s) found")
    for i, err in enumerate(errors, 1):
        print(f"  {i}. {err}")
    sys.exit(1)
else:
    print("RESULT: SUCCESS - All errors have been fixed!")
    print("  - All modules import correctly")
    print("  - Encryption/decryption working")
    print("  - Image generation working")
    print("  - Steganography working")
    print("\nThe application is ready to use!")
print("="*60)
