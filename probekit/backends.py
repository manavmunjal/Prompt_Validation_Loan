"""
Model calls, with a spend ledger, a hard budget and a lock file.

A model is "<backend>:<name>" with backend gemini (as in src/scanners/semantic_scanner.py), openai, anthropic or mantle
(Amazon Bedrock Mantle), or "mock" (no call; for trying a scenario end to end). Keys come from the environment or the
repo's .env, as for the validator. A bare name uses the configured default backend. No paid call starts while the
lock file exists, or if its worst case could take the ledger past the budget. Every paid call is logged to the ledger.
"""

import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config

# USD per 1M tokens (input, output), rounded up from public list prices; models without a published price get a
# deliberately high bound. A name is looked up as given, then with its backend in front (openai:gpt-5.5 has the price of
# openai.gpt-5.5). Any other model needs --price IN,OUT.
PRICES = {"gemini-2.5-flash": (0.30, 2.50), "gemini-2.5-flash-lite": (0.10, 0.40), "gemini-2.5-pro": (1.25, 10.00),
          "openai.gpt-oss-120b": (0.20, 0.80), "anthropic.claude-haiku-4-5": (1.10, 5.50),
          "openai.gpt-oss-20b": (0.10, 0.40), "qwen.qwen3-235b-a22b-2507": (0.50, 2.00),
          "deepseek.v3.2": (1.00, 3.00), "openai.gpt-5.5": (5.50, 33.00),
          "mistral.mistral-large-3-675b-instruct": (2.00, 6.00), "openai.gpt-5.6-sol": (4.40, 22.00),
          "openai.gpt-5.4": (2.75, 16.50)}
MAX_TOKENS = {"qwen.qwen3-235b-a22b-2507": 2500, "deepseek.v3.2": 2500, "mistral.mistral-large-3-675b-instruct": 2500}


def list_price(backend, name):
    return PRICES.get(name) or PRICES.get(f"{backend}.{name}")


def max_tokens(name):
    return MAX_TOKENS.get(name, 6000 if "gpt-5" in name else 8000 if "gemini" in name else 3000)


def parse(model):
    if model == "mock":
        return "mock", "mock"
    if ":" in model:
        return tuple(model.split(":", 1))
    if not config.load()["default_backend"]:
        raise ValueError(f"model {model!r} names no backend: use gemini:, openai:, anthropic:, mantle: or mock")
    return config.load()["default_backend"], model


def spent():
    ledger = config.load()["ledger"]
    return sum(json.loads(line)["usd"] for line in ledger.open()) if ledger.exists() else 0.0


def chat(model, system, messages, temperature=1.0, tag="", price=None):
    """messages: [{"role": "user"|"assistant", "content": str}, ...]. Returns (text, usage dict)."""
    backend, name = parse(model)
    if backend == "mock":
        return _mock(system, messages), {"in": 0, "out": 0, "usd": 0.0}
    cfg = config.load()
    if cfg["spend_lock"].exists():  # created by the budget owner; only they remove it
        raise RuntimeError(f"spend locked: {cfg['spend_lock'].read_text().strip()}")
    if not (price or list_price(backend, name)):
        raise ValueError(f"no price for {name!r}: pass --price IN,OUT (USD per 1M tokens)")
    p_in, p_out = price or list_price(backend, name)
    # worst case: about 3 characters per token for the input, and the full output allowance
    tokens_in = max(8000, len(system + "".join(m["content"] for m in messages)) // 3)
    worst = (tokens_in * p_in + max_tokens(name) * p_out) / 1e6
    if spent() + worst > cfg["budget_usd"]:
        raise RuntimeError(f"budget stop: spent ${spent():.4f} of ${cfg['budget_usd']}")
    text, tin, tout = BACKENDS[backend](name, system, messages, temperature)
    usd = (tin * p_in + tout * p_out) / 1e6
    cfg["ledger"].parent.mkdir(parents=True, exist_ok=True)
    with cfg["ledger"].open("a") as f:
        f.write(json.dumps({"t": time.time(), "model": model, "in": tin, "out": tout, "usd": usd, "tag": tag}) + "\n")
    return text, {"in": tin, "out": tout, "usd": usd}


def _post(url, data, headers):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def _chat_completions(name, system, messages, temperature):
    body = {"model": name, "messages": [{"role": "system", "content": system}, *messages]}
    if "gpt-5" in name:  # GPT-5.x takes max_completion_tokens and only its default temperature
        body["max_completion_tokens"] = max_tokens(name)
    else:
        body.update({"max_tokens": max_tokens(name), "temperature": temperature})
    return body


def _anthropic_body(name, system, messages, temperature):
    return {"model": name, "max_tokens": max_tokens(name), "temperature": temperature, "system": system,
            "messages": messages}


def _parse(b):
    if "content" in b:  # Anthropic Messages API
        return "".join(c.get("text", "") for c in b["content"]), b["usage"]["input_tokens"], b["usage"]["output_tokens"]
    return b["choices"][0]["message"].get("content") or "", b["usage"]["prompt_tokens"], b["usage"]["completion_tokens"]


def _openai(name, system, messages, temperature):
    url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions"
    body = _chat_completions(name, system, messages, temperature)
    return _parse(_post(url, json.dumps(body).encode(), {"Content-Type": "application/json",
                                                          "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}))


def _anthropic(name, system, messages, temperature):
    body = _anthropic_body(name, system, messages, temperature)
    return _parse(_post("https://api.anthropic.com/v1/messages", json.dumps(body).encode(),
                        {"Content-Type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                         "anthropic-version": "2023-06-01"}))


def _gemini(name, system, messages, temperature):
    """Google Gemini through google-genai, the SDK the validator uses. Key: env GEMINI_API_KEY. Thinking tokens are
    billed as output, so they count as output here."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    contents = [types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
                for m in messages]
    r = client.models.generate_content(model=name, contents=contents, config=types.GenerateContentConfig(
        system_instruction=system, temperature=temperature, max_output_tokens=max_tokens(name)))
    u = r.usage_metadata
    return r.text or "", u.prompt_token_count or 0, (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)


def _mantle(name, system, messages, temperature):
    """Amazon Bedrock Mantle, signed with the local AWS credentials. Project id: env PROBEKIT_MANTLE_PROJECT, or the
    private config's mantle.env_file and mantle.project_key."""
    import boto3
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    m = config.load()["mantle"]
    region = m.get("region", "us-east-2")
    project = os.environ.get("PROBEKIT_MANTLE_PROJECT")
    if not project:
        env = dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", Path(m["env_file"]).expanduser().read_text(), re.M))
        project = env[m["project_key"]].strip()
    if name.startswith("anthropic."):
        path, body = "/anthropic/v1/messages", _anthropic_body(name, system, messages, temperature)
        headers = {"anthropic-version": "2023-06-01", "anthropic-workspace-id": project}
    else:  # GPT-5.x is served under /openai/v1, the other models under /v1
        path = "/openai/v1/chat/completions" if name.startswith("openai.gpt-5") else "/v1/chat/completions"
        body, headers = _chat_completions(name, system, messages, temperature), {"OpenAI-Project": project}
    url, data = f"https://bedrock-mantle.{region}.api.aws{path}", json.dumps(body).encode()
    req = AWSRequest(method="POST", url=url, data=data, headers={"Content-Type": "application/json", **headers})
    SigV4Auth(boto3.Session().get_credentials(), "bedrock", region).add_auth(req)
    return _parse(_post(url, data, dict(req.headers)))


def _mock(system, messages):
    """Stands in for a model: picks 1-4 menu items at random (seeded by the conversation), else returns a fixed line."""
    ids = re.findall(r"^(M\d+):", messages[-1]["content"], re.M)
    rnd = random.Random(hashlib.sha256((system + json.dumps(messages)).encode()).hexdigest())
    if ids:
        return json.dumps({"attention_item_ids": rnd.sample(ids, rnd.randint(1, min(4, len(ids))))})
    return "(mock reply: no model was called)"


BACKENDS = {"gemini": _gemini, "openai": _openai, "anthropic": _anthropic, "mantle": _mantle}
