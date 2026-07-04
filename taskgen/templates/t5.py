"""T5 — Constrained cart: "build a cart of k distinct <category> products
[each with attr / rating >= r] with subtotal under $B; cheaper is better".
max_turns=14, verify: cart_constrained (gates pass -> 0.6 + 0.4*optimal/actual).

Rejection: infeasible specs; budget must leave headroom above optimal."""

from common import make_task_id, task_row
from phrasing import ALL_REGISTERS, pick_phrasing
from solver import optimal_cart_cost


def gen(catalog, rng, n, catalog_seed, task_seed, registers=ALL_REGISTERS):
    products = catalog["products"]
    categories = sorted({p["category"] for p in products})
    tasks, idx, attempts = [], 0, 0
    seen = set()
    while len(tasks) < n and attempts < n * 200:
        attempts += 1
        category = rng.choice(categories)
        k = rng.choice([2, 2, 3])
        attr = None
        rating_min = rng.choice([None, 3.5, 4.0])
        if rng.random() < 0.4:
            attrs = sorted(
                {a for p in products if p["category"] == category for a in p["attributes"]}
            )
            attr = rng.choice(attrs)
        key = (category, k, attr, rating_min)
        if key in seen:
            continue
        seen.add(key)

        optimal, chosen = optimal_cart_cost(
            products, category=category, k=k, attr=attr, rating_min=rating_min
        )
        if optimal is None:
            continue
        # budget: headroom multiplier; tighter budget = harder
        headroom = rng.choice([1.3, 1.5, 1.8, 2.2])
        budget = round(optimal * headroom)
        if budget <= optimal:
            continue

        cons = [f"{k} different products from the {category} category"]
        if attr:
            cons.append(f"each having the attribute '{attr}'")
        if rating_min is not None:
            cons.append(f"each rated at least {rating_min}")
        cons_txt = ", ".join(cons)
        reg, tpl = pick_phrasing(rng, "t5_constrained", registers)
        q = tpl.format(cons=cons_txt, budget=budget)
        difficulty = min(
            1.0,
            0.35
            + 0.15 * (k - 2)
            + (0.1 if attr else 0.0)
            + (0.1 if rating_min else 0.0)
            + (0.15 if headroom <= 1.5 else 0.0),
        )

        idx += 1
        tasks.append(
            task_row(
                make_task_id("t5", catalog_seed, task_seed, idx),
                q,
                "",
                "t5",
                difficulty,
                {
                    "type": "cart_constrained",
                    "register": reg,
                    "constraints": {
                        "category": category,
                        "k_distinct": k,
                        "attr": attr,
                        "rating_min": rating_min,
                        "qty_each": 1,
                    },
                    "budget": budget,
                    "optimal_cost": optimal,
                },
            )
        )
    return tasks
