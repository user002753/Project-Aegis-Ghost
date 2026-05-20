from __future__ import annotations
import json
import os
import time
from typing import Any
import requests


_SESSION = requests.Session()


def _get_env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    if val:
        return val
    try:
        from dotenv import dotenv_values
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        env_path = os.path.join(root, ".env")
        parsed = dotenv_values(env_path)
        v = parsed.get(name)
        if isinstance(v, str) and v:
            return v
    except Exception:
        pass
    return default


def _post_json_with_retries(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 45):
    retries = max(1, int(_get_env("AI_HTTP_RETRIES", "2") or "2"))
    backoff = float(_get_env("AI_HTTP_BACKOFF_SEC", "0.8") or "0.8")
    last_error = None
    for attempt in range(retries):
        try:
            resp = _SESSION.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code in (408, 429, 500, 502, 503, 504) and attempt < retries - 1:
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


def _chat_json(
    url: str,
    headers: dict[str, str],
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1400,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    r = _post_json_with_retries(url=url, headers=headers, payload=payload, timeout=50)
    data = r.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object from model")
    return parsed


def _heuristic_fallback(context: str, max_findings: int) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    ctx = (context or "").lower()
    if "allow_origins" in ctx and "\"*\"" in ctx:
        findings.append({
            "severity": "high",
            "title": "Overly permissive CORS",
            "details": "CORS allow_origins is wildcard; browser clients from any origin can call API.",
            "remediation": "Restrict to trusted frontend origins and disable credentials for wildcard origins.",
        })
    if "api key" in ctx or "sk-" in ctx or "gsk_" in ctx:
        findings.append({
            "severity": "critical",
            "title": "Potential secret exposure risk",
            "details": "API keys/tokens may be present in runtime context or user-visible paths.",
            "remediation": "Rotate keys, move to env vault, and redact secrets in logs/responses.",
        })
    if "allow_credentials=True" in ctx:
        findings.append({
            "severity": "medium",
            "title": "Credentialed cross-origin requests enabled",
            "details": "Credentialed requests can expand attack surface when origin policy is broad.",
            "remediation": "Use strict origin allowlist and CSRF protections.",
        })
    if "upload" in ctx and "image/" in ctx:
        findings.append({
            "severity": "medium",
            "title": "File upload validation hardening needed",
            "details": "Content-type checks alone can be bypassed with crafted files.",
            "remediation": "Verify magic bytes, normalize images, and scan/quarantine uploads.",
        })
    findings = findings[:max_findings]
    return {
        "summary": "Heuristic security assessment generated due to LLM provider unavailability.",
        "findings": findings,
        "overall_risk": "high" if any(f["severity"] == "critical" for f in findings) else "medium",
        "provider": "heuristic",
    }


def analyze_security_vulnerabilities(system_context: str, max_findings: int = 10) -> dict[str, Any]:
    max_findings = max(1, min(25, int(max_findings)))
    system_prompt = (
        "You are a senior application security engineer. "
        "Return strict JSON only with keys: summary, overall_risk, findings. "
        "findings must be an array of objects with keys: severity, title, details, remediation. "
        "severity must be one of critical/high/medium/low."
    )
    user_prompt = (
        f"Analyze this system context for technical and security vulnerabilities. "
        f"Return up to {max_findings} prioritized findings.\n\n{system_context}"
    )

    groq_key = _get_env("GROQ_API_KEY")
    if groq_key:
        try:
            parsed = _chat_json(
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                model=_get_env("GROQ_SECURITY_MODEL", _get_env("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1600,
            )
            parsed["provider"] = "groq"
            return parsed
        except Exception:
            pass

    openrouter_key = _get_env("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            parsed = _chat_json(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": _get_env("OPENROUTER_HTTP_REFERER", "http://localhost"),
                    "X-Title": _get_env("OPENROUTER_X_TITLE", "Project Aegis Ghost"),
                },
                model=_get_env("OPENROUTER_SECURITY_MODEL", _get_env("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini")),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1600,
            )
            parsed["provider"] = "openrouter"
            return parsed
        except Exception:
            pass

    return _heuristic_fallback(system_context, max_findings=max_findings)
