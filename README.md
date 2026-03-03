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

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone and setup
git clone https://github.com/yourusername/simpa-mcp.git
cd simpa-mcp
cp .env.example .env

# Start all services
make dev-setup

# Download models (one-time)
make pull-models

# Run migrations
make migrate

# Run tests
make test
```

### Option 2: Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Setup database (requires PostgreSQL + pgvector)
docker run -d --name simpa-db \
  -e POSTGRES_USER=simpa \
  -e POSTGRES_PASSWORD=simpa \
  -e POSTGRES_DB=simpa \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Run migrations
alembic upgrade head

# Start MCP server
python -m src.main
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

# Or use docker-compose (includes PostgreSQL + pgvector)
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

- [Test Suite Development](docs/implementation/test_suite_development.md) - Comprehensive testing guide
- [API Reference](docs/) - MCP tool documentation
- [Architecture Decisions](docs/) - ADRs and design patterns

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
