"""T4 — Cart build: "add N of X in <color,size> and M of Y". 1-3 line items.
max_turns=10, verify: cart_exact (multiset equality, supersets FAIL).

Rejection: specs must reference in-stock variants with qty <= available."""

from common import in_stock_variants, make_task_id, task_row
from phrasing import ALL_REGISTERS, pick_phrasing


def gen(catalog, rng, n, catalog_seed, task_seed, registers=ALL_REGISTERS):
    products = [p for p in catalog["products"] if in_stock_variants(p)]
    tasks, idx, attempts = [], 0, 0
    while len(tasks) < n and attempts < n * 100:
        attempts += 1
        n_lines = rng.choice([1, 1, 2, 2, 3])  # skew toward small carts
        chosen = rng.sample(products, n_lines)
        items = []
        ok = True
        for p in chosen:
            variants = in_stock_variants(p, min_qty=1)
            color, size, avail = rng.choice(variants)
            qty = rng.randint(1, min(3, avail))
            items.append(
                {"sku": p["sku"], "color": color, "size": size, "qty": qty, "name": p["name"]}
            )
        if not ok:
            continue

        phrases = []
        for it in items:
            var = f"color {it['color']}" + (
                f", size {it['size']}" if it["size"] != "One Size" else ""
            )
            phrases.append(f"{it['qty']} of the {it['name']} ({var})")
        listing = "; then ".join(phrases)
        reg, tpl = pick_phrasing(rng, "t4_cart", registers)
        q = tpl.format(listing=listing)
        # A5/appendix: answer must be "" (not null) for state tiers
        spec_items = [
            {k: it[k] for k in ("sku", "color", "size", "qty")} for it in items
        ]
        difficulty = min(1.0, 0.25 + 0.25 * (n_lines - 1))

        idx += 1
        tasks.append(
            task_row(
                make_task_id("t4", catalog_seed, task_seed, idx),
                q,
                "",
                "t4",
                difficulty,
                {"type": "cart_exact", "items": spec_items, "register": reg},
            )
        )
    return tasks
