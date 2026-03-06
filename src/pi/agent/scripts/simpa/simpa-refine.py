#!/usr/bin/env python3
"""SIMPA Prompt Refinement Script

Refines a prompt using the SIMPA-MCP service.
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
from simpa.llm.service import LLMService
from simpa.prompts.refiner import PromptRefiner


async def main():
    original_prompt = os.environ.get("_SIMPA_PROMPT", "").strip()
    
    if not original_prompt:
        print("Error: No prompt provided in _SIMPA_PROMPT environment variable")
        print("Usage: _SIMPA_PROMPT='your prompt here' python simpa-refine.py")
        return 1
    
    print("=" * 70)
    print("ORIGINAL PROMPT:")
    print("=" * 70)
    print(original_prompt[:200] + "..." if len(original_prompt) > 200 else original_prompt)
    print()
    
    async with get_db_session() as session:
        repo = RefinedPromptRepository(session)
        embedding_service = EmbeddingService()
        llm_service = LLMService()
        
        refiner = PromptRefiner(repo, embedding_service, llm_service)
        
        result = await refiner.refine(
            original_prompt=original_prompt,
            agent_type="developer",
            main_language="python"
        )
        
        print()
        print("=" * 70)
        print("REFINED PROMPT:")
        print("=" * 70)
        print(result.get("refined_prompt", result.get("prompt", "N/A")))
        print()
        print("=" * 70)
        print("RATIONALE:")
        print("=" * 70)
        print(result.get("rationale", "N/A"))
        print()
        print(f"Agent Type: {result.get('agent_type', 'N/A')}")
        print(f"Language: {result.get('main_language', 'N/A')}")
        print(f"Version: {result.get('refinement_version', 'N/A')}")
        print()
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
