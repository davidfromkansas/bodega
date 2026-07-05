"""M1.2 smoke test: run a few live rollouts against the deployed store.

Usage (env vars must be exported, e.g. `set -a; . environment/.env; set +a`):
    python environment/smoke_test.py --n 3 --tier t1 --model gpt-4o-mini

Spends real (tiny) money: Browserbase session + OpenAI tokens per task.
"""

import argparse
import asyncio
import json
import os

from openai import AsyncOpenAI
from verifiers.clients import OpenAIChatCompletionsClient

from bodega_env.bodega_env import load_environment


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--tier", default="t1")
    ap.add_argument("--split", default="eval")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--mode", default="dom")
    args = ap.parse_args()

    for k in ("BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID", "MODEL_API_KEY",
              "OPENAI_API_KEY", "BODEGA_VERIFY_KEY", "BODEGA_STORE_URL"):
        assert os.environ.get(k), f"missing env var {k}"

    print(f"store={os.environ['BODEGA_STORE_URL']}  agent={args.model}  "
          f"mode={args.mode}  tier={args.tier}  n={args.n}")

    env = load_environment(split=args.split, tier=args.tier,
                           num_examples=args.n, mode=args.mode)
    client = OpenAIChatCompletionsClient(
        AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    )

    results = await env.evaluate(
        client=client,
        model=args.model,
        num_examples=args.n,
        rollouts_per_example=1,
        max_concurrent=2,
        state_columns=["sid", "_bodega_verify_payload", "_bodega_scores"],
    )

    outputs = results["outputs"] if isinstance(results, dict) else results
    if not isinstance(outputs, list):
        outputs = [outputs]

    # dump raw structure so we never lose a paid rollout to a print bug
    def _plain(o):
        if isinstance(o, dict):  # RolloutOutput is a dict subclass
            return dict(o)
        if hasattr(o, "model_dump"):
            try:
                return o.model_dump()
            except Exception:
                pass
        if hasattr(o, "__dict__"):
            return dict(vars(o))
        return o

    dump = [_plain(o) for o in outputs]
    with open("/tmp/smoke_out.json", "w") as f:
        json.dump(dump, f, default=str, indent=2)
    print(f"\n(raw dump -> /tmp/smoke_out.json; {len(outputs)} rollouts)")
    if outputs:
        print("rollout[0] fields:",
              list(dump[0].keys()) if isinstance(dump[0], dict) else type(dump[0]))

    def field(o, name, default=None):
        d = _plain(o)
        return d.get(name, default) if isinstance(d, dict) else default

    print("\n=== SMOKE RESULTS ===")
    rewards = []
    for i, o in enumerate(outputs):
        r = field(o, "reward", 0.0) or 0.0
        rewards.append(r)
        print(f"\n--- task {i}: reward={r} ---")
        print(f"  expected answer: {field(o, 'answer')!r}")
        comp = field(o, "completion")
        final = comp[-1] if isinstance(comp, list) and comp else comp
        print(f"  final msg: {str(final)[:500]}")
        # cart/order diagnosis
        info = field(o, "info") or {}
        spec = info.get("verify_spec", {})
        if spec.get("type") in ("cart_exact", "cart_constrained", "order_placed"):
            print(f"  sid: {field(o, 'sid')}")
            print(f"  spec items: {spec.get('items')}")
            payload = field(o, "_bodega_verify_payload")
            if payload is None and field(o, "sid"):
                # fallback: re-fetch by sid (cart persists in the store DB)
                from bodega_env.verify_client import fetch_verify
                try:
                    payload = fetch_verify(os.environ["BODEGA_STORE_URL"],
                                           os.environ["BODEGA_VERIFY_KEY"],
                                           field(o, "sid"))
                except Exception as e:
                    payload = f"<refetch failed: {e}>"
            print(f"  ACTUAL cart: {payload.get('cart') if isinstance(payload, dict) else payload}")
            if isinstance(payload, dict) and payload.get("orders"):
                print(f"  ACTUAL orders: {payload['orders']}")
        m = field(o, "metrics")
        if isinstance(m, dict):
            for mk, mv in m.items():
                print(f"  metric {mk}: {mv}")
    n = len(rewards) or 1
    print(f"\nmean reward: {sum(rewards)/n:.3f}  ({sum(1 for r in rewards if r>0)}/{len(rewards)} > 0)")


if __name__ == "__main__":
    asyncio.run(main())
