#!/usr/bin/env python3
"""SIMPA Find Similar Prompts Script

Finds similar prompts using vector search.
"""

import asyncio
import os
import sys

# Add simpa src to path
SIMPA_DIR = "/home/dsidlo/workspace/simpa-mcp"
sys.path.insert(0, os.path.join(SIMPA_DIR, "src"))

# Set environment variables before any simpa imports
os.environ["LOG_LEVEL"] = "INFO"
os.environ["JSON_LOGGING"] = "false"
os.environ["LITELLM_LOG"] = "ERROR"

# Configure logging first
import logging
logging.basicConfig(level=logging.WARNING)

# Monkey-patch structlog to add trace method
def _trace_method(self, event, **kw):
    """Mock trace method that falls back to debug."""
    self.debug(event, **kw)

import structlog
# Patch the BoundLogger class to have trace method
structlog.stdlib.BoundLogger.trace = _trace_method

structlog.configure(
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# Now import simpa modules
from simpa.db.engine import get_db_session
from simpa.db.repository import RefinedPromptRepository
from simpa.embedding.service import EmbeddingService


async def main():
    query = os.environ.get("_SIMPA_QUERY", "").strip()
    
    if not query:
        print("Error: No query provided in _SIMPA_QUERY environment variable")
        print("Usage: _SIMPA_QUERY='your search query' python simpa-find-similar.py")
        return 1
    
    print(f"Searching for prompts similar to: {query[:100]}...")
    print()
    
    async with get_db_session() as session:
        repo = RefinedPromptRepository(session)
        embedding_service = EmbeddingService()
        
        embedding = await embedding_service.embed(query)
        
        results = await repo.find_similar(
            embedding=embedding,
            agent_type="developer",
            limit=5
        )
        
        print(f"Found {len(results)} similar prompts:")
        print()
        
        for i, r in enumerate(results, 1):
            print(f"{i}. {r.original_prompt[:100]}...")
            print(f"   Score: {r.average_score:.2f}, Usage: {r.usage_count}")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
