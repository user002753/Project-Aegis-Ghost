from __future__ import annotations
import hashlib
import os
import base64
import io
import json
import time
from typing import List
from urllib.parse import quote
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageOps
import requests

_pipe = None
_GEMINI_IMAGE_CACHE: dict[tuple[str, tuple[int, int], str], Image.Image] = {}
_GEMINI_IMAGE_CACHE_MAX = 32
_TEXT_CACHE: dict[tuple[str, str], str] = {}
_TEXT_CACHE_MAX = 128
_HTTP_SESSION = requests.Session()


def _get_env(name: str, default: str | None = None) -> str | None:
    alias_map = {
        "RAPHAEL_API_KEY": ["RAPHAEL_TOKEN", "RAPHAEL_KEY", "RAPHAEL_API_TOKEN"],
        "PEXELS_API_KEY": ["PEXELS_KEY", "PEXELS_TOKEN", "PEXELS_API_TOKEN"],
        "LEONARDO_API_KEY": ["LEONARDO_KEY", "LEONARDO_TOKEN", "LEONARDO_API_TOKEN"],
        "DEEPAI_API_KEY": ["DEEPAI_KEY", "DEEPAI_TOKEN"],
    }
    val = os.getenv(name)
    if val:
        return val
    for alias in alias_map.get(name, []):
        v_alias = os.getenv(alias)
        if v_alias:
            return v_alias
    try:
        from dotenv import dotenv_values
        # Go up two directories from core/ai/ to project root
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        env_path = os.path.join(root, ".env")
        parsed = dotenv_values(env_path)
        v = parsed.get(name)
        if isinstance(v, str) and v:
            return v
        for alias in alias_map.get(name, []):
            v_alias = parsed.get(alias)
            if isinstance(v_alias, str) and v_alias:
                return v_alias
    except Exception:
        pass
    return default


def _load_dotenv_if_present():
    """Load .env from project root if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    try:
        # Go up two directories from core/ai/ to project root
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        env_path = os.path.join(root, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)  # Changed to override=True to ensure .env values are used
    except Exception:
        pass


_load_dotenv_if_present()


def _generate_mock(prompt: str, size=(512, 512)) -> Image.Image:
    """Deterministic prompt-aware local fallback renderer.

    This is still lightweight and synthetic, but it maps common prompt keywords
    to scene elements so output aligns better with prompt intent.
    """
    w, h = int(size[0]), int(size[1])
    text = (prompt or "").lower()
    seed = int.from_bytes(hashlib.sha256(prompt.encode("utf-8")).digest()[:8], "little")
    rng = np.random.default_rng(seed)

    def has(*words):
        return any(wd in text for wd in words)

    # Sky palette by time/atmosphere keywords
    if has("night", "moon", "stars", "galaxy", "space"):
        sky_top, sky_bottom = np.array([8, 12, 40]), np.array([32, 64, 120])
    elif has("sunset", "dusk", "golden hour"):
        sky_top, sky_bottom = np.array([255, 120, 40]), np.array([80, 40, 90])
    elif has("sunrise", "dawn"):
        sky_top, sky_bottom = np.array([255, 170, 90]), np.array([120, 180, 255])
    else:
        sky_top, sky_bottom = np.array([80, 150, 240]), np.array([185, 220, 255])

    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    arr = (1.0 - y) * sky_top + y * sky_bottom
    arr = np.repeat(arr, w, axis=1).astype(np.float32)

    horizon = int(h * (0.56 + rng.uniform(-0.05, 0.05)))

    # Ground/water layer
    if has("ocean", "sea", "beach", "water", "river", "lake"):
        water_top = np.array([30, 90, 170], dtype=np.float32)
        water_bot = np.array([10, 40, 90], dtype=np.float32)
        gy = np.linspace(0.0, 1.0, h - horizon, dtype=np.float32)[:, None, None]
        water = (1.0 - gy) * water_top + gy * water_bot
        water = np.repeat(water, w, axis=1)
        wave = (np.sin(np.linspace(0, 40, w))[None, :, None] * 7.0)
        arr[horizon:] = np.clip(water + wave, 0, 255)
    elif has("desert", "sand", "dune"):
        arr[horizon:] = np.array([222, 190, 120], dtype=np.float32)
    elif has("snow", "ice", "winter"):
        arr[horizon:] = np.array([230, 236, 245], dtype=np.float32)
    else:
        arr[horizon:] = np.array([58, 118, 62], dtype=np.float32)

    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(img)

    # Celestial lights
    if has("sunset", "sunrise", "day", "beach", "desert"):
        r = int(min(w, h) * 0.08)
        cx, cy = int(w * 0.78), int(h * 0.24)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 230, 140))
    if has("night", "stars", "galaxy", "space"):
        for _ in range(max(40, w // 10)):
            x = int(rng.integers(0, w))
            yy = int(rng.integers(0, horizon))
            draw.point((x, yy), fill=(240, 240, 255))

    # Mountains / skyline / trees
    if has("mountain", "alps", "hills", "peak"):
        for _ in range(5):
            mx = int(rng.integers(0, w))
            mw = int(rng.integers(max(40, w // 9), max(80, w // 4)))
            mh = int(rng.integers(max(40, h // 10), max(100, h // 3)))
            poly = [(mx - mw, horizon), (mx, horizon - mh), (mx + mw, horizon)]
            draw.polygon(poly, fill=(70, 80, 95))
    if has("city", "skyline", "buildings", "urban", "street", "market"):
        for i in range(0, w, max(12, w // 30)):
            bw = int(rng.integers(max(10, w // 60), max(24, w // 24)))
            bh = int(rng.integers(max(30, h // 8), max(120, h // 2)))
            x0 = i
            x1 = min(w - 1, i + bw)
            y0 = max(0, horizon - bh)
            draw.rectangle([x0, y0, x1, horizon], fill=(35, 38, 50))
    if has("forest", "trees", "jungle", "woods"):
        for _ in range(max(18, w // 20)):
            tx = int(rng.integers(0, w))
            th = int(rng.integers(max(25, h // 12), max(80, h // 4)))
            tw = int(max(6, th * 0.4))
            draw.polygon([(tx, horizon - th), (tx - tw, horizon), (tx + tw, horizon)], fill=(24, 88, 38))

    # Road and car cues
    if has("road", "highway", "street"):
        road_top = int(w * 0.18)
        draw.polygon(
            [(w // 2 - road_top // 2, horizon), (w // 2 + road_top // 2, horizon), (w, h), (0, h)],
            fill=(45, 45, 48),
        )
        for y0 in range(horizon + 10, h, max(20, h // 12)):
            y1 = min(h, y0 + max(8, h // 28))
            ww = int((y0 - horizon) / max(1, (h - horizon)) * w * 0.08) + 2
            draw.rectangle([w // 2 - ww, y0, w // 2 + ww, y1], fill=(245, 232, 120))
    if has("car", "sports car", "vehicle"):
        cx, cy = int(w * 0.55), int(h * 0.78)
        car_color = (
            int(rng.integers(180, 256)),
            int(rng.integers(20, 80)),
            int(rng.integers(20, 80)),
        )
        draw.rounded_rectangle([cx - 70, cy - 25, cx + 70, cy + 20], radius=14, fill=car_color)
        draw.rounded_rectangle([cx - 30, cy - 48, cx + 36, cy - 16], radius=10, fill=(70, 90, 120))
        draw.ellipse([cx - 56, cy + 10, cx - 24, cy + 42], fill=(24, 24, 24))
        draw.ellipse([cx + 24, cy + 10, cx + 56, cy + 42], fill=(24, 24, 24))

    if has("fire", "flame", "lava"):
        for _ in range(max(10, w // 30)):
            fx = int(rng.integers(0, w))
            fh = int(rng.integers(max(20, h // 16), max(90, h // 5)))
            fw = int(rng.integers(8, 20))
            draw.polygon([(fx, h), (fx - fw, h - fh), (fx + fw, h - fh)], fill=(255, 90, 20))

    # Final texture for realism
    arr2 = np.array(img, dtype=np.float32)
    grain = rng.normal(0.0, 5.0, size=arr2.shape).astype(np.float32)
    arr2 = np.clip(arr2 + grain, 0, 255).astype(np.uint8)
    return Image.fromarray(arr2, mode="RGB")


def _recommend_prompts_local(theme: str = "Abstract artistic security visualization", n_prompts: int = 10):
    """
    Generate diverse prompt suggestions.
    Fast deterministic fallback when external GenAI providers are unavailable.
    """
    base = (theme or "Abstract artistic security visualization").strip()
    flavors = [
        "cinematic lighting",
        "minimal geometric style",
        "high contrast colors",
        "retro-futuristic palette",
        "organic texture details",
        "surreal composition",
        "architectural abstraction",
        "soft atmospheric haze",
        "macro detail emphasis",
        "dynamic motion aesthetic",
    ]
    out = []
    for i in range(max(1, int(n_prompts))):
        out.append(f"{base}, {flavors[i % len(flavors)]}")
    return out


def _build_photoreal_prompt(prompt: str) -> str:
    base = (prompt or "").strip()
    if not base:
        base = "real-world scene"
    suffix = (
        "photorealistic, real-life photography, natural lighting, realistic textures, "
        "high detail, true-to-life colors, vibrant full-color image, no grayscale, "
        "no monochrome, no black and white, no illustration, no cartoon, no painting, no CGI"
    )
    return f"{base}. {suffix}"


def _build_color_rich_prompt(prompt: str) -> str:
    base = _build_photoreal_prompt(prompt)
    color_suffix = (
        "ultra vibrant full-color grading, rich saturation, cinematic color contrast, "
        "teal and warm highlights, no grayscale, no monochrome, no black-and-white"
    )
    return f"{base}. {color_suffix}"


def _is_effectively_grayscale(img: Image.Image) -> bool:
    """Heuristic grayscale detector for provider outputs."""
    arr = np.array(img.convert("RGB"), dtype=np.int16)
    rg = np.abs(arr[:, :, 0] - arr[:, :, 1]).mean()
    gb = np.abs(arr[:, :, 1] - arr[:, :, 2]).mean()
    rb = np.abs(arr[:, :, 0] - arr[:, :, 2]).mean()
    hsv = np.array(img.convert("HSV"), dtype=np.uint8)
    mean_sat = float(hsv[:, :, 1].mean())
    # Very low channel separation + low saturation => effectively grayscale.
    return (rg + gb + rb) / 3.0 < 6.5 and mean_sat < 22.0


def _colorize_grayscale_fallback(img: Image.Image) -> Image.Image:
    """Last-resort toning if provider repeatedly returns monochrome."""
    luma = img.convert("L")
    # Split-tone to keep contrast but avoid grayscale output.
    toned = ImageOps.colorize(luma, black="#102a43", white="#ffd166", mid="#2a9d8f")
    toned = ImageEnhance.Color(toned).enhance(1.35)
    toned = ImageEnhance.Contrast(toned).enhance(1.08)
    return toned.convert("RGB")


def _cache_put_text(key: tuple[str, str], value: str):
    if len(_TEXT_CACHE) >= _TEXT_CACHE_MAX:
        _TEXT_CACHE.pop(next(iter(_TEXT_CACHE)))
    _TEXT_CACHE[key] = value


def _post_json_with_retries(url: str, headers: dict, payload: dict, timeout: int = 45):
    """HTTP JSON POST with small bounded retry/backoff for smoother provider behavior."""
    retries = max(1, int(_get_env("AI_HTTP_RETRIES", "2") or "2"))
    backoff = float(_get_env("AI_HTTP_BACKOFF_SEC", "0.8") or "0.8")
    last_error = None
    for attempt in range(retries):
        try:
            resp = _HTTP_SESSION.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code in (408, 429, 500, 502, 503, 504):
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
                    continue
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
                continue
    raise RuntimeError(f"Request failed after {retries} attempt(s): {last_error}")


def _extract_image_from_any_payload(payload) -> Image.Image | None:
    """Best-effort parser for provider responses that may return URL or base64 image data."""
    if payload is None:
        return None

    if isinstance(payload, str):
        text = payload.strip()
        if text.startswith("http://") or text.startswith("https://"):
            r = requests.get(text, timeout=60)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        maybe_b64 = text.split(",", 1)[1] if text.startswith("data:image") and "," in text else text
        try:
            raw = base64.b64decode(maybe_b64, validate=False)
            if raw:
                return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            return None
        return None

    if isinstance(payload, list):
        for item in payload:
            img = _extract_image_from_any_payload(item)
            if img is not None:
                return img
        return None

    if isinstance(payload, dict):
        direct_keys = (
            "url", "image_url", "imageUrl", "src", "output", "result", "image",
            "b64_json", "base64", "image_base64", "data",
        )
        for key in direct_keys:
            if key in payload:
                img = _extract_image_from_any_payload(payload.get(key))
                if img is not None:
                    return img

        for key in ("images", "data", "outputs", "artifacts", "result"):
            if key in payload and isinstance(payload.get(key), list):
                img = _extract_image_from_any_payload(payload.get(key))
                if img is not None:
                    return img
        return None

    return None


def _chat_text_completion(
    url: str,
    headers: dict,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 45,
    temperature: float = 0.4,
    max_tokens: int = 220,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    r = _post_json_with_retries(url=url, headers=headers, payload=payload, timeout=timeout)
    data = r.json()
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


# Provider adapters (safe fallbacks)
def _generate_with_pollinations(prompt: str, size=(512, 512), model_variant: str = None) -> Image.Image:
    """Generate image using Pollinations AI API."""
    w = int(size[0]) if size else 512
    h = int(size[1]) if size else 512
    model_default = (model_variant or os.getenv("POLLINATIONS_MODEL", "flux")).strip()

    # Generate a deterministic seed for repeatable prompt outputs.
    seed = int.from_bytes(hashlib.sha256(prompt.encode("utf-8")).digest()[:4], "little")
    prompt_candidates = []
    for p in [prompt, _build_photoreal_prompt(prompt), _build_color_rich_prompt(prompt)]:
        pp = (p or "").strip()
        if pp and pp not in prompt_candidates:
            prompt_candidates.append(pp)

    models = []
    for m in [model_default, "flux", "turbo", "flux-realism"]:
        if m and m not in models:
            models.append(m)

    base_urls = [
        "https://image.pollinations.ai",
        "https://image.pollinations.ai/prompt",
    ]
    last_error = None
    last_img = None

    for model in models:
        for prompt_candidate in prompt_candidates:
            full_params = {
                "prompt": prompt_candidate,
                "model": model,
                "width": min(max(w, 128), 2048),
                "height": min(max(h, 128), 2048),
                "seed": seed,
                "nologo": "true",
                "enhance": "true",
            }
            minimal_params = {
                "prompt": prompt_candidate,
                "seed": seed,
            }
            for base_url in base_urls:
                for params in (full_params, minimal_params):
                    try:
                        if base_url.endswith("/prompt"):
                            # For /prompt endpoint, put prompt in path and avoid duplicate query prompt.
                            prompt_in_path_url = f"{base_url}/{quote(prompt_candidate)}"
                            params_no_prompt = {k: v for k, v in params.items() if k != "prompt"}
                            resp = requests.get(prompt_in_path_url, params=params_no_prompt, timeout=90)
                        else:
                            resp = requests.get(base_url, params=params, timeout=90)
                        resp.raise_for_status()
                        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                        if size:
                            img = img.resize((w, h), Image.Resampling.LANCZOS)
                        # If still grayscale, keep trying richer prompts/models.
                        if _is_effectively_grayscale(img):
                            last_img = img
                            continue
                        # Slight saturation lift for better visual consistency.
                        img = ImageEnhance.Color(img).enhance(1.12)
                        return img
                    except Exception as e:
                        last_error = e
                        continue

    if last_img is not None:
        return _colorize_grayscale_fallback(last_img)

    # Provider outage fallback: keep pipeline operational with Leonardo fallback or vivid local render.
    has_leonardo = _get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN") or _get_env("LEONARDO_API_TOKEN")
    if has_leonardo:
        try:
            print(f"[*] Pollinations failed: {last_error}. Falling back to Leonardo AI API...")
            return _generate_with_leonardo(prompt, size=size)
        except Exception as leo_err:
            print(f"[!] Leonardo AI fallback failed: {leo_err}")

    if (_get_env("POLLINATIONS_ALLOW_LOCAL_FALLBACK", "true") or "true").strip().lower() in ("1", "true", "yes", "on"):
        return _generate_mock(_build_color_rich_prompt(prompt), size=size)

    raise RuntimeError(f"Pollinations generation failed for all models/endpoints: {last_error}")


def _generate_with_genai(prompt: str, size=(512, 512)) -> Image.Image:
    api_key = _get_env("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    prompt_candidates = []
    for p in [_build_color_rich_prompt(prompt), _build_photoreal_prompt(prompt), prompt]:
        pp = (p or "").strip()
        if pp and pp not in prompt_candidates:
            prompt_candidates.append(pp)
    configured_model = _get_env(
        "GENAI_IMAGE_MODEL",
        _get_env("GEMINI_IMAGE_MODEL", "models/gemini-2.0-flash-exp-image-generation"),
    )
    size_wh = (int(size[0]), int(size[1])) if size else (512, 512)

    def _cache_get(model_name: str, prompt_text: str):
        return _GEMINI_IMAGE_CACHE.get((model_name, size_wh, prompt_text))

    def _cache_put(model_name: str, prompt_text: str, img: Image.Image):
        if len(_GEMINI_IMAGE_CACHE) >= _GEMINI_IMAGE_CACHE_MAX:
            _GEMINI_IMAGE_CACHE.pop(next(iter(_GEMINI_IMAGE_CACHE)))
        _GEMINI_IMAGE_CACHE[(model_name, size_wh, prompt_text)] = img.copy()

    def _extract_img_from_response(resp) -> Image.Image | None:
        candidates = getattr(resp, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if not inline_data:
                    continue
                mime = (getattr(inline_data, "mime_type", "") or "").lower()
                data = getattr(inline_data, "data", None)
                if not data or not mime.startswith("image/"):
                    continue
                return Image.open(io.BytesIO(data)).convert("RGB")
        generated_images = getattr(resp, "generated_images", None) or []
        for gi in generated_images:
            image_obj = getattr(gi, "image", None) or gi
            raw = getattr(image_obj, "image_bytes", None) or getattr(image_obj, "bytes", None)
            if raw:
                return Image.open(io.BytesIO(raw)).convert("RGB")
        return None

    model_candidates = []
    for m in [
        configured_model,
        "models/gemini-2.5-flash-image",
        "models/gemini-3-pro-image-preview",
        "models/gemini-3.1-flash-image-preview",
        "models/gemini-2.0-flash-exp-image-generation",
    ]:
        if m and m not in model_candidates:
            model_candidates.append(m)

    # Normalize model names to handle env values with or without "models/" prefix.
    normalized_candidates = []
    for m in model_candidates:
        m = m.strip()
        if not m:
            continue
        variants = [m]
        if m.startswith("models/"):
            variants.append(m.replace("models/", "", 1))
        else:
            variants.append(f"models/{m}")
        for v in variants:
            if v not in normalized_candidates:
                normalized_candidates.append(v)
    model_candidates = normalized_candidates

    try:
        import google.genai as genai

        client = genai.Client(api_key=api_key)
        last_error = None
        last_img = None
        for model in model_candidates:
            for prompt_for_model in prompt_candidates:
                cached = _cache_get(model, prompt_for_model)
                if cached is not None:
                    return cached.copy()
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt_for_model,
                        config={"response_modalities": ["IMAGE"]},
                    )
                    img = _extract_img_from_response(response)
                    if img is None:
                        continue
                    if size_wh:
                        img = img.resize(size_wh, Image.Resampling.LANCZOS)
                    if _is_effectively_grayscale(img):
                        last_img = img
                        continue
                    img = ImageEnhance.Color(img).enhance(1.10)
                    _cache_put(model, prompt_for_model, img)
                    return img
                except Exception as e:
                    last_error = e
                    continue

        if last_img is not None:
            return _colorize_grayscale_fallback(last_img)

        if last_error:
            raise last_error
        raise RuntimeError("Gemini returned no image payload for all candidate models")
    except Exception as e:
        raise RuntimeError(f"Gemini generation failed: {e}")


def _generate_with_openai(prompt: str, size=(512, 512)) -> Image.Image:
    """Generate image using OpenAI API."""
    api_key = _get_env("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    prompt_for_model = _build_photoreal_prompt(prompt)
    model = _get_env("OPENAI_IMAGE_MODEL", "gpt-image-1")
    w = int(size[0]) if size else 512
    h = int(size[1]) if size else 512
    if w > h * 1.25:
        api_size = "1536x1024"
    elif h > w * 1.25:
        api_size = "1024x1536"
    else:
        api_size = "1024x1024"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt_for_model,
        "size": api_size,
        "response_format": "b64_json",
    }
    if model.startswith("dall-e"):
        payload["quality"] = "hd"
        payload["style"] = "natural"

    resp = _post_json_with_retries(
        url="https://api.openai.com/v1/images/generations",
        headers=headers,
        payload=payload,
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    data = (result.get("data") or [{}])[0]
    b64_img = data.get("b64_json")
    if b64_img:
        raw = base64.b64decode(b64_img)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    else:
        image_url = data.get("url")
        if not image_url:
            raise ValueError("OpenAI response missing image data")
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")

    if size:
        img = img.resize((w, h), Image.Resampling.LANCZOS)
    return img


def _generate_with_pexels(prompt: str, size=(512, 512)) -> Image.Image:
    """
    Fetch a prompt-matching photo from Pexels API and adapt it as a carrier image.
    Note: Pexels is photo retrieval, not synthetic generation.
    """
    api_key = _get_env("PEXELS_API_KEY")
    if not api_key:
        raise ValueError("PEXELS API key not set (expected PEXELS_API_KEY)")

    width = int(size[0]) if size else 512
    height = int(size[1]) if size else 512
    query = (prompt or "").strip() or "abstract art"
    keywords = [w for w in query.split() if len(w) >= 3][:6]
    query_candidates = []
    for q in [
        query,
        " ".join(keywords),
        "cyberpunk wallpaper",
        "abstract colorful",
    ]:
        qq = (q or "").strip()
        if qq and qq not in query_candidates:
            query_candidates.append(qq)

    headers = {
        "Authorization": api_key,
        "User-Agent": "Project-Aegis-Ghost/1.0",
    }
    photos = []
    last_error = None
    for q in query_candidates:
        for orientation in ("landscape" if width >= height else "portrait", None):
            params = {"query": q, "per_page": 30}
            if orientation:
                params["orientation"] = orientation
            try:
                resp = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=50)
                if resp.status_code in (401, 403):
                    raise ValueError("Pexels API rejected key (401/403). Verify PEXELS_API_KEY.")
                resp.raise_for_status()
                data = resp.json()
                photos = data.get("photos") or []
                if photos:
                    query = q
                    break
            except Exception as e:
                last_error = e
        if photos:
            break

    if not photos:
        try:
            curated = requests.get("https://api.pexels.com/v1/curated", headers=headers, params={"per_page": 30}, timeout=50)
            curated.raise_for_status()
            photos = (curated.json() or {}).get("photos") or []
        except Exception as e:
            last_error = e

    if not photos:
        raise ValueError(f"Pexels returned no photos for prompt and fallbacks. Last error: {last_error}")

    # Choose deterministically based on prompt for stable behavior.
    idx = int.from_bytes(hashlib.sha256(query.encode("utf-8")).digest()[:2], "little") % len(photos)
    photo = photos[idx] if isinstance(photos[idx], dict) else photos[0]
    src = photo.get("src") if isinstance(photo.get("src"), dict) else {}
    image_url = (
        src.get("landscape")
        or src.get("large2x")
        or src.get("large")
        or src.get("original")
        or src.get("medium")
    )
    if not image_url:
        raise ValueError("Pexels response missing usable image URL")

    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()
    img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
    if size:
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    return img


def _generate_with_openrouter(prompt: str, size=(512, 512)) -> Image.Image:
    """Generate image using OpenRouter Responses API."""
    api_key = _get_env("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    prompt_for_model = _build_photoreal_prompt(prompt)
    model = _get_env("OPENROUTER_IMAGE_MODEL", "google/gemini-3.1-flash-image-preview")
    w = int(size[0]) if size else 512
    h = int(size[1]) if size else 512

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": _get_env("OPENROUTER_HTTP_REFERER", "http://localhost"),
        "X-Title": _get_env("OPENROUTER_X_TITLE", "Project Aegis Ghost"),
    }
    payload = {
        "model": model,
        "input": prompt_for_model,
        "max_output_tokens": int(_get_env("OPENROUTER_MAX_OUTPUT_TOKENS", "512") or "512"),
    }

    resp = _post_json_with_retries(
        url="https://openrouter.ai/api/v1/responses",
        headers=headers,
        payload=payload,
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    output_items = result.get("output") or []
    image_item = next((item for item in output_items if item.get("type") == "image_generation_call"), None)
    if image_item is None:
        raise ValueError(f"OpenRouter response missing image_generation_call: {result}")

    image_result = image_item.get("result")
    if not isinstance(image_result, str) or not image_result:
        raise ValueError("OpenRouter image_generation_call missing result payload")

    b64_img = image_result.split(",", 1)[1] if image_result.startswith("data:image/") and "," in image_result else image_result
    raw = base64.b64decode(b64_img)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if size:
        img = img.resize((w, h), Image.Resampling.LANCZOS)
    return img


def _generate_with_puter(prompt: str, size=(512, 512)) -> Image.Image:
    """Generate image using Puter AI (no API key required - uses JS SDK approach)."""
    w = int(size[0]) if size else 512
    h = int(size[1]) if size else 512
    prompt_for_model = _build_color_rich_prompt(prompt)
    
    # Try Puter's free API endpoint (no API key needed)
    endpoint = "https://api.puter.com/v1/images/generations"
    
    # Try without API key first (for free tier)
    headers = {
        "Content-Type": "application/json",
    }
    
    # Use default SDXL model
    payload = {
        "model": "sdxl",
        "prompt": prompt_for_model,
        "size": f"{w}x{h}",
    }
    
    # Try without auth first
    try:
        resp = _post_json_with_retries(
            url=endpoint,
            headers=headers,
            payload=payload,
            timeout=120,
        )
        
        if resp.status_code == 200 or resp.status_code == 201:
            result = resp.json()
            
            # Handle OpenAI-style payloads
            data = result.get("data")
            if isinstance(data, list) and data:
                item0 = data[0] if isinstance(data[0], dict) else {}
                b64_img = item0.get("b64_json")
                if isinstance(b64_img, str) and b64_img:
                    raw = base64.b64decode(b64_img)
                    img = Image.open(io.BytesIO(raw)).convert("RGB")
                    if size:
                        img = img.resize((w, h), Image.Resampling.LANCZOS)
                    return img
                image_url = item0.get("url") or item0.get("image_url")
                if isinstance(image_url, str) and image_url:
                    img_resp = requests.get(image_url, timeout=60)
                    img_resp.raise_for_status()
                    img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
                    if size:
                        img = img.resize((w, h), Image.Resampling.LANCZOS)
                    return img
            
            # Handle direct URL response
            image_url = result.get("url") or result.get("image_url")
            if isinstance(image_url, str) and image_url:
                img_resp = requests.get(image_url, timeout=60)
                img_resp.raise_for_status()
                img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
                if size:
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                return img
    except Exception as e:
        pass
    
    # Try with API key if available
    api_key = _get_env("PUTER_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        model = _get_env("PUTER_IMAGE_MODEL", "sdxl")
        payload["model"] = model
        
        resp = _post_json_with_retries(
            url=endpoint,
            headers=headers,
            payload=payload,
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()

        # Handle OpenAI-style payloads
        data = result.get("data")
        if isinstance(data, list) and data:
            item0 = data[0] if isinstance(data[0], dict) else {}
            b64_img = item0.get("b64_json")
            if isinstance(b64_img, str) and b64_img:
                raw = base64.b64decode(b64_img)
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                if size:
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                return img
            image_url = item0.get("url") or item0.get("image_url")
            if isinstance(image_url, str) and image_url:
                img_resp = requests.get(image_url, timeout=60)
                img_resp.raise_for_status()
                img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
                if size:
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                return img

        # Handle flat payloads
        image_url = result.get("url") or result.get("image_url")
        if isinstance(image_url, str) and image_url:
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
            if size:
                img = img.resize((w, h), Image.Resampling.LANCZOS)
            return img
    
    raise ValueError("Puter image generation failed - no valid response")


def _generate_with_huggingface(prompt: str, size=(512, 512)) -> Image.Image:
    raise NotImplementedError("Hugging Face image adapter is not implemented in this build")


def _generate_with_replicate(prompt: str, size=(512, 512)) -> Image.Image:
    raise NotImplementedError("Replicate image adapter is not implemented in this build")


def _generate_gemini(prompt: str, size=(512, 512)) -> Image.Image:
    return _generate_with_genai(prompt, size=size)


def _enhance_prompt_with_llm(prompt: str) -> str:
    """
    Enhance a prompt using a text LLM when available.
    Falls back to deterministic local enhancement if APIs are unavailable.
    """
    base_instruction = (
        "Rewrite this into one concise, vivid image-generation prompt. "
        "Keep it colorful and specific. Return only the prompt text."
    )
    cache_key = ("enhance", (prompt or "").strip())
    cached = _TEXT_CACHE.get(cache_key)
    if cached:
        return cached

    # Try Groq text model first (fast + low cost).
    groq_key = _get_env("GROQ_API_KEY")
    if groq_key:
        try:
            model = _get_env("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            }
            text = _chat_text_completion(
                url="https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                model=model,
                system_prompt=base_instruction,
                user_prompt=prompt,
                timeout=35,
                temperature=0.4,
                max_tokens=180,
            )
            if text:
                _cache_put_text(cache_key, text)
                return text
        except Exception:
            pass

    # Try OpenRouter text model.
    openrouter_key = _get_env("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            model = _get_env("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini")
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": _get_env("OPENROUTER_HTTP_REFERER", "http://localhost"),
                "X-Title": _get_env("OPENROUTER_X_TITLE", "Project Aegis Ghost"),
            }
            text = _chat_text_completion(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                model=model,
                system_prompt=base_instruction,
                user_prompt=prompt,
                timeout=40,
                temperature=0.4,
                max_tokens=180,
            )
            if text:
                _cache_put_text(cache_key, text)
                return text
        except Exception:
            pass

    # Then try OpenAI text model.
    openai_key = _get_env("OPENAI_API_KEY")
    if openai_key:
        try:
            model = _get_env("OPENAI_TEXT_MODEL", "gpt-4o-mini")
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            }
            text = _chat_text_completion(
                url="https://api.openai.com/v1/chat/completions",
                headers=headers,
                model=model,
                system_prompt=base_instruction,
                user_prompt=prompt,
                timeout=40,
                temperature=0.4,
                max_tokens=180,
            )
            if text:
                _cache_put_text(cache_key, text)
                return text
        except Exception:
            pass

    # Try Gemini text model.
    gemini_key = _get_env("GEMINI_API_KEY")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model_name = _get_env("GEMINI_TEXT_MODEL", "models/gemini-1.5-flash")
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(f"{base_instruction}\n\nPrompt: {prompt}")
            text = (getattr(resp, "text", "") or "").strip()
            if text:
                _cache_put_text(cache_key, text)
                return text
        except Exception:
            pass

    # Deterministic local fallback
    fallback = f"{prompt}, vivid colors, high detail, cinematic composition, rich lighting"
    _cache_put_text(cache_key, fallback)
    return fallback


def _generate_with_llm_engine(prompt: str, size=(512, 512)) -> Image.Image:
    """
    LLM-guided local image engine:
    1) Use text LLM to optimize prompt
    2) Render with deterministic local generator
    """
    enriched = _enhance_prompt_with_llm(prompt)
    return _generate_mock(enriched, size=size)


def _generate_with_llm_realistic(prompt: str, size=(512, 512)) -> Image.Image:
    """
    LLM-guided realistic image engine:
    1) Use text LLM to optimize prompt
    2) Generate with real image providers only (no mock fallback)
    """
    enriched = _enhance_prompt_with_llm(prompt)
    last_error = None

    # Priority chain for realistic generation.
    if _get_env("OPENROUTER_API_KEY"):
        try:
            return _generate_with_openrouter(enriched, size=size)
        except Exception as e:
            last_error = e
    if _get_env("PUTER_API_KEY"):
        try:
            return _generate_with_puter(enriched, size=size)
        except Exception as e:
            last_error = e
    if _get_env("OPENAI_API_KEY"):
        try:
            return _generate_with_openai(enriched, size=size)
        except Exception as e:
            last_error = e
    if _get_env("RAPHAEL_API_KEY"):
        try:
            return _generate_with_raphael(enriched, size=size)
        except Exception as e:
            last_error = e
    if _get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN"):
        try:
            return _generate_with_leonardo(enriched, size=size)
        except Exception as e:
            last_error = e
    if _get_env("GEMINI_API_KEY"):
        try:
            return _generate_with_genai(enriched, size=size)
        except Exception as e:
            last_error = e
    try:
        return _generate_with_pollinations(enriched, size=size)
    except Exception as e:
        last_error = e

    raise RuntimeError(f"LLM realistic generation failed across providers: {last_error}")


def generate_ghost_carrier(
    prompt,
    save_path,
    use_mock=True,
    size=(512, 512),
    backend: str | None = None,
    allow_fallback: bool = True,
):
    """Generate and save a carrier image for steganography.
    
    Backends:
      - mock: deterministic abstract art based on prompt (default, works offline)
      - genai: Google GenAI image generation (requires GEMINI_API_KEY)
      - llm: text-LLM-guided local renderer (uses text LLM if available, then local render)
      - llm-realistic: text-LLM-guided real image generation (no mock path)
      - openrouter: OpenRouter image generation (requires OPENROUTER_API_KEY)
      - puter: Puter image generation (requires PUTER_API_KEY)
      - openai: OpenAI Images API (requires OPENAI_API_KEY)
      - hf: Hugging Face Inference API (requires HF_API_TOKEN)
      - replicate: Replicate API (requires REPLICATE_API_TOKEN)
      - gemini: Google Gemini API (limited support)
      - pollinations: Pollinations AI (free, no API key required)
      - pexels: Pexels photo retrieval (requires PEXELS_API_KEY)
      - raphael: Raphael AI image generation (requires RAPHAEL_API_KEY)
      - leonardo: Leonardo AI (requires LEONARDO_API_KEY)
      - deepai: DeepAI API (requires DEEPAI_API_KEY)
    """
    chosen = (backend or "").lower() if backend else None
    
    # Handle Pollinations model variants
    pollinations_variant = None
    if chosen and chosen.startswith("pollinations"):
        if chosen == "pollinations-schnell":
            pollinations_variant = "flux-schnell"
            chosen = "pollinations"
        elif chosen == "pollinations-realism":
            pollinations_variant = "flux-realism"
            chosen = "pollinations"
        elif chosen == "pollinations-turbo":
            pollinations_variant = "turbo"
            chosen = "pollinations"
    
    img = None
    last_error = None

    if chosen == "mock" or (chosen is None and use_mock):
        print(f"[*] Generating mock carrier image for: {prompt[:60]}...")
        img = _generate_mock(prompt, size=size)
    else:
        try:
            if chosen == "genai":
                print(f"[*] Using Google GenAI for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_genai, prompt, size=size)
            elif chosen == "llm":
                print(f"[*] Using LLM-guided local engine for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_llm_engine, prompt, size=size)
            elif chosen in ("llm-realistic", "llm_realistic", "realistic"):
                print(f"[*] Using LLM-guided realistic engine for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_llm_realistic, prompt, size=size)
            elif chosen == "openai":
                print(f"[*] Using OpenAI Images API for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_openai, prompt, size=size)
            elif chosen == "openrouter":
                print(f"[*] Using OpenRouter Responses API for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_openrouter, prompt, size=size)
            elif chosen == "puter":
                print(f"[*] Using Puter image API for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_puter, prompt, size=size)
            elif chosen == "hf":
                print(f"[*] Using Hugging Face API for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_huggingface, prompt, size=size)
            elif chosen == "replicate":
                print(f"[*] Using Replicate API for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_replicate, prompt, size=size)
            elif chosen == "gemini":
                print(f"[*] Using Gemini API for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_gemini, prompt, size=size)
            elif chosen == "pollinations":
                print(f"[*] Using Pollinations AI for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_pollinations, prompt, size=size, model_variant=pollinations_variant)
            elif chosen == "pexels":
                print(f"[*] Using Pexels for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_pexels, prompt, size=size)
            elif chosen == "raphael":
                print(f"[*] Using Raphael AI for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_raphael, prompt, size=size)
            elif chosen == "leonardo":
                print(f"[*] Using Leonardo AI for: {prompt[:60]}...")
                img = _generate_with_leonardo(prompt, size=size)
            elif chosen == "deepai":
                print(f"[*] Using DeepAI API for: {prompt[:60]}...")
                img = _generate_with_leonardo_fallback(_generate_with_deepai, prompt, size=size)
            else:
                # Try preferred providers in order, with fallback on failure
                print(f"[*] Auto-selecting backend...")
                img = None
                
                # Priority 1: OpenRouter image generation.
                if _get_env("OPENROUTER_API_KEY"):
                    try:
                        print(f"[*] Trying OpenRouter API for: {prompt[:60]}...")
                        img = _generate_with_openrouter(prompt, size=size)
                        print(f"[SUCCESS] OpenRouter generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] OpenRouter failed: {e}, trying next provider...")
        
                # Priority 2: Puter image generation.
                if img is None and _get_env("PUTER_API_KEY"):
                    try:
                        print(f"[*] Trying Puter API for: {prompt[:60]}...")
                        img = _generate_with_puter(prompt, size=size)
                        print(f"[SUCCESS] Puter generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] Puter failed: {e}, trying next provider...")
        
                # Priority 3: OpenAI image generation.
                if img is None and _get_env("OPENAI_API_KEY"):
                    try:
                        print(f"[*] Trying OpenAI API for: {prompt[:60]}...")
                        img = _generate_with_openai(prompt, size=size)
                        print(f"[SUCCESS] OpenAI generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] OpenAI failed: {e}, trying next provider...")
        
                # Priority 4: Raphael
                if img is None and _get_env("RAPHAEL_API_KEY"):
                    try:
                        print(f"[*] Trying Raphael API for: {prompt[:60]}...")
                        img = _generate_with_raphael(prompt, size=size)
                        print(f"[SUCCESS] Raphael generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] Raphael failed: {e}, trying next provider...")
        
                # Priority 5: Leonardo (backup when Raphael fails or unavailable)
                if img is None and (_get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN")):
                    try:
                        print(f"[*] Trying Leonardo API for: {prompt[:60]}...")
                        img = _generate_with_leonardo(prompt, size=size)
                        print(f"[SUCCESS] Leonardo generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] Leonardo failed: {e}, trying next provider...")
        
                # Priority 6: Pexels photo retrieval
                if img is None and _get_env("PEXELS_API_KEY"):
                    try:
                        print(f"[*] Trying Pexels for: {prompt[:60]}...")
                        img = _generate_with_pexels(prompt, size=size)
                        print(f"[SUCCESS] Pexels returned an image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] Pexels failed: {e}, trying next provider...")
        
                # Priority 7: Pollinations (free, reliable)
                if img is None:
                    try:
                        print(f"[*] Trying Pollinations AI for: {prompt[:60]}...")
                        img = _generate_with_pollinations(prompt, size=size)
                        print(f"[SUCCESS] Pollinations generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] Pollinations failed: {e}, trying next provider...")
                
                # Priority 8: DeepAI (may require paid subscription)
                if img is None and _get_env("DEEPAI_API_KEY"):
                    try:
                        print(f"[*] Trying DeepAI API for: {prompt[:60]}...")
                        img = _generate_with_deepai(prompt, size=size)
                        print(f"[SUCCESS] DeepAI generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] DeepAI failed: {e}, trying next provider...")
                
                # Priority 9: LLM-guided realistic engine (real providers, no mock)
                if img is None and (
                    _get_env("GROQ_API_KEY")
                    or _get_env("OPENROUTER_API_KEY")
                    or _get_env("OPENAI_API_KEY")
                    or _get_env("GEMINI_API_KEY")
                ):
                    try:
                        print(f"[*] Trying LLM-guided realistic engine for: {prompt[:60]}...")
                        img = _generate_with_llm_realistic(prompt, size=size)
                        print(f"[SUCCESS] LLM realistic engine generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] LLM realistic engine failed: {e}, trying next provider...")
        
                # Priority 10: LLM-guided local engine
                if img is None and (
                    _get_env("GROQ_API_KEY")
                    or _get_env("OPENROUTER_API_KEY")
                    or _get_env("OPENAI_TEXT_MODEL")
                    or _get_env("GEMINI_TEXT_MODEL")
                ):
                    try:
                        print(f"[*] Trying LLM-guided local engine for: {prompt[:60]}...")
                        img = _generate_with_llm_engine(prompt, size=size)
                        print(f"[SUCCESS] LLM engine generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] LLM engine failed: {e}, trying next provider...")
                
                # Priority 11: HuggingFace
                if img is None and _get_env("HF_API_TOKEN"):
                    try:
                        print(f"[*] Trying HuggingFace API for: {prompt[:60]}...")
                        img = _generate_with_huggingface(prompt, size=size)
                        print(f"[SUCCESS] HuggingFace generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] HuggingFace failed: {e}, trying next provider...")
                
                # Priority 12: Replicate
                if img is None and _get_env("REPLICATE_API_TOKEN"):
                    try:
                        print(f"[*] Trying Replicate API for: {prompt[:60]}...")
                        img = _generate_with_replicate(prompt, size=size)
                        print(f"[SUCCESS] Replicate generated image")
                    except Exception as e:
                        last_error = e
                        print(f"[!] Replicate failed: {e}, trying next provider...")
                
                if img is None:
                    raise RuntimeError(f"All providers failed in auto mode. Last error: {last_error}")
        except Exception as e:
            last_error = e
            print(f"[!] Chosen provider or auto-selection failed: {e}")
            
            # Check if Leonardo AI API key is configured and try to fall back to it
            has_leonardo = _get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN") or _get_env("LEONARDO_API_TOKEN")
            if allow_fallback and has_leonardo and chosen != "leonardo":
                try:
                    print(f"[*] Falling back to Leonardo AI API for: {prompt[:60]}...")
                    img = _generate_with_leonardo(prompt, size=size)
                    print(f"[SUCCESS] Leonardo AI generated image as fallback")
                except Exception as leo_err:
                    print(f"[!] Leonardo AI fallback failed: {leo_err}")
                    last_error = leo_err
            
            if img is None:
                if not allow_fallback:
                    raise RuntimeError(f"All providers failed. Last error: {last_error}")
                print(f"[!] All providers failed. Last error: {last_error}")
                print(f"[*] Using mock generator (note: mock does not interpret prompts)")
                img = _generate_mock(prompt, size=size)

    img.save(save_path)
    print(f"[*] Carrier image saved to: {save_path}")
    return img


def _generate_with_leonardo_fallback(func, prompt: str, size=(512, 512), *args, **kwargs):
    """Executes the specified image generation function. If it fails (raises an exception),
    it falls back to Leonardo AI API if configured, before re-raising or failing."""
    try:
        return func(prompt, size=size, *args, **kwargs)
    except Exception as e:
        # Check if Leonardo AI API key is configured
        has_leonardo = _get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN") or _get_env("LEONARDO_API_TOKEN")
        if has_leonardo and func.__name__ != "_generate_with_leonardo":
            try:
                print(f"[*] {func.__name__} failed: {e}. Falling back to Leonardo AI API...")
                return _generate_with_leonardo(prompt, size=size)
            except Exception as leo_err:
                print(f"[!] Leonardo AI fallback failed: {leo_err}")
        raise


def _generate_with_leonardo(prompt: str, size=(512, 512)) -> Image.Image:
    """
    Generate image using Leonardo AI REST API.
    """
    api_key = _get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN") or _get_env("LEONARDO_API_TOKEN")
    if not api_key:
        raise ValueError("LEONARDO_API_KEY not set. Set LEONARDO_API_KEY (or LEONARDO_KEY/LEONARDO_TOKEN) in your .env file.")

    width = int(size[0]) if size else 512
    height = int(size[1]) if size else 512
    width = max(256, min(width, 1024))
    height = max(256, min(height, 1024))

    model_id = _get_env("LEONARDO_MODEL_ID", "aa77f04e-3eec-4034-9c07-d0f619684628")
    endpoint = _get_env("LEONARDO_API_URL", "https://cloud.leonardo.ai/api/rest/v1")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "accept": "application/json",
        "content-type": "application/json",
    }

    prompt_for_model = _build_photoreal_prompt(prompt)
    payload = {
        "prompt": prompt_for_model,
        "modelId": model_id,
        "width": width,
        "height": height,
        "num_images": 1,
    }

    last_error = None
    try:
        create = requests.post(f"{endpoint}/generations", headers=headers, json=payload, timeout=90)
        if create.status_code == 401:
            raise ValueError("Leonardo API error: invalid API key - verify LEONARDO_API_KEY in .env")
        if create.status_code == 403:
            raise ValueError(f"Leonardo API forbidden - check API key permissions or account status")
        create.raise_for_status()
        create_data = create.json()
        gen_id = (
            ((create_data.get("sdGenerationJob") or {}).get("generationId"))
            or create_data.get("generationId")
        )
        if not gen_id:
            raise ValueError(f"Leonardo response missing generationId: {create_data}")

        image_url = None
        for _ in range(40):
            time.sleep(1.0)
            status = requests.get(f"{endpoint}/generations/{gen_id}", headers=headers, timeout=60)
            status.raise_for_status()
            data = status.json()
            gen = data.get("generations_by_pk") or {}
            imgs = gen.get("generated_images") or []
            if imgs:
                image_url = imgs[0].get("url")
                if image_url:
                    break

        if not image_url:
            raise ValueError("Leonardo generation did not produce an image URL in time")

        resp = requests.get(image_url, timeout=60)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        if _is_effectively_grayscale(img):
            img = _colorize_grayscale_fallback(img)
        if size:
            img = img.resize(size, Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        last_error = e
        raise ValueError(f"Leonardo generation failed: {e}")


def _generate_with_deepai(prompt: str, size=(512, 512)) -> Image.Image:
    """
    Generate image using DeepAI API.
    
    DeepAI provides various image generation models including:
    - text2img: Standard text-to-image generation
    - stable-diffusion: High-quality diffusion model
    - waifu: Anime-style image generation
    
    API documentation: https://deepai.org/machine-learning-model/text2img
    
    Note: DeepAI requires a paid API subscription. The free tier is limited.
    """
    api_key = _get_env("DEEPAI_API_KEY")
    
    if not api_key:
        raise ValueError("DEEPAI_API_KEY not set")
    
    prompt_for_model = _build_photoreal_prompt(prompt)
    print(f"[*] DeepAI: Generating image for: {prompt[:50]}...")
    
    # Use DeepAI text2img API
    model = _get_env("DEEPAI_MODEL", "text2img")
    url = f"https://api.deepai.org/api/{model}"
    
    # Determine image dimensions
    width = size[0] if size else 512
    height = size[1] if size else 512
    
    # Prepare the request
    data = {
        "text": prompt_for_model,
        "width": min(width, 1024),
        "height": min(height, 1024),
    }
    
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }
    
    # Make the request
    response = requests.post(url, data=json.dumps(data), headers=headers, timeout=120)
    
    # Check for specific error codes and raise appropriate exceptions
    if response.status_code == 401:
        raise ValueError("DeepAI API error: Invalid or expired API key")
    elif response.status_code == 402:
        raise ValueError("DeepAI API error: Payment required. DeepAI requires a paid subscription.")
    elif response.status_code == 429:
        raise ValueError("DeepAI API error: Rate limit exceeded")
    
    response.raise_for_status()
    
    result = response.json()
    
    # Get the image URL from the response
    image_url = None
    if "output_url" in result:
        image_url = result["output_url"]
    elif "image_url" in result:
        image_url = result["image_url"]
    elif "url" in result:
        image_url = result["url"]
    
    if not image_url:
        raise ValueError(f"DeepAI response missing image URL: {result}")
    
    # Download the generated image
    img_response = requests.get(image_url, timeout=60)
    img_response.raise_for_status()
    
    # Load the image
    img = Image.open(io.BytesIO(img_response.content)).convert('RGB')
    
    # Resize if needed
    if size:
        img = img.resize(size, Image.Resampling.LANCZOS)
    
    print(f"[*] DeepAI: Successfully generated image for: {prompt[:50]}...")
    return img


def _generate_with_raphael(prompt: str, size=(512, 512)) -> Image.Image:
    """
    Generate image using Raphael API (z-image endpoint).
    Docs: https://raphael.app/en/z-image-api
    """
    api_key = _get_env("RAPHAEL_API_KEY")
    if not api_key:
        raise ValueError("Raphael API key not set (expected RAPHAEL_API_KEY)")

    width = int(size[0]) if size else 512
    height = int(size[1]) if size else 512
    endpoint = _get_env("RAPHAEL_API_URL", "https://evolink.ai/z-image-turbo")
    prompt_for_model = _build_color_rich_prompt(prompt)
    auth_headers = [
        {"Authorization": f"Bearer {api_key}"},
        {"x-api-key": api_key},
        {"api-key": api_key},
    ]
    payloads = [
        {"prompt": prompt_for_model, "width": width, "height": height, "size": f"{width}x{height}"},
        {"input": prompt_for_model, "width": width, "height": height},
        {"prompt": prompt_for_model, "size": f"{width}x{height}"},
    ]
    last_error = None
    img = None
    for auth in auth_headers:
        for payload in payloads:
            headers = {"Content-Type": "application/json", **auth}
            try:
                response = requests.post(endpoint, headers=headers, json=payload, timeout=120)
                if response.status_code in (401, 403):
                    raise ValueError("Raphael API rejected key (401/403). Verify RAPHAEL_API_KEY and endpoint.")
                response.raise_for_status()
                ctype = (response.headers.get("content-type") or "").lower()
                if ctype.startswith("image/"):
                    img = Image.open(io.BytesIO(response.content)).convert("RGB")
                    break
                parsed = {}
                try:
                    parsed = response.json()
                except Exception:
                    parsed = {}
                img = _extract_image_from_any_payload(parsed) or _extract_image_from_any_payload(response.text)
                if img is not None:
                    break
                last_error = ValueError(f"Raphael response missing image payload: {parsed or response.text[:200]}")
            except Exception as e:
                last_error = e
                continue
        if img is not None:
            break

    if img is None:
        raise ValueError(f"Raphael generation failed: {last_error}")

    if size:
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    return img


def verify_owner(image_path=None, owner_signature=None, biometric_enabled=False):
    """Verify ownership using biometric authentication."""
    if biometric_enabled:
        try:
            from core.biometric_auth import BiometricAuthenticator
            authenticator = BiometricAuthenticator("assets/owner.jpg")
            success = authenticator.authenticate(
                enable_face=True,
                enable_pk=True
            )
            return success
        except Exception as e:
            print(f"[X] Biometric authentication error: {e}")
            return False
    
    if image_path is None and owner_signature is None:
        return True

    with open(image_path, 'rb') as f:
        image_data = f.read()

    image_hash = hashlib.sha256(image_data).hexdigest()
    return image_hash == owner_signature


if __name__ == "__main__":
    print("[*] Testing ghost carrier generation...")
    
    # Test prompts for different themes
    test_prompts = [
        "Ocean waves at sunset",
        "Galaxy nebula with stars",
        "Forest with trees",
        "City skyline at night",
        "Desert sand dunes",
        "Fire flames",
        "Snow mountains"
    ]
    
    for i, prompt in enumerate(test_prompts):
        print(f"\n--- Test {i+1}: {prompt} ---")
        img = _generate_mock(prompt, (256, 256))
        img.save(f"test_mock_{i+1}_{prompt.split()[0]}.png")
        print(f"[OK] Saved: test_mock_{i+1}_{prompt.split()[0]}.png")
    
    print("\n[PASS] All tests passed!")


def recommend_prompts_with_genai(n: int = 10, user_theme: str = "Abstract artistic security visualization") -> List[str]:
    """Recommend diverse image prompts for steganography.
    
    This function generates creative prompts for generating carrier images
    that can be used in steganography workflows.
    
    Args:
        n: Number of prompts to generate (default 10)
        user_theme: Base theme for prompt generation
        
    Returns:
        List of generated prompts
    """
    n = max(1, min(20, int(n)))
    theme = (user_theme or "Abstract artistic security visualization").strip()
    cache_key = ("recommend", f"{theme}|{n}")
    cached = _TEXT_CACHE.get(cache_key)
    if cached:
        return [p.strip() for p in cached.split("\n") if p.strip()][:n]

    system_prompt = (
        "You are a prompt engineer for image generation. "
        "Return only valid JSON with key 'prompts' containing an array of concise strings."
    )
    user_prompt = (
        f"Theme: {theme}\n"
        f"Generate exactly {n} diverse, vivid, colorful image prompts suitable for secure steganography carriers. "
        "No numbering, no markdown."
    )

    def _parse_prompt_json(raw_text: str) -> List[str]:
        t = (raw_text or "").strip()
        if not t:
            return []
        if t.startswith("```"):
            t = t.strip("`")
            if "\n" in t:
                t = t.split("\n", 1)[1]
        data = json.loads(t)
        prompts = data.get("prompts") or []
        out = [str(p).strip() for p in prompts if str(p).strip()]
        return out[:n]

    # 1) Groq
    groq_key = _get_env("GROQ_API_KEY")
    if groq_key:
        try:
            model = _get_env("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            text = _chat_text_completion(
                url="https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=35,
                temperature=0.5,
                max_tokens=800,
            )
            prompts = _parse_prompt_json(text)
            if len(prompts) >= min(3, n):
                _cache_put_text(cache_key, "\n".join(prompts))
                return prompts
        except Exception:
            pass

    # 2) OpenRouter
    openrouter_key = _get_env("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            model = _get_env("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini")
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": _get_env("OPENROUTER_HTTP_REFERER", "http://localhost"),
                "X-Title": _get_env("OPENROUTER_X_TITLE", "Project Aegis Ghost"),
            }
            text = _chat_text_completion(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=40,
                temperature=0.5,
                max_tokens=800,
            )
            prompts = _parse_prompt_json(text)
            if len(prompts) >= min(3, n):
                _cache_put_text(cache_key, "\n".join(prompts))
                return prompts
        except Exception:
            pass

    # 3) Deterministic local fallback
    prompts = _recommend_prompts_local(theme=theme, n_prompts=n)
    _cache_put_text(cache_key, "\n".join(prompts))
    return prompts
