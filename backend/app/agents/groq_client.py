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
    """Raised when all configured AI providers rate limit or fail."""
    pass


# Global circuit breaker timestamp: if rate limited, don't hammer providers
_RATE_LIMITED_UNTIL = 0.0


class GroqClient:
    """Wrapper for multi-provider AI completions with structured JSON output, circuit-breaker, and cascading failover."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        user_api_key: Optional[str] = None,
        user_provider: Optional[str] = None,
        user_keys: Optional[List[Dict[str, str]]] = None,
    ):
        self.user_keys: List[Dict[str, str]] = []
        if user_keys:
            for k in user_keys:
                if isinstance(k, dict) and k.get("api_key") and str(k.get("api_key")).strip():
                    self.user_keys.append({
                        "provider": str(k.get("provider", "groq")).lower().strip(),
                        "api_key": str(k.get("api_key")).strip(),
                    })
        elif user_api_key and user_api_key.strip():
            self.user_keys.append({
                "provider": (user_provider or "groq").lower().strip(),
                "api_key": user_api_key.strip(),
            })

        self.user_api_key = self.user_keys[0]["api_key"] if self.user_keys else None
        self.user_provider = self.user_keys[0]["provider"] if self.user_keys else None

        first_groq_key = next((k["api_key"] for k in self.user_keys if k["provider"] == "groq"), None)
        effective_groq_key = first_groq_key if first_groq_key else (api_key if api_key is not None else settings.GROQ_API_KEY)
        self.api_key = effective_groq_key
        self.model = model or settings.GROQ_MODEL
        self._client: Optional[AsyncGroq] = None
        if self.api_key:
            self._client = AsyncGroq(api_key=self.api_key)

    @property
    def is_configured(self) -> bool:
        """Returns True if ANY supported AI provider has an API key configured or user provided one."""
        return bool(
            len(self.user_keys) > 0
            or self.api_key
            or settings.CEREBRAS_API_KEY
            or settings.GITHUB_MODELS_TOKEN
            or settings.GITHUB_TOKEN
            or settings.SAMBANOVA_API_KEY
            or settings.GEMINI_API_KEY
            or settings.OPENROUTER_API_KEY
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
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> str:
        """
        Sends completion request across configured AI providers in resilient cascade:
        0. User-supplied priority keys (in order of priority across providers)
        1. Groq (Llama / OSS fleet)
        2. Cerebras Cloud (ultra-fast free tier Llama 3.3 70B)
        3. GitHub Models (free GPT-4o-mini / Llama via GITHUB_TOKEN)
        4. SambaNova Cloud (free Llama 3.3 70B)
        5. Google Gemini (Gemini 2.5/2.0 Flash)
        6. OpenRouter (free tier / configured models)
        7. OpenAI
        8. Mistral
        9. Anthropic
        """
        global _RATE_LIMITED_UNTIL
        if time.time() < _RATE_LIMITED_UNTIL:
            raise GroqRateLimitError(
                "Analysis halted: All configured AI providers rate limited. Please retry in a few moments."
            )

        if not self.is_configured:
            raise RuntimeError(
                "No AI provider API key is configured. Please provide at least one of: "
                "GROQ_API_KEY, CEREBRAS_API_KEY, GITHUB_TOKEN (for GitHub Models), SAMBANOVA_API_KEY, "
                "OPENROUTER_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, MISTRAL_API_KEY, ANTHROPIC_API_KEY."
            )

        # 0. Try user-supplied keys in order
        if self.user_keys:
            for idx, user_k in enumerate(self.user_keys):
                u_provider = user_k.get("provider", "groq")
                u_key = user_k.get("api_key", "")
                if not u_key:
                    continue

                try:
                    if u_provider == "groq":
                        logger.info(f"Trying user-provided Groq key (#{idx + 1})...")
                        resp = await self._try_groq_custom_key(
                            u_key,
                            system_prompt,
                            user_prompt,
                            temperature,
                            json_mode,
                            max_tokens,
                            frequency_penalty=frequency_penalty,
                            presence_penalty=presence_penalty,
                        )
                        if resp:
                            return resp
                    elif u_provider == "cerebras":
                        logger.info(f"Trying user-provided Cerebras key (#{idx + 1})...")
                        resp = await self._try_cerebras(
                            system_prompt,
                            user_prompt,
                            temperature,
                            json_mode,
                            max_tokens,
                            custom_key=u_key,
                            frequency_penalty=frequency_penalty,
                            presence_penalty=presence_penalty,
                        )
                        if resp:
                            return resp
                    elif u_provider in ("github_models", "github"):
                        logger.info(f"Trying user-provided GitHub Models token (#{idx + 1})...")
                        resp = await self._try_github_models(
                            system_prompt,
                            user_prompt,
                            temperature,
                            json_mode,
                            max_tokens,
                            custom_key=u_key,
                            frequency_penalty=frequency_penalty,
                            presence_penalty=presence_penalty,
                        )
                        if resp:
                            return resp
                    elif u_provider == "sambanova":
                        logger.info(f"Trying user-provided SambaNova key (#{idx + 1})...")
                        resp = await self._try_sambanova(
                            system_prompt,
                            user_prompt,
                            temperature,
                            json_mode,
                            max_tokens,
                            custom_key=u_key,
                            frequency_penalty=frequency_penalty,
                            presence_penalty=presence_penalty,
                        )
                        if resp:
                            return resp
                    elif u_provider == "gemini":
                        logger.info(f"Trying user-provided Gemini key (#{idx + 1})...")
                        resp = await self._try_gemini(
                            system_prompt, user_prompt, temperature, json_mode, custom_key=u_key
                        )
                        if resp:
                            return resp
                    elif u_provider == "openrouter":
                        logger.info(f"Trying user-provided OpenRouter key (#{idx + 1})...")
                        resp = await self._try_openrouter(
                            system_prompt,
                            user_prompt,
                            temperature,
                            json_mode,
                            max_tokens,
                            custom_key=u_key,
                            frequency_penalty=frequency_penalty,
                            presence_penalty=presence_penalty,
                        )
                        if resp:
                            return resp
                    elif u_provider == "openai":
                        logger.info(f"Trying user-provided OpenAI key (#{idx + 1})...")
                        resp = await self._try_openai(
                            system_prompt,
                            user_prompt,
                            temperature,
                            json_mode,
                            max_tokens,
                            custom_key=u_key,
                            frequency_penalty=frequency_penalty,
                            presence_penalty=presence_penalty,
                        )
                        if resp:
                            return resp
                    elif u_provider == "mistral":
                        logger.info(f"Trying user-provided Mistral key (#{idx + 1})...")
                        resp = await self._try_mistral(
                            system_prompt,
                            user_prompt,
                            temperature,
                            json_mode,
                            max_tokens,
                            custom_key=u_key,
                            frequency_penalty=frequency_penalty,
                            presence_penalty=presence_penalty,
                        )
                        if resp:
                            return resp
                    elif u_provider == "anthropic":
                        logger.info(f"Trying user-provided Anthropic key (#{idx + 1})...")
                        resp = await self._try_anthropic(
                            system_prompt,
                            user_prompt,
                            temperature,
                            json_mode,
                            max_tokens,
                            custom_key=u_key,
                        )
                        if resp:
                            return resp
                except Exception as e:
                    logger.warning(f"User key #{idx + 1} ({u_provider}) failed: {e}. Trying next key...")

        # 1. Try Groq (if configured)
        if self._client:
            models_to_try = [self.model]
            for fb in [
                "openai/gpt-oss-120b",
                "qwen/qwen3.8-27b",
                "openai/gpt-oss-20b",
            ]:
                if fb not in models_to_try:
                    models_to_try.append(fb)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            for candidate_model in models_to_try:
                safe_max_tokens = min(max_tokens or 2000, 3000)
                if "qwen" in candidate_model.lower():
                    safe_max_tokens = min(max_tokens or 800, 800)

                base_kwargs: Dict[str, Any] = {
                    "messages": messages,
                    "temperature": temperature,
                    "model": candidate_model,
                    "max_tokens": safe_max_tokens,
                }
                if frequency_penalty is not None:
                    base_kwargs["frequency_penalty"] = frequency_penalty
                if presence_penalty is not None:
                    base_kwargs["presence_penalty"] = presence_penalty

                modes = [True, False] if json_mode else [False]
                for try_json in modes:
                    kwargs = dict(base_kwargs)
                    if try_json:
                        kwargs["response_format"] = {"type": "json_object"}
                    try:
                        response = await self._client.chat.completions.create(**kwargs)
                        content = response.choices[0].message.content or ""
                        if content.strip():
                            logger.info(f"Successfully received response from Groq model: {candidate_model}")
                            return content.strip()
                    except Exception as e:
                        err_str = str(e)
                        if try_json and ("json_validate_failed" in err_str or "Failed to generate JSON" in err_str):
                            logger.warning(
                                f"Groq model {candidate_model} returned json_validate_failed. Retrying without response_format..."
                            )
                            continue
                        logger.warning(f"Groq model {candidate_model} call failed ({e}). Trying next candidate...")
                        break

        # 2. Try Cerebras Cloud (if configured)
        if settings.CEREBRAS_API_KEY:
            logger.info("Attempting Cerebras Cloud provider...")
            cerebras_resp = await self._try_cerebras(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            if cerebras_resp:
                return cerebras_resp

        # 3. Try GitHub Models (free tier via GITHUB_MODELS_TOKEN or GITHUB_TOKEN)
        if settings.GITHUB_MODELS_TOKEN or settings.GITHUB_TOKEN:
            logger.info("Attempting GitHub Models provider...")
            gh_models_resp = await self._try_github_models(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            if gh_models_resp:
                return gh_models_resp

        # 4. Try SambaNova Cloud (if configured)
        if settings.SAMBANOVA_API_KEY:
            logger.info("Attempting SambaNova Cloud provider...")
            sambanova_resp = await self._try_sambanova(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            if sambanova_resp:
                return sambanova_resp

        # 5. Try Google Gemini (if configured)
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

        # 6. Try OpenRouter (if configured)
        if settings.OPENROUTER_API_KEY:
            logger.info("Attempting OpenRouter provider...")
            openrouter_resp = await self._try_openrouter(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            if openrouter_resp:
                return openrouter_resp

        # 7. Try OpenAI (if configured)
        if settings.OPENAI_API_KEY:
            logger.info("Attempting OpenAI provider...")
            openai_resp = await self._try_openai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            if openai_resp:
                return openai_resp

        # 8. Try Mistral (if configured)
        if settings.MISTRAL_API_KEY:
            logger.info("Attempting Mistral provider...")
            mistral_resp = await self._try_mistral(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            if mistral_resp:
                return mistral_resp

        # 9. Try Anthropic (if configured)
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

    async def _try_openai_compatible_provider(
        self,
        provider_name: str,
        base_url: str,
        api_key: str,
        models: List[str],
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        timeout: float = 25.0,
    ) -> Optional[str]:
        """Generic adapter executing completion requests against any OpenAI-compatible API endpoint."""
        if not api_key:
            return None

        clean_base = base_url.rstrip("/")
        endpoint = f"{clean_base}/chat/completions"

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        seen = set()
        for model in models:
            if not model or model in seen:
                continue
            seen.add(model)

            base_payload: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            if max_tokens:
                base_payload["max_tokens"] = min(max_tokens, 3000)
            if frequency_penalty is not None:
                base_payload["frequency_penalty"] = frequency_penalty
            if presence_penalty is not None:
                base_payload["presence_penalty"] = presence_penalty

            modes = [True, False] if json_mode else [False]
            for try_json in modes:
                payload = dict(base_payload)
                if try_json:
                    payload["response_format"] = {"type": "json_object"}

                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp = await client.post(endpoint, headers=headers, json=payload)

                        if resp.status_code == 200:
                            data = resp.json()
                            choices = data.get("choices", [])
                            if choices:
                                content = choices[0].get("message", {}).get("content")
                                if content and content.strip():
                                    logger.info(
                                        f"Successfully received response from {provider_name} model: {model}"
                                    )
                                    return content.strip()
                        elif resp.status_code == 400 and try_json:
                            # Many providers reject response_format with 400; retry without it
                            err_text = resp.text.lower()
                            if any(k in err_text for k in ["response_format", "json_object", "unsupported", "invalid"]):
                                logger.warning(
                                    f"{provider_name} {model} returned 400 on response_format. Retrying without it..."
                                )
                                continue
                            logger.warning(f"{provider_name} {model} returned 400: {resp.text[:160]}")
                            break
                        elif resp.status_code == 429:
                            logger.warning(f"{provider_name} {model} rate limited (HTTP 429). Trying next candidate...")
                            break
                        else:
                            logger.warning(
                                f"{provider_name} {model} returned status {resp.status_code}: {resp.text[:160]}"
                            )
                            break
                except httpx.TimeoutException:
                    logger.warning(f"{provider_name} {model} request timed out after {timeout}s.")
                    break
                except Exception as e:
                    logger.warning(f"{provider_name} {model} request failed: {e}")
                    break

        return None

    async def _try_cerebras(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        custom_key: Optional[str] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Optional[str]:
        """Cerebras Cloud inference (~2,000 tok/sec free tier)."""
        effective_key = custom_key or settings.CEREBRAS_API_KEY
        if not effective_key:
            return None

        models = [
            settings.CEREBRAS_MODEL or "llama-3.3-70b",
            "llama-3.3-70b",
            "llama3.1-70b",
            "llama3.1-8b",
        ]
        return await self._try_openai_compatible_provider(
            provider_name="Cerebras",
            base_url="https://api.cerebras.ai/v1",
            api_key=effective_key,
            models=models,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            timeout=20.0,
        )

    async def _try_github_models(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        custom_key: Optional[str] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Optional[str]:
        """GitHub Models inference (free tier using GITHUB_MODELS_TOKEN or standard GITHUB_TOKEN)."""
        effective_key = custom_key or settings.GITHUB_MODELS_TOKEN or settings.GITHUB_TOKEN
        if not effective_key:
            return None

        models = [
            settings.GITHUB_MODELS_MODEL or "gpt-4o-mini",
            "gpt-4o-mini",
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-70b-instruct",
            "gpt-4o",
        ]
        return await self._try_openai_compatible_provider(
            provider_name="GitHub Models",
            base_url="https://models.inference.ai.azure.com",
            api_key=effective_key,
            models=models,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            timeout=25.0,
        )

    async def _try_sambanova(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        custom_key: Optional[str] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Optional[str]:
        """SambaNova Cloud inference (high-speed free tier Llama 3.3 70B)."""
        effective_key = custom_key or settings.SAMBANOVA_API_KEY
        if not effective_key:
            return None

        models = [
            settings.SAMBANOVA_MODEL or "Meta-Llama-3.3-70B-Instruct",
            "Meta-Llama-3.3-70B-Instruct",
            "Meta-Llama-3.1-70B-Instruct",
            "Meta-Llama-3.1-8B-Instruct",
        ]
        return await self._try_openai_compatible_provider(
            provider_name="SambaNova",
            base_url="https://api.sambanova.ai/v1",
            api_key=effective_key,
            models=models,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            timeout=20.0,
        )

    async def _try_openrouter(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        custom_key: Optional[str] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Optional[str]:
        """Fallback to OpenRouter models."""
        effective_key = custom_key or settings.OPENROUTER_API_KEY
        if not effective_key:
            return None

        models = [
            settings.OPENROUTER_MODEL or "openrouter/auto",
            "openrouter/auto",
            "google/gemma-4-31b-it:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3.5-lightning:free",
            "google/gemma-4-26b-a4b-it:free",
            "liquid/lfm-2.5-2.6b:free",
        ]
        return await self._try_openai_compatible_provider(
            provider_name="OpenRouter",
            base_url="https://openrouter.ai/api/v1",
            api_key=effective_key,
            models=models,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
            extra_headers={
                "HTTP-Referer": "https://doyoularp.com",
                "X-Title": "doyoularp",
            },
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            timeout=25.0,
        )

    async def _try_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        custom_key: Optional[str] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Optional[str]:
        """Fallback to OpenAI models."""
        effective_key = custom_key or settings.OPENAI_API_KEY
        if not effective_key:
            return None

        models = [settings.OPENAI_MODEL or "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        return await self._try_openai_compatible_provider(
            provider_name="OpenAI",
            base_url="https://api.openai.com/v1",
            api_key=effective_key,
            models=models,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            timeout=20.0,
        )

    async def _try_mistral(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        custom_key: Optional[str] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Optional[str]:
        """Fallback to Mistral models."""
        effective_key = custom_key or settings.MISTRAL_API_KEY
        if not effective_key:
            return None

        models = [settings.MISTRAL_MODEL or "mistral-small-latest", "open-mistral-7b"]
        return await self._try_openai_compatible_provider(
            provider_name="Mistral",
            base_url="https://api.mistral.ai/v1",
            api_key=effective_key,
            models=models,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            timeout=20.0,
        )

    async def _try_groq_custom_key(
        self,
        custom_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> Optional[str]:
        """Try Groq models using user-supplied custom key."""
        try:
            client = AsyncGroq(api_key=custom_key)
            models_to_try = [
                self.model,
                "openai/gpt-oss-20b",
                "groq/compound-mini",
                "openai/gpt-oss-120b",
                "groq/compound",
            ]
            seen = set()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            for candidate_model in models_to_try:
                if candidate_model in seen:
                    continue
                seen.add(candidate_model)

                base_kwargs: Dict[str, Any] = {
                    "messages": messages,
                    "temperature": temperature,
                    "model": candidate_model,
                    "max_tokens": min(max_tokens or 2000, 3000),
                }
                if frequency_penalty is not None:
                    base_kwargs["frequency_penalty"] = frequency_penalty
                if presence_penalty is not None:
                    base_kwargs["presence_penalty"] = presence_penalty

                modes = [True, False] if json_mode else [False]
                for try_json in modes:
                    kwargs = dict(base_kwargs)
                    if try_json:
                        kwargs["response_format"] = {"type": "json_object"}
                    try:
                        response = await client.chat.completions.create(**kwargs)
                        content = response.choices[0].message.content
                        if content and content.strip():
                            logger.info(f"Successfully received response from user Groq key with {candidate_model}")
                            return content.strip()
                    except Exception as e:
                        err_str = str(e)
                        if try_json and ("json_validate_failed" in err_str or "Failed to generate JSON" in err_str):
                            logger.warning(
                                f"User Groq key on {candidate_model} returned json_validate_failed. Retrying without response_format..."
                            )
                            continue
                        logger.warning(f"User Groq key on {candidate_model} failed: {e}")
                        break
        except Exception as e:
            logger.warning(f"Failed to initialize AsyncGroq with user custom key: {e}")
        return None

    async def _try_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        custom_key: Optional[str] = None,
    ) -> Optional[str]:
        """Fallback to Gemini Generative Language models."""
        effective_key = custom_key or settings.GEMINI_API_KEY
        if not effective_key:
            return None

        models = [
            settings.GEMINI_MODEL or "gemini-3.6-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-2.5-flash",
            "gemini-flash-latest",
        ]

        seen = set()
        for model in models:
            if model in seen:
                continue
            seen.add(model)

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={effective_key}"
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
                            if parts:
                                for part in reversed(parts):
                                    if isinstance(part, dict) and "text" in part and part["text"].strip():
                                        logger.info(f"Successfully received response from Gemini model: {model}")
                                        return part["text"].strip()
                    else:
                        logger.warning(f"Gemini {model} returned status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"Gemini {model} request failed: {e}")
        return None

    async def _try_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int],
        custom_key: Optional[str] = None,
    ) -> Optional[str]:
        """Fallback to Anthropic models."""
        effective_key = custom_key or settings.ANTHROPIC_API_KEY
        if not effective_key:
            return None

        models = [settings.ANTHROPIC_MODEL or "claude-3-5-haiku-20241022", "claude-3-haiku-20240307"]
        headers = {
            "x-api-key": effective_key,
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
        code_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if code_match:
            text = code_match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            obj_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
            if obj_match:
                try:
                    return json.loads(obj_match.group(1))
                except Exception:
                    pass

            for suffix in [']}', '}', '"]}', '"]}']:
                try:
                    return json.loads(text + suffix)
                except Exception:
                    pass

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
