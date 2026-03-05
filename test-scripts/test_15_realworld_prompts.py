"""Test 15 real-world prompts with different agent types and scoping options."""

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastmcp import Context

# Add src to path
import sys
sys.path.insert(0, '/home/dsidlo/workspace/simpa-mcp/src')

from simpa.mcp_server import (
    RefinePromptRequest,
    refine_prompt,
    create_project,
    CreateProjectRequest,
)
from simpa.db.models import RefinedPrompt, Project
from simpa.db.engine import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from simpa.db.models import Base


# Test data: 15 real-world prompts with different agent types
TEST_PROMPTS = [
    # Architect prompts (4)
    {
        "agent_type": "architect",
        "original_prompt": "Design a microservices architecture for an e-commerce platform with high availability",
        "main_language": "python",
        "context": {},
    },
    {
        "agent_type": "architect",
        "original_prompt": "Create API gateway patterns for handling rate limiting and authentication",
        "main_language": "python",
        "context": {
            "target_dirs": ["src/api/", "src/gateway/"],
            "scope": "API layer design patterns only",
            "focus": ["scalability", "security", "observability"],
        },
    },
    {
        "agent_type": "architect",
        "original_prompt": "Design event-driven architecture for inventory management system",
        "main_language": "python",
        "context": {},
    },
    {
        "agent_type": "architect",
        "original_prompt": "Propose database sharding strategy for multi-tenant SaaS application",
        "main_language": "python",
        "context": {
            "target_dirs": ["src/db/", "docs/architecture/"],
            "scope": "Data layer architecture",
            "focus": ["performance", "isolation"],
        },
    },
    # Developer prompts (5)
    {
        "agent_type": "developer",
        "original_prompt": "Implement user authentication with JWT tokens and refresh mechanism",
        "main_language": "python",
        "context": {},
    },
    {
        "agent_type": "developer",
        "original_prompt": "Create a function to process CSV files and validate data formats",
        "main_language": "python",
        "context": {
            "target_dirs": ["src/data_processing/"],
            "target_files": ["src/data_processing/csv_handler.py"],
            "scope": "CSV data processing module",
            "focus": ["error-handling", "performance"],
        },
    },
    {
        "agent_type": "developer",
        "original_prompt": "Build REST API endpoints for CRUD operations on user profiles",
        "main_language": "python",
        "context": {},
    },
    {
        "agent_type": "developer",
        "original_prompt": "Add caching layer using Redis for frequently accessed product data",
        "main_language": "python",
        "context": {
            "target_dirs": ["src/cache/", "src/services/"],
            "scope": "Caching implementation",
            "focus": ["performance", "consistency"],
        },
    },
    {
        "agent_type": "developer",
        "original_prompt": "Implement webhook handler with retry logic and exponential backoff",
        "main_language": "python",
        "context": {},
    },
    # Tester prompts (3)
    {
        "agent_type": "tester",
        "original_prompt": "Write comprehensive test suite for payment processing module",
        "main_language": "python",
        "context": {},
    },
    {
        "agent_type": "tester",
        "original_prompt": "Create integration tests for order workflow including edge cases",
        "main_language": "python",
        "context": {
            "target_dirs": ["tests/integration/"],
            "target_files": ["tests/integration/test_orders.py"],
            "scope": "Order workflow integration tests",
            "focus": ["edge-cases", "error-paths"],
        },
    },
    {
        "agent_type": "tester",
        "original_prompt": "Add load testing scenarios for checkout API endpoints",
        "main_language": "python",
        "context": {},
    },
    # Reviewer prompts (3)
    {
        "agent_type": "reviewer",
        "original_prompt": "Review authentication module for security vulnerabilities and best practices",
        "main_language": "python",
        "context": {},
    },
    {
        "agent_type": "reviewer",
        "original_prompt": "Audit database query patterns for SQL injection risks and performance issues",
        "main_language": "python",
        "context": {
            "target_dirs": ["src/db/", "src/queries/"],
            "scope": "Database access layer review",
            "focus": ["security", "performance", "injection-prevention"],
        },
    },
    {
        "agent_type": "reviewer",
        "original_prompt": "Review error handling patterns across the codebase for consistency",
        "main_language": "python",
        "context": {},
    },
]


class MockContext:
    """Mock MCP context for testing."""
    def __init__(self):
        self.request_context = MagicMock()
        embedding_service = MagicMock()
        embedding_service.embed = AsyncMock(return_value=[0.1] * 768)
        embedding_service.close = AsyncMock()
        
        llm_service = MagicMock()
        # Generate contextual refined prompts based on input
        llm_service.complete = AsyncMock(side_effect=self._mock_llm_response)
        llm_service.close = AsyncMock()
        
        self.request_context.lifespan_context = {
            "embedding_service": embedding_service,
            "llm_service": llm_service,
        }
    
    def _mock_llm_response(self, *args, **kwargs) -> str:
        """Generate mock LLM response based on prompt content.
        
        Receives prompt as first positional argument when used with AsyncMock.
        """
        # Get the prompt (first positional argument)
        prompt = args[0] if args else ""
        
        # Extract agent type and scope info from the prompt
        prompt_lower = prompt.lower()
        if "architect" in prompt_lower:
            return self._architect_response(prompt)
        elif "developer" in prompt_lower:
            return self._developer_response(prompt)
        elif "tester" in prompt_lower:
            return self._tester_response(prompt)
        elif "reviewer" in prompt_lower:
            return self._reviewer_response(prompt)
        return "Refined: Enhance clarity and add specific implementation details."
    
    def _architect_response(self, prompt: str) -> str:
        return """Architectural Design Task:

CONTEXT:
- Focus onscalability, maintainability, and extensibility
- Consider integration points and system boundaries
- Document trade-offs and rationale

REQUIREMENTS:
1. Define component boundaries and interfaces
2. Specify communication patterns (sync/async)
3. Address data consistency and availability
4. Include monitoring and observability considerations
5. Provide migration strategy from current state

DELIVERABLES:
- Architecture diagrams (C4 model)
- Interface contracts (OpenAPI/AsyncAPI)
- Decision records (ADRs)
- Risk assessment and mitigation strategies"""
    
    def _developer_response(self, prompt: str) -> str:
        return """Development Task:

IMPLEMENTATION GUIDELINES:
1. Follow language-specific best practices and idioms
2. Add comprehensive error handling with specific exception types
3. Include input validation and sanitization
4. Write self-documenting code with clear naming
5. Optimize for readability over cleverness

ACCEPTANCE CRITERIA:
- [ ] Function handles edge cases (empty input, None values, large data)
- [ ] Unit tests cover happy path and error cases (>80% coverage)
- [ ] Performance benchmarks meet defined SLAs
- [ ] Documentation includes usage examples
- [ ] Security review passed (no injection risks, proper auth checks)

DELIVERABLES:
- Source code with inline documentation
- Unit tests with mocking for external dependencies
- Integration test demonstrating end-to-end flow
- README with setup and usage instructions"""
    
    def _tester_response(self, prompt: str) -> str:
        return """Testing Task:

TEST STRATEGY:
1. Unit tests: Isolate components, mock dependencies
2. Integration tests: Verify component interactions
3. E2E tests: Validate complete user workflows
4. Performance tests: Verify under expected load
5. Security tests: Check for common vulnerabilities

TEST CASE CATEGORIES:
- Happy path: Normal expected usage
- Edge cases: Boundary values, empty inputs
- Error paths: Exceptions, failures, timeouts
- Concurrent scenarios: Race conditions, resource contention
- Data variations: Large datasets, special characters

REQUIREMENTS:
- Use descriptive test names explaining the scenario
- Follow Arrange-Act-Assert pattern
- Include setup/teardown for test isolation
- Parameterize tests for multiple data sets
- Mock external services and time-dependent operations

DELIVERABLES:
- Test files with >= 85% code coverage
- Test data factories/fixtures
- Performance benchmarks with assertions
- Documentation of uncovered edge cases"""
    
    def _reviewer_response(self, prompt: str) -> str:
        return """Code Review Task:

REVIEW CHECKLIST:

SECURITY:
- [ ] Input validation prevents injection attacks
- [ ] Authentication/authorization checks present
- [ ] Secrets not hardcoded, use proper key management
- [ ] Error messages don't leak sensitive information
- [ ] Rate limiting and DoS protections considered

CODE QUALITY:
- [ ] Follows DRY principle, no unnecessary duplication
- [ ] Single Responsibility Principle observed
- [ ] Functions/methods are focused and cohesive
- [ ] Naming is clear, consistent, and descriptive
- [ ] Complexity is manageable (cyclomatic < 10)

PERFORMANCE:
- [ ] Database queries are optimized (N+1 avoided)
- [ ] Expensive operations cached when appropriate
- [ ] Resource leaks prevented (connections, files)
- [ ] Algorithmic complexity is appropriate

TESTING:
- [ ] Tests cover critical paths and edge cases
- [ ] Mocking is appropriate, not over-specified
- [ ] Test data is realistic and representative

DOCUMENTATION:
- [ ] Complex logic has explanatory comments
- [ ] Public APIs are documented
- [ ] README updated if needed

REVIEW OUTPUT:
- Summary of findings (critical, warning, info)
- Specific line-by-line comments
- Recommendations with code examples
- Risk assessment for merging"""


async def setup_test_data(db_session):
    """Create test project if needed, or return existing one."""
    from simpa.db.models import Project
    from sqlalchemy import select
    import uuid
    
    # Check if project already exists
    result = await db_session.execute(
        select(Project).where(Project.project_name == "realworld-test-project")
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return str(existing.id)
    
    project = Project(
        project_name="realworld-test-project",
        description="Test project for 15 real-world prompts",
        main_language="python",
    )
    db_session.add(project)
    await db_session.flush()
    # Don't refresh - just return the ID
    return str(project.id)


async def run_single_test(
    prompt_data: dict,
    db_session: AsyncSession,
    mock_context: MockContext,
    project_id: str,
) -> dict:
    """Run a single prompt refinement test."""
    # Patch AsyncSessionLocal
    from unittest.mock import patch
    
    class MockSessionContextManager:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    def mock_session_local():
        return MockSessionContextManager(db_session)
    
    with patch("simpa.mcp_server.AsyncSessionLocal", mock_session_local):
        request = RefinePromptRequest(
            original_prompt=prompt_data["original_prompt"],
            agent_type=prompt_data["agent_type"],
            main_language=prompt_data["main_language"],
            project_id=project_id,
            context=prompt_data.get("context", {}),
        )
        
        try:
            response = await refine_prompt(request, mock_context)
            return {
                "agent_type": prompt_data["agent_type"],
                "original_prompt": prompt_data["original_prompt"][:80] + "..." if len(prompt_data["original_prompt"]) > 80 else prompt_data["original_prompt"],
                "refined_prompt": response.refined_prompt[:200] + "..." if len(response.refined_prompt) > 200 else response.refined_prompt,
                "action": response.action,
                "has_scope": bool(prompt_data.get("context")),
                "success": True,
            }
        except Exception as e:
            return {
                "agent_type": prompt_data["agent_type"],
                "original_prompt": prompt_data["original_prompt"][:80] + "...",
                "refined_prompt": f"ERROR: {str(e)[:100]}",
                "action": "error",
                "has_scope": bool(prompt_data.get("context")),
                "success": False,
            }


async def run_all_tests():
    """Run all 15 test prompts."""
    # Setup database connection
    from simpa.config import settings
    
    # Convert Pydantic PostgresDsn to string and swap for asyncpg
    db_url = str(settings.database_url)
    if "psycopg2" in db_url:
        db_url = db_url.replace("psycopg2", "asyncpg")
    elif "postgresql://" in db_url and "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    
    print(f"Using database URL: {db_url[:40]}...")
    
    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
    )
    
    async with engine.connect() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.commit()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    results = []
    
    async with async_session() as session:
        project_id = await setup_test_data(session)
        mock_context = MockContext()
        
        for i, prompt_data in enumerate(TEST_PROMPTS, 1):
            print(f"\n[{i}/15] Testing: {prompt_data['agent_type']} - {prompt_data['original_prompt'][:50]}...")
            result = await run_single_test(prompt_data, session, mock_context, project_id)
            results.append(result)
            print(f"   Action: {result['action']} | Scoped: {result['has_scope']} | Success: {result['success']}")
    
    await engine.dispose()
    return results


def format_results_table(results: list[dict]) -> str:
    """Format results as a markdown table."""
    lines = [
        "| # | Agent Type | Scoping | Original Prompt | Refined Prompt | Action |",
        "|---|------------|---------|-----------------|----------------|--------|",
    ]
    
    for i, r in enumerate(results, 1):
        scope_icon = "✅" if r["has_scope"] else "❌"
        original = r["original_prompt"].replace("|", "\\|")
        refined = r["refined_prompt"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {i} | {r['agent_type']} | {scope_icon} | {original} | {refined} | {r['action']} |")
    
    return "\n".join(lines)


def main():
    """Main test runner."""
    print("=" * 80)
    print("TESTING 15 REAL-WORLD PROMPTS WITH SIMPA REFINEMENT")
    print("=" * 80)
    
    # Run the async tests
    results = asyncio.run(run_all_tests())
    
    # Generate summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    by_agent = {}
    scoped_count = 0
    success_count = 0
    
    for r in results:
        agent = r["agent_type"]
        if agent not in by_agent:
            by_agent[agent] = {"total": 0, "scoped": 0, "success": 0}
        by_agent[agent]["total"] += 1
        if r["has_scope"]:
            by_agent[agent]["scoped"] += 1
            scoped_count += 1
        if r["success"]:
            by_agent[agent]["success"] += 1
            success_count += 1
    
    print(f"\nTotal prompts tested: {len(results)}")
    print(f"Successful refinements: {success_count}/{len(results)}")
    print(f"With scoping: {scoped_count}/{len(results)}")
    print(f"Without scoping: {len(results) - scoped_count}/{len(results)}")
    
    print("\nBy Agent Type:")
    for agent, stats in by_agent.items():
        print(f"  {agent}: {stats['success']}/{stats['total']} success, {stats['scoped']}/{stats['total']} scoped")
    
    # Format table
    print("\n" + "=" * 80)
    print("RESULTS TABLE")
    print("=" * 80)
    print("\n" + format_results_table(results))
    
    return results


if __name__ == "__main__":
    results = main()
