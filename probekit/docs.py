"""
Synthetic documents built from a scenario's "doc" spec. Arithmetic is computed, not typed: a wrong running balance
would itself be a reason to flag the file.

  {"template": "... {name} ..."}                        text with the arm's slots filled in
  {"builder": "bank_statement", "prefix": "...", "header": [lines], "opening": {"label": ..., "amount": ...},
   "closing_label": "...", "rows": [{"id", "date", "desc", "amount", "if": slot}]}
      rows with "if" appear only in arms where that slot is true; on the same day, credits come before debits
"""


def build(spec, slots):
    if "template" in spec:
        return spec["template"].format(**slots)
    if spec.get("builder") == "bank_statement":
        return spec.get("prefix", "").format(**slots) + bank_statement(spec, slots)
    raise ValueError(f"unknown doc spec: {sorted(spec)}")


def bank_statement(spec, slots):
    rows = sorted((r for r in spec["rows"] if "if" not in r or slots.get(r["if"])),
                  key=lambda r: (r["date"], r["amount"] < 0, r["id"]))
    bal = spec["opening"]["amount"]
    out = [*spec["header"], f"{spec['opening']['label']}: {bal:,.2f}"]
    for r in rows:
        bal = round(bal + r["amount"], 2)
        sign = "+" if r["amount"] > 0 else "-"
        out.append(f"{r['id']} | {r['date']} | {r['desc'].format(**slots)} | {sign}{abs(r['amount']):,.2f} | {bal:,.2f}")
    out.append(f"{spec['closing_label']}: {bal:,.2f}")
    return "\n".join(out)
