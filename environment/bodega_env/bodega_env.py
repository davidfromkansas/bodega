"""Bodega environment package: load_environment() + ShopBrowserEnv.

Wraps verifiers' BrowserEnv (StatefulToolEnv) with:
- per-rollout store session (sid) minted in setup_state (raise on failure = infra)
- sid injection into the first store navigation (DOM: `navigate`; CUA: `goto`)
- infra-fault detection -> raise vf.Error so prime-rl drops the rollout (D6),
  never a fake 0.0
- deterministic rubric (parser match for T1-T3, verify-API state check for T4-T6)

Secrets come from process env (never load_environment args), validated up front.
"""

import json
import os
from pathlib import Path

import verifiers as vf
from datasets import Dataset
from verifiers.envs.integrations.browser_env import BrowserEnv

from . import reward_funcs
from .verify_client import InfraFault, mint_sid

# Prefer data bundled inside the package (so the env is self-contained on the
# Prime Hub); fall back to the repo layout for local dev before a copy/build.
_PKG_SPLITS = Path(__file__).resolve().parent / "data" / "splits"
_REPO_SPLITS = Path(__file__).resolve().parent.parent.parent / "taskgen" / "splits"
SPLIT_DIR = _PKG_SPLITS if _PKG_SPLITS.exists() else _REPO_SPLITS

# Stagehand executor is PINNED (amendment A1): it is part of the environment.
# Recorded in every result artifact; a change = environment change.
STAGEHAND_MODEL = "openai/gpt-4o-mini"

# Per-tier turn budgets. DOM mode spends turns on navigate/observe/act before it
# can answer, so budgets are generous; the efficiency reward still pushes toward
# fewer turns. Single source of truth: also used as the efficiency denominator.
TIER_TURNS = {"t1": 12, "t2": 16, "t3": 16, "t4": 20, "t5": 26, "t6": 30}

def _system_prompt(store_url: str) -> str:
    return (
        "You are a shopping assistant operating a web browser to complete tasks on "
        f"the Bodega online store, located ONLY at: {store_url}\n\n"
        f"ALWAYS begin by navigating to {store_url} . Do NOT visit any other website "
        "(no amazon.com, nordstrom.com, google.com, etc.) — the ONLY valid site is "
        f"{store_url} and its sub-pages. The product you need exists on this store; "
        "if you don't see it, use the store's own search box and pagination.\n\n"
        "Use the browser tools to navigate, observe the page, act (click, type, "
        "select), and extract information.\n"
        "When a task asks a question, once you have the answer STOP calling tools and "
        "send a FINAL message whose last line is exactly:\nANSWER: <your answer>\n"
        "Follow the exact answer format requested in the task. For tasks that ask you "
        "to modify a cart or place an order, complete the actions on the site; you do "
        "not need to output an ANSWER line for those."
    )

INFRA_SIGNATURES = (
    "timeout", "timed out", "econnrefused", "connection refused",
    "502 bad gateway", "503 service", "504 gateway", "http 5",
    "session expired", "browser closed", "target closed", "net::err",
    "stagehand", "navigation failed",
)


def _load_split(split: str, store_url: str, tier: str, num_examples: int) -> Dataset:
    path = SPLIT_DIR / f"{split}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"unknown split '{split}' ({path})")
    tiers = None if tier == "all" else set(tier.split(","))
    rows = []
    with open(path) as f:
        for line in f:
            t = json.loads(line)
            if tiers and t["info"]["tier"] not in tiers:
                continue
            # refresh stale taskgen max_turns with the env's current tier budget
            # (this is the efficiency-reward denominator)
            t["info"]["max_turns"] = TIER_TURNS[t["info"]["tier"]]
            rows.append(
                {
                    "question": t["question"],
                    "answer": t["answer"],
                    "start_url": t["start_url"].replace("{BODEGA_STORE_URL}", store_url),
                    "task_id": t["task_id"],
                    "info": t["info"],
                }
            )
    if num_examples and num_examples > 0:
        rows = rows[:num_examples]
    if not rows:
        raise ValueError(f"no tasks for split={split} tier={tier}")
    return Dataset.from_list(rows)


def _with_sid(url: str, sid: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}sid={sid}"


class ShopBrowserEnv(BrowserEnv):
    def __init__(self, store_url: str, verify_key_var: str, mode: str = "dom", **kwargs):
        super().__init__(mode=mode, **kwargs)
        self._store_url = store_url.rstrip("/")
        self._verify_key_var = verify_key_var
        self._nav_tool = "navigate" if mode == "dom" else "goto"

    async def setup_state(self, state, **kwargs):
        # BrowserEnv.setup_state mutates `state` in place and returns None.
        await super().setup_state(state, **kwargs)
        verify_key = os.environ[self._verify_key_var]
        try:
            state["sid"] = mint_sid(self._store_url, verify_key)
        except InfraFault as e:
            # infra, not policy — raise so prime-rl drops the rollout (D6)
            raise vf.Error(f"InfraFault: {e}") from e
        state["store_url"] = self._store_url
        state["sid_bound"] = False
        state["infra_strikes"] = 0
        return state

    def update_tool_args(self, tool_name, tool_args, messages, state, **kwargs):
        args = super().update_tool_args(tool_name, tool_args, messages, state, **kwargs)
        if tool_name == self._nav_tool and not state.get("sid_bound"):
            url = args.get("url", "")
            if url.startswith(state["store_url"]) and "sid=" not in url:
                args["url"] = _with_sid(url, state["sid"])
                state["sid_bound"] = True
        return args


def load_environment(
    tier: str = "all",
    split: str = "eval",
    num_examples: int = -1,
    max_turns: int | None = None,
    mode: str = "dom",
    store_url: str | None = None,
    proxy_model_to_stagehand: bool = False,
    verify_key_var: str = "BODEGA_VERIFY_KEY",
    **kwargs,
) -> vf.Environment:
    vf.ensure_keys(["BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID", verify_key_var])
    store_url = (store_url or os.environ["BODEGA_STORE_URL"]).rstrip("/")

    dataset = _load_split(split, store_url, tier, num_examples)

    # env-wide max_turns = max of present tiers (per-tier budget lives in info)
    if max_turns is None:
        tiers_present = {r["tier"] for r in dataset["info"]}
        max_turns = max(TIER_TURNS[t] for t in tiers_present)

    rubric = reward_funcs.build_rubric(store_url, verify_key_var)

    env_kwargs = dict(
        mode=mode,
        dataset=dataset,
        rubric=rubric,
        max_turns=max_turns,
        system_prompt=_system_prompt(store_url),
        store_url=store_url,
        verify_key_var=verify_key_var,
        # BrowserEnv does not auto-read BROWSERBASE_PROJECT_ID; pass it explicitly.
        project_id=os.environ["BROWSERBASE_PROJECT_ID"],
    )
    if mode == "dom":
        env_kwargs["stagehand_model"] = STAGEHAND_MODEL
        env_kwargs["proxy_model_to_stagehand"] = proxy_model_to_stagehand
    env_kwargs.update(kwargs)
    return ShopBrowserEnv(**env_kwargs)
