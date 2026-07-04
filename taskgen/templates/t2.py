"""T2 — Search+filter superlative: "cheapest X under $Y rated >= Z".
max_turns=8, verify: answer_match on name+price (or name+rating).

Rejection rules (spec): non-unique winner; runner-up within $0.50 (price) /
0.2 stars (rating). Difficulty measured from near-miss distractor count."""

from common import (
    ANSWER_SUFFIX_NAME_PRICE,
    ANSWER_SUFFIX_NAME_VALUE,
    fmt_price,
    make_task_id,
    task_row,
)
from phrasing import ALL_REGISTERS, pick_phrasing
from solver import cheapest, highest_rated, near_miss_count

PRICE_MARGIN = 0.50
RATING_MARGIN = 0.2


def _categories(products):
    return sorted({p["category"] for p in products})


def _attrs(products, category):
    s = set()
    for p in products:
        if p["category"] == category:
            s.update(p["attributes"])
    return sorted(s)


def gen(catalog, rng, n, catalog_seed, task_seed, registers=ALL_REGISTERS):
    products = catalog["products"]
    tasks, idx, attempts = [], 0, 0
    seen_specs = set()
    while len(tasks) < n and attempts < n * 200:
        attempts += 1
        category = rng.choice(_categories(products))
        attr = rng.choice([None] + _attrs(products, category))
        # candidate constraint knobs (seeded)
        price_max = rng.choice([None, 25, 50, 75, 100, 150, 200])
        rating_min = rng.choice([None, 3.5, 4.0, 4.5])
        mode = rng.choice(["cheapest", "highest_rated"])
        spec_key = (category, attr, price_max, rating_min, mode)
        if spec_key in seen_specs:
            continue
        seen_specs.add(spec_key)

        kw = dict(category=category, attr=attr, price_max=price_max, rating_min=rating_min)
        if mode == "cheapest":
            winner, runner, m = cheapest(products, **kw)
            if winner is None or len(m) < 2:
                continue
            if runner is not None and runner["price"] - winner["price"] < PRICE_MARGIN:
                continue  # ambiguity margin (spec)
        else:
            winner, runner, m = highest_rated(products, **kw)
            if winner is None or len(m) < 2:
                continue
            if runner is not None and winner["rating"] - runner["rating"] < RATING_MARGIN:
                continue

        # build the question text
        parts = []
        if attr:
            parts.append(attr.replace("-", " "))
        parts.append(f"product in the {category} category")
        desc = " ".join(parts)
        cons = []
        if price_max is not None:
            cons.append(f"priced under ${price_max}")
        if rating_min is not None:
            cons.append(f"with a rating of at least {rating_min}")
        cons_txt = (" " + " and ".join(cons)) if cons else ""

        if mode == "cheapest":
            reg, tpl = pick_phrasing(rng, "t2_cheapest", registers)
            q = f"{tpl.format(desc=desc, cons=cons_txt)} {ANSWER_SUFFIX_NAME_PRICE}"
            ans = f"{winner['name']} | {fmt_price(winner['price'])}"
            fields = ["name", "price"]
        else:
            reg, tpl = pick_phrasing(rng, "t2_highest_rated", registers)
            q = f"{tpl.format(desc=desc, cons=cons_txt)} {ANSWER_SUFFIX_NAME_VALUE.replace('<value>', '<rating>')}"
            ans = f"{winner['name']} | {winner['rating']:.1f}"
            fields = ["name", "value"]

        # measured difficulty: near-miss distractors + constraint count
        nm = near_miss_count(products, category, attr, price_max, rating_min)
        n_cons = sum(x is not None for x in [attr, price_max, rating_min])
        difficulty = min(1.0, 0.2 + 0.15 * n_cons + 0.06 * nm)

        idx += 1
        tasks.append(
            task_row(
                make_task_id("t2", catalog_seed, task_seed, idx),
                q,
                ans,
                "t2",
                difficulty,
                {
                    "type": "answer_match",
                    "fields": fields,
                    "sku": winner["sku"],
                    "register": reg,
                    "constraints": {
                        "category": category,
                        "attr": attr,
                        "price_max": price_max,
                        "rating_min": rating_min,
                        "mode": mode,
                    },
                },
            )
        )
    return tasks
