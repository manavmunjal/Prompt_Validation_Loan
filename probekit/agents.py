"""
Agent settings: the system prompt an agent runs with.

- Stand-in: agents/<id>/agent.json in this kit. Written for this kit; it plays the role of a real agent but
  holds none of its text, so results on a stand-in say nothing about the real agent.
- Export: a ChatGPT custom-GPT export folder (configs.raw.json; the newest config's instructions, word for word).
  Named in the private config, where an id equal to a stand-in's replaces the stand-in (a scenario names one agent id
  everywhere); found under the private agents_dir as export/<name>; or given directly as export:<folder>.
- bare: no system prompt (the model alone).

Knowledge files are appended to the system prompt: a custom GPT retrieves from them, and agent instructions often call
them the source of truth.
"""

import glob
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import config

STANDINS = config.KIT / "agents"


@dataclass
class Agent:
    id: str
    source: str  # "stand-in", "export" or "bare"
    name: str
    system: str

    @property
    def sha(self):
        return hashlib.sha256(self.system.encode()).hexdigest()[:12]


def _with_knowledge(text, files):
    for f in files:
        text += f"\n\n# Knowledge file: {Path(f).name}\n\n" + Path(f).read_text()
    return text


def _export(aid, folder, knowledge=()):
    configs = json.loads((folder / "configs.raw.json").read_text())
    newest = max(configs, key=lambda c: c["created_at"])
    system = _with_knowledge(newest["instructions"], [folder / "files" / k for k in knowledge])
    return Agent(aid, "export", newest.get("name") or folder.name, system)


def _exports():
    """export/<name> for every export folder under the private agents_dir; a repeated name gets 6 chars of its id."""
    root, out = config.load()["agents_dir"], {}
    if not root:
        return out
    for folder in sorted(p for p in root.iterdir() if (p / "configs.raw.json").exists()):
        name, _, gid = folder.name.partition("__")
        slug = "export/" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        out[f"{slug}-{gid[2:8]}" if slug in out else slug] = folder
    return out


def resolve(aid):
    cfg = config.load()
    if aid == "bare":
        return Agent("bare", "bare", "no system prompt", "")
    if aid.startswith("export:"):
        return _export(aid, Path(aid[len("export:"):]).expanduser().resolve())
    if aid in cfg["agents"]:
        entry = cfg["agents"][aid]
        folder = Path(glob.glob(str(cfg["agents_dir"] / entry["export"]))[0])
        return _export(aid, folder, entry.get("knowledge", []))
    spec_file = STANDINS / aid / "agent.json"
    if spec_file.exists():
        spec, d = json.loads(spec_file.read_text()), spec_file.parent
        system = _with_knowledge((d / spec["instructions"]).read_text(), [d / k for k in spec.get("knowledge", [])])
        return Agent(aid, "stand-in", spec["name"], system)
    exports = _exports()
    if aid in exports:
        return _export(aid, exports[aid])
    raise KeyError(f"unknown agent {aid!r}; see `python -m probekit agents`")


def available():
    """(id, source, name) for every agent id that resolve() accepts, except export:<folder>."""
    cfg = config.load()
    rows = [("bare", "bare", "no system prompt")]
    for p in sorted(STANDINS.iterdir()):
        if (p / "agent.json").exists() and p.name not in cfg["agents"]:
            rows.append((p.name, "stand-in", json.loads((p / "agent.json").read_text())["name"]))
    rows += [(k, "export (private)", v["export"].split("__")[0]) for k, v in cfg["agents"].items()]
    rows += [(k, "export (private)", f.name.split("__")[0]) for k, f in _exports().items()]
    return rows
