# 1-Implement code and tests

## Implement code and tests for the SIMPA MCP Server
- Use the architectural design as defined docs/design/SIMPA-Architecture-20260303.md
- The database exists at postgresql://localhost:5432/simpa, with pgpass username 'dsidlo'
- Implement the application code and logic.
- Create pytests trying to get maximum coverage of all functions.
- Create integration tests to verify that the simpa-mcp service works as intended.


## MCP Configuration
- The MCP Server can be configured with the following...
- LLM Provider: OpenAI, Anthropic, Ollama, Xai
- LLM Model: name of model to use
- LLM API Key: API key for the LLM provider. Or, blank to use ~/.env
- LLM Base URL: Base URL for the LLM provider
- SIMPA Context Directory: A semi-colon separated list of directories the SIMPA LLM will use for policy context. These directories should contain text files that the LLM can use to inform its responses.

## Only the most salient diffs
- Only collect the most salient diffs from the code and tests.
- The LLM should be instructed to collect only the most salient diffs from the code and tests base on the context of the request.

## Calls to LLM should be optimized
- The logic in SIMPA should be optimized to only call on the LLM when necessary.
