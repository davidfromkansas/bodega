"""Shared helpers for task generation. Pure functions of their inputs."""

import json
from pathlib import Path


def load_catalog(path: str) -> dict:
    with open(path) as f:
        cat = json.load(f)
    # canonical order (A5): by sku, so all downstream iteration is deterministic
    cat["products"] = sorted(cat["products"], key=lambda p: p["sku"])
    return cat


def fmt_price(x: float) -> str:
    return f"{x:.2f}"


def fmt_value(x) -> str:
    """Format a numeric attribute exactly as the storefront renders it."""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def in_stock_variants(p: dict, min_qty: int = 1):
    """Sorted list of (color, size, qty) with at least min_qty in stock."""
    out = []
    for key, qty in sorted(p["stock"].items()):
        if qty >= min_qty:
            color, size = key.split("|")
            out.append((color, size, qty))
    return out


def out_of_stock_variants(p: dict):
    out = []
    for key, qty in sorted(p["stock"].items()):
        if qty == 0:
            color, size = key.split("|")
            out.append((color, size))
    return out


def make_task_id(tier: str, catalog_seed: str, task_seed: int, idx: int) -> str:
    return f"{tier}-{catalog_seed}{task_seed}-{idx:04d}"


def task_row(task_id, question, answer, tier, difficulty, verify_spec):
    """Canonical task row. `answer` must be "" (never None) for state tiers."""
    return {
        "task_id": task_id,
        "question": question,
        "answer": answer,
        "start_url": "{BODEGA_STORE_URL}",
        "info": {
            "tier": tier,
            "difficulty": round(difficulty, 2),
            "verify_spec": verify_spec,
        },
    }


# Coupons must mirror storefront/prisma/seed.mjs exactly.
COUPONS = [
    {"code": "SAVE10", "type": "percent", "value": 10, "min_subtotal": 0},
    {"code": "FLAT15", "type": "flat", "value": 15, "min_subtotal": 50},
    {"code": "BODEGA20", "type": "percent", "value": 20, "min_subtotal": 100},
]

# Seeded shipping-address banks (fake, storefront accepts anything valid-shaped).
SHIP_NAMES = [
    "Ada Lovelace", "Grace Hopper", "Alan Turing", "Edsger Dijkstra",
    "Katherine Johnson", "Claude Shannon", "Barbara Liskov", "Donald Knuth",
]
SHIP_STREETS = [
    "12 Analytical Way", "44 Compiler Court", "7 Lambda Lane", "301 Turing Trail",
    "88 Vector Avenue", "5 Tensor Terrace", "210 Gradient Grove", "63 Kernel Klose",
]
SHIP_CITIES = [
    ("Springfield", "IL", "62701"), ("Riverton", "NY", "10001"),
    ("Lakewood", "CO", "80226"), ("Fairview", "TX", "75069"),
    ("Georgetown", "SC", "29440"), ("Ashland", "OR", "97520"),
]

ANSWER_SUFFIX_PRICE = "Reply with the final line exactly as: ANSWER: <price>  (numbers only, e.g. ANSWER: 89.99)"
ANSWER_SUFFIX_NAME_PRICE = "Reply with the final line exactly as: ANSWER: <product name> | <price>  (e.g. ANSWER: Trailhead Rain Jacket | 89.99)"
ANSWER_SUFFIX_NAME_VALUE = "Reply with the final line exactly as: ANSWER: <product name> | <value>  (number only for the value)"
ANSWER_SUFFIX_YESNO = "Reply with the final line exactly as: ANSWER: yes  or  ANSWER: no"
ANSWER_SUFFIX_VALUE = "Reply with the final line exactly as: ANSWER: <value>  (number only)"
