"""
Settings. The kit needs none: results, the spend ledger and the lock file default to probekit/results/.

A private folder holds what must not go in the repo: real agent exports, real prompt files (chat history), scenario
overlays, knowledge excerpts, run logs and the ledger, and the private text the leak check scans. It is probekit/private/
(git-ignored) when that folder exists, or any folder named by env PROBEKIT_PRIVATE. Its optional config.json uses the
keys below; paths are relative to that folder. Without config.json, its agents/ and excerpts/ subfolders are used.

prompt_files maps an id prefix to a file ({"NV": "prompts/chats.xlsx"}), so a scenario can name a real prompt by
id ("NV 559") without holding its text. prompt_text_in_repo (default false) says whether text copied from those files
may be in the repo: false for a public repo (any copy is a leak), true for a repo whose readers hold the files (copies
allowed without PII).
"""

import json
import os
from functools import lru_cache
from pathlib import Path

KIT = Path(__file__).resolve().parent
DEFAULT_PRIVATE = KIT / "private"

try:  # model API keys and PROBEKIT_BUDGET_USD can go in the repo's .env (copy .env.example), as for the validator
    from dotenv import load_dotenv
    load_dotenv(KIT.parent / ".env")
except ImportError:
    pass
PATH_KEYS = ("results_dir", "ledger", "spend_lock", "agents_dir", "excerpts_dir")


@lru_cache(maxsize=None)
def load():
    cfg = {"private": None, "results_dir": KIT / "results", "ledger": KIT / "results" / "spend.jsonl",
           "spend_lock": KIT / "results" / "SPEND_LOCK", "budget_usd": 5.0, "default_backend": None,
           "agents_dir": None, "agents": {}, "excerpts_dir": None, "mantle": {}, "corpora": [], "prompt_files": {},
           "prompt_text_in_repo": False, "blocked_terms": [], "overlays": {}}
    priv = os.environ.get("PROBEKIT_PRIVATE") or (DEFAULT_PRIVATE if DEFAULT_PRIVATE.is_dir() else None)
    if priv:
        priv = Path(priv).expanduser().resolve()
        raw = json.loads((priv / "config.json").read_text()) if (priv / "config.json").exists() else {}
        raw = {"agents_dir": "agents", "excerpts_dir": "excerpts", **raw}
        cfg.update({k: v for k, v in raw.items() if not k.startswith("_")})
        cfg.update({k: (priv / raw[k]).resolve() for k in PATH_KEYS if k in raw})
        for k in ("agents_dir", "excerpts_dir"):
            cfg[k] = cfg[k] if cfg[k].is_dir() else None
        cfg["corpora"] = [(priv / c).resolve() for c in raw.get("corpora", [])]
        files = raw.get("prompt_files", {})
        files = files if isinstance(files, dict) else {f"FILE{i}": f for i, f in enumerate(files, 1)}
        cfg["prompt_files"] = {k.upper(): (priv / v).resolve() for k, v in files.items()}
        cfg["private"] = priv
        if (priv / "overlays.json").exists():
            cfg["overlays"] = json.loads((priv / "overlays.json").read_text())
    if os.environ.get("PROBEKIT_BUDGET_USD"):
        cfg["budget_usd"] = float(os.environ["PROBEKIT_BUDGET_USD"])
    return cfg
