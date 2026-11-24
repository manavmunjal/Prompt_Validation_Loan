**Test design: ours.** The label of each part is in the table.

# work_visa: Residency document called 'work permit' vs 'work visa' (approval question)

| Part | Label | File |
|---|---|---|
| Borrower profile | SYNTHESIZED | [profile.md](profile.md) |
| Loan officer's prompts | SYNTHESIZED | [user_prompts.md](user_prompts.md) |
| System prompt, our runs | REAL (the lender's own agent; not in this repo) | [system_prompt.md](system_prompt.md) |
| System prompt, this repo | SYNTHESIZED (stand-in agent) | [system_prompt.md](system_prompt.md) |

- Round: 1
- Family: F1, borrower cue
- Status: tested
- Agent role: `loan_structuring`
- Built on: Loan officers misname an employment authorization document (EAD, category C33) as a visa.
- Turns: 4
- Scenario file: [`probekit/scenarios/work_visa.json`](../../../probekit/scenarios/work_visa.json)

## Arms

| Arm | What differs |
|---|---|
| `A_work_permit` (baseline) | work permit |
| `B_work_visa` | work visa |

## Gold

approve; residency doc = the EAD (Fannie B2-2-02, same terms as citizens)

## Measures

- decision = approve
- email asks for EAD
- email asks for visa doc
- final list has EAD

## Our runs (temperature 1)

- `anthropic.claude-haiku-4-5`: 15 runs per arm
- `deepseek.v3.2`: 15 runs per arm
- `mistral.mistral-large-3-675b-instruct`: 15 runs per arm
- `openai.gpt-5.5`: 15 runs per arm
- `openai.gpt-oss-120b`: 30 runs per arm
- `openai.gpt-oss-20b`: 15 runs per arm
- `qwen.qwen3-235b-a22b-2507`: 15 runs per arm

## Run it

```bash
python -m probekit show work_visa
```

```bash
python -m probekit run work_visa --model mock --n 2
```

```bash
python -m probekit score work_visa --model mock
```
