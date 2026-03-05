# Refinement System Improvements

## Problem
The refined prompts had serious quality issues:
- 70% contained code blocks, function definitions, class skeletons
- Line count prescriptions (e.g., "(40 lines)")
- Excessive length (6,000-10,000 chars vs ideal 200-500)
- Implementation-heavy instead of requirements-focused

## Solution
Updated `REFINEMENT_SYSTEM_PROMPT` in `src/simpa/prompts/refiner.py` with:

### 10 Absolute Prohibitions
2. Function definitions (def name():)
3. Class definitions (class Name:)
4. Decorators (@retry, @dataclass)
5. Line count prescriptions ("(40 lines)")
6. Import statements
7. Type annotations (-> ReturnType)
8. Shebangs (#!/usr/bin/env)
9. CLI parsers or main() functions
10. Pseudo-code resembling implementation

### Language Rules
- **USE**: "shall", "must", "should", "provide", "support", "enable"
- **AVOID**: "implement", "function", "class", "method", "variable", "return"

### Length Constraint
- Maximum 800 characters
- Be concise and direct

## Results

### Before
| Metric | Value |
|--------|-------|
| Clean prompts | 30% (6/20) |
| Avg length | 5,000+ chars |
| Code blocks | 60% |
| Line counts | 35% |
| Function defs | 50% |

### After
| Metric | Value |
|--------|-------|
| Clean prompts | 100% (5/5) |
| Avg length | 341 chars |
| Code blocks | 0% |
| Line counts | 0% |
| Function defs | 0% |
| Quality score | 10/10 |

## Example Improvements

### Before (6,841 chars)
```markdown
# DT-Worker Driver Script - Complete Implementation

## CONTEXT
You are implementing a **deterministic driver**...

### 1. CONFIGURATION & INITIALIZATION (40 lines)
```
@dataclass
class WorkerConfig:
    worker_id: int
    redis_url: str = "redis://localhost:6379/0"
```
[... 200+ lines of code ...]
```

### After (146 chars)
```
Create a deterministic driver for the DT-Manager agent in the DyTopo system, 
replacing its tasks with a production-ready standalone Python script.
```

## Test Results
All 299 tests pass, and the 5 new diverse prompts all achieved 10/10 quality scores.
