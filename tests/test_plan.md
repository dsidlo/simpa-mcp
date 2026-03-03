# SIMPA Test Plan

**Version**: 1.0  
**Date**: 2026-03-03  
**Author**: DT-Tester  
**System**: SIMPA (Self-Improving Meta Prompt Agent)

---

## 1. Test Strategy Overview

### 1.1 Testing Objectives
- Validate sigmoid refinement algorithm and probability calculations
- Ensure MCP tool handlers function correctly under various conditions
- Verify vector similarity search accuracy with pgvector
- Confirm end-to-end prompt refinement workflows
- Establish performance benchmarks for embedding and vector operations

### 1.2 Test Coverage Goals
| Component | Target Coverage |
|-----------|-----------------|
| Sigmoid Algorithm | 100% (all score boundaries) |
| MCP Tools | 100% (both tools, all paths) |
| Database Layer | 95%+ (vector + relational operations) |
| Integration Flows | 90%+ (end-to-end scenarios) |
| Performance | All benchmarks met |

### 1.3 Test Categories
1. **Unit Tests** - Individual component validation
2. **Integration Tests** - Multi-component orchestration
3. **End-to-End Tests** - Full workflow validation
4. **Performance Tests** - Latency and throughput benchmarks
5. **Property-Based Tests** - Fuzzing and invariant checking

---

## 2. Unit Tests

### 2.1 Sigmoid Refinement Algorithm Tests

**File**: `tests/unit/test_refinement.py`

#### 2.1.1 Boundary Condition Tests
```python
test_sigmoid_score_1_0()
# Expected: p_refine ≈ 0.953 (aggressive refinement)
# Formula: 1 / (1 + exp(1.5 * (1.0 - 3.0)))

test_sigmoid_score_3_0()
# Expected: p_refine = 0.50 (coin-flip territory)
# Formula: 1 / (1 + exp(1.5 * (3.0 - 3.0)))

test_sigmoid_score_5_0()
# Expected: p_refine ≈ 0.047 (rare refinement)
# Formula: 1 / (1 + exp(1.5 * (5.0 - 3.0)))
```

#### 2.1.2 Probability Distribution Tests
```python
test_sigmoid_all_score_bins()
# Scores: [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
# Expected: [0.953, 0.905, 0.818, 0.679, 0.5, 0.321, 0.182, 0.095, 0.047]
# Tolerance: ±0.01
```

#### 2.1.3 Parameter Variation Tests
```python
test_sigmoid_steepness_k_variation()
# Test k values: [0.5, 1.0, 1.5, 2.0, 2.5]
# Verify curve steepness changes appropriately

test_sigmoid_midpoint_mu_variation()
# Test μ values: [2.0, 2.5, 3.0, 3.5, 4.0]
# Verify 50% probability point shifts correctly
```

#### 2.1.4 Exploration Floor Tests
```python
test_exploration_floor_enforced()
# Input: score=5.0, floor=0.05
# Expected: p_refine >= 0.05 (guaranteed minimum)

test_usage_decay_formula()
# Formula: p_final = 0.8 * p_refine + 0.2 * e^(-usage/30)
# Test usage values: [0, 10, 30, 60, 100]
# Verify decay curve for new prompts
```

#### 2.1.5 Decision Logic Tests
```python
test_should_refine_probability_boundary()
# Mock random() to test threshold behavior
# Case 1: random < p_refine → refine=True
# Case 2: random >= p_refine → refine=False
```

### 2.2 Score Statistics Tests

**File**: `tests/unit/test_statistics.py`

```python
test_average_score_calculation()
# Input scores: [1, 2, 3, 4, 5]
# Expected: 3.0

test_score_histogram_update()
# Insert scores across bins 1-5
# Verify distribution tracking

test_score_aggregation_with_history()
# Current: usage=10, avg=3.5
# New score: 4.0
# Expected: new_avg = (3.5*10 + 4.0) / 11 = 3.55

test_score_distribution_percentile()
# Verify histogram percentiles for quartile analysis
```

### 2.3 Embedding Service Tests

**File**: `tests/unit/test_embeddings.py`

```python
test_embedding_generation_mock()
# Mock Ollama/nomic-embed-text response
# Verify 768-dimensional vector output

test_embedding_text_preprocessing()
# Input: agent_type + original_prompt + main_language
# Verify concatenation and normalization

test_embedding_cache_hit()
# Same text twice → second call uses cache
# Verify no redundant API calls
```

---

## 3. Integration Tests

### 3.1 MCP Tool Handler Tests

**File**: `tests/integration/test_mcp_tools.py`

#### 3.1.1 Tool: `simpa_refine_prompt`

**Test Case: Existing High-Quality Prompt Reuse**
```python
test_refine_prompt_reuse_existing()
# Setup:
#   - Insert prompt with score=4.5 into DB
#   - Mock vector search to return this prompt
#   - Mock random() > 0.095 (rarely refine)
# 
# Input: agent_type="python-dev", prompt="Write a function"
# 
# Assertions:
#   - Returns existing refined_prompt
#   - Returns existing prompt_key
#   - source = "existing"
#   - No LLM API call made
```

**Test Case: New Prompt Creation**
```python
test_refine_prompt_create_new()
# Setup:
#   - Vector search returns no similar prompts
#   - OR returns low-scoring prompts (avg < 2.0)
#   - Mock random() < p_refine (will refine)
#
# Input: agent_type="rust-dev", prompt="Implement a trait"
#
# Assertions:
#   - LLM API called with correct context
#   - New prompt stored in DB with embedding
#   - Returns generated prompt_key
#   - source = "new"
```

**Test Case: Prompt Refinement**
```python
test_refine_prompt_refine_existing()
# Setup:
#   - Vector search returns prompt with score=2.5
#   - Mock random() < 0.679 (will refine)
#
# Input: agent_type="python-dev", prompt="Debug this code"
#
# Assertions:
#   - LLM called with existing prompt as context
#   - New refined prompt stored
#   - prior_refinement_id set correctly
#   - Returns new prompt_key
```

**Test Case: Error Handling - Invalid Agent Type**
```python
test_refine_prompt_invalid_agent_type()
# Input: agent_type="", prompt="test"
# Expected: MCP error response with code -32602 (Invalid params)
```

**Test Case: Error Handling - LLM Timeout**
```python
test_refine_prompt_llm_timeout()
# Setup: Mock LLM to timeout after 30s
# Expected: Graceful error, fallback to original prompt
```

#### 3.1.2 Tool: `simpa_update_result`

**Test Case: Successful Result Update**
```python
test_update_result_success()
# Setup: Existing prompt in DB with usage_count=5, average_score=3.2
#
# Input:
#   prompt_key=<valid_uuid>
#   action_score=4.5
#   files_modified=["src/main.py"]
#   diffs={"python": [{"file": "src/main.py", "diff": "..."}]}
#
# Assertions:
#   - prompt_history record created
#   - refined_prompts.usage_count = 6
#   - refined_prompts.average_score ≈ 3.42
#   - Distribution bin 4 incremented
#   - Returns {"success": true}
```

**Test Case: Invalid Prompt Key**
```python
test_update_result_invalid_key()
# Input: prompt_key="non-existent-uuid"
# Expected: Error response, prompt_key not found
```

**Test Case: Score Out of Range**
```python
test_update_result_score_out_of_range()
# Input: action_score=6.0 (valid: 1.0-5.0)
# Expected: Validation error
```

**Test Case: Concurrent Update Race Condition**
```python
test_update_result_concurrent()
# Setup: Two simultaneous updates to same prompt
# Expected: No lost updates, usage_count accurate
```

### 3.2 Vector Search Integration Tests

**File**: `tests/integration/test_vector_search.py`

```python
test_vector_search_top_k_accuracy()
# Insert 100 prompts with known similarities
# Query with test prompt
# Verify top-K results ordered by cosine similarity

test_vector_search_similarity_threshold()
# Configure threshold (e.g., 0.7)
# Insert prompts with varying similarity
# Verify only above-threshold results returned

test_vector_search_with_filters()
# Filter by agent_type="python-dev"
# Verify results constrained to type

test_vector_search_language_filter()
# Filter by main_language="rust"
# Verify language matching works

test_vector_search_performance()
# Measure: Query latency < 100ms for 10k prompts
```

### 3.3 LLM Integration Tests

**File**: `tests/integration/test_llm_integration.py`

```python
test_llm_refinement_prompt_structure()
# Verify prompt sent to LLM includes:
#   - Original prompt
#   - Policy context (Security, Coding, Testing, Linting)
#   - Top-K successful prompts as examples
#   - Clear instructions for refinement

test_llm_refinement_output_parsing()
# Mock LLM response with tags
# Verify parsing extracts refined prompt correctly

test_llm_refinement_quality_check()
# Verify refined prompt != original prompt (meaningful change)
# Verify refined prompt length reasonable (not empty, not 10x)
```

---

## 4. Database Tests

### 4.1 Schema Validation Tests

**File**: `tests/db/test_schema.py`

```python
test_refined_prompts_table_schema()
# Verify all columns present with correct types
# Verify primary key: id
# Verify unique constraint: prompt_key

test_prompt_history_table_schema()
# Verify foreign key: prompt_id → refined_prompts.id
# Verify JSONB column: diffs
# Verify array column: files_modified

test_pgvector_extension()
# Verify pgvector extension installed
# Verify VECTOR(768) column type supported

test_indexes()
# Verify index on embedding column (ivfflat or hnsw)
# Verify index on agent_type
# Verify index on created_at
```

### 4.2 Data Integrity Tests

**File**: `tests/db/test_integrity.py`

```python
test_foreign_key_cascade()
# Delete refined_prompts record
# Verify associated prompt_history records handled

test_prompt_key_uuid_format()
# Insert with invalid UUID format
# Expected: Constraint violation

test_score_decimal_precision()
# Insert score with 3 decimal places
# Verify storage as DECIMAL(3,2) rounds correctly

test_embedding_dimension_constraint()
# Attempt to insert vector with wrong dimensions
# Expected: Dimension mismatch error
```

### 4.3 Vector Operations Tests

**File**: `tests/db/test_vector_ops.py`

```python
test_cosine_similarity_function()
# Compute similarity between known vectors
# Verify: identical vectors = 1.0, orthogonal = 0.0

test_euclidean_distance_function()
# Compute L2 distance
# Verify mathematical correctness

test_vector_normalization()
# Test L2 normalization of embedding vectors

test_hnsw_index_query_performance()
# Build HNSW index on 100k vectors
# Measure approximate search latency
```

---

## 5. End-to-End Tests

### 5.1 Full Workflow Tests

**File**: `tests/e2e/test_workflows.py`

#### Test Case: New Prompt Bootstrap → Refinement → Feedback
```python
test_e2e_new_prompt_lifecycle()
# Step 1: Controller calls refine_prompt for new agent type
# Step 2: SIMPA creates initial prompt (no similar found)
# Step 3: Controller executes agent with refined prompt
# Step 4: Controller submits results (score=2.0)
# Step 5: Verify stats updated
# Step 6: Controller submits new similar request
# Step 7: Verify high refinement probability (81.8% at score=2.0)
# Step 8: New refined prompt created
# Step 9: Verify prior_refinement_id linkage
```

#### Test Case: Prompt Improvement Over Time
```python
test_e2e_prompt_evolution()
# Create prompt with initial score=2.0
# Simulate 10 iterations of refinement + feedback
# Track average_score trend
# Verify: Score improves or stabilizes by iteration 10
# Verify: Refinement probability decreases as score improves
```

#### Test Case: Agent Type Isolation
```python
test_e2e_agent_type_isolation()
# Create prompts for "python-dev" with high scores
# Create prompts for "rust-dev" with low scores
# Query for rust-dev with similar semantics
# Verify: Only rust-dev prompts considered (not polluted by python-dev)
```

### 5.2 Failure Recovery Tests

```python
test_e2e_db_connection_recovery()
# Simulate PostgreSQL connection drop during refinement
# Verify: Graceful error, no orphaned state

test_e2e_llm_rate_limit()
# Simulate LLM API rate limiting
# Verify: Exponential backoff, eventual success or timeout

test_e2e_embedding_service_down()
# Simulate embedding service unavailable
# Verify: Fallback or error with original prompt usable
```

---

## 6. Performance Benchmarks

### 6.1 Latency Benchmarks

**File**: `tests/perf/test_latency.py`

| Operation | Target | Maximum |
|-----------|--------|---------|
| Vector Search (10k prompts) | < 50ms | 100ms |
| Vector Search (100k prompts) | < 100ms | 200ms |
| LLM Refinement Call | < 2s | 5s |
| Refine Prompt (no LLM) | < 10ms | 25ms |
| Update Result | < 50ms | 100ms |
| End-to-End Refinement | < 5s | 10s |

```python
test_vector_search_latency_10k()
# Setup: 10,000 prompts in DB
# Measure: 100 queries, report p50, p95, p99

test_vector_search_latency_100k()
# Setup: 100,000 prompts in DB
# Measure: 100 queries, report p50, p95, p99

test_llm_refinement_latency()
# Measure: Time from LLM API call to response parsing
# Network latency excluded (mock for unit test)

test_end_to_end_refinement_latency()
# Measure: Full refine_prompt call with LLM
# Include embedding, vector search, LLM call, storage
```

### 6.2 Throughput Benchmarks

**File**: `tests/perf/test_throughput.py`

| Metric | Target | Minimum |
|--------|--------|---------|
| Refine Prompt RPS | 10/sec | 5/sec |
| Update Result RPS | 50/sec | 20/sec |
| Concurrent Connections | 20 | 10 |

```python
test_concurrent_refinement_throughput()
# Simulate 20 concurrent refine_prompt calls
# Measure: Total throughput, average latency

test_concurrent_update_throughput()
# Simulate 50 concurrent update_result calls
# Measure: Total throughput, check for race conditions

test_sustained_load_1min()
# Run at target RPS for 60 seconds
# Measure: Memory stability, no connection leaks
```

### 6.3 Memory Benchmarks

```python
test_embedding_cache_memory()
# Measure: Memory usage per cached embedding
# Target: < 10KB per embedding (768 floats * 4 bytes + overhead)

test_prompt_history_retention()
# 1M history records
# Measure: Query performance for stats aggregation
```

---

## 7. Test Environment Setup

### 7.1 Local Development

```bash
# PostgreSQL with pgvector (Docker)
docker run -d \
  --name simpa-test-db \
  -e POSTGRES_DB=simpa_test \
  -e POSTGRES_USER=test \
  -e POSTGRES_PASSWORD=test \
  -p 5433:5432 \
  ankane/pgvector:latest

# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v --cov=simpa --cov-report=term-missing
```

### 7.2 CI/CD Configuration

```yaml
# .github/workflows/test.yml
test:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: ankane/pgvector:latest
      env:
        POSTGRES_PASSWORD: test
        POSTGRES_DB: simpa_test
  steps:
    - uses: actions/checkout@v4
    - run: pip install -r requirements-dev.txt
    - run: pytest tests/ -v --cov=simpa --cov-fail-under=90
    - run: pytest tests/perf/ -m perf --benchmark-only
```

### 7.3 Test Data Fixtures

**File**: `tests/conftest.py`

```python
@pytest.fixture
def sample_prompts():
    """Generate 100 diverse prompts with known scores"""
    return [
        {"agent_type": "python-dev", "score": i % 5 + 1, ...}
        for i in range(100)
    ]

@pytest.fixture
def mock_llm_response():
    """Standard LLM refinement response"""
    return {
        "refined_prompt": "Improved prompt text...",
        "explanation": "Added context..."
    }

@pytest.fixture
def test_db(postgresql):
    """TestContainers PostgreSQL with pgvector"""
    yield postgresql
```

---

## 8. Testing Dependencies

```txt
# requirements-dev.txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-benchmark>=4.0.0
pytest-testcontainers>=0.1.0
hypothesis>=6.88.0      # Property-based testing
factory-boy>=3.3.0      # Test data generation
respx>=0.20.0           # HTTP mocking (for LLM API)
```

---

## 9. Test Execution Plan

### Phase 1: Unit Tests (Sprint 1)
- [ ] Sigmoid algorithm tests
- [ ] Score statistics tests
- [ ] Mock embedding service tests

### Phase 2: Integration Tests (Sprint 2)
- [ ] MCP tool handler tests
- [ ] Vector search tests
- [ ] LLM integration tests

### Phase 3: Database Tests (Sprint 2)
- [ ] Schema validation
- [ ] Vector operation tests
- [ ] Integrity constraint tests

### Phase 4: E2E & Performance (Sprint 3)
- [ ] Full workflow tests
- [ ] Latency benchmarks
- [ ] Throughput benchmarks

---

## 10. Success Criteria

✅ **All unit tests passing**: Sigmoid calculations accurate within 0.01  
✅ **Integration tests passing**: MCP tools handle all edge cases  
✅ **Database tests passing**: Vector search returns correct results  
✅ **E2E tests passing**: Full workflow completes successfully  
✅ **Performance targets met**: Latency benchmarks achieved  
✅ **Code coverage**: >90% for core logic, >80% for MCP handlers  

---

## Appendix: Test Data Samples

### Sample Prompts for Testing

| Agent Type | Original Prompt | Expected Refined Characteristics |
|------------|-----------------|----------------------------------|
| python-dev | "Write a function" | Type hints, docstring, error handling |
| rust-dev | "Implement a trait" | Generic bounds, lifetime annotations |
| architect | "Design a system" | Component breakdown, trade-offs |
| reviewer | "Review this code" | Checklist, security, performance |

### Score Distribution Test Data

```python
# For testing histogram accuracy
test_distribution = {
    1: 10,  # 10 prompts scored 1
    2: 20,  # 20 prompts scored 2
    3: 40,  # 40 prompts scored 3  
    4: 20,  # 20 prompts scored 4
    5: 10,  # 10 prompts scored 5
}
# Expected average: (1*10 + 2*20 + 3*40 + 4*20 + 5*10) / 100 = 3.0
```
