# Bodega — state-verified rewards for browser shopping agents

Bodega is a browser-use RL environment where agents shop on a store **we own**, so
rewards come from **backend state the agent actually mutated** — checked via a
private API against our database — not from an LLM judge reading a transcript.
This makes rewards near-unhackable for state-mutating tasks and produces a clean
training signal.

## Why state verification

Every shopping/browser env on the Hub is either read-only navigation scored by an
LLM judge or a shopping eval without verifiable rewards. Bodega's differentiator:
for cart/checkout tasks, the reward is computed from the store's own database
(`GET /api/verify/{sid}`, bearer-authed), so "did the agent really add 2 blue
jackets?" is answered by ground truth, not opinion.

## Task tiers

| Tier | Task | max_turns | Reward |
|---|---|---|---|
| T1 | Lookup (price / rating / spec / stock) | 5 | answer match |
| T2 | Search + filter superlative | 8 | answer match |
| T3 | Numeric comparison | 8 | answer match |
| T4 | Cart build (exact multiset; supersets fail) | 10 | verify state |
| T5 | Constrained cart (cheaper scores higher) | 14 | verify state (shaped) |
| T6 | Checkout (items + coupon + shipping exact) | 16 | verify state |

Tasks are procedurally generated with machine-checked rejection rules (unique
answers, ambiguity margins, in-stock variants) and split into disjoint sets with
an automated dedup check.

**Split policy (public dev / private held-out, Zapier-style):**

| Split | Shipped in package? | Purpose |
|---|---|---|
| `train-pool` | yes (public) | training pool |
| `eval` | yes (public) | public dev/eval set |
| `test` | no (repo only) | held-out, same distribution — official/uncontaminated numbers |
| `eval-ood` | no (repo only) | held-out, different catalog — OOD generalization |

Only the public splits are bundled into the published environment, so the
held-out sets can never leak through the Hub. Official scores are measured
locally against `test` / `eval-ood`.

## Usage

```python
import verifiers as vf
env = vf.load_environment(
    "bodega",
    tier="t1,t2,t3",      # "t1".."t6" | "all" | comma list
    split="eval",          # public: "train-pool" | "eval"  (held-out, repo only: "test" | "eval-ood")
    mode="dom",            # "dom" (default, text model) | "cua" (vision fallback)
    num_examples=-1,
)
```

### Required environment variables

| Variable | Used for |
|---|---|
| `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` | browser provider |
| `MODEL_API_KEY` | Stagehand DOM executor (pinned `openai/gpt-4o-mini`) |
| `BODEGA_VERIFY_KEY` | bearer for the store's session + verify API |
| `BODEGA_STORE_URL` | store base URL |

## Design guarantees

- **Infra faults raise, never score 0.0** (D6): dead sessions / 5xx / expired-sid
  404 raise `vf.Error` so prime-rl drops the rollout instead of poisoning the
  gradient with a fake policy failure.
- **Deterministic rewards** — no LLM judge anywhere.
- **Pinned Stagehand executor** (`openai/gpt-4o-mini`) — recorded per run; an
  executor change is treated as an environment change.
- **Anti-hacking**: superset carts fail, multiple orders fail, zero-tool-call
  rollouts score 0, answers can't be satisfied by echoing the prompt.

## License / provenance

Storefront catalog is fully synthetic (seeded generation) — no scraped data.
