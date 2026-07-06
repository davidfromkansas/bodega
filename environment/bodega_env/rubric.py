"""Reward computation core (spec Part III §5) — pure functions, no I/O.

Weighted composition, evaluated in order:
1. zero-reward gate: no tool calls -> 0.0 (kills answer-from-priors)
2. terminal correctness (0.85): answer_match / cart_exact / cart_constrained /
   order_placed
3. partial credit (0.10, T4/T6 only, only when terminal < 1)
4. efficiency (0.05): max(0, 1 - turns_used/max_turns)
   (A7: efficiency weight is a config knob; zero it if turns fall while
   success falls during training)

The vf.Rubric wiring (M1) calls these with the verify-API payload; verify-API
failures never reach scoring — they raise as infra faults upstream (D6).
"""

from .parser import answers_equal, extract_answer

WEIGHTS = {"terminal": 0.85, "partial": 0.10, "efficiency": 0.05}


# ------------------------------------------------------------- terminal

def score_answer_match(final_text: str, expected_answer: str, fields) -> float:
    got = extract_answer(final_text)
    return 1.0 if answers_equal(got, expected_answer, fields) else 0.0


def _cart_multiset(items):
    """[(sku,color,size,qty)] as a sorted tuple list (multiset identity)."""
    return sorted((i["sku"], i["color"], i["size"], i["qty"]) for i in items)


def score_cart_exact(verify_payload: dict, spec_items: list) -> float:
    """Multiset equality of (sku,color,size,qty). ANY extra line item fails
    (anti-hack: supersets score 0)."""
    return 1.0 if _cart_multiset(verify_payload["cart"]) == _cart_multiset(spec_items) else 0.0


def _product_matches(p, constraints) -> bool:
    if constraints.get("category") and p["category"] != constraints["category"]:
        return False
    if constraints.get("attr") and constraints["attr"] not in p["attributes"]:
        return False
    if constraints.get("rating_min") is not None and p["rating"] < constraints["rating_min"]:
        return False
    return True


def score_cart_constrained(verify_payload: dict, spec: dict, catalog_by_sku: dict) -> float:
    """All constraint gates pass AND subtotal <= budget
    -> 0.6 + 0.4 * clip(optimal_cost / actual_cost, 0, 1); else 0."""
    cart = verify_payload["cart"]
    cons = spec["constraints"]
    k = cons["k_distinct"]

    skus = [i["sku"] for i in cart]
    if len(cart) != k or len(set(skus)) != k:
        return 0.0
    if any(i["qty"] != cons.get("qty_each", 1) for i in cart):
        return 0.0
    for i in cart:
        p = catalog_by_sku.get(i["sku"])
        if p is None or not _product_matches(p, cons):
            return 0.0
    actual = round(sum(i["unit_price"] * i["qty"] for i in cart), 2)
    if actual > spec["budget"]:
        return 0.0
    if actual <= 0:
        return 0.0
    ratio = spec["optimal_cost"] / actual
    return 0.6 + 0.4 * max(0.0, min(1.0, ratio))


def _norm_field(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", s.strip().lower())


def score_order_placed(verify_payload: dict, spec: dict) -> float:
    """Exactly ONE order must exist (multiple orders = fail, anti-hack), with
    items multiset-exact, coupon code matching, and every shipping field exact
    (case-insensitive, whitespace-normalized)."""
    orders = verify_payload["orders"]
    if len(orders) != 1:
        return 0.0
    order = orders[0]
    if _cart_multiset(order["items"]) != _cart_multiset(spec["items"]):
        return 0.0
    expected_coupon = spec.get("coupon")
    got_coupon = order.get("coupon")
    if (expected_coupon or None) != (got_coupon or None):
        return 0.0
    for field in ("name", "address1", "city", "state", "zip"):
        if _norm_field(order["shipping"][field]) != _norm_field(spec["shipping"][field]):
            return 0.0
    return 1.0


# ---------------------------------------------------------- partial credit

def partial_credit(actual_items: list, spec_items: list) -> float:
    """Per spec line item: right sku present 0.4, right variant 0.3,
    right qty 0.3; averaged across spec line items. (T4/T6, terminal<1 only.)"""
    if not spec_items:
        return 0.0
    total = 0.0
    for want in spec_items:
        line = 0.0
        sku_lines = [a for a in actual_items if a["sku"] == want["sku"]]
        if sku_lines:
            line += 0.4
            variant_lines = [
                a for a in sku_lines
                if a["color"] == want["color"] and a["size"] == want["size"]
            ]
            if variant_lines:
                line += 0.3
                if any(a["qty"] == want["qty"] for a in variant_lines):
                    line += 0.3
        total += line
    return total / len(spec_items)


def partial_credit_constrained(cart: list, spec: dict, catalog_by_sku: dict) -> float:
    """Dense partial credit for T5 (cart_constrained), used ONLY when the cart is
    invalid (terminal == 0). T5 has no target SKUs, so credit is constraint-
    satisfaction based, and deliberately penalizes over-adding (the dominant
    failure/hack: dumping items to game a coverage term). Returns [0, 1]:

        coverage  = min(valid_distinct, k) / k                    (progress)
        tidiness  = min(valid_distinct, k) / max(total_lines, k)  (anti-superset)
        budget_ok = 1 if under budget else budget/actual, gated on valid items
        partial   = 0.5*coverage + 0.3*tidiness + 0.2*budget_ok

    A line item is 'qualifying' iff its product passes every per-item gate
    (category, attr, rating_min) AND has qty == qty_each."""
    cons = spec["constraints"]
    k = cons["k_distinct"]
    if k <= 0:
        return 0.0
    qty_each = cons.get("qty_each", 1)

    qualifying_skus = set()
    for i in cart:
        p = catalog_by_sku.get(i["sku"])
        if p is not None and _product_matches(p, cons) and i["qty"] == qty_each:
            qualifying_skus.add(i["sku"])
    valid_distinct = len(qualifying_skus)
    total_lines = len(cart)

    coverage = min(valid_distinct, k) / k
    tidiness = (min(valid_distinct, k) / max(total_lines, k)) if total_lines else 0.0

    actual = round(sum(i["unit_price"] * i["qty"] for i in cart), 2)
    if valid_distinct == 0 or actual <= 0:
        budget_ok = 0.0
    elif actual <= spec["budget"]:
        budget_ok = 1.0
    else:
        budget_ok = spec["budget"] / actual

    return 0.5 * coverage + 0.3 * tidiness + 0.2 * budget_ok


# ------------------------------------------------------------- composition

def efficiency(turns_used: int, max_turns: int) -> float:
    if max_turns <= 0:
        return 0.0
    return max(0.0, 1.0 - turns_used / max_turns)


def combine(terminal: float, partial: float, eff: float, tier: str,
            made_tool_calls: bool, weights: dict = WEIGHTS) -> float:
    """Final reward. Zero-gate first; partial credit for T4/T6 when terminal < 1
    and for T5 when terminal == 0 (once a T5 cart is valid its own terminal score
    is already graded 0.6-1.0, so no partial on top); efficiency bonus ONLY on
    full success (terminal == 1) so failing fast is never rewarded over trying
    hard (anti-hack)."""
    if not made_tool_calls:
        return 0.0
    partial_term = 0.0
    if tier in ("t4", "t6") and terminal < 1.0:
        partial_term = partial
    elif tier == "t5" and terminal == 0.0:
        partial_term = partial
    eff_term = eff if terminal >= 1.0 else 0.0
    return (
        weights["terminal"] * terminal
        + weights["partial"] * partial_term
        + weights["efficiency"] * eff_term
    )
