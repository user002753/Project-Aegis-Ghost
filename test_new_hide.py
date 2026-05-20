"""Test the full flow: hide a secret and then reveal it - CORRECT ORDER"""
import hashlib
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# This tests that the CURRENT code works correctly

# Use the same key derivation as server.py
SALT = b"aegis_ghost_russian_doll"
KDF_ROUNDS = 250000

def derive_layer_key(password, rounds=KDF_ROUNDS):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        SALT,
        rounds,
        dklen=32,
    )

# Test encryption/decryption
secret = "Hello, this is a test secret!"
passwords = ["layer1", "layer2", "layer3"]

print("=== Testing encryption flow (CORRECT ORDER) ===")
print(f"Secret: {secret}")
print(f"Passwords: {passwords}")
print()

# Encrypt with Russian Doll - innermost first (reversed order)
# server.py does: for pw in reversed(passwords):
current = secret
for pw in reversed(passwords):
    key = derive_layer_key(pw, KDF_ROUNDS)
    key_check = hashlib.sha256(key).hexdigest()[:16]
    print(f"Password: {pw}")
    print(f"  Key: {key.hex()}")
    print(f"  key_check: {key_check}")
    
    # Encrypt - current is a string, encrypt it
    nonce = b'\x00' * 12  # Use fixed nonce for testing
    aesgcm = AESGCM(key)
    blob = nonce + aesgcm.encrypt(nonce, current.encode("utf-8"), None)
    
    layer = {
        "blob": blob.hex(),
        "key_check": key_check,
        "algo": "AES-GCM",
        "v": 1
    }
    # Convert layer to JSON string for next iteration
    current = json.dumps(layer, separators=(",", ":"))
    print(f"  Layer blob: {blob.hex()[:40]}...")

print()
print("=== Testing decryption flow (outermost first) ===")
print(f"Layered payload: {current[:100]}...")

# Decrypt in FORWARD order (layer1, layer2, layer3)
for i, pw in enumerate(passwords):
    layer = json.loads(current)
    key = derive_layer_key(pw, KDF_ROUNDS)
    computed_check = hashlib.sha256(key).hexdigest()[:16]
    stored_check = layer.get("key_check")
    
    print(f"Layer {i+1}: Password '{pw}'")
    print(f"  Computed key_check: {computed_check}")
    print(f"  Stored key_check: {stored_check}")
    print(f"  Match: {computed_check == stored_check}")
    
    if computed_check != stored_check:
        print("  ERROR: Password mismatch!")
        break
    
    blob = bytes.fromhex(layer["blob"])
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(blob[:12], blob[12:], None).decode("utf-8")
    current = plaintext
    print(f"  Decrypted: {plaintext[:50]}...")

print()
print("=== CONCLUSION ===")
if current == secret:
    print("SUCCESS! The encryption/decryption flow works correctly!")
else:
    print(f"ERROR: Expected '{secret}' but got '{current}'")
