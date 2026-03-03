# 0-Project Bootstrap Prompt

## DT-Agent Behaviour

- If you need to do any scratch work and scripting, place those files into the dev-agent-workspace.

## Design of SIMPA

- Create a design document for SIMPA, a self-improving meta prompt agent that evolves over time to optimize its performance.
- Document the architecture, components, and key features of SIMPA.
- Include a detailed explanation of the self-improvement mechanism.
- Provide examples and use cases to illustrate the benefits of SIMPA.
- SIMPA Presents itself to Agent Controllers as an MCP Service.
- Before the Agent Controller launches an Agent to take action on a given prompt, is submits the prompt for refinement to the simpa-mcp service.
- It receives the refined prompt, then launches the Agent to take action on the refined prompt.
- Design the service around the concepts outlined in the document "docs/design/SIMPA - A Self Improving Meta Prompt Agent".
- Place the Architectural document into the docs/design directory, and add the date to the document's file name.
- Include advisories and best practices for testing and deployment.
- Use mermaid diagrams to visualize the architecture and process flow between service's components.
- Generate the postgres database schema to postgresql://localhost:5432/simpa using the pgpass user "dsidlo".

### Notes...

- Agent did not find the vector extention
  - Agent tried to install it but did not have the permissions to do so.
  - I had to run...
    ```text
    ❯ sudo su - postgres -c "psql -c \"CREATE EXTENSION IF NOT EXISTS vector;\" simpa" 2>&1 || echo "su failed"
    [sudo] password for dsidlo: 
    CREATE EXTENSION
    ```
