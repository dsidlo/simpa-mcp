# Refined Prompt: BM25 Hybrid Search Implementation

**Agent:** DT-Manager  
**Date:** March 4, 2026  
**Task Type:** Architecture Implementation  
**Priority:** High  
**Estimated Tokens:** ~4,000 for context window

---

## Original Request Summary

Implement BM25-like search for PostgreSQL 14.22 (which lacks pg_search extension from ParadeDB) and integrate it with SIMPA's existing vector search to create a hybrid search system for prompt retrieval.

---

## REFINED PROMPT

### Context

SIMPA currently uses PostgreSQL 14.22 with pgvector for embedding-based similarity search. The system retrieves up to 5 similar prompts using cosine similarity (threshold 0.7) but cannot perform keyword-based BM25 search since pg_search requires PostgreSQL 15+. This limits the ability to find prompts based on specific terms when semantic similarity fails.

### Task

As the DT-Manager, orchestrate the DyTopo crew to implement a **hybrid search system** that combines:
1. **Vector search** (existing): Top 5 results via pgvector cosine similarity
2. **BM25 search** (new): Top 5 results via pure SQL implementation
3. **LLM re-ranking**: Combine results and have the LLM select the best match
4. **Observability**: Trace logs for the entire refinement process

### Detailed Requirements

#### Phase 1: BM25 Stored Procedure (DT-Architect + DT-Developer)

**Create SQL Stored Procedures:**

1. **Document Statistics Table**
   ```sql
   CREATE TABLE bm25_stats (
       id SERIAL PRIMARY KEY,
       total_docs INTEGER,
       avg_doc_length FLOAT,
       term TEXT UNIQUE,
       doc_freq INTEGER,
       updated_at TIMESTAMP
   );
   ```

2. **BM25 Scoring Function**
   ```sql
   CREATE OR REPLACE FUNCTION bm25_score(
       query_terms TEXT[],
       doc_text TEXT,
       k1 FLOAT DEFAULT 1.2,
       b FLOAT DEFAULT 0.75
   ) RETURNS FLOAT AS $$
   -- Implementation: Calculate BM25 score for document
   -- Use: idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_len)))
   $$ LANGUAGE plpgsql;
   ```

3. **Hybrid Search Query**
   ```sql
   -- Retrieve top 5 BM25 results
   -- Retrieve top 5 vector results
   -- Return combined 10 with source indicators
   ```

#### Phase 2: Repository Layer Updates (DT-Developer)

**Update `RefinedPromptRepository`:**

```python
async def find_hybrid_similar(
    self,
    embedding: list[float],
    query_text: str,  # For BM25
    agent_type: str,
    vector_limit: int = 5,
    bm25_limit: int = 5,
    similarity_threshold: float = 0.7,
) -> HybridSearchResult:
    """
    Find similar prompts using both vector and BM25 search.
    
    Returns:
        HybridSearchResult with:
        - vector_results: List[RefinedPrompt]
        - bm25_results: List[RefinedPrompt]
        - combined: List[RefinedPrompt] (deduplicated)
    """
```

#### Phase 3: Search Logic Integration (DT-Developer)

**Update `PromptRefiner.build_context()`:**

```python
async def build_context_hybrid(
    self,
    original_prompt: str,
    agent_type: str,
    main_language: str | None,
    context: dict | None = None,
) -> str:
    # 1. Get vector results (5 prompts)
    # 2. Get BM25 results (5 prompts)
    # 3. Log token count for each result
    # 4. Pass all 10 to LLM for selection
    # 5. Return selected prompt + reasoning
```

#### Phase 4: Token Length Logging (DT-Developer)

**Add Token Counting:**

```python
import tiktoken

# In repository or refiner:
def count_tokens(text: str, model: str = "gpt-4") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Log for each of 10 results:
logger.debug(
    "token_count",
    prompt_id=str(prompt.prompt_key),
    original_tokens=count_tokens(prompt.original_prompt),
    refined_tokens=count_tokens(prompt.refined_prompt),
    total_tokens=count_tokens(prompt.original_prompt) + count_tokens(prompt.refined_prompt),
)
```

**Log Total Context Size:**
```python
# In build_context_hybrid:
total_context_tokens = sum(
    count_tokens(p.original_prompt) + count_tokens(p.refined_prompt)
    for p in combined_results
)
logger.debug("total_context_tokens", count=total_context_tokens)
```

#### Phase 5: LLM Selection Logic (DT-Developer + DT-Tester)

**Update LLM Context Format:**

```
You are selecting the best prompt from 10 candidates (5 from vector search, 5 from BM25).

For each candidate, you have:
- Source: "vector" or "bm25"
- Original prompt text
- Refined prompt text
- Score (vector similarity or BM25 score)

TASK:
1. Analyze all 10 candidates
2. Select the ONE that best matches the user's request
3. Provide reasoning for your selection
4. Indicate whether to reuse this prompt or create new

Consider:
- Semantic relevance (vector)
- Keyword/term overlap (BM25)
- Historical performance (usage_count, average_score)
- Specificity to the current context

Respond in format:
SELECTED_PROMPT: [number 1-10 or "NEW"]
SOURCE: [vector|bm25|new]
REASONING: [explanation]
CONFIDENCE: [0.0-1.0]
```

#### Phase 6: Trace-Level Logging (DT-Developer)

**Add Structured Trace Logging:**

```python
# In refiner.py - add trace logs for each phase:

# Phase 1: Hash Fast Path
trace_logger.trace("refinement.phase_start", phase="hash_fast_path", original_hash=original_hash)

# Phase 2: Embedding Generation
trace_logger.trace("refinement.embedding", 
    text_length=len(text_to_embed),
    cache_hit=is_cached,
    dimensions=settings.embedding_dimensions,
)

# Phase 3: Vector Search
trace_logger.trace("refinement.vector_search",
    query_embedding=embedding[:5],  # First 5 dimensions
    limit=settings.vector_search_limit,
    threshold=settings.vector_similarity_threshold,
    results_found=len(vector_results),
)

# Phase 4: BM25 Search
trace_logger.trace("refinement.bm25_search",
    query_terms=extracted_terms,
    limit=5,
    results_found=len(bm25_results),
)

# Phase 5: LLM Selection
trace_logger.trace("refinement.llm_selection",
    context_tokens=total_tokens,
    candidates_count=10,
    selected_index=selected_idx,
    confidence=confidence,
)

# Phase 6: Result Storage
trace_logger.trace("refinement.complete",
    action=action,  # "reuse" or "create"
    prompt_id=str(prompt_key),
    duration_ms=elapsed_ms,
)
```

**Enable Trace Logging in Config:**
```python
# In config.py:
trace_logging_enabled: bool = Field(default=True)
trace_log_level: Literal["trace", "debug", "info"] = Field(default="trace")
```

---

## Output Format

### 1. Deliverables

| File | Description |
|------|-------------|
| `sql/bm25_stored_procs.sql` | BM25 stored procedures and tables |
| `src/simpa/db/bm25_repository.py` | BM25 search repository methods |
| `tests/unit/test_bm25_search.py` | Unit tests for BM25 scoring |
| `tests/integration/test_hybrid_search.py` | Integration tests for hybrid flow |
| `docs/implementation/bm25-hybrid-search-*.md` | Implementation documentation |

### 2. Key Metrics to Validate

- [ ] BM25 scores calculated correctly (test with known corpus)
- [ ] Hybrid search returns exactly 10 prompts (5+5, deduplicated)
- [ ] Token counts logged for each of 10 results
- [ ] LLM successfully selects from combined results
- [ ] Trace logs output for all 8 refinement phases
- [ ] Performance: Hybrid search completes < 200ms

### 3. Testing Strategy

**Unit Tests:**
```python
def test_bm25_score_calculation():
    # Use classic BM25 test corpus
    
def test_hybrid_search_deduplication():
    # Ensure same prompt not in both vector and BM25 results
    
def test_token_count_logging():
    # Verify token counts logged correctly
```

**Integration Tests:**
```python
async def test_end_to_end_hybrid_refinement():
    # Full flow: original prompt → hybrid search → LLM selection → refined prompt
```

---

## DyTopo Crew Assignment

| Agent | Tasks |
|-------|-------|
| **DT-Architect** | Define BM25 SQL schema, API design for hybrid search |
| **DT-Developer** | Implement stored procedures, repository methods, LLM selection logic |
| **DT-Tester** | Write unit tests, integration tests, performance benchmarks |
| **DT-Reviewer** | Review SQL for injection safety, review token counting, review trace logging |
| **DT-Manager** (you) | Orchestrate workflow, resolve conflicts, validate acceptance criteria |

---

## REASONING

### Why BM25 Instead of Full-Text Search?

PostgreSQL's built-in `ts_rank`/`ts_rank_cd` provides basic full-text search but:
- Lacks field-length normalization (BM25's "b" parameter)
- No inverse document frequency tuning
- Less effective for short text (prompts are typically short)

Pure SQL BM25 implementation provides:
- Better ranking for short documents
- Tunable parameters (k1, b)
- Document length normalization
- Comparable performance on PostgreSQL 14

### Why Top 5 + Top 5?

- **5 vector**: Maintains current semantic similarity behavior
- **5 BM25**: Adds keyword-based recall for specific terms
- **10 total**: Stays within typical LLM context limits (~4K tokens for 10 prompts)
- **LLM selection**: Combines best of both worlds algorithmically + semantically

### Why Token Logging?

Critical for:
- Understanding context window usage
- Optimizing number of examples sent to LLM
- Budget estimation for LLM API costs
- Debugging "context too long" errors

---

## Dependencies

```toml
[tool.poetry.dependencies]
tiktoken = "^0.7.0"  # For token counting
```

## Configuration

```python
# Add to settings:
bm25_search_enabled: bool = Field(default=True)
bm25_k1: float = Field(default=1.2, ge=0.1, le=3.0)
bm25_b: float = Field(default=0.75, ge=0.0, le=1.0)
hybrid_search_limit: int = Field(default=5, ge=1, le=20)
```

---

## Acceptance Criteria

- [ ] All tests pass (`pytest tests/unit/test_bm25* tests/integration/test_hybrid*`)
- [ ] Trace logs show complete flow for sample refinements
- [ ] Token counts logged within ±5% of actual GPT-4 tokenization
- [ ] Hybrid search latency < 200ms p95
- [ ] No breaking changes to existing vector-only search
- [ ] Documentation updated with architecture decisions

---

**Generated by:** DT-Manager via SIMPA Refiner  
**Confidence:** 0.95  
**Refinement Type:** New Feature Implementation
