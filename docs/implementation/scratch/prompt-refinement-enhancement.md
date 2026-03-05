# Prompt Refinement Enhancement: Context-Aware Differentiation

## Problem Statement

The current prompt refinement system has a critical flaw when handling semantically similar but contextually distinct requests:

**Scenario:**
- **Prompt 1:** "Create a python script for DT-Manager" → Creates Refined Prompt A (DT-Manager focused)
- **Prompt 2:** "Create a python script for DT-Worker" → Returns Refined Prompt A with a note to "adapt for DT-Worker"

**Root Cause:**
Vector similarity matching finds Prompt A (high semantic similarity: both request Python scripts for DyTopo agents), but the refined prompt content is specific to DT-Manager and inappropriate for DT-Worker needs.

**Impact:**
- Users receive inadequate refinements
- The system fails to create distinct, tailored prompts for different use cases
- Prior refinement chains don't properly branch for contextual variations

---

## Proposed Solution

### 1. Exact Text Matching Layer

**Add an exact text lookup before vector similarity search:**

```python
# Check for exact match on refined_prompt text
existing = await repository.get_by_refined_prompt_text(refined_text)
if existing:
    return existing  # Don't duplicate
```

**Database Index:**
```sql
-- Add hash index for efficient exact matching
CREATE INDEX idx_refined_prompt_text_hash ON refined_prompts USING hash (md5(refined_prompt));
```

### 2. LLM Validation Step

**Before returning a reused prompt, validate contextual appropriateness:**

```python
async def validate_prompt_appropriateness(
    candidate_prompt: RefinedPrompt,
    original_request: str,
    agent_type: str,
) -> bool:
    """Validate if candidate prompt is appropriate for the request."""
    validation_prompt = f"""
    Task: Validate if the refined prompt is appropriate for the original request.

    Original Request:
    {original_request}

    Candidate Refined Prompt:
    {candidate_prompt.refined_prompt}

    Question: Is this refined prompt specifically tailored for the original request,
    or would it need significant modifications?

    Respond with only:
    APPROPRIATE: yes|no
    REASON: brief explanation
    """
    response = await llm.complete(validation_prompt)
    return "APPROPRIATE: yes" in response.lower()
```

### 3. Smart Refinement Chain

**When similarity is high but context differs:**

```python
if similar_prompts and similarity > threshold:
    if await validate_prompt_appropriateness(best_prompt, original_prompt, agent_type):
        return reuse_prompt(best_prompt)
    else:
        # Create NEW prompt with prior_refinement_id chain
        return await create_tailored_refinement(
            original_prompt=original_prompt,
            similar_prompt=best_prompt,  # Use as prior_refinement_id
            agent_type=agent_type,
            reason="contextual variation: similar topic, different target"
        )
```

### 4. Enhanced System Prompt

**Update REFINEMENT_SYSTEM_PROMPT to emphasize contextual tailoring:**

```python
REFINEMENT_SYSTEM_PROMPT = """
You are an expert prompt engineer specializing in refining prompts for AI agents.

CRITICAL RULE:
If the original request has a SPECIFIC TARGET (e.g., "DT-Worker" vs "DT-Manager",
"frontend" vs "backend", "React" vs "Vue"), you MUST create a tailored prompt
for that SPECIFIC TARGET. Do NOT return a generic prompt with a note to adapt it.

Your task is to analyze the provided agent request and either:
1. Select the most appropriate existing refined prompt if it's EXACTLY appropriate
2. Create a NEW refined prompt tailored to the SPECIFIC context

Guidelines for refinement:
- Tailor the prompt to the SPECIFIC target/context mentioned in the request
- Replace generic references with specific ones (e.g., "DT-Worker" not "agent")
- Include specific examples relevant to the target
- Make the prompt immediately usable without modifications
... (rest of guidelines)
"""
```

---

## Implementation Plan

### Phase 1: Exact Match Prevention
1. Add `get_by_refined_text_hash()` method to repository
2. Add database index on MD5 hash of refined_prompt
3. Check exact match before returning LLM-generated prompt
4. If exact match exists, return existing with metadata

### Phase 2: Contextual Validation
1. Implement `validate_prompt_appropriateness()` method
2. Call validation when similarity > threshold
3. Use validation result to decide: reuse vs. create new

### Phase 3: Smart Refinement Chain
1. Modify `refine()` to create new prompts when context differs
2. Set `prior_refinement_id` to link related prompts
3. Add `refinement_context` field to track why new version was created

### Phase 4: Enhanced System Prompt
1. Update REFINEMENT_SYSTEM_PROMPT with contextual tailoring rules
2. Add examples of good vs. bad refinements
3. Test with DT-Manager vs. DT-Worker scenarios

---

## Database Schema Changes

```sql
-- Add index for exact text matching
CREATE INDEX idx_refined_prompt_text_hash 
ON refined_prompts USING hash (md5(refined_prompt));

-- Optional: Add refinement_context field for tracking
ALTER TABLE refined_prompts 
ADD COLUMN refinement_context TEXT;
```

---

## Efficiency Considerations

### Vector Search (Current)
- **Use case:** Find semantically similar prompts
- **Complexity:** O(n) with pgvector indexing
- **Best for:** Initial similarity discovery

### Exact Text Hash (New)
- **Use case:** Prevent duplicate refined prompts
- **Complexity:** O(1) with hash index
- **Best for:** Post-LLM deduplication

### Contextual Validation (New)
- **Use case:** Validate appropriateness before reuse
- **Complexity:** O(1) LLM call
- **Best for:** High-similarity edge cases

---

## Success Criteria

1. **DT-Manager vs. DT-Worker Test:**
   - Prompt 1 creates DT-Manager script → ✓
   - Prompt 2 creates DT-Worker script (NOT DT-Manager with note) → ✓

2. **No Duplicate Prompts:**
   - Same request twice → Returns same prompt_key → ✓
   - Different request, same similarity → Different prompt_key → ✓

3. **Proper Chain Tracking:**
   - DT-Worker prompt has prior_refinement_id pointing to DT-Manager → ✓
   - Can trace evolution from generic to specific → ✓

---

## Testing Strategy

### Unit Tests
- Test `get_by_refined_text_hash()` method
- Test exact match detection
- Test prior_refinement_id assignment

### Integration Tests
- Test DT-Manager → DT-Worker refinement chain
- Test that similar but distinct prompts create separate entries
- Test that identical requests return same prompt

### Edge Cases
- Same topic, different targets (Manager vs. Worker)
- Same target, different topics (Worker for testing vs. Worker for docs)
- Incremental refinements (v1 → v2 → v3)

---

## Related Files

- `src/simpa/prompts/refiner.py` - Core refinement logic
- `src/simpa/db/repository.py` - Database operations
- `src/simpa/db/models.py` - Database models
- `alembic/versions/` - Migration scripts

---

## References

- DyTopo Protocol: See `~/.pi/agent/skills/dytopo-skills/dt-manager/SKILL.md`
- Current refiner implementation: `src/simpa/prompts/refiner.py`
- Repository pattern: `src/simpa/db/repository.py`
