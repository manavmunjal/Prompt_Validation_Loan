"""
Run a scenario: every arm × reps 0..n-1, for one agent and one model. Arms are interleaved (A, B, A, B, ...) so drift
over time hits all arms equally. Each run is logged as JSON under the agent's version (a hash of its instructions and
knowledge files): a run already logged for this version is skipped, so it is never paid twice, and a re-exported or
remapped agent gets runs of its own instead of mixing with the old ones.
"""

import glob
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import agents, backends, check, config, scenarios

_lock = threading.Lock()


def folder(sc, agent_id=None):
    """results/<scenario>/ for the scenario's own agent; results/<scenario>@<agent>/ for any other agent."""
    if agent_id in (None, sc["agent"]):
        return config.load()["results_dir"] / sc["id"]
    return config.load()["results_dir"] / f"{sc['id']}@{agent_id.replace('/', '_').replace(':', '_')}"


def log_path(sc, agent_id, agent, model, arm, temperature, rep):
    return folder(sc, agent_id) / f"{model.replace(':', '_')}__{arm}__T{temperature:g}__rep{rep}__{agent.sha}.json"


def logs(sc, agent_id, agent, temperature=1.0):
    """The runs that count for this agent version: its own logs, plus the scenario's extra_logs (earlier runs of the
    scenario's own agent kept elsewhere, named in a private overlay). Also returns how many logs in the folder belong
    to other agent versions."""
    found = sorted(folder(sc, agent_id).glob(f"*__T{temperature:g}__rep*.json"))
    counted = {p for p in found if p.stem.endswith(f"__{agent.sha}")}
    out = [json.loads(p.read_text()) for p in sorted(counted)]
    for pattern in sc.get("extra_logs", []) if agent_id in (None, sc["agent"]) else []:
        for p in map(Path, sorted(glob.glob(str(config.load()["results_dir"] / pattern)))):
            log = json.loads(p.read_text())
            if log["temperature"] == temperature:
                out.append({"model": sc.get("extra_logs_model", "unknown"), **log})
                counted.add(p)
    return out, len(set(found) - counted)


def run_one(sc, agent, agent_id, model, arm, temperature, rep, price=None):
    msgs, order = scenarios.messages(sc, arm, rep)
    system, turns, usd = scenarios.system_prompt(sc, agent), [], 0.0
    for msg in msgs:
        turns.append({"role": "user", "content": msg})
        reply, u = backends.chat(model, system, turns, temperature=temperature,
                                 tag=f"probe/{sc['id']}/{model}/{arm}", price=price)
        turns.append({"role": "assistant", "content": reply})
        usd += u["usd"]
    log = {"scenario": sc["id"], "source_prompts": sc.get("source", ""), "gold": sc["gold"], "agent": agent.id,
           "agent_source": agent.source, "agent_sha": agent.sha, "model": model, "arm": arm, "cue": sc["arms"][arm],
           "temperature": temperature, "rep": rep, "turns": turns, "usd": round(usd, 5),
           **({"paraphrase": rep % len(sc["paraphrases"]), "menu_order": order} if order else {})}
    path = log_path(sc, agent_id, agent, model, arm, temperature, rep)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=1, ensure_ascii=False))
    with _lock:
        print(f"{sc['id']:14} {model:28} {arm:22} T{temperature:g} rep{rep:2} ${usd:.4f}  total ${backends.spent():.3f}",
              flush=True)


def run(sid, model, agent_id=None, n=1, arms=None, temperature=1.0, workers=1, price=None):
    sc = scenarios.load(sid)
    agent = agents.resolve(agent_id or sc["agent"])
    done = {(log["model"], log["arm"], log["rep"]) for log in logs(sc, agent_id, agent, temperature)[0]}
    jobs = [(arm, rep) for rep in range(n) for arm in (arms or list(sc["arms"])) if (model, arm, rep) not in done]
    pii = sorted({h for arm, rep in jobs for msg in scenarios.messages(sc, arm, rep)[0] for h in check.copied_pii(msg)})
    if pii:
        raise SystemExit(f"{sid}: not run. Text copied from a real prompt may hold PII:\n" + "\n".join(pii))
    print(f"{sid}: agent {agent.id} ({agent.source}, {agent.sha}), model {model}, {len(jobs)} runs to do")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f in [pool.submit(run_one, sc, agent, agent_id, model, arm, temperature, rep, price) for arm, rep in jobs]:
            f.result()
