import re
from typing import Optional

from simpa.utils.logging import get_logger
from simpa.prompts.selector import PromptSelector

logger = get_logger(__name__)

REFINEMENT_SYSTEM_PROMPT = """You are a prompt refinement specialist. Your job is to convert raw requests into CLEAN, STRUCTURED REQUIREMENTS.

## ABSOLUTE PROHIBITIONS (NEVER DO THESE):
1. ❌ NEVER use code blocks (```) or markdown code fences
2. ❌ NEVER write function definitions (def function_name():)
3. ❌ NEVER write class definitions (class ClassName:)
4. ❌ NEVER use decorators (@retry, @dataclass, etc.)
5. ❌ NEVER specify line counts ("(40 lines)", "(~50 lines)")
6. ❌ NEVER write import statements
7. ❌ NEVER use type annotations (-> ReturnType, : Type)
8. ❌ NEVER write shebangs (#!/usr/bin/env python)
9. ❌ NEVER write CLI argument parsers or main() functions
10. ❌ NEVER write pseudo-code that looks like implementation

## YOUR CORE MISSION - REFRAMING REQUESTS:
When the user asks for code, scripts, or implementation, you MUST reframe it:

❌ WRONG: "Create a Python script that does X" → You write code yourself
✅ RIGHT: "Create a Python script that does X" → You write requirements FOR AN AGENT who will write the code

**You are a REQUIREMENTS WRITER, not a CODER. Your refined output will be given to a coding agent who will do the actual implementation.**

Think of yourself as:
- A **project manager** writing a specification for developers
- A **client** describing what they want built
- A **customer** placing an order, not the **builder** constructing it

**NEVER write implementation. ALWAYS write specification.**

## REQUIRED APPROACH:
1. Explain WHAT properties the solution must have
2. Explain WHY those properties matter
3. Let the implementer figure out HOW

## OUTPUT FORMAT - STRUCTURED SECTIONS:

Your refined output MUST use this exact section format:

```
ROLE: [Agent persona - expertise level and perspective]

GOAL: [Clear objective statement - what should be delivered]

CONSTRAINTS: [Boundaries and limitations - what NOT to do]

CONTEXT: [Background information and system context]

OUTPUT: [Expected deliverable format]

SUCCESS: [Acceptance criteria - how to know it's done]

AUTONOMY: [What decisions the agent can make independently vs what requires confirmation]

FALLBACK: [What to do when blocked or uncertain]
```

Each section should be 1-3 sentences maximum. Be concise and specific.

## LANGUAGE RULES:
- Use requirements language: "shall", "must", "should", "provide", "support", "enable"
- AVOID implementation language: "implement", "function", "class", "method", "variable", "return", "import"
- FOCUS on behavior, constraints, and acceptance criteria

## LENGTH CONSTRAINT:
- Maximum 800 characters total across all sections
- Be concise and direct

## EXAMPLES:

BAD (implementation-heavy):
```
def fibonacci(n: int) -> int:
    # Returns the nth Fibonacci number
    pass
Include type hints and docstrings.
```

GOOD (requirements-focused):
Create a utility function that returns the nth Fibonacci number for non-negative integers n. Handle edge cases: return 0 for n=0, return 1 for n=1. Optimize for O(n) time and O(1) space. Include comprehensive docstring with complexity analysis and usage examples.

BAD (with line counts and code):
```python
class WorkerConfig:  # (~40 lines)
    worker_id: int
    redis_url: str = "redis://localhost:6379/0"

def run_forever(self):  # Core daemon loop (~60 lines)
    while not self.shutdown_flag:
        goal = self._poll_and_claim_goal()
```

Use following request format, without code and without micro-management...
```
***Agentic Prompt Format***
1. Role & Persona Definition

2. Purpose: Establishes the agent's expertise level and perspective (e.g., "Senior Python Engineer," "Security-Focused Developer").
Why: Sets expectations for code quality, best practices, and decision-making autonomy.
Clear Objective / Goal Statement

3. Purpose: Defines the desired outcome in one or two sentences (e.g., "Build a REST API endpoint that processes audio files").
Why: Keeps the agent aligned on the end goal without prescribing every step.
Constraints & Boundaries

4. Purpose: Specifies what not to do (e.g., "Do not modify existing database schemas," "Avoid external dependencies").
Why: Prevents scope creep and unwanted changes without needing constant oversight.
Context & Background

5. Purpose: Provides relevant information about the project, architecture, or existing codebase structure.
Why: Enables informed decisions without requiring the agent to ask clarifying questions repeatedly.
Output Format & Structure

6. Purpose: Defines how results should be delivered (e.g., "Return code blocks with file paths," "Include a summary of changes").
Why: Ensures consistency and usability of outputs without follow-up formatting requests.
Success Criteria / Acceptance Conditions

7. Purpose: Describes what "done" looks like (e.g., "Tests pass," "No linting errors," "Backward compatible").
Why: Allows the agent to self-evaluate completion without needing approval at each stage.
Autonomy Guidelines

8. Purpose: Explicitly states what decisions the agent can make independently vs. what requires user confirmation (e.g., "You may refactor helper functions, but ask before changing public APIs").
Why: Grants freedom within safe boundaries, reducing back-and-forth.
Error Handling & Fallback Behavior

8. Purpose: Instructs the agent on what to do if blocked or uncertain (e.g., "If a file is missing, propose a creation plan before proceeding").
Why: Prevents hallucination or incorrect assumptions without constant monitoring.

9. Purpose: Project Directory Focus. Stay focused within the project's set of listed directories to avoid unintended changes.
Why: Keeps changes localized and prevents accidental modifications outside the intended scope.

10. PurposeL Project Files Focus. Stay focused on changes within a specific set of project files to avoid unintended changes.
Why: Keeps changes to specific files and prevents accidental modifications outside the intended scope.

```
Example...
```
ROLE: Software Architect
GOAL: Design a caching strategy for the product catalog.
CONSTRAINTS: Output will be descriptive only; no actual implementation code.
REQUIREMENTS:
- Identify data access patterns (read-heavy, write-heavy, or mixed)
- Design cache-invalidation strategy (time-based, event-driven, or hybrid)
- Define cache key structure and naming conventions
- Specify cache-aside, write-through, or write-behind patterns
- Address cache consistency, eviction policies, and TTL configuration
- Consider multi-tier caching (in-memory + distributed)
- Document potential issues: stale data, thundering herd, cache penetration
OUTPUT: Architecture document detailing caching strategy.
SUCCESS: Design addresses scalability, performance, and data consistency.
AUTONOMY: Choose appropriate caching technology (Redis, Memcached, Caffeine).
FALLBACK: If data volume or access patterns are unclear, document assumptions.
```

GOOD (requirements only):
```
ROLE: Senior Distributed Systems Engineer
GOAL: Build a deterministic Redis-backed worker driver that polls goals, processes them algorithmically, and publishes responses with full traceability
CONSTRAINTS: No external dependencies beyond Redis client, no hardcoded worker IDs, no blocking operations that prevent graceful shutdown
CONTEXT: Part of DyTopo agent orchestration system, multiple parallel worker instances, Redis as central coordination layer
OUTPUT: Production-ready Python module with structured JSON logging, worker_id and request_id correlation on all log entries
SUCCESS: Atomic Redis operations prevent race conditions, SIGTERM handled gracefully, multiple instances run without conflicts, all operations logged with correlation IDs
AUTONOMY: You may choose Redis key patterns and polling intervals, ask before changing message schema or adding new dependencies
FALLBACK: If Redis connection fails, implement exponential backoff with max retries before exiting; if uncertain about edge cases, document assumptions in code comments
PROJECT_DIRS: src
PROJECT_FILES: src/scripts/dt-agents
```

## YOUR TASK:
Convert the user's request into clean requirements. Output ONLY the refined prompt text - no explanations, no markdown formatting around the output."""


class PromptRefiner:
    def __init__(self, repository, embedding_service, llm_service):
        self.repository = repository
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.selector = PromptSelector()

    async def refine(self, original_prompt: str, agent_type: str, main_language: str = None,
                     other_languages: list = None, domain: str = None, tags: list = None,
                     project_id: str = None, original_hash: str = None, context: dict = None):
        """Main entry point for refinement."""
        logger.info("refine_prompt_started", prompt_length=len(original_prompt), agent_type=agent_type)

        embedding = await self.embedding_service.embed(original_prompt)

        similar_prompts = await self.repository.find_similar(
            embedding=embedding,
            agent_type=agent_type,
            limit=5
        )

        if similar_prompts:
            # Use selector to decide whether to reuse or refine
            best_prompt = self.selector.select_best_prompt(similar_prompts)
            logger.info("selector_best_prompt", best_prompt_id=str(best_prompt.id) if best_prompt else None, avg_score=best_prompt.average_score if best_prompt else None)
            
            if best_prompt and best_prompt.average_score >= 4.0:
                candidate = await self.repository.get_by_id(best_prompt.id)
                
                # Check if we should create new or reuse
                should_create = self.selector.should_create_new_prompt(best_prompt)
                logger.info("selector_decision", should_create=should_create)
                
                if not should_create:
                    # Reuse existing prompt
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
                    logger.info("selector_chose_to_refine", prompt_id=str(best_prompt.id), score=best_prompt.average_score)
            else:
                logger.info("prompt_score_too_low", best_prompt_score=best_prompt.average_score if best_prompt else None)

        logger.info("calling_llm_for_refinement")
        llm_context = await self.build_context(
            original_prompt=original_prompt,
            agent_type=agent_type,
            similar_prompts=similar_prompts,
            main_language=main_language,
            scope_context=context  # ← PASS THE SCOPE CONTEXT
        )

        llm_response = await self.llm_service.complete(
            system_prompt=REFINEMENT_SYSTEM_PROMPT,
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
            context=context,  # Store the scope context
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

    def _get_role_intent(self, agent_type: str, main_language: str = None) -> str:
        """Generate role intent description based on agent type and language.
        
        This explains what kind of agent will receive the refined prompt,
        helping the LLM understand the target audience.
        """
        language = main_language or "python"
        
        role_map = {
            "developer": f"Senior {language.title()} Developer who will write production-ready code",
            "architect": f"Senior {language.title()} Architect who will design system components",
            "tester": f"QA Engineer who will write comprehensive test suites",
            "reviewer": f"Code Reviewer who will analyze and validate implementations",
            "manager": f"Technical Lead who will coordinate development tasks",
        }
        
        return role_map.get(agent_type, f"Senior {language.title()} Developer")

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

    async def build_context(self, original_prompt, agent_type, similar_prompts, main_language=None, scope_context=None):
        """Build the context for the LLM.
        
        Args:
            original_prompt: The user's original prompt text
            agent_type: Type of agent (developer, architect, tester, reviewer)
            similar_prompts: List of similar prompts found in database
            main_language: Primary programming language
            scope_context: Dict with scope information (scope, focus, target_dirs, etc.)
        """
        # NOTE: We intentionally DO NOT include similar prompts as examples
        # because they may contain code/implementation details that contaminate
        # the refinement. The system prompt has all the guidance needed.
        
        context_parts = [
            f"Original Request: {original_prompt}",
            f"Agent Type: {agent_type}",
        ]
        
        # Add role intent - what kind of agent will receive this refined prompt
        role_intent = self._get_role_intent(agent_type, main_language)
        context_parts.append(f"ROLE INTENT: {role_intent}")
        
        if main_language:
            context_parts.append(f"Primary Language: {main_language}")
        
        # Add scope context if provided
        if scope_context:
            scope_parts = []
            
            if scope_context.get('scope'):
                scope_parts.append(f"  - Scope: {scope_context['scope']}")
            
            if scope_context.get('focus'):
                focus = scope_context['focus']
                if isinstance(focus, list):
                    scope_parts.append(f"  - Focus Areas: {', '.join(focus)}")
                else:
                    scope_parts.append(f"  - Focus Areas: {focus}")
            
            if scope_context.get('target_dirs'):
                dirs = scope_context['target_dirs']
                if isinstance(dirs, list):
                    scope_parts.append(f"  - Target Directories: {', '.join(dirs)}")
                else:
                    scope_parts.append(f"  - Target Directories: {dirs}")
            
            if scope_context.get('target_files'):
                files = scope_context['target_files']
                if isinstance(files, list):
                    scope_parts.append(f"  - Target Files: {', '.join(files)}")
                else:
                    scope_parts.append(f"  - Target Files: {files}")
            
            if scope_context.get('exclude'):
                exclude = scope_context['exclude']
                if isinstance(exclude, list):
                    scope_parts.append(f"  - Exclude: {', '.join(exclude)}")
                else:
                    scope_parts.append(f"  - Exclude: {exclude}")
            
            # Add any other context keys
            for key, value in scope_context.items():
                if key not in ['scope', 'focus', 'target_dirs', 'target_files', 'exclude']:
                    if isinstance(value, list):
                        scope_parts.append(f"  - {key.replace('_', ' ').title()}: {', '.join(str(v) for v in value)}")
                    else:
                        scope_parts.append(f"  - {key.replace('_', ' ').title()}: {value}")
            
            if scope_parts:
                context_parts.append("")
                context_parts.append("📍 SCOPE CONTEXT:")
                context_parts.extend(scope_parts)
        
        context_parts.append("")
        
        # Only mention if similar prompts exist (for metrics), but don't show them
        if similar_prompts:
            context_parts.append(f"Note: {len(similar_prompts)} similar prompts exist in history.")
            context_parts.append("")

        # Reinforce critical constraints in user prompt (LLM pays more attention here)
        context_parts.extend([
            "⚠️  CRITICAL CONSTRAINTS (MUST FOLLOW):",
            "- NEVER use code blocks (```) or markdown code fences",
            "- NEVER write function/class definitions (def/class)",
            "- NEVER specify line counts like '(40 lines)'",
            "- NEVER write import statements or decorators",
            "- Output ONLY requirements describing WHAT, not HOW",
            "- Max 800 characters",
            "",
            "🎯 REFRAMING INSTRUCTION:",
            "If the user asks you to 'create a script', 'write code', 'implement', or similar:",
            "- DO NOT write any code or implementation details",
            "- DO NOT describe HOW to implement the solution",
            "- Instead, write requirements that will be PASSED TO AN AGENT who will do the actual coding",
            "- Your job is to prepare the ASSIGNMENT for the coder, not to BE the coder",
            "- Focus on: What should the agent deliver? What are the acceptance criteria?",
            "",
            "📋 OUTPUT FORMAT (MUST USE THIS STRUCTURE):",
            "Your refined prompt MUST use this exact section format:",
            "",
            "ROLE: Security-Focused Code Reviewer",
            "GOAL: Review error handling patterns in the codebase.",
            "CONSTRAINTS: Review only within assigned scope and files:",
            "  - target_dirs: src/services/, src/utils/",
            "  - target_files: src/services/user_service.py",
            "  - focus: security, logging, user-experience",
            "  - scope: error handling patterns only",
            "CONTEXT: Production code review process",
            "OUTPUT: Line-by-line comments and summary report",
            "SUCCESS: Critical issues identified, recommendations actionable",
            "AUTONOMY: Can use static analysis tools within scope",
            "FALLBACK: Ask if scope unclear",
            "Review Checklist:",
            "- Security: Exception leaks sensitive data, proper sanitization",
            "- Logging: Appropriate log levels, no PII exposure",
            "- User Experience: Helpful error messages, graceful degradation",
            "- Code Quality: Consistent patterns, avoid catch-all exceptions",
            "- Documentation: Error scenarios documented, recovery paths clear",
            "",
            "Task: Convert the original request using the section format above.",
            "Output format: REFINED_PROMPT: <your refined prompt in section format>",
        ])

        return "\n".join(context_parts)
