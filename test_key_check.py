import hashlib
import sys

def _derive_layer_key(password, rounds=250000):
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        b'aegis_ghost_russian_doll',
        rounds,
        dklen=32,
    )

# Test with layer1 and 250000 rounds
key = _derive_layer_key('layer1', 250000)
key_check = hashlib.sha256(key).hexdigest()[:16]
sys.stdout.write(f'Password: layer1, Rounds: 250000\n')
sys.stdout.write(f'Key: {key.hex()}\n')
sys.stdout.write(f'key_check: {key_check}\n')
sys.stdout.write(f'\nExpected key_check from images: 0b9b44e60deccb24\n')
