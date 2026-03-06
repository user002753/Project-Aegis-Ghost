#!/usr/bin/env python3
"""
End-to-end pipeline:
- Takes a secret (string or file)
- Encrypts and splits into Shamir shares
- Generates 10 AI carrier images
- Embeds each share into its corresponding image using DWT steganography
- Saves metadata for recovery

Usage examples:
  python run_pipeline.py --secret "Top secret" --threshold 6
  python run_pipeline.py --secret-file path/to/secret.txt --n-shares 10 --threshold 6

By default uses the fast mock image generator (no heavy AI model). You can
switch off the mock with --no-mock if you have the diffusion dependencies.
"""

import os
import argparse
from typing import List, Tuple
import requests

from core.encryption import encrypt_and_shatter, save_metadata
from core.steganography import embed_data_dwt
from core.ai_engine import generate_ghost_carrier
import os
import json


def ensure_dirs():
    os.makedirs("data/output_stego", exist_ok=True)


def build_prompts(n: int, base_prompt: str = None) -> List[str]:
    if base_prompt:
        base = f"{base_prompt}, shard #{{i}}, vivid colors, picturesque, not grayscale"
    else:
        base = (
            "Abstract oil texture, layered brush strokes, high-frequency micro-contrast, "
            "rich gradients and noise-like details, shard #{i}, cohesive visual theme, vivid colors"
        )
    return [base.format(i=i) for i in range(1, n + 1)]


def build_prompts_gemini(n: int, user_theme: str = None) -> List[str]:
    """Generate n varied image prompts using OpenAI text model.
    Falls back to deterministic prompts if OpenAI is unavailable or fails.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return build_prompts(n, base_prompt=user_theme)
    try:
        model_name = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
        theme_instruction = f" The user's requested theme is: '{user_theme}'." if user_theme else ""
        prompt_text = (
            "You are a prompt engineer. Create a list of unique, high-quality, picturesque and colorful image generation prompts "
            f"for {n} images.{theme_instruction} Each prompt must specify a distinct art style or medium (e.g., watercolor, "
            "oil impasto, cyberpunk neon, ukiyo-e woodblock, low-poly 3D, "
            "isometric pixel art, chiaroscuro baroque, generative abstract). "
            "IMPORTANT: The images must NOT be grayscale. They must be colorful and picturesque. Keep them "
            f"concise yet descriptive. Return ONLY a JSON array of strings with exactly {n} entries, no extra text."
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You produce structured JSON output only."},
                {"role": "user", "content": prompt_text},
            ],
            "temperature": 0.9,
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        # Strip markdown code-fence wrappers if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json", "", 1).strip()
        # Extract JSON array from response
        start = raw.find('[')
        end = raw.rfind(']')
        if start == -1 or end == -1 or end <= start:
            return build_prompts(n, base_prompt=user_theme)
        prompts = json.loads(raw[start:end+1])
        # Ensure we have exactly n prompts
        if not isinstance(prompts, list):
            return build_prompts(n, base_prompt=user_theme)
        cleaned = [str(p).strip() for p in prompts if str(p).strip()]
        if len(cleaned) < n:
            cleaned += build_prompts(n - len(cleaned), base_prompt=user_theme)
        return cleaned[:n]
    except Exception:
        return build_prompts(n, base_prompt=user_theme)


def read_secret(args: argparse.Namespace) -> str:
    if args.secret is not None:
        return args.secret
    if args.secret_file is not None:
        with open(args.secret_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    raise SystemExit("Provide --secret or --secret-file")


def generate_carriers_and_embed(
    prompts: List[str],
    shares: List[Tuple[int, bytes]],
    use_mock: bool = True,
    size=(512, 512),
    out_dir: str = "data/output_stego",
) -> List[str]:
    paths = []
    for (idx, share), prompt in zip(shares, prompts):
        out_path = os.path.join(out_dir, f"ghost_{idx}.png")
        # 1) Generate carrier image
        generate_ghost_carrier(prompt=prompt, save_path=out_path, use_mock=use_mock, size=size)
        # 2) Embed share into the carrier
        embed_data_dwt(out_path, share, out_path)
        paths.append(out_path)
    return paths


def main():
    parser = argparse.ArgumentParser(description="Aegis Ghost end-to-end pipeline")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--secret", type=str, help="Secret message string")
    g.add_argument("--secret-file", type=str, help="Path to file containing secret text")
    parser.add_argument("--n-shares", type=int, default=10, help="Total number of shares (default 10)")
    parser.add_argument("--threshold", type=int, default=6, help="Reconstruction threshold (default 6)")
    parser.add_argument("--no-mock", action="store_true", help="Use diffusion model instead of fast mock generator")
    parser.add_argument("--width", type=int, default=512, help="Carrier width (default 512)")
    parser.add_argument("--height", type=int, default=512, help="Carrier height (default 512)")
    parser.add_argument("--prompt", type=str, help="User-defined theme or prompt for image generation")
    args = parser.parse_args()

    ensure_dirs()

    # Read secret
    secret_text = read_secret(args)

    # Encrypt and shatter
    print(f"[+] Encrypting and splitting secret into {args.n_shares} shares (threshold={args.threshold})...")
    ciphertext, shares, nonce, tag = encrypt_and_shatter(secret_text, n_shares=args.n_shares, threshold=args.threshold)

    # Save metadata for recovery later
    print("[+] Saving metadata (ciphertext, nonce, tag)...")
    save_metadata(ciphertext, nonce, tag)

    # Build prompts and generate carriers
    print("[+] Generating carrier images and embedding shares...")
    # Prefer Gemini-driven diverse prompts; fallback to deterministic prompts
    prompts = build_prompts_gemini(args.n_shares, user_theme=args.prompt)
    size = (args.width, args.height)
    use_mock = not args.no_mock

    out_paths = generate_carriers_and_embed(prompts, shares, use_mock=use_mock, size=size)

    print("\n[OK] Pipeline complete. Shards written:")
    for p in out_paths:
        print(f" - {p}")
    print("\nOpen your gallery and click 'Refresh Gallery' to view the images.")


if __name__ == "__main__":
    main()
