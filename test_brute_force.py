"""Brute force to find the password that was used to create the images"""
import hashlib

# Target key_check from the images
target_key_check = "0b9b44e60deccb24"

# Try various passwords
passwords = [
    "layer1", "layer2", "layer3", "layer4", "layer5", "layer6",
    "password", "secret", "test", "admin", "owner", "root",
    "aegis", "ghost", "russian", "doll",
    "1", "2", "3", "4", "5", "6",
]

# Try different salts and rounds
salts_and_rounds = [
    (b"aegis_ghost_russian_doll", 250000),
    (b"aegis_ghost_russian_doll", 200000),
    (b"aegis_ghost_russian_doll", 100000),
    (b"aegis_ghost_salt", 100000),
    (b"aegis_ghost_salt", 250000),
    (b"salt_aegis_ghost", 100000),
    (b"aegis", 100000),
    (b"ghost", 100000),
]

# Also try passwords with numbers appended
extended_passwords = passwords.copy()
for pw in passwords:
    for i in range(10):
        extended_passwords.append(f"{pw}{i}")
        extended_passwords.append(f"{pw}_{i}")

print(f"Target key_check: {target_key_check}")
print(f"Testing {len(extended_passwords)} passwords with {len(salts_and_rounds)} salt/rounds combinations...")

for salt, rounds in salts_and_rounds:
    for pw in extended_passwords:
        key = hashlib.pbkdf2_hmac(
            "sha256",
            pw.encode("utf-8"),
            salt,
            rounds,
            dklen=32,
        )
        key_check = hashlib.sha256(key).hexdigest()[:16]
        if key_check == target_key_check:
            print(f"\n*** FOUND! ***")
            print(f"Password: {pw}")
            print(f"Salt: {salt}")
            print(f"Rounds: {rounds}")
            print(f"Key: {key.hex()}")
            exit(0)

print("\nNo password found with these combinations")
