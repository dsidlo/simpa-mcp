"""Prompt selector using sigmoid-based refinement probability."""

import math
import random
import structlog

from simpa.config import settings
from simpa.db.models import RefinedPrompt

logger = structlog.get_logger()


class PromptSelector:
    """Select prompts using sigmoid-based refinement probability."""

    def __init__(self) -> None:
        self.k = settings.sigmoid_k
        self.mu = settings.sigmoid_mu
        self.min_probability = settings.min_refinement_probability

    def calculate_refinement_probability(self, score: float) -> float:
        """Calculate probability of refinement based on score.

        Uses a sigmoid function: p = 1 / (1 + exp(k * (score - mu)))
        where lower scores result in higher refinement probability.

        Args:
            score: Average score between 1.0 and 5.0

        Returns:
            Probability between 0 and 1
        """
        # Sigmoid curve: p = 1 / (1 + exp(k * (S - mu)))
        probability = 1.0 / (1.0 + math.exp(self.k * (score - self.mu)))

        # Apply floor to ensure minimum exploration
        return max(probability, self.min_probability)

    def should_create_new_prompt(self, prompt: RefinedPrompt | None) -> bool:
        """Determine whether to create a new refined prompt.

        Args:
            prompt: The best existing prompt found (or None if no match)

        Returns:
            True if a new prompt should be created, False to reuse existing
        """
        if prompt is None:
            # No existing prompt found, must create new
            logger.debug("no_existing_prompt", decision="create_new", reason="no_match")
            return True

        # Calculate refinement probability based on prompt's average score
        score = prompt.average_score if prompt.usage_count > 0 else 2.5  # Default to neutral
        probability = self.calculate_refinement_probability(score)

        # Random decision based on probability
        should_refine = random.random() < probability

        logger.debug(
            "refinement_decision",
            prompt_id=str(prompt.id),
            score=score,
            probability=probability,
            should_refine=should_refine,
        )

        return should_refine

    def select_best_prompt(
        self,
        prompts: list[RefinedPrompt],
    ) -> RefinedPrompt | None:
        """Select the best prompt from a list of candidates.

        Selection criteria:
        1. Highest average score (for prompts with usage)
        2. If no usage, use vector similarity (already ordered by similarity)

        Args:
            prompts: List of candidate prompts

        Returns:
            Best prompt or None if list is empty
        """
        if not prompts:
            return None

        # Separate prompts with usage from new ones
        with_usage = [p for p in prompts if p.usage_count > 0]
        new_prompts = [p for p in prompts if p.usage_count == 0]

        if with_usage:
            # Sort by average score descending, then by usage count
            best = sorted(
                with_usage,
                key=lambda p: (p.average_score, p.usage_count),
                reverse=True,
            )[0]
            logger.debug(
                "selected_prompt_with_usage",
                prompt_id=str(best.id),
                score=best.average_score,
                usage=best.usage_count,
            )
            return best

        if new_prompts:
            # Return the first one (highest vector similarity)
            best = new_prompts[0]
            logger.debug(
                "selected_new_prompt",
                prompt_id=str(best.id),
                reason="no_usage_history",
            )
            return best

        return None


# Example probabilities for documentation
EXAMPLE_PROBABILITIES = {
    1.0: 0.953,
    1.5: 0.905,
    2.0: 0.818,
    2.5: 0.679,
    3.0: 0.500,
    3.5: 0.321,
    4.0: 0.182,
    4.5: 0.095,
    5.0: 0.047,
}
