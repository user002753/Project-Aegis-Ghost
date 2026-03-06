<<<<<<< HEAD
import os
import shutil
import json
from core.encryption import encrypt_and_shatter, biometric_unlock, save_metadata, load_metadata
from core.ai_engine import generate_ghost_carrier, verify_owner
from core.steganography import embed_data_dwt, extract_data_dwt
from core.steganalysis import analyze_image

def run_lockdown():
    print("\n[PHASE 1] --- LOCKDOWN INITIATED ---")
    secret_message = input("Enter the secret message: ")
    
    # Option for custom prompt
    user_prompt = input("Enter image theme/prompt (default: 'Abstract colorful'): ").strip()
    if not user_prompt:
        user_prompt = "Abstract colorful, vivid colors"

    # 1. Encrypt
    ciphertext, shares, nonce, tag = encrypt_and_shatter(secret_message)
    
    # 2. Prepare output folder
    stego_path = "data/output_stego"
    os.makedirs(stego_path, exist_ok=True)
    
    save_metadata(ciphertext, nonce, tag)

    # 3. Generate & Hide - Optimized for speed
    # Check for API keys to determine if we should use real AI or mock
    has_ai_keys = os.getenv("HF_API_TOKEN") or os.getenv("REPLICATE_API_TOKEN") or os.getenv("GEMINI_API_KEY")
    use_mock = not has_ai_keys
    
    if has_ai_keys:
        print("[*] AI keys detected. Using AI generation (this may take longer)...")
    else:
        print("[*] No AI keys detected. Using fast mock generator.")

    for i, (idx, share) in enumerate(shares, 1):
        path = f"data/output_stego/ghost_{idx}.png"
        if i % 2 == 0:  # Progress indicator
            print(f"Embedding share {i}/10...")
        # Generate unique image for each share
        generate_ghost_carrier(f"{user_prompt} - variant {idx}", path, use_mock=use_mock)
        embed_data_dwt(path, share, path)
        
    print("\n[OK] LOCKDOWN COMPLETE. Check data/output_stego/")

def run_recovery():
    print("\n[PHASE 2] --- RECOVERY INITIATED ---")
    
    # 1. AI Biometric Authentication (disabled by default for testing)
    print("\n[AUTHENTICATION] Starting verification...")
    if not verify_owner(biometric_enabled=False):
        print("[X] Access Denied: Authentication failed.")
        return

    print("[OK] Identity Confirmed. Extracting data...")
    
    # 2. Extract Fragments (optimized)
    captured_shares = []
    stego_folder = "data/output_stego"
    files = sorted([f for f in os.listdir(stego_folder) if f.endswith('.png')])[:6]
    
    for i, filename in enumerate(files, 1):
        path = os.path.join(stego_folder, filename)
        if i % 2 == 0:
            print(f"Extracting share {i}/6...")
        share_data = extract_data_dwt(path, num_bytes=16)
        idx = int(filename.split('_')[1].split('.')[0])
        captured_shares.append((idx, share_data))

    # 3. Final Unlock
    ciphertext, nonce, tag = load_metadata()
    decrypted_msg = biometric_unlock(captured_shares, ciphertext, nonce, tag)
    
    print(f"\n[REVEALED SECRET]: {decrypted_msg}")

def run_recovery_with_biometric():
    print("\n[PHASE 2] --- RECOVERY INITIATED (BIOMETRIC MODE) ---")
    print("\n[INFO] Multi-factor biometric authentication:")
    print("  1. Face Recognition - Match against owner image")
    
    # 1. AI Biometric Authentication (ENABLED for security)
    print("\n[AUTHENTICATION] Starting biometric verification...")
    if not verify_owner(biometric_enabled=True):
        print("[X] Access Denied: Biometric authentication failed.")
        return

    print("[OK] Identity Confirmed. Extracting data...")
    
    # 2. Extract Fragments (optimized)
    captured_shares = []
    stego_folder = "data/output_stego"
    files = sorted([f for f in os.listdir(stego_folder) if f.endswith('.png')])[:6]
    
    for i, filename in enumerate(files, 1):
        path = os.path.join(stego_folder, filename)
        if i % 2 == 0:
            print(f"Extracting share {i}/6...")
        share_data = extract_data_dwt(path, num_bytes=16)
        idx = int(filename.split('_')[1].split('.')[0])
        captured_shares.append((idx, share_data))

    # 3. Final Unlock
    ciphertext, nonce, tag = load_metadata()
    decrypted_msg = biometric_unlock(captured_shares, ciphertext, nonce, tag)
    
    print(f"\n[REVEALED SECRET]: {decrypted_msg}")

def run_steganalysis():
    print("\n[PHASE 3] --- STEGANALYSIS INITIATED ---")
    image_path = input("Enter image path to analyze: ").strip().strip('"')

    if not image_path:
        print("[X] No image path provided.")
        return

    if not os.path.isfile(image_path):
        print(f"[X] File not found: {image_path}")
        return

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        result = analyze_image(image_bytes)
        overall = result.get("overall", {})
        analyses = result.get("analyses", {})

        print("\n[STEGANALYSIS RESULT]")
        print(f"Verdict: {overall.get('verdict', 'Unknown')}")
        print(f"Risk Level: {overall.get('risk_level', 'Unknown')}")
        print(
            f"Suspicious Methods: {overall.get('suspicious_methods', 0)} / "
            f"{overall.get('total_methods', 0)}"
        )
        print(f"Average Confidence: {overall.get('average_confidence', 0)}%")

        print("\n[Method Breakdown]")
        for method_name, method_result in analyses.items():
            print(f"- {method_name}: {method_result.get('verdict', 'Unknown')}")

        save_report = input("\nSave full JSON report? (y/n): ").strip().lower()
        if save_report == "y":
            report_path = os.path.splitext(image_path)[0] + "_steganalysis_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"[OK] Report saved: {report_path}")
    except Exception as e:
        print(f"[X] Steganalysis failed: {e}")

if __name__ == "__main__":
    import sys
    
    # Check for biometric flag
    biometric_enabled = '--biometric' in sys.argv or '-b' in sys.argv
    
    choice = input(
        "Select Mode: (1) Lockdown [Hide], (2) Recovery [Reveal], or (3) Steganalysis: "
    )
    if choice == '1':
        run_lockdown()
    elif choice == '2':
        # Enable biometric auth for recovery if flag is set
        if biometric_enabled:
            run_recovery_with_biometric()
        else:
            run_recovery()
    elif choice == '3':
        run_steganalysis()
    else:
        print("[X] Invalid choice")
=======
import os
import shutil
from core.encryption import encrypt_and_shatter, biometric_unlock, save_metadata, load_metadata
from core.ai_engine import generate_ghost_carrier, verify_owner
from core.steganography import embed_data_dwt, extract_data_dwt

def run_lockdown():
    print("\n[PHASE 1] --- LOCKDOWN INITIATED ---")
    secret_message = input("Enter the secret message: ")
    
    # Option for custom prompt
    user_prompt = input("Enter image theme/prompt (default: 'Abstract colorful'): ").strip()
    if not user_prompt:
        user_prompt = "Abstract colorful, vivid colors"

    # 1. Encrypt
    ciphertext, shares, nonce, tag = encrypt_and_shatter(secret_message)
    
    # 2. Prepare output folder
    stego_path = "data/output_stego"
    os.makedirs(stego_path, exist_ok=True)
    
    save_metadata(ciphertext, nonce, tag)

    # 3. Generate & Hide - Optimized for speed
    for i, (idx, share) in enumerate(shares, 1):
        path = f"data/output_stego/ghost_{idx}.png"
        if i % 2 == 0:  # Progress indicator
            print(f"Embedding share {i}/10...")
        # Generate unique image for each share
        generate_ghost_carrier(f"{user_prompt} - variant {idx}", path, use_mock=True)
        embed_data_dwt(path, share, path)
        
    print("\n[OK] LOCKDOWN COMPLETE. Check data/output_stego/")

def run_recovery():
    print("\n[PHASE 2] --- RECOVERY INITIATED ---")
    
    # 1. AI Biometric Authentication (disabled by default for testing)
    print("\n[AUTHENTICATION] Starting verification...")
    if not verify_owner(biometric_enabled=False):
        print("[X] Access Denied: Authentication failed.")
        return

    print("[OK] Identity Confirmed. Extracting data...")
    
    # 2. Extract Fragments (optimized)
    captured_shares = []
    stego_folder = "data/output_stego"
    files = sorted([f for f in os.listdir(stego_folder) if f.endswith('.png')])[:6]
    
    for i, filename in enumerate(files, 1):
        path = os.path.join(stego_folder, filename)
        if i % 2 == 0:
            print(f"Extracting share {i}/6...")
        share_data = extract_data_dwt(path, num_bytes=16)
        idx = int(filename.split('_')[1].split('.')[0])
        captured_shares.append((idx, share_data))

    # 3. Final Unlock
    ciphertext, nonce, tag = load_metadata()
    decrypted_msg = biometric_unlock(captured_shares, ciphertext, nonce, tag)
    
    print(f"\n[REVEALED SECRET]: {decrypted_msg}")

def run_recovery_with_biometric():
    print("\n[PHASE 2] --- RECOVERY INITIATED (BIOMETRIC MODE) ---")
    print("\n[INFO] Multi-factor biometric authentication:")
    print("  1. Face Recognition - Match against owner image")
    
    # 1. AI Biometric Authentication (ENABLED for security)
    print("\n[AUTHENTICATION] Starting biometric verification...")
    if not verify_owner(biometric_enabled=True):
        print("[X] Access Denied: Biometric authentication failed.")
        return

    print("[OK] Identity Confirmed. Extracting data...")
    
    # 2. Extract Fragments (optimized)
    captured_shares = []
    stego_folder = "data/output_stego"
    files = sorted([f for f in os.listdir(stego_folder) if f.endswith('.png')])[:6]
    
    for i, filename in enumerate(files, 1):
        path = os.path.join(stego_folder, filename)
        if i % 2 == 0:
            print(f"Extracting share {i}/6...")
        share_data = extract_data_dwt(path, num_bytes=16)
        idx = int(filename.split('_')[1].split('.')[0])
        captured_shares.append((idx, share_data))

    # 3. Final Unlock
    ciphertext, nonce, tag = load_metadata()
    decrypted_msg = biometric_unlock(captured_shares, ciphertext, nonce, tag)
    
    print(f"\n[REVEALED SECRET]: {decrypted_msg}")

if __name__ == "__main__":
    import sys
    
    # Check for biometric flag
    biometric_enabled = '--biometric' in sys.argv or '-b' in sys.argv
    
    choice = input("Select Mode: (1) Lockdown [Hide] or (2) Recovery [Reveal]: ")
    if choice == '1':
        run_lockdown()
    elif choice == '2':
        # Enable biometric auth for recovery if flag is set
        if biometric_enabled:
            run_recovery_with_biometric()
        else:
            run_recovery()
    else:
        print("[X] Invalid choice")
>>>>>>> e5fc0b8f35306ee3f5004b4278ee840afa3c8da4
