import os
import sys

def check_setup():
    print("--- AEGIS-GHOST: PRE-FLIGHT CHECK ---")
    
    # 1. Check Directory Structure
    required_folders = ['assets', 'data', 'data/output_stego', 'core']
    for folder in required_folders:
        if os.path.exists(folder):
            print(f"[✓] Folder found: {folder}")
        else:
            os.makedirs(folder)
            print(f"[+] Created missing folder: {folder}")

    # 2. Check for Biometric Identity
    if os.path.exists('assets/owner.jpg'):
        print("[✓] Biometric Identity Found (assets/owner.jpg)")
    else:
        print("[!] WARNING: assets/owner.jpg is missing. Biometric unlock will fail!")

    # 3. Check for Decoy Secret
    if not os.path.exists('decoy.txt'):
        with open('decoy.txt', 'w') as f:
            f.write("DECOY: The actual plans are in the vault at VJEC Building 3.")
        print("[+] Created default decoy.txt")
    else:
        print("[✓] Decoy file found.")

    # 4. Check Core Modules
    core_files = ['encryption.py', 'steganography.py', 'ai_engine.py']
    for cf in core_files:
        if os.path.exists(f'core/{cf}'):
            print(f"[✓] Logic module found: {cf}")
        else:
            print(f"[X] ERROR: core/{cf} is missing!")

    print("\n--- CHECK COMPLETE: Ready for Phase 1 (Lockdown) ---")

if __name__ == "__main__":
    check_setup()