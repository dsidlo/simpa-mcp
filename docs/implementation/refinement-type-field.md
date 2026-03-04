# Refinement Type Field Documentation

## Overview

The `refinement_type` field in the `refined_prompts` table tracks how a refined prompt was created - whether through a direct/manual request or through the sigmoid-based automatic refinement process.

## Schema Changes

### Migration

**File**: `alembic/versions/008_add_refinement_type.py`

```sql
-- Add refinement_type column
ALTER TABLE refined_prompts 
ADD COLUMN refinement_type VARCHAR(20) NOT NULL DEFAULT 'sigmoid';

-- Create index for filtering
CREATE INDEX idx_refined_prompts_refinement_type ON refined_prompts(refinement_type);
```

### Model Update

**File**: `src/simpa/db/models.py`

```python
# In RefinedPrompt class
refinement_type: Mapped[str] = mapped_column(
    String(20),
    nullable=False,
    default="sigmoid",
    server_default="sigmoid",
)
```

## Refinement Types

| Type | Description | Use Case |
|------|-------------|----------|
| `sigmoid` | Created through sigmoid-based automatic refinement | Normal flow where probability determines if new prompt is created |
| `direct` | Created through direct/manual request | API calls or manual refinement requests |

## Implementation Details

### Repository Layer

**File**: `src/simpa/db/repository.py`

The `RefinedPromptRepository.create()` method now accepts an optional `refinement_type` parameter (defaults to "sigmoid"):

```python
async def create(
    self,
    # ... other parameters ...
    refinement_type: str = "sigmoid",
) -> RefinedPrompt:
    prompt = RefinedPrompt(
        # ... other fields ...
        refinement_type=refinement_type,
    )
```

### Refiner Layer

**File**: `src/simpa/prompts/refiner.py`

Currently, the refiner always passes `refinement_type="sigmoid"` when creating prompts through the normal flow:

```python
new_prompt = await self.repository.create(
    # ... other parameters ...
    refinement_type="sigmoid",
)
```

## Future Enhancements

### Direct Refinement via API

To support direct/manual refinement, extend the MCP tool to accept a `refinement_type` parameter:

```python
class RefinePromptRequest(BaseModel):
    original_prompt: str
    agent_type: str
    main_language: Optional[str] = None
    refinement_type: str = "sigmoid"  # "sigmoid" | "direct"
    # ... other fields ...
```

Then in the refiner:

```python
refinement_type = request.refinement_type or "sigmoid"

new_prompt = await self.repository.create(
    # ... other parameters ...
    refinement_type=refinement_type,
)
```

### Analytics Use Cases

The `refinement_type` field enables:

1. **Effectiveness Comparison**: Compare success rates between sigmoid and direct refinements
2. **Usage Patterns**: Track how prompts are being created in the system
3. **Audit Trail**: Understand the creation context for debugging
4. **Reporting**: Generate reports on refinement method distribution

### Query Examples

```sql
-- Count prompts by refinement type
SELECT refinement_type, COUNT(*) as count 
FROM refined_prompts 
GROUP BY refinement_type;

-- Find high-performing sigmoid-refined prompts
SELECT * FROM refined_prompts 
WHERE refinement_type = 'sigmoid' 
  AND average_score > 4.0;

-- Find direct refinements for analysis
SELECT * FROM refined_prompts 
WHERE refinement_type = 'direct' 
ORDER BY created_at DESC;
```

## Testing

All existing tests pass with the new field:

```bash
$ python -m pytest tests/unit/test_refiner.py -v
==============================
10 passed in 1.36s

$ python -m pytest tests/ -q
288 passed, 33 skipped
```

## Migration Notes

- **Default Value**: Existing prompts will have `refinement_type = 'sigmoid'`
- **Index**: An index is created for efficient filtering by type
- **Backward Compatible**: Default value ensures existing code continues to work
