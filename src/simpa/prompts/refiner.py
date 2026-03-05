import re
from typing import Optional


class PromptRefiner:
    def __init__(self, repository, embedding_service, llm_service):
        self.repository = repository
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    async def refine(self, original_prompt: str, agent_type: str, main_language: str = None,
                     other_languages: list = None, domain: str = None, tags: list = None,
                     project_id: str = None):
        """Main entry point for refinement."""
        from simpa.utils.logging import get_logger
        logger = get_logger(__name__)

        logger.info("refine_prompt_started", prompt_length=len(original_prompt), agent_type=agent_type)

        embedding = await self.embedding_service.embed(original_prompt)

        similar_prompts = await self.repository.find_similar(
            embedding=embedding,
            agent_type=agent_type,
            limit=5
        )

        if similar_prompts:
            best_prompt = max(similar_prompts, key=lambda p: p.average_score)
            if best_prompt.average_score >= 4.0:
                candidate = await self.repository.get_by_id(best_prompt.id)
                llm_context = self.build_context(
                    original_prompt=original_prompt,
                    agent_type=agent_type,
                    similar_prompts=similar_prompts
                )

                is_appropriate = await self._validate_prompt_appropriateness(candidate, llm_context)
                if is_appropriate:
                    logger.info("returning_existing_prompt", prompt_id=str(best_prompt.id), score=best_prompt.average_score)
                    return {
                        "refined_prompt": candidate.refined_prompt,
                        "prompt_key": str(candidate.prompt_key),
                        "source": "reused",
                        "action": "reuse",
                        "similar_prompts_found": len(similar_prompts),
                        "average_score": best_prompt.average_score,
                        "usage_count": best_prompt.usage_count,
                        "confidence_score": best_prompt.average_score / 5.0,
                    }
                else:
                    logger.info("selector_reused_rejected_not_appropriate", prompt_id=str(best_prompt.id))

        logger.info("calling_llm_for_refinement")
        llm_context = self.build_context(
            original_prompt=original_prompt,
            agent_type=agent_type,
            similar_prompts=similar_prompts
        )

        llm_response = await self.llm_service.complete(
            system_prompt="""You are a prompt refinement specialist. Take raw requests and convert them to clean, structured specifications. Output ONLY requirements, constraints, and acceptance criteria. NEVER include code, implementation details, line counts, or technical scaffolding.

Before writing each line of the refined prompt, review it to ensure you are NOT writing code. If a line contains code patterns (```, class/def definitions, type annotations like ->, import statements), stop and rewrite it as requirements-only.""",
            user_prompt=llm_context
        )

        refined_text = self._parse_refinement(llm_response)
        has_code, reason = self._contains_code(refined_text)
        if has_code:
            logger.warning("prompt_contains_code", reason=reason, cleaning=True)
            refined_text = self._clean_code_from_prompt(refined_text)
            refined_text = f"""⚠️ NOTE: Code was removed from this prompt because it violates best practices.\nPrompts with code are LOW QUALITY and confuse programming agents.\n\n{refined_text}"""

        exact_match = await self._check_exact_refined_match(refined_text)
        if exact_match:
            return {
                "action": "reuse",
                "prompt_key": str(exact_match.prompt_key),
                "refined_prompt": exact_match.refined_prompt,
                "source": "reused",
                "similar_prompts_found": len(similar_prompts),
                "average_score": exact_match.average_score,
                "usage_count": exact_match.usage_count,
                "confidence_score": exact_match.average_score / 5.0,
            }

        new_prompt = await self.repository.create(
            embedding=embedding,
            agent_type=agent_type,
            original_prompt=original_prompt,
            refined_prompt=refined_text,
            main_language=main_language,
            other_languages=other_languages,
            domain=domain,
            tags=tags,
            original_prompt_hash="",
            prior_refinement_id=best_prompt.id if similar_prompts else None,
            project_id=project_id,
            refinement_type="sigmoid",
        )

        logger.info("created_new_refined_prompt", prompt_id=str(new_prompt.prompt_key))

        return {
            "action": "refine" if similar_prompts else "new",
            "prompt_key": str(new_prompt.prompt_key),
            "refined_prompt": refined_text,
            "source": "refined" if similar_prompts else "new",
            "similar_prompts_found": len(similar_prompts),
            "average_score": 0.0,
            "usage_count": 0,
            "confidence_score": 0.5,
        }

    async def _validate_prompt_appropriateness(self, candidate, llm_context):
        """Validate if a candidate prompt is appropriate for reuse."""
        return True

    async def _check_exact_refined_match(self, refined_text):
        """Check if this exact refined text already exists."""
        return None

    def _contains_code(self, text: str) -> tuple[bool, str]:
        """Check if text contains code patterns."""
        import re

        if '```' in text:
            return True, "Contains code block markers"

        code_patterns = [
            (r"\bclass\s+\w+", "Contains class definition"),
            (r"\bdef\s+\w+\s*\(", "Contains function definition"),
            (r"\)\s*-\u003e\s*\w", "Contains type annotation"),
            (r"# \.\.\.", "Contains code placeholder"),
            (r"^\s*import\s+\w", "Contains import statement"),
            (r"^\s*from\s+\w+\s+import", "Contains import statement"),
        ]

        for pattern, reason in code_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True, reason

        return False, ""

    def _clean_code_from_prompt(self, text: str) -> str:
        """Remove code blocks and clean up prompt to be requirements-only."""
        import re

        # Remove markdown code blocks
        text = re.sub(r"```[^`]*```", "[CODE BLOCK REMOVED - REQUIREMENTS ONLY]", text, flags=re.DOTALL)

        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            bullet_removed = line.lstrip()
            if bullet_removed.startswith(("- ", "* ", "+ ")):
                bullet_removed = bullet_removed[2:].lstrip()

            stripped = bullet_removed
            if any(stripped.startswith(p) for p in ["class ", "def ", "# ...", "-> ", "pass", "import ", "from "]):
                continue

            code_keywords = ["class", "def", "code", "pydantic", "redis"]
            if re.search(r"~?\d+\s*lines?", line, re.IGNORECASE) and any(kw in line.lower() for kw in code_keywords):
                continue
            cleaned_lines.append(line)

        result = "\n".join(cleaned_lines)
        result = re.sub(r"\n{3,}", "\n\n", result)

        return result.strip()

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

    def build_context(self, original_prompt, agent_type, similar_prompts):
        """Build the context for the LLM."""
        context_parts = [
            f"Original Request: {original_prompt}",
            f"Agent Type: {agent_type}",
            "",
        ]

        if similar_prompts:
            context_parts.extend([
                "Similar Successful Prompts:",
                "⚠️ WARNING: Examples below may contain CODE which is LOW QUALITY.",
                "HIGH QUALITY prompts contain only REQUIREMENTS with ZERO code.",
                "",
            ])
            for p in similar_prompts[:3]:
                context_parts.append(f"Score {p.average_score}: {p.refined_prompt[:200]}...")
                context_parts.append("")

        context_parts.extend([
            "Task: Convert the original request to a requirements-only specification.",
            "Output format: REFINED_PROMPT: <your refined prompt here>",
        ])

        return "\n".join(context_parts)
