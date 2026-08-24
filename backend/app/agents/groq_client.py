import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import httpx
from groq import AsyncGroq
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class GroqRateLimitError(Exception):
    """Raised when Groq API rate limits (HTTP 429, TPM, TPD) are reached."""
    pass


# Global circuit breaker timestamp: if rate limited, don't hammer Groq
_RATE_LIMITED_UNTIL = 0.0


class GroqClient:
    """Wrapper for Groq API with structured JSON output, circuit-breaker, and fallback support."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self._client: Optional[AsyncGroq] = None
        if self.api_key:
            self._client = AsyncGroq(api_key=self.api_key)

    @property
    def is_configured(self) -> bool:
        return bool(self._client)

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Sends a completion request to Groq with rate-limit circuit breaker."""
        global _RATE_LIMITED_UNTIL
        if time.time() < _RATE_LIMITED_UNTIL:
            raise GroqRateLimitError(
                "Analysis halted: LLM provider rate limit reached (Groq 429). Please wait a few minutes before retrying."
            )

        if not self._client:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            if not max_tokens:
                max_tokens = 3000

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        # Candidate model cascade: try primary model, then high-capacity fallback models before failing
        models_to_try = [self.model]
        for fb in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
            if fb not in models_to_try:
                models_to_try.append(fb)

        last_err = None
        for candidate_model in models_to_try:
            kwargs["model"] = candidate_model
            try:
                response = await self._client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as e:
                err_str = str(e).lower()
                last_err = e
                if (
                    "rate limit" in err_str
                    or "429" in err_str
                    or "try again in" in err_str
                    or "rate_limit" in err_str
                    or "tpm" in err_str
                    or "tpd" in err_str
                    or "tokens per minute" in err_str
                    or "tokens per day" in err_str
                ):
                    logger.warning(f"Groq model {candidate_model} rate limited: {e}. Trying next candidate model...")
                    continue
                logger.error(f"Groq API call error on {candidate_model}: {e}")
                raise

        # All Groq models in cascade were rate limited or failed: try OpenRouter
        logger.warning("All Groq candidate models rate limited. Attempting OpenRouter fallback...")
        openrouter_resp = await self._try_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )
        if openrouter_resp:
            return openrouter_resp

        # OpenRouter unavailable or failed: try Gemini fallback
        logger.warning("OpenRouter fallback unavailable or rate limited. Attempting Gemini fallback...")
        gemini_resp = await self._try_gemini(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=json_mode,
        )
        if gemini_resp:
            return gemini_resp

        # All providers (Groq, OpenRouter, Gemini) exhausted or rate limited
        _RATE_LIMITED_UNTIL = time.time() + 60.0
        logger.warning("All LLM providers (Groq, OpenRouter, Gemini) rate limited or unavailable.")
        raise GroqRateLimitError(
            "Analysis halted: LLM provider rate limit reached across all providers. Please wait a few minutes before retrying."
        ) from last_err

    async def _try_openrouter(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
    ) -> Optional[str]:
        """Fallback to OpenRouter free models."""
        if not settings.OPENROUTER_API_KEY:
            return None

        models = [
            settings.OPENROUTER_MODEL or "nvidia/nemotron-3.5-lightning:free",
            "nex-agi/nex-n2.5-mini:free",
            "liquid/lfm-2.5-2.6b:free",
        ]
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        for model in models:
            payload: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            if max_tokens:
                payload["max_tokens"] = max_tokens

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content")
                            if content:
                                logger.info(f"Successfully received response from OpenRouter model: {model}")
                                return content
                    else:
                        logger.warning(f"OpenRouter {model} returned status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"OpenRouter {model} request failed: {e}")
        return None

    async def _try_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
    ) -> Optional[str]:
        """Fallback to Gemini Generative Language models."""
        if not settings.GEMINI_API_KEY:
            return None

        models = [
            settings.GEMINI_MODEL or "gemini-flash-latest",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
        ]

        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
            gen_config: Dict[str, Any] = {"temperature": temperature}
            if json_mode:
                gen_config["responseMimeType"] = "application/json"

            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": gen_config,
            }

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                logger.info(f"Successfully received response from Gemini model: {model}")
                                return parts[0]["text"]
                    else:
                        logger.warning(f"Gemini {model} returned status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"Gemini {model} request failed: {e}")
        return None

    def extract_json(self, text: Optional[str]) -> Dict[str, Any]:
        """Safely parses JSON from LLM output, extracting from markdown blocks or recovering truncated arrays."""
        if not text or not isinstance(text, str):
            return {}

        text = text.strip()
        # Look for markdown json code block
        code_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if code_match:
            text = code_match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find { ... } or [ ... ]
            obj_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
            if obj_match:
                try:
                    return json.loads(obj_match.group(1))
                except Exception:
                    pass

            # Try auto-closing open structures
            for suffix in [']}', '}', '"]}', '"]}']:
                try:
                    return json.loads(text + suffix)
                except Exception:
                    pass

            # Recover completed claims objects from truncated JSON array
            claims = []
            matches = re.finditer(r'\{[^{}]*"claim_text"\s*:\s*"([^"]+)"[^{}]*\}', text)
            for m in matches:
                try:
                    obj = json.loads(m.group(0))
                    claims.append(obj)
                except Exception:
                    pass
            if claims:
                return {"claims": claims}

            # Recover completed evaluations objects from truncated JSON array
            evals = []
            matches_eval = re.finditer(r'\{[^{}]*"claim_id"\s*:\s*"?[^"]+"?[^{}]*\}', text)
            for m in matches_eval:
                try:
                    obj = json.loads(m.group(0))
                    evals.append(obj)
                except Exception:
                    pass
            if evals:
                return {"evaluations": evals}

            return {}
