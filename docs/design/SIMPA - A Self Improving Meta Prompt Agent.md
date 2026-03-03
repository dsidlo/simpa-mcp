# SIMPA - A Self Improving Meta Prompt Agent

Self-Improving Meta Prompting Agent (SIMPA)

* MCP Server: Self Improving Prompt Refinement
	* Service Requirements
		* LLM Service (High Quality Reasoning)
		* Embedding Service
		* PostgreSql (All in one simpler implementation)
			* Vector DB Service
				* Vector Store fields Schema
			* Relational DB Service
				* Relational DB Prompt Tables Schema
	* Leader Generates Prompt for Agent
		* Leader refines prompt using...
			* Vector Search: Given Agent-Type, Request
				* Returns: Top Successful request/prompts for a given agent-type
					* includes relational lookup keys.
			* Prompt Expert Decides which prompt to use or creates a new prompt
				* New prompt → store new prompt to vector and relational DBs
		* Refined Prompt is Given to agent for action
		* Reviewer Reviews Quality of Success for Agent prompt vs tests and validations
			* Prompt History and Stats are updated to the Prompt-Relational Store
	* Prompts for the Prompting-Agent
		* Prompt Refinement:
			* Context:
				* Policies:
					* Security Policies
					* Coding Policies
					* Testing Policies
					* Linting Policies
					* etc...
				* Top Similar Successful Prompt for the given Agent-Type
			* Prompt:
				* "Given your knowledge of various coding policies and existing successful agentic-prompts vs the current prompt request. Use and existing prompt, or refine the current prompt to more accurately address policy requirements of the requests problem domain so that the agent prompted has a higher probability of performing the given task in one-shot."
				* "If you decide to refine the prompt, store the following data to the vector store and relational database"
				* "Finally return the following data if you choose to use and existing prompt..."
				   "Or return the following data if you choose to create a new refined prompt..."
					* Returns Prompt string and best applicable examples (from diff) with comments.
			* Prompt Refinement Response:
				* Prompt-Returned: Prompt to use
				* Relation key to Prompt-Returned
					* Agentic-Coordinator hold on to this key so that the prompts actions history and stats can be stored.
		* Prompt Results Update:
			* Called by Agentic-Coordinator to update the stats and history of a given prompts effectiveness.
			* Updates the results of the agents actions:
				* Prompts Action History:
					* Validation Score after (test, lint, etc..)
					* Diffs of changed files.
				* Updates prompt record aggregated stats
					* Usage Count: +1
					* Average Score: Average of all Scores.
					* Scoring Bins 1 to 5: Scoring Distribution by usage.

## Schemas for Self-Improving Prompts

* PostgreSql: Vector Indexed/Relation DB
	* Table: Refine-Prompt
		* Refined-Prompt-Key: The RDB Key to the Refined-Prompt
		* Vector-Embedding: Vector Embedding key
			* The Vector Embedding is based on the following text
				* Main-Language
				* Other-Languages
				* Original-Prompt
				* Refined-Prompt
		* Date-Time: When this record was created
		* Main-Language: The main programming Language (Python, Rust, Java, Bash, Markdown, etc...)
		* Other-Languages: List of other languages involved
		* Original-Prompt: The original prompt under refinement
		* Refined-Prompt: The Refined prompt returned
		* Prior-Refinement: Allow Prompt-Refiner to Refine and existing prompt by some sliding percentage based on the existing score (Tunable Sigmoid Curve).
		* Stats:
			* Usage-Count: The number of times the Refined-Prompt was used
			* Average-Score: The Average overall score for this Refined-Prompt
			* Score-Distrib: Histogram of Scores based on usage
	* Table: Refined-Prompt-History:
		* FK: Associated Refine-Prompt Record
		* Date-Time: When this record was created
		* Prompt-Action-Score: A score on the Actions performed by the Agent, given results of tests, linters and validation results.
		* Files-Modified: A list of files that were modified
		* Diffs-by-language: A report of diffs by language
			* Language: Language used (Shell, Python, Javascript, Java, etc...)
			* File Modified: Name of file that was modified
			* Diff: Diff of the given file comparing against last commit.

## Refinement Intensity based on current Prompt Performance

This is the perfect tunable control knob for the “Prompt Expert Decides which prompt to use or creates a new prompt” step in your Leader.

The cleanest, most natural way to express the sliding probability you described (lower score → dramatically higher chance of refinement) is with a logistic sigmoid curve. It gives you a smooth, S-shaped transition that feels organic: terrible prompts are almost always refined, excellent prompts are almost always reused, and everything in between slides gracefully.

### Recommended formula (core sliding probability)

Let \( S \) = the Average-Score of the best prompt returned by vector search (\( 1.0 \leq S \leq 5.0 \)).

\[
p_{\text{refine}}(S) = \frac{1}{1 + \exp\bigl( k \cdot (S - \mu) \bigr)}
\]

Recommended defaults (tuned specifically for your 1–5 scoring bins):
- Midpoint \( \mu = 3.0 \) (50 % refinement chance exactly at “average” performance)
- Steepness \( k = 1.5 \) (balanced slide — not too abrupt, not too flat)

### Concrete probabilities (exact values)

| Score ( S ) | \( p_{\text{refine}}(S) \) | Interpretation (what the Prompt Expert does) |
| :--- | :--- | :--- |
| 1.0 | 95.3 % | Almost always create a new/refined prompt |
| 1.5 | 90.5 % | Strongly prefer refinement |
| 2.0 | 81.8 % | High chance to improve |
| 2.5 | 67.9 % | Still leans toward refinement |
| 3.0 | 50.0 % | Coin-flip territory (balanced) |
| 3.5 | 32.1 % | Mostly reuse, but still some evolution |
| 4.0 | 18.2 % | Usually reuse |
| 4.5 | 9.5 % | Rarely refine |
| 5.0 | 4.7 % | Almost never refine (but never zero) |

### Why this curve works so well in your architecture
- True “sliding” behavior — exactly what you asked for. No hard thresholds.
- Differentiable — if you ever want to evolve the curve itself with another meta-layer, you can.
- Built-in minimum exploration — even a perfect 5.0 prompt still has ~5 % chance to spawn a variant (keeps diversity alive forever).
- Trivial to implement in the Leader (one line of code after the vector search):
  ```python
  import random
  p = 1 / (1 + math.exp(1.5 * (best_prompt.avg_score - 3.0)))
  if random.random() < p:
	  # call refinement prompt (create new)
  else:
	  # reuse existing prompt + relational key
  ```

### Easy practical tweaks you’ll probably want
1. Add a hard floor: `p = max(0.05, sigmoid)` → guarantees at least 5 % evolution even for god-tier prompts.
2. Blend with usage count (optional but powerful):
   $$
   p_{\text{final}} = 0.8 \cdot p_{\text{refine}}(S) + 0.2 \cdot e^{-\text{usage}/30}
   $$
   New prompts (low usage) get an extra boost to be refined.
3. You can change $ \mu $ and $ k $ on the fly (e.g., start aggressive with $ k=2.5 $, then anneal down to 1.0 as the whole system matures).

This single curve turns your entire self-improving MCP Server from “static prompt bank” into a true evolutionary system that visibly gets better every few hundred runs. It’s clean, explainable, and directly plugs into the Prompt Refinement and Results Update flows you already designed.

Drop this in and you’ll have measurable one-shot success rate gains within the first 200–300 tasks. Want the exact Python snippet for the Leader, or a version that also considers language/domain weighting? Happy to give it.

