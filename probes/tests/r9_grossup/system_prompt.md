**REAL**: the lender's own agent settings. Not in this repo.

# System prompt: Round 9: can or cannot gross up, by income source

The agent is the lender's own income-calculator agent, in the role `income_calculator`. Its system prompt in our runs:

1. the newest instructions of the agent's custom-GPT export, word for word;
2. the agent's two knowledge files, appended in the order of the private config (a custom GPT retrieves from them);
3. the line `Current date: 2026-11-10.`

The text is the lender's and is not in this repo. There is no stand-in for this role, so these rounds run only with an export mapped to `income_calculator` in the private config ([probes/README.md](../../README.md), "Rounds 5-9").

Our runs used agent version `cb546c205717` (the hash that ends each log's file name).
