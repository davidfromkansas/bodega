#!/usr/bin/env python3
"""Oracle: scripted Playwright bot (no LLM) that solves every task through the
real storefront UI and asserts the graders agree (M0 step 6, Part III §4).

- Answer tiers (T1-T3): derives the answer from RENDERED PAGES ONLY
  (search box, category filters, product pages) and checks it against the
  task's ground truth via the environment's own parser.
- State tiers (T4-T6): drives cart/checkout forms, then asserts via the
  verify API + the environment's own rubric scorers.

If the oracle can't score ~100%, every later model number would measure our
bugs. Doubles as the regression suite after every env change.

Usage:
  python oracle/solve.py --split eval --against localhost
  python oracle/solve.py --split eval-ood --against localhost   # store must run BODEGA_CATALOG=B
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "environment"))

from bodega_env.parser import answers_equal  # noqa: E402
from bodega_env.rubric import (  # noqa: E402
    score_cart_constrained,
    score_cart_exact,
    score_order_placed,
)

VERIFY_KEY = os.environ.get("BODEGA_VERIFY_KEY", "dev-verify-key")

SHIP_CARD = "4111111111111111"


def load_catalog(label):
    with open(ROOT / "storefront" / "seed" / f"catalog-seed-{label}.json") as f:
        cat = json.load(f)
    return {p["sku"]: p for p in cat["products"]}


def catalog_label_for(task):
    # task_id format: t2-A7-0031 / t1-B2000-0001
    return task["task_id"].split("-")[1][0]


def mint_sid(store_url):
    r = httpx.post(f"{store_url}/api/sessions",
                   headers={"Authorization": f"Bearer {VERIFY_KEY}"}, timeout=15)
    r.raise_for_status()
    return r.json()["sid"]


def fetch_verify(store_url, sid):
    r = httpx.get(f"{store_url}/api/verify/{sid}",
                  headers={"Authorization": f"Bearer {VERIFY_KEY}"}, timeout=15)
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------- navigation

def goto_product(page, store_url, product):
    """Reach a product page the way a shopper would: search box -> click card."""
    page.goto(f"{store_url}/")
    page.fill("#search-input", product["name"])
    page.click("#search-submit")
    page.click(f'#card-{product["sku"]} a.name')
    page.wait_for_selector("#product-name")


def read_rendered_price(page):
    txt = page.text_content("#product-price").strip()
    return txt.lstrip("$")


def read_rendered_rating(page):
    txt = page.text_content("#product-rating").strip()
    return txt.split("★")[0].strip()


def read_rendered_spec(page, field):
    txt = page.text_content(f"#spec-{field}").strip()
    # "Battery life: 38 hours" -> "38"
    return txt.split(":", 1)[1].strip().split(" ")[0]


def read_rendered_stock(page, color, size):
    rows = page.locator("#stock-table tbody tr")
    for i in range(rows.count()):
        cells = rows.nth(i).locator("td").all_text_contents()
        if cells[0] == color and cells[1] == size:
            return "yes" if "In stock" in cells[2] else "no"
    return None


def add_to_cart(page, store_url, by_sku, item):
    p = by_sku[item["sku"]]
    goto_product(page, store_url, p)
    page.select_option("#color", item["color"])
    page.select_option("#size", item["size"])
    page.fill("#qty", str(item["qty"]))
    page.click("#add-to-cart")
    page.wait_for_selector("#cart-notice, #cart-error")
    err = page.locator("#cart-error")
    if err.count() > 0:
        raise AssertionError(f"add_to_cart error: {err.text_content()}")


# ------------------------------------------------------------- tier logic

def solve_t1(page, store_url, task, by_sku):
    spec = task["info"]["verify_spec"]
    p = by_sku[spec["sku"]]
    goto_product(page, store_url, p)
    kind = spec["kind"]
    if kind == "price":
        derived = read_rendered_price(page)
    elif kind == "rating":
        derived = read_rendered_rating(page)
    elif kind == "numeric":
        derived = read_rendered_spec(page, spec["field"])
    else:  # stock
        derived = read_rendered_stock(page, spec["color"], spec["size"])
    return derived


def solve_t2(page, store_url, task, by_sku):
    c = task["info"]["verify_spec"]["constraints"]
    params = []
    if c["price_max"] is not None:
        params.append(("price_max", str(c["price_max"])))
    if c["rating_min"] is not None:
        params.append(("rating_min", str(c["rating_min"])))
    if c["attr"]:
        params.append(("attr", c["attr"]))
    params.append(("sort", "price_asc" if c["mode"] == "cheapest" else "rating"))
    qs = "&".join(f"{k}={v}" for k, v in params)
    page.goto(f"{store_url}/c/{c['category']}?{qs}")
    page.wait_for_selector("#category-results")
    first = page.locator("#category-results .product-card").first
    name = first.locator("a.name").text_content().strip()
    if c["mode"] == "cheapest":
        value = first.locator(".price").text_content().strip().lstrip("$")
    else:
        value = first.locator(".rating").text_content().strip().split("★")[0]
    return f"{name} | {value}"


def solve_t3(page, store_url, task, by_sku):
    spec = task["info"]["verify_spec"]
    field, mode = spec["field"], spec["mode"]
    best_name, best_val = None, None
    for sku in spec["candidates"]:
        p = by_sku[sku]
        goto_product(page, store_url, p)
        val = float(read_rendered_spec(page, field))
        better = (
            best_val is None
            or (mode == "highest" and val > best_val)
            or (mode == "lowest" and val < best_val)
        )
        if better:
            best_name, best_val = p["name"], val
    v = int(best_val) if best_val == int(best_val) else best_val
    return f"{best_name} | {v}"


def solve_t4(page, store_url, task, by_sku, sid):
    for item in task["info"]["verify_spec"]["items"]:
        add_to_cart(page, store_url, by_sku, item)
    pl = fetch_verify(store_url, sid)
    return score_cart_exact(pl, task["info"]["verify_spec"]["items"]) == 1.0


def solve_t5(page, store_url, task, by_sku, sid, full_catalog):
    spec = task["info"]["verify_spec"]
    c = spec["constraints"]
    pool = [
        p for p in full_catalog.values()
        if p["category"] == c["category"]
        and (c["attr"] is None or c["attr"] in p["attributes"])
        and (c["rating_min"] is None or p["rating"] >= c["rating_min"])
        and any(q > 0 for q in p["stock"].values())
    ]
    pool.sort(key=lambda p: (p["price"], p["sku"]))
    chosen = pool[: c["k_distinct"]]
    for p in chosen:
        color, size = next(
            k.split("|") for k, q in sorted(p["stock"].items()) if q > 0
        )
        add_to_cart(page, store_url, by_sku,
                    {"sku": p["sku"], "color": color, "size": size, "qty": 1})
    pl = fetch_verify(store_url, sid)
    return score_cart_constrained(pl, spec, full_catalog) == 1.0


def solve_t6(page, store_url, task, by_sku, sid):
    spec = task["info"]["verify_spec"]
    for item in spec["items"]:
        add_to_cart(page, store_url, by_sku, item)
    if spec["coupon"]:
        page.goto(f"{store_url}/cart")
        page.fill("#coupon-code", spec["coupon"])
        page.click("#apply-coupon")
        page.wait_for_selector("#cart-notice")
    page.goto(f"{store_url}/checkout")
    s = spec["shipping"]
    page.fill("#name", s["name"])
    page.fill("#address1", s["address1"])
    page.fill("#city", s["city"])
    page.fill("#state", s["state"])
    page.fill("#zip", s["zip"])
    page.fill("#card", SHIP_CARD)
    page.click("#place-order")
    page.wait_for_selector("#order-confirmation")
    pl = fetch_verify(store_url, sid)
    return score_order_placed(pl, spec) == 1.0


# ------------------------------------------------------------------ main

def solve_task(browser, store_url, task, by_sku, full_catalog):
    tier = task["info"]["tier"]
    sid = mint_sid(store_url)
    ctx = browser.new_context()
    page = ctx.new_page()
    try:
        page.goto(f"{store_url}/?sid={sid}")
        if tier in ("t1", "t2", "t3"):
            derived = {"t1": solve_t1, "t2": solve_t2, "t3": solve_t3}[tier](
                page, store_url, task, by_sku
            )
            ok = answers_equal(str(derived), task["answer"],
                               task["info"]["verify_spec"]["fields"])
            return ok, f"derived={derived!r} expected={task['answer']!r}"
        if tier == "t4":
            return solve_t4(page, store_url, task, by_sku, sid), "cart_exact"
        if tier == "t5":
            return solve_t5(page, store_url, task, by_sku, sid, full_catalog), "cart_constrained"
        if tier == "t6":
            return solve_t6(page, store_url, task, by_sku, sid), "order_placed"
        raise ValueError(tier)
    finally:
        ctx.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default=None, help="train-pool | eval | eval-ood")
    ap.add_argument("--tasks", default=None, help="explicit JSONL path")
    ap.add_argument("--against", default="localhost")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tier", default=None)
    args = ap.parse_args()

    store_url = (
        "http://localhost:3000" if args.against == "localhost" else args.against.rstrip("/")
    )
    path = args.tasks or (ROOT / "taskgen" / "splits" / f"{args.split}.jsonl")
    with open(path) as f:
        tasks = [json.loads(line) for line in f]
    if args.tier:
        tasks = [t for t in tasks if t["info"]["tier"] == args.tier]
    if args.limit:
        tasks = tasks[: args.limit]

    catalogs = {label: load_catalog(label) for label in {catalog_label_for(t) for t in tasks}}

    results, failures = {}, []
    start = time.time()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for i, task in enumerate(tasks, 1):
            by_sku = catalogs[catalog_label_for(task)]
            tier = task["info"]["tier"]
            try:
                ok, detail = solve_task(browser, store_url, task, by_sku, by_sku)
            except Exception as e:
                ok, detail = False, f"EXC {type(e).__name__}: {e}"
            results.setdefault(tier, []).append(ok)
            if not ok:
                failures.append((task["task_id"], detail[:180]))
            if i % 25 == 0:
                print(f"  ...{i}/{len(tasks)} ({time.time()-start:.0f}s)")
        browser.close()

    total = sum(len(v) for v in results.values())
    solved = sum(sum(v) for v in results.values())
    print("\nper-tier solve rate:")
    for tier in sorted(results):
        v = results[tier]
        print(f"  {tier}: {sum(v)}/{len(v)}")
    for tid, detail in failures:
        print(f"  FAIL {tid}: {detail}")
    rate = 100.0 * solved / total if total else 0.0
    print(f"\nsolve rate: {solved}/{total} = {rate:.1f}%  ({time.time()-start:.0f}s)")
    sys.exit(0 if rate >= 98.0 else 1)


if __name__ == "__main__":
    main()
