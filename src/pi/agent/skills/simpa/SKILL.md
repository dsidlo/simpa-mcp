# SIMPA Skill

**Skill ID:** simpa-user  
**Purpose:** Use SIMPA's intelligent prompt refinement for structured, high-quality LLM prompts

## Overview

SIMPA (Structured Intelligent Multi-Prompt Assistant) provides a database-backed prompt refinement service that:
- Stores and retrieves refined prompts based on context
- Scores prompt effectiveness using feedback loops
- Associates prompts with projects for organization
- Tracks prompt iteration and version history

## When to Use SIMPA

**Use SIMPA when:**
- Crafting complex prompts for multi-step tasks
- Refining prompts for specific agent types (architect, developer, tester, reviewer)
- Building a reusable prompt library with proven effectiveness
- Optimizing prompts based on past performance scores

**SIMPA excels at:**
- Code generation prompts
- Architecture/design specification prompts
- Testing and validation prompts
- Review and analysis prompts

## Hints for Effective SIMPA Usage

### Intent Scoping

**Agent Type Selection (Required):**
- `architect` - System design, API specs, architecture diagrams
- `developer` - Code implementation, bug fixes, integration
- `tester` - Test writing, test execution, bug identification
- `reviewer` - Code review, security audits, optimization
- `manager` - Orchestration, task routing, coordination
- `researcher` - Information gathering, analysis, exploration

**Domain Categories (Optional but Recommended):**
- backend, frontend, api, database, infrastructure
- game-development, web-development, mobile, ai/ml
- security, testing, documentation, devops

**Primary Language Context (Optional):**
- python, typescript, javascript, rust, go, c#, c++, java
- framework-specific: react, django, fastapi, unity, etc.

### Project Scoping

**Associate prompts with projects for:**
- Context-aware retrieval (similar prompts from same project)
- Organization and discoverability
- Team-wide prompt sharing
- Version tracking per project

**Create project first if needed:**
```
Tool: simpa_create_project
- project_name: "my-project"
- main_language: "python"
- description: "My project description"
```

### Context Provision

**Provide context for better refinement:**
- Current codebase structure
- Existing patterns or conventions
- Specific constraints or requirements
- Related files or modules
- Previous attempts or partial solutions

**Structured context helps SIMPA:**
- Understand the problem space
- Align refinements with project conventions
- Avoid repeating exploration steps

### Tags for Categorization

**Use tags for discoverability:**
- Technical tags: "database", "auth", "api", "ui"
- Task tags: "create", "update", "refactor", "debug"
- Scope tags: "endpoint", "model", "service", "component"
- Quality tags: "performance", "security", "maintainability"

## Usage Pattern

### 1. Health Check (Optional but Recommended)

```
Tool: simpa_health
No parameters
```

### 2. Refine Prompt

```
Tool: simpa_refine_prompt
Required:
- original_prompt: "Your natural language task description"
- agent_type: "architect | developer | tester | reviewer | manager | researcher"

Optional (but highly recommended):
- project_id: "uuid-of-project" (from simpa_create_project or simpa_list_projects)
- context: { /* structured context object */ }
- main_language: "python | typescript | c# | etc."
- other_languages: ["rust", "go"]  // list of additional languages
- domain: "backend | frontend | api | database | etc."
- tags: ["tag1", "tag2", "tag3"]
```

### 3. Use Refined Prompt + Callback Pattern

The response contains:
- `refined_prompt`: The optimized, structured prompt
- `prompt_key`: UUID to reference this prompt for updates
- `source`: "cache" (retrieved) or "new" (created)
- `action`: "retrieved" or "new"

**CRITICAL: The refined prompt MUST include callback instructions** for the executing agent:

```
After completing this task, you MUST call the SIMPA agent
@simpa-specialist with:
- prompt_key: "uuid-from-this-refinement"
- original_prompt: "original-user-request"
- action_score: 1-5 (how well did this refined prompt work?)
- execution_details:
  - files_created: ["path/to/file.py"]
  - files_modified: ["path/to/file.py"]
  - files_deleted: ["path/to/file.py"]
  - records_created: [{"table": "users", "count": 5}]
  - records_updated: [{"table": "orders", "count": 3}]
  - records_deleted: [{"table": "logs", "count": 10}]
  - test_results: {passed: 15, failed: 2, coverage: "85%"}
  - errors_encountered: ["error1", "error2"]
  - duration_ms: 12345
- context_summary: "Brief description of what was accomplished"
```

**Why this matters:** SIMPA learns from feedback. Without callback data, we cannot improve prompt quality over time.

**Example workflow:**
1. User asks: "Create a REST API for user management"
2. Agent calls `simpa_refine_prompt` with parameters
3. SIMPA returns structured prompt **with callback instructions embedded**
4. Agent (developer) uses refined prompt to generate code
5. **Developer agent calls @simpa-specialist with:**
   - prompt_key, original_prompt, action_score
   - All files created/modified/deleted
   - Test results
   - Any errors or issues encountered
6. SIMPA updates the prompt's performance metrics
7. Future similar prompts benefit from this scored feedback

### 4. The Executing Agent Reports Completion (Feedback Loop)

After performing the task described in the refined prompt:

**Step A: Gather Results**
- What files were created/modified/deleted?
- What database records were changed?
- Did tests pass?
- How long did it take?
- Any errors or unexpected behavior?

**Step B: Call SIMPA Agent**
```
@simpa-specialist Record task completion:
- prompt_key: "uuid-from-step-2"
- original_prompt: "exact-original-user-request"
- action_score: 4  // How effective was the refined prompt?
- execution_duration_ms: 45000
- files_created: ["src/user/api.py", "src/user/models.py"]
- files_modified: ["src/main.py"]
- files_deleted: []
- test_results: {passed: 12, failed: 0, coverage: 92}
- lint_score: 0.95
- validation_results: {type_check: "passed", security_scan: "passed"}
- errors: []
- notes: "Refined prompt was well-structured but could specify auth requirements more clearly"
```

**Step C: SIMPA Updates & Learns**
- Updates usage_count, average_score
- Associates this outcome with the prompt_key
- Future refinements consider this feedback

### 5. Update With Results (Direct Tool Access)

If calling @simpa-specialist is not available, use the tool directly:

```
Tool: simpa_update_results
Required:
- prompt_key: "uuid-from-refine-response"
- action_score: 1-5  // How effective was the prompt?

Optional:
- execution_duration_ms: Time taken
- files_modified: ["src/user/api.py"]
- files_added: ["src/user/models.py"]
- files_deleted: ["src/legacy.py"]
- diffs: { "src/user/api.py": "patch content" }
- validation_results: { tests: "passed", lint: 0.95 }
- test_passed: true/false
- lint_score: 0.0-1.0
- security_scan_passed: true/false
- executed_by_agent: "developer-agent-1"
```

## Response Interpretation

### Source Interpretation
- **source: "cache"** - Retrieved existing high-quality prompt
- **source: "new"** - Created new prompt entry
- **source: "llm"** - LLM refinement on the fly

### Action Interpretation
- **action: "retrieved"** - Perfect match found, using as-is
- **action: "hybrid"** - Retrieved with minor context adjustments
- **action: "new"** - First-time prompt or significantly different context

## Project Management

### Create Project
```
Tool: simpa_create_project
- project_name: "my-awesome-project"
- description: "A Python API service for..."
- main_language: "python"
- other_languages: ["javascript", "html"]
- library_dependencies: ["fastapi", "sqlalchemy", "pydantic"]
- project_structure: { "src_dirs": ["src/"], "test_dirs": ["tests/"] }
```

### List Projects
```
Tool: simpa_list_projects
Optional filters:
- main_language: "python"
- limit: 50
```

### Get Project Details
```
Tool: simpa_get_project
- project_id: "uuid" OR project_name: "my-project"
```

## Prompt Lifecycle Management

### Deactivate Underperforming Prompts
```
Tool: simpa_deactivate_prompt
- prompt_key: "uuid"
```

### Reactivate Previously Deactivated
```
Tool: simpa_activate_prompt
- prompt_key: "uuid"
```

## Common Patterns

### Pattern 1: Architecture Specification (with full feedback loop)
```
User: "Design the database schema"
→ @simpa-specialist Refine with:
    agent_type: "architect",
    domain: "database",
    original_prompt: "Design the database schema",
    context: { "existing_models": [...], "requirements": [...] }
  
→ SIMPA returns refined prompt **with callback instructions**
→ Use refined_prompt for architecture response
→ Execute architecture design task
→ Architect agent gathers:
    - files_created: ["docs/architecture/db-schema.md"]
    - models_defined: ["User", "Order", "Product"]
    - assumptions_made: ["Using PostgreSQL", "UUID primary keys"]
    - duration: 30 minutes
    
→ Architect agent calls @simpa-specialist:
    "Record completion:
    - prompt_key: uuid
    - action_score: 5
    - files_created: [...]
    - context_summary: 'Created schema for 12 entities with relationships'"
    
→ SIMPA learns: This prompt produces excellent architecture specs
```

### Pattern 2: Code Generation (full feedback loop)
```
User: "Implement user authentication"
→ @simpa-specialist Refine with:
    agent_type: "developer",
    domain: "backend",
    main_language: "python",
    original_prompt: "Implement user authentication",
    tags: ["auth", "api", "security"]
  
→ SIMPA returns refined prompt with callback instructions
→ Developer uses refined prompt to generate code
→ Developer implements JWT auth with 5 new files
→ Developer agent calls @simpa-specialist:
    "Record completion:
    - prompt_key: uuid
    - action_score: 4
    - files_created: ['src/auth/jwt.py', 'src/auth/middleware.py', ...]
    - files_modified: ['src/main.py']
    - test_results: {passed: 8, failed: 0}
    - lint_score: 0.94
    - notes: 'Refined prompt was good but could specify token expiration'"
    
→ SIMPA learns: Auth prompts score well, consider adding expiration guidance
```

### Pattern 3: Testing (full feedback loop)
```
User: "Write tests for the API"
→ @simpa-specialist Refine with:
    agent_type: "tester",
    domain: "testing",
    original_prompt: "Write tests for the API",
    context: { "endpoints": [...], "coverage_target": "80%" }
  
→ SIMPA returns refined prompt with callback instructions
→ Tester generates comprehensive test suite
→ Tester runs tests: 45 pass, 3 fail
→ Tester agent calls @simpa-specialist:
    "Record completion:
    - prompt_key: uuid
    - action_score: 3
    - files_created: ['tests/test_api.py', 'tests/fixtures.py']
    - test_results: {passed: 45, failed: 3, coverage: "78%"}
    - errors: ['Missing JWT token in 3 tests']
    - notes: 'Refined prompt missed auth context for test setup'"
    
→ SIMPA learns: Test prompts need explicit auth context
```

## Feedback Loop is Critical

**Without callback data:**
- SIMPA cannot learn which prompts work best
- No improvement over time
- Every prompt is treated as brand new

**With callback data:**
- High-scoring prompts are retrieved first
- Low-scoring prompts are refined or deactivated
- Context-aware matching improves
- Team benefits from collective prompt intelligence

## Agent Responsibility

**Every agent using a SIMPA-refined prompt MUST:**

1. Identify themselves when reporting (e.g., "Reporting as architect-agent")
2. Capture all file CRUD operations
3. Record test/lint/validation results
4. Rate the prompt effectiveness honestly (1-5)
5. Provide notes for improvement
6. Call @simpa-specialist or use simpa_update_results tool

**Failure to report means:**
- SIMPA cannot validate prompt quality
- Future users get unproven prompts
- Team loses institutional knowledge
- No continuous improvement

## Quick Reference: Callback Data to Collect

| Category | What to Capture |
|----------|-----------------|
| **Identity** | Your agent_type, name, version |
| **Timing** | Start time, end time, duration_ms |
| **Files** | created[], modified{}, deleted[] |
| **Records** | Tables affected, insert/update/delete counts |
| **Quality** | test_passed, lint_score, security_scan_passed |
| **Results** | validation_results, errors[], warnings[] |
| **Subjective** | action_score (1-5), notes for improvement |

## Sample Callback Message

```
@simpa-specialist Record task completion:

PROMPT_KEY: a1b2c3d4-e5f6-7890-abcd-ef1234567890
ORIGINAL_PROMPT: "Create REST API for user management"

ACTION_SCORE: 4

EXECUTION_SUMMARY:
- Duration: 12 minutes (720000ms)
- Agent: developer-agent-v2
- Success: true (all requirements met)

FILES:
- Created: src/user/api.py, src/user/models.py, src/user/schemas.py
- Modified: src/main.py (added routes), src/config.py (added settings)
- Deleted: None

RECORDS:
- Database migrations: 2 (create_users_table, create_user_profiles)
- Configuration entries: 3 (JWT secret, token expiry, refresh policy)

QUALITY_METRICS:
- Tests: 18/18 passed (100%)
- Coverage: 94%
- Lint: 0.98 (pylint)
- Security: passed (bandit scan)
- Type check: passed (mypy)

VALIDATION:
- API spec validated: OpenAPI 3.0 compliant
- Integration tests: All auth flows working

ISSUES_NOTED:
- Refined prompt could mention refresh token expiry
- Would benefit from mentioning rate limiting

NARRATIVE:
"Refined prompt was well-structured. JWT implementation clear. 
Missing explicit mention of rate limiting and token refresh 
mechanism, had to infer from context."
```

## Important Notes

- **Cache Hit**: When source is "cache", the prompt was used before and proven effective
- **Action Score**: Rate 1-5 based on how well the refined prompt achieved the goal
- **Context Matters**: Providing project_id and context significantly improves retrieval quality
- **Feedback Loop**: Always update results to improve future retrievals
- **Prompt Key**: Save this to update the prompt's performance metrics later
