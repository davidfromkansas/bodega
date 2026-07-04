"""T3 — Comparison: "of A, B, C — which has the highest <numeric attr>?".
max_turns=8, verify: answer_match on name+value. Reject ties (spec)."""

from common import ANSWER_SUFFIX_NAME_VALUE, fmt_value, make_task_id, task_row
from phrasing import ALL_REGISTERS, pick_phrasing
from solver import NUMERIC_FIELDS, comparison_winner

FIELD_LABEL = {
    "battery_hours": "battery life",
    "capacity_liters": "capacity",
    "wattage": "power (watts)",
    "weight_grams": "weight",
    "screen_inches": "screen size",
}


def gen(catalog, rng, n, catalog_seed, task_seed, registers=ALL_REGISTERS):
    products = catalog["products"]
    by_field = {
        f: sorted((p for p in products if p.get(f) is not None), key=lambda p: p["sku"])
        for f in NUMERIC_FIELDS
    }
    tasks, idx, attempts = [], 0, 0
    seen = set()
    while len(tasks) < n and attempts < n * 200:
        attempts += 1
        field = rng.choice(sorted(f for f in by_field if len(by_field[f]) >= 3))
        k = rng.choice([2, 3])
        subset = rng.sample(by_field[field], k)
        key = (field, tuple(sorted(p["sku"] for p in subset)))
        if key in seen:
            continue
        seen.add(key)
        mode = rng.choice(["highest", "lowest"])
        winner = comparison_winner(subset, field, mode)
        if winner is None:
            continue  # tie or missing -> reject

        names = [p["name"] for p in sorted(subset, key=lambda p: p["sku"])]
        listing = ", ".join(names[:-1]) + f" and {names[-1]}"
        reg, tpl = pick_phrasing(rng, "t3_compare", registers)
        q = f"{tpl.format(listing=listing, mode=mode, label=FIELD_LABEL[field])} {ANSWER_SUFFIX_NAME_VALUE}"
        ans = f"{winner['name']} | {fmt_value(winner[field])}"
        difficulty = min(1.0, 0.3 + 0.2 * (k - 2) + (0.1 if mode == "lowest" else 0.0))

        idx += 1
        tasks.append(
            task_row(
                make_task_id("t3", catalog_seed, task_seed, idx),
                q,
                ans,
                "t3",
                difficulty,
                {
                    "type": "answer_match",
                    "fields": ["name", "value"],
                    "sku": winner["sku"],
                    "register": reg,
                    "field": field,
                    "mode": mode,
                    "candidates": sorted(p["sku"] for p in subset),
                },
            )
        )
    return tasks
