"""T1 — Lookup: price / rating / numeric attribute / stock status of a named
product. Includes an easy tail: featured products (one click from home).
max_turns=5, verify: answer_match."""

from common import (
    ANSWER_SUFFIX_PRICE,
    ANSWER_SUFFIX_VALUE,
    ANSWER_SUFFIX_YESNO,
    fmt_price,
    fmt_value,
    make_task_id,
    task_row,
)
from phrasing import ALL_REGISTERS, pick_phrasing
from solver import NUMERIC_FIELDS

FIELD_LABEL = {
    "battery_hours": "battery life in hours",
    "capacity_liters": "capacity in liters",
    "wattage": "power in watts",
    "weight_grams": "weight in grams",
    "screen_inches": "screen size in inches",
}


def gen(catalog, rng, n, catalog_seed, task_seed, registers=ALL_REGISTERS):
    products = catalog["products"]
    featured = [p for p in products if p["featured"]]
    tasks, idx, attempts = [], 0, 0
    while len(tasks) < n and attempts < n * 50:
        attempts += 1
        # easy tail: ~25% of tasks target a featured (home page) product
        easy = rng.random() < 0.25
        p = rng.choice(featured if easy else products)
        kind = rng.choice(["price", "rating", "numeric", "stock"])

        extra = {}
        if kind == "price":
            reg, tpl = pick_phrasing(rng, "t1_price", registers)
            q = f"{tpl.format(name=p['name'])} {ANSWER_SUFFIX_PRICE}"
            ans = fmt_price(p["price"])
            fields = ["price"]
            difficulty = 0.1 if easy else 0.3
        elif kind == "rating":
            reg, tpl = pick_phrasing(rng, "t1_rating", registers)
            q = f"{tpl.format(name=p['name'])} {ANSWER_SUFFIX_VALUE}"
            ans = f"{p['rating']:.1f}"
            fields = ["value"]
            difficulty = 0.15 if easy else 0.35
        elif kind == "numeric":
            avail = [f for f in NUMERIC_FIELDS if p.get(f) is not None]
            if not avail:
                continue
            f = rng.choice(sorted(avail))
            reg, tpl = pick_phrasing(rng, "t1_numeric", registers)
            q = f"{tpl.format(name=p['name'], label=FIELD_LABEL[f])} {ANSWER_SUFFIX_VALUE}"
            ans = fmt_value(p[f])
            fields = ["value"]
            difficulty = 0.2 if easy else 0.4
            extra = {"field": f}
        else:  # stock
            variants = sorted(p["stock"].keys())
            key = rng.choice(variants)
            color, size = key.split("|")
            in_stock = p["stock"][key] > 0
            reg, tpl = pick_phrasing(rng, "t1_stock", registers)
            q = f"{tpl.format(name=p['name'], color=color, size=size)} {ANSWER_SUFFIX_YESNO}"
            ans = "yes" if in_stock else "no"
            fields = ["value"]
            difficulty = 0.25 if easy else 0.45
            extra = {"color": color, "size": size}

        idx += 1
        tasks.append(
            task_row(
                make_task_id("t1", catalog_seed, task_seed, idx),
                q,
                ans,
                "t1",
                difficulty,
                {"type": "answer_match", "fields": fields, "sku": p["sku"], "kind": kind,
                 "register": reg, **extra},
            )
        )
    return tasks
