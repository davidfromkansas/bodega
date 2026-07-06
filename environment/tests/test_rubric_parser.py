"""M0 step 5 acceptance: rubric + parser unit tests over simulated
completions/verify payloads — every verify_spec type, every normalization
edge, superset-cart fail, partial-credit math (spec Part IV M0.5)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bodega_env.parser import (
    answers_equal,
    extract_answer,
    norm_number,
    split_name_value,
)
from bodega_env.rubric import (
    WEIGHTS,
    combine,
    efficiency,
    partial_credit,
    partial_credit_constrained,
    score_answer_match,
    score_cart_constrained,
    score_cart_exact,
    score_order_placed,
)

# ------------------------------------------------------------------ parser

def test_extract_last_answer_line_wins():
    text = "I think ANSWER: 10.00 is wrong.\nLet me check.\nANSWER: 89.99"
    assert extract_answer(text) == "89.99"


def test_extract_answer_missing():
    assert extract_answer("I could not find it, sorry.") is None
    assert extract_answer("") is None
    assert extract_answer(None) is None


def test_extract_answer_ignores_placeholder_echo():
    # echoing the question's format hint must not count as an answer
    assert extract_answer("ANSWER: <price>") is None
    assert extract_answer("ANSWER: <product name> | <price>") is None


def test_norm_number_edges():
    assert norm_number("$89.99") == 89.99
    assert norm_number("89.990") == 89.99
    assert norm_number("89") == 89.0
    assert norm_number("1,299.00") == 1299.0
    assert norm_number("not a number") is None


def test_split_on_last_pipe():
    assert split_name_value("Trailhead Rain Jacket | 89.99") == ("Trailhead Rain Jacket", "89.99")
    assert split_name_value("no pipe here") is None


@pytest.mark.parametrize(
    "got,expected,fields,ok",
    [
        ("$89.99", "89.99", ["price"], True),
        ("89.990", "89.99", ["price"], True),
        ("89.98", "89.99", ["price"], False),
        ("4.3", "4.3", ["value"], True),
        ("4.30", "4.3", ["value"], True),
        ("YES", "yes", ["value"], True),
        ("No", "no", ["value"], True),
        ("yes", "no", ["value"], False),
        ("38", "38", ["value"], True),
        ("38.0", "38", ["value"], True),
        ("  trailhead rain jacket  |  $89.99", "Trailhead Rain Jacket | 89.99", ["name", "price"], True),
        ("Trailhead Rain Jacket | 89.99", "Trailhead Rain Jacket | 89.99", ["name", "price"], True),
        ("Wrong Product | 89.99", "Trailhead Rain Jacket | 89.99", ["name", "price"], False),
        ("Trailhead Rain Jacket | 89.98", "Trailhead Rain Jacket | 89.99", ["name", "price"], False),
        ("Luma Earbuds | 55.0", "Luma Earbuds | 55", ["name", "value"], True),
        ("Luma Earbuds", "Luma Earbuds | 55", ["name", "value"], False),
    ],
)
def test_answers_equal(got, expected, fields, ok):
    assert answers_equal(got, expected, fields) is ok


def test_score_answer_match_end_to_end():
    text = "I browsed the store.\nANSWER: Trailhead Rain Jacket | $89.99"
    assert score_answer_match(text, "Trailhead Rain Jacket | 89.99", ["name", "price"]) == 1.0
    assert score_answer_match("no answer given", "89.99", ["price"]) == 0.0


# -------------------------------------------------------------- cart_exact

ITEM = {"sku": "OUT-0142", "color": "blue", "size": "M", "qty": 2, "unit_price": 89.99}
ITEM2 = {"sku": "KIT-0034", "color": "teal", "size": "One Size", "qty": 1, "unit_price": 25.49}


def payload(cart=None, orders=None):
    return {"cart": cart or [], "orders": orders or [], "coupons_applied": []}


def spec_of(*items):
    return [{k: i[k] for k in ("sku", "color", "size", "qty")} for i in items]


def test_cart_exact_pass():
    assert score_cart_exact(payload(cart=[ITEM, ITEM2]), spec_of(ITEM2, ITEM)) == 1.0


def test_cart_exact_superset_fails():
    # anti-hack: any extra line item => 0 (add-everything strategy must not pay)
    assert score_cart_exact(payload(cart=[ITEM, ITEM2]), spec_of(ITEM)) == 0.0


def test_cart_exact_wrong_qty_fails():
    wrong = dict(ITEM, qty=3)
    assert score_cart_exact(payload(cart=[wrong]), spec_of(ITEM)) == 0.0


def test_cart_exact_wrong_variant_fails():
    wrong = dict(ITEM, color="black")
    assert score_cart_exact(payload(cart=[wrong]), spec_of(ITEM)) == 0.0


def test_cart_exact_empty_fails():
    assert score_cart_exact(payload(), spec_of(ITEM)) == 0.0


# -------------------------------------------------------- cart_constrained

CATALOG = {
    "ELC-0001": {"sku": "ELC-0001", "category": "electronics", "attributes": ["bluetooth"], "rating": 4.5, "price": 30.0},
    "ELC-0002": {"sku": "ELC-0002", "category": "electronics", "attributes": ["bluetooth"], "rating": 4.0, "price": 43.25},
    "ELC-0003": {"sku": "ELC-0003", "category": "electronics", "attributes": ["wireless"], "rating": 3.0, "price": 20.0},
    "APP-0001": {"sku": "APP-0001", "category": "apparel", "attributes": ["recycled"], "rating": 4.8, "price": 15.0},
}

T5_SPEC = {
    "constraints": {"category": "electronics", "k_distinct": 2, "attr": "bluetooth",
                    "rating_min": None, "qty_each": 1},
    "budget": 161,
    "optimal_cost": 73.25,
}


def line(sku, qty=1):
    p = CATALOG[sku]
    return {"sku": sku, "color": "black", "size": "One Size", "qty": qty, "unit_price": p["price"]}


def test_cart_constrained_optimal_full_score():
    pl = payload(cart=[line("ELC-0001"), line("ELC-0002")])  # cost 73.25 == optimal
    assert score_cart_constrained(pl, T5_SPEC, CATALOG) == pytest.approx(1.0)


def test_cart_constrained_suboptimal_shaped():
    # pretend a pricier bluetooth item existed; simulate with inflated unit price
    pricey = dict(line("ELC-0002"), unit_price=116.5)  # actual = 146.5 = 2x optimal
    pl = payload(cart=[line("ELC-0001"), pricey])
    assert score_cart_constrained(pl, T5_SPEC, CATALOG) == pytest.approx(0.6 + 0.4 * 0.5)


def test_cart_constrained_gate_failures():
    # wrong attribute
    pl = payload(cart=[line("ELC-0001"), line("ELC-0003")])
    assert score_cart_constrained(pl, T5_SPEC, CATALOG) == 0.0
    # wrong category
    pl = payload(cart=[line("ELC-0001"), line("APP-0001")])
    assert score_cart_constrained(pl, T5_SPEC, CATALOG) == 0.0
    # not distinct (same sku twice)
    pl = payload(cart=[line("ELC-0001"), line("ELC-0001")])
    assert score_cart_constrained(pl, T5_SPEC, CATALOG) == 0.0
    # wrong count
    pl = payload(cart=[line("ELC-0001")])
    assert score_cart_constrained(pl, T5_SPEC, CATALOG) == 0.0
    # qty != 1
    pl = payload(cart=[line("ELC-0001", qty=2), line("ELC-0002")])
    assert score_cart_constrained(pl, T5_SPEC, CATALOG) == 0.0
    # over budget
    over = dict(line("ELC-0002"), unit_price=200.0)
    pl = payload(cart=[line("ELC-0001"), over])
    assert score_cart_constrained(pl, T5_SPEC, CATALOG) == 0.0


def test_cart_constrained_rating_gate():
    spec = {
        "constraints": {"category": "electronics", "k_distinct": 2, "attr": None,
                        "rating_min": 4.2, "qty_each": 1},
        "budget": 200, "optimal_cost": 50.0,
    }
    pl = payload(cart=[line("ELC-0001"), line("ELC-0002")])  # 4.5 ok, 4.0 fails
    assert score_cart_constrained(pl, spec, CATALOG) == 0.0


# ------------------------------------------------------------ order_placed

T6_SPEC = {
    "items": spec_of(ITEM),
    "coupon": "SAVE10",
    "shipping": {"name": "Ada Lovelace", "address1": "12 Analytical Way",
                 "city": "London", "state": "NY", "zip": "10001"},
}


def order(items=None, coupon="SAVE10", **ship_overrides):
    shipping = dict(T6_SPEC["shipping"])
    shipping.update(ship_overrides)
    return {
        "order_id": "ord_x_1",
        "items": items if items is not None else [dict(ITEM)],
        "subtotal": 179.98, "coupon": coupon, "discount": 18.0, "total": 161.98,
        "shipping": shipping,
    }


def test_order_placed_pass():
    assert score_order_placed(payload(orders=[order()]), T6_SPEC) == 1.0


def test_order_placed_shipping_case_whitespace_insensitive():
    o = order(name="  ADA   LOVELACE ", city="london")
    assert score_order_placed(payload(orders=[o]), T6_SPEC) == 1.0


def test_order_placed_wrong_coupon_fails():
    assert score_order_placed(payload(orders=[order(coupon=None)]), T6_SPEC) == 0.0
    assert score_order_placed(payload(orders=[order(coupon="FLAT15")]), T6_SPEC) == 0.0


def test_order_placed_no_coupon_spec():
    spec = dict(T6_SPEC, coupon=None)
    assert score_order_placed(payload(orders=[order(coupon=None)]), spec) == 1.0
    assert score_order_placed(payload(orders=[order(coupon="SAVE10")]), spec) == 0.0


def test_order_placed_extra_item_fails():
    o = order(items=[dict(ITEM), dict(ITEM2)])
    assert score_order_placed(payload(orders=[o]), T6_SPEC) == 0.0


def test_order_placed_wrong_shipping_fails():
    assert score_order_placed(payload(orders=[order(zip="99999")]), T6_SPEC) == 0.0


def test_order_placed_multiple_orders_fail():
    # anti-hack: retry-until-lucky ordering must not pay
    assert score_order_placed(payload(orders=[order(), order()]), T6_SPEC) == 0.0


def test_order_placed_zero_orders_fail():
    assert score_order_placed(payload(), T6_SPEC) == 0.0


# ---------------------------------------------------------- partial credit

def test_partial_credit_math():
    spec = spec_of(ITEM, ITEM2)
    # both perfect -> 1.0
    assert partial_credit([dict(ITEM), dict(ITEM2)], spec) == pytest.approx(1.0)
    # right skus, one wrong variant: (1.0 + 0.4) / 2
    wrong_variant = dict(ITEM2, color="navy")
    assert partial_credit([dict(ITEM), wrong_variant], spec) == pytest.approx(0.7)
    # right sku+variant, wrong qty: (1.0 + 0.7) / 2
    wrong_qty = dict(ITEM2, qty=3)
    assert partial_credit([dict(ITEM), wrong_qty], spec) == pytest.approx(0.85)
    # one sku missing entirely: (1.0 + 0) / 2
    assert partial_credit([dict(ITEM)], spec) == pytest.approx(0.5)
    # empty cart -> 0
    assert partial_credit([], spec) == 0.0


# ------------------------------------- partial credit (T5 cart_constrained)

def test_partial_constrained_full_valid_under_budget():
    # exactly k valid items, under budget -> coverage 1, tidiness 1, budget 1
    pl = [line("ELC-0001"), line("ELC-0002")]
    assert partial_credit_constrained(pl, T5_SPEC, CATALOG) == pytest.approx(1.0)


def test_partial_constrained_progress_one_of_two():
    # one valid item under budget -> 0.5*0.5 + 0.3*0.5 + 0.2*1
    pl = [line("ELC-0001")]
    assert partial_credit_constrained(pl, T5_SPEC, CATALOG) == pytest.approx(0.6)


def test_partial_constrained_over_budget_graded():
    # both valid but subtotal over budget -> budget term = budget/actual
    over = dict(line("ELC-0002"), unit_price=200.0)  # actual 230 > 161
    pl = [line("ELC-0001"), over]
    expected = 0.5 * 1 + 0.3 * 1 + 0.2 * (161 / 230.0)
    assert partial_credit_constrained(pl, T5_SPEC, CATALOG) == pytest.approx(expected)


def test_partial_constrained_extras_penalized_via_tidiness():
    # 2 valid + 2 junk (wrong attr + wrong category), under budget
    # coverage 1, tidiness min(2,2)/max(4,2)=0.5, budget 1
    pl = [line("ELC-0001"), line("ELC-0002"), line("ELC-0003"), line("APP-0001")]
    assert partial_credit_constrained(pl, T5_SPEC, CATALOG) == pytest.approx(0.85)


def test_partial_constrained_over_add_hack_capped():
    # dumping many valid copies can't inflate coverage (capped at k) and tanks
    # tidiness; must stay well below a real success's weighted floor (0.51)
    pl = [line("ELC-0001"), line("ELC-0002")] + [line("ELC-0001")] * 18
    val = partial_credit_constrained(pl, T5_SPEC, CATALOG)
    assert val < 1.0
    assert WEIGHTS["partial"] * val < WEIGHTS["terminal"] * 0.6


def test_partial_constrained_junk_only_zero():
    # no qualifying items -> 0 even if cheap/under budget (no free credit)
    assert partial_credit_constrained([line("ELC-0003")], T5_SPEC, CATALOG) == 0.0


def test_partial_constrained_empty_zero():
    assert partial_credit_constrained([], T5_SPEC, CATALOG) == 0.0


def test_partial_constrained_duplicates_count_once():
    # same valid sku twice: distinct=1, total_lines=2 -> tidiness penalty
    pl = [line("ELC-0001"), line("ELC-0001")]
    assert partial_credit_constrained(pl, T5_SPEC, CATALOG) == pytest.approx(0.6)


def test_combine_t5_partial_only_when_terminal_zero():
    # invalid T5 cart (terminal 0) -> partial is awarded
    assert combine(0.0, 0.6, 0.0, "t5", True) == pytest.approx(0.10 * 0.6)
    # valid-but-suboptimal T5 cart (terminal 0.7) -> NO partial on top of terminal
    assert combine(0.7, 1.0, 0.0, "t5", True) == pytest.approx(0.85 * 0.7)


# ------------------------------------------------------------- composition

def test_efficiency():
    assert efficiency(0, 10) == 1.0
    assert efficiency(5, 10) == 0.5
    assert efficiency(10, 10) == 0.0
    assert efficiency(12, 10) == 0.0  # clipped


def test_combine_zero_gate():
    # no tool calls -> 0 regardless of a "correct" answer (anti answer-from-priors)
    assert combine(1.0, 1.0, 1.0, "t1", made_tool_calls=False) == 0.0


def test_combine_weights():
    # perfect T1: 0.85 + efficiency share
    assert combine(1.0, 0.0, 1.0, "t1", True) == pytest.approx(0.85 + 0.05)
    # failed T4 with partial 0.7: efficiency is NOT awarded on failure (anti-hack)
    assert combine(0.0, 0.7, 0.5, "t4", True) == pytest.approx(0.10 * 0.7)
    # partial credit NOT awarded when terminal == 1
    assert combine(1.0, 0.9, 0.0, "t4", True) == pytest.approx(0.85)
    # partial credit NOT awarded outside t4/t6
    assert combine(0.0, 0.9, 0.0, "t2", True) == pytest.approx(0.0)


def test_efficiency_only_on_full_success():
    # failing fast must never beat trying hard: no efficiency bonus unless terminal==1
    assert combine(0.0, 0.0, 0.9, "t1", True) == 0.0
    assert combine(0.0, 0.0, 0.9, "t6", True) == 0.0
    # full success gets the speed bonus
    assert combine(1.0, 0.0, 0.9, "t1", True) == pytest.approx(0.85 + 0.05 * 0.9)


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
