# OpenProse-SIMPA Integration Test Plan

**Date**: 2026-03-04  
**Status**: Test Plan - Ready for Implementation  
**Author**: DT-Tester  
**Version**: 1.0  
**Architecture Reference**: [OpenProse-SIMPA-Integration-Architecture.md](./OpenProse-SIMPA-Integration-Architecture.md)

---

## Executive Summary

This document outlines the comprehensive test strategy for the OpenProse-SIMPA integration. The integration adds 5 new MCP tools, a `prose/` module, and database extensions for managing prose scripts with vector search and self-improvement tracking.

### Test Coverage Goals

| Layer | Coverage Target | Priority |
|-------|----------------|----------|
| Database | 100% schema validation | Critical |
| Repository | 100% CRUD + vector search | Critical |
| Service | 90%+ generation + validation | High |
| MCP Tools | 100% tool coverage | Critical |
| Integration | 80%+ end-to-end flows | High |

---

## Test Strategy

### 1. Test Pyramid

```
                    /\
                   /  \  E2E/Integration Tests (5%)
                  /____\  ~20 tests
                 /      \
                /        \  MCP/Service Tests (20%)
               /          \  ~80 tests
              /____________\
             /              \
            /                \  Repository/Unit Tests (75%)
           /                  \  ~300 tests
          /____________________\
```

### 2. Testing Approach

| Category | Approach |
|----------|----------|
| Unit Tests | pytest with mocks, in-memory SQLite |
| Integration Tests | Test containers with PostgreSQL + pgvector |
| MCP Tests | Async test client calling actual MCP server |
| Performance Tests | k6 or pytest-benchmark for search latency |
| E2E | Full docker-compose stack with real OpenProse VM |

### 3. Test Organization

```
tests/
├── unit/
│   ├── prose/
│   │   ├── test_models.py
│   │   ├── test_repository.py
│   │   ├── test_service.py
│   │   └── test_validation.py
│   └── db/
│       └── test_migrations.py
├── integration/
│   ├── test_repository_pg.py
│   ├── test_service_integration.py
│   └── test_mcp_tools.py
├── e2e/
│   └── test_prose_workflow.py
├── fixtures/
│   ├── prose_scripts/
│   │   ├── valid_simple.prose
│   │   ├── valid_parallel.prose
│   │   ├── invalid_syntax.prose
│   │   └── invalid_undefined_agent.prose
│   └── data/
│       └── test_embeddings.py
└── conftest.py
```

---

## Component Test Plans

### 1. Database Layer Tests

#### 1.1 Schema Migration Tests

**File**: `tests/db/test_migrations.py`

| Test ID | Description | Setup | Expected Result |
|---------|-------------|-------|-----------------|
| DB-001 | prose_scripts table created | Run migration `008_add_prose_scripts` | Table exists with all columns |
| DB-002 | prose_script_history table created | Run migration | Table exists with FK constraints |
| DB-003 | Embedding index created | Run migration | ivfflat index exists on embedding column |
| DB-004 | Text search index created | Run migration | GIN index exists for BM25 search |
| DB-005 | Foreign key constraints work | Insert invalid FK | Raises IntegrityError |
| DB-006 | Downgrade removes tables | Run downgrade | Tables dropped, no residual objects |

#### 1.2 Data Type Validation

| Test ID | Description | Input | Expected Result |
|---------|-------------|-------|-----------------|
| DB-007 | UUID generation | Insert without id | Auto-generated UUID v4 |
| DB-008 | Embedding dimension | 768-dimensional vector | Accepts VECTOR(768) |
| DB-009 | Score distribution | -1 score value | Constraint error |
| DB-010 | Score distribution | 6 score value | Constraint error |
| DB-011 | is_active default | Insert without is_active | Defaults to TRUE |
| DB-012 | timestamp handling | Insert record | created_at set to NOW() |

#### 1.3 Vector Search Function Tests

**File**: `tests/db/test_vector_search.py`

| Test ID | Description | Test Data | Expected Result |
|---------|-------------|-----------|-----------------|
| DB-013 | find_prose_scripts with exact match | 3 scripts, search for "security" | Returns matching script with high similarity |
| DB-014 | find_prose_scripts with semantic match | "vulnerability scanner" vs "security checker" | Returns relevant script (>0.7 similarity) |
| DB-015 | find_prose_scripts empty query | Valid query, no matches | Empty result set, no errors |
| DB-016 | find_prose_scripts threshold filtering | Set threshold=0.9 | Only scripts above threshold |
| DB-017 | find_prose_scripts with BM25 | Search "review code" | Text rank > 0 |
| DB-018 | find_prose_scripts combined scoring | Hybrid search | Results ordered by combined_score |
| DB-019 | find_prose_scripts agent_type filter | filter="DT-Developer" | Only scripts for that agent type |
| DB-020 | find_prose_scripts performance | 1000 scripts | < 200ms query time |

### 2. Repository Layer Tests

**File**: `tests/unit/prose/test_repository.py`

#### 2.1 CRUD Operations

| Test ID | Method | Description | Expected |
|---------|--------|-------------|----------|
| REPO-001 | create | Create script with all fields | Returns ProseScript with generated script_key |
| REPO-002 | create | Create with duplicate title | Success (unique script_key) |
| REPO-003 | create | Create with duplicate prose_hash | Success (unique hash) |
| REPO-004 | get_by_key | Retrieve by valid script_key | Returns correct script |
| REPO-005 | get_by_key | Retrieve with invalid key | Returns None |
| REPO-006 | get_by_id | Retrieve by internal id | Returns correct script |
| REPO-007 | get_by_slug | Retrieve by slug | Returns correct script |
| REPO-008 | update | Update title | Updated_at changed, version +1 |
| REPO-009 | update | Update prose_content | New hash, embedding updated |
| REPO-010 | delete | Soft delete (is_active=False) | Record persists, is_active=False |
| REPO-011 | list | List with project_id filter | Only scripts from project |
| REPO-012 | list | List with agent_type filter | Only matching agent_type |
| REPO-013 | list | List with pagination | Correct offset/limit |
| REPO-014 | list | List with sort ordering | Ordered by specified field |

#### 2.2 Vector Search Operations

| Test ID | Method | Description | Expected |
|---------|--------|-------------|----------|
| REPO-015 | find_similar | Search with embedding | Returns scripts sorted by similarity |
| REPO-016 | find_similar | With high_score_only | Only scores > threshold |
| REPO-017 | search_hybrid | Vector + BM25 hybrid | Uses find_prose_scripts() function |
| REPO-018 | search_hybrid | No text matches | Returns vector-based results |
| REPO-019 | search_hybrid | No vector matches | Returns BM25-based results |

#### 2.3 Statistics Operations

| Test ID | Method | Description | Expected |
|---------|--------|-------------|----------|
| REPO-020 | update_stats | Update usage_count | Incremented by 1 |
| REPO-021 | update_stats | Update average_score | Recalculated weighted average |
| REPO-022 | update_stats | Update score_dist arrays | Correct bucket incremented |
| REPO-023 | update_usage | Mark as used | last_used_at updated |

### 3. Service Layer Tests

**File**: `tests/unit/prose/test_service.py`

#### 3.1 Validation Tests

| Test ID | Method | Input | Expected |
|---------|--------|-------|----------|
| SRV-001 | validate | Valid simple prose | valid=True, errors=[] |
| SRV-002 | validate | Valid parallel prose | valid=True |
| SRV-003 | validate | Valid resume prose | valid=True |
| SRV-004 | validate | Missing session/resume | valid=False, error about required section |
| SRV-005 | validate | Undefined agent | valid=False, error lists undefined agent |
| SRV-006 | validate | Invalid indentation | valid=False, error about first-line indent |
| SRV-007 | validate | Invalid agent definition | valid=False, error about agent syntax |
| SRV-008 | validate | Missing agent block | valid=False, error about agent body |
| SRV-009 | validate | Invalid model specifier | valid=False, warns about model |

#### 3.2 Generation Tests

| Test ID | Method | Setup | Expected |
|---------|--------|-------|----------|
| SRV-010 | create_from_prompt | Valid description | Returns generated prose, script stored |
| SRV-011 | create_from_prompt | With context hints | Uses hints in generation |
| SRV-012 | create_from_prompt | With similar examples | Similar scripts used as context |
| SRV-013 | create_from_prompt | Invalid description | Raises ValidationError |
| SRV-014 | create_from_prompt | LLM fails | Raises appropriate error |
| SRV-015 | create_from_prompt | Validation fails | Returns error details, partial result |
| SRV-016 | create_from_prompt | Generation > 3s | Logs warning, still returns |

#### 3.3 Score Tracking Tests

| Test ID | Method | Input | Expected |
|---------|--------|-------|----------|
| SRV-017 | record_execution | score=5 | Usage count +1, avg_score updated |
| SRV-018 | record_execution | score=1 | score_dist_1 incremented |
| SRV-019 | record_execution | duration_ms tracked | Recorded in history |
| SRV-020 | record_execution | files modified | Stored as array in history |

### 4. MCP Tool Tests

**File**: `tests/integration/test_mcp_tools.py`

#### 4.1 Tool: create_prose_from_prompt

| Test ID | Scenario | Input | Expected Output |
|---------|----------|-------|-----------------|
| MCP-001 | Successful generation | "Create code review script" | prose_content, script_key, confidence |
| MCP-002 | With project_id | project_id=valid_uuid | Script associated with project |
| MCP-003 | With complexity hint | complexity="simple" | Generation respects hint |
| MCP-004 | Empty description | "" | Error: description required |
| MCP-005 | Invalid agent_type | "UnknownAgent" | Error: invalid agent_type |
| MCP-006 | Invalid project_id | "not-a-uuid" | Error: invalid format |
| MCP-007 | Generation timeout | Complex request | Returns timeout error |
| MCP-008 | LLM error | LLM service down | Returns service unavailable |

#### 4.2 Tool: list_prose_scripts

| Test ID | Scenario | Input | Expected Output |
|---------|----------|-------|-----------------|
| MCP-009 | List all | No filters | Paginated list of all scripts |
| MCP-010 | Filter by project | project_id=xxx | Only scripts for project |
| MCP-011 | Filter by agent | agent_type="DT-Developer" | Only matching scripts |
| MCP-012 | Pagination | limit=10, offset=20 | Correct page of results |
| MCP-013 | Sort by usage | sort_by="usage_count" | Ordered by usage desc |
| MCP-014 | Empty result | Filter=no_match | Empty array, total=0 |
| MCP-015 | Inactive scripts | is_active=false | Excluded by default |

#### 4.3 Tool: find_prose_scripts

| Test ID | Scenario | Input | Expected Output |
|---------|----------|-------|-----------------|
| MCP-016 | Semantic search | "code review" | Relevant scripts with scores |
| MCP-017 | With threshold | threshold=0.9 | Only high-confidence matches |
| MCP-018 | Limit results | max_results=3 | At most 3 results |
| MCP-019 | With agent_type | agent_type="DT-Tester" | Filtered to agent type |
| MCP-020 | Empty search | "" | Returns empty or raises |

#### 4.4 Tool: list_prose_script

| Test ID | Scenario | Input | Expected Output |
|---------|----------|-------|-----------------|
| MCP-021 | By script_key | valid key | Full script with metadata |
| MCP-022 | By title | title="Security Scanner" | Matching script |
| MCP-023 | With usage stats | - | Includes usage_count, avg_score |
| MCP-024 | Invalid key | "not-a-uuid" | Not found error |
| MCP-025 | Inactive script | key of inactive | Returns with is_active=false |

#### 4.5 Tool: update_prose_script

| Test ID | Scenario | Input | Expected Output |
|---------|----------|-------|-----------------|
| MCP-026 | Create new | no script_key | Creates new script |
| MCP-027 | Update existing | valid key | Updates, increments version |
| MCP-028 | Update content | new prose_content | Validates before store |
| MCP-029 | Update tags | tags=["security"] | Tags updated |
| MCP-030 | Invalid syntax | prose with errors | Error: validation failed |
| MCP-031 | Duplicate title | title exists | Either error or allow |
| MCP-032 | Non-existent key | script_key=random | Not found error |

### 5. Integration Tests

**File**: `tests/integration/test_prose_workflow.py`

#### 5.1 Full Workflow Tests

| Test ID | Scenario | Steps | Validation |
|---------|----------|-------|------------|
| INT-001 | Happy path workflow | 1. Create from prompt<br>2. Store script<br>3. Find similar<br>4. List script<br>5. Execute<br>6. Record score | Each step succeeds |
| INT-002 | Concurrent creation | 3 simultaneous creates | No race conditions, all created |
| INT-003 | Versioning flow | 1. Create script<br>2. Update 3 times<br>3. Check versions | Versions 1, 2, 3 track correctly |
| INT-004 | Search refinement | 1. Search vague term<br>2. Drill down with filters | Results improve with filters |
| INT-005 | Score tracking | 1. Create<br>2. Execute with score X<br>3. Execute again<br>4. Check avg | Average correctly calculated |

#### 5.2 OpenProse Integration Tests

| Test ID | Scenario | Steps | Validation |
|---------|----------|-------|------------|
| INT-006 | VM execution | 1. Generate prose<br>2. Pass to OpenProse VM<br>3. Execute | VM accepts and executes |
| INT-007 | Generated validity | 1. Generate 10 scripts<br>2. Validate all<br>3. Check pass rate | >80% pass validation |
| INT-008 | Generated semantics | 1. Generate from description<br>2. Human verify match | LLM intent preserved |

---

## Test Data Fixtures

### 1. Valid Prose Scripts

**valid_simple.prose**:
```prose
# Simple research agent

agent researcher:
  model: sonnet
  prompt: "You are a research assistant. Find relevant information and summarize clearly."

session: researcher
  prompt: "Research the current state of LLM evaluation benchmarks"
```

**valid_parallel.prose**:
```prose
# Parallel code review

agent security:
  model: opus
  prompt: "Focus on security vulnerabilities"

agent performance:
  model: sonnet
  prompt: "Focus on performance optimizations"

parallel:
  session: security
    prompt: "Review for vulnerabilities"
  session: performance
    prompt: "Review for performance"
```

### 2. Invalid Prose Scripts

**invalid_syntax.prose** (missing session/resume):
```prose
agent tester:
  prompt: "test"
```

**invalid_undefined_agent.prose**:
```prose
session: undefined_agent
  prompt: "This won't work"
```

### 3. Test Embeddings

```python
# fixtures/data/test_embeddings.py
TEST_EMBEDDINGS = {
    "security_scanner": [0.1, 0.2, ...],  # 768 dims
    "code_review": [0.3, 0.4, ...],
    "documentation": [0.5, 0.6, ...],
}
```

---

## Mock Requirements

### 1. LLM Service Mock

```python
@pytest.fixture
def mock_llm_service():
    """Returns deterministic prose based on description keywords"""
    def generate(description, system_context):
        if "security" in description:
            return load_fixture("valid_security.prose")
        elif "parallel" in description:
            return load_fixture("valid_parallel.prose")
        return load_fixture("valid_simple.prose")
    return MockLLMService(generate)
```

### 2. Embedding Service Mock

```python
@pytest.fixture
def mock_embedding_service():
    """Returns consistent embeddings for test strings"""
    def embed(text):
        # Deterministic based on content hash
        return generate_test_embedding(text)
    return MockEmbeddingService(embed)
```

### 3. Database Setup

```python
@pytest.fixture(scope="function")
def pg_container():
    """PostgreSQL + pgvector test container"""
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        yield postgres
```

---

## Performance Benchmarks

### 1. Search Performance

| Metric | Target | Test | Pass Criteria |
|--------|--------|------|---------------|
| Vector search | < 100ms | 1000 scripts | p95 < 100ms |
| BM25 search | < 50ms | 1000 scripts | p95 < 50ms |
| Hybrid search | < 200ms | 1000 scripts | p95 < 200ms |
| Find similar | < 150ms | 1000 scripts | p95 < 150ms |

### 2. Generation Performance

| Metric | Target | Test | Pass Criteria |
|--------|--------|------|---------------|
| Simple generation | < 2s | 10 requests | average < 2s |
| Complex generation | < 5s | 10 requests | average < 5s |
| Concurrent generation | < 10s | 5 parallel | all complete < 10s |

### 3. Database Performance

| Metric | Target | Test | Pass Criteria |
|--------|--------|------|---------------|
| Migration time | < 5s | Fresh DB | Complete < 5s |
| Insert rate | > 100/sec | Batch insert | > 100 rows/sec |
| Index creation | < 10s | 1000 rows | < 10s for ivfflat |

---

## CI/CD Integration

### 1. GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test OpenProse Integration

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run unit tests
        run: pytest tests/unit -v --cov=src/simpa/prose

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
    steps:
      - name: Run integration tests
        run: pytest tests/integration -v --timeout=300

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - name: Run E2E tests
        run: pytest tests/e2e -v --timeout=600
```

### 2. Coverage Requirements

```ini
# .coveragerc
[run]
source = src/simpa/prose

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError

fail_under = 85
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM generation flaky | High | Medium | Retry logic, mock in CI |
| Vector search slow | Low | High | Performance tests, index tuning |
| OpenProse incompatibility | Medium | High | E2E tests with actual VM |
| Migration issues | Low | High | Test both up/down migrations |
| Race conditions | Medium | Medium | Concurrent tests, transaction isolation |

---

## Test Schedule

| Phase | Duration | Focus | Owner |
|-------|----------|-------|-------|
| Unit Tests | 2 days | Repository, Service, Validation | DT-Tester |
| Integration Tests | 3 days | MCP Tools, Database | DT-Tester |
| E2E Tests | 2 days | Full workflow, OpenProse VM | DT-Tester |
| Performance Tests | 1 day | Search latency, throughput | DT-Tester |
| **TOTAL** | **1 week** | | |

---

## Approval

| Role | Status | Notes |
|------|--------|-------|
| DT-Tester | ✅ APPROVED | Ready to implement |
| DT-Developer | ⏳ PENDING | Review for feasibility |
| DT-Reviewer | ⏳ PENDING | Review for coverage adequacy |

---

*This test plan was created using the DyTopo multi-agent process by DT-Tester.*
