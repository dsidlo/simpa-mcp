# Prompt Refinement Enhancement - Implementation Summary

## Overview
Implemented contextual-aware prompt refinement to prevent the system from returning generic prompts with notes instead of tailored prompts for specific targets.

## Problem Solved
Previously, when similar prompts were found via vector similarity (e.g., DT-Manager script), the system would return them even if they weren't appropriate for the specific context (e.g., DT-Worker request), just adding a note saying "change DT-Manager to DT-Worker where appropriate."

## Changes Implemented

### 1. Database Layer (`src/simpa/db/repository.py`)

**New Method: `get_by_refined_text_hash()`**
```python
async def get_by_refined_text_hash(self, refined_text: str) -> RefinedPrompt | None:
    """Find exact match by refined prompt text using MD5 hash.
    
    Uses the functional MD5 hash index for O(1) exact matching.
    This prevents storing duplicate refined prompts.
    """
```

**Purpose:**
- Prevents storing duplicate refined prompts in the database
- Uses functional MD5 index for O(1) lookups
- Called after LLM generation to check for exact duplicates

### 2. Database Migration (`alembic/versions/007_add_refined_prompt_hash_index.py`)

**Created hash indexes for exact text matching:**
```sql
CREATE INDEX idx_refined_prompt_md5_hash 
ON refined_prompts USING hash (md5(refined_prompt));

CREATE INDEX idx_original_prompt_md5_hash 
ON refined_prompts USING hash (md5(original_prompt));
```

### 3. Refiner Engine (`src/simpa/prompts/refiner.py`)

**New Method: `_validate_prompt_appropriateness()`**
```python
async def _validate_prompt_appropriateness(
    self,
    candidate_prompt: RefinedPrompt,
    original_request: str,
    agent_type: str,
) -> tuple[bool, str]:
    """Validate if a candidate prompt is appropriate for the original request.
    
    Uses LLM to determine if the candidate prompt is contextually appropriate
    for the specific request, or if it needs modifications.
    """
```

**Purpose:**
- Called before reusing an existing prompt
- Validates that the candidate prompt is specifically tailored for the request
- Returns boolean indicating appropriateness and reason

**New Method: `_check_exact_refined_match()`**
```python
async def _check_exact_refined_match(
    self,
    refined_text: str,
) -> RefinedPrompt | None:
    """Check if exact refined prompt text already exists."""
```

**Purpose:**
- Called after LLM generates a refined prompt
- Returns existing prompt if exact match found
- Prevents duplicate storage

**Updated System Prompt:**
The `REFINEMENT_SYSTEM_PROMPT` now includes:
- **CRITICAL RULE - CONTEXTUAL TAILORING**: Must create prompts tailored for specific targets
- Examples of proper vs. improper contextual tailoring
- Enforcement of immediate usability (no adaptation needed)
- Emphasis on replacing generic references with specific targets

**Updated Refinement Logic:**
1. **Hash Fast Path** (existing) - Check for exact hash match
2. **Vector Similarity Search** (existing) - Find semantically similar prompts
3. **Similarity Bypass Validation** (NEW) - Validate high-similarity candidates
4. **Selector Reuse Validation** (NEW) - Validate before reusing selector-selected prompts
5. **LLM Refinement** (existing) - Generate new tailored prompt
6. **Exact Match Check** (NEW) - Check for duplicate refined text
7. **Storage with Prior Refinement Chain** (existing) - Store with proper chain linking

## Test Updates

### Updated Tests in `tests/unit/test_refiner.py`
- `test_refine_reuses_existing_prompt` - Added mocks for validation
- `test_refine_creates_new_prompt` - Added mocks for exact match check
- `test_refine_with_prior_refinement` - Added mocks for exact match check
- `test_refine_embedding_composition` - Added mocks for validation
- `test_refine_strips_llm_output` - Added mocks for exact match check
- `test_refine_uses_repository_find_similar` - Added mocks for exact match check
- `test_llm_called_with_system_prompt` - Added mocks for exact match check

### Updated Test in `tests/integration/test_mcp_tools.py`
- `test_reuse_existing_prompt` - Mocked LLM with validation responses

## Flow Diagram

```
Original Request
     ↓
[Hash Fast Path Check]
     ↓ (if not found)
[Generate Embedding]
     ↓
[Vector Similarity Search]
     ↓
[Similarity Bypass Check]
     ↓
[Validate Appropriateness] ← NEW
     ↓ (if not appropriate)
[Selector Decision]
     ↓
[Validate Appropriateness] ← NEW
     ↓ (if not appropriate)
[LLM Refinement]
     ↓
[Exact Match Check] ← NEW
     ↓ (if not duplicate)
[Store with Prior Refinement ID]
     ↓
Return Refined Prompt
```

## Validation Prompt Structure

The validation prompt sent to LLM:
```
Validate if a refined prompt is appropriate for an original request.

Original Request:
---
{original_request}
---

Agent Type: {agent_type}

Candidate Refined Prompt:
---
{candidate_prompt.refined_prompt}
---

Task: Determine if the candidate refined prompt is specifically tailored 
for the original request, or if it would need significant modifications.

Key Questions:
1. Does the refined prompt address the SPECIFIC TARGET mentioned?
2. Are there any placeholders suggesting user needs to modify it?
3. Is the content immediately usable without changes?

Respond in this exact format:
APPROPRIATE: yes|no
REASON: one-sentence explanation
```

## Success Criteria Achieved

1. ✅ **Contextual Appropriateness**: System now validates prompts before reuse
2. ✅ **Exact Match Prevention**: Prevents storing duplicate refined prompts
3. ✅ **Proper Refinement Chain**: Links related prompts via prior_refinement_id
4. ✅ **Tailored Prompts**: System prompt enforces specific targeting
5. ✅ **All Tests Pass**: 288 passed, 33 skipped, 0 warnings

## Future Enhancements

Potential improvements:
1. Add `refinement_context` column to track why new prompts were created
2. Cache validation results to avoid redundant LLM calls
3. Add confidence threshold for validation (e.g., only validate if similarity > 0.85)
4. Implement batch validation for multiple candidates

## Files Changed

- `src/simpa/db/repository.py` - Added `get_by_refined_text_hash()` method
- `src/simpa/prompts/refiner.py` - Added validation and exact match logic
- `alembic/versions/007_add_refined_prompt_hash_index.py` - New migration
- `tests/unit/test_refiner.py` - Updated tests with new mocks
- `tests/integration/test_mcp_tools.py` - Updated integration test
- `docs/implementation/prompt-refinement-enhancement.md` - Design document
- `docs/implementation/prompt-refinement-implementation-summary.md` - This document
