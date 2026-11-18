"""
planner.llm
Provider adapter for LLM calls supporting:
  - Groq & other OpenAI-compatible providers (openai_compat)
  - Google Gemini API (gemini) with automatic JSON mode & usageMetadata token capture
  - Ollama local models (ollama)
  - Deterministic Fake provider for tests (fake)
Automatic fallback: If primary provider experiences rate limit or network failure,
falls back to backup provider if configured.
"""

import os
import time
from typing import Dict, Any, Optional
import requests

def _load_env() -> Dict[str, str]:
    """Basic .env parser without external dependencies."""
    env = dict(os.environ)
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in env:
                        env[k] = v
    return env

_FAKE_RESPONSES = []

def set_fake_responses(responses: list):
    """Set mock responses for fake provider testing."""
    global _FAKE_RESPONSES
    _FAKE_RESPONSES = list(responses)

def _call_openai_compat(base_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str, timeout: float) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "max_tokens": 1200
    }

    t0 = time.time()
    for attempt in range(2):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 429 and attempt == 0:
            time.sleep(5)
            continue
        resp.raise_for_status()
        break
    data = resp.json()
    ms = (time.time() - t0) * 1000

    res_model = data.get("model", model)
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    return {
        "model": res_model,
        "text": text,
        "in": usage.get("prompt_tokens"),
        "out": usage.get("completion_tokens"),
        "total": usage.get("total_tokens"),
        "ms": round(ms, 1)
    }

def _call_gemini(api_key: str, model: str, system_prompt: str, user_prompt: str, timeout: float) -> Dict[str, Any]:
    # Support models like gemini-1.5-flash or gemini-2.0-flash
    model_name = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.0,
            "maxOutputTokens": 700
        }
    }

    t0 = time.time()
    for attempt in range(2):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 429 and attempt == 0:
            time.sleep(5)
            continue
        resp.raise_for_status()
        break
    data = resp.json()
    ms = (time.time() - t0) * 1000

    # Extract text
    candidates = data.get("candidates", [])
    text = "{}"
    if candidates and "content" in candidates[0]:
        parts = candidates[0]["content"].get("parts", [])
        if parts:
            text = parts[0].get("text", "{}")

    # Capture token metadata directly from API
    usage = data.get("usageMetadata", {})
    in_tokens = usage.get("promptTokenCount")
    out_tokens = usage.get("candidatesTokenCount")
    total_tokens = usage.get("totalTokenCount")

    return {
        "model": model,
        "text": text,
        "in": in_tokens,
        "out": out_tokens,
        "total": total_tokens,
        "ms": round(ms, 1)
    }

def _call_ollama(base_url: str, model: str, system_prompt: str, user_prompt: str, timeout: float) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_predict": 700
        }
    }

    t0 = time.time()
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    ms = (time.time() - t0) * 1000

    res_model = data.get("model", model)
    text = data.get("message", {}).get("content", "{}")
    in_tokens = data.get("prompt_eval_count")
    out_tokens = data.get("eval_count")
    total_tokens = (in_tokens + out_tokens) if (in_tokens is not None and out_tokens is not None) else None

    return {
        "model": res_model,
        "text": text,
        "in": in_tokens,
        "out": out_tokens,
        "total": total_tokens,
        "ms": round(ms, 1)
    }

def call(
    area: str,
    system_prompt: str,
    user_prompt: str,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Execute model call with automatic fallback between primary and backup provider.
    """
    env = _load_env()
    provider = env.get("LLM_PROVIDER", "fake").lower()
    model = env.get("LLM_MODEL", "llama-3.1-8b-instant")
    base_url = env.get("LLM_BASE_URL", "")
    api_key = env.get("LLM_API_KEY", "")
    req_timeout = timeout if timeout is not None else 80.0

    # 1. Fake Provider or Queued Mock Responses for Unit Tests
    if _FAKE_RESPONSES:
        item = _FAKE_RESPONSES.pop(0)
        return {
            "model": item.get("model", model),
            "text": item.get("text", "{}"),
            "in": item.get("in", 100),
            "out": item.get("out", 50),
            "total": item.get("total", 150),
            "ms": 10.0
        }

    if provider == "fake":
        return {
            "model": model,
            "text": '{"m":[]}',
            "in": 50,
            "out": 10,
            "total": 60,
            "ms": 10.0
        }

    # Helper execution function
    def _execute(p: str, b: str, k: str, m: str) -> Dict[str, Any]:
        if p == "openai_compat" or p == "groq":
            return _call_openai_compat(b, k, m, system_prompt, user_prompt, req_timeout)
        elif p == "gemini":
            return _call_gemini(k, m, system_prompt, user_prompt, req_timeout)
        elif p == "ollama":
            return _call_ollama(b, m, system_prompt, user_prompt, req_timeout)
        raise ValueError(f"Unsupported LLM provider: {p}")

    # Primary attempt
    try:
        return _execute(provider, base_url, api_key, model)
    except Exception as primary_err:
        # Check if fallback provider is configured (e.g. FALLBACK_PROVIDER=gemini)
        fallback_provider = env.get("FALLBACK_PROVIDER", "").lower()
        if fallback_provider:
            fb_model = env.get("FALLBACK_MODEL", "gemini-1.5-flash")
            fb_base_url = env.get("FALLBACK_BASE_URL", "")
            fb_api_key = env.get("FALLBACK_API_KEY", "")
            try:
                res = _execute(fallback_provider, fb_base_url, fb_api_key, fb_model)
                return res
            except Exception as fb_err:
                raise RuntimeError(
                    f"Both primary ({provider}) and fallback ({fallback_provider}) failed. "
                    f"Primary: {primary_err}; Fallback: {fb_err}"
                )
        raise primary_err
