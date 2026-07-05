"""Regression tests for the vf.Rubric wiring (requires `verifiers`; run under a
3.10+ venv). Locks two invariants that a plain weighted-sum rubric gets wrong:

1. partial credit is NOT added on full success (terminal == 1) — no double count.
2. the zero-tool-call gate forces total 0 regardless of any other signal.
"""

import pytest

pytest.importorskip("verifiers")

import bodega_env.reward_funcs as rf  # noqa: E402

STORE = "http://store.test"
KEY_VAR = "TEST_VERIFY_KEY"

T4_SPEC = {
    "type": "cart_exact",
    "items": [{"sku": "GRO-1", "color": "green", "size": "One Size", "qty": 2}],
}
T4_INFO = {"tier": "t4", "max_turns": 20, "verify_spec": T4_SPEC}

GOOD_COMPLETION = [
    {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
    {"role": "assistant", "content": "done"},
]


def _reward_func(monkeypatch, payload):
    monkeypatch.setenv(KEY_VAR, "k")
    monkeypatch.setattr(rf, "fetch_verify", lambda *a, **k: payload)
    rubric = rf.build_rubric(STORE, KEY_VAR)
    return rubric.funcs[0]  # the single weight-1.0 reward func


def test_full_success_excludes_partial(monkeypatch):
    # cart matches spec exactly -> terminal 1.0, partial must NOT be added
    payload = {"cart": [{"sku": "GRO-1", "color": "green", "size": "One Size", "qty": 2}]}
    reward = _reward_func(monkeypatch, payload)
    r = reward(completion=GOOD_COMPLETION, answer="", info=dict(T4_INFO), state={"sid": "s"})
    # 2 assistant turns, max 20 -> eff = 1 - 2/20 = 0.9
    expected = 0.85 * 1.0 + 0.05 * (1 - 2 / 20)
    assert r == pytest.approx(expected)
    assert r < 0.95  # would be ~0.975 if partial were double-counted


def test_partial_added_only_when_terminal_lt_1(monkeypatch):
    # right sku+variant, wrong qty -> terminal 0, partial = 0.4+0.3 = 0.7
    payload = {"cart": [{"sku": "GRO-1", "color": "green", "size": "One Size", "qty": 1}]}
    reward = _reward_func(monkeypatch, payload)
    r = reward(completion=GOOD_COMPLETION, answer="", info=dict(T4_INFO), state={"sid": "s"})
    # terminal=0 -> no efficiency bonus (anti-hack); only partial counts
    expected = 0.10 * 0.7
    assert r == pytest.approx(expected)


def test_zero_tool_call_gate(monkeypatch):
    payload = {"cart": [{"sku": "GRO-1", "color": "green", "size": "One Size", "qty": 2}]}
    reward = _reward_func(monkeypatch, payload)
    no_tools = [{"role": "assistant", "content": "the answer is obviously green"}]
    r = reward(completion=no_tools, answer="", info=dict(T4_INFO), state={"sid": "s"})
    assert r == 0.0


def test_verify_called_at_most_once(monkeypatch):
    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        return {"cart": [{"sku": "GRO-1", "color": "green", "size": "One Size", "qty": 1}]}

    monkeypatch.setenv(KEY_VAR, "k")
    monkeypatch.setattr(rf, "fetch_verify", fake)
    rubric = rf.build_rubric(STORE, KEY_VAR)
    state = {"sid": "s"}
    # run every func (reward + monitors) as the rubric would
    for f in rubric.funcs:
        f(completion=GOOD_COMPLETION, answer="", info=dict(T4_INFO), state=state)
    assert calls["n"] == 1
