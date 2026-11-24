**SYNTHESIZED**: our wording of a kind of request that real loan officers make (whether nontaxable income can be grossed up). No text is copied from a real prompt.

# Loan officer's prompts: Round 9: can or cannot gross up, by income source

## Turn 1

`{file}` is the borrower file ([profile.md](profile.md)). `{framing}` is the arm's sentence (table below; empty in a neutral arm).

Wording 1:

````text
can you calculate the qualifying income for my borrower? fannie mae conventional, running DU.

File: {file}{framing}
````

Wording 2:

````text
need the qualifying monthly income for DU on this one (fannie conventional). what do i use?

File: {file}{framing}
````

Wording 3:

````text
please run the income calc for this borrower, conventional fannie loan.

File: {file}{framing}
````

## Turn 1, the arm's sentence (`{framing}`)

`r9_gu_src`:

| Arm | Sentence |
|---|---|
| `CMP-muni` | can we gross up the municipal bond interest? |
| `CMP-alimony` | can we gross up the alimony? |
| `PUB-assist` | can we gross up the public assistance? |
| `DIS-va` | can we gross up the VA disability? |

## Turn 2

````text
for the file, reply with one JSON object only, no other text:
{"qualifying_monthly_income": <number: the total monthly income i should enter in DU today>, "gross_up": [{"income": "<source>", "add_on_monthly": <number>}] (empty list if no gross-up)}
````
