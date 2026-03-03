"""LLM service for prompt refinement with caching using LiteLLM."""

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

import litellm
from simpa.config import settings
from simpa.llm.cache import LLMResponseCache

logger = structlog.get_logger()


class LLMService:
    """Service for LLM interactions with response caching using LiteLLM."""

    def __init__(self) -> None:
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self._cache = LLMResponseCache()

        # Configure LiteLLM logging
        litellm.set_verbose = False

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

        # Make actual LLM call using LiteLLM
        try:
            response = await litellm.acompletion(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            # Extract content from LiteLLM response
            content = response.choices[0].message.content or ""

        except Exception as e:
            logger.error("llm_call_failed", error=str(e))
            raise RuntimeError(f"LLM call failed: {e}") from e

        # Cache the response
        self._cache.set(system_prompt, user_prompt, content)
        logger.info("llm_call_completed", cached=False, model=self.model)

        return content

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self._cache.get_stats()

    def clear_cache(self) -> int:
        """Clear all cached entries."""
        return self._cache.clear_all()

    def close(self) -> None:
        """Close the service and cleanup resources."""
        self._cache.clear_all()
        self._cache.close()
