# Test Suite Development Report

## Overview

Developing a comprehensive test suite for SIMPA (Simple AI-assisted Project Assistant) presented significant challenges due to the async nature of the application, database integration with PostgreSQL/pgvector, and the MCP (Model Context Protocol) server architecture.

## Test Suite Structure

### Test Organization
```
tests/
├── conftest.py              # Shared fixtures and configuration
├── db/
│   ├── test_engine.py       # Database engine and session testing
│   ├── test_schema.py       # Schema validation
│   ├── test_models.py       # Model unit tests
│   ├── test_repository.py   # Repository pattern tests
│   └── test_project_migration.py
├── integration/
│   ├── test_mcp_tools.py    # MCP tool integration tests (16 tests)
│   ├── test_optimized_workflow.py  # Workflow optimization (14 tests)
│   └── test_project_mcp.py  # Project management MCP tests (17 tests)
└── unit/
    ├── test_embedding_service.py
    ├── test_llm_service.py
    └── test_selector.py
```

## Development Difficulties

### 1. Async Event Loop Management

**Challenge:** Coordinating async database sessions with pytest-asyncio across multiple test scopes.

**Problems Encountered:**
- `RuntimeError: Event loop is closed` when tests tried to reuse event loops
- Scope conflicts between `session`-scoped and `function`-scoped fixtures
- AsyncSession not properly isolated between tests

**Solutions Applied:**

```python
# pytest.ini configuration
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_loop_scope = "session"
asyncio_default_test_loop_scope = "function"

# Fixture scoping strategy
@pytest_asyncio.fixture(scope="session")  # Database container
async def postgres_container():
    ...

@pytest_asyncio.fixture  # Function-scoped for isolation  
async def db_engine(postgres_url):
    # Drop and recreate tables for each test
    ...
```

### 2. Database Session Isolation

**Challenge:** MCP tools create their own database sessions via `AsyncSessionLocal()`, making them invisible to test data.

**Root Cause:** 
```python
# In mcp_server.py - imports happen at module load time
from simpa.db.engine import AsyncSessionLocal

async def update_prompt_results(...):
    async with AsyncSessionLocal() as session:  # Creates NEW session
        ...
```

**Solution:** The `patch_async_session_local` fixture:

```python
@pytest.fixture(scope="function")
def patch_async_session_local(db_session: AsyncSession):
    """Patch AsyncSessionLocal to return the test session."""
    class MockSessionContextManager:
        def __init__(self, session):
            self.session = session
        
        async def __aenter__(self):
            return self.session  # Returns test session, not new one
        
        async def __aexit__(self, *args):
            pass
    
    def mock_session_local():
        return MockSessionContextManager(db_session)
    
    with patch("simpa.mcp_server.AsyncSessionLocal", mock_session_local):
        with patch("simpa.db.engine.AsyncSessionLocal", mock_session_local):
            yield
```

### 3. Schema Migration Issues

**Challenge:** Database schema drift between migrations and models caused test failures.

**Problems:**
- Legacy column `diffs_by_language` renamed to `diffs` in migrations but not reflected in test assertions
- Extra column `score_distribution` added manually to database but not in model
- Default value assertions failing because `server_default` only applies at DB level, not Python

**Solution:** Created compensating migrations:

```python
# alembic/versions/005_rename_diffs_column.py
"""Rename diffs_by_language to diffs"""

def upgrade():
    op.alter_column('prompt_history', 'diffs_by_language', new_column_name='diffs')

# alembic/versions/006_remove_score_distribution.py
"""Remove score_distribution column"""

def upgrade():
    op.drop_column('refined_prompts', 'score_distribution')
```

### 4. Embedding Vector Similarity

**Challenge:** Test embeddings were matching unexpectedly due to cosine similarity properties.

**Discovery:**
```python
# These vectors have cosine similarity of 1.0!
embedding_a = [0.1] * 768
embedding_b = [0.5] * 768
# cos_sim(a, b) = dot(a,b) / (|a|*|b|) = constant/constant = 1.0
```

**Solution:** Use varied embedding patterns:
```python
# In tests - distinct pattern
mock_embedding = [i % 2 for i in range(768)]  # [0, 1, 0, 1, ...]

# In fixtures - different pattern
sample_embedding = [0.1] * 768
```

### 5. Pydantic Model Validation

**Challenge:** Validation occurs at model instantiation, not at usage.

**Example:**
```python
# This raises ValidationError immediately, before reaching business logic
UpdatePromptResultsRequest(
    prompt_key="invalid-uuid",  # UUID validation here
    action_score=6.0,          # Range validation here
)
```

**Solution:** Tests must wrap request creation:
```python
with pytest.raises(ValidationError):
    UpdatePromptResultsRequest(prompt_key="invalid-uuid", ...)
```

### 6. API Response Model Evolution

**Challenge:** Response models changed during development, breaking assertions.

**Changes Required:**
| Old | New |
|-----|-----|
| `response.prompt_id` | `response.prompt_key` |
| `response.found` | Removed (now raises ValueError) |
| `p["project_name"]` | `p.project_name` (Pydantic model) |
| `get_history_for_prompt()` | `get_by_prompt_key()` |

### 7. Test Container Orchestration

**Challenge:** TestContainers require Docker and have startup timing issues.

**Solution Pattern:**
```python
@pytest_asyncio.fixture(scope="session")
async def postgres_container():
    # Docker availability check
    try:
        subprocess.run(["docker", "version"], ...)
    except:
        pytest.skip("Docker not available")
    
    container = PostgresContainer(image="pgvector/pgvector:pg16")
    container.start()
    time.sleep(3)  # Wait for extension availability
    yield container
    container.stop()
```

### 8. LLM Prompt Refinement: System vs User Prompt Attention

**Challenge:** Model (`ollama/llama3.2`) was ignoring system prompt constraints, generating code blocks and line counts despite explicit prohibitions.

**Root Causes Discovered:**

| Issue | Evidence | Solution |
|-------|----------|----------|
| **Example Contamination** | Old prompts with code included as "examples" in context | Removed similar prompts from context entirely |
| **LLM Attention Bias** | System prompt ignored; user prompt followed constraints | Reinforce critical constraints in both locations |
| **The "Taint" Effect** | Words like "create script" trigger coding mode before constraints | User prompt must open with constraints first |

**Before (Failed):**
```python
# System prompt: "NEVER use code blocks"
# User prompt included: "Example 1 (Score: 4.0): [old code-heavy prompt]"
# Result: 4,800 chars of code blocks, line counts, class definitions
```

**The "Aha Moment" - Reframing:**

The breakthrough came from realizing the LLM was identifying as the **coder**, not the **specification writer**. When users said "create a script", the LLM thought "I should write that script" instead of "I should write specs for a coder to implement."

**After (Working):**
```python
# System prompt now includes:
"""
## YOUR CORE MISSION - REFRAMING REQUESTS:
When the user asks for code, scripts, or implementation, you MUST reframe it:

❌ WRONG: "Create a Python script" → You write code yourself
✅ RIGHT: "Create a Python script" → You write requirements FOR AN AGENT

**You are a REQUIREMENTS WRITER, not a CODER.**
Think of yourself as a project manager writing a spec for developers.
NEVER write implementation. ALWAYS write specification.
"""

# User prompt opens with reinforcement:
"""
⚠️  CRITICAL CONSTRAINTS (MUST FOLLOW):
- NEVER use code blocks (```) or markdown code fences
- NEVER write function/class definitions
- NEVER specify line counts like '(40 lines)'
- Output ONLY requirements describing WHAT, not HOW

🎯 REFRAMING INSTRUCTION:
If the user asks you to 'create a script', 'write code', 'implement', or similar:
- DO NOT write any code or implementation details
- Instead, write requirements that will be PASSED TO AN AGENT who will do the actual coding
- Your job is to prepare the ASSIGNMENT for the coder, not to BE the coder
- Focus on: What should the agent deliver? What are the acceptance criteria?
"""
# Result: 337 chars, clean requirements only
```

**Testing Strategy:**
- Clear LLM cache between runs to eliminate false positives
- Print exact context sent to LLM for inspection
- Test with "tainted" inputs (verbose code requests) as hardest case
- Isolate system vs user prompt effectiveness separately

**Working Architecture:**
```
System prompt:  General guidelines, tone, role definition
      ↓
User prompt:   CRITICAL CONSTRAINTS (reinforcement) ⚠️
               Original request
               Task instructions
               Output format
      ↓
LLM Call:      Clean output ✓
```

**Additional Discovery - Role Intent & Structured Format:**

We found that simply telling the LLM to "write requirements" wasn't enough. The refined prompts needed two more elements:

1. **Role Intent**: Explicitly stating WHO will receive the refined prompt:
```python
# Added to user prompt context:
"ROLE INTENT: Senior Python Developer who will write production-ready code"
# This helps the LLM write requirements appropriate for the target agent's expertise level
```

2. **Structured Output Format**: Enforcing a specific 8-section format:
```
ROLE: [Agent expertise/persona]
GOAL: [Clear objective]
CONSTRAINTS: [Boundaries]
CONTEXT: [Background]
OUTPUT: [Deliverable format]
SUCCESS: [Acceptance criteria]
AUTONOMY: [Decision scope]
FALLBACK: [What to do when blocked]
```

This structure ensures consistency and completeness without the LLM inventing implementation details.

**Updated Context Flow:**
```
User prompt now includes:
  - ROLE INTENT (who receives this)
  - Original request
  - CRITICAL CONSTRAINTS
  - REFRAMING INSTRUCTION
  - OUTPUT FORMAT (8 sections)
  ↓
LLM Call
  ↓
Structured requirements in ROLE/GOAL/CONSTRAINTS format ✓
```

**Lessons:**
1. System prompts set the stage; user prompts enforce the rules
2. Never trust training data without quality filtering
3. The **opening words** of the user prompt matter as much as constraints
4. LLMs may pay more attention to user prompts than system prompts (model-dependent)
5. **Reframing is critical:** When users ask for code, the LLM must understand it's writing a specification FOR another agent, not writing the code itself
6. **Self-identification matters:** Explicitly telling the LLM "You are a REQUIREMENTS WRITER, not a CODER" changes its role identity
7. **Role intent bridges the gap:** Explicitly stating who will receive the refined prompt helps the LLM calibrate the requirements appropriately
8. **Structured format prevents hallucination:** Forcing specific sections (ROLE, GOAL, CONSTRAINTS, etc.) prevents the LLM from drifting into implementation details

## Key Takeaways

1. **Fixture Scoping Matters:** `session`-scoped for containers, `function`-scoped for isolation
2. **Patch Early and Often:** Mock imports at module level, not just where defined
3. **Database State Isolation:** Drop/recreate tables per test for true isolation
4. **Vector Math Awareness:** Understand cosine similarity behavior with constant vectors
5. **Pydantic Validation Timing:** Validation happens at `__init__`, not usage
6. **Integration Testing Complexity:** Async + DB + containers requires careful orchestration
7. **LLM Prompt Testing:** Test exact context sent; cache invalidation; contamination isolation; role intent calibration; structured output enforcement

## Current Status

**Test Count:** 274 passed, 8 skipped, 0 failed

**Coverage Areas:**
- Database engine and models: ✅
- Repository pattern: ✅
- MCP tool endpoints: ✅
- Project management: ✅
- Workflow optimization: ✅

**Skipped Tests:** 8 tests requiring external services or future features
