"""Ground-truth computation against the catalog JSON.

Used by task templates (to compute answers + enforce rejection rules) and by
the oracle (to independently re-derive answers). Pure functions only.
"""

NUMERIC_FIELDS = [
    "battery_hours", "capacity_liters", "wattage", "weight_grams", "screen_inches",
]


def matches(p, category=None, attr=None, price_max=None, price_min=None, rating_min=None):
    if category is not None and p["category"] != category:
        return False
    if attr is not None and attr not in p["attributes"]:
        return False
    if price_max is not None and p["price"] > price_max:
        return False
    if price_min is not None and p["price"] < price_min:
        return False
    if rating_min is not None and p["rating"] < rating_min:
        return False
    return True


def filter_products(products, **constraints):
    return [p for p in products if matches(p, **constraints)]


def cheapest(products, **constraints):
    """(winner, runner_up_or_None, all_matches) by price, sku tiebreak."""
    m = sorted(filter_products(products, **constraints), key=lambda p: (p["price"], p["sku"]))
    if not m:
        return None, None, []
    return m[0], (m[1] if len(m) > 1 else None), m


def highest_rated(products, **constraints):
    m = sorted(filter_products(products, **constraints), key=lambda p: (-p["rating"], p["sku"]))
    if not m:
        return None, None, []
    return m[0], (m[1] if len(m) > 1 else None), m


def near_miss_count(products, category, attr, price_max, rating_min):
    """Distractors: products that fail exactly one constraint by a small margin.
    Used as the measured difficulty signal for T2."""
    n = 0
    for p in products:
        if p["category"] != category:
            continue
        ok_attr = attr is None or attr in p["attributes"]
        ok_price = price_max is None or p["price"] <= price_max
        ok_rating = rating_min is None or p["rating"] >= rating_min
        fails = [not ok_attr, not ok_price, not ok_rating]
        if sum(fails) != 1:
            continue
        if not ok_price and price_max is not None and p["price"] <= price_max * 1.15:
            n += 1
        elif not ok_rating and rating_min is not None and p["rating"] >= rating_min - 0.3:
            n += 1
    return n


def comparison_winner(products_subset, field, mode="highest"):
    """Winner of a numeric-attribute comparison, or None on any tie/missing value."""
    vals = []
    for p in products_subset:
        v = p.get(field)
        if v is None:
            return None
        vals.append((v, p))
    vals.sort(key=lambda t: (-t[0] if mode == "highest" else t[0], t[1]["sku"]))
    if len(vals) >= 2 and vals[0][0] == vals[1][0]:
        return None  # tie -> reject
    return vals[0][1]


def optimal_cart_cost(products, category, k, attr=None, rating_min=None):
    """Min cost of k DISTINCT in-stock products meeting the constraints (qty 1 each).
    Returns (cost, chosen_products) or (None, []) if infeasible."""
    pool = [
        p
        for p in filter_products(products, category=category, attr=attr, rating_min=rating_min)
        if any(q > 0 for q in p["stock"].values())
    ]
    pool.sort(key=lambda p: (p["price"], p["sku"]))
    if len(pool) < k:
        return None, []
    chosen = pool[:k]
    cost = round(sum(p["price"] for p in chosen), 2)
    return cost, chosen


def order_totals(items, coupon):
    """items: [{unit_price, qty}]; coupon: dict from COUPONS or None.
    Mirrors storefront computeTotals exactly."""
    subtotal = round(sum(it["unit_price"] * it["qty"] for it in items), 2)
    discount = 0.0
    if coupon and subtotal >= coupon["min_subtotal"]:
        if coupon["type"] == "percent":
            discount = round(subtotal * coupon["value"] / 100, 2)
        else:
            discount = min(coupon["value"], subtotal)
    total = round(subtotal - discount, 2)
    return subtotal, discount, total
