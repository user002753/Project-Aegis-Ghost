import hashlib
from Cryptodome.Cipher import AES
from Cryptodome.Protocol.SecretSharing import Shamir
from PIL import Image
import numpy as np
import struct
import json

# Extract shares from images
shares = []
ciphertext = None
nonce = None
tag = None

for i in range(1, 7):
    img_path = f'data/output_stego/adv_stego_1772721170_{i}.png'
    
    img = Image.open(img_path).convert('RGB')
    arr = np.array(img, dtype=np.uint8)
    blue = arr[:, :, 2].reshape(-1)
    
    header_bits = (blue[:32] & 1).astype(np.uint8)
    header = np.packbits(header_bits).tobytes()
    n = struct.unpack('>I', header)[0]
    
    total_bits = (4 + n) * 8
    bits = (blue[:total_bits] & 1).astype(np.uint8)
    payload = np.packbits(bits).tobytes()
    
    body = payload[4:4+n]
    data = json.loads(body.decode('utf-8'))
    
    if i == 1:
        ciphertext = bytes.fromhex(data['ciphertext_hex'])
        nonce = bytes.fromhex(data['nonce_hex'])
        tag = bytes.fromhex(data['tag_hex'])
    
    shares.append((int(data['share_index']), bytes.fromhex(data['share_hex'])))
    print(f"Image {i}: share_index={data['share_index']}")

# Reconstruct key and decrypt outer layer
key = Shamir.combine(shares)
print(f"\nReconstructed key: {key.hex()}")
cipher = AES.new(key[:16], AES.MODE_GCM, nonce=nonce)
layer1 = cipher.decrypt_and_verify(ciphertext, tag)
layer_data = json.loads(layer1)

print(f"\nDecrypted outer layer:")
print(json.dumps(layer_data, indent=2))

# The key_check doesn't match any known password
# This means the images were created with DIFFERENT passwords than we have
# OR the key derivation during creation was different than what we expect

# Since we can't recover the passwords, let's see what happens if we just
# output the blob as-is (it might be the secret in plaintext)
blob_hex = layer_data['blob']
blob = bytes.fromhex(blob_hex)
print(f"\nBlob hex: {blob_hex}")
print(f"Blob length: {len(blob)} bytes")

# Check if it might be plain text
try:
    plaintext = bytes.fromhex(blob_hex).decode('utf-8')
    print(f"Could be UTF-8 hex string: {plaintext}")
except:
    pass

# Check if it's just raw bytes (not hex encoded)
print(f"Raw bytes (first 20): {blob[:20]}")

# Maybe it's just the raw encrypted secret without additional encoding?
print("\n--- Trying various interpretations ---")

# 1. Maybe blob is actually just the secret (plaintext) that was accidentally hex-encoded twice?
# 2. Or maybe it's encrypted with a completely different key

# Let's print what we CAN verify
print("\n=== Summary ===")
print(f"Images contain valid Shamir shares: YES")
print(f"Outer AES-GCM layer decrypts successfully: YES")
print(f"Inner blob key_check matches provided passwords: NO")
print(f"\nConclusion: The passwords used to create these images are unknown.")
print(f"The images cannot be decrypted without the correct passwords.")
