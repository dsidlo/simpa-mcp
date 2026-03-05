# SIMPA - Self-Improving Meta Prompt Agent

> 🚀 **Transform your AI agents with self-optimizing prompt intelligence**

SIMPA is a Model Context Protocol (MCP) service that learns from every interaction to continuously improve prompt quality. It remembers what worked, refines what didn't, and automatically selects the best prompts for any situation.

## 🌟 Why SIMPA?

Every agent you deploy faces the same challenge: **getting the prompt right**. SIMPA solves this by:

- 📊 **Learning from feedback** - Automatically improves based on execution scores
- 🔍 **Semantic search** - Finds similar successful prompts using vector similarity
- 🧠 **Smart selection** - Chooses between refinement and reuse based on proven performance
- 🔗 **MCP Native** - Seamlessly integrates with any MCP-compatible agent controller

## 🏗️ Architecture

```mermaid
flowchart TB
    subgraph Controller["Agent Controller"]
        A[Agent Request]
    end
    
    subgraph SIMPA["SIMPA MCP Service"]
        direction TB
        R[Refiner] --> S[Selector]
        S --> V[Vector Store]
        S --> L[LLM Service]
        L --> E[Embedding Service]
    end
    
    subgraph Storage["Knowledge Base"]
        direction TB
        P[(PostgreSQL + pgvector)]
        H[Prompt History]
    end
    
    A -->|original_prompt| R
    V -->|similar_prompts| S
    S -->|refined_prompt| A
    S -->|store & learn| P
    P -->|usage_stats| S
    H -->|feedback_loop| S
    
    style Controller fill:#e1f5fe
    style SIMPA fill:#fff3e0
    style Storage fill:#e8f5e9
```

## 🔄 Prompt Lifecycle

SIMPA sits between the **Agent Orchestrator** and **Implementation Agents**, continuously learning from each interaction:

```mermaid
flowchart LR
    AO[Agent Orchestrator] -->|prompt| SR[SIMPA Prompt<br/>Refinement]
    SR -->|refined-prompt| IA[Implementation<br/>Agent]
    IA -->|Actions, Results<br/>& Products| RA[Reviewing Agent]
    RA -->|refined-prompt-score| SR2[SIMPA]
    SR2 -->|learn & improve| SR
    
    style AO fill:#e1f5fe,color:#000000
    style SR fill:#fff3e0,color:#000000
    style IA fill:#fce4ec,color:#000000
    style RA fill:#f3e5f5,color:#000000
    style SR2 fill:#fff3e0,color:#000000
```

**The Flow:**

1. **Agent Orchestrator** → Sends raw `prompt` to SIMPA
2. **SIMPA** → Returns `refined-prompt` (structured with ROLE, GOAL, REQUIREMENTS)
3. **Implementation Agent** → Executes actions using refined prompt, produces results/products
4. **Reviewing Agent** → Evaluates outcomes, generates `refined-prompt-score`
5. **SIMPA** → Receives score, learns what works, improves future refinements

This closed feedback loop ensures prompts get better with every execution.

## ✨ Features

| Feature | Description |
|---------|-------------|
| **🤖 MCP Protocol** | Native Model Context Protocol support for universal agent integration |
| **🔎 Vector Search** | pgvector-powered similarity search for prompt retrieval |
| **📈 Self-Improvement** | Sigmoid-based probability for intelligent refinement vs reuse |
| **🎯 Multi-Provider** | OpenAI, Anthropic, and Ollama support for embeddings and LLM |
| **📊 Observability** | Structured logging with structlog and comprehensive metrics |
| **🛡️ Security** | PII detection and input validation built-in |
| **🧪 Tested** | 274 automated tests with 100% pass rate |

## 📋 Prerequisites

Before installing SIMPA, ensure you have the following:

### Required

| Component | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.10+ | Runtime environment |
| **PostgreSQL** | 14+ | Database with pgvector extension |
| **Docker** | Latest | Required for running tests with TestContainers |
| **Git** | Latest | Clone repository |

> **Note:** PostgreSQL and Ollama are expected to be installed and running separately (not via Docker) for normal operation. Docker is only required for the automated test suite.

### For Ollama (Local Models - Recommended)

| Component | Purpose |
|-----------|---------|
| **Ollama** | Local LLM & embedding inference |
| **nomic-embed-text** | Embedding model (pull via `ollama pull nomic-embed-text`) |
| **llama3.2** | LLM for prompt refinement (pull via `ollama pull llama3.2`) |

### For Cloud Providers (Optional)

> **🔐 Security Best Practice:** Provider API keys (OpenAI, Anthropic, Google, Azure) should be kept in your user home directory at `~/.env` rather than in the project `.env` file. This prevents accidental commits of sensitive credentials to version control.
>
> Create `~/.env` with your provider keys:
> ```bash
> # ~/.env - User-level secrets (not committed)
> OPENAI_API_KEY=sk-...
> ANTHROPIC_API_KEY=sk-ant-...
> GOOGLE_API_KEY=...
> AZURE_OPENAI_KEY=...
> ```
> SIMPA will automatically load keys from `~/.env` if available.

- **OpenAI API Key** - Get from [platform.openai.com](https://platform.openai.com)
- **Anthropic API Key** - Get from [console.anthropic.com](https://console.anthropic.com)
- **Azure OpenAI** - Azure subscription with OpenAI service
- **Google Gemini** - Get from [Google AI Studio](https://makersuite.google.com)

### System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **RAM** | 4 GB | 8 GB+ |
| **Disk** | 2 GB free | 10 GB+ |
| **CPU** | 2 cores | 4 cores+ |

> **Note:** For local Ollama models, CPU is sufficient but GPU acceleration significantly improves performance.

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended for Development/Testing)

This option runs PostgreSQL and Ollama in Docker containers for easy development and testing:

```bash
# Clone and setup
git clone https://github.com/yourusername/simpa-mcp.git
cd simpa-mcp
cp .env.example .env

# Start all services (PostgreSQL + Ollama in Docker)
make dev-setup

# Download models (one-time)
make pull-models

# Run migrations
make migrate

# Run tests
make test
```

> **For Production Use:** Install PostgreSQL and Ollama directly on your system instead of using Docker. See the Manual Setup section below.

### Option 2: Manual Setup (Production/Existing Services)

Use this if you already have PostgreSQL and Ollama installed locally.

**Prerequisites:**
- PostgreSQL 14+ with pgvector extension installed
- Ollama running locally (with `nomic-embed-text` and `llama3.2` pulled)

```bash
# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env to match your PostgreSQL and Ollama settings

# Run migrations
alembic upgrade head

# Start MCP server
python -m src.main
```

**Quick PostgreSQL setup with Docker (if needed):**
```bash
# Only if you don't have PostgreSQL installed locally
docker run -d --name simpa-db \
  -e POSTGRES_USER=simpa \
  -e POSTGRES_PASSWORD=simpa \
  -e POSTGRES_DB=simpa \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

## 🔌 Adding SIMPA to Your MCP Configuration

SIMPA works with any MCP-compatible client (Cursor, Claude Desktop, Windsurf, etc.).

### Step 1: Install SIMPA Server

#### Option A: Global Installation (Easiest)

```bash
# Clone the repository
git clone https://github.com/dsidlo/simpa-mcp.git
cd simpa-mcp

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install in editable mode
pip install -e .

# Install MCP dependencies
pip install fastmcp asyncpg pgvector sqlalchemy

# Setup environment
cp .env.example .env
# Edit .env with your configuration (see Configuration section below)

# Run database migrations
alembic upgrade head
```

#### Option B: Docker (Recommended for Production)

```bash
# Build the MCP server image
docker build --target production -t simpa-mcp:latest .

# Or use docker compose (includes PostgreSQL + pgvector)
docker-compose up -d
```

### Step 2: Configure Your MCP Client

Add SIMPA to your MCP client's configuration file:

#### Cursor (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "simpa-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/simpa-mcp",
        "run",
        "--env",
        "/absolute/path/to/simpa-mcp/.env",
        "python",
        "-m",
        "src.main"
      ],
      "env": {
        "PYTHONPATH": "/absolute/path/to/simpa-mcp/src"
      }
    }
  }
}
```

#### Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "simpa-mcp": {
      "command": "/absolute/path/to/simpa-mcp/.venv/bin/python",
      "args": [
        "-m",
        "src.main"
      ],
      "env": {
        "DATABASE_URL": "postgresql://simpa:simpa@localhost:5432/simpa",
        "EMBEDDING_PROVIDER": "ollama",
        "EMBEDDING_MODEL": "nomic-embed-text",
        "EMBEDDING_BASE_URL": "http://localhost:11434",
        "LLM_PROVIDER": "ollama",
        "LLM_MODEL": "llama3.2",
        "PYTHONPATH": "/absolute/path/to/simpa-mcp/src"
      }
    }
  }
}
```

#### Generic MCP Configuration

```json
{
  "mcpServers": {
    "simpa-mcp": {
      "name": "SIMPA Prompt Refinement",
      "description": "Self-improving prompt optimization service",
      "command": "python",
      "args": [
        "-m",
        "src.main",
        "--mcp",
        "stdio"
      ],
      "workingDirectory": "/absolute/path/to/simpa-mcp",
      "envFile": "/absolute/path/to/simpa-mcp/.env"
    }
  }
}
```

#### Using uv (Recommended)

This configuration ensures the server runs from the source directory and uses uv for dependency management:

```json
{
  "mcpServers": {
    "simpa-mcp": {
      "command": "/bin/bash",
      "args": [
        "-c",
        "cd /path/to/simpa-mcp && uv run python src/main.py --log-level debug --log-file /tmp/simpa-mcp.log"
      ]
    }
  }
}
```

> **Note:** Replace `/path/to/simpa-mcp` with your actual installation path. Using `bash -c` with `cd` ensures the server runs from the project root where `pyproject.toml` and `.env` are located.

### Step 3: Install MCP Inspector (Optional, for Testing)

```bash
# Install MCP Inspector globally
npm install -g @anthropics/mcp-inspector

# Test your SIMPA server
mcp-inspector --server "uv --directory /path/to/simpa-mcp run python -m src.main"
```

### Step 4: Verify Installation

In your MCP client (Cursor/Claude Desktop), you should see:

- ✅ **Available Tools**: `refine_prompt`, `update_prompt_results`
- ✅ **Server Status**: Connected
- ✅ **Capabilities**: Prompt refinement enabled

### 🛠️ Troubleshooting

#### "Command not found: uv"

Install uv first:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### "ModuleNotFoundError: No module named 'src'"

Ensure `PYTHONPATH` includes the `src` directory:
```bash
export PYTHONPATH="/absolute/path/to/simpa-mcp/src:$PYTHONPATH"
```

#### Database Connection Errors

Verify PostgreSQL is running with pgvector:
```bash
# Check if pgvector extension is available
psql -d simpa -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### MCP Server Not Responding

Test manually:
```bash
cd /path/to/simpa-mcp
source .venv/bin/activate
python -m src.main --help
```

## 🔧 Configuration

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql://simpa:simpa@localhost:5432/simpa

# Embedding (OpenAI or Ollama)
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434

# LLM (OpenAI, Anthropic, or Ollama)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_TEMPERATURE=0.7

# MCP Server
MCP_TRANSPORT=stdio
```

### Command Line Options

SIMPA supports several command line flags for runtime configuration:

```bash
# Show all available options
python -m src.main --help

# Common options
--transport {stdio,sse}     # MCP transport protocol (default: stdio)
--log-level {debug,info,warn,error,fatal}  # Logging level (default: info)
--log-file PATH             # Path to log file (default: /tmp/simpa-mcp.log)
--log-console               # Also log to console (stderr)
--init-db                   # Initialize database and exit
```

#### Project-Associated Prompt Development (`--project-id-required`)

Enable **strict project association mode** to enforce that all prompts must be linked to a project:

```bash
# Require project_id for all prompt refinements
python -m src.main --project-id-required
```

When enabled, calling `refine_prompt` without a `project_id` returns a helpful response guiding the agent to:
1. **List existing projects** - View available projects to find a suitable match
2. **Create a new project** - Use `create_project` if no suitable project exists
3. **Resubmit with project_id** - Retry the refinement with the chosen project

**Why use project association?**

- **Cross-project learning**: Prompts refined for one Python web project can benefit similar Flask/Django projects
- **Knowledge clustering**: Projects with similar tech stacks (React+Node, Python+PostgreSQL) share prompt patterns
- **Relevance scoring**: Prompt selection considers project context for better matches
- **Team organization**: Different teams/projects have distinct prompt preferences and patterns

**Example workflow:**
```bash
# Start server with strict project mode
python -m src.main --project-id-required

# Agent workflow:
# 1. First call without project_id → returns list of existing projects
# 2. Agent picks or creates project → gets project_id
# 3. Resubmit with project_id → prompt is refined and associated with project
```

## 🛠️ MCP Tools

### `refine_prompt`

Intelligently refine prompts before agent execution.

```python
# Request
{
  "original_prompt": "Write a function to sort a list",
  "agent_type": "developer",
  "main_language": "python"
}

# Response
{
  "refined_prompt": "Write a Python function that takes a list of integers...",
  "prompt_key": "uuid-v4",
  "action": "refine|new|reuse",
  "confidence_score": 0.95,
  "similar_prompts_found": 3
}
```

### `update_prompt_results`

Provide feedback to improve future prompts.

```python
# Request
{
  "prompt_key": "uuid-v4",
  "action_score": 4.5,
  "test_passed": true,
  "files_modified": ["main.py"],
  "lint_score": 0.95
}

# Response
{
  "success": true,
  "usage_count": 5,
  "average_score": 4.25
}
```

## 📝 Prompt Refinement Examples

SIMPA transforms vague user requests into structured, actionable specifications.

### Example 1: Developer Agent

**Original Prompt:**
```
Build a REST API for managing tasks.
```

**Refined Prompt:**
```
ROLE: Senior Backend Developer
GOAL: Build a REST API for managing tasks.
CONSTRAINTS: Your output will be only a descriptive overview of what the API will do.
REQUIREMENTS:
- Define all REST endpoints (GET, POST, PUT, DELETE) with their URLs and purposes
- Explicitly specify request/response JSON formats for each endpoint
- Include pagination, filtering, and sorting capabilities for task listing
- Describe authentication mechanism (JWT or API key based)
- Define error response formats and standard HTTP status codes
- Outline rate limiting strategy if applicable
OUTPUT: Structured API specification document.
SUCCESS: All endpoints are well-defined, formats are validated, and specification is ready to implement.
AUTONOMY: You may choose implementation technology and framework.
FALLBACK: If a task requirement is unclear, ask for clarification or document your assumptions.
```

---

### Example 2: Architect Agent

**Original Prompt:**
```
Design a caching strategy for the product catalog.
```

**Refined Prompt:**
```
ROLE: Software Architect
GOAL: Design a caching strategy for the product catalog.
CONSTRAINTS: Output will be descriptive only; no actual implementation code.
REQUIREMENTS:
- Identify data access patterns (read-heavy, write-heavy, or mixed)
- Design cache-invalidation strategy (time-based, event-driven, or hybrid)
- Define cache key structure and naming conventions
- Specify cache-aside, write-through, or write-behind patterns
- Address cache consistency, eviction policies, and TTL configuration
- Consider multi-tier caching (in-memory + distributed)
- Document potential issues: stale data, thundering herd, cache penetration
OUTPUT: Architecture document detailing caching strategy.
SUCCESS: Design addresses scalability, performance, and data consistency.
AUTONOMY: Choose appropriate caching technology (Redis, Memcached, Caffeine).
FALLBACK: If data volume or access patterns are unclear, document assumptions.
```

---

### Example 3: Tester Agent

**Original Prompt:**
```
Write tests for the login module.
```

**Refined Prompt:**
```
ROLE: QA Engineer
GOAL: Write tests for the login module.
CONSTRAINTS: Provide complete test scenarios and detailed expected outcomes, no code.
TEST CATEGORIES:
- Unit Tests: Each function/method tested in isolation with mocks
- Integration Tests: Service interactions (DB, external auth providers)
- Edge Cases: Empty input, SQL injection attempts, XSS payloads
- Boundary Tests: Max username length, password complexity rules
- Error Paths: Invalid credentials, account locked, service unavailable
- Load Tests: Concurrent login attempts
REQUIREMENTS:
- Use GIVEN/WHEN/THEN format for each scenario
- Define specific test data (usernames, passwords)
- Specify expected status codes and error messages
- Identify test dependencies and setup requirements
OUTPUT: Comprehensive test specification document.
SUCCESS: All happy paths and edge cases are covered.
AUTONOMY: Choose testing frameworks and assertion styles.
FALLBACK: If authentication flow is unclear, document assumptions.
```

---

### Example 4: Reviewer Agent (with scope constraints)

**Original Prompt:**
```
Review error handling in the codebase.
```

**Scope Context:**
```json
{
  "target_dirs": ["src/services/", "src/utils/"],
  "target_files": ["src/services/user_service.py"],
  "scope": "error handling patterns only",
  "focus": ["security", "logging", "user-experience"]
}
```

**Refined Prompt:**
```
ROLE: Security-Focused Code Reviewer
GOAL: Review error handling patterns in the codebase.
CONSTRAINTS: Review only within assigned scope and files:
  - target_dirs: src/services/, src/utils/
  - target_files: src/services/user_service.py
  - focus: security, logging, user-experience
  - scope: error handling patterns only
CONTEXT: Production code review process
OUTPUT: Line-by-line comments and summary report
SUCCESS: Critical issues identified, recommendations actionable
AUTONOMY: Can use static analysis tools within scope
FALLBACK: Ask if scope unclear

Review Checklist:
- Security: Exception leaks sensitive data, proper sanitization
- Logging: Appropriate log levels, no PII exposure
- User Experience: Helpful error messages, graceful degradation
- Code Quality: Consistent patterns, avoid catch-all exceptions
- Documentation: Error scenarios documented, recovery paths clear
```

> **Note:** When scope context is provided (target_dirs, target_files, scope, focus), SIMPA injects these constraints into the refined prompt above the CONSTRAINTS section, limiting the agent's work to the specified boundaries.

## 🧠 Self-Improvement Algorithm

SIMPA uses a sigmoid function to intelligently balance exploration (refinement) vs exploitation (reuse):

```
p_refine(S) = 1 / (1 + exp(k * (S - mu)))
```

**Where:**
- `S` = Average score (1.0 - 5.0)
- `k` = Steepness (default: 1.5)
- `mu` = Midpoint (default: 3.0)

**Refinement Probability:**

| Score | Probability |
|-------|-------------|
| ⭐ 1.0 | ~95% 🔄 Refine heavily |
| ⭐⭐ 2.0 | ~82% 🔄 Likely refine |
| ⭐⭐⭐ 3.0 | ~50% ⚖️ Balance point |
| ⭐⭐⭐⭐ 4.0 | ~18% ✅ Start reusing |
| ⭐⭐⭐⭐⭐ 5.0 | ~5% ✅ Reuse proven |

## 📊 Database Schema

### `refined_prompts` - The Prompt Knowledge Base

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `prompt_key` | UUID | Public identifier for MCP tools |
| `embedding` | vector(768) | Semantic embedding for similarity search |
| `agent_type` | VARCHAR | Agent specialization |
| `main_language` | VARCHAR | Primary programming language |
| `original_prompt` | TEXT | Raw input prompt |
| `refined_prompt` | TEXT | Optimized/expanded version |
| `average_score` | FLOAT | Running average of action scores |
| `usage_count` | INTEGER | Total times used |
| `score_dist_1-5` | INTEGER | Histogram of score distribution |

### `prompt_history` - Learning Data

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `prompt_id` | UUID | FK to refined_prompts |
| `action_score` | FLOAT | Score for this execution |
| `test_passed` | BOOLEAN | Test results |
| `lint_score` | FLOAT | Code quality score |
| `files_modified` | JSON | Changed files |
| `diffs` | JSON | Code diffs by language |

## 🧪 Development

### Running Tests

```bash
# All tests (requires Docker)
pytest

# Integration tests only
pytest tests/integration -v

# With coverage
pytest --cov=src --cov-report=html
```

**Current Status:** 274 tests passing ✅

### Database Migrations

```bash
# Create new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 🐳 Docker

> **Note:** Docker is primarily used for **testing** SIMPA in an isolated environment. It can also be used as an alternative to installing PostgreSQL directly on your machine during development.
>
> For production deployments, you may prefer running SIMPA directly with your existing PostgreSQL instance rather than containerizing both services.

### Quick Start with Docker Compose (Testing)

The easiest way to test SIMPA without installing PostgreSQL locally:

```bash
# Start PostgreSQL with pgvector in Docker
docker-compose up -d postgres

# Initialize the database
python -m src.main --init-db

# Run the MCP server
python -m src.main
```

This uses the `docker-compose.test.yml` which only starts the PostgreSQL service—SAMPA runs natively on your machine using the containerized database.

### Production Deployment

```bash
# Build optimized image
docker build --target production -t simpa-mcp:latest .

# Run with environment
docker run -d \
  --name simpa-mcp \
  -e DATABASE_URL=postgresql://... \
  -e OPENAI_API_KEY=sk-... \
  simpa-mcp:latest
```

### Multi-stage Targets

| Target | Purpose | Size |
|--------|---------|------|
| `builder` | Compile dependencies | Base |
| `development` | Live code mounting | ~2GB |
| `production` | Optimized runtime | ~700MB |

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [SIMPA Process Architecture](docs/implementation/SIMPA-Process-Architecture.md) | System architecture, data flow, and component design |
| [Test Suite Development](docs/implementation/test_suite_development.md) | Comprehensive testing guide and test development |
| [API Reference](docs/) - MCP tool documentation
| [Architecture Decisions](docs/) - ADRs and design patterns

## 📈 What's Next?

- [ ] Multi-agent prompt coordination
- [ ] Prompt lineage tracking
- [ ] A/B testing framework
- [ ] Prompt security scanning
- [ ] Custom embedding models

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests (we have 274 as examples!)
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

---

<p align="center">
  <strong>SIMPA</strong> - Making AI prompts smarter, one interaction at a time.
  <br>
  <a href="https://github.com/yourusername/simpa-mcp">GitHub</a> •
  <a href="https://example.com/docs">Documentation</a> •
  <a href="https://example.com/discord">Discord</a>
</p>
