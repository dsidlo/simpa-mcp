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

Remove

A prompts project and the details regarding what that project was about and what Languages and Modules were used in that project
can help improve the choice of which prompts better apply to the current project and request.

- Add a project-name table
  - Fields project_name (VARCHAR(255), NOT NULL)
  - Fields project_description (TEXT, NULL)
  - Main language
  - Other languages
  - Library dependencies used by the project
  - Fields project_created_at (TIMESTAMP, NOT NULL, DEFAULT CURRENT_TIMESTAMP)
  - Fields project_updated_at (TIMESTAMP, NULL)

- Add a foreign key to a project table record in the prompt history and the refined_prompts table.
- Add an endpoint to the MCP service that allows for the creation and retrieval of project information.
- Require that the creation or update of a project required a high description of the project.
  - The main language in the project, all other languages used in the project.
  - library dependencies used by the project

- Add tests for any new function added.
- Ensure that tests are comprehensive and cover edge cases.

- Cycle through test -- fix action until all tests are passing and dt-reviewer is satisfied with tests and programs as they are.

## Docker Testing

- Create tests to build and run the docker server.
- Create tests to test the simpa-mcp server and its endpoints via the running docker service.


