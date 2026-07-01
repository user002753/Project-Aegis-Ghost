import json
import os
import binascii
import hashlib

try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Protocol.SecretSharing import Shamir
    from Cryptodome.Random import get_random_bytes
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Signature import pkcs1_15
    from Cryptodome.Hash import SHA256
except ImportError:
    from Crypto.Cipher import AES
    from Crypto.Protocol.SecretSharing import Shamir
    from Crypto.Random import get_random_bytes
    from Crypto.PublicKey import RSA
    from Crypto.Signature import pkcs1_15
    from Crypto.Hash import SHA256

def encrypt_and_shatter(secret_text, n_shares=10, threshold=6, password=None):
    # If password is provided, derive 16-byte key using PBKDF2 with 100k rounds of SHA256
    # This aligns the core symmetric key derivation with Section 3.1 of the paper.
    if password:
        salt = b'aegis_ghost_salt'
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=16)
    else:
        key = get_random_bytes(16)  
        
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(secret_text.encode())
    
    shares = Shamir.split(threshold, n_shares, key)
    return ciphertext, shares, cipher.nonce, tag

def reconstruct_and_decrypt(shares, ciphertext, nonce, tag, password=None):
    """Reconstruct AES key from Shamir shares and decrypt ciphertext (AES-GCM).

    shares: list of (index, share_bytes)
    ciphertext: bytes
    nonce: bytes
    tag: bytes
    password: optional password to validate against the reconstructed key
    """
    try:
        key = Shamir.combine(shares)
    except Exception as e:
        raise ValueError(f"Failed to combine shares: {e}")

    if password:
        salt = b'aegis_ghost_salt'
        expected_key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=16)
        if key != expected_key:
            raise ValueError("Decryption failed: Incorrect password or corrupted shares.")

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext.decode()


def biometric_unlock(captured_shares, ciphertext, nonce, tag):
    try:
        return reconstruct_and_decrypt(captured_shares, ciphertext, nonce, tag)
    except Exception as e:
        return f"Extraction Failed: {str(e)}"

def save_metadata(ciphertext, nonce, tag):
    import os
    os.makedirs('data', exist_ok=True)
    with open('data/metadata.json', 'w') as f:
        json.dump({
            "ciphertext": ciphertext.hex(),
            "nonce": nonce.hex(),
            "tag": tag.hex()
        }, f)

def load_metadata():
    with open('data/metadata.json', 'r') as f:
        data = json.load(f)
    return (
        bytes.fromhex(data["ciphertext"]),
        bytes.fromhex(data["nonce"]),
        bytes.fromhex(data["tag"])
    )


def generate_rsa_keypair(private_path='assets/private.pem', public_path='assets/public.pem', bits=2048):
    """Generate an RSA keypair and save to files (PEM).

    Overwrites existing files if present.
    """
    key = RSA.generate(bits)
    private_key = key.export_key()
    public_key = key.publickey().export_key()

    with open(private_path, 'wb') as f:
        f.write(private_key)
    with open(public_path, 'wb') as f:
        f.write(public_key)

    return private_path, public_path


def sign_file(private_path, file_path, out_sig_path=None):
    """Sign the contents of `file_path` using RSA private key and save signature as hex.

    Returns the signature bytes.
    """
    with open(private_path, 'rb') as f:
        key = RSA.import_key(f.read())

    with open(file_path, 'rb') as f:
        data = f.read()

    h = SHA256.new(data)
    signature = pkcs1_15.new(key).sign(h)
    sig_hex = binascii.hexlify(signature).decode()

    if out_sig_path:
        with open(out_sig_path, 'w') as f:
            f.write(sig_hex)

    return signature


def verify_file_signature(public_path, file_path, sig_path_or_hex):
    """Verify signature for file. `sig_path_or_hex` can be a path to a hex file or a hex string.

    Returns True if signature is valid, False otherwise.
    """
    with open(public_path, 'rb') as f:
        pub = RSA.import_key(f.read())

    with open(file_path, 'rb') as f:
        data = f.read()

    h = SHA256.new(data)

    # load signature
    if os.path.exists(sig_path_or_hex):
        with open(sig_path_or_hex, 'r') as f:
            sig_hex = f.read().strip()
    else:
        sig_hex = sig_path_or_hex

    try:
        signature = binascii.unhexlify(sig_hex)
    except Exception:
        return False

    try:
        pkcs1_15.new(pub).verify(h, signature)
        return True
    except (ValueError, TypeError):
        return False


# Additional secure messaging functions
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_aes_gcm(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt data using AES-GCM"""
    nonce = secrets.token_bytes(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_aes_gcm(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt data using AES-GCM"""
    nonce = ciphertext[:12]
    data = ciphertext[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, data, None)


def sign_message(message: bytes) -> bytes:
    """Sign a message using RSA private key from file"""
    private_path = 'assets/private.pem'
    if not os.path.exists(private_path):
        # Generate keypair if doesn't exist
        generate_rsa_keypair()
    
    with open(private_path, 'rb') as f:
        key = RSA.import_key(f.read())
    
    h = SHA256.new(message)
    signature = pkcs1_15.new(key).sign(h)
    return signature


def verify_signature(message: bytes, signature: bytes) -> bool:
    """Verify a message signature using RSA public key"""
    public_path = 'assets/public.pem'
    if not os.path.exists(public_path):
        return False
    
    try:
        with open(public_path, 'rb') as f:
            pub = RSA.import_key(f.read())
        
        h = SHA256.new(message)
        pkcs1_15.new(pub).verify(h, signature)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Quick Test (only when run directly)
    text = "Mission Brief: Meet at VJEC Main Gate at 0900."
    ct, shares, nonce, tag = encrypt_and_shatter(text)
    print(f"Secret shattered into {len(shares)} parts.")