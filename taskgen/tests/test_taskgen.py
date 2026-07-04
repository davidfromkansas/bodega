"""M0 step 4 acceptance: golden-file determinism + rejection-rule enforcement.

Every rejection rule from the spec gets validated over a large generated batch:
- T2: unique winner, runner-up margin ($0.50 price / 0.2 rating)
- T3: no ties
- T4/T6: no out-of-stock variants, qty <= available
- T5: feasible, optimal <= budget
- T6: coupon effective (subtotal >= min_subtotal)
- state tiers: answer == "" (HF Dataset typing, spec appendix)
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TASKGEN = Path(__file__).resolve().parent.parent
ROOT = TASKGEN.parent
CATALOG_A = ROOT / "storefront" / "seed" / "catalog-seed-A.json"
GOLDEN = Path(__file__).resolve().parent / "golden" / "sample_A_seed0_n5.jsonl"

sys.path.insert(0, str(TASKGEN))

from common import COUPONS, load_catalog  # noqa: E402
from generate import generate_tasks  # noqa: E402
from solver import (  # noqa: E402
    cheapest,
    comparison_winner,
    filter_products,
    highest_rated,
    order_totals,
)

ALL_TIERS = ["t1", "t2", "t3", "t4", "t5", "t6"]


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(str(CATALOG_A))


@pytest.fixture(scope="module")
def products(catalog):
    return catalog["products"]


@pytest.fixture(scope="module")
def by_sku(products):
    return {p["sku"]: p for p in products}


@pytest.fixture(scope="module")
def batch(catalog):
    # large batch across tiers for rule validation
    return generate_tasks(str(CATALOG_A), task_seed=42, tiers=ALL_TIERS, n=40)


# ------------------------------------------------------------ determinism

def test_golden_file_regeneration_byte_identical(tmp_path):
    out = tmp_path / "regen.jsonl"
    subprocess.run(
        [sys.executable, str(TASKGEN / "generate.py"),
         "--catalog", str(CATALOG_A), "--task-seed", "0",
         "--tier", "all", "--n", "5", "--out", str(out)],
        check=True, capture_output=True,
    )
    assert out.read_bytes() == GOLDEN.read_bytes()


def test_same_seed_same_output(catalog):
    a = generate_tasks(str(CATALOG_A), 7, ["t2"], 10)
    b = generate_tasks(str(CATALOG_A), 7, ["t2"], 10)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_different_seeds_differ():
    a = generate_tasks(str(CATALOG_A), 7, ["t2"], 10)
    b = generate_tasks(str(CATALOG_A), 8, ["t2"], 10)
    assert json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)


# ------------------------------------------------------------ row contract

def test_row_shape_and_counts(batch):
    assert len(batch) == 40 * 6
    for t in batch:
        assert set(t.keys()) == {"task_id", "question", "answer", "start_url", "info"}
        assert t["start_url"] == "{BODEGA_STORE_URL}"
        info = t["info"]
        assert info["tier"] in ALL_TIERS
        assert 0.0 <= info["difficulty"] <= 1.0
        assert info["max_turns"] in (5, 8, 10, 14, 16)
        assert isinstance(t["answer"], str)  # never None


def test_state_tiers_have_empty_answer(batch):
    for t in batch:
        if t["info"]["tier"] in ("t4", "t5", "t6"):
            assert t["answer"] == "", t["task_id"]
        else:
            assert t["answer"] != "", t["task_id"]


def test_unique_task_ids(batch):
    ids = [t["task_id"] for t in batch]
    assert len(ids) == len(set(ids))


# ----------------------------------------------------- rejection rules: T2

def test_t2_unique_winner_with_margin(products, batch, by_sku):
    for t in batch:
        if t["info"]["tier"] != "t2":
            continue
        c = t["info"]["verify_spec"]["constraints"]
        kw = dict(category=c["category"], attr=c["attr"],
                  price_max=c["price_max"], rating_min=c["rating_min"])
        if c["mode"] == "cheapest":
            winner, runner, m = cheapest(products, **kw)
            assert winner["sku"] == t["info"]["verify_spec"]["sku"], t["task_id"]
            if runner:
                assert runner["price"] - winner["price"] >= 0.50, t["task_id"]
        else:
            winner, runner, m = highest_rated(products, **kw)
            assert winner["sku"] == t["info"]["verify_spec"]["sku"], t["task_id"]
            if runner:
                assert winner["rating"] - runner["rating"] >= 0.2, t["task_id"]
        assert len(m) >= 2, t["task_id"]  # a real search, not a single-item category


# ----------------------------------------------------- rejection rules: T3

def test_t3_no_ties(products, batch, by_sku):
    for t in batch:
        if t["info"]["tier"] != "t3":
            continue
        spec = t["info"]["verify_spec"]
        subset = [by_sku[s] for s in spec["candidates"]]
        w = comparison_winner(subset, spec["field"], spec["mode"])
        assert w is not None, t["task_id"]
        assert w["sku"] == spec["sku"], t["task_id"]


# -------------------------------------------------- rejection rules: T4/T6

def _assert_items_in_stock(items, by_sku, task_id):
    for it in items:
        p = by_sku[it["sku"]]
        avail = p["stock"].get(f"{it['color']}|{it['size']}", 0)
        assert avail >= it["qty"], f"{task_id}: {it} exceeds stock {avail}"


def test_t4_items_in_stock_and_no_dup_lines(by_sku, batch):
    for t in batch:
        if t["info"]["tier"] != "t4":
            continue
        items = t["info"]["verify_spec"]["items"]
        assert 1 <= len(items) <= 3
        _assert_items_in_stock(items, by_sku, t["task_id"])
        keys = [(i["sku"], i["color"], i["size"]) for i in items]
        assert len(keys) == len(set(keys)), t["task_id"]


def test_t6_items_in_stock_coupon_effective(by_sku, batch):
    coupons = {c["code"]: c for c in COUPONS}
    for t in batch:
        if t["info"]["tier"] != "t6":
            continue
        spec = t["info"]["verify_spec"]
        _assert_items_in_stock(spec["items"], by_sku, t["task_id"])
        ship = spec["shipping"]
        assert len(ship["state"]) == 2 and len(ship["zip"]) == 5
        if spec["coupon"]:
            c = coupons[spec["coupon"]]
            items = [
                {"unit_price": by_sku[i["sku"]]["price"], "qty": i["qty"]}
                for i in spec["items"]
            ]
            subtotal, discount, _ = order_totals(items, c)
            assert discount > 0, f"{t['task_id']}: coupon ineffective (subtotal {subtotal})"


# ----------------------------------------------------- rejection rules: T5

def test_t5_feasible_with_headroom(products, batch):
    for t in batch:
        if t["info"]["tier"] != "t5":
            continue
        spec = t["info"]["verify_spec"]
        c = spec["constraints"]
        pool = [
            p for p in filter_products(
                products, category=c["category"], attr=c["attr"], rating_min=c["rating_min"]
            )
            if any(q > 0 for q in p["stock"].values())
        ]
        assert len(pool) >= c["k_distinct"], t["task_id"]
        cheapest_k = sorted(p["price"] for p in pool)[: c["k_distinct"]]
        assert round(sum(cheapest_k), 2) == spec["optimal_cost"], t["task_id"]
        assert spec["optimal_cost"] < spec["budget"], t["task_id"]


# --------------------------------------------------------- answer sanity

def test_t1_answers_match_catalog(by_sku, batch):
    for t in batch:
        if t["info"]["tier"] != "t1":
            continue
        spec = t["info"]["verify_spec"]
        p = by_sku[spec["sku"]]
        if spec["kind"] == "price":
            assert t["answer"] == f"{p['price']:.2f}"
        elif spec["kind"] == "rating":
            assert t["answer"] == f"{p['rating']:.1f}"
        elif spec["kind"] == "stock":
            assert t["answer"] in ("yes", "no")


def test_phrasing_banks_slot_integrity():
    """Every phrasing variant in a bank must use the exact same slots — this is
    what guarantees no register drops a constraint (the diversity/ambiguity line)."""
    import re

    from phrasing import BANKS

    for key, bank in BANKS.items():
        assert len(bank) == 4, key
        slot_sets = [frozenset(re.findall(r"{(\w+)}", tpl)) for tpl in bank]
        assert len(set(slot_sets)) == 1, f"{key}: registers use different slots"


def test_train_registers_exclude_held_out():
    from phrasing import HELD_OUT_REGISTER, TRAIN_REGISTERS

    assert HELD_OUT_REGISTER not in TRAIN_REGISTERS
    tasks = generate_tasks(str(CATALOG_A), 5, ALL_TIERS, 10, registers=TRAIN_REGISTERS)
    for t in tasks:
        assert t["info"]["verify_spec"]["register"] != HELD_OUT_REGISTER, t["task_id"]


def test_registers_produce_different_questions():
    a = generate_tasks(str(CATALOG_A), 5, ["t2"], 10, registers=[0])
    b = generate_tasks(str(CATALOG_A), 5, ["t2"], 10, registers=[1])
    # same seed, same specs — different surface language
    assert [t["answer"] for t in a] == [t["answer"] for t in b]
    assert [t["question"] for t in a] != [t["question"] for t in b]


def test_no_pipe_in_answer_names(batch):
    # A5: '|' is reserved as the answer delimiter
    for t in batch:
        if t["answer"] and "|" in t["answer"]:
            name_part = t["answer"].rsplit("|", 1)[0].strip()
            assert "|" not in name_part, t["task_id"]
