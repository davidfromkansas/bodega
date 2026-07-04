# Bodega — a browser-use agentic shopping RL environment

*(working name — rename freely)*

**One-line goal:** Build a rigorous RL environment where AI agents shop on a website we control, use it to benchmark closed + open models, then post-train a small open model (Qwen3-4B) to measurably improve — all for ~$100.

**This document is the execution spec.** Part I is a plain-English overview for the project owner. Parts II–VI are for the coding agent: context, architecture, contracts, and milestone work orders.

---

## ⚑ HANDOFF INSTRUCTIONS — read first (coding agent)

1. **Read this entire document before writing any code.** Then confirm back, in your own words, (a) the milestone structure, (b) what the spend gates are and why, and (c) the DOM-mode + verify-API design. Do not start coding until you've confirmed understanding.
2. **Build strictly in milestone order (M0 → M4), and within M0, strictly in the numbered step order.** Do not start a step until the previous step's tests pass. Do not scaffold everything at once.
3. **Never take an action that costs money without explicit owner approval.** Everything through the end of M0 is free/local (Gate A). Deploying, starting the Browserbase plan, calling paid model APIs, and launching training are gated (Gates B and C) and require a go-ahead.
4. **Stop and show the owner the result after each numbered step** (tests passing, sample output, the artifact produced). The owner is a non-technical beginner — explain what you built in plain terms and what they should check.
5. **When a spec says "or" (e.g. a library choice), it has been resolved** — see the Tech Stack block in Part III. Do not re-decide.
6. **The two design rules that are non-obvious and load-bearing:** (a) infra faults must *raise*, never score 0.0 (D6); (b) train / eval / eval-ood task sets must never overlap (M0 step 4b). Both have explicit tests. Do not skip them.
7. If anything in the spec seems wrong or underspecified, **stop and ask** rather than guessing — especially anything touching rewards, verification, or spend.

---

# PART I — The high-level picture (plain English)

## What we're building, in one paragraph

We're building a fake online store (like a mini Amazon that we own) and a testing harness around it. AI agents visit the store in a real web browser and try to complete shopping tasks we give them: "find the cheapest waterproof jacket under $100," "add 2 blue jackets in size M to the cart," "check out with coupon SAVE10." Because *we* own the store's database, we can check whether the agent **actually did the thing** — is the jacket really in the cart? — instead of trusting the agent's word or asking another AI to guess from a transcript. That checkability is the entire innovation: it's what makes the scores trustworthy and what makes training on this environment produce real skill instead of learned bluffing.

## Why a fake store instead of real Amazon?

Three reasons. (1) **Real sites change constantly** — prices, inventory, layouts — so two attempts at the same task face different worlds, and you can't tell if the agent got better or the website got easier. (2) **Real sites fight bots** — CAPTCHAs, IP bans — and every block looks like the agent failing. (3) **You can't verify or allow real transactions** — no placing actual Amazon orders thousands of times, and no way to check ground truth. Our store is frozen, bot-friendly, and fully inspectable. (Notably, Browserbase — the company whose infrastructure we use — published research showing that on live-site benchmarks, AI judges wrongly marked failures as successes ≥45% of the time. Our design makes that failure mode impossible for state-based tasks.)

## How the training works (30-second RL primer)

The method is **GRPO** (a reinforcement-learning algorithm). For each task, the model tries it **8 times** ("rollouts"). Each attempt gets a **reward** (did the cart end up correct? was the answer right?). GRPO then compares the 8 attempts *against each other*: whatever the higher-scoring attempts did differently gets reinforced; whatever the lower-scoring ones did gets discouraged. Repeat over thousands of tasks and the model's behavior shifts toward what earns reward. Two consequences drive a lot of our design: **the learning signal only exists when attempts disagree** (8 failures teach nothing, 8 successes teach nothing — so tasks must be at the right difficulty for *our specific model*), and **the reward must be honest** (if a broken browser session scores 0, the model gets punished for our infrastructure's mistake — so we exclude those instead).

## The plan in five steps

1. **M0 — Build it locally, spend $0.** Store + task generator + a scripted robot ("oracle") that proves every task is solvable and every checker is correct.
2. **M1 — Put it online, measure everyone.** Deploy the store, run 2 closed models (as reference points) and open models including our untrained 4B. Also measure our own noise: run the same model 5× to learn how much scores wobble, so we never mistake wobble for improvement.
3. **M2 — Fix everything the traces reveal.** Read ~50 failures by hand; fix ambiguous tasks, bugs, and any way to cheat the reward.
4. **M3 — Publish + ask for free compute.** Put the environment on Prime Intellect's public Hub; apply for their credits program and Browserbase builder credits. (If this lands, someone else pays for step 5.)
5. **M4 — Train, re-measure, write it up.** One careful GRPO run on the small model, then the headline chart: frontier models / our 4B before / our 4B after — per task type, including tasks with products it never saw during training.

## What success looks like

A public environment on the Hub that others can use; a credible per-tier benchmark of several models; and a before/after result showing the 4B measurably improved on held-out tasks — with the honest caveats stated (single training run, k=1 frontier numbers are reference lines, 4B on easy tiers is a proof of concept). The story — *"state-verified rewards for browser shopping agents, built and trained for $100"* — is the essay.

## Tiny glossary

| Term | Meaning |
|---|---|
| **Rollout** | One complete attempt at one task by a model (a browsing session from start to answer). |
| **Reward / rubric** | The score for a rollout (0–1) / the set of functions that compute it. |
| **Verifier / verifiable reward** | Scoring by checking objective ground truth (our store's database) rather than opinion. |
| **GRPO** | The RL algorithm: compare a group of rollouts on the same task; reinforce what the better ones did. |
| **DOM mode** | How our agent acts: it issues plain-language commands ("click the Add to cart button") that a helper AI (Stagehand) carries out. This is what we use — cheaper, works with a text model. |
| **CUA mode** | An alternative where the model sees screenshots and clicks exact coordinates itself. More expensive; only a fallback for us. |
| **Trajectory** | The recorded sequence of (what the model saw, what it did) — the raw material training learns from. |
| **Oracle** | Our scripted (non-AI) Playwright bot that solves tasks from ground truth, to prove tasks/checkers work. |
| **verifiers / prime-rl / Browserbase** | Prime Intellect's environment library / their training framework / the cloud-browser provider. |
| **Learnable band** | Tasks a model passes 10–90% of the time — the only tasks GRPO can learn from. |
| **sid** | Our per-rollout session token; isolates each agent's cart from every other concurrent agent. |

---

# PART II — Context & locked decisions (agent: read fully before coding)

## Thesis

Every browser environment on the Prime Intellect Hub is either read-only navigation scored by an LLM judge (WebVoyager, Mind2Web) or a shopping eval without verifiable rewards (ecom-bench). Bodega's differentiator: **rewards come from backend state the agent actually mutated**, checked via a private API against a database we own. This is near-unhackable, enables state-mutating task tiers no live-site env can support, and produces a training signal clean enough to trust.

## Locked decisions (do not revisit during implementation)

| # | Decision | Rationale |
|---|---|---|
| D1 | **DOM mode.** (CUA stays as a documented fallback if M1 shows we need it — see note.) | DOM is cheaper per rollout, uses a simpler text model, and is on Browserbase's officially-supported training path (their RL guide trains a text Qwen3-4B on a DOM env). The one tradeoff: DOM trains the model's *decision-making* (which tools to use, how to search, how to phrase instructions, answer format) but not its *clicking* — Stagehand's helper AI does the clicking and doesn't learn. That tradeoff barely bites us because our storefront is clean and easy to navigate, so a weak model's failures will mostly be decision failures, which DOM fixes. **Fallback note:** if M1 failure traces show the model failing at clicking/grounding despite good decisions (unlikely on our clean site), switch to CUA + Qwen3-VL-4B. Don't plan for this; just know the escape hatch exists. |
| D2 | Training model: **Qwen/Qwen3-4B-Instruct-2507** (text), LoRA. | Matches Browserbase's DOM training guide. Small = cheap GPU; weak baseline = more room to show improvement; easy tasks = short = cheap. |
| D3 | Train on **T1–T3 only**, `max_turns=8`. T4–T6 are **eval-only** in v1. | Short horizons ≈ 1-min rollouts — the biggest lever on GPU wall-clock and browser hours. The frontier-vs-4B gap on T4–T6 is itself a headline finding without training on them. |
| D4 | **Fully deterministic rewards.** No LLM judge anywhere. | Free, reproducible, unhackable. Parser match for T1–T3; verify-API state check for T4–T6. |
| D5 | 1 theme, no obstacle flags (cookie banners, popups, etc.). | v1 scope — keep the store simple. Add variety in v2. |
| D6 | **Infra faults must raise, never score 0.0.** | Confirmed from prime-rl source: raised errors → rollout dropped; for GRPO, one errored rollout drops the **whole group** (advantages would be relative to missing members). But stock BrowserEnv tools swallow browser errors into result strings → fake 0.0 "policy failures" that poison the gradient. `ShopBrowserEnv` must detect infra-fault signatures and raise `vf.Error`. At 8 rollouts/group, 5% infra-fault rate ⇒ ~34% of groups dropped (1−0.95⁸) — the <5% env-fault target is compute-critical. |
| D7 | Spend gates: **$0 until M0 passes locally** (Gate A) → **~$45 for deploy+eval month** (Gate B) → **~$45 GPU only if M1 found a learnable band and M2 hit <5% env-fault** (Gate C). | One-shot budget; every gate is a checkpoint where a bad result stops spend *before* the next expense. |

## Key external facts the implementation depends on

- **verifiers `BrowserEnv`** (`verifiers.envs.integrations.browser_env`, `verifiers[browser]>=0.1.10`): `StatefulToolEnv` subclass; `mode="cua"` deploys a TS action server (prebuilt image `deepdream19/cua-server:latest`) into a Prime sandbox; tools ≈ `click, type_text, keypress, scroll, goto, back, forward, wait, screenshot`; per-rollout session created in `setup_state`, ended by cleanup hook. Fresh Browserbase browser per rollout ⇒ **fresh cookie jar per rollout** (we exploit this for isolation).
- **Dataset convention** (from their examples): HF Dataset with `question`, `answer`, `start_url`, `task_id` columns (+ our `info`).
- **prime-rl error handling:** dispatcher captures rollout *exceptions* as errors; `train_sink.process_group` drops errored rollouts / whole GRPO groups. Swallowed errors are invisible to it (hence D6).
- **Browserbase pricing (verified Jul 2026):** Free = 3 concurrent, 1 browser-hr, 15-min session cap (smoke tests only). Developer = $20/mo, 25 concurrent, 100 browser-hrs included, $0.12/hr overage, 6-hr session cap.
- **Published training recipe reference** (Browserbase × Prime, WebVoyager run): Qwen3-VL-8B, CUA, 200 steps, batch 32, 8 rollouts/example, lr 1e-4, max_tokens 512, oversampling 2. We scale this down.
- **Required env vars:** `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`, `BODEGA_VERIFY_KEY`, `BODEGA_STORE_URL`. Validate at the top of `load_environment()` with `vf.ensure_keys([...])`.

## Budget

| Item | ~Cost | Gate |
|---|---|---|
| Railway hosting | $5 | B |
| Browserbase Developer, 1 month | $20 | B |
| Closed-model evals (2 × ~100 tasks × k=1) | $15–20 | B |
| Open-model evals (k=3 + noise-floor) | ~$5 | B |
| GRPO run, GPU (1 shot + 1 restart) | $40–45 | C |
| Buffer | ~$10 | — |

Free-compute hustle (M3, before Gate C): publish to Hub → apply to Prime's Environments Program → ping Browserbase re: builder credits.

---

# PART III — System specification

## Tech stack (resolved — do not re-decide)

| Component | Choice | Notes |
|---|---|---|
| Storefront framework | **Next.js (App Router)**, server-rendered pages only | No client-side fetching for product content |
| Database | **Postgres** via **Prisma** | (Prisma over Drizzle — pick this) |
| Storefront language | TypeScript | — |
| Local dev | **docker-compose** (app + postgres) | Gate A runs entirely here |
| Deploy | **Railway** (app + Postgres) | Gate B |
| Environment package | **Python**, `verifiers[browser]>=0.1.10`, `httpx` | published to Hub |
| Task generator | **Python** | shares the catalog JSON with storefront |
| Oracle bot | **Python + Playwright** | (Python over TS — shares language with taskgen) |
| Training | prime-rl hosted training, **DOM mode**, **Qwen3-4B-Instruct-2507** (LoRA) | Gate C |

## Secrets & environment variables (single source of truth)

Create `.env.example` in the repo documenting every variable. Never commit real values; never log secret values.

| Variable | Used by | Purpose | Where set |
|---|---|---|---|
| `BODEGA_STORE_URL` | env package, oracle | Base URL of the storefront (localhost in M0, Railway URL in M1+) | local `.env`, Prime env var |
| `BODEGA_VERIFY_KEY` | storefront, env package (rubric), oracle | Bearer token protecting `/api/sessions` + `/api/verify` | generated secret; storefront env + Prime env secret |
| `DATABASE_URL` | storefront | Postgres connection string | docker-compose (local), Railway (prod) |
| `BROWSERBASE_API_KEY` | env package | Browserbase auth | Prime env secret (Gate B) |
| `BROWSERBASE_PROJECT_ID` | env package | Browserbase project | Prime env secret (Gate B) |
| `MODEL_API_KEY` | env package (DOM Stagehand executor) | Key for the model doing Stagehand's grounding calls | Prime env secret (Gate B) |
| *(eval model keys)* | eval runner | Closed/open model API keys for benchmarking | local/Prime, as needed (Gate B) |

`load_environment()` must call `vf.ensure_keys([...])` for the ones it needs and fail loudly if any are missing.

## Repository layout

```
bodega/
├── storefront/                  # Next.js app (the website agents browse)
│   ├── app/                     # routes: /, /search, /c/[category], /p/[slug],
│   │                            #         /cart, /checkout, /orders, /orders/[id]
│   ├── app/api/                 # public: cart & checkout endpoints (cookie-scoped)
│   │                            # private: sessions + verify (bearer-auth)
│   ├── lib/catalog.ts           # deterministic seeded catalog generation
│   ├── lib/session.ts           # sid ↔ cookie binding, cart state
│   ├── prisma/ (or drizzle/)    # Postgres schema + migrations
│   ├── docker-compose.yml       # local: app + postgres
│   └── seed/catalog-seed-A.json # frozen catalog content (see below)
├── environment/                 # the verifiers package (published to Hub)
│   ├── bodega_env/
│   │   ├── bodega_env.py        # load_environment() + ShopBrowserEnv
│   │   ├── rubric.py            # reward functions + monitor metrics
│   │   ├── parser.py            # ANSWER: extraction + normalization
│   │   └── verify_client.py     # httpx client for the verify API
│   ├── pyproject.toml           # deps: verifiers[browser]>=0.1.10, httpx
│   └── README.md                # Hub listing
├── taskgen/                     # task generation (Python, shares no runtime with storefront)
│   ├── generate.py              # CLI: --catalog-seed --task-seed --tier --n --out
│   ├── templates/               # per-tier template modules t1.py … t6.py
│   └── solver.py                # ground-truth computation against catalog JSON
├── oracle/                      # scripted Playwright bot (TS or Python)
│   └── solve.py                 # reads task JSONL, drives browser, asserts via verify API
├── evals/                       # eval configs + analysis notebooks/scripts
│   ├── run_matrix.md            # who/what/k per Part V
│   └── analyze.py               # per-tier tables, CIs, noise floor
└── plan.md                      # this file
```

## 1. Catalog

**Generation:** a one-time script produces `catalog-seed-A.json` (and later `catalog-seed-B.json` with different products): ~800 SKUs across 8–10 categories (apparel, electronics, kitchen, outdoors, grocery, home, toys, office…). Use an LLM once to generate plausible product names/descriptions, then a **seeded PRNG** assigns all numeric/enumerable fields. Human-skim, then **freeze the JSON into the repo** — the catalog is data, not runtime code, so determinism is trivial and taskgen/oracle/storefront all read the same file.

**Product schema:**
```json
{
  "sku": "OUT-0142",
  "slug": "trailhead-rain-jacket",
  "name": "Trailhead Rain Jacket",
  "category": "outdoors",
  "price": 89.99,
  "rating": 4.3,
  "review_count": 127,
  "variants": { "color": ["blue","black","olive"], "size": ["S","M","L","XL"] },
  "stock": { "blue|M": 12, "blue|L": 0, "...": "per-variant int, 0 = out of stock" },
  "attributes": ["waterproof","packable","hooded"],
  "description": "2–3 sentences, human-readable",
  "battery_hours": null
}
```
Category-specific numeric attributes (battery_hours, capacity_liters, wattage…) exist so T3 comparisons have objective answers. **Invariant:** every fact a task can ask about must be visible as rendered text/image on exactly the pages a human would find it on.

**Ground-truth hygiene (hard rules, enforce in code review):**
- No answers in URLs, `data-*` attributes, HTML comments, `<meta>`, or JSON embedded in pages.
- No public JSON API that exposes catalog fields (all product data arrives server-rendered as HTML).
- Prices/ratings/stock rendered only where a shopper would see them.

## 2. Storefront

**Stack:** Next.js (App Router), **server-rendered pages only** (no client-side data fetching for product content), Postgres via Prisma/Drizzle. Docker-compose for local dev; Railway for deploy.

**Pages** (build in this order):
1. `/` — home: category tiles, a few featured products, prominent search box.
2. `/search?q=` — full-text over name+description+attributes; result cards show name, price, rating, thumbnail.
3. `/c/[category]` — grid + filters (price min/max, min rating, attribute checkboxes) + sort (price asc/desc, rating). **Filters are HTML forms (GET)** — no JS-only widgets.
4. `/p/[slug]` — product page: name, price, rating+count, description, attribute list, variant `<select>`s, stock status per selected variant, **Add to cart** button (form POST).
5. `/cart` — line items with variant, qty steppers (form POST), remove, subtotal, coupon `<input>` + apply, **Checkout** button.
6. `/checkout` — shipping form (name, address1, city, state, zip — validated, nothing real), fake payment fieldset (any 16 digits accepted), **Place order**.
7. `/orders` + `/orders/[id]` — confirmation + history for the current sid.

**Visual legibility is a functional requirement** (CUA agents read 800×600 screenshots): ≥16px body text, high-contrast primary buttons, generous hit targets (≥40px), obvious prices, no hover-only information, product images as simple generated placeholder images (colored block + product name text is fine — deterministic, no asset pipeline).

**Semantic HTML also required** (oracle uses selectors; DOM mode may come later): stable `id`/`name` attributes on search box, filter inputs, variant selects, add-to-cart, coupon field, checkout fields, place-order button.

### Session model (per-rollout isolation)

- `POST /api/sessions` *(bearer: BODEGA_VERIFY_KEY)* → `{ "sid": "uuid" }`. Creates a session row (30-min TTL).
- First request hitting any page with `?sid=<uuid>`: server validates sid, sets an httpOnly cookie binding this browser to the sid, **302-redirects to the same URL without the param**. All cart/order state keys off the cookie's sid.
- No sid cookie and no `?sid=` param → storefront still works (mints an anonymous sid) so humans can browse, but env-created rollouts always come in via `?sid=`.
- Concurrency: all mutations scoped by sid; no shared mutable state anywhere except the sessions/carts/orders tables keyed by sid. Nightly purge of expired sids.

### Cart/checkout endpoints (public, cookie-scoped — normal form posts)

`POST /api/cart/add {sku, color, size, qty}` · `POST /api/cart/update {line_id, qty}` · `POST /api/cart/remove {line_id}` · `POST /api/cart/coupon {code}` (rate-limit: 5 attempts/sid) · `POST /api/checkout {shipping fields}` → creates order row, clears cart, redirects to `/orders/[id]`.

**Coupons:** table of `{code, type: percent|flat, value, min_subtotal}`. v1 ships 3 codes; codes appear only in task prompts (never guessable from the site).

### Verification API (private — bearer: BODEGA_VERIFY_KEY; must be unreachable without the key)

```
GET /api/verify/{sid} →
{
  "cart":   [ { "sku": "OUT-0142", "color": "blue", "size": "M", "qty": 2, "unit_price": 89.99 } ],
  "orders": [ { "order_id": "ord_...", "items": [ ...same shape... ], "subtotal": 179.98,
                "coupon": "SAVE10", "discount": 18.00, "total": 161.98,
                "shipping": { "name": "...", "address1": "...", "city": "...", "state": "...", "zip": "..." } } ],
  "coupons_applied": ["SAVE10"]
}
```
Return `404` for unknown/expired sid (the rubric treats that as an infra fault → raise, per D6).

## 3. Task generation (`taskgen/`)

**Contract:** `generate.py --catalog seed/catalog-seed-A.json --task-seed 7 --tier t2 --n 50 --difficulty 0..1 --out tasks.jsonl` — pure function of its inputs; same inputs ⇒ byte-identical output.

**Every task row:**
```json
{
  "task_id": "t2-A7-0031",
  "question": "Find the cheapest waterproof jacket under $100 with a rating of at least 4.0. Reply with the final line exactly as: ANSWER: <name> | <price>",
  "answer": "Trailhead Rain Jacket | 89.99",
  "start_url": "{BODEGA_STORE_URL}",
  "info": { "tier": "t2", "difficulty": 0.55,
            "verify_spec": { "type": "answer_match", "fields": ["name","price"] } }
}
```

**Tiers & verify_spec types:**

| Tier | Task shape | max_turns | verify_spec.type | Ground truth computed by |
|---|---|---|---|---|
| **T1** Lookup | price / stock / attribute of a named product. **Include an easy tail** (product featured on home page — one click away). | 5 | `answer_match` | direct catalog lookup |
| **T2** Search+filter | superlative under constraints ("cheapest X under $Y rated ≥Z") | 8 | `answer_match` | solver filters+sorts catalog; **reject if answer not unique** or if runner-up is within $0.50 (ambiguity margin) |
| **T3** Comparison | "of A, B, C — which has the highest <numeric attr>? name + value" | 8 | `answer_match` | solver compares; reject ties |
| **T4** Cart build | "add N of X in <color,size> and M of Y" (1–3 line items) | 10 | `cart_exact` | items copied from spec; **exact match required — supersets fail** (anti-hack) |
| **T5** Constrained cart | "cart satisfying <constraints> under $B; cheaper is better" | 14 | `cart_constrained` | solver brute-forces `optimal_cost` over catalog |
| **T6** Checkout | "buy <items>, apply <coupon>, ship to <given address>" | 16 | `order_placed` | order must exist with exact items, coupon, shipping fields |

**Difficulty is a continuous per-task knob** (`info.difficulty`), not a tier property: it controls distractor density (near-miss items: $101 when the limit is $100; 3.9★ lookalikes), multi-hop depth, count of line items, and out-of-stock traps. Rationale: frontier models need hard instances to avoid saturating the eval; the 4B needs easy ones to have any GRPO gradient. **The same template must emit instances across the whole range.**

**Rejection rules (generator must enforce):** non-unique answers; answers requiring info not rendered anywhere; T2 margin rule above; T4–T6 specs referencing out-of-stock variants (unless the task is explicitly a stock-trap and the spec accounts for it).

### Train / eval separation (correctness-critical — see M0 step 4b)

If a task the model trained on also appears in eval, a high eval score just means memorization, not skill. This must be structurally impossible, enforced by two layers plus an automated check.

**Splits to generate (once, from a fixed script, then frozen):**
- `train-pool`: ~250 tasks, T1–T3, catalog **seed A**, task **seeds 0–999**, full difficulty spectrum. *(The model learns on these.)*
- `eval`: ~120 tasks, **all six tiers**, catalog **seed A**, task **seeds 1000–1999** (disjoint from train-pool). *(Same store, brand-new tasks — tests "did it learn to shop, or memorize training tasks?")*
- `eval-ood`: ~50 tasks, **catalog seed B** (entirely different products), task seeds 2000+. *(Different store — tests "did it learn a general skill, or memorize store-A facts?" This is the honest capability test.)*

**Guardrails (all three are hard requirements):**
1. **Disjoint seed ranges** (above) so sets can't share generation inputs.
2. **Automated dedup test** (M0 step 4b acceptance criterion): after generating all three sets, assert no `task_id` and no task *content* (normalized `question` string, and for state tiers the `verify_spec`) appears in more than one set. Any overlap = bug, fix before proceeding. Report overlap counts.
3. **`eval-ood` is sacred:** do all environment iteration/hardening (M2) against `train-pool` or a scratch set, never against `eval-ood`. Ideally look at `eval-ood` results only once, at the very end, after all tuning — otherwise you slowly fit the environment to it ("the eval set gets used up," Part V-B).

## 4. Oracle (`oracle/`)

A **scripted** Playwright bot (no LLM). For each task: read `verify_spec`/`answer`, drive the storefront via stable selectors (search → filter → product → variant → cart → checkout as needed), then assert: answer tasks — the answer it derives from the *rendered page* equals `answer`; state tasks — `GET /api/verify/{sid}` matches the spec exactly. Runs against localhost in M0 and against Railway in M1.

**Why it exists:** it proves tasks are solvable and verifiers are correct *before any model or dollar touches the system*. If the oracle can't score ~100%, every model number would measure our bugs. It doubles as a regression suite forever after.

## 5. Environment package (`environment/bodega_env/`)

### `load_environment()`

```python
def load_environment(
    tier: str = "all",              # "t1".."t6" | "all" | comma list
    split: str = "eval",            # "train-pool" | "eval" | "eval-ood"
    band: str | None = None,        # "learnable" → filter by baseline pass-rate file (M4)
    num_examples: int = -1,
    max_turns: int | None = None,   # default: per-tier values above
    mode: str = "dom",              # "dom" (default) | "cua" (fallback per D1)
    store_url: str = os.environ["BODEGA_STORE_URL"],
    proxy_model_to_stagehand: bool = False,   # DOM: whether the eval/train model also does Stagehand grounding
    **kwargs,                       # CUA-only params (viewport_*, keep_recent_screenshots) pass through when mode="cua"
) -> vf.Environment:
    vf.ensure_keys(["BROWSERBASE_API_KEY","BROWSERBASE_PROJECT_ID","BODEGA_VERIFY_KEY"])
    ...
    return ShopBrowserEnv(mode=mode, dataset=ds, rubric=rubric, ...)
```

### `ShopBrowserEnv(BrowserEnv)` — the ~60 lines that matter

```python
class ShopBrowserEnv(BrowserEnv):
    async def setup_state(self, state, **kw):
        state = await super().setup_state(state, **kw)
        # mint per-rollout store session (httpx, bearer BODEGA_VERIFY_KEY)
        state["sid"] = await mint_sid(...)          # raise vf.Error on failure (infra, not policy)
        state["infra_strikes"] = 0
        return state

    def update_tool_args(self, tool_name, tool_args, messages, state, **kw):
        args = super().update_tool_args(tool_name, tool_args, messages, state, **kw)
        if tool_name == "goto" and args.get("url","").startswith(state["store_url"]) \
           and "sid=" not in args["url"] and not state.get("sid_bound"):
            args["url"] = with_query_param(args["url"], "sid", state["sid"])
            state["sid_bound"] = True
        return args
```

**Infra-fault detection (implements D6 — this is not optional):** wrap/inspect tool results; classify as infra-fault: CUA server/session errors, HTTP 5xx or timeouts from the storefront, storefront unreachable, verify API 404 (expired sid). Policy: 1st infra fault → retry the action once; 2nd distinct infra fault in a rollout → `raise vf.Error(type="InfraFault", message=...)`. Never let these become 0.0-reward completions. (prime-rl will drop the rollout — and the whole GRPO group — which is correct.)

### `rubric.py`

Weighted `vf.Rubric`, evaluated in order:
1. **Zero-reward gate:** rollout made no tool calls → 0.0, skip everything (kills "answer from priors without browsing"; pattern from webvoyager-no-anti-bot).
2. **Terminal correctness (weight 0.85):**
   - `answer_match`: parse final assistant message for `ANSWER:` line (see parser); normalize (strip `$`, case, whitespace, trailing zeros: `89.99`≡`$89.99`); exact match on required fields.
   - `cart_exact`: fetch verify API; multiset equality of `(sku,color,size,qty)` — **any extra line item ⇒ fail**.
   - `cart_constrained`: constraint gates all pass AND subtotal ≤ budget → `0.6 + 0.4·clip(optimal_cost/actual_cost, 0, 1)`; else 0.
   - `order_placed`: order exists; items multiset-exact; coupon code matches; each shipping field exact (case-insensitive, whitespace-normalized).
3. **Partial credit (0.10, T4/T6 only, awarded only when terminal < 1):** per spec line item — right sku present 0.4, right variant 0.3, right qty 0.3; average across line items. *Known dynamic to monitor, not prevent:* within-group partial-credit farming is a legitimate early curriculum; the plateau tell is partial mean rising while success rate flatlines.
4. **Efficiency (0.05):** `max(0, 1 − turns_used/max_turns)`.

**Monitor metrics** (verifiers monitor rubrics — logged, never rewarded): malformed-action rate, ANSWER-format compliance, infra-fault count, turns used, tokens/rollout, wall-seconds/rollout. These (a) separate "can't shop" from "can't emit valid actions" — small models fail formats constantly and early training gains are mostly format compliance, which we want visible; (b) continuously quantify the env-fault noise floor.

**System prompt (fixed across all models — any variation is a confound):** brief instructions on the available browser tools (navigate/observe/act/extract in DOM mode) + "When the task asks a question, your final message must end with a line of the form `ANSWER: <...>` exactly."

### Anti-hacking checklist (red-team in M2; each item gets an explicit test)

☐ grep rendered HTML of every page type for prices/answers outside visible text ☐ no public JSON endpoints ☐ verify API rejects requests without bearer key (from the browser's network position) ☐ superset cart fails `cart_exact` ☐ coupon endpoint rate-limited (brute force infeasible) ☐ `ANSWER:` extraction can't be satisfied by echoing the question ☐ agent cannot mint or guess another sid (uuid4).

---

# PART IV — Milestones (executable work orders)

## M0 — Local environment *(Gate A: $0)*

Build order (each step's tests pass before the next):
1. **Catalog:** generation script → `catalog-seed-A.json` (+ seed-B); schema validation; invariant checks (every attribute referenced by templates exists; per-variant stock present).
2. **Storefront core:** docker-compose (app+postgres); pages 1–5 (home→cart); sid model; cookie binding + redirect; concurrency test (two sids, interleaved cart ops, no bleed).
3. **Verify API + checkout:** pages 6–7; coupons; bearer auth; 404-on-expired-sid.
4. **Taskgen:** T1–T3 templates + solver + rejection rules; then T4–T6. Golden-file tests (fixed seeds ⇒ fixed JSONL).
4b. **Generate the three splits + dedup test:** run the generation script once to produce `train-pool`, `eval`, `eval-ood` (disjoint seed ranges per Part III); then run the dedup test asserting zero task overlap (task_id + normalized content) across all three sets. Freeze the outputs. **This is correctness-critical — a leak here silently invalidates every later result.**
5. **Rubric + parser unit tests:** simulated completions/verify-payloads covering every verify_spec type, every normalization edge, superset-cart fail, partial-credit math.
6. **Oracle:** solve all generated tasks against localhost.
7. (Optional, free) One end-to-end smoke test on Browserbase free tier: 2–3 T1 tasks with any cheap model, confirming `ShopBrowserEnv` sid-injection + verify round-trip work against an early Railway deploy (Browserbase's cloud can't reach localhost, so this needs a public URL — do it after M1's deploy if simpler).

**✅ Accept:** oracle ≥98% over ≥300 generated tasks (investigate every failure — each is a real bug); concurrency test green; rubric tests green; golden files stable; **dedup test reports zero overlap across splits.**

**Definition of Done — the literal commands that must succeed** (agent: wire these up so the owner can verify without reading code):
```bash
cd storefront && docker compose up -d          # storefront + postgres come up healthy
pytest storefront/tests                          # sid isolation, verify API, coupons — green
python taskgen/generate.py --catalog seed/catalog-seed-A.json \
        --task-seed 0 --tier all --n 50 --out /tmp/sample.jsonl   # produces 50 valid tasks
python taskgen/make_splits.py                    # writes train-pool / eval / eval-ood, frozen
python taskgen/dedup_check.py                    # prints "overlap: 0" across all splits
pytest environment/tests                         # rubric + parser unit tests — green
python oracle/solve.py --split eval --against localhost   # prints solve rate ≥ 98%
```

## M1 — Deploy + calibration *(Gate B opens: Railway $5, Browserbase $20, eval tokens ~$25)*

1. Deploy storefront to Railway (Postgres + app); oracle re-run against production URL.
2. Package `bodega_env`; `prime env install` locally; smoke test 3 tasks with a cheap model.
3. **Noise-floor experiment:** cheapest capable open text model, 5 identical runs × ~100 eval tasks. Record per-run overall + per-tier; noise floor = max pairwise spread. **All later comparisons must exceed it.**
4. **Baseline matrix** (identical harness everywhere — same system prompt, max_turns, temperature):
   - 2 closed models (one premium, one cheap/fast class), `eval` + `eval-ood`, k=1 → *reference lines*.
   - 2–3 open models incl. **Qwen3-4B-Instruct-2507 (pre-training baseline)**, k=3.
   - Log per-task pass rates for the 4B on `train-pool` (feeds M4 banding).
5. Record minutes/rollout and tokens/rollout per tier (cost model; context-ceiling check — trim tool-result verbosity if tight). Also record the **Stagehand executor token spend per rollout** (the gpt-4o-mini calls that do the actual clicking) — it's a real training line item on a budget.

**✅ Accept:** frontier ≈55–85% on `eval` (headroom both directions); the 4B has a nonzero learnable band on T1–T2 (some tasks it passes sometimes but not always — that's what training needs); noise floor measured; cost/rollout table exists. If frontier saturates (>90%) or the band is empty → fix difficulty distribution before proceeding (regenerate with shifted knobs — this is why difficulty is a continuous knob).

## M2 — Harden

1. Manually read ≥50 failure traces across models/tiers; classify each: policy fault / task ambiguity / markup-visibility fault / verifier bug / infra fault. Fix everything not policy-fault.
2. Execute the anti-hacking checklist as explicit tests.
3. Verify infra-fault→raise path fires correctly (kill the storefront mid-rollout in a test; confirm the rollout errors rather than scoring 0).
4. Re-run oracle + a 1-model spot eval after fixes.

**✅ Accept:** env-fault share of failures <5% on a fresh 50-trace audit; zero known reward hacks; regression suite green.

## M3 — Publish + free-compute hustle *(before Gate C on purpose)*

1. Hub listing: README (thesis, tiers, verify design, load-args, baseline table), eval config, version pin.
2. Cold-start test: fresh account, `prime env install`, run 5 tasks.
3. Apply to Prime Intellect Environments Program; email Browserbase re: builder credits (angle: novel state-verified shopping env built on BrowserEnv + forthcoming writeup).

**✅ Accept:** a stranger can install and run it. Credits = bonus, not dependency.

## M4 — Train + write up *(Gate C: ~$45 GPU; opens only if M1 band exists AND M2 <5%)*

1. **Difficulty banding:** from M1's per-task 4B pass rates, select `train-pool` tasks in the 10–90% band → `band=learnable` filter file. (Expect heavy T1/easy-T2 skew; that's correct.)
2. **Config** (scaled down from Browserbase's DOM training guide):
```toml
model = "Qwen/Qwen3-4B-Instruct-2507"        # text model, LoRA
max_steps = 60
batch_size = 16
rollouts_per_example = 8
learning_rate = 1e-4
oversampling_factor = 2                       # keeps the GPU busy while browsers run
[sampling]
max_tokens = 512
[[env]]
id = "<owner>/bodega"
args = { mode="dom", split="train-pool", band="learnable", tier="t1,t2,t3", max_turns=8 }
```
Budget math: 60×16×8 = 7,680 rollouts × ~1 min ≈ 130 browser-hrs (~$4 past the plan's included 100). GPU: target ≤15–20 hrs ≈ $30–45. Plus the Stagehand executor spend measured in M1 (× 7,680 rollouts — sanity-check this against budget before launching).
3. **Kill criteria:** abort if reward flat after 25 steps, or malformed-action rate not falling (format compliance is the first thing GRPO fixes — visible in monitor metrics), or group-drop rate >15% (infra problem — go fix, don't burn).
4. **Post-training eval:** full `eval` + `eval-ood`, k=3, identical harness.
5. **Writeup:** headline chart (frontier reference lines / 4B baseline / 4B post-trained, per tier); noise floor shown; honest asterisks (k=1 frontier refs; single training seed; 4B on easy tiers = proof of concept). Title direction: *"State-verified rewards for browser shopping agents: eval + post-training for $100."*

**✅ Accept:** held-out `eval` improvement > noise floor; `eval-ood` reported either way (flat-on-ood is an honest, publishable finding); essay drafted.

---

# PART V — Evaluation methodology (rules that make numbers mean something)

1. **Oracle before models.** No model runs until the oracle passes; it re-runs after every env change.
2. **Noise floor before comparisons.** Never report a model difference smaller than the measured run-to-run spread.
3. **k policy:** open models k=3; frontier k=1 labeled *reference lines* (budget honesty, stated in writeup).
4. **Report per-tier and per-difficulty-band; never a single blended number.** Report **success rate** (terminal=1.0) separately from **shaped reward** (training signal only — not comparable across environments).
5. **Identical harness across models.** Same prompt, max_turns, temperature, and mode. Model-specific tweaks are confounds; if a model needs one to function at all, document it loudly.
6. **Frontier models double as env QA:** oracle 100% + frontier 45% ⇒ suspect task ambiguity/harness flakiness first.
7. **The training claim = transfer battery:** held-out task seeds (memorization) → seed-B catalog (product generalization) → [v2: second theme, external benchmark slice]. "Reward went up" is never the claim.

---

# PART V-B — Beginner blindspots & self-checks (for the project owner)

*Plain-language traps that catch first-time RL/eval builders. Revisit this list at each milestone.*

## The 8 blindspots

☐ **1. "The model got better" is easy to fake yourself out on.** A rising score can come from a bug that made tasks easier, from accidentally testing on tasks the model trained on, or from a difference smaller than normal run-to-run wobble. Rule: treat any good result as suspect until the boring explanations are ruled out (check the noise floor, confirm held-out tasks are truly held out, read some traces).

☐ **2. Expect ~80% plumbing, ~20% RL.** The hard part isn't the training algorithm (it's a config file) — it's dead browser sessions, weird storefront errors, secretly-unsolvable tasks, off-by-one reward bugs. These don't crash; they silently produce wrong rewards the model then learns from. Budget patience for infrastructure debugging.

☐ **3. Cost is spiky and can run away silently.** A misconfig (sessions that never close, a retry storm, an infinite loop) can drain the budget in an afternoon with nothing erroring. Do a spend sanity-check *before* the big run and watch the meter *during* it. (Gate C exists for this.)

☐ **4. Reward hacking is real and looks like good news.** RL brute-force-searches for anything that scores. If there's a way to earn points without doing the task, the model finds it — and it shows up as "scores went up!" until you inspect what it actually did. Assume every reward gap will be exploited; verify wins by reading rollouts.

☐ **5. GRPO only learns from right-difficulty tasks.** Tasks the model always fails, or always passes, teach nothing — learning lives only in tasks it passes *sometimes*. A training set that looks nicely varied to you can produce zero learning if it's all too-hard/too-easy for your specific weak model. (This is why M4's difficulty-banding step exists — don't skip it.)

☐ **6. "Read the traces" is the actual core skill.** The aggregate score tells you *that* something's wrong; only reading individual rollouts step-by-step tells you *what*. It's tedious and the transcripts are ugly, which is why beginners avoid it — and why it's the highest-value habit in the project. Build this muscle first.

☐ **7. The environment is a scientific instrument — calibrate before trusting it.** An uncalibrated scale gives confident, precise, wrong numbers. The oracle bot, frontier-model sanity checks, and noise floor are the calibration. Skipping them doesn't get you "no numbers" — it gets you numbers you shouldn't believe.

☐ **8. Scope creep disguised as thoroughness.** "Just one more tier / theme / model" each feels responsible; together they mean you never ship. The v1/v2 split is the defense — ship the small honest thing before the big polished thing.

## Quieter gotchas

☐ **Determinism drift** — if "the same task" isn't byte-identical each run (a stray timestamp, random product ordering), comparisons quietly break. The seed design prevents this; don't let randomness sneak back in.
☐ **Eval sets get "used up"** — once you've tuned everything against your eval tasks, you've implicitly fit to them and they're no longer a clean test. The seed-B (ood) set is the truly-clean check; guard it.
☐ **Weak models fail dumbly, not smartly** — often by malformed output (bad format), not bad shopping. Early "improvement" is frequently just learning to format correctly. Know this so you don't overclaim.
☐ **A negative result is still a result** — "we did it rigorously and the model didn't improve" is honest and publishable. The win is the rigorous attempt, not a guaranteed score bump.

## How to prompt the AI assistant better

☐ **State your level + what you want** — "explain non-technically, just the decision" vs "give full reasoning" produce very different answers. Correct in-flight: *"too dense, simpler"* / *"more depth here."*
☐ **Ask it to check your understanding** — *"Here's X in my own words — what am I getting wrong?"* Catching a misconception beats another explanation.
☐ **Ask "what would go wrong if…"** — *"What breaks if I skip the oracle?"* Surfaces consequences while they're cheap to avoid.
☐ **Ask for the cheap check before the expensive action** — *"Before I start the training run, what should I verify?"* / *"Smallest test that tells me this works?"*
☐ **Ask it to rank, not list** — *"Of everything here, the 3 things most likely to sink this?"* forces prioritization over a flat wall.
☐ **Push back when it feels off** — *"Are you sure?"* / *"Is this actually necessary or are you being cautious?"* gets a straight reassessment. (The DOM-mode correction happened exactly this way.)
☐ **Ask what it's assuming** — *"What are you assuming about my setup that might not be true?"* catches quiet mismatches.

---

# PART VI — Deferred to v2 (with budget/credits)

Second + third storefront themes (layout generalization) · obstacle flags (cookie banner, modals, infinite scroll) · DOM eval track for text-only models · T4–T6 training · CUA-only visual tasks (pick-the-floral-variant) · multi-store price comparison (two deployments, one catalog, different prices) · external transfer eval · 8B run · upstream contribution: trainable DOM mode via verifiers' v1 interception server (mechanism exists; BrowserEnv is legacy-API and Stagehand runs on Browserbase's cloud, so it's real work, not a flag).

---

# APPENDIX — Facts, gotchas, and source-reading results for the coding agent

**Resolved from source (PrimeIntellect-ai/verifiers + prime-rl, cloned Jul 2026):**
- Trainable tokens = `TrajectoryStep.tokens` (prompt_ids/completion_ids/logprobs) created **only** in `MultiTurnEnv.add_model_response()` for responses obtained through the env's own rollout client; prime-rl's `train_sink` builds samples from exactly these (`trace_to_samples`). Stagehand's internal observe/act/extract calls never create trajectory steps. ⇒ **DOM training trains the orchestrator only** (real learning: tool choice, instruction phrasing, strategy, format — officially supported per Browserbase's RL guide, which trains a text Qwen3-4B on a DOM env); the grounding executor receives no gradient. CUA trains the full perception→action loop. Hence the D1 decision gate.
- `train_sink.process_group()`: drops errored rollouts; for group-scored algorithms (GRPO), **any** errored member drops the whole group. Dispatcher marks rollouts errored only on **raised exceptions** (or empty trajectories). Stock BrowserEnv tools `try/except` and return error **strings** → invisible to this machinery. ⇒ D6.
- `BrowserEnv` constructor params worth knowing: `mode`, `viewport_width/height`, `keep_recent_screenshots`, `save_screenshots`, `proxies` (leave False), `advanced_stealth` (leave False — our store wants bots), CUA sandbox params (`use_prebuilt_image=True` default is fine), `stop_errors`.
- Dataset columns convention: `question`, `answer`, `start_url`, `task_id`, plus arbitrary `info`.

**Gotchas:**
- CUA sessions live in a Prime sandbox running the CUA server; first-session startup has latency — don't count it as agent turns; keep `sandbox_timeout_minutes` above expected batch duration.
- Browserbase free tier caps sessions at 15 min — fine for smoke tests, not for T5/T6 debugging.
- Screenshots dominate context: with `keep_recent_screenshots=2`, older screenshots are placeholder-replaced, but tool-result *text* still accumulates — keep storefront responses/redirect chains terse.
- `answer` must be `""` (not null) for state tiers — HF Dataset column typing.
- Never log `BODEGA_VERIFY_KEY`; verify calls happen rubric-side only.
- Railway: enable at least 1 GB RAM for the app; run the oracle against prod immediately after every deploy (it's the smoke test).
- When in doubt between "swallow and continue" vs "raise": tasks may legitimately fail (policy's fault — score it); infrastructure may not (our fault — raise it). The classifier for which is which is D6's fault-signature list; extend it whenever a new failure mode appears in traces.

---

# AMENDMENTS — approved by owner Jul 3, 2026 (binding; supplements the spec above)

| # | Amendment | Where it lands |
|---|---|---|
| A1 | **Pin the Stagehand executor model.** The DOM-mode grounding model is part of the environment. Pin an exact model version in config; record it in every result artifact. An executor model change = environment change (re-run noise floor before comparing across it). | environment package config; evals/analyze.py records it |
| A2 | **Freeze sampling params.** Eval harness fixes temperature/top_p in one config file used by every model run (evals and any k>1 runs use temperature > 0, e.g. 0.7; record exact values). Training sampling recorded separately. | evals/ harness config; M1 step 4 |
| A3 | **Larger T1–T3 eval counts + Wilson CIs.** `eval` split sizes ≥50 tasks each for T1, T2, T3 (claim-bearing tiers); T4–T6 ~20 each is acceptable but reported with Wilson 95% CIs and labeled low-n. `eval-ood` (~50) reported overall only, never per-tier. analyze.py computes Wilson intervals for every reported rate. | M0 step 4b split sizes; evals/analyze.py |
| A4 | **Session robustness:** sid TTL extended to 4 hours (was 30 min) to survive training-queue latency; additionally verify-404 remains an infra fault per D6. All sid-scoped pages send `Cache-Control: no-store` (explicit test). | storefront session model; M0 step 3 tests |
| A5 | **Determinism hardening:** no rendered timestamps on any page agents see (order pages show order id only); all product listings ordered by explicit deterministic sort keys, never DB order; ANSWER parser splits on the *last* ` | ` and product names are rejected at catalog-gen if they contain `|`. | storefront, catalog gen, parser.py |
| A6 | **M2 additions (acceptance items):** (a) load test — 25 concurrent scripted oracle runs against the deployed store, zero 5xx; (b) no-browsing sanity eval — one model run with browser tools disabled must score ≈0, proving answers aren't guessable from priors. | M2 checklist |
| A7 | **Efficiency-reward guard:** monitor mean-turns-used alongside success rate during training; if turns fall while success falls, set efficiency weight to 0. Added to M4 kill criteria. | rubric.py weights config; M4 step 3 |
| A8 | **Writeup limitations section is mandatory:** single training seed, k=3 evals, frontier k=1 reference lines, pass@1 (not pass^k), traces published for audit. | M4 step 5 |
| A9 | **Deploy target: Vercel (Hobby) + Neon Postgres (free) instead of Railway.** Owner decision Jul 4, 2026. Saves ~$5/mo; requires Neon pooled connection string for Prisma. Watch cold-start latency in the M2 load test; fall back to Railway if cold starts inflate the infra-fault rate. | M1 step 1 |
