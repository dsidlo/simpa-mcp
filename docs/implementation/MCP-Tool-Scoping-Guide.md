# MCP Tool Scoping Guide

## Overview

SIMPA MCP tools support scoping capabilities that help agents define boundaries for their work. This reduces token waste, improves focus, and prevents modification of the wrong files.

## Scoping Levels

### 1. Project-Level Structure Hints

When creating a project, define its structure to guide agents:

```json
{
  "request": {
    "project_name": "my-api",
    "description": "REST API service",
    "main_language": "python",
    "project_structure": {
      "src_dirs": ["src/api/", "src/services/", "src/models/"],
      "test_dirs": ["tests/"],
      "entry_points": ["src/main.py", "src/cli.py"],
      "exclude": [".venv/", "__pycache__/", "node_modules/", "*.pyc"]
    }
  }
}
```

**Fields:**
- `src_dirs`: Root directories containing source code
- `test_dirs`: Locations of test files
- `entry_points`: Main application entry points
- `exclude`: Glob patterns for paths to ignore

### 2. Prompt-Level Scope Constraints

When refining a prompt, use the `context` dict to scope agent work:

```json
{
  "request": {
    "agent_type": "developer",
    "original_prompt": "Add authentication to the API",
    "main_language": "python",
    "project_id": "...",
    "context": {
      "target_dirs": ["src/api/auth/"],
      "target_files": ["src/api/routes.py"],
      "exclude_paths": ["tests/legacy/"],
      "scope": "API authentication layer only",
      "focus": ["security", "error-handling"]
    }
  }
}
```

**Context Fields:**
- `target_dirs`: Directories to focus on (restricts exploration)
- `target_files`: Specific files to modify
- `exclude_paths`: Explicit exclusions beyond defaults
- `scope`: High-level scope description
- `focus`: Priority aspects to emphasize

### 3. Result Feedback for Learning

After execution, report which files were actually touched:

```json
{
  "request": {
    "prompt_key": "...",
    "action_score": 4.5,
    "files_modified": ["src/api/auth.py", "src/config.py"],
    "files_added": ["tests/test_auth.py"],
    "diffs": {
      "src/api/auth.py": "..."
    }
  }
}
```

## Workflow: Scoping Best Practices

### Step 1: Create Project with Structure

```python
# Define project boundaries upfront
response = await create_project(CreateProjectRequest(
    project_name="web-api",
    project_structure={
        "src_dirs": ["src/api/", "src/services/"],
        "test_dirs": ["tests/"],
        "exclude": [".venv/", "__pycache__/"]
    }
))
```

### Step 2: Query for Structure Before Refining

```python
# Discover project layout
project = await get_project(GetProjectRequest(
    project_id="..."
))

# Use structure to inform scope
structure = project.project_structure
target_dirs = structure.get("src_dirs", [])
```

### Step 3: Refine with Explicit Scope

```python
# Scope refinement to specific areas
response = await refine_prompt(RefinePromptRequest(
    original_prompt="Fix the database queries",
    context={
        "target_dirs": ["src/db/", "src/models/"],
        "focus": ["performance", "sql-injection-prevention"],
        "scope": "database layer optimizations"
    }
))
```

### Step 4: Report Actual Scope

```python
# Report what was actually modified
await update_prompt_results(UpdatePromptResultsRequest(
    prompt_key=response.prompt_key,
    action_score=4.8,
    files_modified=["src/db/queries.py"],  # Actual scope
    files_added=[]
))
```

## Tool Reference

| Tool | Scoping Feature |
|------|-----------------|
| `create_project` | Define `project_structure` with src_dirs, exclude patterns |
| `get_project` | Retrieve full `project_structure` for scoping decisions |
| `list_projects` | Quick view with structure hints available |
| `refine_prompt` | Scope via `context.target_dirs`, `context.target_files`, `context.focus` |
| `update_prompt_results` | Report `files_modified`, `files_added` for scope tracking |

## Benefits

1. **Reduced Token Usage**: Agents don't explore irrelevant directories
2. **Improved Accuracy**: Clear boundaries prevent accidental modifications
3. **Better Reuse**: Similar scoped prompts can be matched more effectively
4. **Audit Trail**: Track which files are typically touched for each prompt type
5. **Progressive Discovery**: Start narrow, expand scope based on results

## Examples by Agent Type

### Developer Agent
```json
{
  "context": {
    "target_dirs": ["src/feature/"],
    "focus": ["maintainability", "type-safety"]
  }
}
```

### Architect Agent
```json
{
  "context": {
    "scope": "API design patterns",
    "target_dirs": ["src/api/", "docs/"],
    "focus": ["scalability", "observability"]
  }
}
```

### Tester Agent
```json
{
  "context": {
    "target_dirs": ["tests/"],
    "target_files": ["tests/test_feature.py"],
    "focus": ["edge-cases", "performance"]
  }
}
```
