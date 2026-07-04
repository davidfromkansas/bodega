"""M0 step 2/3 acceptance tests, run against a live storefront (docker compose up).

Covers: session minting + bearer auth, ?sid= cookie binding + redirect,
sid isolation under interleaved concurrent cart ops, cache headers (A4),
page rendering, and stock guards.
"""

import json
import os
import re
import uuid
from pathlib import Path

import httpx
import pytest

BASE = os.environ.get("BODEGA_STORE_URL", "http://localhost:3000")
KEY = os.environ.get("BODEGA_VERIFY_KEY", "dev-verify-key")
SEED = Path(__file__).resolve().parent.parent / "seed" / "catalog-seed-A.json"


def catalog():
    with open(SEED) as f:
        return json.load(f)["products"]


def client():
    # each client = its own browser (separate cookie jar), no shared state
    return httpx.Client(base_url=BASE, follow_redirects=False, timeout=30)


def mint_sid(c: httpx.Client) -> str:
    r = c.post("/api/sessions", headers={"Authorization": f"Bearer {KEY}"})
    assert r.status_code == 200, r.text
    return r.json()["sid"]


def bind(c: httpx.Client, sid: str):
    r = c.get(f"/?sid={sid}")
    assert r.status_code == 302
    assert "sid=" not in r.headers["location"]
    assert "bodega_sid" in r.headers.get("set-cookie", "")


def first_in_stock(p):
    for key, n in sorted(p["stock"].items()):
        if n > 0:
            c, s = key.split("|")
            return c, s, n
    return None


def pick_product(min_stock=2):
    for p in catalog():
        v = first_in_stock(p)
        if v and v[2] >= min_stock:
            return p, v
    raise AssertionError("no in-stock product found")


# ---------------------------------------------------------------- sessions

def test_sessions_requires_bearer():
    with client() as c:
        assert c.post("/api/sessions").status_code == 401
        assert (
            c.post("/api/sessions", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )


def test_sid_binding_redirect():
    with client() as c:
        sid = mint_sid(c)
        bind(c, sid)


def test_redirects_are_relative_no_host_leak():
    # Regression: redirects must not leak the container hostname; a browser
    # behind Docker/proxy/Railway must resolve Location against its own host.
    p, (color, size, _) = pick_product()
    with client() as c:
        sid = mint_sid(c)
        # sid-strip redirect (middleware): absolute, but must use the request's
        # host (localhost), never the container hostname.
        r1 = c.get(f"/?sid={sid}")
        loc1 = r1.headers["location"]
        assert "localhost" in loc1, loc1
        assert "sid=" not in loc1, loc1
        # mutation redirect (add to cart): relative, no host leak
        r2 = add_to_cart(c, p["sku"], color, size, 1)
        loc2 = r2.headers["location"]
        assert loc2.startswith("/"), loc2
        assert "://" not in loc2, loc2


def test_malformed_sid_param_ignored():
    with client() as c:
        r = c.get("/?sid=not-a-uuid")
        assert r.status_code == 200  # no redirect, no cookie
        assert "bodega_sid" not in r.headers.get("set-cookie", "")


def test_no_store_cache_header():
    # A4: sid-scoped state must never be cached
    with client() as c:
        for path in ["/", "/cart"]:
            r = c.get(path)
            assert r.headers.get("cache-control") == "no-store", path


# ------------------------------------------------------------------ pages

def test_home_renders_categories_and_featured():
    with client() as c:
        html = c.get("/").text
        for cat in ["apparel", "electronics", "outdoors"]:
            assert f'href="/c/{cat}"' in html
        featured = [p for p in catalog() if p["featured"]]
        for p in featured[:3]:
            assert p["name"] in html


def test_search_finds_product():
    p = catalog()[0]
    with client() as c:
        html = c.get("/search", params={"q": p["name"]}).text
        assert p["name"] in html


def test_category_filter_price_and_sort():
    with client() as c:
        html = c.get(
            "/c/outdoors", params={"price_max": 60, "sort": "price_asc"}
        ).text
        prices = [float(m) for m in re.findall(r'class="price"[^>]*>\$([0-9.]+)<', html)]
        assert prices, "no products rendered"
        assert all(pr <= 60 for pr in prices)
        assert prices == sorted(prices)


def test_category_pagination():
    with client() as c:
        # unfiltered category has 90 products -> 4 pages of 24
        html1 = c.get("/c/outdoors").text
        assert "page 1 of 4" in html1
        assert html1.count('class="product-card"') == 24
        assert 'id="page-2"' in html1
        html4 = c.get("/c/outdoors", params={"page": 4}).text
        assert "page 4 of 4" in html4
        assert html4.count('class="product-card"') == 90 - 3 * 24
        # sort survives pagination
        htmlp2 = c.get("/c/outdoors", params={"sort": "price_asc", "page": 2}).text
        prices = [float(m) for m in re.findall(r'class="price"[^>]*>\$([0-9.]+)<', htmlp2)]
        assert prices == sorted(prices)


def test_product_page_shows_facts():
    p, _ = pick_product()
    with client() as c:
        html = c.get(f"/p/{p['slug']}").text
        assert p["name"] in html
        assert f"${p['price']:.2f}" in html
        assert f"{p['rating']:.1f}" in html
        for a in p["attributes"]:
            assert a in html


# ------------------------------------------------------------------- cart

def add_to_cart(c, sku, color, size, qty):
    return c.post(
        "/api/cart/add",
        data={"sku": sku, "color": color, "size": size, "qty": qty},
    )


def cart_html(c):
    return c.get("/cart").text


def test_add_to_cart_and_view():
    p, (color, size, _) = pick_product()
    with client() as c:
        sid = mint_sid(c)
        bind(c, sid)
        r = add_to_cart(c, p["sku"], color, size, 1)
        assert r.status_code == 303
        html = cart_html(c)
        assert p["name"] in html
        assert f"${p['price']:.2f}" in html


def test_out_of_stock_add_rejected():
    oos = None
    for p in catalog():
        for key, n in sorted(p["stock"].items()):
            if n == 0:
                c_, s_ = key.split("|")
                oos = (p, c_, s_)
                break
        if oos:
            break
    assert oos, "catalog has no out-of-stock variant"
    p, color, size = oos
    with client() as c:
        sid = mint_sid(c)
        bind(c, sid)
        r = add_to_cart(c, p["sku"], color, size, 1)
        assert r.status_code == 303
        assert "error" in r.headers["location"]
        assert p["name"] not in cart_html(c)


def test_qty_exceeding_stock_rejected():
    p, (color, size, n) = pick_product()
    with client() as c:
        sid = mint_sid(c)
        bind(c, sid)
        r = add_to_cart(c, p["sku"], color, size, n + 1)
        assert "error" in r.headers["location"]


def test_anonymous_visitor_gets_cart():
    p, (color, size, _) = pick_product()
    with client() as c:
        r = add_to_cart(c, p["sku"], color, size, 1)  # no sid, no cookie
        assert r.status_code == 303
        assert "bodega_sid" in r.headers.get("set-cookie", "")
        assert p["name"] in cart_html(c)


# ----------------------------------------------------- concurrency / bleed

def test_two_sids_interleaved_no_bleed():
    """Spec M0.2 acceptance: two sids, interleaved cart ops, no bleed."""
    prods = []
    for p in catalog():
        v = first_in_stock(p)
        if v and v[2] >= 3:
            prods.append((p, v))
        if len(prods) == 2:
            break
    (pa, (ca_, sa_, _)), (pb, (cb_, sb_, _)) = prods

    with client() as ca, client() as cb:
        sid_a = mint_sid(ca)
        sid_b = mint_sid(cb)
        assert sid_a != sid_b
        bind(ca, sid_a)
        bind(cb, sid_b)

        # interleaved mutations
        add_to_cart(ca, pa["sku"], ca_, sa_, 1)
        add_to_cart(cb, pb["sku"], cb_, sb_, 2)
        add_to_cart(ca, pa["sku"], ca_, sa_, 1)  # bump A's qty to 2

        html_a = cart_html(ca)
        html_b = cart_html(cb)

        assert pa["name"] in html_a
        assert pb["name"] not in html_a, "sid B's item leaked into sid A's cart"
        assert pb["name"] in html_b
        assert pa["name"] not in html_b, "sid A's item leaked into sid B's cart"


def test_cookieless_request_sees_no_cart():
    p, (color, size, _) = pick_product()
    with client() as c:
        sid = mint_sid(c)
        bind(c, sid)
        add_to_cart(c, p["sku"], color, size, 1)
    with client() as fresh:  # brand-new browser, no cookie
        assert p["name"] not in cart_html(fresh)


def test_unminted_sid_yields_no_cart():
    # a guessed/unminted uuid binds a cookie but has no session row -> empty cart
    with client() as c:
        r = c.get(f"/?sid={uuid.uuid4()}")
        assert r.status_code == 302
        assert "cart is empty" in cart_html(c).lower()
