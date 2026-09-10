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
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self._client: Optional[AsyncGroq] = None
        if self.api_key:
            self._client = AsyncGroq(api_key=self.api_key)

    @property
    def is_configured(self) -> bool:
        """Returns True if ANY supported AI provider has an API key configured."""
        return bool(
            self.api_key
            or settings.OPENROUTER_API_KEY
            or settings.GEMINI_API_KEY
            or settings.OPENAI_API_KEY
            or settings.MISTRAL_API_KEY
            or settings.ANTHROPIC_API_KEY
        )

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Sends completion request across configured AI providers in resilient cascade:
        1. Groq (with model cascade & safe OTPM token limits)
        2. OpenRouter (free tier / configured models)
        3. Google Gemini
        4. OpenAI
        5. Mistral
        6. Anthropic
        """
        global _RATE_LIMITED_UNTIL
        if time.time() < _RATE_LIMITED_UNTIL:
            raise GroqRateLimitError(
                "Analysis halted: All configured AI providers rate limited. Please retry in a few moments."
            )

        if not self.is_configured:
            raise RuntimeError(
                "No AI provider API key is configured. Please provide at least one of: "
                "GROQ_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, MISTRAL_API_KEY, ANTHROPIC_API_KEY."
            )

        # 1. Try Groq (if configured)
        if self._client:
            models_to_try = [self.model]
            for fb in [
                "openai/gpt-oss-20b",
                "groq/compound-mini",
                "openai/gpt-oss-120b",
                "groq/compound",
                "qwen/qwen3.6-27b",
                "qwen/qwen3.8-27b",
            ]:
                if fb not in models_to_try:
                    models_to_try.append(fb)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            for candidate_model in models_to_try:
                base_kwargs: Dict[str, Any] = {
                    "messages": messages,
                    "temperature": temperature,
                    "model": candidate_model,
                }

                # Enforce safe output token limits per model tier
                if "qwen/qwen3.8-27b" in candidate_model.lower():
                    base_kwargs["max_tokens"] = min(max_tokens or 750, 850)
                else:
                    base_kwargs["max_tokens"] = min(max_tokens or 1500, 2500)

                # If json_mode requested, attempt with response_format first, but if Groq's
                # schema validator rejects with json_validate_failed (400), retry without response_format
                # so our robust Python extract_json parser can extract the JSON payload.
                modes = [True, False] if json_mode else [False]
                success = False
                for try_json in modes:
                    kwargs = dict(base_kwargs)
                    if try_json:
                        kwargs["response_format"] = {"type": "json_object"}
                    try:
                        response = await self._client.chat.completions.create(**kwargs)
                        content = response.choices[0].message.content or ""
                        if content.strip():
                            return content
                    except Exception as e:
                        err_str = str(e)
                        if try_json and ("json_validate_failed" in err_str or "Failed to generate JSON" in err_str):
                            logger.warning(
                                f"Groq model {candidate_model} returned json_validate_failed. Retrying without response_format..."
                            )
                            continue
                        logger.warning(f"Groq model {candidate_model} call failed ({e}). Trying next candidate...")
                        break

        # 2. Try OpenRouter (if configured)
        if settings.OPENROUTER_API_KEY:
            logger.info("Attempting OpenRouter provider...")
            openrouter_resp = await self._try_openrouter(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
            if openrouter_resp:
                return openrouter_resp

        # 3. Try Gemini (if configured)
        if settings.GEMINI_API_KEY:
            logger.info("Attempting Gemini provider...")
            gemini_resp = await self._try_gemini(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
            )
            if gemini_resp:
                return gemini_resp

        # 4. Try OpenAI (if configured)
        if settings.OPENAI_API_KEY:
            logger.info("Attempting OpenAI provider...")
            openai_resp = await self._try_openai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
            if openai_resp:
                return openai_resp

        # 5. Try Mistral (if configured)
        if settings.MISTRAL_API_KEY:
            logger.info("Attempting Mistral provider...")
            mistral_resp = await self._try_mistral(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
            if mistral_resp:
                return mistral_resp

        # 6. Try Anthropic (if configured)
        if settings.ANTHROPIC_API_KEY:
            logger.info("Attempting Anthropic provider...")
            anthropic_resp = await self._try_anthropic(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
            if anthropic_resp:
                return anthropic_resp

        # All configured providers exhausted or unavailable
        _RATE_LIMITED_UNTIL = time.time() + 30.0
        logger.warning("All configured LLM providers rate limited or unavailable.")
        raise GroqRateLimitError(
            "Analysis halted: All configured AI providers rate limited or unavailable. Please retry in a few moments."
        )

    async def _try_openrouter(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
    ) -> Optional[str]:
        """Fallback to OpenRouter models."""
        if not settings.OPENROUTER_API_KEY:
            return None

        models = [
            settings.OPENROUTER_MODEL or "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "qwen/qwen-2.5-coder-32b-instruct:free",
            "nvidia/nemotron-3.5-lightning:free",
        ]
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://doyoularp.com",
            "X-Title": "doyoularp",
        }

        seen = set()
        for model in models:
            if model in seen:
                continue
            seen.add(model)

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
                payload["max_tokens"] = min(max_tokens, 2500)

            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
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
            settings.GEMINI_MODEL or "gemini-2.0-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro",
        ]

        seen = set()
        for model in models:
            if model in seen:
                continue
            seen.add(model)

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
                async with httpx.AsyncClient(timeout=20.0) as client:
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

    async def _try_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
    ) -> Optional[str]:
        """Fallback to OpenAI models."""
        if not settings.OPENAI_API_KEY:
            return None

        models = [settings.OPENAI_MODEL or "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        seen = set()
        for model in models:
            if model in seen:
                continue
            seen.add(model)

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
                payload["max_tokens"] = min(max_tokens, 2500)

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content")
                            if content:
                                logger.info(f"Successfully received response from OpenAI model: {model}")
                                return content
                    else:
                        logger.warning(f"OpenAI {model} returned status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"OpenAI {model} request failed: {e}")
        return None

    async def _try_mistral(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
    ) -> Optional[str]:
        """Fallback to Mistral models."""
        if not settings.MISTRAL_API_KEY:
            return None

        models = [settings.MISTRAL_MODEL or "mistral-small-latest", "open-mistral-7b"]
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }
        seen = set()
        for model in models:
            if model in seen:
                continue
            seen.add(model)

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
                payload["max_tokens"] = min(max_tokens, 2000)

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content")
                            if content:
                                logger.info(f"Successfully received response from Mistral model: {model}")
                                return content
                    else:
                        logger.warning(f"Mistral {model} returned status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"Mistral {model} request failed: {e}")
        return None

    async def _try_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
    ) -> Optional[str]:
        """Fallback to Anthropic models."""
        if not settings.ANTHROPIC_API_KEY:
            return None

        models = [settings.ANTHROPIC_MODEL or "claude-3-5-haiku-20241022", "claude-3-haiku-20240307"]
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        seen = set()
        for model in models:
            if model in seen:
                continue
            seen.add(model)

            payload: Dict[str, Any] = {
                "model": model,
                "system": system_prompt + ("\nRespond strictly with a valid JSON object." if json_mode else ""),
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": temperature,
                "max_tokens": min(max_tokens or 1500, 3000),
            }
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content_list = data.get("content", [])
                        if content_list and content_list[0].get("text"):
                            logger.info(f"Successfully received response from Anthropic model: {model}")
                            return content_list[0]["text"]
                    else:
                        logger.warning(f"Anthropic {model} returned status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"Anthropic {model} request failed: {e}")
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
