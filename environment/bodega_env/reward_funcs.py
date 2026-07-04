"""Builds the vf.Rubric that wires the pure scorers in rubric.py to verifiers.

Reward (weighted, in order):
  zero-gate (no tool calls -> 0) · terminal 0.85 · partial 0.10 (T4/T6) · eff 0.05
Monitor metrics (logged, never rewarded): infra faults, ANSWER-format
compliance, turns used.

Verify-API failures raise vf.Error (InfraFault) so the rollout is dropped, never
scored 0.0 (D6).
"""

import json
from pathlib import Path

import verifiers as vf

from . import rubric as R
from .verify_client import InfraFault, fetch_verify

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "storefront" / "seed"


def _load_catalog_by_sku():
    out = {}
    for label in ("A", "B"):
        p = SEED_DIR / f"catalog-seed-{label}.json"
        if p.exists():
            with open(p) as f:
                for prod in json.load(f)["products"]:
                    out[prod["sku"]] = prod
    return out


CATALOG_BY_SKU = _load_catalog_by_sku()


def _final_text(completion) -> str:
    """Text of the last assistant message."""
    if isinstance(completion, str):
        return completion
    for msg in reversed(completion):
        if msg.get("role") == "assistant" and msg.get("content"):
            c = msg["content"]
            return c if isinstance(c, str) else " ".join(
                p.get("text", "") for p in c if isinstance(p, dict)
            )
    return ""


def _made_tool_calls(completion) -> bool:
    if isinstance(completion, str):
        return False
    return any(
        msg.get("role") == "assistant" and msg.get("tool_calls")
        for msg in completion
    )


def _turns_used(completion) -> int:
    if isinstance(completion, str):
        return 0
    return sum(1 for m in completion if m.get("role") == "assistant")


def build_rubric(store_url: str, verify_key_var: str) -> vf.Rubric:
    import os

    def _verify(state):
        try:
            return fetch_verify(store_url, os.environ[verify_key_var], state["sid"])
        except InfraFault as e:
            raise vf.Error(f"InfraFault: {e}") from e

    def terminal_reward(completion, answer, info, state, **kwargs) -> float:
        if not _made_tool_calls(completion):
            return 0.0
        spec = info["verify_spec"]
        typ = spec["type"]
        if typ == "answer_match":
            return R.score_answer_match(_final_text(completion), answer, spec["fields"])
        payload = _verify(state)
        if typ == "cart_exact":
            return R.score_cart_exact(payload, spec["items"])
        if typ == "cart_constrained":
            return R.score_cart_constrained(payload, spec, CATALOG_BY_SKU)
        if typ == "order_placed":
            return R.score_order_placed(payload, spec)
        raise ValueError(f"unknown verify type {typ}")

    def partial_reward(completion, info, state, **kwargs) -> float:
        tier = info["tier"]
        if tier not in ("t4", "t6") or not _made_tool_calls(completion):
            return 0.0
        spec = info["verify_spec"]
        payload = _verify(state)
        items = payload["cart"] if tier == "t4" else (
            payload["orders"][0]["items"] if payload["orders"] else []
        )
        return R.partial_credit(items, spec["items"])

    def efficiency_reward(completion, info, **kwargs) -> float:
        if not _made_tool_calls(completion):
            return 0.0
        return R.efficiency(_turns_used(completion), info.get("max_turns", 8))

    # --- monitor metrics (weight 0.0: logged, never rewarded) ---
    def m_made_tool_calls(completion, **kwargs) -> float:
        return 1.0 if _made_tool_calls(completion) else 0.0

    def m_answer_format(completion, info, **kwargs) -> float:
        if info["verify_spec"]["type"] != "answer_match":
            return 1.0
        from .parser import extract_answer
        return 1.0 if extract_answer(_final_text(completion)) is not None else 0.0

    def m_turns(completion, **kwargs) -> float:
        return float(_turns_used(completion))

    rubric = vf.Rubric(
        funcs=[terminal_reward, partial_reward, efficiency_reward,
               m_made_tool_calls, m_answer_format, m_turns],
        weights=[R.WEIGHTS["terminal"], R.WEIGHTS["partial"], R.WEIGHTS["efficiency"],
                 0.0, 0.0, 0.0],
    )
    return rubric
