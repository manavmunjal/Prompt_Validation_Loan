# Scenario files

One JSON file per probe. Files whose name starts with `_` are ignored (`_template.json` is a starting point).

## Fields

| Field | Required | Meaning |
|---|---|---|
| `title` | yes | One line: what changes between arms, and what is scored |
| `family` | yes | `F1` borrower cue, `F2` steering the agent, `F3` steering the underwriter through the agent |
| `status` | yes | `draft` (not reviewed), `tested` (reviewed and run), `template` |
| `agent` | yes | Default agent id (`python -m probekit agents`) |
| `source` | yes | The kind of loan-officer request the probe is built on |
| `notes` | no | Design notes: why the file is clean, what the control shows |
| `arms` | yes | `{arm name: value}`. A string fills `{cue}`; an object fills each of its keys |
| `slots` | no | Values every arm shares; an arm's own value wins. A value `{"prompt": "NV 1193", "sha": "..."}` is a real prompt read from the private prompt files, so the file holds only its id and a fingerprint of its text (`python -m probekit prompts --id "NV 1193"` prints it) |
| `baseline` | no | The arm the others are compared with (default: first arm in sort order) |
| `controls` | no | Arms where the decoy answer is correct. They get no gap |
| `paraphrases` | no | Several wordings of turn 1; run k uses wording k mod n. An entry can be `{"prompt": id, "sha": ...}` |
| `turns` | yes | The loan officer's messages (after the paraphrase, if any). Slots are filled with `str.format`: write `{{` and `}}` for literal braces |
| `doc` | no | A synthetic document, filled into `{doc}` (see `probekit/docs.py`) |
| `menu`, `decoys`, `control_item` | no | A fixed menu `{id: text}` filled into `{menu}`, shuffled per run with the same seed in every arm. Adds three measures: JSON parsed, any decoy picked, control item picked |
| `menu_field` | no | JSON field holding the picked ids (default `attention_item_ids`) |
| `excerpt` | no | Knowledge excerpt appended to the system prompt (`excerpts/<name>.txt`) |
| `date` | no | Appended to the system prompt as the current date |
| `gold` | yes | The correct output in every arm, with the rule it comes from |
| `measures` | no | Tests on each run (below) |
| `primary` | no | Names of the measures the conclusion rests on |

## Measures

Each measure is an object with a `name` and one test. It is true or false for each run.

| Test | Fields |
|---|---|
| Text | `text` (where), `regex`, optional `mode`, `mask`, `section`, `filter`, `flags` (default `"i"`) |
| JSON value | `json` (field of the last JSON object in the last reply) with `equals`, or `ge` / `gt` / `le` / `lt` |
| JSON ids | `json` with `any_of` (true if any id is listed); `key` and `where` for lists of objects; `nonempty` |
| Validator | `validate` (where, as for `text`), optional `context`: true if the repo's `PromptValidator` (rule and proxy tiers, no model call) flags the text |
| Combination | `any`: names of earlier measures, or measures written in place |
| Mean | `summary: "mean"` with `json`, `key`, `id`, `field`: a number, reported as a mean per arm |

Add `"not": true` to invert any test.

`text` is one of: `replies` (all agent replies), `replies[:-1]`, `reply[k]` (Python index), `json[field]` (list items
joined by ` | `), or a list of these.

| `mode` | True when |
|---|---|
| `match` (default) | The regex matches |
| `requested` | It matches outside a negated clause ("no medical records are needed" does not count) |
| `negated` | It matches, but only inside negated clauses |
| `stated` | Some line states it un-negated ("hold for OFAC review") |
| `dismissed` | Some line mentions it only to dismiss it ("OFAC search: no match") |

`mask` is `[pattern, replacement, flags]`, applied first (e.g. hide the cue words so they cannot match). `section` is
`[start, stop]`: keep only the text between two headings. `filter` keeps only the lines that match it; the test is then
true if any kept line passes (with no `regex`: true if any line is kept).

Every regex hit should still be read by hand before a result is reported.
