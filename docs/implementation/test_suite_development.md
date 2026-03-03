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

## Key Takeaways

1. **Fixture Scoping Matters:** `session`-scoped for containers, `function`-scoped for isolation
2. **Patch Early and Often:** Mock imports at module level, not just where defined
3. **Database State Isolation:** Drop/recreate tables per test for true isolation
4. **Vector Math Awareness:** Understand cosine similarity behavior with constant vectors
5. **Pydantic Validation Timing:** Validation happens at `__init__`, not usage
6. **Integration Testing Complexity:** Async + DB + containers requires careful orchestration

## Current Status

**Test Count:** 274 passed, 8 skipped, 0 failed

**Coverage Areas:**
- Database engine and models: ✅
- Repository pattern: ✅
- MCP tool endpoints: ✅
- Project management: ✅
- Workflow optimization: ✅

**Skipped Tests:** 8 tests requiring external services or future features
