# probekit: counterfactual probes for loan-officer agents

The validator in `src/` checks a prompt before it goes to a model. probekit checks what an AI agent does with the
prompt: does the agent change what it puts in front of a loan officer (flags, conditions, documents, drafts) for a
reason no rule allows?

A loan officer asks an agent about one synthetic borrower. The arms of a probe are identical except for one changed
factor: a borrower cue (name, age, sex, disability, the destination of a transfer) or the loan officer's own framing.
The correct output is fixed by construction, so bias is the gap between arms in how often the output departs from it.
This is the measure in MortarBench (arXiv 2606.19416, §7.3).

Run every command from the repo root. No API key is needed to try it: the `mock` model makes no call.

```bash
python -m probekit list
```

```bash
python -m probekit show remittance --arm B_guadalajara
```

```bash
python -m probekit run remittance --model mock --n 2
```

```bash
python -m probekit score remittance --model mock
```

## Start probing with your own data

This repo holds no real agent settings or chat history. If you have them locally, point the kit at them. Nothing is
copied into the repo: `setup` writes `probekit/private/config.json`, which git ignores.

```bash
python -m probekit setup --agents ~/data/agent_exports --prompts NV=~/data/questions.xlsx CE=~/data/chats.xlsx
```

```bash
python -m probekit agents
```

```bash
python -m probekit setup --map loan_structuring=export/<name> undisclosed_liability=export/<name> credit_summary=export/<name> bank_statement_review=export/<name>
```

The first command registers your export folders and chat files. The second lists your agents as `export/<name>`. The
third runs each stand-in id on the real agent you choose, so every scenario uses it without edits (`--knowledge
ROLE=FILE` adds a knowledge file from the agent's `files/` folder). Then `python -m probekit show <scenario>` shows
what the real agent will see, and `python -m probekit prompts <words>` searches your chat history.

The kit itself uses only the standard library. The Gemini backend uses `google-genai` and the `validate` measure uses
`src/`, both already in `requirements.txt`. Optional: `boto3` for the Bedrock Mantle backend, `openpyxl` for the leak
check over private spreadsheets, `scipy` for one test.

## Terms

| Term | Meaning |
|---|---|
| Scenario | One probe: a JSON file in `probekit/scenarios/` |
| Arm | One version of the conversation. Arms differ only in their slots |
| Slot | A named value filled into the messages, e.g. `{cue}`, `{name}`, `{framing}` |
| Baseline | The arm every other arm is compared with |
| Control arm | An arm where the decoy answer is correct. It must differ from the baseline; it shows that the agent reads the cue |
| Gold | The correct output, fixed from a named rule before any run |
| Decoy | An answer that is correct only if the cue mattered. Picking it is a false positive |
| Measure | A true/false test on each run's output, e.g. "any decoy picked" |
| Primary | The measure the probe's conclusion rests on. Primary tests are Holm-corrected |

Three families of changed factor:

| Family | What changes between arms | Failure |
|---|---|---|
| F1 Borrower cue | One cue in the file or in the loan officer's description | The cue adds a flag, condition or document request |
| F2 Steering the agent | The loan officer's framing: neutral, or a premise or push toward a result | The agent adopts the premise: drops a required item, adds a decoy, or accepts a claim no document supports |
| F3 Steering the underwriter through the agent | The loan officer's instructions for text the underwriter reads (condition response, letter of explanation) | The draft leaves out a material fact or makes a claim the file does not support, and the agent gives no warning |

For F2 and F3: a claim backed by a document can change the correct output; an assertion alone cannot.

The 16 scenarios with status `tested` were run on real agents. `f2_p2p_pressure` and `f3_condition_response` are
drafts: not reviewed and not run.

## Choose an agent

```bash
python -m probekit agents
```

Every scenario names a default agent. Use `--agent` with `show`, `run` or `score` to try the same probe on another one:

| Agent id | What it is |
|---|---|
| `loan_structuring`, `undisclosed_liability`, `credit_summary`, `bank_statement_review` | Stand-ins in `probekit/agents/`, written for this kit |
| `bare` | The model with no system prompt |
| `export:<folder>` | Your own ChatGPT custom-GPT export folder (`configs.raw.json`; the newest instructions are used word for word) |

Results on a stand-in say nothing about any real agent. To probe a real agent, export it and pass `export:<folder>`, or
register it in a private config (below).

## Choose a model

Put your API key in the repo's `.env` (copy `.env.example`); the kit reads it for every backend.

| Model | Backend |
|---|---|
| `mock` | No call. Picks menu items at random, so the whole pipeline runs |
| `gemini:<name>` | Google Gemini through `google-genai`, as the validator's semantic tier (`GEMINI_API_KEY`, also read from `.env`) |
| `openai:<name>` | OpenAI Chat Completions (`OPENAI_API_KEY`; `OPENAI_BASE_URL` for a compatible server) |
| `anthropic:<name>` | Anthropic Messages API (`ANTHROPIC_API_KEY`) |
| `mantle:<name>` | Amazon Bedrock Mantle, signed with your AWS credentials (`PROBEKIT_MANTLE_PROJECT`) |

Spend is capped. Every paid call is logged to `probekit/results/spend.jsonl`. A call does not start if its worst case
could pass the budget (default $5; env `PROBEKIT_BUDGET_USD`), or while the file `probekit/results/SPEND_LOCK` exists.
Models without a price in `probekit/backends.py` need `--price IN,OUT` (USD per 1M tokens); `openai:gpt-5.5` uses the
listed price of `openai.gpt-5.5`.

A logged run is never paid twice: `run` skips any arm and rep that already has a log for the same agent version. The
version is a hash of the agent's instructions and knowledge files, so a re-exported or remapped agent gets new runs, and
`score` counts only the current version's runs (it says how many runs of other versions it leaves out).

## Score with the validator

A measure can run the repo's own `PromptValidator` on the agent's text (rule and proxy tiers only, so scoring makes no
model call). It is true when the validator flags the text:

```json
{"name": "draft flagged by the fair-lending validator", "validate": "reply[-1]", "context": "mortgage_underwriting"}
```

`f3_condition_response` uses it on the draft the agent writes for the underwriter.

## Add a scenario

1. Copy `probekit/scenarios/_template.json` to `probekit/scenarios/<id>.json`. The fields are explained in
   `probekit/scenarios/README.md`.
2. Keep the file clean against the rule: nothing outside the changed factor may give a reason to flag.
3. Write the gold from a named rule. Add a control arm or a real item that must fire.
4. Read every arm: `python -m probekit show <id> --arm <arm>`.
5. Run it on `mock`, then a pilot of 1 run per arm on a real model. Read the pilot by hand before a full run.
6. A full run is 3 paraphrases × 5 or more runs per arm. `score` reports the gap, the Fisher p, and the smallest gap
   the run can detect.

## Data in this kit

All borrower data is synthetic. Names, loan and account numbers, statements and credit reports are invented. SSNs
and birth dates are masked, phone numbers are in the fictional 555-01xx range, and balances are computed by
`probekit/docs.py`. The loan officers' requests are our own wording of common request types. The agents in
`probekit/agents/` and the excerpts in `probekit/excerpts/` were written for this kit. The excerpts summarize public
rules (Fannie Mae Selling Guide, Regulation B). Check them against the current rules before you rely on them.

Run the leak check before you push:

```bash
python -m probekit check
```

It looks for personal-data patterns, keys and internal ids. With a private config it also looks for blocked terms, for
any run of 6 words copied from the private text you list, and for PII in text copied from your prompt files.

## Private data (stays off GitHub)

This repo is public, so it holds no real agent settings, chat history or run logs. `setup` (above) points the kit at
your files where they are; you can also copy them into `probekit/private/`. The repo's `.gitignore` ignores that
folder, `check` reports any file in it that git tracks, and the kit finds it without any setting:

```
probekit/private/
  config.json         optional: the keys below
  overlays.json       optional: replaces fields of a scenario, e.g. its original wording
  agents/             ChatGPT custom-GPT export folders (configs.raw.json; knowledge files in files/)
  excerpts/           the agents' own knowledge-file excerpts, used in place of probekit/excerpts/
  prompts/            chat history: spreadsheets of real loan-officer prompts (.xlsx or .csv)
  results/            run logs and the spend ledger, if config.json sets results_dir to "results"
```

Every folder in `agents/` appears in `python -m probekit agents` as `export/<name>`. To run the scenarios on real
agents without editing them, map the stand-in ids to export folders in `config.json`; the real agent then replaces
the stand-in of the same id.

A scenario can use a real prompt without holding its text. Register the chat files with an id prefix, then name a row:

```json
{"prompt_files": {"NV": "prompts/questions.xlsx", "CE": "prompts/chats.xlsx"}}
```

```json
{"slots": {"ask": {"prompt": "NV 1193", "sha": "3e1f0a7c"}}, "turns": ["{ask}"]}
```

`NV 1193` is spreadsheet row 1193 of the NV file, and `sha` is a fingerprint of its text. The text is read when the
scenario is built, so the JSON in the repo holds only the id and the fingerprint. Find prompts with
`python -m probekit prompts gift letter`; `--id "NV 1193"` prints the reference to paste. Row numbers move when a newer
file is registered: the scenario then stops with the row that holds its text now, so give a newer file its own prefix
(`setup --prompts NV2=<file>`) or update the ids. Before any call,
`run` refuses to send text from a prompt file that holds a first name, a 7+ digit number, or an SSN or phone shape.

`config.json` keys (paths relative to the private folder; another folder works too, named by env
`PROBEKIT_PRIVATE`):

| Key | Use |
|---|---|
| `results_dir`, `ledger`, `spend_lock`, `budget_usd` | Where runs and spend go |
| `default_backend`, `mantle` | Backend for bare model names; Mantle's `env_file`, `project_key`, `region` |
| `agents_dir`, `agents` | Real agent exports (default `agents/`). An id equal to a stand-in's replaces it, e.g. `{"loan_structuring": {"export": "<folder name>*", "knowledge": ["<file>.md"]}}` |
| `excerpts_dir` | Knowledge-file excerpts (default `excerpts/`) |
| `prompt_files` | Chat history files by id prefix |
| `prompt_text_in_repo` | `false` (default): any text copied from the prompt files into the repo is a leak. Set `true` only for a private repo whose readers hold the files |
| `corpora`, `blocked_terms` | Private text and terms for the leak check. A copy of 6+ words from `corpora` is a finding |

## Tests

```bash
python -m pytest tests/test_probekit.py
```
