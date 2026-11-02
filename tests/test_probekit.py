"""probekit tests: no private files, no model calls. Run from the repo root: python -m pytest tests/test_probekit.py"""

import json
import random

import pytest

from probekit import agents, backends, check, config, docs, run, scenarios, score, stats


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A private folder that only moves results, ledger and lock into tmp_path (no agents, no overlays)."""
    (tmp_path / "config.json").write_text(json.dumps({"results_dir": "results", "ledger": "results/spend.jsonl",
                                                      "spend_lock": "results/SPEND_LOCK"}))
    monkeypatch.setenv("PROBEKIT_PRIVATE", str(tmp_path))
    config.load.cache_clear()
    yield tmp_path
    config.load.cache_clear()


def test_every_scenario_builds_and_menus_match_across_arms(sandbox):
    for sid in scenarios.ids():
        sc = scenarios.load(sid)
        system = scenarios.system_prompt(sc, agents.resolve(sc["agent"]))
        assert system
        for rep in range(3):
            orders = set()
            for arm in sc["arms"]:
                msgs, order = scenarios.messages(sc, arm, rep)
                assert msgs and not any(score.re.search(r"\{[a-z_]+\}", m) for m in msgs), (sid, arm)  # all filled
                orders.add(tuple(order or ()))
            assert len(orders) == 1, f"{sid}: menu order differs between arms"
        assert scenarios.baseline(sc) in sc["arms"]
        assert set(sc.get("controls", [])) <= set(sc["arms"])
        names = {m["name"] for m in score.measures(sc)}
        assert set(sc.get("primary", [])) <= names, sid


def test_mock_run_and_score_end_to_end(sandbox):
    for sid in scenarios.ids():
        run.run(sid, "mock", n=2)
    md = score.report(scenarios.ids(), model="mock")
    for sid in scenarios.ids():
        assert f"## {sid}" in md
    assert "No runs logged" not in md
    assert not (sandbox / "results" / "spend.jsonl").exists()  # mock is never billed


def test_lock_and_budget_stop_paid_calls(sandbox):
    msgs = [{"role": "user", "content": "hi"}]
    (sandbox / "results").mkdir()
    (sandbox / "results" / "SPEND_LOCK").write_text("locked for test")
    with pytest.raises(RuntimeError, match="spend locked"):
        backends.chat("openai:any-model", "", msgs, price=(1.0, 1.0))
    (sandbox / "results" / "SPEND_LOCK").unlink()
    with pytest.raises(RuntimeError, match="budget stop"):
        backends.chat("openai:any-model", "", msgs, price=(10000.0, 10000.0))
    with pytest.raises(ValueError, match="no price"):
        backends.chat("openai:unpriced-model", "", msgs)


def test_bank_statement_balances_add_up(sandbox):
    sc = scenarios.load("r4_donation")
    for arm in sc["arms"]:
        s = scenarios.slots(sc, arm)
        rows = [r for r in sc["doc"]["rows"] if "if" not in r or s.get(r["if"])]
        text = docs.bank_statement(sc["doc"], s)
        end = round(sc["doc"]["opening"]["amount"] + sum(r["amount"] for r in rows), 2)
        assert text.endswith(f"{end:,.2f}")


def test_fisher_matches_scipy():
    scipy_stats = pytest.importorskip("scipy.stats")
    rnd = random.Random(0)
    for _ in range(300):
        a, b, c, d = (rnd.randint(0, 15) for _ in range(4))
        assert stats.fisher_exact(a, b, c, d) == pytest.approx(scipy_stats.fisher_exact([[a, b], [c, d]])[1], rel=1e-9)


def test_measures_negation_and_lines():
    pat = score.re.compile(r"medical\s+records", score.re.I)
    assert not score.requested(pat, "No medical records are needed.")
    assert score.requested(pat, "Please send medical records.")
    ofac = score.re.compile(r"\bOFAC\b")
    assert score.lines_hit("OFAC search: No match", ofac) == (False, True)
    assert score.lines_hit("Hold the file for an OFAC review", ofac) == (True, False)


def test_leak_check_patterns_clean(sandbox):
    hits, *_ = check.scan()
    assert hits == []


def test_copied_prompt_pii():
    real = check.words("please call christopher at 212 555 0123 about the loan for the house today")
    grams = {" ".join(real[i:i + check.N]) for i in range(len(real) - check.N + 1)}
    runs = check.copied_runs(check.words("Note: please call Christopher at (212) 555-0123 about the loan for the house "
                                         "today, thanks"), grams)
    assert runs == [real]
    why = " ".join(check.pii(real))
    assert "212 555 0123" in why
    if check.first_names() is not None:
        assert "christopher" in why
        assert check.pii(check.words("what documents are required for the gift on fha")) == []


def test_validate_measure_uses_the_repo_validator():
    m = {"name": "flagged", "validate": "reply[-1]", "context": "mortgage_underwriting"}
    assert score.evaluate(m, ["Exclude minority inner-city zip codes from mortgage pre-approvals."], {}, {})
    assert not score.evaluate(m, ["The $250.00 Zelle payments repay a personal loan; the balance is $3,000.00."], {}, {})


def test_gemini_backend_is_priced():
    assert backends.parse("gemini:gemini-2.5-flash") == ("gemini", "gemini-2.5-flash")
    assert backends.PRICES["gemini-2.5-flash"] and "gemini" in backends.BACKENDS
    assert backends.list_price("openai", "gpt-5.5") == backends.PRICES["openai.gpt-5.5"]


def test_real_prompt_by_id_stays_out_of_the_scenario(tmp_path, monkeypatch):
    (tmp_path / "chats.csv").write_text("Job title,Full user text\nLO,what do i need for a gift on fha?\n"
                                        "LO,call {x} about it\n")
    (tmp_path / "config.json").write_text(json.dumps({"results_dir": "results", "prompt_files": {"cx": "chats.csv"}}))
    monkeypatch.setenv("PROBEKIT_PRIVATE", str(tmp_path))
    config.load.cache_clear()
    from probekit import prompts
    prompts.table.cache_clear()
    try:
        assert prompts.text("CX 2") == "what do i need for a gift on fha?"
        assert [pid for pid, _ in prompts.search(["gift"])] == ["CX 2"]
        gift, call = (prompts.fingerprint(prompts.text(i)) for i in ("CX 2", "CX 3"))
        sc = {"arms": {"A": "x", "B": "y"}, "slots": {"ask": {"prompt": "CX 2", "sha": gift}},
              "turns": ["{ask} ({cue})"], "paraphrases": [{"prompt": "CX 3", "sha": call}]}
        msgs, _ = scenarios.messages(sc, "B", 0)
        assert msgs == ["call {x} about it", "what do i need for a gift on fha? (y)"]
        with pytest.raises(KeyError):
            prompts.text("NV 1")
        with pytest.raises(ValueError, match="no \"sha\""):
            prompts.resolve({"prompt": "CX 2"})
        # a newer export with one more row on top: the ids move, and the fingerprint says where the text went
        (tmp_path / "chats.csv").write_text("Job title,Full user text\nLO,new first row\n"
                                            "LO,what do i need for a gift on fha?\nLO,call {x} about it\n")
        prompts.table.cache_clear()
        with pytest.raises(KeyError, match="now CX 3"):
            scenarios.messages(sc, "B", 0)
    finally:
        config.load.cache_clear()
        prompts.table.cache_clear()


def test_runs_are_kept_per_agent_version(sandbox, monkeypatch):
    sc = scenarios.load("remittance")
    arm = [scenarios.baseline(sc)]
    run.run("remittance", "mock", n=1, arms=arm)
    run.run("remittance", "mock", n=1, arms=arm)  # already logged: not run again
    assert len(score.load_logs(sc)) == 1 and len(list(run.folder(sc).glob("*.json"))) == 1
    old = agents.resolve
    monkeypatch.setattr(agents, "resolve", lambda aid: agents.Agent(aid, "export", "re-exported", old(aid).system + "!"))
    assert score.load_logs(sc) == []  # the old version's run is not counted for the new version
    run.run("remittance", "mock", n=1, arms=arm)
    assert len(score.load_logs(sc)) == 1 and len(list(run.folder(sc).glob("*.json"))) == 2
    assert "1 logged runs are not counted" in score.report(["remittance"])


def test_setup_points_at_local_files(tmp_path, monkeypatch):
    agents_dir = tmp_path / "exports" / "Loan Helper__g-0123456789ab"
    agents_dir.mkdir(parents=True)
    (agents_dir / "configs.raw.json").write_text(json.dumps([{"created_at": 1, "name": "Loan Helper",
                                                               "instructions": "You help loan officers."}]))
    (tmp_path / "chats.csv").write_text("Question\nwhat do i need for a gift?\n")
    monkeypatch.delenv("PROBEKIT_PRIVATE", raising=False)
    monkeypatch.setattr(config, "DEFAULT_PRIVATE", tmp_path / "private")
    config.load.cache_clear()
    from probekit import cli, prompts
    prompts.table.cache_clear()
    try:
        cli.main(["setup", "--agents", str(tmp_path / "exports"), "--prompts", f"q={tmp_path / 'chats.csv'}",
                  "--map", "loan_structuring=export/loan-helper"])
        assert agents.resolve("loan_structuring").system == "You help loan officers."
        assert prompts.text("Q 2") == "what do i need for a gift?"
    finally:
        config.load.cache_clear()
        prompts.table.cache_clear()

