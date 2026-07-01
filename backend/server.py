import os
import io
import time
import zipfile
import base64
import json
import struct
import hashlib
import secrets
import requests
import re
from itertools import combinations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple
from pathlib import Path
import numpy as np
from PIL import Image

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, StreamingResponse
from starlette.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

from core.encryption import (
    encrypt_and_shatter,
    reconstruct_and_decrypt,
    save_metadata,
    load_metadata,
    encrypt_aes_gcm,
    decrypt_aes_gcm,
)
from core.steganography import embed_data_dwt, extract_data_dwt, _decrypt_payload
from core.steganalysis import analyze_image as steganalyze_image, decode_only_image as stego_decode_only_image
from core.ai_engine import generate_ghost_carrier, recommend_prompts_with_genai
from core.biometric_auth import BiometricAuthenticator
from core.digital_watermarking import DigitalWatermarker, analyze_image_forensic
from core.secure_messaging import SecureConversationManager, create_self_destruct_message
from core.security_advisor_llm import analyze_security_vulnerabilities
from run_pipeline import build_prompts, build_prompts_gemini
from core.auth_service import (
    get_all_registered_users,
    register_user,
    authenticate_user,
    generate_otp,
    send_otp_email,
    send_test_email,
    verify_otp_code,
    reset_password,
    get_user,
    is_profile_complete,
    is_registered_user,
    update_user_profile,
    update_user_face_reference,
    update_user_pattern_signature,
    load_users,
    normalize_email,
)

# Load .env keys for provider selection if python-dotenv is installed.
def _load_dotenv_if_present():
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    try:
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".env",
        )
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
    except Exception:
        pass


_load_dotenv_if_present()

# Initialize FastAPI app
app = FastAPI(title="Project Aegis Ghost API", version="0.1.0")

# CORS (safe defaults for localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== HEALTH ENDPOINTS ==============
@app.get("/api/health/live")
async def liveness():
    """Liveness probe - is the app running"""
    from datetime import datetime
    return {"status": "alive", "timestamp": datetime.now().isoformat()}

@app.get("/api/health/ready")
async def readiness():
    """Readiness probe - is the app ready to serve traffic"""
    from datetime import datetime
    checks = {
        "output_dir": os.path.exists(OUTPUT_DIR),
        "assets_dir": os.path.exists(ASSETS_DIR),
        "data_dir": os.path.exists(DATA_DIR),
    }
    ready = all(checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend", "build")
LEGACY_FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
LEGACY_FRONTEND_INDEX = os.path.join(LEGACY_FRONTEND_DIR, "index.html")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output_stego")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DATA_DIR = os.path.join(BASE_DIR, "data")
AUDIT_DIR = os.path.join(DATA_DIR, "audit")
MANIFEST_DIR = os.path.join(DATA_DIR, "manifests")
SECURE_TMP_DIR = os.path.join(DATA_DIR, "secure_tmp")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)


def get_user_output_dir(user_id: str = None) -> str:
    """Get output directory for a specific user, or return shared OUTPUT_DIR if no user_id"""
    if not user_id or user_id == 'anonymous':
        return OUTPUT_DIR
    
    # Create user-specific directory
    safe_user_id = user_id.replace("@", "_at_").replace(".", "_")
    user_dir = os.path.join(BASE_DIR, "data", "user_outputs", safe_user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir
os.makedirs(MANIFEST_DIR, exist_ok=True)
os.makedirs(SECURE_TMP_DIR, exist_ok=True)


def _advanced_crypto_enabled() -> bool:
    return os.getenv("ENABLE_ADVANCED_CRYPTO", "false").strip().lower() in ("1", "true", "yes", "on")


def _require_advanced_crypto_enabled():
    if not _advanced_crypto_enabled():
        raise HTTPException(status_code=404, detail="Advanced crypto feature is disabled")

# Mount static (if present)
if os.path.isdir(FRONTEND_DIR):
    static_dir = os.path.join(FRONTEND_DIR, "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount assets directory for static files like logo
if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

# Mount data/output_stego directory for generated images under /api/data path
if os.path.isdir(OUTPUT_DIR):
    app.mount("/api/data", StaticFiles(directory=DATA_DIR), name="data")

# Mount data directory so generated outputs can be downloaded from frontend
if os.path.isdir(DATA_DIR):
    app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")

# Global authenticator for face verification
_auth = BiometricAuthenticator(owner_image_path=os.path.join(ASSETS_DIR, "owner.jpg"))

# ========= Security/Compliance Utilities =========

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "30"))
_rate_store: dict[tuple[str, str], list[float]] = {}


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
        env_path = os.path.join(BASE_DIR, ".env")
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


def _get_client_ip(req: Request) -> str:
    try:
        forwarded = req.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    except Exception:
        pass
    return req.client.host if req.client else "unknown"


def _derive_key_from_secret(secret_text: str) -> bytes:
    return hashlib.sha256(secret_text.encode("utf-8")).digest()


def _audit_log(action: str, request: Request | None = None, details: dict | None = None):
    entry = {
        "timestamp": time.time(),
        "action": action,
        "ip": _get_client_ip(request) if request else "system",
        "details": details or {},
    }
    path = os.path.join(AUDIT_DIR, "audit.log")
    line = json.dumps(entry, separators=(",", ":"))

    at_rest_key = os.getenv("DATA_AT_REST_KEY")
    if at_rest_key:
        key = _derive_key_from_secret(at_rest_key)
        encrypted = encrypt_aes_gcm(line.encode("utf-8"), key)
        line = base64.b64encode(encrypted).decode("utf-8")

    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _cleanup_old_files():
    now = time.time()
    cutoff = now - (RETENTION_DAYS * 86400)
    cleaned = 0
    for folder in (OUTPUT_DIR, MANIFEST_DIR, SECURE_TMP_DIR):
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            p = os.path.join(folder, name)
            try:
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                    os.remove(p)
                    cleaned += 1
            except Exception:
                continue
    return cleaned


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_signing_key() -> bytes:
    key_file = os.path.join(DATA_DIR, "manifest_signing.key")
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            key = f.read()
            if len(key) >= 32:
                return key[:32]
    key = secrets.token_bytes(32)
    with open(key_file, "wb") as f:
        f.write(key)
    return key


def _sign_manifest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(_manifest_signing_key() + raw).hexdigest()


def _verify_manifest(manifest: dict) -> bool:
    sig = manifest.get("signature")
    payload = dict(manifest)
    payload.pop("signature", None)
    return sig == _sign_manifest(payload)


def _encrypt_path_to_enc(path: str, secret_text: str) -> str:
    key = _derive_key_from_secret(secret_text)
    with open(path, "rb") as f:
        raw = f.read()
    encrypted = encrypt_aes_gcm(raw, key)
    enc_path = path + ".enc"
    with open(enc_path, "wb") as f:
        f.write(encrypted)
    os.remove(path)
    return enc_path


def _decrypt_enc_to_tmp(path: str, secret_text: str) -> str:
    key = _derive_key_from_secret(secret_text)
    with open(path, "rb") as f:
        raw = f.read()
    plain = decrypt_aes_gcm(raw, key)
    tmp_path = os.path.join(SECURE_TMP_DIR, f"dec_{int(time.time()*1000)}_{os.path.basename(path).replace('.enc','')}")
    with open(tmp_path, "wb") as f:
        f.write(plain)
    return tmp_path


async def _save_validated_upload(
    upload: UploadFile,
    dst_path: str,
    allowed_mime_prefixes: tuple[str, ...] = ("image/",),
    max_bytes: int = MAX_UPLOAD_BYTES
):
    ctype = (upload.content_type or "").lower()
    if allowed_mime_prefixes and not any(ctype.startswith(p) for p in allowed_mime_prefixes):
        raise HTTPException(status_code=400, detail=f"Unsupported MIME type: {upload.content_type}")
    data = await upload.read()
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Upload too large (>{max_bytes} bytes)")
    with open(dst_path, "wb") as f:
        f.write(data)
    return len(data)


class _RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Scope to sensitive endpoints
        if path.startswith("/api/auth") or path.startswith("/api/stego") or path.startswith("/api/genai") or path.startswith("/api/ai"):
            ip = _get_client_ip(request)
            key = (ip, path)
            now = time.time()
            window = 60.0
            limit = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))
            hits = _rate_store.get(key, [])
            hits = [t for t in hits if now - t < window]
            if len(hits) >= limit:
                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            hits.append(now)
            _rate_store[key] = hits
        return await call_next(request)


app.add_middleware(_RateLimitMiddleware)


@app.on_event("startup")
def _startup_housekeeping():
    cleaned = _cleanup_old_files()
    _audit_log("startup_cleanup", details={"cleaned_files": cleaned, "retention_days": RETENTION_DAYS})


# ==================== LOCKDOWN & RECOVERY APIs ====================

class LockdownRequest(BaseModel):
    secret: str
    prompt: str = "Abstract colorful"
    n_shares: int = 10
    threshold: int = 6
    use_gemini: bool = True
    provider: str = "auto"  # auto | openai | openrouter | pexels | raphael | leonardo | llm | llm-realistic | mock


def _resolve_image_backend(provider: str = "auto", use_gemini: bool = True):
    """
    Resolve image backend with backward compatibility.
    Returns tuple: (backend_name, use_mock_flag, reason)
    """
    p = (provider or "auto").strip().lower()
    has_leonardo = bool(_get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN") or _get_env("LEONARDO_API_TOKEN"))
    
    if p == "genai":
        if _get_env("GEMINI_API_KEY"):
            return ("genai", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("auto", False, "GEMINI_API_KEY missing; using auto provider chain")
    if p == "openai":
        if _get_env("OPENAI_API_KEY"):
            return ("openai", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "OPENAI_API_KEY missing")
    if p == "openrouter":
        if _get_env("OPENROUTER_API_KEY"):
            return ("openrouter", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "OPENROUTER_API_KEY missing")
    if p == "puter":
        if _get_env("PUTER_API_KEY"):
            return ("puter", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "PUTER_API_KEY missing")
    if p == "gemini":
        if _get_env("GEMINI_API_KEY"):
            return ("genai", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("auto", False, "GEMINI_API_KEY missing; using auto provider chain")
    if p == "groq":
        # Groq is text-only for image workflows; use LLM-guided local renderer.
        if _get_env("GROQ_API_KEY"):
            return ("llm", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "GROQ_API_KEY missing")
    if p == "llm":
        return ("llm", False, None)
    if p in ("llm-realistic", "llm_realistic", "realistic"):
        return ("llm-realistic", False, None)
    if p == "mock":
        return ("mock", True, None)
    if p == "pollinations":
        # Pollinations is a free AI image generator - no API key needed
        return ("pollinations", False, None)
    if p in ("pollinations-schnell", "pollinations-turbo", "pollinations-realism"):
        # Fast/free Pollinations model variants.
        return (p, False, None)
    if p == "pexels":
        if _get_env("PEXELS_API_KEY"):
            return ("pexels", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "PEXELS_API_KEY missing")
    if p == "deepai":
        # DeepAI is a powerful image generation API
        if _get_env("DEEPAI_API_KEY"):
            return ("deepai", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "DEEPAI_API_KEY missing")
    if p == "raphael":
        if _get_env("RAPHAEL_API_KEY"):
            return ("raphael", False, None)
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "RAPHAEL_API_KEY missing")
    if p == "leonardo":
        return ("leonardo", False, None) if has_leonardo else ("mock", True, "LEONARDO_API_KEY missing")
    if p == "hf":
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "HF provider not implemented in this build")
    if p == "replicate":
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, "Replicate provider not implemented in this build")
    if p != "auto":
        # Unknown provider -> safe fallback
        if has_leonardo:
            return ("leonardo", False, None)
        return ("mock", True, f"Unknown provider: {provider}")

    # auto resolution: use ai_engine provider chain.
    return ("auto", False, "Using provider auto-chain")


@app.post("/api/lockdown")
def run_lockdown(req: LockdownRequest):
    """Full lockdown: encrypt secret, generate ghost images, embed shares."""
    try:
        if req.n_shares < 2:
            raise HTTPException(status_code=400, detail="n_shares must be at least 2")
        if req.threshold < 2 or req.threshold > req.n_shares:
            raise HTTPException(status_code=400, detail="threshold must be between 2 and n_shares")

        # 1. Encrypt the secret
        ciphertext, shares, nonce, tag = encrypt_and_shatter(
            req.secret, n_shares=req.n_shares, threshold=req.threshold
        )
        
        # 2. Save metadata
        save_metadata(ciphertext, nonce, tag)
        
        # 3. Build varied prompts and generate ghost images
        backend_name, use_mock_flag, backend_reason = _resolve_image_backend(req.provider, req.use_gemini)
        if req.provider in ("openai", "openrouter", "puter", "groq", "gemini", "genai", "pexels", "raphael", "leonardo") and backend_name == "mock":
            raise HTTPException(status_code=400, detail=f"Requested provider '{req.provider}' unavailable: {backend_reason}")
        if backend_name == "gemini":
            prompts = build_prompts_gemini(req.n_shares, user_theme=req.prompt)
        else:
            prompts = build_prompts(req.n_shares, base_prompt=req.prompt)

        # Ensure one prompt per share
        if len(prompts) < len(shares):
            prompts += build_prompts(len(shares) - len(prompts), base_prompt=req.prompt)
        prompts = prompts[:len(shares)]

        generated_files = []
        for i, (idx, share_bytes) in enumerate(shares):
            path = os.path.join(OUTPUT_DIR, f"ghost_{idx}.png")
            # Generate unique image for each share using prompt list
            generate_ghost_carrier(
                prompts[i],
                path,
                use_mock=use_mock_flag,
                backend=backend_name,
            )
            # Embed share data
            embed_data_dwt(path, bytes(share_bytes), path)
            rel_path = os.path.relpath(path, BASE_DIR).replace("\\", "/")
            generated_files.append(rel_path)
        
        return {
            "status": "success",
            "message": "LOCKDOWN COMPLETE",
            "ciphertext": ciphertext.hex(),
            "nonce": nonce.hex(),
            "tag": tag.hex(),
            "shares": len(shares),
            "threshold": req.threshold,
            "backend_used": backend_name,
            "prompts_used": prompts,
            "generated_files": generated_files
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lockdown failed: {e}")


class RecoveryRequest(BaseModel):
    biometric_enabled: bool = False


@app.post("/api/recovery")
def run_recovery(req: RecoveryRequest):
    """Full recovery: authenticate, extract shares, decrypt secret."""
    try:
        # 1. Biometric authentication (optional)
        if req.biometric_enabled:
            # For now, return a message that biometric recovery requires setup
            return {
                "status": "auth_required",
                "message": "Biometric authentication enabled. Face verification would occur here.",
                "note": "Set biometric_enabled=false for testing without biometrics"
            }
        
        # 2. Load metadata
        ciphertext, nonce, tag = load_metadata()
        
        # 3. Extract shares from ghost images
        captured_shares = []
        files = sorted([
            f for f in os.listdir(OUTPUT_DIR)
            if f.endswith('.png') and f.startswith('ghost_')
        ])
        
        for filename in files[:6]:  # Need at least threshold shares
            path = os.path.join(OUTPUT_DIR, filename)
            share_data = extract_data_dwt(path, num_bytes=16)
            idx = int(filename.split('_')[1].split('.')[0])
            captured_shares.append((idx, share_data))
        
        # 4. Reconstruct and decrypt
        plaintext = reconstruct_and_decrypt(
            captured_shares,
            ciphertext,
            bytes.fromhex(nonce) if isinstance(nonce, str) else nonce,
            bytes.fromhex(tag) if isinstance(tag, str) else tag
        )
        
        return {
            "status": "success",
            "message": "RECOVERY COMPLETE",
            "secret": plaintext,
            "shares_used": len(captured_shares)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Recovery failed: {e}")


# ==================== EXISTING APIs ====================


class EncryptRequest(BaseModel):
    text: str
    n_shares: int = 10
    threshold: int = 6


class ShareModel(BaseModel):
    index: int
    share: str  # hex string


class DecryptRequest(BaseModel):
    shares: List[ShareModel]
    ciphertext: str  # hex
    nonce: str       # hex
    tag: str         # hex


class AuthRegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthProfileRequest(BaseModel):
    email: str


class AuthProfileUpdateRequest(BaseModel):
    email: str
    name: str
    id_no: str = ""


class PatternRegisterRequest(BaseModel):
    email: str
    pattern: str


class PatternVerifyRequest(BaseModel):
    email: str
    pattern: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


class SmtpTestRequest(BaseModel):
    email: str = ""


@app.get("/api/status")
def status():
    return {
        "status": "ok",
        "message": "API running",
        "outputs_dir": OUTPUT_DIR,
        "frontend": os.path.isdir(FRONTEND_DIR) or os.path.exists(LEGACY_FRONTEND_INDEX),
    }


@app.get("/api/ai/providers")
def ai_providers():
    """Expose provider availability for quick troubleshooting."""
    # Debug: Print what env vars are available
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DEBUG] GEMINI_API_KEY: {'SET' if _get_env('GEMINI_API_KEY') else 'NOT SET'}")
    logger.info(f"[DEBUG] OPENAI_API_KEY: {'SET' if _get_env('OPENAI_API_KEY') else 'NOT SET'}")
    logger.info(f"[DEBUG] OPENROUTER_API_KEY: {'SET' if _get_env('OPENROUTER_API_KEY') else 'NOT SET'}")
    logger.info(f"[DEBUG] PUTER_API_KEY: {'SET' if _get_env('PUTER_API_KEY') else 'NOT SET'}")
    logger.info(f"[DEBUG] GROQ_API_KEY: {'SET' if _get_env('GROQ_API_KEY') else 'NOT SET'}")
    logger.info(f"[DEBUG] DEEPAI_API_KEY: {'SET' if _get_env('DEEPAI_API_KEY') else 'NOT SET'}")
    logger.info(f"[DEBUG] LEONARDO_API_KEY: {'SET' if _get_env('LEONARDO_API_KEY') else 'NOT SET'}")
    logger.info(f"[DEBUG] RAPHAEL_API_KEY: {'SET' if _get_env('RAPHAEL_API_KEY') else 'NOT SET'}")
    logger.info(f"[DEBUG] PEXELS_API_KEY: {'SET' if _get_env('PEXELS_API_KEY') else 'NOT SET'}")
    
    return {
        "providers": {
            "genai": bool(_get_env("GEMINI_API_KEY")),
            "openrouter": bool(_get_env("OPENROUTER_API_KEY")),
            "puter": bool(_get_env("PUTER_API_KEY")),
            "groq": bool(_get_env("GROQ_API_KEY")),
            "openai": bool(_get_env("OPENAI_API_KEY")),
            "gemini": bool(_get_env("GEMINI_API_KEY")),
            "leonardo": bool(_get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN")),
            "raphael": bool(_get_env("RAPHAEL_API_KEY")),
            "pexels": bool(_get_env("PEXELS_API_KEY")),
            "llm": True,  # local renderer always available
            "mock": True,
        },
        "defaults": {
            "groq_text_model": _get_env("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile"),
            "openrouter_image_model": _get_env("OPENROUTER_IMAGE_MODEL", "google/gemini-3.1-flash-image-preview"),
            "puter_image_model": _get_env("PUTER_IMAGE_MODEL", "sdxl"),
            "openrouter_text_model": _get_env("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini"),
            "openai_image_model": _get_env("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            "openai_text_model": _get_env("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
            "gemini_image_model": _get_env("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp-image-generation"),
            "gemini_text_model": _get_env("GEMINI_TEXT_MODEL", "models/gemini-1.5-flash"),
            "raphael_api_url": _get_env("RAPHAEL_API_URL", "https://evolink.ai/z-image-turbo"),
        }
    }


@app.get("/api/ai/capabilities")
def ai_capabilities():
    """Unified provider capability discovery."""
    return {
        "status": "success",
        "priority_chain": ["openrouter", "puter", "openai", "raphael", "leonardo", "pexels", "pollinations", "deepai", "llm", "mock"],
        "providers": {
            "pollinations": {
                "available": True,
                "supports": ["image"],
                "model": os.getenv("POLLINATIONS_MODEL", "flux"),
                "note": "Free AI image generation, no API key required"
            },
            "genai": {
                "available": bool(_get_env("GEMINI_API_KEY")),
                "supports": ["image", "prompt_recommendation"],
                "model": _get_env("GENAI_IMAGE_MODEL", "gemini-2.0-flash-exp-image-generation"),
            },
            "openai": {
                "available": bool(_get_env("OPENAI_API_KEY")),
                "supports": ["image", "text"],
                "model": _get_env("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            },
            "leonardo": {
                "available": bool(_get_env("LEONARDO_API_KEY") or _get_env("LEONARDO_KEY") or _get_env("LEONARDO_TOKEN")),
                "supports": ["image"],
                "model": _get_env("LEONARDO_MODEL_ID", "aa77f04e-3eec-4034-9c07-d0f619684628"),
            },
            "raphael": {
                "available": bool(_get_env("RAPHAEL_API_KEY")),
                "supports": ["image"],
                "endpoint": _get_env("RAPHAEL_API_URL", "https://evolink.ai/z-image-turbo"),
            },
            "pexels": {
                "available": bool(_get_env("PEXELS_API_KEY")),
                "supports": ["image_retrieval"],
                "endpoint": "https://api.pexels.com/v1/search",
            },
            "openrouter": {
                "available": bool(_get_env("OPENROUTER_API_KEY")),
                "supports": ["image", "text"],
                "model": _get_env("OPENROUTER_IMAGE_MODEL", "google/gemini-3.1-flash-image-preview"),
            },
            "puter": {
                "available": bool(_get_env("PUTER_API_KEY")),
                "supports": ["image"],
                "model": _get_env("PUTER_IMAGE_MODEL", "sdxl"),
                "endpoint": _get_env("PUTER_IMAGE_ENDPOINT", "https://api.puter.com/v1/images/generations"),
            },
            "groq": {
                "available": bool(_get_env("GROQ_API_KEY")),
                "supports": ["text", "security_advisory"],
                "model": _get_env("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile"),
            },
            "llm": {"available": True, "supports": ["prompt_rewrite", "local_render"]},
            "mock": {"available": True, "supports": ["deterministic_render"]},
        },
    }


@app.post("/api/auth/register")
def auth_register(req: AuthRegisterRequest):
    if len(req.password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    success, msg = register_user(req.email, req.password, req.name)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/auth/login")
def auth_login(req: AuthLoginRequest):
    if not authenticate_user(req.email, req.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user = get_user(req.email) or {}
    profile_ok = is_profile_complete(user)
    name = user.get("name") or req.email.split("@")[0]
    return {
        "success": True,
        "email": req.email.strip().lower(),
        "name": name,
        "id_no": user.get("id_no", ""),
        "profile_picture": user.get("profile_picture", ""),
        "profile_completed": bool(profile_ok),
        "profile_required": not bool(profile_ok),
    }


@app.post("/api/auth/profile/complete")
async def auth_complete_profile(
    email: str = Form(...),
    name: str = Form(...),
    id_no: str = Form(""),
    profile_picture: UploadFile = File(...),
):
    email_norm = (email or "").strip().lower()
    if not email_norm:
        raise HTTPException(status_code=400, detail="Email is required.")
    if not (name or "").strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    if profile_picture is None:
        raise HTTPException(status_code=400, detail="Profile picture is required.")

    pic_dir = os.path.join(DATA_DIR, "profile_pictures")
    os.makedirs(pic_dir, exist_ok=True)
    ext = os.path.splitext(profile_picture.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".png"
    safe_email = hashlib.sha256(email_norm.encode("utf-8")).hexdigest()[:16]
    file_name = f"profile_{safe_email}_{int(time.time())}{ext}"
    abs_path = os.path.join(pic_dir, file_name)
    await _save_validated_upload(profile_picture, abs_path, ("image/",))

    rel_path = os.path.relpath(abs_path, BASE_DIR).replace("\\", "/")
    ok, msg = update_user_profile(email_norm, name, id_no, rel_path)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {
        "success": True,
        "message": msg,
        "email": email_norm,
        "name": (name or "").strip(),
        "id_no": (id_no or "").strip(),
        "profile_picture": rel_path,
        "profile_completed": True,
    }


@app.post("/api/auth/profile")
def auth_get_profile(req: AuthProfileRequest):
    email_norm = (req.email or "").strip().lower()
    if not email_norm:
        raise HTTPException(status_code=400, detail="Email is required.")
    user = get_user(email_norm)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {
        "success": True,
        "email": email_norm,
        "name": user.get("name", ""),
        "id_no": user.get("id_no", ""),
        "profile_picture": user.get("profile_picture", ""),
        "face_reference_picture": user.get("face_reference_picture", ""),
        "pattern_signature": user.get("pattern_signature", ""),
        "pattern_registered": bool((user.get("pattern_signature") or "").strip()),
        "biometric_updated_at": user.get("biometric_updated_at", 0),
        "profile_completed": bool(is_profile_complete(user)),
        "created_at": user.get("created_at"),
        "profile_updated_at": user.get("profile_updated_at"),
    }


@app.post("/api/auth/profile/update")
def auth_update_profile(req: AuthProfileUpdateRequest):
    email_norm = (req.email or "").strip().lower()
    if not email_norm:
        raise HTTPException(status_code=400, detail="Email is required.")
    user = get_user(email_norm)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")

    existing_picture = (user.get("profile_picture") or "").strip()
    ok, msg = update_user_profile(email_norm, name, req.id_no or "", existing_picture)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    updated = get_user(email_norm) or {}
    return {
        "success": True,
        "message": msg,
        "email": email_norm,
        "name": updated.get("name", ""),
        "id_no": updated.get("id_no", ""),
        "profile_picture": updated.get("profile_picture", ""),
        "profile_completed": bool(is_profile_complete(updated)),
    }


def _normalize_pattern_signature(pattern_text: str) -> str:
    """Normalize pattern to grid positions (0-8 for 3x3 grid).
    
    Handles both pixel coordinates (60,180,300) and already normalized grid indices (0-8).
    """
    raw = (pattern_text or "").strip()
    if not raw:
        return ""
    
    # Check if already normalized (single digits 0-8 separated by dashes)
    # e.g., "0-3-6-7-8" is already normalized
    parts = raw.split("-")
    if all(p in '012345678' for p in parts) and len(parts) > 1:
        # Already normalized
        return raw
    
    # Otherwise, extract numbers and convert pixel coords to grid positions
    nums = re.findall(r"\d+", raw)
    if not nums or len(nums) < 2:
        return ""
    
    # Convert pixel coordinates to grid positions (0-8 for 3x3 grid)
    # Grid points are at: 60,180,300 (for 360px canvas with 3x3 grid)
    grid_positions = []
    for i in range(0, len(nums), 2):
        if i+1 < len(nums):
            try:
                x, y = int(nums[i]), int(nums[i+1])
            except (ValueError, TypeError):
                continue
            # Map pixel coordinates to grid index (0-8)
            # Cell size is 120px, grid points at 60, 180, 300
            grid_x = min(2, max(0, round((x - 60) / 120)))
            grid_y = min(2, max(0, round((y - 60) / 120)))
            grid_positions.append(grid_y * 3 + grid_x)
    
    if not grid_positions:
        return ""
    return "-".join(str(p) for p in grid_positions)


def _compare_patterns(expected: str, provided: str) -> bool:
    """Compare two patterns - both should be normalized to grid positions."""
    if not expected or not provided:
        return False
    
    # Exact match
    if expected == provided:
        return True
    
    # Use constant-time comparison
    return secrets.compare_digest(expected, provided)


def _resolve_user_reference_face_path(email_norm: str) -> str:
    user = get_user(email_norm)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    rel_path = (user.get("face_reference_picture") or user.get("profile_picture") or "").strip()
    if not rel_path:
        raise HTTPException(status_code=400, detail="Face reference is not registered for this user.")
    abs_path = os.path.abspath(os.path.join(BASE_DIR, rel_path))
    if not abs_path.startswith(BASE_DIR):
        raise HTTPException(status_code=403, detail="Invalid reference image path.")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=400, detail="Reference face image not found. Re-register face in Profile.")
    return abs_path


@app.post("/api/auth/profile/face/register")
async def auth_register_face(
    email: str = Form(...),
    face_image: UploadFile = File(...),
):
    email_norm = (email or "").strip().lower()
    if not email_norm:
        raise HTTPException(status_code=400, detail="Email is required.")
    user = get_user(email_norm)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    pic_dir = os.path.join(DATA_DIR, "profile_faces")
    os.makedirs(pic_dir, exist_ok=True)
    ext = os.path.splitext(face_image.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"

    safe_email = hashlib.sha256(email_norm.encode("utf-8")).hexdigest()[:16]
    file_name = f"face_ref_{safe_email}_{int(time.time())}{ext}"
    abs_path = os.path.join(pic_dir, file_name)
    print(f"[DEBUG] Saving face image to: {abs_path}")
    await _save_validated_upload(face_image, abs_path, ("image/",))

    rel_path = os.path.relpath(abs_path, BASE_DIR).replace("\\", "/")
    print(f"[DEBUG] Calling update_user_face_reference with: {rel_path}")
    ok, msg = update_user_face_reference(email_norm, rel_path)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg,
        "email": email_norm,
        "face_reference_picture": rel_path,
    }


@app.post("/api/auth/profile/pattern/register")
def auth_register_pattern(req: PatternRegisterRequest):
    email_norm = (req.email or "").strip().lower()
    if not email_norm:
        raise HTTPException(status_code=400, detail="Email is required.")
    signature = _normalize_pattern_signature(req.pattern)
    if len(signature.split("-")) < 3:
        raise HTTPException(status_code=400, detail="Pattern must contain at least 3 points.")
    ok, msg = update_user_pattern_signature(email_norm, signature)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {
        "success": True,
        "message": msg,
        "email": email_norm,
        "pattern_registered": True,
    }


@app.post("/api/auth/pattern/verify")
def auth_verify_pattern(req: PatternVerifyRequest):
    email_norm = (req.email or "").strip().lower()
    if not email_norm:
        raise HTTPException(status_code=400, detail="Email is required.")
    user = get_user(email_norm)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    expected = _normalize_pattern_signature(user.get("pattern_signature", ""))
    if not expected:
        raise HTTPException(status_code=400, detail="No pattern registered. Register pattern in Profile first.")
    provided = _normalize_pattern_signature(req.pattern)
    if not provided:
        raise HTTPException(status_code=400, detail="Pattern input is empty or invalid.")

    matched = secrets.compare_digest(expected, provided)
    return {
        "success": True,
        "matched": matched,
        "access_granted": matched,
        "message": "Pattern verified. Access granted." if matched else "Pattern mismatch. Access denied.",
    }


@app.post("/api/auth/forgot-password")
def auth_forgot_password(req: ForgotPasswordRequest):
    user = get_user(req.email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email.")
    otp = generate_otp(req.email)
    sent, msg = send_otp_email(req.email, otp)

    if not sent:
        raise HTTPException(status_code=500, detail=msg)

    # OTP is intentionally NOT included in the response — check the server terminal for mock email output
    return {"success": True, "message": "OTP sent to your email. Check your inbox."}


@app.post("/api/auth/reset-password")
def auth_reset_password(req: ResetPasswordRequest):
    if len(req.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if not verify_otp_code(req.email, req.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")
    success, msg = reset_password(req.email, req.new_password)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/auth/logout")
def auth_logout():
    return {"success": True}


@app.post("/api/auth/smtp-test")
def auth_smtp_test(req: SmtpTestRequest):
    sent, msg = send_test_email(req.email or None)
    if not sent:
        raise HTTPException(status_code=500, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/crypto/encrypt")
def crypto_encrypt(req: EncryptRequest):
    try:
        ct, shares, nonce, tag = encrypt_and_shatter(req.text, n_shares=req.n_shares, threshold=req.threshold)
        shares_out = []
        for idx, share_bytes in shares:
            shares_out.append({"index": int(idx), "share": share_bytes.hex()})
        return {
            "ciphertext": ct.hex(),
            "shares": shares_out,
            "nonce": nonce.hex(),
            "tag": tag.hex(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Encryption failed: {e}")


@app.post("/api/crypto/decrypt")
def crypto_decrypt(req: DecryptRequest):
    try:
        shares_in = []
        for s in req.shares:
            shares_in.append((int(s.index), bytes.fromhex(s.share)))
        pt = reconstruct_and_decrypt(
            shares_in,
            bytes.fromhex(req.ciphertext),
            bytes.fromhex(req.nonce),
            bytes.fromhex(req.tag),
        )
        return {"plaintext": pt}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {e}")


@app.post("/api/stego/hide")
async def stego_hide(request: Request, image: UploadFile = File(...), secret_text: str = Form(...)):
    try:
        # Save uploaded image to a temp path
        fname = f"stego_src_{int(time.time())}_{image.filename}"
        src_path = os.path.join(OUTPUT_DIR, fname)
        size_bytes = await _save_validated_upload(image, src_path, ("image/",))

        # Prepare output filenames
        out_name = f"ghost_{int(time.time())}.png"
        out_path = os.path.join(OUTPUT_DIR, out_name)

        # Embed
        embed_data_dwt(src_path, secret_text.encode("utf-8"), out_path)

        coeff_path = out_path.replace(".png", "_coeff.npy")
        rel_out = os.path.relpath(out_path, BASE_DIR).replace("\\", "/")
        rel_coeff = os.path.relpath(coeff_path, BASE_DIR).replace("\\", "/")
        _audit_log("stego_hide", request, {"bytes_in": size_bytes, "bytes_hidden": len(secret_text.encode("utf-8"))})
        return {"output_image": rel_out, "coeff": rel_coeff}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stego hide failed: {e}")


@app.post("/api/stego/reveal")
async def stego_reveal(request: Request, stego_image: UploadFile = File(...), num_bytes: int = Form(...)):
    try:
        # Save stego image
        fname = f"stego_in_{int(time.time())}_{stego_image.filename}"
        in_path = os.path.join(OUTPUT_DIR, fname)
        await _save_validated_upload(stego_image, in_path, ("image/",))

        data = extract_data_dwt(in_path, num_bytes)
        # Try to decode as utf-8; otherwise return base64/hex
        try:
            text = data.decode("utf-8")
            _audit_log("stego_reveal", request, {"num_bytes": num_bytes, "encoding": "utf-8"})
            return {"text": text, "encoding": "utf-8"}
        except Exception:
            _audit_log("stego_reveal", request, {"num_bytes": num_bytes, "encoding": "binary"})
            return {"raw_hex": data.hex(), "encoding": "binary"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stego reveal failed: {e}")


@app.post("/api/stego/analyze")
async def stego_analyze(request: Request, image: UploadFile = File(...)):
    """
    Steganalysis: detect hidden data in an image using multiple statistical methods.
    Runs Chi-Square, RS Analysis, Histogram, Noise, Sample Pair, and Bit-Plane analyses.
    """
    try:
        fname = f"stego_analyze_{int(time.time())}_{image.filename}"
        in_path = os.path.join(SECURE_TMP_DIR, fname)
        await _save_validated_upload(image, in_path, ("image/",))
        with open(in_path, "rb") as f:
            image_bytes = f.read()
        result = steganalyze_image(image_bytes, image_path=in_path)
        _audit_log("stego_analyze", request, {"bytes": len(image_bytes)})
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Steganalysis failed: {e}")


@app.post("/api/stego/decode")
async def stego_decode(
    request: Request,
    image: UploadFile = File(...),
    passwords: str = Form(""),
):
    """
    Decode-only endpoint: attempts hidden payload extraction without running
    statistical steganalysis methods.
    """
    try:
        fname = f"stego_decode_{int(time.time())}_{image.filename}"
        in_path = os.path.join(SECURE_TMP_DIR, fname)
        await _save_validated_upload(image, in_path, ("image/",))
        with open(in_path, "rb") as f:
            image_bytes = f.read()
        pw_list = [p.strip() for p in (passwords or "").split(",") if p.strip()]
        result = stego_decode_only_image(image_bytes, image_path=in_path, passwords=pw_list or None)

        # Stronger direct extraction + optional password decrypt fallback.
        if pw_list and not result.get("decrypted_text"):
            try:
                raw_payload = extract_data_dwt(in_path, num_bytes=65536)
                # Plain-text payload path
                try:
                    plain_text = raw_payload.decode("utf-8").strip("\x00")
                    if plain_text and sum(ch.isprintable() for ch in plain_text) / max(len(plain_text), 1) > 0.85:
                        result["decrypted_text"] = plain_text
                        result["decryption_status"] = "success"
                except Exception:
                    pass

                # Encrypted payload path
                if not result.get("decrypted_text"):
                    for pw in pw_list:
                        try:
                            key = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), b"aegis_ghost_salt", 100000, dklen=16)
                            dec = decrypt_aes_gcm(raw_payload, key).decode("utf-8")
                            result["decrypted_text"] = dec
                            result["decryption_status"] = "success"
                            break
                        except Exception:
                            continue
            except Exception:
                pass

        _audit_log(
            "stego_decode",
            request,
            {
                "bytes": len(image_bytes),
                "found": bool(result.get("decoded_payload", {}).get("found")),
                "method": result.get("decoded_payload", {}).get("method"),
                "passwords_supplied": bool(pw_list),
            },
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stego decode failed: {e}")


@app.post("/api/stego/analyze-batch")
async def stego_analyze_batch(
    request: Request,
    images: List[UploadFile] = File(default=[]),
    archive: UploadFile | None = File(default=None),
    passwords: str = Form(""),
):
    """
    Batch steganalysis for multiple images.
    Accepts either:
    - `images`: multiple image files
    - `archive`: a .zip containing image files
    """
    try:
        accepted_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
        max_bytes = MAX_UPLOAD_BYTES
        items: list[tuple[str, bytes]] = []
        sidecars_by_image: dict[str, bytes] = {}

        for f in images or []:
            filename = os.path.basename(f.filename or "image")
            ext = os.path.splitext(filename)[1].lower()
            ctype = (f.content_type or "").lower()
            if ext not in accepted_exts and not ctype.startswith("image/"):
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {filename}")
            raw = await f.read()
            if len(raw) > max_bytes:
                raise HTTPException(status_code=413, detail=f"File too large: {filename}")
            items.append((filename, raw))

        if archive is not None:
            archive_name = (archive.filename or "").lower()
            archive_type = (archive.content_type or "").lower()
            if not archive_name.endswith(".zip") and "zip" not in archive_type:
                raise HTTPException(status_code=400, detail="Archive must be a .zip file.")
            raw_zip = await archive.read()
            if len(raw_zip) > (max_bytes * 20):
                raise HTTPException(status_code=413, detail="ZIP archive too large.")
            try:
                with zipfile.ZipFile(io.BytesIO(raw_zip), "r") as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        name = os.path.basename(info.filename)
                        if not name:
                            continue
                        # Optional exact payload sidecar support:
                        # <image>.png.steg.bin
                        if name.lower().endswith(".steg.bin"):
                            data = zf.read(info)
                            if len(data) <= max_bytes:
                                image_name = name[:-9]  # strip ".steg.bin"
                                sidecars_by_image[image_name] = data
                            continue
                        ext = os.path.splitext(name)[1].lower()
                        if ext not in accepted_exts:
                            continue
                        data = zf.read(info)
                        if len(data) > max_bytes:
                            continue
                        items.append((name, data))
            except zipfile.BadZipFile:
                head = raw_zip[:200].lstrip().lower()
                if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Invalid ZIP archive. Received HTML instead of a ZIP file. "
                            "Re-download the attachment and ensure /api/chat/files/{file_id} "
                            "is served by the backend (not the frontend catch-all route)."
                        ),
                    )
                raise HTTPException(status_code=400, detail="Invalid ZIP archive.")

        if not items:
            raise HTTPException(status_code=400, detail="No valid images provided.")

        pw_list = [p.strip() for p in (passwords or "").split(",") if p.strip()]
        results = []
        suspicious = 0
        # Advanced share payload groups (carry ciphertext/nonce/tag in each image).
        share_groups: dict[tuple[str, str, str, int], dict] = {}
        # Shamir-stego payload groups (carry only share string + index).
        shamir_stego_groups: dict[str, dict] = {}
        for filename, data in items:
            analysis = steganalyze_image(data)
            # Check for hidden data using risk_level or verdict containing 'Hidden Data'
            risk_level = analysis.get("overall", {}).get("risk_level", "CLEAN")
            verdict = analysis.get("overall", {}).get("verdict", "")
            is_suspicious = risk_level in ("HIGH", "MEDIUM", "LOW") or "Hidden Data" in verdict
            if is_suspicious:
                suspicious += 1

            row = {
                "filename": filename,
                "overall": analysis.get("overall", {}),
                "image_info": analysis.get("image_info", {}),
                "analyses": analysis.get("analyses", {}),
                "decoded_payload": analysis.get("decoded_payload", {}),
            }

            # Extract share payload directly for threshold reconstruction.
            try:
                # Prefer sidecar payload (exact bytes, least corruption risk) when available.
                raw_payload = sidecars_by_image.get(filename)
                decoder_report = {"strategy": "sidecar_raw", "attempts": []} if raw_payload else {"strategy": None, "attempts": []}

                if raw_payload is None:
                    raw_payload = _extract_payload_lsb_bytes(data)
                    share_payload, decoder_report = _decode_payload_multiformat(raw_payload)
                else:
                    share_payload = None
                    # For sidecar, payload is typically raw JSON.
                    try:
                        share_payload = json.loads(raw_payload.decode("utf-8", errors="strict").strip("\x00").strip())
                    except Exception:
                        share_payload, decoder_report = _decode_payload_multiformat(raw_payload)

                if share_payload is None and raw_payload:
                    # Final fallback: relaxed plain JSON text parse.
                    try:
                        share_payload = json.loads(raw_payload.decode("utf-8", errors="ignore").strip("\x00").strip())
                    except Exception:
                        share_payload = None
                if share_payload is None:
                    raise ValueError("Could not decode payload from extracted bytes")
                row["decoder_report"] = decoder_report
                share_idx = int(share_payload["share_index"])

                # Format A: advanced stego payload (share_hex + ciphertext metadata).
                if all(k in share_payload for k in ("share_hex", "ciphertext_hex", "nonce_hex", "tag_hex")):
                    share_hex = str(share_payload["share_hex"])
                    threshold = int(share_payload.get("threshold", 6))
                    ct_hex = str(share_payload["ciphertext_hex"])
                    nonce_hex = str(share_payload["nonce_hex"])
                    tag_hex = str(share_payload["tag_hex"])
                    if threshold < 2:
                        threshold = 2

                    group_key = (ct_hex, nonce_hex, tag_hex, threshold)
                    group = share_groups.setdefault(
                        group_key,
                        {
                            "threshold": threshold,
                            "shares": {},
                            "source_files": {},
                        },
                    )
                    group["shares"][share_idx] = bytes.fromhex(share_hex)
                    group["source_files"][share_idx] = filename
                    row["share_info"] = {
                        "type": "advanced",
                        "share_index": share_idx,
                        "threshold": threshold,
                    }
                # Format B: shamir-stego payload (share string, total_shares).
                elif "share" in share_payload:
                    share_obj = share_payload["share"]
                    total_shares = int(share_payload.get("total_shares", 0)) or 0
                    payload_threshold = int(share_payload.get("threshold", 0) or 0)
                    share_threshold = 0
                    if isinstance(share_obj, dict):
                        try:
                            share_threshold = int(share_obj.get("threshold", 0)) or 0
                        except Exception:
                            share_threshold = 0
                    effective_threshold = payload_threshold or share_threshold or total_shares
                    # Group by batch hint from filename when available.
                    batch_key = str(share_payload.get("batch_id", "")).strip() or "unknown"
                    parts = filename.split("_")
                    # expected: shamir_stego_<batchid>_<idx>.png
                    if batch_key == "unknown" and len(parts) >= 4 and parts[0] == "shamir" and parts[1] == "stego":
                        batch_key = parts[2]
                    group_key = f"{batch_key}:{effective_threshold}:{total_shares}"
                    group = shamir_stego_groups.setdefault(
                        group_key,
                        {
                            "threshold": effective_threshold,
                            "total_shares": total_shares,
                            "shares": {},
                            "source_files": {},
                            "decrypt_key_hex": None,
                        },
                    )
                    is_valid_share = _is_valid_shamir_share_obj(share_obj) if isinstance(share_obj, dict) else False
                    if is_valid_share:
                        group["shares"][share_idx] = share_obj
                    group["source_files"][share_idx] = filename
                    if not group.get("decrypt_key_hex") and share_payload.get("decrypt_key_hex"):
                        group["decrypt_key_hex"] = str(share_payload.get("decrypt_key_hex"))
                    row["share_info"] = {
                        "type": "shamir_stego",
                        "share_index": share_idx,
                        "threshold": effective_threshold if effective_threshold > 0 else None,
                        "valid": bool(is_valid_share),
                    }
            except Exception:
                pass

            results.append(row)

        batch_decrypted_text = None
        batch_decryption_status = "not_attempted"
        batch_decryption_error = None
        contributing_files = set()

        if share_groups:
            candidate_groups = sorted(share_groups.items(), key=lambda x: len(x[1]["shares"]), reverse=True)
            for (ct_hex, nonce_hex, tag_hex, threshold), group in candidate_groups:
                shares = group["shares"]
                if len(shares) < threshold:
                    continue
                try:
                    selected_shares = sorted(shares.items(), key=lambda x: x[0])[:threshold]
                    plaintext = reconstruct_and_decrypt(
                        selected_shares,
                        bytes.fromhex(ct_hex),
                        bytes.fromhex(nonce_hex),
                        bytes.fromhex(tag_hex),
                    )
                    batch_decrypted_text = plaintext
                    batch_decryption_status = "success"
                    contributing_files = {
                        group["source_files"].get(idx)
                        for idx, _ in selected_shares
                        if group["source_files"].get(idx)
                    }
                    break
                except Exception as e:
                    batch_decryption_status = "failed"
                    batch_decryption_error = str(e)

            if batch_decryption_status == "not_attempted":
                largest_group = candidate_groups[0][1]
                batch_decryption_status = "failed"
                batch_decryption_error = (
                    f"Insufficient shares for reconstruction: found {len(largest_group['shares'])}, "
                    f"need {largest_group['threshold']}."
                )

        # Fallback: try classic shamir-stego reconstruction for payloads with "share" strings.
        if batch_decryption_status != "success" and shamir_stego_groups:
            candidate_shamir = sorted(shamir_stego_groups.items(), key=lambda x: len(x[1]["shares"]), reverse=True)
            for _group_key, group in candidate_shamir:
                required = int(group.get("threshold", 0)) or int(group.get("total_shares", 0)) or len(group["shares"])
                if len(group["shares"]) < required:
                    batch_decryption_status = "failed"
                    batch_decryption_error = (
                        f"Insufficient shamir-stego shares: found {len(group['shares'])}, need {required}."
                    )
                    continue
                try:
                    sorted_items = sorted(group["shares"].items(), key=lambda x: x[0])
                    candidate_sets = [tuple(sorted_items[:required])]
                    if len(sorted_items) > required:
                        candidate_sets = list(combinations(sorted_items, required))

                    recovered = False
                    last_err = None
                    for combo in candidate_sets:
                        combo_shares = [s for _, s in combo]
                        try:
                            encrypted_b64 = _shamir.reconstruct_secret(combo_shares)
                            encrypted, b64_mode = _decode_base64_resilient(encrypted_b64)
                            if encrypted is None:
                                raise ValueError("base64_decode_failed")
                        except Exception as e:
                            last_err = e
                            continue

                        decrypted_text = None
                        # Primary path: no-user-input decryption from embedded key (new batches).
                        key_hex = group.get("decrypt_key_hex")
                        if key_hex:
                            try:
                                decrypted_text = decrypt_aes_gcm(encrypted, bytes.fromhex(key_hex)).decode("utf-8")
                            except Exception:
                                decrypted_text = None

                        # Fallback path: try user-supplied passwords (legacy batches).
                        if decrypted_text is None:
                            for pw in pw_list:
                                try:
                                    key = _derive_key_from_secret(pw)
                                    decrypted_text = decrypt_aes_gcm(encrypted, key).decode("utf-8")
                                    break
                                except Exception:
                                    continue

                        if decrypted_text is None:
                            last_err = ValueError("decrypt_failed")
                            continue

                        batch_decrypted_text = decrypted_text
                        batch_decryption_status = "success"
                        if b64_mode == "salvaged":
                            batch_decryption_error = None
                        contributing_files = {
                            group["source_files"].get(idx)
                            for idx, _ in combo
                            if group["source_files"].get(idx)
                        }
                        recovered = True
                        break

                    if recovered:
                        break

                    batch_decryption_status = "failed"
                    batch_decryption_error = (
                        "Reconstruction did not yield valid decryptable Base64 payload from available shares. "
                        "Likely corrupted/legacy fragments or hidden share extraction noise."
                    )
                    if last_err is not None:
                        batch_decryption_error += f" Last error: {last_err}"
                except Exception as e:
                    batch_decryption_status = "failed"
                    batch_decryption_error = f"Shamir-stego reconstruction failed: {e}"
                    if "integer division or modulo by zero" in str(e):
                        batch_decryption_error += (
                            " Likely legacy share batch created before Shamir field fix; "
                            "please regenerate shares with the current server and retry."
                        )

        if batch_decryption_status == "success" and batch_decrypted_text is not None:
            for row in results:
                if row.get("filename") in contributing_files:
                    row["decrypted_text"] = batch_decrypted_text
                    row["decryption_status"] = "success"
        elif batch_decryption_status == "failed":
            for row in results:
                if row.get("share_info"):
                    row["decryption_status"] = "failed"
                    row["decryption_error"] = batch_decryption_error

        _audit_log("stego_analyze_batch", request, {"count": len(results), "suspicious": suspicious})
        return {
            "batch": True,
            "total_images": len(results),
            "suspicious_images": suspicious,
            "clean_images": len(results) - suspicious,
            "decryption_status": batch_decryption_status,
            "decrypted_text": batch_decrypted_text,
            "decryption_error": batch_decryption_error,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Batch steganalysis failed: {e}")


# ==================== GEMINI AI IMAGE GENERATION APIs ====================


class GeminiGenerateRequest(BaseModel):
    prompt: str = "Abstract artistic pattern"
    use_gemini: bool = True
    provider: str = "auto"  # auto | genai | openai | llm | mock
    size: Tuple[int, int] = (512, 512)
    allow_fallback: bool = False
    user_id: str = None  # User-specific storage


class GeminiHideRequest(BaseModel):
    prompt: str
    secret_text: str
    password: str = ""
    use_gemini: bool = True
    provider: str = "auto"
    size: Tuple[int, int] = (1024, 1024)
    allow_fallback: bool = False
    user_id: Optional[str] = None


class GenAIPromptRequest(BaseModel):
    theme: str = "Abstract artistic security visualization"
    n_prompts: int = 10


@app.post("/api/genai/recommend-prompts")
def genai_recommend_prompts(req: GenAIPromptRequest):
    """Recommend diverse image prompts using GenAI text capabilities."""
    try:
        n = max(1, min(20, int(req.n_prompts)))
        prompts = recommend_prompts_with_genai(n=n, user_theme=req.theme)
        return {
            "status": "success",
            "n_prompts": len(prompts),
            "theme": req.theme,
            "prompts": prompts,
            "model_chain": {
                "primary": _get_env("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile") if _get_env("GROQ_API_KEY") else None,
                "secondary": _get_env("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini") if _get_env("OPENROUTER_API_KEY") else None,
                "fallback": "local_deterministic",
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prompt recommendation failed: {e}")


@app.get("/api/genai/models")
def genai_models():
    """
    Expose recommended model defaults for GenAI image + prompt workflows.
    """
    return {
        "status": "success",
        "recommended": {
            "image_model": os.getenv("GENAI_IMAGE_MODEL", "gemini-2.0-flash-exp"),
            "text_model": os.getenv("GENAI_TEXT_MODEL", "models/gemini-1.5-flash")
        },
        "features": [
            "Prompt recommendation (diverse styles)",
            "Colorful anti-grayscale prompt constraints",
            "Image generation with SDK/REST fallback"
        ]
    }


def _derive_layer_key(password: str, rounds: int = 200000) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        b"aegis_ghost_russian_doll",
        rounds,
        dklen=32,
    )


def _kdf_rounds_from_profile(profile: str) -> int:
    p = (profile or "pbkdf2_high").lower()
    if p == "pbkdf2_low":
        return 100000
    return 250000


def _create_russian_doll_payload(secret_text: str, passwords: List[str], kdf_rounds: int) -> str:
    """
    Build nested encrypted payload string.
    Password list order is outermost -> innermost for decryption.
    """
    if not passwords:
        raise ValueError("At least one password is required")
    current = secret_text
    # Encrypt innermost first, then wrap outward
    for pw in reversed(passwords):
        key = _derive_layer_key(pw, rounds=kdf_rounds)
        from core.encryption import encrypt_aes_gcm
        blob = encrypt_aes_gcm(current.encode("utf-8"), key)
        layer = {
            "blob": blob.hex(),
            "key_check": hashlib.sha256(key).hexdigest()[:16],
            "algo": "AES-GCM",
            "v": 1
        }
        current = json.dumps(layer, separators=(",", ":"))
    return current


def _open_russian_doll_payload(payload: str, passwords: List[str], kdf_rounds: int) -> str:
    """
    Open nested encrypted payload with passwords in outermost -> innermost order.
    """
    from core.encryption import decrypt_aes_gcm
    current = payload
    for pw in passwords:
        layer = json.loads(current)
        if "blob" not in layer:
            raise ValueError("Invalid layered payload format")
        key = _derive_layer_key(pw, rounds=kdf_rounds)
        if layer.get("key_check") != hashlib.sha256(key).hexdigest()[:16]:
            raise ValueError("Invalid password order or value")
        blob = bytes.fromhex(layer["blob"])
        current = decrypt_aes_gcm(blob, key).decode("utf-8")
    return current


def _pack_share_payload(share: dict) -> bytes:
    raw = json.dumps(share, separators=(",", ":")).encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


def _unpack_share_payload(payload: bytes) -> dict:
    if len(payload) < 4:
        raise ValueError("Share payload too short")
    n = struct.unpack(">I", payload[:4])[0]
    body = payload[4:4 + n]
    if len(body) != n:
        raise ValueError("Share payload truncated")
    return json.loads(body.decode("utf-8"))


def _embed_payload_lsb_image(image_path: str, payload: bytes, output_path: str):
    """
    Embed payload bytes in blue-channel LSBs.
    First 4 bytes of payload are expected to be length prefix.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    h, w, _ = arr.shape
    bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
    capacity = h * w  # one bit per pixel (blue channel)
    if len(bits) > capacity:
        raise ValueError(f"Payload too large for image capacity ({len(bits)} > {capacity} bits)")
    blue = arr[:, :, 2].reshape(-1)
    blue[:len(bits)] = (blue[:len(bits)] & 0xFE) | bits
    arr[:, :, 2] = blue.reshape(h, w)
    Image.fromarray(arr).save(output_path, "PNG")


def _extract_payload_lsb_image(image_path: str) -> bytes:
    """
    Extract length-prefixed payload from blue-channel LSBs.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    blue = arr[:, :, 2].reshape(-1)
    if blue.size < 32:
        raise ValueError("Image too small for payload header")
    header_bits = (blue[:32] & 1).astype(np.uint8)
    header = np.packbits(header_bits).tobytes()
    n = struct.unpack(">I", header)[0]
    if n <= 0 or n > 65536:
        raise ValueError("Invalid payload length")
    total_bits = (4 + n) * 8
    if blue.size < total_bits:
        raise ValueError("Image does not contain full payload")
    bits = (blue[:total_bits] & 1).astype(np.uint8)
    return np.packbits(bits).tobytes()


def _extract_payload_lsb_bytes(image_bytes: bytes) -> bytes:
    """
    Extract length-prefixed payload from blue-channel LSBs from image bytes.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    blue = arr[:, :, 2].reshape(-1)
    if blue.size < 32:
        raise ValueError("Image too small for payload header")
    header_bits = (blue[:32] & 1).astype(np.uint8)
    header = np.packbits(header_bits).tobytes()
    n = struct.unpack(">I", header)[0]
    if n <= 0 or n > 65536:
        raise ValueError("Invalid payload length")
    total_bits = (4 + n) * 8
    if blue.size < total_bits:
        raise ValueError("Image does not contain full payload")
    bits = (blue[:total_bits] & 1).astype(np.uint8)
    return np.packbits(bits).tobytes()


def _is_valid_shamir_share_obj(share_obj: dict) -> bool:
    """
    Validate Shamir share payload integrity using embedded checksum.
    """
    try:
        if not isinstance(share_obj, dict):
            return False
        y_values = share_obj.get("y_values")
        checksum = share_obj.get("checksum")
        if not isinstance(y_values, list) or not isinstance(checksum, str):
            return False
        calc = hashlib.sha256(str(y_values).encode()).hexdigest()[:16]
        return calc == checksum
    except Exception:
        return False


def _decode_base64_resilient(value: str | bytes) -> tuple[bytes | None, str | None]:
    """
    Decode possibly-corrupted base64 text using strict then salvage strategies.
    """
    try:
        if isinstance(value, bytes):
            s = value.decode("ascii")
        else:
            s = str(value)
        raw = base64.b64decode(s.encode("ascii"), validate=True)
        if raw:
            return raw, "strict"
    except Exception:
        pass

    # Salvage strategy: keep only base64 alphabet, re-pad, decode non-strict.
    try:
        if isinstance(value, bytes):
            s = value.decode("utf-8", errors="ignore")
        else:
            s = str(value)
        cleaned = re.sub(r"[^A-Za-z0-9+/=]", "", s)
        if not cleaned:
            return None, None
        if len(cleaned) % 4:
            cleaned += "=" * (4 - (len(cleaned) % 4))
        raw = base64.b64decode(cleaned.encode("ascii"), validate=False)
        if raw:
            return raw, "salvaged"
    except Exception:
        pass
    return None, None


def _preprocess_image_bytes(image_bytes: bytes) -> tuple[bytes, dict]:
    """
    Normalize uploaded image bytes for deterministic steganalysis.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PNG")
    w, h = img.size
    return out.getvalue(), {"width": int(w), "height": int(h), "channels": 3}


def _decode_payload_multiformat(payload_bytes: bytes) -> tuple[dict | None, dict]:
    """
    Decode payload using binary/base64/hex strategies.
    Returns (decoded_object_or_none, decoder_report).
    """
    report = {"strategy": None, "attempts": []}

    # 1) Native length-prefixed JSON payload (binary path).
    try:
        obj = _unpack_share_payload(payload_bytes)
        report["strategy"] = "binary_length_prefixed_json"
        report["attempts"].append({"name": "binary", "ok": True})
        return obj, report
    except Exception as e:
        report["attempts"].append({"name": "binary", "ok": False, "error": str(e)})

    # 2) Base64 decode then parse length-prefixed JSON.
    try:
        b64 = base64.b64decode(payload_bytes, validate=True)
        obj = _unpack_share_payload(b64)
        report["strategy"] = "base64_then_binary_json"
        report["attempts"].append({"name": "base64", "ok": True})
        return obj, report
    except Exception as e:
        report["attempts"].append({"name": "base64", "ok": False, "error": str(e)})

    # 3) Hex decode then parse length-prefixed JSON.
    try:
        hex_text = payload_bytes.decode("ascii", errors="strict").strip()
        hx = bytes.fromhex(hex_text)
        obj = _unpack_share_payload(hx)
        report["strategy"] = "hex_then_binary_json"
        report["attempts"].append({"name": "hex", "ok": True})
        return obj, report
    except Exception as e:
        report["attempts"].append({"name": "hex", "ok": False, "error": str(e)})

    return None, report


class AdvancedStegoHideRequest(BaseModel):
    secret_text: str
    prompt_theme: str = "Abstract artistic pattern"
    passwords: List[str]
    threshold: int = 6
    n_images: int = 10
    provider: str = "genai"  # genai | openai | llm | mock | auto
    size: tuple = (512, 512)
    kdf_profile: str = "pbkdf2_high"  # pbkdf2_high | pbkdf2_low
    encrypt_outputs_at_rest: bool = False
    fake_lsb_secret: Optional[str] = "NO_VALID_SECRET_PRESENT"
    require_ai_images: bool = True
    allow_fallback: bool = False
    user_id: str = None  # User-specific storage


class AdvancedStegoRevealRequest(BaseModel):
    image_paths: List[str]
    passwords: List[str]
    threshold: int = 6
    manifest_path: Optional[str] = None


class AdvancedBackupExportRequest(BaseModel):
    manifest_path: str
    backup_passphrase: str


class AdvancedBackupImportRequest(BaseModel):
    backup_blob_b64: str
    backup_passphrase: str


@app.post("/api/stego/advanced/hide")
def stego_advanced_hide(req: AdvancedStegoHideRequest):
    _require_advanced_crypto_enabled()
    """
    Advanced hide flow:
    1) Russian Doll encrypt secret
    2) Shamir split into exactly 10 shares (default)
    3) Generate 10 AI images and embed one share per image
    """
    try:
        if req.n_images != 10:
            raise HTTPException(status_code=400, detail="n_images must be exactly 10")
        if req.threshold < 2 or req.threshold > req.n_images:
            raise HTTPException(status_code=400, detail="threshold must be between 2 and 10")
        if not req.passwords:
            raise HTTPException(status_code=400, detail="At least one password is required")

        backend_name, use_mock_flag, backend_reason = _resolve_image_backend(req.provider, use_gemini=True)
        if req.provider in ("genai", "openai", "openrouter", "puter", "groq", "pexels", "raphael") and backend_name == "mock":
            raise HTTPException(status_code=400, detail=f"Requested provider '{req.provider}' unavailable: {backend_reason}")
        if not req.allow_fallback and req.provider in ("genai", "gemini") and backend_name != "genai":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "openrouter" and backend_name != "openrouter":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "puter" and backend_name != "puter":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "openai" and backend_name != "openai":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "pexels" and backend_name != "pexels":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "raphael" and backend_name != "raphael":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "groq" and backend_name != "llm":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")

        rounds = _kdf_rounds_from_profile(req.kdf_profile)
        layered_payload = _create_russian_doll_payload(req.secret_text, req.passwords, rounds)
        ciphertext, shares, nonce, tag = encrypt_and_shatter(
            layered_payload,
            n_shares=req.n_images,
            threshold=req.threshold
        )
        # Preserve user's exact theme prompt for fidelity across all generated images.
        base_prompt = (req.prompt_theme or "").strip() or "Abstract artistic pattern"
        prompts = [base_prompt for _ in range(req.n_images)]

        timestamp = int(time.time())
        out_paths = [None] * len(shares)
        file_hashes = {}
        max_workers = max(2, int(os.getenv("ADV_STEGO_WORKERS", str(req.n_images))))

        def _generate_embed_one(i: int, share_item: tuple[int, bytes]):
            share_idx, share_bytes = share_item
            img_name = f"adv_stego_{timestamp}_{i}.png"
            user_output_dir = get_user_output_dir(req.user_id)
            img_path = os.path.join(user_output_dir, img_name)
            generate_ghost_carrier(
                prompt=prompts[i - 1],
                save_path=img_path,
                use_mock=use_mock_flag,
                size=req.size,
                backend=backend_name,
                allow_fallback=req.allow_fallback,
            )

            share_payload = {
                "share_index": int(share_idx),
                "share_hex": bytes(share_bytes).hex(),
                "threshold": req.threshold,
                "ciphertext_hex": ciphertext.hex(),
                "nonce_hex": nonce.hex(),
                "tag_hex": tag.hex(),
            }
            _embed_payload_lsb_image(img_path, _pack_share_payload(share_payload), img_path)

            if req.encrypt_outputs_at_rest:
                out_path_enc = _encrypt_path_to_enc(img_path, os.getenv("OUTPUT_ENCRYPTION_KEY", "aegis-output-default"))
                rel = os.path.relpath(out_path_enc, BASE_DIR).replace("\\", "/")
                h = _hash_file(out_path_enc)
            else:
                rel = os.path.relpath(img_path, BASE_DIR).replace("\\", "/")
                h = _hash_file(img_path)
            return i, rel, h

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [
                ex.submit(_generate_embed_one, i, share)
                for i, share in enumerate(shares, 1)
            ]
            for fut in as_completed(futures):
                i, rel, h = fut.result()
                out_paths[i - 1] = rel
                file_hashes[rel] = h

        manifest_payload = {
            "type": "advanced_stego_manifest",
            "timestamp": int(time.time()),
            "n_images": req.n_images,
            "threshold": req.threshold,
            "provider": backend_name,
            "provider_reason": backend_reason,
            "kdf_profile": req.kdf_profile,
            "kdf_rounds": rounds,
            "encrypted_outputs": bool(req.encrypt_outputs_at_rest),
            "image_paths": out_paths,
            "file_hashes": file_hashes,
            "prompt_theme": req.prompt_theme,
            "prompts_used": prompts,
        }
        manifest_payload["signature"] = _sign_manifest(manifest_payload)
        manifest_name = f"manifest_adv_{timestamp}.json"
        manifest_path = os.path.join(MANIFEST_DIR, manifest_name)
        with open(manifest_path, "w", encoding="utf-8") as mf:
            json.dump(manifest_payload, mf, indent=2)

        meta = {
            "status": "success",
            "message": "Advanced stego complete (Russian Doll + Shamir key-shares over 10 images)",
            "backend_used": backend_name,
            "n_images": req.n_images,
            "threshold": req.threshold,
            "image_paths": out_paths,
            "prompt_theme": req.prompt_theme,
            "prompts_used": prompts,
            "password_layers": len(req.passwords),
            "kdf_profile": req.kdf_profile,
            "manifest_path": os.path.relpath(manifest_path, BASE_DIR).replace("\\", "/")
        }
        _audit_log("advanced_hide", details={"provider": backend_name, "n_images": req.n_images, "threshold": req.threshold})
        return meta
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Advanced hide failed: {e}")


@app.post("/api/stego/advanced/reveal")
def stego_advanced_reveal(req: AdvancedStegoRevealRequest):
    _require_advanced_crypto_enabled()
    """
    Advanced reveal flow:
    1) Extract share payloads from provided images
    2) Reconstruct Russian Doll payload via Shamir threshold
    3) Decrypt nested layers with provided passwords
    """
    try:
        if req.threshold < 2:
            raise HTTPException(status_code=400, detail="threshold must be >= 2")
        if len(req.image_paths) < req.threshold:
            raise HTTPException(status_code=400, detail=f"Need at least {req.threshold} images")
        if not req.passwords:
            raise HTTPException(status_code=400, detail="Passwords are required")

        manifest_obj = None
        rounds = _kdf_rounds_from_profile("pbkdf2_high")
        if req.manifest_path:
            mabs = os.path.abspath(os.path.join(BASE_DIR, req.manifest_path))
            if not (mabs.startswith(BASE_DIR) and os.path.exists(mabs)):
                raise HTTPException(status_code=400, detail="Manifest file not found")
            with open(mabs, "r", encoding="utf-8") as mf:
                manifest_obj = json.load(mf)
            if not _verify_manifest(manifest_obj):
                raise HTTPException(status_code=400, detail="Manifest signature invalid")
            rounds = int(manifest_obj.get("kdf_rounds", rounds))
            for rp in req.image_paths:
                if rp in manifest_obj.get("file_hashes", {}):
                    abs_img = os.path.abspath(os.path.join(BASE_DIR, rp))
                    if os.path.exists(abs_img):
                        if _hash_file(abs_img) != manifest_obj["file_hashes"][rp]:
                            raise HTTPException(status_code=400, detail=f"Image hash mismatch: {rp}")

        reconstructed_shares = []
        ciphertext = None
        nonce = None
        tag = None
        tmp_decrypted_paths = []
        for p in req.image_paths:
            abs_path = os.path.abspath(os.path.join(BASE_DIR, p))
            if not abs_path.startswith(BASE_DIR) or not os.path.exists(abs_path):
                continue
            src_for_extract = abs_path
            if abs_path.endswith(".enc"):
                src_for_extract = _decrypt_enc_to_tmp(abs_path, os.getenv("OUTPUT_ENCRYPTION_KEY", "aegis-output-default"))
                tmp_decrypted_paths.append(src_for_extract)
            payload = _extract_payload_lsb_image(src_for_extract)
            share = _unpack_share_payload(payload)
            idx = int(share["share_index"])
            sbytes = bytes.fromhex(share["share_hex"])
            reconstructed_shares.append((idx, sbytes))
            if ciphertext is None:
                ciphertext = bytes.fromhex(share["ciphertext_hex"])
                nonce = bytes.fromhex(share["nonce_hex"])
                tag = bytes.fromhex(share["tag_hex"])
            if len(reconstructed_shares) >= req.threshold:
                break

        if len(reconstructed_shares) < req.threshold:
            raise HTTPException(status_code=400, detail="Insufficient valid share payloads extracted")

        layered_payload = reconstruct_and_decrypt(
            reconstructed_shares[:req.threshold],
            ciphertext,
            nonce,
            tag
        )
        secret = _open_russian_doll_payload(layered_payload, req.passwords, rounds)
        for tp in tmp_decrypted_paths:
            try:
                os.remove(tp)
            except Exception:
                pass
        _audit_log("advanced_reveal", details={"shares_used": req.threshold, "with_manifest": bool(req.manifest_path)})
        return {
            "status": "success",
            "message": "Advanced stego reveal complete",
            "secret_text": secret,
            "shares_used": req.threshold,
            "password_layers": len(req.passwords)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Advanced reveal failed: {e}")


@app.post("/api/stego/advanced/backup/export")
def advanced_backup_export(req: AdvancedBackupExportRequest):
    _require_advanced_crypto_enabled()
    """
    Export encrypted backup bundle for advanced stego manifest.
    """
    try:
        mabs = os.path.abspath(os.path.join(BASE_DIR, req.manifest_path))
        if not (mabs.startswith(BASE_DIR) and os.path.exists(mabs)):
            raise HTTPException(status_code=400, detail="Manifest path not found")
        with open(mabs, "rb") as f:
            payload = f.read()
        key = _derive_key_from_secret(req.backup_passphrase)
        blob = encrypt_aes_gcm(payload, key)
        _audit_log("advanced_backup_export", details={"manifest_path": req.manifest_path})
        return {
            "status": "success",
            "backup_blob_b64": base64.b64encode(blob).decode("utf-8")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Backup export failed: {e}")


@app.post("/api/stego/advanced/backup/import")
def advanced_backup_import(req: AdvancedBackupImportRequest):
    _require_advanced_crypto_enabled()
    """
    Import encrypted backup bundle and restore manifest file.
    """
    try:
        key = _derive_key_from_secret(req.backup_passphrase)
        raw = base64.b64decode(req.backup_blob_b64)
        payload = decrypt_aes_gcm(raw, key)
        manifest = json.loads(payload.decode("utf-8"))
        if not _verify_manifest(manifest):
            raise HTTPException(status_code=400, detail="Imported manifest signature invalid")
        out_name = f"manifest_restored_{int(time.time())}.json"
        out_path = os.path.join(MANIFEST_DIR, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        rel = os.path.relpath(out_path, BASE_DIR).replace("\\", "/")
        _audit_log("advanced_backup_import", details={"restored_manifest": rel})
        return {"status": "success", "manifest_path": rel}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Backup import failed: {e}")


# =============================================================================
# New Russian Doll Steganography with Fake LSB + Shamir Splitting
# =============================================================================

class RussianDollFakeLSBRequest(BaseModel):
    """Request model for Russian Doll with Fake LSB steganography."""
    secret_text: str
    password: str
    decoy_message: Optional[str] = None
    num_shares: int = 10
    threshold: int = 6
    prompt_themes: Optional[List[str]] = None
    provider: str = "auto"
    size: tuple = (512, 512)
    allow_fallback: bool = True


class RussianDollFakeLSBRevealRequest(BaseModel):
    """Request model for revealing from Russian Doll images."""
    image_paths: List[str]
    password: str
    threshold: int = 6
    manifest_path: Optional[str] = None


@app.post("/api/stego/russian-doll-fake-lsb/hide")
def russian_doll_fake_lsb_hide(req: RussianDollFakeLSBRequest):
    _require_advanced_crypto_enabled()
    """
    Russian Doll Steganography with Fake LSB + Shamir Splitting:
    
    Process:
    1. Encrypt REAL secret with AES-GCM (password-derived key)
    2. Split encryption key into N shares using Shamir's Secret Sharing
    3. Generate 10 unique AI images
    4. Embed each Shamir share in DWT coefficients (hidden layer)
    5. Embed FAKE decoy data in LSB (visible, misleading layer)
    
    Security:
    - LSB layer contains decoy (easy to detect, misleading)
    - DWT layer contains encrypted real secret (hidden)
    - Need threshold number of shares to reconstruct key
    """
    try:
        from core.steganography_russian_doll import RussianDollSteganography
        
        if req.num_shares != 10:
            raise HTTPException(status_code=400, detail="num_shares must be exactly 10")
        if req.threshold < 2 or req.threshold > req.num_shares:
            raise HTTPException(status_code=400, detail="threshold must be between 2 and 10")
        
        # Initialize steganography engine
        rds = RussianDollSteganography(output_dir=OUTPUT_DIR)
        
        # Resolve AI backend
        backend_name, use_mock_flag, backend_reason = _resolve_image_backend(req.provider, True)
        
        # Validate provider availability
        if req.provider in ("deepai", "openai", "openrouter", "puter", "groq", "gemini", "genai", "pexels", "raphael", "leonardo") and backend_name == "mock":
            raise HTTPException(status_code=400, detail=f"Requested provider '{req.provider}' unavailable: {backend_reason}")
        
        # Create Shamir shares in 10 AI-generated images
        result = rds.create_shamir_shares_in_images(
            real_secret=req.secret_text,
            password=req.password,
            num_shares=req.num_shares,
            threshold=req.threshold,
            prompt_themes=req.prompt_themes,
            ai_backend=backend_name,
            size=tuple(req.size) if req.size else (512, 512),
            decoy_message=req.decoy_message,
            allow_fallback=req.allow_fallback,
        )
        
        # Build response
        image_paths_rel = []
        for path in result['image_paths']:
            rel = os.path.relpath(path, BASE_DIR).replace("\\", "/")
            image_paths_rel.append(rel)
        
        manifest_rel = os.path.relpath(result['manifest_path'], BASE_DIR).replace("\\", "/")
        
        _audit_log("russian_doll_fake_lsb_hide", details={
            "num_shares": req.num_shares,
            "threshold": req.threshold
        })
        
        return {
            "status": "success",
            "message": "Russian Doll stego complete: Fake LSB (decoy) + Encrypted secret in DWT + Shamir shares in 10 AI images",
            "image_paths": image_paths_rel,
            "manifest_path": manifest_rel,
            "threshold": result['threshold'],
            "num_shares": result['num_shares'],
            "ciphertext_length": result['ciphertext_length'],
            "backend_used": backend_name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Russian Doll hide failed: {e}")


@app.post("/api/stego/russian-doll-fake-lsb/reveal")
def russian_doll_fake_lsb_reveal(req: RussianDollFakeLSBRevealRequest):
    _require_advanced_crypto_enabled()
    """
    Reveal secret from Russian Doll steganography images.
    
    Process:
    1. Extract Shamir shares from DWT coefficients of provided images
    2. Reconstruct encryption key using Shamir threshold
    3. Decrypt the real secret
    """
    try:
        from core.steganography_russian_doll import RussianDollSteganography
        
        if len(req.image_paths) < req.threshold:
            raise HTTPException(status_code=400, detail=f"Need at least {req.threshold} images")
        
        # Convert relative paths to absolute
        abs_paths = []
        for p in req.image_paths:
            abs_path = os.path.abspath(os.path.join(BASE_DIR, p))
            if not os.path.exists(abs_path):
                raise HTTPException(status_code=400, detail=f"Image not found: {p}")
            abs_paths.append(abs_path)
        
        # Initialize steganography engine
        rds = RussianDollSteganography(output_dir=OUTPUT_DIR)
        
        # Reconstruct secret
        secret = rds.reconstruct_secret_from_shares(
            image_paths=abs_paths,
            password=req.password,
            threshold=req.threshold
        )
        
        _audit_log("russian_doll_fake_lsb_reveal", details={
            "num_images_used": len(abs_paths),
            "threshold": req.threshold
        })
        
        return {
            "status": "success",
            "secret": secret,
            "images_used": len(abs_paths)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Reveal failed: {e}")


@app.post("/api/gemini/generate")
def gemini_generate(req: GeminiGenerateRequest):
    """Generate an image using Gemini AI (or fallback to mock)."""
    try:
        # Generate unique filename
        timestamp = int(time.time())
        filename = f"gemini_{timestamp}.png"
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        backend_name, use_mock_flag, backend_reason = _resolve_image_backend(req.provider, req.use_gemini)
        if req.provider in ("openai", "openrouter", "puter", "groq", "gemini", "genai", "pexels", "raphael", "leonardo") and backend_name == "mock":
            raise HTTPException(status_code=400, detail=f"Requested provider '{req.provider}' unavailable: {backend_reason}")
        if not req.allow_fallback and req.provider in ("genai", "gemini") and backend_name != "genai":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "openrouter" and backend_name != "openrouter":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "puter" and backend_name != "puter":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "openai" and backend_name != "openai":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "pexels" and backend_name != "pexels":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "raphael" and backend_name != "raphael":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "leonardo" and backend_name != "leonardo":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "groq" and backend_name != "llm":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        
        # Generate the image
        generate_ghost_carrier(
            prompt=req.prompt,
            save_path=output_path,
            use_mock=use_mock_flag,
            size=req.size,
            backend=backend_name,
            allow_fallback=req.allow_fallback,
        )
        
        # Return the image path
        rel_path = os.path.relpath(output_path, BASE_DIR).replace("\\", "/")
        
        return {
            "status": "success",
            "message": "Image generated successfully",
            "image_path": rel_path,
            "backend_used": backend_name,
            "prompt": req.prompt
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gemini generation failed: {e}")


@app.post("/api/gemini/hide")
def gemini_hide(req: GeminiHideRequest):
    """Generate an image with Gemini AI and hide secret data inside."""
    try:
        timestamp = int(time.time())
        
        # Generate the carrier image
        raw_filename = f"gemini_raw_{timestamp}.png"
        raw_path = os.path.join(OUTPUT_DIR, raw_filename)
        
        backend_name, use_mock_flag, backend_reason = _resolve_image_backend(req.provider, req.use_gemini)
        if req.provider in ("openai", "openrouter", "puter", "groq", "gemini", "genai", "pexels", "raphael", "leonardo") and backend_name == "mock":
            raise HTTPException(status_code=400, detail=f"Requested provider '{req.provider}' unavailable: {backend_reason}")
        if not req.allow_fallback and req.provider in ("genai", "gemini") and backend_name != "genai":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "openrouter" and backend_name != "openrouter":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "puter" and backend_name != "puter":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "openai" and backend_name != "openai":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "pexels" and backend_name != "pexels":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "raphael" and backend_name != "raphael":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "leonardo" and backend_name != "leonardo":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        if not req.allow_fallback and req.provider == "groq" and backend_name != "llm":
            raise HTTPException(status_code=400, detail=f"Strict provider mode: requested '{req.provider}' but resolved '{backend_name}' ({backend_reason})")
        
        generate_ghost_carrier(
            prompt=req.prompt,
            save_path=raw_path,
            use_mock=use_mock_flag,
            size=req.size,
            backend=backend_name,
            allow_fallback=req.allow_fallback,
        )
        
        # Embed the secret data
        output_filename = f"gemini_stego_{timestamp}.png"
        user_output_dir = get_user_output_dir(req.user_id)
        output_path = os.path.join(user_output_dir, output_filename)
        
        embed_data_dwt(raw_path, req.secret_text.encode("utf-8"), output_path)
        
        # Save coefficients for exact extraction
        coeff_path = output_path.replace(".png", "_coeff.npy")
        
        rel_out = os.path.relpath(output_path, BASE_DIR).replace("\\", "/")
        rel_coeff = os.path.relpath(coeff_path, BASE_DIR).replace("\\", "/")
        
        return {
            "status": "success",
            "message": "Secret data hidden in AI-generated image",
            "image_path": rel_out,
            "coeff_path": rel_coeff,
            "backend_used": backend_name,
            "backend_reason": backend_reason,
            "prompt": req.prompt,
            "hidden_data_length": len(req.secret_text)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gemini hide failed: {e}")


@app.post("/api/gemini/reveal")
async def gemini_reveal(request: Request, stego_image: UploadFile = File(...), password: str = Form("")):
    """Extract hidden data from an AI-generated steganography image."""
    try:
        # Save the stego image
        fname = f"gemini_reveal_{int(time.time())}_{stego_image.filename}"
        in_path = os.path.join(OUTPUT_DIR, fname)
        await _save_validated_upload(stego_image, in_path, ("image/",))
        
        # Try to extract data
        # First try with saved coefficients if available
        coeff_path = in_path.replace(".png", "_coeff.npy")
        
        import numpy as np
        raw_data = None
        if os.path.exists(coeff_path):
            # Use exact coefficients
            HH = np.load(coeff_path)
            hh_flat = HH.flatten()
            bits_list = []
            # Extract up to 256 bytes
            for i in range(256 * 8):
                val = hh_flat[i]
                lsb = int(np.round(val)) % 2
                bits_list.append(lsb)
            bits_array = np.array(bits_list, dtype=np.uint8)
            raw_data = np.packbits(bits_array).tobytes()
            # Find null terminator
            null_pos = raw_data.find(b'\x00')
            if null_pos > 0:
                raw_data = raw_data[:null_pos]
        else:
            # Fallback to extraction from image
            raw_data = extract_data_dwt(in_path, num_bytes=256)
        
        # Try decryption if password provided
        data = raw_data
        if password and raw_data:
            try:
                data = _decrypt_payload(raw_data, password)
            except Exception:
                # Decryption failed, use raw data
                data = raw_data
        
        # Try to decode as UTF-8
        try:
            text = data.decode("utf-8").strip('\x00')
            _audit_log("ai_reveal", request, {"encoding": "utf-8"})
            return {
                "status": "success",
                "text": text,
                "encoding": "utf-8"
            }
        except Exception:
            _audit_log("ai_reveal", request, {"encoding": "binary"})
            return {
                "status": "success",
                "raw_hex": data.hex(),
                "encoding": "binary"
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gemini reveal failed: {e}")


# Unified AI aliases
@app.post("/api/ai/generate")
def ai_generate(req: GeminiGenerateRequest):
    return gemini_generate(req)


@app.post("/api/ai/hide")
def ai_hide(req: GeminiHideRequest):
    return gemini_hide(req)


@app.post("/api/ai/reveal")
async def ai_reveal(stego_image: UploadFile = File(...), request: Request = None):
    return await gemini_reveal(request, stego_image)


@app.post("/api/ai/recommend-prompts")
def ai_recommend_prompts(req: GenAIPromptRequest):
    return genai_recommend_prompts(req)


@app.post("/api/auth/face/verify")
async def face_verify(
    request: Request,
    email: str = Form(""),
    images: List[UploadFile] = File(...),
):
    try:
        if not images or len(images) < 2:
            raise HTTPException(status_code=400, detail="At least 2 face frames are required for liveness detection.")
        if len(images) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 face frames are allowed.")

        frame_paths: List[str] = []
        for i, image in enumerate(images):
            tmp_path = os.path.join(OUTPUT_DIR, f"face_{int(time.time())}_{i}_{image.filename}")
            await _save_validated_upload(image, tmp_path, ("image/",))
            frame_paths.append(tmp_path)

        email_norm = (email or "").strip().lower()
        if email_norm:
            owner_path = _resolve_user_reference_face_path(email_norm)
            user_auth = BiometricAuthenticator(owner_image_path=owner_path)
            result = user_auth.verify_face_with_liveness_from_images(frame_paths)
            result["email"] = email_norm
        else:
            result = _auth.verify_face_with_liveness_from_images(frame_paths)
        # Removed: exactly one face constraint - allowing multiple faces
        if not bool(result.get("liveness_passed", False)):
            raise HTTPException(status_code=401, detail="Liveness detection failed.")

        _audit_log("face_verify", request, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Face verify failed: {e}")


@app.get("/api/outputs")
def list_outputs(user_id: str = None):
    """List output files - optionally filtered by user_id"""
    files = []
    
    # Get all output directories (shared and user-specific)
    output_base = Path("data/output_stego")
    user_output_base = Path("data/user_outputs")
    
    # First add user-specific images if user_id provided
    if user_id:
        user_dir = user_output_base / user_id.replace("@", "_at_").replace(".", "_")
        if user_dir.exists():
            for name in os.listdir(user_dir):
                if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
                    rel = str(user_dir / name).replace("\\", "/")
                    files.append(rel)
    
    # Then add shared images
    if OUTPUT_DIR and os.path.exists(OUTPUT_DIR):
        for name in os.listdir(OUTPUT_DIR):
            if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
                rel = os.path.join("data", "output_stego", name).replace("\\", "/")
                files.append(rel)
    
    return {"files": sorted(set(files))}


@app.delete("/api/outputs")
def delete_outputs(file_paths: List[str], user_id: str = None):
    """Delete specified output files"""
    deleted = []
    errors = []
    
    for file_path in file_paths:
        try:
            # Clean up the path
            clean_path = file_path.strip().lstrip("/")
            
            # Try to delete from various locations
            for base in ["", "data/", "data/user_outputs/"]:
                full_path = os.path.join(base, clean_path) if base else clean_path
                if os.path.exists(full_path):
                    os.remove(full_path)
                    deleted.append(clean_path)
                    break
            else:
                errors.append(f"File not found: {clean_path}")
        except Exception as e:
            errors.append(f"Error deleting {file_path}: {str(e)}")
    
    return {"deleted": deleted, "errors": errors}


@app.post("/api/compliance/cleanup")
def compliance_cleanup():
    cleaned = _cleanup_old_files()
    _audit_log("manual_cleanup", details={"cleaned_files": cleaned})
    return {"status": "success", "cleaned_files": cleaned, "retention_days": RETENTION_DAYS}


@app.get("/api/compliance/audit")
def compliance_audit(limit: int = 100):
    path = os.path.join(AUDIT_DIR, "audit.log")
    if not os.path.exists(path):
        return {"entries": []}
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    lines = lines[-max(1, min(limit, 1000)):]
    out = []
    at_rest_key = os.getenv("DATA_AT_REST_KEY")
    for ln in lines:
        try:
            if at_rest_key:
                key = _derive_key_from_secret(at_rest_key)
                dec = decrypt_aes_gcm(base64.b64decode(ln), key).decode("utf-8")
                out.append(json.loads(dec))
            else:
                out.append(json.loads(ln))
        except Exception:
            continue
    return {"entries": out}


@app.get("/download")
def download(path: str):
    # Security: allow only within BASE_DIR and specific folders
    abs_path = os.path.abspath(os.path.join(BASE_DIR, path))
    if not abs_path.startswith(BASE_DIR):
        raise HTTPException(status_code=403, detail="Forbidden path")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(abs_path)


@app.get("/")
def root_index():
    # Default to React frontend.
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    # Fallback to legacy interface if React build is missing.
    if os.path.exists(LEGACY_FRONTEND_INDEX):
        return FileResponse(LEGACY_FRONTEND_INDEX)
    # Fallback HTML if frontend not created yet
    html = """
    <!doctype html>
    <html>
      <head><meta charset='utf-8'><title>Project Aegis Ghost</title></head>
      <body>
        <h1>Project Aegis Ghost</h1>
        <p>Frontend not yet created. Endpoints are available under /api/*</p>
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


@app.get("/legacy")
def legacy_index():
    """Serve original static frontend interface."""
    if os.path.exists(LEGACY_FRONTEND_INDEX):
        return FileResponse(LEGACY_FRONTEND_INDEX)
    raise HTTPException(status_code=404, detail="Legacy frontend not found")


# API to get all registered users (for finding users in secure chat)
@app.get("/api/users")
def get_registered_users():
    """Get list of all registered users (for secure chat user search)"""
    try:
        users = get_all_registered_users()
        return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get users: {e}")


# IMPORTANT:
# Keep chat GET routes before the catch-all React route so they return JSON
# instead of index.html.
@app.get("/api/chat/conversations")
def chat_get_conversations_early(user_id: str):
    return get_conversations(user_id)


@app.get("/api/chat/messages/{conversation_id}")
def chat_get_messages_early(conversation_id: str, user_id: str):
    return get_messages(conversation_id, user_id)


@app.get("/api/chat/files/{file_id}")
async def chat_get_file_early(file_id: str):
    return await get_chat_file(file_id)


@app.get("/{path:path}")
def serve_react_app(path: str):
    """Serve frontend assets/routes with preference for React UI."""
    # 1) React build static files
    build_file_path = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(build_file_path):
        return FileResponse(build_file_path)

    # 2) Legacy frontend files
    legacy_file_path = os.path.join(LEGACY_FRONTEND_DIR, path)
    if os.path.isfile(legacy_file_path):
        return FileResponse(legacy_file_path)

    # 3) Prefer React index, fallback to legacy index
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    if os.path.exists(LEGACY_FRONTEND_INDEX):
        return FileResponse(LEGACY_FRONTEND_INDEX)
    return HTMLResponse(content=html, status_code=200)


# Initialize watermark manager
_watermarker = DigitalWatermarker()

# Initialize conversation manager
_conversation_manager = SecureConversationManager(
    storage_path=os.path.join(BASE_DIR, "data", "conversations")
)


def _normalize_chat_identifier(value: str) -> str:
    return (value or "").strip().lower()


def _resolve_chat_user_identity(identifier: str, *, strict_lookup: bool = False) -> tuple[str, list[str]]:
    """
    Resolve a chat identifier (email/name/member-id) to canonical user email when possible.
    Returns (canonical_identifier, aliases).
    """
    raw = (identifier or "").strip()
    if not raw:
        raise ValueError("User identifier is required")
    normalized = _normalize_chat_identifier(raw)
    users = load_users()

    canonical = normalized
    aliases = {normalized}

    if normalized in users:
        canonical = normalize_email(normalized)
    else:
        matches = []
        for email, profile in users.items():
            name_key = _normalize_chat_identifier(profile.get("name", ""))
            id_key = _normalize_chat_identifier(profile.get("id_no", ""))
            if normalized and (normalized == name_key or normalized == id_key):
                matches.append(normalize_email(email))
        if len(matches) == 1:
            canonical = matches[0]
        elif len(matches) > 1:
            raise ValueError("Identifier matches multiple users; use recipient email instead")
        elif strict_lookup and "@" not in normalized:
            raise ValueError("Recipient not found. Enter the recipient email")

    aliases.add(canonical)
    profile = users.get(canonical)
    if profile:
        aliases.add(canonical)
        aliases.add(_normalize_chat_identifier(profile.get("name", "")))
        aliases.add(_normalize_chat_identifier(profile.get("id_no", "")))

    aliases.discard("")
    return canonical, sorted(aliases)


def _canonicalize_participants(participants: List[str]) -> List[str]:
    if not participants:
        raise ValueError("At least one participant is required")
    resolved: List[str] = []
    seen = set()
    for participant in participants:
        canonical, _aliases = _resolve_chat_user_identity(participant, strict_lookup=True)
        key = _normalize_chat_identifier(canonical)
        if key and key not in seen:
            seen.add(key)
            resolved.append(canonical)
    if len(resolved) < 2:
        raise ValueError("A conversation requires at least two unique participants")
    return resolved


def _chat_display_name(identifier: str) -> str:
    """Return human-friendly display name for a chat identifier."""
    users = load_users()
    key = normalize_email(identifier)
    profile = users.get(key) or {}
    name = (profile.get("name") or "").strip()
    if name:
        return name
    if "@" in identifier:
        return identifier.split("@", 1)[0]
    return identifier


def _chat_participant_names(participants: List[str]) -> List[str]:
    return [_chat_display_name(p) for p in participants]

# ==================== DIGITAL WATERMARKING APIs ====================


class WatermarkEmbedRequest(BaseModel):
    watermark_text: str
    position: str = "bottom-right"
    opacity: float = 0.5
    font_size: int = 24
    font_family: str = "Arial"
    font_style: str = "normal"
    font_weight: str = "normal"
    text_shadow: bool = True
    rotation: float = 0.0
    color: str = "#FFFFFF"
    logo_position: str = "top-right"
    logo_size: int = 50
    logo_opacity: float = 0.8
    visible: bool = True
    invisible: bool = True
    owner_id: str = "AEGIS-GHOST"


@app.post("/api/watermark/embed")
async def embed_watermark(
    request: Request,
    image: UploadFile = File(...),
    watermark_text: str = Form(...),
    position: str = Form("bottom-right"),
    opacity: float = Form(0.5),
    font_size: int = Form(24),
    font_family: str = Form("Arial"),
    font_style: str = Form("normal"),
    font_weight: str = Form("normal"),
    text_shadow: bool = Form(True),
    rotation: float = Form(0.0),
    color: str = Form("#FFFFFF"),
    logo_position: str = Form("top-right"),
    logo_size: int = Form(50),
    logo_opacity: float = Form(0.8),
    logo_image: UploadFile | None = File(None),
    doodle_image: UploadFile | None = File(None),
    visible: bool = Form(True),
    invisible: bool = Form(True),
    owner_id: str = Form("AEGIS-GHOST"),
    user_id: str = Form(None)
):
    """Embed visible and/or invisible watermark in image"""
    try:
        # Get user-specific output directory
        user_output_dir = get_user_output_dir(user_id)
        timestamp = int(time.time())
        
        # Save uploaded image
        fname = f"watermark_src_{timestamp}_{image.filename}"
        src_path = os.path.join(user_output_dir, fname)
        await _save_validated_upload(image, src_path, ("image/",))
        
        # Output filename
        out_name = f"watermarked_{timestamp}.png"
        out_path = os.path.join(user_output_dir, out_name)
        logo_path = None
        doodle_path = None

        if logo_image is not None and logo_image.filename:
            logo_name = f"watermark_logo_{timestamp}_{logo_image.filename}"
            logo_path = os.path.join(user_output_dir, logo_name)
            await _save_validated_upload(logo_image, logo_path, ("image/",))

        if doodle_image is not None and doodle_image.filename:
            doodle_name = f"watermark_doodle_{timestamp}_{doodle_image.filename}"
            doodle_path = os.path.join(user_output_dir, doodle_name)
            await _save_validated_upload(doodle_image, doodle_path, ("image/",))
        
        result = {}
        
        # Apply visible watermark
        if visible:
            _watermarker.create_visible_watermark(
                src_path, out_path,
                watermark_text=watermark_text,
                position=position,
                opacity=opacity,
                font_size=font_size,
                color=color,
                font_family=font_family,
                font_style=font_style,
                font_weight=font_weight,
                text_shadow=text_shadow,
                rotation=rotation,
                logo_path=logo_path,
                logo_position=logo_position,
                logo_size=logo_size,
                logo_opacity=logo_opacity,
                doodle_path=doodle_path,
            )
        else:
            # Just copy the file
            import shutil
            shutil.copy(src_path, out_path)
        
        # Apply invisible watermark to the current output so a single image
        # contains both visible and invisible watermark when both are enabled.
        if invisible:
            invisible_result = _watermarker.create_invisible_watermark(
                out_path,
                out_path,
                secret_data=watermark_text,
                owner_id=owner_id
            )
            result['invisible'] = invisible_result
        
        # Get image for analysis
        from core.digital_watermarking import analyze_image_forensic
        analysis = analyze_image_forensic(out_path)
        
        rel_out = os.path.relpath(out_path, BASE_DIR).replace("\\", "/")
        result_obj = {
            "success": True,
            "output_path": f"/{rel_out}",
            "metadata": {
                "owner_id": owner_id,
                "timestamp": timestamp,
                "watermark_text": watermark_text,
                "visible": visible,
                "invisible": invisible,
                "font_size": font_size,
                "font_family": font_family,
                "font_style": font_style,
                "font_weight": font_weight,
                "text_shadow": text_shadow,
                "rotation": rotation,
                "color": color,
            },
            **result,
            "file_analysis": analysis
        }
        _audit_log("watermark_embed", request, {"visible": visible, "invisible": invisible, "owner_id": owner_id})
        return result_obj
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Watermark embed failed: {e}")


class WatermarkVerifyRequest(BaseModel):
    expected_owner: Optional[str] = ""


@app.post("/api/watermark/verify")
async def verify_watermark(
    request: Request,
    image: UploadFile = File(...),
    expected_owner: str = Form("")
):
    """Verify invisible watermark in image"""
    try:
        # Save uploaded image
        fname = f"verify_{int(time.time())}_{image.filename}"
        in_path = os.path.join(OUTPUT_DIR, fname)
        await _save_validated_upload(image, in_path, ("image/",))
        
        # Only pass expected_owner if it's not empty
        owner_param = expected_owner if expected_owner else None
        
        result = _watermarker.verify_watermark(
            in_path,
            expected_owner=owner_param
        )
        
        _audit_log("watermark_verify", request, {"verified": bool(result.get("verified"))})
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Watermark verify failed: {e}")


@app.post("/api/watermark/analyze")
async def analyze_watermark(request: Request, image: UploadFile = File(...)):
    """Perform forensic analysis on image"""
    try:
        # Save uploaded image
        fname = f"analyze_{int(time.time())}_{image.filename}"
        in_path = os.path.join(OUTPUT_DIR, fname)
        await _save_validated_upload(image, in_path, ("image/",))
        
        analysis = analyze_image_forensic(in_path)
        
        result = {
            "success": True,
            **analysis
        }
        _audit_log("watermark_analyze", request, {"status": "ok"})
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {e}")


# ==================== SECURE CHAT APIs ====================


class CreateConversationRequest(BaseModel):
    participants: List[str]
    name: Optional[str] = None
    is_group: bool = False


@app.post("/api/chat/conversations")
def create_conversation(req: CreateConversationRequest):
    """Create new secure conversation"""
    try:
        canonical_participants = _canonicalize_participants(req.participants)
        if not canonical_participants or not is_registered_user(canonical_participants[0]):
            raise HTTPException(status_code=403, detail="Only registered users can create secure chat conversations")
        conversation = _conversation_manager.create_conversation(
            participants=canonical_participants,
            name=req.name
        )
        
        return {
            "success": True,
            "conversation": {
                "id": conversation.id,
                "name": conversation.name,
                "display_name": conversation.name or ", ".join(_chat_participant_names(conversation.participants)),
                "participants": conversation.participants,
                "participant_names": _chat_participant_names(conversation.participants),
                "is_group": conversation.is_group,
                "created_at": conversation.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Create conversation failed: {e}")


@app.get("/api/chat/conversations")
def get_conversations(user_id: str):
    """Get all conversations for user"""
    try:
        canonical_user, user_aliases = _resolve_chat_user_identity(user_id, strict_lookup=False)
        if not is_registered_user(canonical_user):
            raise HTTPException(status_code=403, detail="Only registered users can access secure chat")
        conversations = _conversation_manager.get_user_conversations(canonical_user, user_aliases=user_aliases)
        for conv in conversations:
            participants = conv.get("participants") or []
            names = _chat_participant_names(participants)
            conv["participant_names"] = names
            others = [n for p, n in zip(participants, names) if normalize_email(p) != canonical_user]
            conv["display_name"] = conv.get("name") or ", ".join(others or names) or "Secure Chat"
        return {"conversations": conversations}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Get conversations failed: {e}")


class SendMessageRequest(BaseModel):
    conversation_id: str
    sender_id: str
    content: str
    ephemeral: bool = False
    destroy_after_seconds: Optional[int] = None


@app.post("/api/chat/send")
def send_message(req: SendMessageRequest):
    """Send encrypted message"""
    try:
        canonical_sender, sender_aliases = _resolve_chat_user_identity(req.sender_id, strict_lookup=False)
        if not is_registered_user(canonical_sender):
            raise HTTPException(status_code=403, detail="Only registered users can use secure chat")
        message = _conversation_manager.send_message(
            conversation_id=req.conversation_id,
            sender_id=canonical_sender,
            content=req.content,
            ephemeral=req.ephemeral,
            destroy_after_seconds=req.destroy_after_seconds,
            sender_aliases=sender_aliases
        )
        
        return {
            "success": True,
            "message_id": message.id,
            "timestamp": message.timestamp,
            "ephemeral": message.ephemeral,
            "destroy_at": message.destroy_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Send message failed: {e}")


# ==================== FILE UPLOAD FOR CHAT ====================

import base64

CHAT_FILES_DIR = os.path.join(DATA_DIR, "chat_files")
os.makedirs(CHAT_FILES_DIR, exist_ok=True)

class SendFileRequest(BaseModel):
    conversation_id: str
    sender_id: str
    file_name: str
    file_type: str  # "image" or "zip"
    ephemeral: bool = False
    destroy_after_seconds: Optional[int] = None


@app.post("/api/chat/send-file")
async def send_file(
    request: Request,
    conversation_id: str = Form(...),
    sender_id: str = Form(...),
    file_name: str = Form(...),
    file_type: str = Form(...),
    ephemeral: bool = Form(False),
    destroy_after_seconds: int = Form(None),
    file: UploadFile = File(...)
):
    """Send image or zip file in encrypted chat"""
    try:
        canonical_sender, sender_aliases = _resolve_chat_user_identity(sender_id, strict_lookup=False)
        if not is_registered_user(canonical_sender):
            raise HTTPException(status_code=403, detail="Only registered users can use secure chat")
        
        # Validate file type
        allowed_types = {
            "image": ["image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"],
            "zip": ["application/zip", "application/x-zip-compressed"]
        }
        
        content_type = file.content_type
        if file_type not in allowed_types or content_type not in allowed_types[file_type]:
            raise HTTPException(status_code=400, detail=f"Invalid file type for {file_type}")
        
        # Read and encode file content
        file_content = await file.read()
        file_b64 = base64.b64encode(file_content).decode('utf-8')
        
        # Create message with file data
        # Store file and create message
        import time
        timestamp = int(time.time() * 1000)
        safe_name = f"{timestamp}_{file_name}"
        file_path = os.path.join(CHAT_FILES_DIR, safe_name)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Create message content with file reference
        file_message = f"[FILE:{file_type}:{file_name}:{safe_name}]"
        
        message = _conversation_manager.send_message(
            conversation_id=conversation_id,
            sender_id=canonical_sender,
            content=file_message,
            ephemeral=ephemeral,
            destroy_after_seconds=destroy_after_seconds,
            sender_aliases=sender_aliases
        )
        
        return {
            "success": True,
            "message_id": message.id,
            "timestamp": message.timestamp,
            "ephemeral": message.ephemeral,
            "destroy_at": message.destroy_at,
            "file_name": file_name,
            "file_type": file_type,
            "file_id": safe_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Send file failed: {e}")


@app.get("/api/chat/files/{file_id}")
async def get_chat_file(file_id: str):
    """Download a chat file"""
    try:
        file_path = os.path.join(CHAT_FILES_DIR, file_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine content type
        ext = os.path.splitext(file_id)[1].lower()
        content_type = "application/octet-stream"
        if ext == ".png":
            content_type = "image/png"
        elif ext in [".jpg", ".jpeg"]:
            content_type = "image/jpeg"
        elif ext == ".gif":
            content_type = "image/gif"
        elif ext == ".webp":
            content_type = "image/webp"
        elif ext == ".zip":
            content_type = "application/zip"
        
        # Extract original filename (remove timestamp prefix)
        original_filename = os.path.basename(file_id)
        if '_' in original_filename:
            # Find the first underscore and check if timestamp (all digits)
            parts = original_filename.split('_', 1)
            if len(parts) > 1 and parts[0].isdigit():
                original_filename = parts[1]
        
        # Force download with Content-Disposition header
        headers = {
            "Content-Disposition": f'attachment; filename="{original_filename}"'
        }
        return FileResponse(
            file_path, 
            media_type=content_type, 
            filename=original_filename,
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Get file failed: {e}")


@app.get("/api/chat/messages/{conversation_id}")
def get_messages(conversation_id: str, user_id: str):
    """Get and decrypt messages for conversation"""
    try:
        canonical_user, user_aliases = _resolve_chat_user_identity(user_id, strict_lookup=False)
        if not is_registered_user(canonical_user):
            raise HTTPException(status_code=403, detail="Only registered users can access secure chat")
        messages = _conversation_manager.get_messages(
            conversation_id=conversation_id,
            user_id=canonical_user,
            user_aliases=user_aliases
        )
        for msg in messages:
            sender = msg.get("sender")
            if sender:
                msg["sender_name"] = _chat_display_name(str(sender))
        return {"messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Get messages failed: {e}")


class DeleteMessagesRequest(BaseModel):
    message_ids: List[str]
    conversation_id: str
    user_id: str


@app.post("/api/chat/messages/delete")
def delete_messages(request: DeleteMessagesRequest):
    """Delete selected messages"""
    try:
        canonical_user, _ = _resolve_chat_user_identity(request.user_id, strict_lookup=False)
        if not is_registered_user(canonical_user):
            raise HTTPException(status_code=403, detail="Only registered users can delete messages")
        
        success = _conversation_manager.delete_messages(
            conversation_id=request.conversation_id,
            message_ids=request.message_ids,
            user_id=canonical_user
        )
        return {"success": success, "deleted": len(request.message_ids)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Delete messages failed: {e}")


from core.security_monitor import security_monitor


@app.delete("/api/chat/conversations/{conversation_id}")
def destroy_conversation(conversation_id: str):
    """Permanently destroy conversation"""
    try:
        success = _conversation_manager.destroy_conversation(conversation_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Destroy conversation failed: {e}")


# ==================== SECURITY MONITORING APIs ====================


class SecurityRecordRequest(BaseModel):
    user_id: str
    action: str = "login"


class SecurityAdvisorRequest(BaseModel):
    system_context: str = ""
    max_findings: int = 10
    include_runtime_context: bool = True


class AIAssistRequest(BaseModel):
    prompt: str
    provider: str = "auto"  # auto|groq|openrouter|openai
    max_tokens: int = 700


@app.post("/api/security/record")
def record_security_event(request: SecurityRecordRequest):
    """Record a security event (login, logout, etc.)"""
    try:
        client_ip = "127.0.0.1"  # Will be overridden by actual IP in production
        result = security_monitor.record_session(
            user_id=request.user_id,
            ip=client_ip,
            action=request.action
        )
        return {
            "status": "recorded",
            "event": result["event"],
            "alert": result["alert"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Record failed: {e}")


@app.post("/api/security/advisor")
def security_advisor(req: SecurityAdvisorRequest):
    """LLM-backed technical/security vulnerability assessment."""
    try:
        context_parts = []
        if req.include_runtime_context:
            context_parts.append(
                json.dumps(
                    {
                        "cors_allow_origins": ["*"],
                        "allow_credentials": True,
                        "max_upload_mb": MAX_UPLOAD_MB,
                        "retention_days": RETENTION_DAYS,
                        "providers": {
                            "groq": bool(_get_env("GROQ_API_KEY")),
                            "openrouter": bool(_get_env("OPENROUTER_API_KEY")),
                            "openai": bool(_get_env("OPENAI_API_KEY")),
                            "gemini": bool(_get_env("GEMINI_API_KEY")),
                        },
                    },
                    separators=(",", ":"),
                )
            )
            try:
                alerts = security_monitor.get_all_alerts()
                context_parts.append(json.dumps({"recent_security_alerts": alerts[:20]}, separators=(",", ":")))
            except Exception:
                pass
        if req.system_context:
            context_parts.append(req.system_context)

        report = analyze_security_vulnerabilities(
            system_context="\n".join(context_parts),
            max_findings=req.max_findings,
        )
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Security advisor failed: {e}")


@app.post("/api/ai/assist")
def ai_assist(req: AIAssistRequest):
    """General assistant using Groq/OpenRouter/OpenAI with explicit provider control."""
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")

    system_prompt = (
        "You are a security-focused software engineering assistant. "
        "Provide specific, practical, non-generic answers."
    )
    p = (req.provider or "auto").strip().lower()
    if p == "groq":
        chain = ["groq"]
    elif p == "openrouter":
        chain = ["openrouter"]
    elif p == "openai":
        chain = ["openai"]
    else:
        chain = ["groq", "openrouter", "openai"]

    def _chat(url: str, headers: dict, model: str) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.45,
            "max_tokens": max(80, min(1200, int(req.max_tokens))),
        }
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        r.raise_for_status()
        data = r.json()
        return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()

    last_error = None
    for provider in chain:
        try:
            if provider == "groq" and _get_env("GROQ_API_KEY"):
                text = _chat(
                    "https://api.groq.com/openai/v1/chat/completions",
                    {"Authorization": f"Bearer {_get_env('GROQ_API_KEY')}", "Content-Type": "application/json"},
                    _get_env("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile"),
                )
                if text:
                    return {"status": "success", "provider": "groq", "text": text}
            if provider == "openrouter" and _get_env("OPENROUTER_API_KEY"):
                text = _chat(
                    "https://openrouter.ai/api/v1/chat/completions",
                    {
                        "Authorization": f"Bearer {_get_env('OPENROUTER_API_KEY')}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": _get_env("OPENROUTER_HTTP_REFERER", "http://localhost"),
                        "X-Title": _get_env("OPENROUTER_X_TITLE", "Project Aegis Ghost"),
                    },
                    _get_env("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini"),
                )
                if text:
                    return {"status": "success", "provider": "openrouter", "text": text}
            if provider == "openai" and _get_env("OPENAI_API_KEY"):
                text = _chat(
                    "https://api.openai.com/v1/chat/completions",
                    {"Authorization": f"Bearer {_get_env('OPENAI_API_KEY')}", "Content-Type": "application/json"},
                    _get_env("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
                )
                if text:
                    return {"status": "success", "provider": "openai", "text": text}
        except Exception as e:
            last_error = e
            continue

    raise HTTPException(status_code=400, detail=f"No text provider available or request failed: {last_error}")


@app.get("/api/security/status/{user_id}")
def get_security_status(user_id: str):
    """Get security status for a specific user"""
    try:
        status = security_monitor.get_user_security_status(user_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Status check failed: {e}")


@app.get("/api/security/alerts")
def get_security_alerts():
    """Get all security alerts"""
    try:
        alerts = security_monitor.get_all_alerts()
        return {
            "alerts": alerts,
            "total_count": len(alerts)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Get alerts failed: {e}")


@app.get("/api/security/recent-activity")
def get_recent_activity():
    """Get recent activity for dashboard"""
    try:
        activities = security_monitor.get_recent_activity(limit=10)
        return {
            "activities": activities,
            "total_count": len(activities)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Get recent activity failed: {e}")


@app.delete("/api/security/history/{user_id}")
def clear_security_history(user_id: str):
    """Clear security history for a user (admin function)"""
    try:
        security_monitor.clear_user_history(user_id)
        return {"status": "cleared", "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Clear history failed: {e}")


@app.delete("/api/security/alerts")
async def delete_alerts(request: Request):
    """Delete multiple alerts by IDs"""
    try:
        body = await request.json()
        alert_ids = body.get('alert_ids', [])
        if not alert_ids:
            return {"status": "no_alerts_specified", "deleted_count": 0}
        
        deleted_count = security_monitor.delete_alerts(alert_ids)
        return {"status": "deleted", "deleted_count": deleted_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Delete alerts failed: {e}")


# ==================== SHAMIR & RUSSIAN DOLL ENCRYPTION ====================

from core.shamir_russian_doll import ShamirSecretSharing, RussianDollEncryption
_shamir = ShamirSecretSharing()
_russian_doll = RussianDollEncryption()


class ShamirSplitRequest(BaseModel):
    secret: str
    num_shares: int = 5
    threshold: int = 3


class ShamirStegoRequest(BaseModel):
    secret: str
    password: str
    num_shares: int = 10
    threshold: int = 6
    prompt: str = "Abstract geometric patterns with hidden data, dark theme, cyberpunk"
    model: str = "pollinations"


@app.post("/api/shamir-stego/create")
def create_shamir_stego_images(req: ShamirStegoRequest):
    _require_advanced_crypto_enabled()
    """Create 10 images with encrypted Shamir shares embedded."""
    try:
        import json
        import base64
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from core.encryption import encrypt_aes_gcm
        from core.steganography import embed_data_dwt
        from core.ai_engine import generate_ghost_carrier
        from PIL import Image
        import numpy as np
        
        # 1. Encrypt the secret
        key = _derive_key_from_secret(req.password)
        secret_bytes = req.secret.encode('utf-8')
        encrypted = encrypt_aes_gcm(secret_bytes, key)
        
        # Convert bytes to base64 string for Shamir (it expects string)
        encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')
        
        # 2. Split using Shamir's Secret Sharing into 10 shares
        if req.num_shares < 2:
            raise HTTPException(status_code=400, detail="num_shares must be at least 2")
        if req.threshold < 2 or req.threshold > req.num_shares:
            raise HTTPException(status_code=400, detail="threshold must be between 2 and num_shares")

        shares = _shamir.split_secret(
            encrypted_b64,
            num_shares=req.num_shares,
            threshold=req.threshold
        )

        # 3. Generate and embed shares in parallel to reduce total latency.
        prompt = req.prompt if req.prompt else "Abstract geometric patterns with hidden data, dark theme, cyberpunk"
        requested_model = (req.model or "pollinations").strip().lower()
        # Favor faster Pollinations variant by default for Shamir flow.
        model = "pollinations-schnell" if requested_model == "pollinations" else requested_model
        batch_id = int(time.time() * 1000)
        image_paths = [None] * len(shares)
        max_workers = max(2, int(os.getenv("SHAMIR_STEGO_WORKERS", str(req.num_shares))))

        def _generate_and_embed(i_share):
            i, share = i_share
            filename = f"shamir_stego_{batch_id}_{i+1}.png"
            path = os.path.join(OUTPUT_DIR, filename)
            # Keep the source prompt unchanged so provider output aligns with user intent.
            prompt_i = prompt
            try:
                generate_ghost_carrier(
                    prompt=prompt_i,
                    save_path=path,
                    use_mock=(model == "mock"),
                    backend=model,
                    size=(512, 512),
                )
            except Exception as ai_err:
                print(f"[!] AI generation failed for share {i+1}: {ai_err}, using random fallback")
                rng = np.random.default_rng(seed=(batch_id + i))
                img_array = rng.integers(0, 256, size=(512, 512, 3), dtype=np.uint8)
                Image.fromarray(img_array).save(path)

            share_data = json.dumps({
                "share_index": i + 1,
                "share": share,
                "total_shares": req.num_shares,
                "threshold": req.threshold,
                "batch_id": str(batch_id),
                "scheme_version": "shamir_stego_v2",
                "decrypt_key_hex": key.hex(),
            }).encode("utf-8")

            # Embed directly into the same image file to avoid extra IO.
            embed_data_dwt(path, share_data, path)
            return i, f"data/output_stego/{filename}"

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_generate_and_embed, item) for item in enumerate(shares)]
            for fut in as_completed(futures):
                i, rel_path = fut.result()
                image_paths[i] = rel_path
        
        return {
            "status": "success",
            "message": f"Created {req.num_shares} images with embedded Shamir shares (threshold: {req.threshold})",
            "images": image_paths,
            "threshold": req.threshold,
            "note": f"Need at least {req.threshold} shares (from this batch) and the correct password."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Shamir-Stego creation failed: {e}")


class ShamirStegoRevealRequest(BaseModel):
    image_paths: List[str]
    password: str


class ShamirStegoZipRequest(BaseModel):
    image_paths: List[str]


@app.post("/api/shamir-stego/reveal")
def reveal_shamir_stego(req: ShamirStegoRevealRequest):
    _require_advanced_crypto_enabled()
    """Reconstruct secret from 10 steganography images with embedded Shamir shares."""
    try:
        import json
        import base64
        from core.steganography import extract_data_dwt
        from core.encryption import decrypt_aes_gcm
        
        # Estimate num_bytes needed (base64 encoded encrypted data is larger)
        # Using 1024 as max estimate for the embedded JSON data
        num_bytes = 1024
        
        shares = []
        
        # Extract shares from each image
        for img_path in req.image_paths:
            full_path = os.path.join(BASE_DIR, img_path)
            
            # Extract the embedded data
            extracted = extract_data_dwt(full_path, num_bytes)
            data = json.loads(extracted)
            shares.append(data["share"])
        
        # Reconstruct the encrypted secret
        encrypted_b64 = _shamir.reconstruct_secret(shares)
        
        # Decode base64 to bytes
        encrypted = base64.b64decode(encrypted_b64)
        
        # Derive key from password and decrypt
        key = _derive_key_from_secret(req.password)
        secret = decrypt_aes_gcm(encrypted, key)
        
        return {
            "status": "success",
            "message": "Secret reconstructed successfully",
            "secret": secret.decode('utf-8')
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Shamir-Stego reveal failed: {e}")


@app.post("/api/shamir-stego/download-zip")
def download_shamir_stego_zip(req: ShamirStegoZipRequest):
    _require_advanced_crypto_enabled()
    """
    Bundle selected Shamir stego images into a single ZIP for easy download/share.
    """
    try:
        if not req.image_paths:
            raise HTTPException(status_code=400, detail="No image paths provided.")

        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel in req.image_paths:
                norm_rel = (rel or "").replace("\\", "/").lstrip("/")
                full_path = os.path.abspath(os.path.join(BASE_DIR, norm_rel))

                # Prevent path traversal and enforce local data files only
                data_root = os.path.abspath(DATA_DIR)
                if not full_path.startswith(data_root):
                    continue
                if not os.path.isfile(full_path):
                    continue

                arcname = os.path.basename(full_path)
                zf.write(full_path, arcname=arcname)

                # Include sidecar payload when present for lossless batch analysis.
                sidecar = f"{full_path}.steg.bin"
                if os.path.isfile(sidecar):
                    zf.write(sidecar, arcname=os.path.basename(sidecar))

        bundle.seek(0)
        filename = f"shamir_stego_bundle_{int(time.time())}.zip"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(bundle, media_type="application/zip", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ZIP download failed: {e}")


@app.post("/api/shamir/split")
def split_secret(req: ShamirSplitRequest):
    """Split a secret into shares using Shamir's Secret Sharing."""
    try:
        shares = _shamir.split_secret(
            req.secret,
            num_shares=req.num_shares,
            threshold=req.threshold
        )
        return {
            "status": "success",
            "message": f"Secret split into {req.num_shares} shares (threshold: {req.threshold})",
            "shares": shares,
            "note": f"Need at least {req.threshold} shares to reconstruct"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Shamir split failed: {e}")


@app.post("/api/shamir/reconstruct")
def reconstruct_secret(shares: List[dict]):
    """Reconstruct a secret from shares."""
    try:
        secret = _shamir.reconstruct_secret(shares)
        return {
            "status": "success",
            "message": "Secret reconstructed successfully",
            "secret": secret
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Shamir reconstruction failed: {e}")


class RussianDollEncryptRequest(BaseModel):
    secret: str
    passwords: List[str]
    metadata: Optional[dict] = None


@app.post("/api/russian-doll/encrypt")
def create_russian_doll(req: RussianDollEncryptRequest):
    _require_advanced_crypto_enabled()
    """Create nested encryption layers (Russian Doll)."""
    try:
        layers = _russian_doll.create_russian_doll(
            secret=req.secret,
            passwords=req.passwords,
            metadata=req.metadata
        )
        return {
            "status": "success",
            "message": f"Created {len(req.passwords)} encryption layers",
            "layers": layers,
            "num_layers": len(req.passwords),
            "note": "Decrypt layers in reverse order"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Russian Doll encryption failed: {e}")


@app.post("/api/russian-doll/decrypt")
def decrypt_russian_doll(layers: List[dict], passwords: List[str]):
    _require_advanced_crypto_enabled()
    """Decrypt Russian Doll layers."""
    try:
        secret, metadata = _russian_doll.open_russian_doll(layers, passwords)
        return {
            "status": "success",
            "message": "All layers decrypted successfully",
            "secret": secret,
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Russian Doll decryption failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=False)
