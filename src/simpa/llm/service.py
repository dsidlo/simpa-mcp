"""LLM service for prompt refinement with caching using LiteLLM."""

import litellm
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from simpa.config import settings
from simpa.llm.cache import LLMResponseCache
from simpa.utils.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Service for LLM interactions with response caching using LiteLLM."""

    def __init__(self) -> None:
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self._cache = LLMResponseCache()

        # Configure LiteLLM logging
        litellm.set_verbose = False
        
        logger.info(
            "llm_service_initialized",
            model=self.model,
            temperature=self.temperature,
            cache_enabled=True,
        )

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
        logger.debug(
            "llm_completion_request",
            model=self.model,
            system_length=len(system_prompt),
            user_length=len(user_prompt),
        )
        
        # Check cache first
        cached_response = self._cache.get(system_prompt, user_prompt)
        if cached_response is not None:
            logger.info("llm_cache_hit", model=self.model, response_length=len(cached_response))
            return cached_response

        logger.debug("llm_cache_miss", model=self.model)

        # Make actual LLM call using LiteLLM
        try:
            logger.debug("llm_api_call_start", model=self.model)
            
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
            
            logger.debug(
                "llm_api_call_success",
                model=self.model,
                response_length=len(content),
                prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                completion_tokens=response.usage.completion_tokens if response.usage else None,
            )

        except Exception as e:
            logger.error(
                "llm_api_call_failed",
                error=str(e),
                model=self.model,
                exc_info=True,
            )
            raise RuntimeError(f"LLM call failed: {e}") from e

        # Cache the response
        self._cache.set(system_prompt, user_prompt, content)
        logger.info(
            "llm_completion_success",
            cached=False,
            model=self.model,
            response_length=len(content),
        )

        return content

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        stats = self._cache.get_stats()
        logger.info("llm_cache_stats", **stats)
        return stats

    def clear_cache(self) -> int:
        """Clear all cached entries."""
        count = self._cache.clear_all()
        logger.info("llm_cache_cleared", entries_removed=count)
        return count

    def close(self) -> None:
        """Close the service and cleanup resources."""
        logger.info("llm_service_closing")
        count = self._cache.clear_all()
        logger.info("llm_service_closed", cache_entries_cleared=count)
