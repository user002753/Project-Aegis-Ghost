import hashlib

# Known: key_check = sha256(derived_key)[:16] = "0b9b44e60deccb24"
target_key_check = "0b9b44e60deccb24"

# We need to find: password such that sha256(pbkdf2(...))[:16] = target

# Common salts from the codebase
salts = [
    b"aegis_ghost_russian_doll",
    b"salt_aegis_ghost",
    b"aegis",
    b"ghost",
    b"russian_doll",
    b"stego",
]

# Common password patterns
passwords = [
    "layer1", "layer2", "layer3", "layer4", "layer5", "layer6",
    "password1", "password2", "password3", "password4", "password5", "password6",
    "secret1", "secret2", "secret3", "secret4", "secret5", "secret6",
    "key1", "key2", "key3", "key4", "key5", "key6",
    "test1", "test2", "test3", "test4", "test5", "test6",
    "pass1", "pass2", "pass3", "pass4", "pass5", "pass6",
    "aegis", "ghost", "russian", "doll", "stego", "hidden",
    "admin", "user", "owner", "root",
    "secret", "password", "123456",
]

# Also try with layer suffix patterns
passwords_with_suffix = []
for pw in passwords:
    for layer in range(1, 7):
        passwords_with_suffix.append(f"{pw}_layer_{layer}")
        passwords_with_suffix.append(f"{pw}{layer}")
        passwords_with_suffix.append(f"{pw}_{layer}")

passwords.extend(passwords_with_suffix)

rounds_list = [100000, 250000, 50000, 200000]

print(f"Target key_check: {target_key_check}")
print(f"Testing {len(passwords)} passwords with {len(salts)} salts and various rounds...")

for salt in salts:
    for rounds in rounds_list:
        for pw in passwords:
            # Try direct derivation
            try:
                key = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, rounds, dklen=32)
                key_check = hashlib.sha256(key).hexdigest()[:16]
                if key_check == target_key_check:
                    print(f'\n*** FOUND! ***')
                    print(f'Password: {pw}')
                    print(f'Salt: {salt}')
                    print(f'Rounds: {rounds}')
                    print(f'Key: {key.hex()}')
                    exit(0)
            except:
                pass

print("No match found with common passwords")
