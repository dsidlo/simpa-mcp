# SIMPA Pi Extension

JSON-RPC bridge for integrating SIMPA (Self-Improving Meta Prompt Agent) with [pi](https://github.com/mariozechner/pi) coding agent.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           pi Agent                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  simpa.ts Extension                                        │ │
│  │  - Spawns Python process on first call                     │ │
│  │  - Manages JSON-RPC over stdio                            │ │
│  │  - Registers 8 custom tools                                │ │
│  └────────────────────┬────────────────────────────────────────┘ │
│                       │ stdio (JSON-RPC)                          │
│  ┌────────────────────▼────────────────────────────────────────┐ │
│  │  jsonrpc_server.py                                         │ │
│  │  - Reads NDJSON requests from stdin                       │ │
│  │  - Routes to service_api.py functions                     │ │
│  │  - Writes JSON responses to stdout                        │ │
│  └────────────────────┬────────────────────────────────────────┘ │
└───────────────────────┼─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│  service_api.py                                                  │
│  - Pure business logic (DB, embeddings, LLM)                    │
│  - No transport-specific code                                  │
│  - Shared between MCP and JSON-RPC servers                       │
└─────────────────────────────────────────────────────────────────┘
```

### Design Decisions

- **JSON-RPC 2.0 over stdio**: No network ports, no HTTP overhead, simple and reliable
- **Lazy initialization**: Server spawns on first tool access (~2-3s), stays hot afterwards
- **Shared service layer**: `service_api.py` contains all business logic, used by both MCP and JSON-RPC transports
- **Pip-installable**: Extension auto-detects development vs installed mode

## Installation

### Step 1: Install SIMPA Python Module

```bash
# From PyPI (when published)
pip install simpa-mcp

# Or from source
git clone https://github.com/yourusername/simpa-mcp.git
cd simpa-mcp
pip install -e .
```

### Step 2: Configure Database

SIMPA requires PostgreSQL with pgvector:

```bash
# Set connection string
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/simpa"

# Or use config file
export SIMPA_CONFIG_PATH=/path/to/config.yaml
```

### Step 3: Install Pi Extension

```bash
# Create extensions directory if it doesn't exist
mkdir -p ~/.pi/agent/extensions

# Copy the extension
cp src/pi/agent/extensions/simpa.ts ~/.pi/agent/extensions/

# Restart pi
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMPA_PYTHON` | Python executable path | `python` |
| `SIMPA_ROOT` | Development install path (optional) | Auto-detected |
| `DATABASE_URL` | PostgreSQL connection string | From config |

## Usage

### First Access (Cold Start)

The SIMPA server starts automatically on first tool call:

```
/simpa_health
```

You'll see in the output:
```
[SIMPA] Spawning JSON-RPC server...
[SIMPA] Server ready
SIMPA status: healthy (1.0.0)
Timestamp: 2025-03-05T19:30:00
```

### Available Tools

| Tool | Description |
|------|-------------|
| `/simpa_refine_prompt` | Refine prompts using intelligent prompt engineering |
| `/simpa_update_results` | Update prompt performance metrics |
| `/simpa_create_project` | Create a new project for organizing prompts |
| `/simpa_get_project` | Get project details by ID or name |
| `/simpa_list_projects` | List all projects |
| `/simpa_activate_prompt` | Activate a deactivated prompt |
| `/simpa_deactivate_prompt` | Deactivate a prompt |
| `/simpa_health` | Check SIMPA service health |

### Example: Refine a Prompt

```
/simpa_refine_prompt agent_type="developer" original_prompt="Write a function to sort a list" main_language="python" project_id="550e8400-e29b-41d4-a716-446655440000"
```

Response:
```markdown
**Refined Prompt**

Write a Python function that sorts a list of integers using an efficient algorithm. Include type hints, docstrings, and error handling for edge cases.

---
**Source:** new | **Action:** refine
**Prompt Key:** 550e8400-e29b-41d4-a716-446655440001
```

### Example: Update Results

```
/simpa_update_results prompt_key="550e8400-e29b-41d4-a716-446655440001" action_score=4.5 files_modified=["src/sort.py"] test_passed=true lint_score=0.95
```

### Example: Create Project

```
/simpa_create_project project_name="my-api" description="REST API service" main_language="python" library_dependencies=["fastapi", "sqlalchemy"]
```

## Development

### Testing the JSON-RPC Server

```bash
# Start the server manually
cd /path/to/simpa-mcp
python -m simpa.jsonrpc_server

# Send a request (in another terminal)
echo '{"jsonrpc":"2.0","id":"1","method":"health_check","params":{}}' | python -m simpa.jsonrpc_server
```

### Debugging

Enable verbose logging:

```bash
export SIMPA_LOG_LEVEL=DEBUG
export SIMPA_LOG_FORMAT=json
```

Check if extension loaded:
```
/pi extensions
# Should show: simpa (8 tools)
```

### Troubleshooting

**"Could not find SIMPA project root"**
- If using development install: `export SIMPA_ROOT=/path/to/simpa-mcp`
- If using pip install: Ensure `simpa` module is in Python path (`which python` + `pip list | grep simpa`)

**"Timeout waiting for SIMPA server to start"**
- Check database connection: `python -m simpa.db.check` (if available)
- Check logs: Look for errors in stderr output
- Test manually: `python -m simpa.jsonrpc_server` should print "SIMPA JSON-RPC server ready"

**"Method not found"**
- Server is running but might be an old version. Restart pi to kill and respawn.

## Architecture Details

### Request Flow

1. **Pi calls tool** → Extension's `execute()` function
2. **Ensure process** → Spawn Python if not running
3. **Send JSON-RPC** → Write NDJSON to stdin
4. **Python processes** → Route to `service_api.py` function
5. **Database/LLM** → Business logic executes
6. **Response** → JSON written to stdout
7. **Parse response** → TypeScript resolves Promise
8. **Return to Pi** → Tool result displayed

### Why stdio?

- **No ports**: No firewall issues, no port conflicts
- **Lifecycle management**: Process dies when parent dies
- **Security**: Isolated to local machine
- **Simplicity**: No HTTP stack, no certificates

### Future Extensions

This architecture supports adding alternative transports:

```
src/simpa/
├── service_api.py          # Shared business logic
├── jsonrpc_server.py       # stdio transport (current)
├── mcp_server.py           # MCP/FastMCP transport
├── http_server.py          # HTTP/REST transport (future)
└── grpc_server.py          # gRPC transport (future)
```

## License

Same as SIMPA project (see root LICENSE file)
