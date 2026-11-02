# 🏛️ Fair Housing & Lending Prompt Compliance Validator

A production-grade, multi-tiered compliance engine that validates prompts, rental advertisements, underwriting criteria, and loan automation workflows against all federal and state fair housing and lending laws as documented in [Housing discrimination in the United States (Wikipedia)](https://en.wikipedia.org/wiki/Housing_discrimination_in_the_United_States).

---

## ⚖️ Legal Frameworks & Variables Enforced

The system audits against all statutory provisions, landmark Supreme Court precedents, and administrative guidance:

| Statute / Authority | Citation / Precedent | Protected Classes & Key Rules |
| :--- | :--- | :--- |
| **Civil Rights Act of 1866** | 42 U.S.C. § 1982 | Equal right to inherit, purchase, lease, sell, and convey property regardless of race or color. |
| **Fair Housing Act (Title VIII, 1968)** | 42 U.S.C. §§ 3601–3619 | Prohibits discrimination based on Race, Color, Religion, Sex (incl. sexual orientation & gender identity), National Origin. § 3604(c) bans discriminatory statements/ads. |
| **Fair Housing Amendments Act of 1988** | 42 U.S.C. § 3604(f) | Prohibits discrimination based on Disability and Familial Status (children under 18, pregnancy). Mandates reasonable accommodations (assistance/service animals) and reasonable modifications (ramps/grab bars). |
| **Equal Credit Opportunity Act (ECOA)** | 15 U.S.C. § 1691 / Reg B | Prohibits credit & mortgage discrimination based on Race, Color, Religion, National Origin, Sex, Marital Status, Age, or receipt of Public Assistance (Section 8, SSDI, alimony). |
| **Community Reinvestment Act (CRA)** | 12 U.S.C. § 2901 | Prohibits **Redlining** (denying financial services to specific neighborhoods based on demographic composition). |
| **Home Mortgage Disclosure Act (HMDA)** | 12 U.S.C. § 2801 / Reg C | Requires data transparency on mortgage lending to prevent discriminatory denials and steering. |
| **Landmark Supreme Court Cases** | *Buchanan v. Warley* (1917)<br>*Shelley v. Kraemer* (1948)<br>*Inclusive Communities* (2015) | Struck down racial zoning ordinances; invalidated judicial enforcement of racially restrictive deed covenants; affirmed the **Disparate Impact** doctrine under the FHA. |
| **HUD Guidance & Modern Precedents** | HUD 2016 Criminal & LEP Memos<br>HUD 2021 Bostock Order<br>HUD Ad Targeting Rules | Prohibits blanket bans on arrest records, English-only language barriers as national origin proxies, sexual orientation/gender identity bias, and digital ad audience exclusion. |

---

## 🚀 Key Features

1. **Deterministic Heuristic Scanner (Tier 1)**: Sub-millisecond regex scanner checking explicit preferences, terms, and statutory triggers.
2. **Proxy & Disparate Impact Scanner (Tier 2)**: Detects subtle demographic proxies, neighborhood coded terms, blanket animal bans without assistance animal carveouts, and maternity leave lending restrictions.
3. **Google Gemini Semantic AI Evaluator (Tier 3)**: Deep contextual evaluation powered by Gemini (`gemini-2.5-flash`) for nuanced implicit bias, algorithmic ad exclusion, and disparate impact.
4. **Affirmative Prompt Rewriter (Tier 4)**: Generates safe, legally compliant rewrites that achieve the user's business objectives without unlawful criteria.
5. **Interactive Web UI Dashboard**: Modern dark-mode interface with live risk gauges, interactive violation cards, one-click copy rewrites, and built-in legal reference explorer.
6. **Rich CLI Tool**: Terminal audit utility with formatted tables, violation severities, and automated benchmark execution.
7. **Agent Probing Kit (`probekit/`)**: Counterfactual A/B probes that test what a loan-officer AI agent does with a prompt. Arms differ in one borrower cue or in the loan officer's framing; bias is the gap in false flags between arms (MortarBench §7.3). It can score agent drafts with this validator.

---

## 📦 Installation & Setup

```bash
# Clone and enter project directory
cd Prompt_Validation_Loan

# Install dependencies
pip install -r requirements.txt
```

### Optional: Set Gemini API Key
To enable Tier 3 deep semantic checks:
```bash
# In PowerShell:
$env:GEMINI_API_KEY="your-gemini-api-key"

# In Bash:
export GEMINI_API_KEY="your-gemini-api-key"
```
*(You can also configure your API key dynamically through the Web UI modal or via `--api-key` in the CLI.)*

---

## 🔬 Agent Probing Kit

The validator checks a prompt; `probekit/` checks the agent's answer. Each scenario is one JSON file with synthetic borrowers, a fixed correct output, and arms that differ in one factor.

**Setup.** Your agent exports and chat files stay where they are: `setup` only writes `probekit/private/config.json`, which git ignores.

```bash
pip install -r requirements.txt openpyxl
cp .env.example .env    # add your model's API key
python -m probekit setup --agents <exports folder> --prompts NV=<questions.xlsx> CE=<chats.xlsx>
python -m probekit agents    # your agents, as export/<name>
python -m probekit setup --map loan_structuring=export/<name> undisclosed_liability=export/<name> credit_summary=export/<name> bank_statement_review=export/<name>
python -m probekit run remittance --model gemini:gemini-2.5-flash --n 1    # or openai:<model>, anthropic:<model>; mock = no call
python -m probekit score remittance
```

Paid runs stop at the budget ($5; set `PROBEKIT_BUDGET_USD` in `.env`). Details: [`probekit/README.md`](probekit/README.md).

---

## 💻 CLI Usage

### 1. Audit a Prompt
```bash
python -m src.cli audit "Spacious 3-bedroom unit downtown. Adults only, no kids, near Christian church."
```

### 2. Audit with Custom Context & Raw JSON Output
```bash
python -m src.cli audit "Exclude minority inner-city zip codes from mortgage pre-approvals." --context mortgage_underwriting --json
```

### 3. Run Benchmark Test Suite (21 Cases)
```bash
python -m src.cli benchmark
```

### 4. Launch the Web UI Dashboard
```bash
python -m src.cli serve --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## 🐍 Python SDK Usage

```python
from src.engine import PromptValidator

validator = PromptValidator(gemini_api_key="your-api-key")

# Validate a prompt
result = validator.validate(
    prompt="Rental listing: No service animals permitted under any circumstances.",
    context="rental_listing"
)

print("Compliant:", result.is_compliant)  # False
print("Risk Score:", result.risk_score)     # 0.80
print("Violations:", len(result.violations))

for v in result.violations:
    print(f"- [{v.severity}] {v.category}: {v.law_cited} ({v.statutory_reference})")
    print(f"  Explanation: {v.explanation}")
    print(f"  Remediation: {v.remediation_guidance}")

print("\nSuggested Rewrite:")
print(result.suggested_compliant_prompt)
```

---

## 🧪 Benchmark Test Coverage

Run the automated pytest suite:
```bash
python -m pytest tests/test_benchmarks.py -v
```

The test suite validates 21 scenarios covering:
* `CASE_01_FAMILIAL_STATUS`: Banning children or indicating "adults only"
* `CASE_02_RELIGION`: Stating preference for church-going tenants
* `CASE_03_RACE_EXPLICIT`: Seeking white tenants for traditional demographics
* `CASE_04_LANGUAGE_LEP`: English-only requirements / LEP barriers
* `CASE_05_SERVICE_ANIMAL`: Enforcing pet bans against assistance animals
* `CASE_06_ECOA_MARITAL_STATUS`: Requiring male guarantors for unmarried women
* `CASE_07_SOURCE_OF_INCOME`: Blanket bans on Section 8 vouchers
* `CASE_08_CRIMINAL_RECORD_ARREST`: Disqualification based on arrest records
* `CASE_09_REDLINING_GEOGRAPHIC`: Filtering out minority inner-city ZIP codes
* `CASE_10_RACIAL_STEERING`: Steering Black buyers away from white neighborhoods
* `CASE_11_DISABILITY_RAMP`: Refusing reasonable wheelchair ramp modification
* `CASE_12_ALGORITHMIC_AD_EXCLUSION`: Social media ad targeting exclusions
* `CASE_13_RESTRICTIVE_COVENANT`: Racially restrictive deed covenants
* `CASE_14_MATERNITY_LEAVE_LENDING`: Pausing mortgage approval due to maternity leave
* `CASE_15_CRIME_FREE_EVICTION_ARREST`: Automatic lease termination on arrest
* `CASE_16_LGBTQ_DISCRIMINATION`: Exclusion of gay or transgender applicants
* `CASE_17_CODED_STEERING`: Coded demographic neighborhood steering
* `CASE_18_COMPLIANT_RENTAL`: Standard lawful rental listing
* `CASE_19_COMPLIANT_PET_POLICY`: Lawful pet policy with service animal carveout
* `CASE_20_COMPLIANT_UNDERWRITING`: Objective income and credit ratio evaluation
* `CASE_21_COMPLIANT_PREAPPROVAL`: Non-discriminatory credit pre-approval
