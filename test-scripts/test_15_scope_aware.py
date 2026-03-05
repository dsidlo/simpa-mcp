"""Test 15 real-world prompts with different agent types and scoping options.

This version includes scope-aware mock LLM responses."""

import asyncio
import uuid
import json
from typing import Any, Dict
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
    """Mock MCP context for testing with scope-aware responses."""
    
    def __init__(self):
        self.request_context = MagicMock()
        embedding_service = MagicMock()
        embedding_service.embed = AsyncMock(return_value=[0.1] * 768)
        embedding_service.close = AsyncMock()
        
        llm_service = MagicMock()
        llm_service.complete = AsyncMock(side_effect=self._mock_llm_response)
        llm_service.close = AsyncMock()
        
        self.request_context.lifespan_context = {
            "embedding_service": embedding_service,
            "llm_service": llm_service,
        }
    
    def _extract_scoping_info(self, prompt: str) -> Dict[str, Any]:
        """Extract scoping context from the prompt sent to LLM."""
        try:
            # The prompt contains RefinePromptRequest as JSON - extract context
            if '"context":' not in prompt:
                return {}
                
            # Find the context object
            start = prompt.find('"context":') + len('"context":')
            
            # Extract braces with proper nesting
            brace_count = 0
            in_string = False
            result = ""
            
            for char in prompt[start:]:
                if char == '"' and (not result or result[-1] != '\\'):
                    in_string = not in_string
                elif char == '{' and not in_string:
                    brace_count += 1
                elif char == '}' and not in_string:
                    brace_count -= 1
                    if brace_count == 0:
                        result += char
                        break
                result += char
            
            if result.strip():
                return json.loads(result)
        except:
            pass
        return {}
    
    def _format_scope_section(self, context: Dict[str, Any]) -> str:
        """Format scoping context into a readable section."""
        if not context:
            return ""
            
        parts = []
        
        if context.get('scope'):
            parts.append(f"SCOPE: {context['scope']}")
        
        if context.get('focus'):
            parts.append(f"FOCUS AREAS: {', '.join(context['focus'])}")
        
        if context.get('target_dirs'):
            parts.append(f"TARGET DIRECTORIES: {', '.join(context['target_dirs'])}")
        
        if context.get('target_files'):
            parts.append(f"TARGET FILES: {', '.join(context['target_files'])}")
        
        if parts:
            return "SCOPE CONTEXT:\n" + "\n".join(f"- {p}" for p in parts) + "\n"
        return ""
    
    def _get_original_prompt(self, prompt: str) -> str:
        """Extract original prompt from the full prompt."""
        try:
            if '"original_prompt":' in prompt:
                start = prompt.find('"original_prompt":') + len('"original_prompt":')
                if prompt[start:start+1] == '"':
                    start += 1
                    end = prompt.find('",', start)
                    return prompt[start:end].replace('\\"', '"')
        except:
            pass
        return ""
    
    def _mock_llm_response(self, *args, **kwargs) -> str:
        """Generate mock LLM response that INCLUDES scope context."""
        # Get the prompt (first positional argument)
        prompt = args[0] if args else ""
        
        # Extract scoping info from the request
        scope_context = self._extract_scoping_info(prompt)
        original_prompt = self._get_original_prompt(prompt)
        
        # Extract agent type from the prompt
        prompt_lower = prompt.lower()
        
        if "architect" in prompt_lower:
            return self._architect_response(prompt, scope_context, original_prompt)
        elif "developer" in prompt_lower:
            return self._developer_response(prompt, scope_context, original_prompt)
        elif "tester" in prompt_lower:
            return self._tester_response(prompt, scope_context, original_prompt)
        elif "reviewer" in prompt_lower:
            return self._reviewer_response(prompt, scope_context, original_prompt)
        return "Refined: Enhance clarity and add specific implementation details."
    
    def _architect_response(self, prompt: str, scope: Dict, original: str) -> str:
        """Generate architect response WITH scope context."""
        scope_section = self._format_scope_section(scope)
        
        # Dynamic focus based on scope
        focus_areas = scope.get('focus', ['scalability', 'maintainability', 'extensibility'])
        focus_text = ', '.join(focus_areas)
        
        return f"""ARCHITECTURAL DESIGN TASK

{scope_section}ORIGINAL REQUEST: {original or "Design appropriate architecture"}

DESIGN FOCUS:
- Primary concerns: {focus_text}
- Integration points and system boundaries
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
    
    def _developer_response(self, prompt: str, scope: Dict, original: str) -> str:
        """Generate developer response WITH scope context."""
        scope_section = self._format_scope_section(scope)
        
        # Dynamic focus
        focus_areas = scope.get('focus', ['best practices', 'error handling', 'readability'])
        focus_text = ', '.join(focus_areas)
        
        # Target-specific implementations
        target_dirs = scope.get('target_dirs', [])
        file_context = f"\nCONSTRAINED TO: {', '.join(target_dirs)}" if target_dirs else ""
        
        return f"""DEVELOPMENT TASK{file_context}

{scope_section}ORIGINAL REQUEST: {original or "Implement the requested functionality"}

IMPLEMENTATION FOCUS:
- {focus_text}
- Language-specific idioms and patterns
- Self-documenting code with clear naming

ACCEPTANCE CRITERIA:
- [ ] Function handles edge cases (empty input, None values, large data)
- [ ] Unit tests cover happy path and error cases (>80% coverage)
- [ ] {focus_areas[0].capitalize() if focus_areas else 'Code'} requirements met
- [ ] Documentation includes usage examples
- [ ] Security review passed (no injection risks, proper auth checks)

DELIVERABLES:
- Source code with inline documentation
- Unit tests with mocking for external dependencies
- Integration test demonstrating end-to-end flow
- README with setup and usage instructions"""
    
    def _tester_response(self, prompt: str, scope: Dict, original: str) -> str:
        """Generate tester response WITH scope context."""
        scope_section = self._format_scope_section(scope)
        
        focus_areas = scope.get('focus', ['test coverage', 'edge cases', 'reliability'])
        focus_text = ', '.join(focus_areas)
        
        target_files = scope.get('target_files', [])
        file_context = f"\nTARGET TEST FILES: {', '.join(target_files)}" if target_files else ""
        
        return f"""TESTING TASK{file_context}

{scope_section}ORIGINAL REQUEST: {original or "Create comprehensive test suite"}

TEST FOCUS AREAS:
- {focus_text}
- Validating user-defined behavior and requirements
- Error handling and edge cases

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
    
    def _reviewer_response(self, prompt: str, scope: Dict, original: str) -> str:
        """Generate reviewer response WITH scope context."""
        scope_section = self._format_scope_section(scope)
        
        focus_areas = scope.get('focus', ['security', 'code quality', 'best practices'])
        focus_text = ', '.join(focus_areas)
        
        target_dirs = scope.get('target_dirs', [])
        scope_context = f"\nSCOPE LIMITED TO: {', '.join(target_dirs)}" if target_dirs else ""
        
        return f"""CODE REVIEW TASK{scope_context}

{scope_section}ORIGINAL REQUEST: {original or "Review code for quality and best practices"}

REVIEW FOCUS:
- {focus_text}
- Code correctness and adherence to standards
- Potential bugs and security vulnerabilities

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
    """Create test project if needed."""
    from simpa.db.models import Project
    import uuid
    
    # Check if project exists first
    from sqlalchemy import select
    result = await db_session.execute(
        select(Project).where(Project.project_name == "scope-aware-test-project")
    )
    existing = result.scalar_one_or_none()
    if existing:
        return str(existing.id)
    
    project = Project(
        project_name="scope-aware-test-project",
        description="Test project for scope-aware prompts",
        main_language="python",
    )
    db_session.add(project)
    await db_session.flush()
    return str(project.id)


async def run_single_test(
    prompt_data: dict,
    project_id: str,
    ctx: Context
) -> dict:
    """Run a single test and return results."""
    agent_type = prompt_data["agent_type"]
    original_prompt = prompt_data["original_prompt"]
    
    result = {
        "agent_type": agent_type,
        "original_prompt": original_prompt,
        "has_scoping": bool(prompt_data.get("context")),
        "scoping_context": prompt_data.get("context", {}),
    }
    
    try:
        request = RefinePromptRequest(
            project_id=project_id,
            original_prompt=original_prompt,
            agent_type=agent_type,
            main_language=prompt_data["main_language"],
            context=prompt_data.get("context", {}),
        )
        
        response = await refine_prompt(request, ctx)
        
        result["refined_prompt"] = response.refined_prompt
        result["action"] = response.action
        result["success"] = True
        
    except Exception as e:
        result["error"] = str(e)
        result["refined_prompt"] = f"ERROR: {e}"
        result["action"] = "error"
        result["success"] = False
    
    return result


async def run_all_tests():
    """Run all 15 tests and collect results."""
    ctx = MockContext()
    
    async with AsyncSessionLocal() as session:
        project_id = await setup_test_data(session)
        
        results = []
        for i, prompt_data in enumerate(TEST_PROMPTS, 1):
            print(f"\n[{i}/{len(TEST_PROMPTS)}] Testing: {prompt_data['agent_type']} - {prompt_data['original_prompt'][:50]}...")
            result = await run_single_test(prompt_data, project_id, ctx)
            results.append(result)
            
            scoping_indicator = "✅" if result['has_scoping'] else "❌"
            print(f"   Action: {result['action']} | Scoped: {scoping_indicator} | Success: {result['success']}")
        
        return results


def main():
    """Main entry point."""
    print("=" * 80)
    print("TESTING 15 REAL-WORLD PROMPTS WITH SCOPE-AWARE SIMPA REFINEMENT")
    print("=" * 80)
    print()
    print("NOTE: This test now includes scope context in refined prompts!")
    print("The mock LLM extracts scope from the request and includes it in output.")
    print()
    
    results = asyncio.run(run_all_tests())
    
    # Display summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    with_scoping = sum(1 for r in results if r["has_scoping"])
    without_scoping = total - with_scoping
    
    print(f"\nTotal prompts tested: {total}")
    print(f"Successful refinements: {successful}/{total}")
    print(f"With scoping: {with_scoping}/{total}")
    print(f"Without scoping: {without_scoping}/{total}")
    
    # By agent type
    print("\nBy Agent Type:")
    for agent in ["architect", "developer", "tester", "reviewer"]:
        agent_results = [r for r in results if r["agent_type"] == agent]
        agent_success = sum(1 for r in agent_results if r["success"])
        agent_scoped = sum(1 for r in agent_results if r["has_scoping"])
        print(f"  {agent}: {agent_success}/{len(agent_results)} success, {agent_scoped}/{len(agent_results)} scoped")
    
    # Display detailed results table
    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    
    for i, (test_data, result) in enumerate(zip(TEST_PROMPTS, results), 1):
        scoping = "✅ SCOPED" if result['has_scoping'] else "❌ UNSCOPED"
        print(f"\n--- Test {i} | {result['agent_type'].upper()} | {scoping} ---")
        print(f"ORIGINAL: {result['original_prompt'][:70]}...")
        if result.get('scoping_context'):
            ctx = result['scoping_context']
            print(f"CONTEXT:")
            if ctx.get('scope'):
                print(f"  - scope: {ctx['scope']}")
            if ctx.get('focus'):
                print(f"  - focus: {', '.join(ctx['focus'])}")
            if ctx.get('target_dirs'):
                print(f"  - target_dirs: {', '.join(ctx['target_dirs'])}")
        print(f"REFINED:\n{result['refined_prompt']}")
        print(f"ACTION: {result['action']}")
        print("-" * 80)
    
    # Save results to file
    output_file = "test_15_scope_aware_results.md"
    with open(output_file, "w") as f:
        f.write("# 15 Real-World Prompts: Scope-Aware Test Results\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Total prompts: {total}\n")
        f.write(f"- Successful: {successful}/{total}\n")
        f.write(f"- With scoping: {with_scoping}/{total}\n")
        f.write(f"- Without scoping: {without_scoping}/{total}\n\n")
        
        f.write("## Results by Agent Type\n\n")
        for agent in ["architect", "developer", "tester", "reviewer"]:
            agent_results = [r for r in results if r["agent_type"] == agent]
            agent_success = sum(1 for r in agent_results if r["success"])
            agent_scoped = sum(1 for r in agent_results if r["has_scoping"])
            f.write(f"| {agent} | {len(agent_results)} | {agent_success}/{len(agent_results)} | {agent_scoped}/{len(agent_results)} |\n")
        
        f.write("\n## Detailed Results\n\n")
        for i, result in enumerate(results, 1):
            scoping = "✅" if result['has_scoping'] else "❌"
            f.write(f"### Test {i}: {result['agent_type'].upper()} | Scoping: {scoping}\n\n")
            f.write(f"**Original Prompt:**\n{result['original_prompt']}\n\n")
            if result.get('scoping_context'):
                f.write(f"**Scoping Context:**\n```json\n{json.dumps(result['scoping_context'], indent=2)}\n```\n\n")
            f.write(f"**Refined Prompt:**\n```\n{result['refined_prompt']}\n```\n\n")
            f.write(f"**Action:** {result['action']}\n\n")
            f.write("---\n\n")
    
    print(f"\n\nFull results saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    results = main()
