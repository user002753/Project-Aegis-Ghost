"""Test script for lockdown functionality"""
import os
import sys

# Ensure data directories exist
os.makedirs("data/output_stego", exist_ok=True)

# Test lockdown with a secret message
print("Testing lockdown functionality...")
print("="*50)

from core.encryption import encrypt_and_shatter, save_metadata
from core.ai_engine import generate_ghost_carrier
from core.steganography import embed_data_dwt

secret_message = "Test secret: Mission at VJEC 0900"
print(f"Secret message: {secret_message}")

# 1. Encrypt and shatter
print("\n[Step 1] Encrypting and shattering...")
ciphertext, shares, nonce, tag = encrypt_and_shatter(secret_message)
print(f"✓ Created {len(shares)} shares")

# 2. Save metadata
save_metadata(ciphertext, nonce, tag)
print("✓ Metadata saved")

# 3. Generate ghost images and embed
print("\n[Step 2] Generating ghost images and embedding shares...")
for i, (idx, share) in enumerate(shares[:3], 1):  # Test with just 3 shares
    path = f"data/output_stego/ghost_{idx}.png"
    print(f"  Processing share {i}/3...")
    generate_ghost_carrier(f"Ghost_{idx}", path, use_mock=True)
    embed_data_dwt(path, share, path)
    print(f"  ✓ Share {i} embedded")

print("\n" + "="*50)
print("✓ Lockdown test completed successfully!")
print("Files created in data/output_stego/")
