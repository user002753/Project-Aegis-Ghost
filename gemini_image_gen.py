#!/usr/bin/env python3
"""
Gemini Image Generation Script

This script demonstrates how to use Google's Gemini API to generate images.
It uses the google.genai client library to create images from text prompts.

Usage:
    python gemini_image_gen.py [--prompt "Your prompt here"]
    
Alternative (using Pollinations AI - no API key needed):
    python gemini_image_gen.py --use-pollinations
    
Requirements:
    - GEMINI_API_KEY in .env file or environment variable (for Gemini)
    - google-generativeai package installed

Note: If you hit quota limits with Gemini, use --use-pollinations for free generation.
"""

import os
import sys
import argparse
import io
import hashlib
from pathlib import Path
from urllib.parse import quote

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import PIL.Image
from google import genai
from google.genai import types
from datetime import datetime
import requests


def get_api_key() -> str:
    """Get Gemini API key from environment."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Try to get from .env file
        env_path = project_root / ".env"
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
    return api_key or ""


def generate_image(
    prompt: str,
    model: str = "gemini-2.0-flash-exp-image-generation",
    save_path: str = None
) -> PIL.Image.Image:
    """
    Generate an image using Google's Gemini API.
    
    Args:
        prompt: Text description of the image to generate
        model: Model to use for generation (default: gemini-2.0-flash-exp-image-generation)
        save_path: Optional path to save the generated image
        
    Returns:
        PIL.Image.Image object
        
    Raises:
        ValueError: If API key is not configured
        RuntimeError: If image generation fails
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not set. Please configure it in .env file "
            "or set the GEMINI_API_KEY environment variable."
        )
    
    # Initialize the client
    client = genai.Client(api_key=api_key)
    
    print(f"Generating image with prompt: {prompt}")
    print(f"Using model: {model}")
    
    try:
        # Generate content with image response
        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config={
                "response_modalities": ["IMAGE"]
            }
        )
        
        # Extract image from response
        image = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                mime_type = part.inline_data.mime_type
                if mime_type and mime_type.startswith('image/'):
                    image_data = part.inline_data.data
                    image = PIL.Image.open(io.BytesIO(image_data))
                    break
        
        if image is None:
            raise RuntimeError("No image found in response")
        
        # Save image if path provided
        if save_path:
            image.save(save_path)
            print(f"Image saved to: {save_path}")
        
        return image
        
    except Exception as e:
        raise RuntimeError(f"Image generation failed: {e}")


def generate_image_with_fallback(
    prompt: str,
    save_path: str = None,
    size: tuple = (512, 512)
) -> PIL.Image.Image:
    """
    Generate an image with fallback to multiple model variants.
    
    Args:
        prompt: Text description of the image to generate
        save_path: Optional path to save the generated image
        size: Optional size for the generated image (width, height)
        
    Returns:
        PIL.Image.Image object
    """
    # Try multiple model variants
    model_candidates = [
        "gemini-2.0-flash-exp-image-generation",
        "gemini-2.5-flash-image",
        "gemini-3-pro-image-preview",
        "gemini-3.1-flash-image-preview",
    ]
    
    last_error = None
    for model in model_candidates:
        try:
            print(f"Trying model: {model}")
            image = generate_image(prompt, model=model, save_path=save_path)
            
            # Resize if needed
            if size and image.size != size:
                image = image.resize(size, PIL.Image.Resampling.LANCZOS)
            
            return image
        except Exception as e:
            last_error = e
            print(f"Model {model} failed: {e}")
            continue
    
    raise RuntimeError(f"All models failed. Last error: {last_error}")


def generate_with_pollinations(prompt: str, size: tuple = (512, 512), save_path: str = None) -> PIL.Image.Image:
    """
    Generate an image using Pollinations AI (free, no API key needed).
    Uses the existing project AI engine for reliability.
    
    Args:
        prompt: Text description of the image to generate
        size: Optional size for the generated image (width, height)
        save_path: Optional path to save the generated image
        
    Returns:
        PIL.Image.Image object
    """
    w, h = int(size[0]), int(size[1])
    
    print(f"Generating image with Pollinations AI (via project AI engine)...")
    print(f"Prompt: {prompt}")
    
    try:
        # Use the existing project AI engine
        from core.ai_engine import _generate_with_pollinations
        
        # Generate image with existing engine
        img = _generate_with_pollinations(prompt, size=(w, h))
        
        # Save if path provided
        if save_path:
            img.save(save_path)
            print(f"Image saved to: {save_path}")
        
        return img
        
    except Exception as e:
        # If project engine fails, try direct approach
        print(f"  Project engine failed, trying direct approach: {e}")
        return _generate_pollinations_direct(prompt, size, save_path)


def _generate_pollinations_direct(prompt: str, size: tuple = (512, 512), save_path: str = None) -> PIL.Image.Image:
    """
    Direct Pollinations API call as fallback.
    """
    w, h = int(size[0]), int(size[1])
    seed = int.from_bytes(hashlib.sha256(prompt.encode("utf-8")).digest()[:4], "little")
    enhanced_prompt = f"{prompt}, photorealistic, high detail, vibrant colors"
    
    # Try different URL formats
    urls_to_try = [
        f"https://image.pollinations.ai/prompt/{quote(enhanced_prompt)}?width={w}&height={h}&seed={seed}&nologo=true&enhance=true&model=flux",
    ]
    
    for url in urls_to_try:
        try:
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            img = PIL.Image.open(io.BytesIO(response.content)).convert("RGB")
            if img.size != (w, h):
                img = img.resize((w, h), PIL.Image.Resampling.LANCZOS)
            if save_path:
                img.save(save_path)
            return img
        except Exception as e:
            print(f"  Direct attempt failed: {e}")
            continue
    
    raise RuntimeError("All Pollinations direct attempts failed")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Generate images using Google's Gemini API or Pollinations AI"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Show me a picture of a nano banana dish in a fancy restaurant with a Gemini theme",
        help="Text prompt for image generation"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.0-flash-exp-image-generation",
        help="Model to use for generation"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: auto-generated in data/output_stego/)"
    )
    parser.add_argument(
        "--size",
        type=str,
        default="512x512",
        help="Output size (e.g., 512x512, 1024x1024)"
    )
    parser.add_argument(
        "--use-pollinations",
        action="store_true",
        help="Use Pollinations AI instead of Gemini (free, no API key needed)"
    )
    
    args = parser.parse_args()
    
    # Parse size
    try:
        width, height = map(int, args.size.split('x'))
        size = (width, height)
    except:
        size = (512, 512)
    
    # Generate output path if not provided
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = project_root / "data" / "output_stego"
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(output_dir / f"gemini_{timestamp}.png")
    
    print("=" * 60)
    print("Image Generation")
    print("=" * 60)
    
    try:
        if args.use_pollinations:
            # Use Pollinations AI (free alternative)
            image = generate_with_pollinations(
                prompt=args.prompt,
                size=size,
                save_path=args.output
            )
        else:
            # Try Gemini first
            try:
                image = generate_image_with_fallback(
                    prompt=args.prompt,
                    save_path=args.output,
                    size=size
                )
            except Exception as e:
                error_str = str(e)
                if "quota" in error_str.lower() or "resource_exhausted" in error_str.lower() or "429" in error_str or "530" in error_str:
                    print("\nGemini service unavailable. Using Pollinations fallback...")
                    try:
                        image = generate_with_pollinations(
                            prompt=args.prompt,
                            size=size,
                            save_path=args.output
                        )
                    except Exception as pe:
                        print(f"Error: {pe}")
                        return 1
                else:
                    print(f"Error: {e}")
                    return 1
        
        print("=" * 60)
        print(f"Success! Image generated and saved to: {args.output}")
        print(f"Image size: {image.size}")
        print("=" * 60)
        return 0
    except Exception as e:
        print("=" * 60)
        print(f"Error: {e}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
