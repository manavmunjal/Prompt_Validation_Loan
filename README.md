# Loan-officer agent probes

The code for every probe we ran on loan-officer agents: 23 tests. Each test has its setting, borrower profile, loan
officer prompts and system prompt, labeled SYNTHESIZED or REAL. Index: [probes/tests/README.md](probes/tests/README.md).

The borrowers and prompts are synthesized and are in this repo. The agents' real system prompts are not: you add your
copy of the agent exports in step 1.

## 1. Put the files in place

Put the lab's `Agents` folder (the agent exports) next to this repo, not inside it:

```
<any folder>/
  Prompt_Validation_Loan/        this repo
  Agents/                        the agent exports, one folder per agent
    Income Calculator__g-.../
      configs.raw.json           the agent's instructions
      files/
        income_calcs_conventional_system_prompt.txt
        income_calcs_conventional_policy_math.txt
    ...
```

For a paid model, copy `.env.example` to `.env` in this repo and add your API key. The mock model needs no key.

## 2. Point the kit at the files (once)

From this repo's folder:

```bash
pip install -r requirements.txt
python -m probekit setup --agents ../Agents --map income_calculator=export/income-calculator --knowledge income_calculator=income_calcs_conventional_system_prompt.txt income_calculator=income_calcs_conventional_policy_math.txt
```

Nothing is copied. The command writes only `probekit/private/config.json`, which git ignores.

## 3. Run a test

`--model mock` makes no call and costs nothing. For a real model use `openai:<model>`, `gemini:<model>` or
`anthropic:<model>`; paid runs stop at the budget ($5; `PROBEKIT_BUDGET_USD` in `.env`).

Rounds 5-9 (gross-up; `--round r5` to `r9`):

```bash
python probes/scripts/grossup_probe.py --round r9 run --model mock --n 1
python probes/scripts/grossup_probe.py --round r9 score --model mock
```

The setup matches our runs when the log file names in `probekit/results/` end in `cb546c205717`.

Rounds 1-4 (any test name from the index):

```bash
python -m probekit run r3_ssdi --model mock --n 2
python -m probekit score r3_ssdi --model mock
```

Rounds 1-4 run on stand-in agents until you map their roles to real exports: `python -m probekit agents` lists
your exports, and `python -m probekit setup --map <role>=export/<name>` maps one. Each test's role is in the index.

## More

- [probes/README.md](probes/README.md): the labels, the hand coding, and how to change a test or the analysis.
- [probekit/README.md](probekit/README.md): the kit's commands, models and scenario format.
