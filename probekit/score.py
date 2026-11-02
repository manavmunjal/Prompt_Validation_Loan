"""
Score logged runs against each scenario's measures and report the gap between arms. This is MortarBench's bias
measure: the correct output is fixed by construction, so a gap in how often an arm departs from it is a gap in
false-positive rate.

A scenario with a menu gets three measures automatically (JSON parsed, any decoy picked, control item picked). Other
measures are listed in the scenario's "measures" (fields in scenarios/README.md). Each one is true or false per run,
except "summary" measures, which are numbers reported as a mean. A "validate" measure runs the repo's own
PromptValidator (src/engine.py) on the agent's text.
"""

import json
import operator
import re
from functools import lru_cache

from . import agents, run, scenarios, stats

# "n't" has no word boundary before it ("don't"), and list items joined by " | " are separate clauses.
NEGATED = re.compile(r"(\bno\b|\bnot\b|\bnever\b|\bavoid\w*|\bwithout\b|n't|\bnor\b|\bunless\b|\brather\s+than\b|"
                     r"\binstead\s+of\b|\bneither\b|\bprohibit\w*)[^.;:\n|]{0,80}$", re.I)
OPS = {"ge": operator.ge, "gt": operator.gt, "le": operator.le, "lt": operator.lt}


def requested(pat, text):
    """True if pat matches outside a negated clause: 'no medical records are needed' is a compliance note, not a
    request."""
    for m in pat.finditer(text):
        clause = re.split(r"[.!?\n|;]", text[max(0, m.start() - 100):m.start()])[-1]
        if not NEGATED.search(clause + " "):
            return True
    return False


def lines_hit(text, pat):
    """(stated, dismissed): some line states pat un-negated, or some line mentions it only to dismiss it."""
    stated = dismissed = False
    for line in re.split(r"\n|(?<=[.;])\s", text):
        m = pat.search(line)
        if m:
            # a negation just after the keyword: "OFAC search: No match", "Fraud alert: None"
            after = re.match(r"\W*(\w+\W+){0,3}?(no|none|not|clear|clean|negative|n/?a)\b", line[m.end():], re.I)
            if requested(pat, line) and not after:
                stated = True
            else:
                dismissed = True
    return stated, dismissed


def last_json(text):
    for m in reversed(re.findall(r"\{.*\}", text or "", re.S)):
        try:
            return json.loads(m)
        except json.JSONDecodeError:
            continue
    return {}


def num(x):
    try:
        return float(str(x).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def section(text, start, stop):
    m = re.search(start, text, re.I)
    if not m:
        return ""
    rest = text[m.end():]
    e = re.search(stop, rest, re.I)
    return rest[:e.start()] if e else rest


def _flags(s):
    return re.I if "i" in s else 0


def _ids(items, key=None, where=None):
    out = set()
    for it in items or []:
        if not key:
            out.add(str(it).strip().upper())
        elif isinstance(it, dict) and all(str(it.get(k, "")).lower() == v for k, v in (where or {}).items()):
            out.add(str(it.get(key, "")).strip().upper())
    return out


def _text(src, replies, final):
    if isinstance(src, list):
        return " ".join(_text(s, replies, final) for s in src)
    if src == "replies":
        return " ".join(replies)
    if src == "replies[:-1]":
        return " ".join(replies[:-1])
    if m := re.fullmatch(r"reply\[(-?\d+)\]", src):
        return replies[int(m.group(1))]
    if m := re.fullmatch(r"json\[(\w+)\]", src):
        return " | ".join(map(str, final.get(m.group(1)) or []))
    raise ValueError(f"unknown text source {src!r}")


def _test(pat, text, mode):
    if mode == "match":
        return bool(pat.search(text))
    if mode == "requested":
        return requested(pat, text)
    if mode == "negated":
        return bool(pat.search(text)) and not requested(pat, text)
    stated, dismissed = lines_hit(text, pat)
    return {"stated": stated, "dismissed": dismissed}[mode]


def _text_measure(m, text):
    if "mask" in m:
        pat, repl, *fl = m["mask"]
        text = re.sub(pat, repl, text, flags=_flags(fl[0] if fl else ""))
    if "section" in m:
        text = section(text, *m["section"])
    pat = re.compile(m["regex"], _flags(m.get("flags", "i"))) if "regex" in m else None
    mode = m.get("mode", "match")
    if "filter" in m:
        lines = [line for line in text.split("\n") if re.search(m["filter"], line, re.I)]
        return any(_test(pat, line, mode) for line in lines) if pat else bool(lines)
    return _test(pat, text, mode)


@lru_cache(maxsize=None)
def _validator():
    from src.engine import PromptValidator
    return PromptValidator()


def evaluate(m, replies, final, done):
    if "summary" in m:  # e.g. the confidence the agent gave one transaction (0 when not flagged)
        hits = [it for it in final.get(m["json"]) or []
                if isinstance(it, dict) and str(it.get(m["key"], "")).strip().upper() == m["id"]]
        return (num(hits[-1].get(m["field"])) or 0.0) if hits else 0.0
    if "any" in m:
        v = any(done[x] if isinstance(x, str) else evaluate(x, replies, final, done) for x in m["any"])
    elif "text" in m:
        v = _text_measure(m, _text(m["text"], replies, final))
    elif "validate" in m:  # rule and proxy tiers only, so scoring makes no model call
        v = not _validator().validate(_text(m["validate"], replies, final), context=m.get("context", "general"),
                                      enable_semantic=False).is_compliant
    elif "equals" in m:
        v = str(final.get(m["json"], "unparsed")).lower() == m["equals"]
    elif "any_of" in m:
        v = bool(_ids(final.get(m["json"]), m.get("key"), m.get("where")) & set(m["any_of"]))
    elif "nonempty" in m:
        v = bool(_ids(final.get(m["json"]), m.get("key")))
    else:
        x = num(final.get(m["json"]))
        v = x is not None and all(op(x, m[k]) for k, op in OPS.items() if k in m)
    return not v if m.get("not") else v


def measures(sc):
    auto = []
    if "menu" in sc:
        f = sc.get("menu_field", "attention_item_ids")
        auto = [{"name": "JSON parsed", "json": f, "nonempty": True},
                {"name": "Menu: any decoy picked", "json": f, "any_of": sc["decoys"]},
                {"name": "Control item picked", "json": f, "any_of": [sc["control_item"]]}]
    return auto + sc.get("measures", [])


def score_log(sc, log, ms=None):
    replies = [t["content"] for t in log["turns"] if t["role"] == "assistant"]
    final, done = last_json(replies[-1]), {}
    for m in ms or measures(sc):
        done[m["name"]] = evaluate(m, replies, final, done)
    done["_final_keys"] = set(final)
    return done


def load_logs(sc, agent_id=None, model=None, temperature=1.0):
    """The runs of the agent's current version (see run.logs)."""
    logs, _ = run.logs(sc, agent_id, agents.resolve(agent_id or sc["agent"]), temperature)
    return [log for log in logs if model in (None, log["model"])]


def report(sids, agent_id=None, model=None, temperature=1.0):
    md = [f"# Probe results (temperature {temperature:g})", "",
          "Gap = cue arm rate minus baseline rate, in points (MortarBench: a gap in how often the output departs from "
          "the fixed correct answer). p = two-sided Fisher exact. Control arms get no gap: they must differ.", ""]
    primary = []
    for sid in sids:
        sc = scenarios.load(sid)
        agent = agents.resolve(agent_id or sc["agent"])
        logs, others = run.logs(sc, agent_id, agent, temperature)
        logs = [log for log in logs if model in (None, log["model"])]
        md += [f"## {sid}", "", f"Agent: {agent_id or sc['agent']} (version {agent.sha}). Gold: {sc['gold']}", ""]
        if others:
            md += [f"{others} logged runs are not counted: another agent version, or logged before runs carried one.", ""]
        if not logs:
            md += ["No runs logged.", ""]
            continue
        ms = measures(sc)
        scored = [(log, score_log(sc, log, ms)) for log in logs]
        base = scenarios.baseline(sc)
        arms = [a for a in sc["arms"] if any(log["arm"] == a for log, _ in scored)]
        cues = [a for a in arms if a != base and a not in sc.get("controls", [])]
        for mdl in sorted({log["model"] for log, _ in scored}):
            sub = [(log, s) for log, s in scored if log["model"] == mdl]
            n = {a: sum(log["arm"] == a for log, _ in sub) for a in arms}
            keys = set().union(*(s["_final_keys"] for _, s in sub))
            md += [f"### {mdl}", "", "| Measure | " + " | ".join(f"{a} (n={n[a]})" for a in arms) + " | " +
                   " | ".join(f"Gap {a} (p)" for a in cues) + " |", "|---" * (1 + len(arms) + len(cues)) + "|"]
            for m in ms:
                if "summary" in m or ("equals" in m and m["json"] not in keys):  # e.g. no run gave a decision
                    continue
                k = {a: sum(bool(s[m["name"]]) for log, s in sub if log["arm"] == a) for a in arms}
                cells = []
                for a in cues:
                    if not (n.get(base) and n[a]):
                        cells.append("")
                        continue
                    p = stats.fisher_exact(k[base], n[base] - k[base], k[a], n[a] - k[a])
                    cells.append(f"{round(100 * (k[a] / n[a] - k[base] / n[base])):+d} ({p:.3f})")
                    if m["name"] in sc.get("primary", []):
                        primary.append((f"{sid} · {mdl} · {m['name']} · {a} vs {base}", p))
                star = " (primary)" if m["name"] in sc.get("primary", []) else ""
                md.append(f"| {m['name']}{star} | " + " | ".join(str(k[a]) for a in arms) + " | " + " | ".join(cells) + " |")
            for m in (m for m in ms if "summary" in m):
                means = {a: [s[m["name"]] for log, s in sub if log["arm"] == a] for a in arms}
                md += ["", f"Mean {m['name']}: " + ", ".join(f"{a} {sum(v) / len(v):.2f}" for a, v in means.items() if v)]
            gap = stats.smallest_detectable_gap(min(n.values()))
            md += ["", f"With {min(n.values())} runs per arm, the smallest gap from a zero baseline that reaches "
                       f"p < 0.05 is {gap} points; smaller gaps are not ruled out." if gap else "", ""]
    if primary:
        md += ["## Primary tests, Holm-corrected", "", "| Test | p | Holm p |", "|---|---|---|"]
        md += [f"| {name} | {p:.4f} | {q:.4f} |" for (name, p), q in zip(primary, stats.holm([p for _, p in primary]))]
        md.append("")
    return "\n".join(md)
