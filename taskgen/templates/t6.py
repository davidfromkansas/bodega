"""T6 — Checkout: "buy <items>, apply <coupon>, ship to <given address>".
max_turns=16, verify: order_placed (items multiset-exact, coupon code,
shipping fields exact).

Rejection: out-of-stock variants; coupon must be effective (subtotal >= min)
when a coupon is specified."""

from common import (
    COUPONS,
    SHIP_CITIES,
    SHIP_NAMES,
    SHIP_STREETS,
    in_stock_variants,
    make_task_id,
    task_row,
)
from phrasing import ALL_REGISTERS, pick_phrasing
from solver import order_totals


def gen(catalog, rng, n, catalog_seed, task_seed, registers=ALL_REGISTERS):
    products = [p for p in catalog["products"] if in_stock_variants(p)]
    tasks, idx, attempts = [], 0, 0
    while len(tasks) < n and attempts < n * 200:
        attempts += 1
        n_lines = rng.choice([1, 1, 2])
        chosen = rng.sample(products, n_lines)
        items = []
        for p in chosen:
            color, size, avail = rng.choice(in_stock_variants(p))
            qty = rng.randint(1, min(2, avail))
            items.append(
                {
                    "sku": p["sku"],
                    "color": color,
                    "size": size,
                    "qty": qty,
                    "unit_price": p["price"],
                    "name": p["name"],
                }
            )

        use_coupon = rng.random() < 0.6
        coupon = None
        if use_coupon:
            subtotal, _, _ = order_totals(items, None)
            eligible = [c for c in COUPONS if subtotal >= c["min_subtotal"]]
            if not eligible:
                continue  # reject: coupon requested but none effective
            coupon = rng.choice(sorted(eligible, key=lambda c: c["code"]))

        name = rng.choice(SHIP_NAMES)
        street = rng.choice(SHIP_STREETS)
        city, state, zip_ = rng.choice(SHIP_CITIES)

        phrases = []
        for it in items:
            var = f"color {it['color']}" + (
                f", size {it['size']}" if it["size"] != "One Size" else ""
            )
            phrases.append(f"{it['qty']} of the {it['name']} ({var})")
        listing = "; ".join(phrases)
        coupon_txt = (
            f" Apply the coupon code {coupon['code']} at the cart before checking out."
            if coupon
            else ""
        )
        address = f"{name}, {street}, {city}, {state} {zip_}"
        reg, tpl = pick_phrasing(rng, "t6_checkout", registers)
        q = tpl.format(listing=listing, coupon=coupon_txt, address=address)

        spec_items = [
            {k: it[k] for k in ("sku", "color", "size", "qty")} for it in items
        ]
        difficulty = min(
            1.0, 0.4 + 0.2 * (n_lines - 1) + (0.15 if coupon else 0.0)
        )

        idx += 1
        tasks.append(
            task_row(
                make_task_id("t6", catalog_seed, task_seed, idx),
                q,
                "",
                "t6",
                difficulty,
                {
                    "type": "order_placed",
                    "register": reg,
                    "items": spec_items,
                    "coupon": coupon["code"] if coupon else None,
                    "shipping": {
                        "name": name,
                        "address1": street,
                        "city": city,
                        "state": state,
                        "zip": zip_,
                    },
                },
            )
        )
    return tasks
