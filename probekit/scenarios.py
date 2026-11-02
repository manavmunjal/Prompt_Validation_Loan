"""
Scenarios: one JSON file per probe in scenarios/ (fields in scenarios/README.md). Every arm sees the same messages
except the arm's slots. A slot or paraphrase can be {"prompt": "NV 559", "sha": "..."}: a real prompt read from the
private prompt files at run time, so the shared file holds only its id and fingerprint (prompts.py). A private overlay (overlays.json) can replace top-level fields
of a scenario, e.g. the original wording.
"""

import json
import random

from . import config, docs, prompts

DIR = config.KIT / "scenarios"


def ids():
    return sorted(p.stem for p in DIR.glob("*.json") if not p.stem.startswith("_"))


def load(sid):
    sc = json.loads((DIR / f"{sid}.json").read_text())
    sc.update(config.load()["overlays"].get(sid, {}))
    sc["id"] = sid
    return sc


def baseline(sc):
    return sc.get("baseline") or sorted(sc["arms"])[0]


def real(v):
    """A slot value or paraphrase: text as given, or the text of a real prompt for {"prompt": id, "sha": ...}."""
    return prompts.resolve(v) if isinstance(v, dict) and "prompt" in v else v


def slots(sc, arm):
    cue = sc["arms"][arm]
    return {k: real(v) for k, v in {**sc.get("slots", {}), **(cue if isinstance(cue, dict) else {"cue": cue})}.items()}


def messages(sc, arm, rep):
    """The loan officer's messages for one run, and the menu order (shuffled with the same seed in every arm)."""
    s, order = slots(sc, arm), None
    if "menu" in sc:
        order = list(sc["menu"])
        random.Random(rep).shuffle(order)
        s["menu"] = "\n".join(f"{k}: {sc['menu'][k]}" for k in order)
    if "doc" in sc:
        s["doc"] = docs.build(sc["doc"], s)
    if "paraphrases" in sc:
        p = sc["paraphrases"][rep % len(sc["paraphrases"])]
        first = [real(p).replace("{", "{{").replace("}", "}}") if isinstance(p, dict) else p]  # real text: no slots
    else:
        first = []
    return [t.format(**s) for t in first + sc["turns"]], order


def excerpt(name):
    """A knowledge-file excerpt: the private copy (the agent's own file) if configured, else the kit's own."""
    for d in (config.load()["excerpts_dir"], config.KIT / "excerpts"):
        if d and (d / f"{name}.txt").exists():
            return (d / f"{name}.txt").read_text()
    raise FileNotFoundError(f"knowledge excerpt {name!r} not found")


def system_prompt(sc, agent):
    system = agent.system
    if "excerpt" in sc:
        system += "\n\n# Knowledge file excerpt\n\n" + excerpt(sc["excerpt"])
    if "date" in sc:  # ChatGPT's own system prompt carries the date; without it the agent guesses one
        system += f"\n\nCurrent date: {sc['date']}."
    return system
