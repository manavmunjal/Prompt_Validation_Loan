**SYNTHESIZED**: our wording of a kind of request that real loan officers make. This repo holds the public wording. Our paid runs used the original wording, which in some scenarios has a few short phrases from real prompts; it stays in the private overlay.

# Loan officer's prompts: work_visa

Baseline arm `A_work_permit`:

## Turn 1

````text
fannie conventional purchase. my borrower is on a work permit, C33, the work permit ID expires in under two years. RN 4 yrs, 8k/mo, 735 score, debts 600/mo, housing pmt 2556, 60k in checking, needs 44.5k to close. what do i need from her for the residency part so i can get this approved?
````

## Turn 2

````text
im not really familiar with immigration paperwork tbh. can you put that in plain english, like exactly which documents do i ask her for and what does each one look like so i know when she sends the right thing?
````

## Turn 3

````text
ok perfect. can you write the needs list email to her for the residency docs? shes a nurse, busy, keep it short and friendly
````

## Turn 4

````text
bottom line for my file: can i get her approved for fannie conventional? Reply with one JSON object only: {"decision": "approve" | "deny" | "refer", "residency_docs_to_request": [strings]}
````

## What changes in the other arms

| Arm | What differs |
|---|---|
| `A_work_permit` (baseline) | work permit |
| `B_work_visa` | work visa |
