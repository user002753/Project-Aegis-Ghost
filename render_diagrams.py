import os
import re
import json
import zlib
import base64
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIAGRAMS_DIR = os.path.join(BASE_DIR, "assets", "diagrams")
os.makedirs(DIAGRAMS_DIR, exist_ok=True)

DIAGRAM_MAP = {
    0: "system_context_diagram.png",
    1: "detailed_component_architecture.png",
    2: "comprehensive_use_case_diagram.png",
    3: "core_lockdown_process_flow.png",
    4: "core_recovery_process_flow.png",
    5: "russian_doll_fake_lsb_flow.png"
}

def encode_pako(mermaid_code):
    """Encode Mermaid code using Pako compression for mermaid.ink."""
    data = {"code": mermaid_code, "mermaid": {"theme": "dark"}}
    json_data = json.dumps(data).encode('utf-8')
    compressor = zlib.compressobj(wbits=-15, level=zlib.Z_BEST_COMPRESSION)
    compressed = compressor.compress(json_data) + compressor.flush()
    b64_encoded = base64.urlsafe_b64encode(compressed).decode('ascii').replace("=", "")
    return f"pako:{b64_encoded}"

def encode_simple(mermaid_code):
    """Encode Mermaid code using simple Base64 for fallback."""
    # urlsafe base64 encoding
    b64 = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii").replace("=", "")
    return b64

def fetch_and_save(mermaid_code, filename):
    print(f"[*] Rendering diagram for {filename}...")
    save_path = os.path.join(DIAGRAMS_DIR, filename)
    
    # Try Pako encoding first
    try:
        pako_code = encode_pako(mermaid_code)
        url = f"https://mermaid.ink/img/{pako_code}"
        # We can also add styling queries like bgcolor=transparent or custom colors
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            print(f"[OK] Saved: {filename} (via Pako)")
            return True
    except Exception as e:
        print(f"[!] Pako rendering failed for {filename}: {e}")
        
    # Fallback to Simple encoding
    try:
        simple_code = encode_simple(mermaid_code)
        url = f"https://mermaid.ink/img/{simple_code}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            print(f"[OK] Saved: {filename} (via Simple)")
            return True
        else:
            print(f"[!] Simple rendering API returned status {resp.status_code}")
    except Exception as e:
        print(f"[!] Simple rendering failed for {filename}: {e}")
        
    return False

def render_all():
    md_path = os.path.join(BASE_DIR, "PROJECT_DIAGRAMS.md")
    if not os.path.exists(md_path):
        print(f"[X] PROJECT_DIAGRAMS.md not found at {md_path}")
        return
        
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Find all mermaid blocks
    mermaid_blocks = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
    
    print(f"[*] Found {len(mermaid_blocks)} Mermaid blocks in PROJECT_DIAGRAMS.md")
    
    rendered_count = 0
    for idx, code in enumerate(mermaid_blocks):
        if idx in DIAGRAM_MAP:
            filename = DIAGRAM_MAP[idx]
            success = fetch_and_save(code.strip(), filename)
            if success:
                rendered_count += 1
                
    print(f"\n[OK] Successfully rendered {rendered_count}/{len(mermaid_blocks)} diagrams.")
    print(f"Diagrams stored in: {os.path.relpath(DIAGRAMS_DIR, BASE_DIR)}")

if __name__ == "__main__":
    render_all()
