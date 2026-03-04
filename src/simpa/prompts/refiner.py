"""Prompt refinement engine for SIMPA with optimization support."""

import difflib
import hashlib
import structlog
import uuid
from typing import TYPE_CHECKING

from simpa.config import settings
from simpa.db.models import RefinedPrompt
from simpa.embedding.service import EmbeddingService
from simpa.llm.service import LLMService
from simpa.prompts.selector import PromptSelector

if TYPE_CHECKING:
    from simpa.db.repository import RefinedPromptRepository

logger = structlog.get_logger()


REFINEMENT_SYSTEM_PROMPT = """You are an expert prompt engineer specializing in refining prompts for AI agents.

CRITICAL RULE - CONTEXTUAL TAILORING:
If the original request has a SPECIFIC TARGET (e.g., "DT-Worker" vs "DT-Manager", "frontend" vs "backend", "React" vs "Vue"), you MUST create a prompt that is TAILORED for that SPECIFIC TARGET. Do NOT return a generic template with a note to "adapt" or "change" it. Make the prompt immediately usable for the specific target.

Examples of proper contextual tailoring:
- WRONG: Generic script + note saying "change DT-Manager to DT-Worker where appropriate"
- RIGHT: Script explicitly using DT-Worker roles, DT-Worker context, DT-Worker examples

Your task is to analyze the provided agent request and either:
1. Select the most appropriate existing refined prompt if it's EXACTLY appropriate for the context
2. Create a NEW refined prompt that is TAILORED to the SPECIFIC context

Guidelines for refinement:
- Make the prompt specific and immediately usable (no adaptation needed)
- Replace generic references with the SPECIFIC target mentioned in the request
- Include examples relevant to the SPECIFIC target context
- Structure the prompt with clear sections (context, task, constraints, output format)
- Ensure the prompt guides the agent to complete the task in one shot
- Add relevant examples and templates for the SPECIFIC target
- Add comments explaining key decisions

Respond in the following format:

REFINED_PROMPT:
[The refined prompt text - tailored for the specific target]

REASONING:
[Your reasoning for the refinement - explain how you tailored it for the specific context]
"""


class PromptRefiner:
    """Engine for refining prompts with optimization features."""

    def __init__(
        self,
        repository: "RefinedPromptRepository",
        embedding_service: EmbeddingService,
        llm_service: LLMService,
    ):
        self.repository = repository
        self.embedding = embedding_service
        self.llm = llm_service
        self.selector = PromptSelector()
        self._llm_context_cache: str | None = None

    async def _check_hash_fast_path(
        self,
        original_hash: str | None,
        agent_type: str,
    ) -> dict | None:
        """Check for exact hash match with high score.
        
        Args:
            original_hash: Hash of original prompt
            agent_type: Agent type filter
            
        Returns:
            Result dict if fast path applies, None otherwise
        """
        if not settings.hash_fast_path_enabled or not original_hash:
            return None
        
        # Look up by hash with minimum score
        cached = await self.repository.get_best_by_hash(
            original_hash=original_hash,
            agent_type=agent_type,
            min_score=settings.hash_fast_path_min_score,
        )
        
        if cached:
            logger.info(
                "hash_fast_path_hit",
                prompt_id=str(cached.prompt_key),
                score=cached.average_score,
            )
            return {
                "action": "fast_path",
                "prompt_key": str(cached.prompt_key),
                "refined_prompt": cached.refined_prompt,
                "source": "reused",
                "similar_prompts_found": 1,
                "average_score": cached.average_score,
                "usage_count": cached.usage_count,
                "confidence_score": cached.average_score / 5.0,
                "fast_path": "hash",
            }
        
        return None

    def _check_similarity_bypass(
        self,
        similar_prompts: list[RefinedPrompt],
        threshold: float = 0.95,
    ) -> RefinedPrompt | None:
        """Check if we can bypass LLM due to very high similarity.
        
        Args:
            similar_prompts: List of similar prompts
            threshold: Cosine similarity threshold
            
        Returns:
            Best prompt if bypass applies, None otherwise
        """
        if not similar_prompts:
            return None
        
        # Get the first (most similar) that meets the threshold
        best = similar_prompts[0]
        
        # Check if best is very similar and has high score
        if (best.average_score >= settings.similarity_bypass_min_score and 
            best.usage_count > 0):
            # Very high quality match, bypass LLM
            logger.info(
                "similarity_bypass",
                prompt_id=str(best.prompt_key),
                score=best.average_score,
            )
            return best
        
        return None

    async def _validate_prompt_appropriateness(
        self,
        candidate_prompt: RefinedPrompt,
        original_request: str,
        agent_type: str,
    ) -> tuple[bool, str]:
        """Validate if a candidate prompt is appropriate for the original request.
        
        Uses LLM to determine if the candidate prompt is contextually appropriate
        for the specific request, or if it needs modifications.
        
        Args:
            candidate_prompt: The prompt to validate
            original_request: The original user request
            agent_type: The agent type
            
        Returns:
            Tuple of (is_appropriate, reason)
        """
        validation_prompt = f"""Validate if a refined prompt is appropriate for an original request.

Original Request:
---
{original_request}
---

Agent Type: {agent_type}

Candidate Refined Prompt:
---
{candidate_prompt.refined_prompt}
---

Task: Determine if the candidate refined prompt is specifically tailored for the original request,
or if it would need significant modifications to be appropriate.

Key Questions:
1. Does the refined prompt address the SPECIFIC TARGET mentioned in the request?
2. Are there any placeholders or notes suggesting the user needs to modify it?
3. Is the content immediately usable without changes?

Respond in this exact format:
APPROPRIATE: yes|no
REASON: one-sentence explanation
"""
        
        try:
            response = await self.llm.complete(
                system_prompt="You are a validation assistant. Be strict about specificity.",
                user_prompt=validation_prompt,
            )
            
            response_lower = response.lower()
            is_appropriate = "appropriate: yes" in response_lower
            
            # Extract reason
            reason = ""
            if "reason:" in response_lower:
                try:
                    reason_part = response.split("reason:", 1)[1].strip()
                    reason = reason_part.split("\n")[0].strip()
                except IndexError:
                    reason = ""
            
            logger.info(
                "validation_result",
                is_appropriate=is_appropriate,
                reason=reason,
                candidate_prompt_id=str(candidate_prompt.prompt_key),
            )
            
            return is_appropriate, reason
            
        except Exception as e:
            logger.error("validation_failed", error=str(e))
            # If validation fails, be conservative and don't reuse
            return False, "validation failed"

    async def _check_exact_refined_match(
        self,
        refined_text: str,
    ) -> RefinedPrompt | None:
        """Check if exact refined prompt text already exists.
        
        Uses MD5 hash index for efficient exact matching.
        Prevents storing duplicate refined prompts.
        
        Args:
            refined_text: The refined prompt text to check
            
        Returns:
            Existing RefinedPrompt if exact match found, None otherwise
        """
        try:
            existing = await self.repository.get_by_refined_text_hash(refined_text)
            if existing:
                logger.info(
                    "exact_refined_match_found",
                    prompt_id=str(existing.prompt_key),
                    agent_type=existing.agent_type,
                )
                return existing
        except Exception as e:
            logger.error("exact_match_check_failed", error=str(e))
        
        return None

    async def build_context(
        self,
        original_prompt: str,
        agent_type: str,
        main_language: str | None,
        similar_prompts: list[RefinedPrompt],
        context: dict | None = None,
    ) -> str:
        """Build the context for the LLM refinement prompt (lazy evaluation).

        Args:
            original_prompt: The original agent request
            agent_type: Type of agent performing the task
            main_language: Primary programming language
            similar_prompts: List of similar prompts for context
            context: Optional additional context

        Returns:
            Formatted context string
        """
        # Return cached if already built (shouldn't happen with current flow)
        if self._llm_context_cache:
            return self._llm_context_cache
            
        context_parts = [
            f"Agent Type: {agent_type}",
            f"Primary Language: {main_language or 'Not specified'}",
            "",
            "Original Request:",
            "---",
            original_prompt,
            "---",
            "",
        ]

        # Add policies if provided
        if context and isinstance(context, dict):
            policies = context.get("policies", [])
            if policies:
                context_parts.append(f"Policies to consider: {', '.join(policies)}")
                context_parts.append("")
            
            domain = context.get("domain")
            if domain:
                context_parts.append(f"Domain: {domain}")
                context_parts.append("")
            
            constraints = context.get("constraints", [])
            if constraints:
                context_parts.append("Additional Constraints:")
                for constraint in constraints:
                    context_parts.append(f"- {constraint}")
                context_parts.append("")

        if similar_prompts:
            context_parts.append(f"Similar Successful Prompts ({len(similar_prompts)} found):")
            for i, prompt in enumerate(similar_prompts[:3], 1):
                context_parts.extend([
                    f"\nExample {i} (Score: {prompt.average_score:.2f}, Usage: {prompt.usage_count}):",
                    "---",
                    prompt.refined_prompt,
                    "---",
                ])
            context_parts.append("")

        context_parts.extend([
            "Task:",
            "Review the original request and the similar examples above.",
            "Either select the best existing prompt to reuse, or create an improved refined prompt.",
            "The refined prompt should increase the agent's probability of completing the task in one shot.",
        ])

        llm_context = "\n".join(context_parts)
        self._llm_context_cache = llm_context
        return llm_context

    async def refine(
        self,
        original_prompt: str,
        agent_type: str,
        main_language: str | None = None,
        other_languages: list[str] | None = None,
        domain: str | None = None,
        tags: list[str] | None = None,
        original_hash: str | None = None,
        context: dict | None = None,
        project_id: uuid.UUID | None = None,
    ) -> dict:
        """Refine a prompt or select an existing one with optimizations.

        Args:
            original_prompt: The original agent request
            agent_type: Type of agent performing the task
            main_language: Primary programming language
            other_languages: Other languages involved
            domain: Problem domain context
            tags: Tags for categorization
            original_hash: Hash of the original prompt
            context: Additional context
            project_id: Optional project ID to associate with this prompt

        Returns:
            Dict with refinement results
        """
        # PHASE 1: Hash Fast Path
        fast_path_result = await self._check_hash_fast_path(original_hash, agent_type)
        if fast_path_result:
            return fast_path_result
        
        # PHASE 2: Generate embedding (may be cached)
        text_to_embed = f"{agent_type} {main_language or ''} {original_prompt}"
        embedding = await self.embedding.embed(text_to_embed)

        # PHASE 3: Find similar prompts
        similar_prompts = await self.repository.find_similar(
            embedding=embedding,
            agent_type=agent_type,
            limit=settings.vector_search_limit,
            similarity_threshold=settings.vector_similarity_threshold,
        )

        logger.info(
            "similar_prompts_found",
            count=len(similar_prompts),
            agent_type=agent_type,
        )

        # PHASE 4: Select best candidate
        best_prompt = self.selector.select_best_prompt(similar_prompts)
        
        # PHASE 5: Similarity Bypass Check (very high match)
        bypass_candidate = self._check_similarity_bypass(
            similar_prompts, 
            settings.similarity_bypass_threshold
        )
        if bypass_candidate:
            # Validate even high-similarity candidates for contextual appropriateness
            is_appropriate, validation_reason = await self._validate_prompt_appropriateness(
                bypass_candidate,
                original_prompt,
                agent_type,
            )
            
            if is_appropriate:
                logger.info(
                    "reusing_existing_prompt_bypass",
                    prompt_id=str(bypass_candidate.prompt_key),
                    score=bypass_candidate.average_score,
                )
                return {
                    "action": "reuse",
                    "prompt_key": str(bypass_candidate.prompt_key),
                    "refined_prompt": bypass_candidate.refined_prompt,
                    "source": "reused",
                    "similar_prompts_found": len(similar_prompts),
                    "average_score": bypass_candidate.average_score,
                    "usage_count": bypass_candidate.usage_count,
                    "confidence_score": bypass_candidate.average_score / 5.0,
                    "bypass_reason": "high_similarity_score",
                }
            else:
                logger.info(
                    "bypass_rejected_not_appropriate",
                    prompt_id=str(bypass_candidate.prompt_key),
                    reason=validation_reason,
                )

        # PHASE 6: Decide whether to refine or reuse (selector logic)
        if not self.selector.should_create_new_prompt(best_prompt):
            # Validate the candidate before reuse
            is_appropriate, validation_reason = await self._validate_prompt_appropriateness(
                best_prompt,
                original_prompt,
                agent_type,
            )
            
            if is_appropriate:
                # Reuse existing prompt
                logger.info(
                    "reusing_existing_prompt",
                    prompt_id=str(best_prompt.prompt_key),
                    score=best_prompt.average_score,
                )
                return {
                    "action": "reuse",
                    "prompt_key": str(best_prompt.prompt_key),
                    "refined_prompt": best_prompt.refined_prompt,
                    "source": "reused",
                    "similar_prompts_found": len(similar_prompts),
                    "average_score": best_prompt.average_score,
                    "usage_count": best_prompt.usage_count,
                    "confidence_score": best_prompt.average_score / 5.0,
                }
            else:
                logger.info(
                    "selector_reused_rejected_not_appropriate",
                    prompt_id=str(best_prompt.prompt_key),
                    reason=validation_reason,
                )
                # Continue to create new tailored prompt
                # Will use best_prompt as prior_refinement_id

        # PHASE 7: Build context and call LLM (LAZY EVALUATION)
        # Only build context if we're going to call LLM
        llm_context = await self.build_context(
            original_prompt=original_prompt,
            agent_type=agent_type,
            main_language=main_language,
            similar_prompts=similar_prompts,
            context=context,
        )

        logger.info("calling_llm_for_refinement")
        llm_response = await self.llm.complete(
            system_prompt=REFINEMENT_SYSTEM_PROMPT,
            user_prompt=llm_context,
        )

        # Parse the response to extract refined prompt
        refined_text = self._parse_refinement(llm_response)

        # PHASE 8a: Check for exact refined text match (prevent duplicates)
        exact_match = await self._check_exact_refined_match(refined_text)
        if exact_match:
            logger.info(
                "returning_existing_exact_match",
                prompt_id=str(exact_match.prompt_key),
            )
            return {
                "action": "reuse",
                "prompt_key": str(exact_match.prompt_key),
                "refined_prompt": exact_match.refined_prompt,
                "source": "reused",
                "similar_prompts_found": len(similar_prompts),
                "average_score": exact_match.average_score,
                "usage_count": exact_match.usage_count,
                "confidence_score": exact_match.average_score / 5.0,
                "match_type": "exact_refined_text",
            }

        # PHASE 8b: Store the new refined prompt with prior refinement chain
        prior_refinement_id = best_prompt.id if best_prompt else None

        new_prompt = await self.repository.create(
            embedding=embedding,
            agent_type=agent_type,
            original_prompt=original_prompt,
            refined_prompt=refined_text,
            main_language=main_language,
            other_languages=other_languages,
            domain=domain,
            tags=tags,
            original_prompt_hash=original_hash,
            prior_refinement_id=prior_refinement_id,
            project_id=project_id,
            refinement_type="sigmoid",
        )

        logger.info(
            "created_new_refined_prompt",
            prompt_id=str(new_prompt.prompt_key),
            prior_id=str(best_prompt.prompt_key) if best_prompt else None,
        )

        source = "refined" if prior_refinement_id else "new"

        return {
            "action": "refine" if prior_refinement_id else "new",
            "prompt_key": str(new_prompt.prompt_key),
            "refined_prompt": refined_text,
            "source": source,
            "similar_prompts_found": len(similar_prompts),
            "average_score": 0.0,
            "usage_count": 0,
            "confidence_score": 0.5,  # Neutral confidence for new prompts
        }

    def _parse_refinement(self, llm_response: str) -> str:
        """Parse the LLM response to extract the refined prompt."""
        if "REFINED_PROMPT:" in llm_response:
            parts = llm_response.split("REFINED_PROMPT:")
            if len(parts) > 1:
                text = parts[1]
                if "REASONING:" in text:
                    text = text.split("REASONING:")[0]
                return text.strip()
        
        return llm_response.strip()
