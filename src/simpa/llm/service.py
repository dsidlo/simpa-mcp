"""LLM service for prompt refinement with caching."""

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from simpa.config import settings
from simpa.llm.cache import LLMResponseCache

logger = structlog.get_logger()


class LLMService:
    """Service for LLM interactions with response caching."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self._client = None
        self._cache = LLMResponseCache()

    async def _get_client(self):
        """Lazy load the appropriate client."""
        if self._client is None:
            if self.provider == "openai":
                from openai import AsyncOpenAI

                if not settings.openai_api_key:
                    raise ValueError("OpenAI API key not configured")
                self._client = AsyncOpenAI(api_key=settings.openai_api_key)

            elif self.provider == "anthropic":
                import anthropic

                if not settings.anthropic_api_key:
                    raise ValueError("Anthropic API key not configured")
                self._client = anthropic.AsyncAnthropic(
                    api_key=settings.anthropic_api_key
                )

            elif self.provider == "ollama":
                import httpx

                self._client = httpx.AsyncClient(base_url=settings.ollama_base_url)

        return self._client

    @retry(
        retry=retry_if_exception_type(RuntimeError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a completion from the LLM with caching.

        Args:
            system_prompt: System context/instructions
            user_prompt: User prompt to refine

        Returns:
            Generated text response
        """
        # Check cache first
        cached_response = self._cache.get(system_prompt, user_prompt)
        if cached_response is not None:
            logger.info("llm_cache_hit")
            return cached_response

        # Make actual LLM call
        client = await self._get_client()
        response = None

        if self.provider == "openai":
            result = await client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            response = result.choices[0].message.content or ""

        elif self.provider == "anthropic":
            result = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            response = result.content[0].text if result.content else ""

        elif self.provider == "ollama":
            result = await client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                    },
                },
            )
            result.raise_for_status()
            data = result.json()
            response = data["message"]["content"]

        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

        # Cache the response
        self._cache.set(system_prompt, user_prompt, response)
        logger.info("llm_call_completed", cached=False)

        return response

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self._cache.get_stats()

    def clear_cache(self) -> int:
        """Clear all cached entries."""
        return self._cache.clear_all()

    async def close(self) -> None:
        """Close the client connection."""
        self._cache.close()
        if self._client and self.provider == "ollama":
            await self._client.aclose()
