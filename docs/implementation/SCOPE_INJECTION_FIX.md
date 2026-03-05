# Scope Injection Fix - Summary

## Problem
Scoping context (scope, focus, target_dirs, target_files) was being passed in the `RefinePromptRequest` but was **never being included** in the LLM prompt or stored in the database.

### Before (Broken)
```
Request: {
  "original_prompt": "Create API gateway...",
  "context": {
    "scope": "API layer design patterns only",
    "focus": ["scalability", "security"],
    "target_dirs": ["src/api/", "src/gateway/"]
  }
}

LLM Prompt Sent:
  "Original Request: Create API gateway..."
  "Agent Type: architect"
  "ROLE INTENT: Senior Python Architect..."
  (NO scope, NO focus, NO target_dirs!)
  
Database Record:
  - refined_prompt: "Generic architecture template..."
  - context: NULL
```

### After (Fixed)
```
Request: {
  "original_prompt": "Create API gateway...",
  "context": {
    "scope": "API layer design patterns only",
    "focus": ["scalability", "security"],
    "target_dirs": ["src/api/", "src/gateway/"]
  }
}

LLM Prompt Sent:
  "Original Request: Create API gateway..."
  "Agent Type: architect"
  "ROLE INTENT: Senior Python Architect..."
  "SCOPE CONTEXT:"
  "  - Scope: API layer design patterns only"
  "  - Focus Areas: scalability, security"
  "  - Target Directories: src/api/, src/gateway/"
  
Database Record:
  - refined_prompt: "Scope-aware refinement..."
  - context: {"scope": "...", "focus": [...], "target_dirs": [...]}
```

## Changes Made

### 1. `src/simpa/prompts/refiner.py`

#### Updated `refine()` method (line ~227)
- Added `context` parameter to `build_context()` call

```python
# Before
llm_context = await self.build_context(
    original_prompt=original_prompt,
    agent_type=agent_type,
    similar_prompts=similar_prompts,
    main_language=main_language
)

# After
llm_context = await self.build_context(
    original_prompt=original_prompt,
    agent_type=agent_type,
    similar_prompts=similar_prompts,
    main_language=main_language,
    scope_context=context  # ← ADDED
)
```

#### Updated `build_context()` method (line ~376)
- Added `scope_context` parameter
- Added scope context formatting in the prompt

```python
# Added parameter
async def build_context(self, original_prompt, agent_type, similar_prompts, 
                        main_language=None, scope_context=None):
    
    ...
    
    # Added scope context section
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
            context_parts.append("SCOPE CONTEXT:")
            context_parts.extend(scope_parts)
```

#### Updated `repository.create()` call (line ~260)
- Added `context` parameter when creating prompt

```python
new_prompt = await self.repository.create(
    ...
    context=context,  # ← ADDED
)
```

### 2. `src/simpa/db/models.py`

Added `context` column to `RefinedPrompt` model:

```python
# Scope context (JSON blob for scope, focus, target_dirs, etc.)
context: Mapped[dict | None] = mapped_column(
    JSON,
    nullable=True,
    default=None,
)
```

### 3. `src/simpa/db/repository.py`

Updated `RefinedPromptRepository.create()` method to accept and pass context:

```python
async def create(
    self,
    embedding: list[float] | None,
    agent_type: str,
    ...
    context: dict | None = None,  # ← ADDED
) -> RefinedPrompt:
    prompt = RefinedPrompt(
        ...
        context=context,  # ← ADDED
    )
```

### 4. `tests/integration/test_scope_injection.py`

Created comprehensive integration tests:
- `test_scope_context_included_in_llm_call` - Verifies scope appears in LLM prompt
- `test_scoped_prompt_has_scope_in_output` - Verifies scope in refined output
- `test_scope_vs_no_scope_comparison` - Compares scoped vs unscoped prompts
- `test_scope_stored_in_refinement_history` - Verifies scope stored in DB
- `test_reviewer_with_security_focus` - Tests specific use case

## Test Results

All 60 integration tests pass, including 5 new scope injection tests.

## Impact

Without scope injection:
```
Arch Prompt with scope → Generic architecture template
Dev Prompt with scope → Generic development template
```

With scope injection:
```
Arch Prompt with "API gateway, scalable" scope → 
  Refines to include API-specific patterns, scalability concerns

Dev Prompt with "CSV processing, error-handling" scope →
  Refines to include CSV validation patterns, error-handling patterns

Tester Prompt with "order workflow, edge-cases" scope →
  Refines to include order-specific test scenarios

Reviewer Prompt with "SQL injection, src/db/" scope →
  Refines to include security review checklist for DB layer
```

## Notes

- The `scope_context` field is optional (nullable), so backward compatibility is maintained
- Any additional keys in the context dict are automatically included in the LLM prompt
- The context is stored as JSON in the database for full round-trip preservation
