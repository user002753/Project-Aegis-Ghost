<<<<<<< HEAD
#!/usr/bin/env python3
"""Interactive CLI to record and enroll the owner's voice.

Usage:
  python enroll_owner_voice.py --duration 8 --out assets/owner_sample.wav

This records audio from the default microphone and uses
`BiometricAuthenticator.enroll_owner_voice_from_file` to compute and save
the owner's MFCC embedding to `assets/owner_voice.npy`.
"""
import os
import argparse
import speech_recognition as sr

from core.biometric_auth import BiometricAuthenticator


def record_and_save(output_path: str, duration: int = 8) -> bool:
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print(f"Recording for {duration} seconds. Please speak clearly...")
            audio = recognizer.record(source, duration=duration)

        wav_data = audio.get_wav_data()
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(wav_data)

        print(f"Saved recording to {output_path}")
        return True
    except Exception as e:
        print(f"[X] Recording failed: {e}")
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--duration', '-d', type=int, default=8, help='Recording duration in seconds')
    p.add_argument('--out', '-o', default='assets/owner_sample.wav', help='Output WAV path')
    args = p.parse_args()

    ok = record_and_save(args.out, args.duration)
    if not ok:
        print('[X] Recording failed, aborting enrollment')
        return

    auth = BiometricAuthenticator()
    enrolled = auth.enroll_owner_voice_from_file(args.out)
    if enrolled:
        print('[OK] Enrollment completed. assets/owner_voice.npy created.')
    else:
        print('[X] Enrollment failed.')


if __name__ == '__main__':
    main()
=======
#!/usr/bin/env python3
"""Interactive CLI to record and enroll the owner's voice.

Usage:
  python enroll_owner_voice.py --duration 8 --out assets/owner_sample.wav

This records audio from the default microphone and uses
`BiometricAuthenticator.enroll_owner_voice_from_file` to compute and save
the owner's MFCC embedding to `assets/owner_voice.npy`.
"""
import os
import argparse
import speech_recognition as sr

from core.biometric_auth import BiometricAuthenticator


def record_and_save(output_path: str, duration: int = 8) -> bool:
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print(f"Recording for {duration} seconds. Please speak clearly...")
            audio = recognizer.record(source, duration=duration)

        wav_data = audio.get_wav_data()
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(wav_data)

        print(f"Saved recording to {output_path}")
        return True
    except Exception as e:
        print(f"[X] Recording failed: {e}")
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--duration', '-d', type=int, default=8, help='Recording duration in seconds')
    p.add_argument('--out', '-o', default='assets/owner_sample.wav', help='Output WAV path')
    args = p.parse_args()

    ok = record_and_save(args.out, args.duration)
    if not ok:
        print('[X] Recording failed, aborting enrollment')
        return

    auth = BiometricAuthenticator()
    enrolled = auth.enroll_owner_voice_from_file(args.out)
    if enrolled:
        print('[OK] Enrollment completed. assets/owner_voice.npy created.')
    else:
        print('[X] Enrollment failed.')


if __name__ == '__main__':
    main()
>>>>>>> e5fc0b8f35306ee3f5004b4278ee840afa3c8da4
