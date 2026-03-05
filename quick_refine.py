#!/usr/bin/env python3
"""Quick test of refine_prompt functionality."""

import asyncio
import os

# Set env vars from mcp.json
os.environ.update({
    "DATABASE_URL": "postgresql://dsidlo:rexrabbit@127.0.0.1:5432/simpa",
    "EMBEDDING_PROVIDER": "ollama",
    "EMBEDDING_MODEL": "nomic-embed-text:latest",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    "LLM_MODEL": "xai/grok-4-1-fast-non-reasoning",
    "PYTHONPATH": "./src",
    "FASTMCP_SHOW_SERVER_BANNER": "false",
    "LITELLM_LOG": "ERROR",
})

import sys
sys.path.insert(0, './src')

from simpa.mcp_server import refine_prompt, RefinePromptRequest
from simpa.db.engine import init_db, AsyncSessionLocal

from unittest.mock import AsyncMock, MagicMock


class MockContext:
    """Mock MCP context for testing."""
    def __init__(self):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = {
            "embedding_service": AsyncMock(),
            "llm_service": AsyncMock(),
        }


async def main():
    """Test refine_prompt directly."""
    # Initialize database
    await init_db()
    
    prompt = """Add a field to deactivate prompts, 
- Change the vector search for prompts to include a bm25 search.
- The queries for prompts should dis-regard deactivated prompts.
- Add an endpoints to activate and deactivate prompts. 
- Create Tests for the new features."""
    
    print(f"Original prompt:\n{prompt}\n")
    print("="*60)
    print("Refining...")
    print("="*60 + "\n")
    
    request = RefinePromptRequest(
        original_prompt=prompt,
        agent_type="developer",
        main_language="python",
        tags=["database", "search", "testing", "api"]
    )
    
    ctx = MockContext()
    
    # Set up mock returns
    ctx.request_context.lifespan_context["embedding_service"].embed.return_value = [0.1] * 768
    ctx.request_context.lifespan_context["llm_service"].complete.return_value = """This is a refined prompt focusing on database and search functionality:

Task: Implement soft delete/is_active field for prompts, add BM25 hybrid search, and create activation/deactivation endpoints."""
    
    try:
        response = await refine_prompt(request, ctx)
        
        print(f"Action: {response.action}")
        print(f"Prompt Key: {response.prompt_key}")
        print(f"Confidence: {response.confidence_score}")
        print(f"\nRefined Prompt:\n{response.refined_prompt}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
