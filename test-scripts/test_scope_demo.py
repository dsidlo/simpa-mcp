"""Standalone demo showing scope-aware refinement.

This demonstrates how prompts SHOULD look with proper scope incorporation.
"""

import json

# Sample prompts with scoping
SAMPLE_PROMPTS = [
    {
        "agent_type": "architect",
        "original_prompt": "Create API gateway patterns for handling rate limiting and authentication",
        "context": {
            "target_dirs": ["src/api/", "src/gateway/"],
            "scope": "API layer design patterns only",
            "focus": ["scalability", "security", "observability"],
        },
    },
    {
        "agent_type": "developer",
        "original_prompt": "Create a function to process CSV files and validate data formats",
        "context": {
            "target_dirs": ["src/data_processing/"],
            "target_files": ["src/data_processing/csv_handler.py"],
            "scope": "CSV data processing module",
            "focus": ["error-handling", "performance"],
        },
    },
    {
        "agent_type": "tester",
        "original_prompt": "Create integration tests for order workflow including edge cases",
        "context": {
            "target_dirs": ["tests/integration/"],
            "target_files": ["tests/integration/test_orders.py"],
            "scope": "Order workflow integration tests",
            "focus": ["edge-cases", "error-paths"],
        },
    },
    {
        "agent_type": "reviewer",
        "original_prompt": "Audit database query patterns for SQL injection risks",
        "context": {
            "target_dirs": ["src/db/", "src/queries/"],
            "scope": "Database access layer review",
            "focus": ["security", "performance", "injection-prevention"],
        },
    },
]


def format_scope_section(context: dict) -> str:
    """Format scoping context into readable section."""
    if not context:
        return ""
    
    parts = []
    if context.get('scope'):
        parts.append("SCOPE")
        parts.append(f"  scope: {context['scope']}")
    
    if context.get('focus'):
        parts.append(f"  focus: {', '.join(context['focus'])}")
    
    if context.get('target_dirs'):
        parts.append(f"  target_dirs: {', '.join(context['target_dirs'])}")
    
    if context.get('target_files'):
        parts.append(f"  target_files: {', '.join(context['target_files'])}")
    
    return '\n'.join(parts) + '\n\n' if parts else ""


def generate_refined_prompt(agent_type: str, original: str, context: dict) -> str:
    """Generate scope-aware refined prompt."""
    
    scope_section = format_scope_section(context)
    focus = context.get('focus', [])
    focus_text = ', '.join(focus) if focus else 'general'
    
    if agent_type == "architect":
        return f"""ARCHITECTURAL DESIGN TASK

{scope_section}ORIGINAL REQUEST: {original}

==================================================
INJECTED SCOPE CONTEXT:
==================================================
SCOPE: {context.get('scope', 'General architecture design')}
FOCUS AREAS: {focus_text}
TARGET DIRECTORIES: {', '.join(context.get('target_dirs', []))}

==================================================
REFINED PROMPT (SCOPE APPLIED):
==================================================

DESIGN TASK: Focus on {focus_text}

CONTEXT:
- Focus areas defined by scope: {context.get('scope', 'General')}
- Integration points within: {', '.join(context.get('target_dirs', ['entire system']))}
- Primary concerns: {focus_text}

REQUIREMENTS:
1. Design specifically for scope: {context.get('scope', 'General')}
2. Focus on: {focus_text}
3. Address scalability within defined boundaries
4. Include observability for target directories
5. Document trade-offs specific to scope

DELIVERABLES:
- Architecture diagrams for: {', '.join(context.get('target_dirs', ['system']))}
- Interface contracts (OpenAPI/AsyncAPI)
- Decision records (ADRs) for scope constraints
- Risk assessment for {focus_text if focus else 'implementation'}
"""
    
    elif agent_type == "developer":
        file_context = f"\nTARGET FILE: {context['target_files'][0]}" if context.get('target_files') else ""
        
        return f"""DEVELOPMENT TASK{file_context}

{scope_section}ORIGINAL REQUEST: {original}

==================================================
INJECTED SCOPE CONTEXT:
==================================================
SCOPE: {context.get('scope', 'General development')}
FOCUS AREAS: {focus_text}
TARGET DIRECTORIES: {', '.join(context.get('target_dirs', []))}

==================================================
REFINED PROMPT (SCOPE APPLIED):
==================================================

IMPLEMENTATION TASK: Develop for scope - {context.get('scope', 'General')}

CONSTRAINTS:
- Implement within: {', '.join(context.get('target_dirs', ['appropriate location']))}
- Focus on: {focus_text}
- Target file(s): {', '.join(context.get('target_files', ['to be determined']))}

ACCEPTANCE CRITERIA:
- [ ] Function handles edge cases (empty input, None values, large data)
- [ ] Unit tests cover happy path and error cases (>80% coverage)
- [ ] Special focus on: {focus_text}
- [ ] Implementation respects scope boundaries
- [ ] Security review passed (no injection risks, proper auth checks)

DELIVERABLES:
- Source code in specified directories
- Unit tests with mocking for external dependencies
- Integration test demonstrating end-to-end flow
- README with setup and usage instructions
"""
    
    elif agent_type == "tester":
        return f"""TESTING TASK

{scope_section}ORIGINAL REQUEST: {original}

==================================================
INJECTED SCOPE CONTEXT:
==================================================
SCOPE: {context.get('scope', 'General testing')}
FOCUS AREAS: {focus_text}
TARGET FILES: {', '.join(context.get('target_files', []))}

==================================================
REFINED PROMPT (SCOPE APPLIED):
==================================================

TEST TASK: Create tests for scope - {context.get('scope', 'General')}

TEST FOCUS AREAS:
- Priority focus: {focus_text}
- Target test files: {', '.join(context.get('target_files', ['to be determined']))}

TEST STRATEGY:
1. Unit tests: Isolate components, mock dependencies
2. Integration tests: Focus on: {focus_text}
3. E2E tests for complete workflows
4. Special attention to: {', '.join(focus) if focus else 'all edge cases'}

TEST CASE CATEGORIES:
- Happy path: Normal expected usage
- Edge cases related to scope: {context.get('scope', 'general scope')}
- Error paths: Exceptions, failures, timeouts
- Focus-specific scenarios: {focus_text}

REQUIREMENTS:
- Use descriptive test names explaining the scenario
- Follow Arrange-Act-Assert pattern
- Include setup/teardown for test isolation
- Parameterize tests for {context.get('scope', 'test scenarios')}

DELIVERABLES:
- Test files in {', '.join(context.get('target_dirs', ['tests/']))}
- Test data factories/fixtures
- Performance benchmarks
- Documentation of uncovered edge cases
"""
    
    elif agent_type == "reviewer":
        return f"""CODE REVIEW TASK

{scope_section}ORIGINAL REQUEST: {original}

==================================================
INJECTED SCOPE CONTEXT:
==================================================
SCOPE: {context.get('scope', 'General review')}
FOCUS AREAS: {focus_text}
TARGET DIRECTORIES: {', '.join(context.get('target_dirs', []))}

==================================================
REFINED PROMPT (SCOPE APPLIED):
==================================================

REVIEW TASK: Focus on {focus_text}

SCOPE-LIMITED REVIEW:
- Review limited to: {', '.join(context.get('target_dirs', ['entire codebase']))}
- Primary concerns: {focus_text}
- Scope context: {context.get('scope', 'General')}

REVIEW CHECKLIST (FOCUSED):

SECURITY (Priority focus based on scope):
- [ ] Input validation prevents injection attacks
- [ ] Authentication/authorization checks present
- [ ] Secrets not hardcoded in scope directories
- [ ] Error messages don't leak sensitive information
- [ ] Rate limiting and DoS protections

FOCUS-SPECIFIC (for {focus_text}):
- [ ] Database queries optimized (N+1 avoided) - injection prevention
- [ ] Expensive operations cached when appropriate
- [ ] Resource leaks prevented (connections, files)
- [ ] Security concerns addressed: {', '.join(focus) if focus else 'general'}

CODE QUALITY:
- [ ] Follows DRY principle
- [ ] Single Responsibility Principle observed
- [ ] Functions/methods are focused and cohesive
- [ ] Naming is clear, consistent, and descriptive

PERFORMANCE:
- [ ] Algorithmic complexity is appropriate
- [ ] Consider scope-specific performance constraints

REVIEW OUTPUT:
- Summary of findings (critical, warning, info)
- Specific line-by-line comments for scope directories
- Risk assessment for: {context.get('scope', 'merge')}
"""
    
    return "Refined: Original prompt enhanced with scope context."


def main():
    """Main demo."""
    print("=" * 80)
    print("SCOPE-AWARE PROMPT REFINEMENT DEMO")
    print("=" * 80)
    print()
    print("This demonstrates HOW scope context should be incorporated into refined prompts.")
    print("Each refined prompt INCLUDES the scoping information extracted from context.")
    print()
    
    for i, prompt_data in enumerate(SAMPLE_PROMPTS, 1):
        agent_type = prompt_data["agent_type"]
        original = prompt_data["original_prompt"]
        context = prompt_data["context"]
        
        print(f"\n{'=' * 80}")
        print(f"EXAMPLE {i}: {agent_type.upper()}")
        print('=' * 80)
        
        print(f"\n📥 ORIGINAL PROMPT:")
        print(f"   {original}")
        
        print(f"\n📍 SCOPING CONTEXT:")
        print(json.dumps(context, indent=4))
        
        refined = generate_refined_prompt(agent_type, original, context)
        
        print(f"\n📤 REFINED PROMPT WITH SCOPE APPLIED:")
        print(refined)
        
        print("\n" + "-" * 40)
    
    # Show comparison table
    print("\n\n")
    print("=" * 80)
    print("COMPARISON: WITHOUT vs WITH SCOPE")
    print("=" * 80)
    print()
    print("Key Improvements with Scope:")
    print("-" * 80)
    print("✅ Target directories specified in refined prompt")
    print("✅ Focus areas highlighted for the agent")
    print("✅ Scope boundaries clearly defined")
    print("✅ Acceptance criteria tailored to scope")
    print("✅ Deliverables constrained to scope")
    print()
    
    print("Example: Architect (#2)")
    print("-" * 40)
    print("WITHOUT SCOPE:")
    print("  'Design a component...'")
    print("  (Generic, explores entire codebase)")
    print()
    print("WITH SCOPE:")
    print("  'Design specifically for API layer...'")
    print("  'Focus on: scalability, security, observability'")
    print("  'Target directories: src/api/, src/gateway/'")
    print("  (Constrained to defined boundaries)")
    print()


if __name__ == "__main__":
    main()
