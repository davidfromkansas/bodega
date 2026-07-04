"""M0 step 3 acceptance: coupons, checkout, orders, and the verify API.

The verify API is the core of the trustworthy-rewards thesis, so these tests
are thorough: bearer auth, 404-on-expired-sid (D6 infra-fault signal),
cart/order/coupon ground-truth shape, and that verify state matches what the
agent actually did via normal form posts.
"""

import json
import os
import uuid
from pathlib import Path

import httpx
import pytest

BASE = os.environ.get("BODEGA_STORE_URL", "http://localhost:3000")
KEY = os.environ.get("BODEGA_VERIFY_KEY", "dev-verify-key")
SEED = Path(__file__).resolve().parent.parent / "seed" / "catalog-seed-A.json"

VALID_SHIPPING = {
    "name": "Ada Lovelace",
    "address1": "12 Analytical Way",
    "city": "London",
    "state": "NY",
    "zip": "10001",
    "card": "4111111111111111",
}


def catalog():
    with open(SEED) as f:
        return json.load(f)["products"]


def client():
    return httpx.Client(base_url=BASE, follow_redirects=False, timeout=30)


def auth():
    return {"Authorization": f"Bearer {KEY}"}


def mint_and_bind(c):
    sid = c.post("/api/sessions", headers=auth()).json()["sid"]
    c.get(f"/?sid={sid}")
    return sid


def verify(c, sid):
    return c.get(f"/api/verify/{sid}", headers=auth())


def add(c, sku, color, size, qty):
    return c.post(
        "/api/cart/add",
        data={"sku": sku, "color": color, "size": size, "qty": qty},
    )


def in_stock_variant(p, need=1):
    for key, n in sorted(p["stock"].items()):
        if n >= need:
            c, s = key.split("|")
            return c, s
    return None


def pick(need=1):
    for p in catalog():
        v = in_stock_variant(p, need)
        if v:
            return p, v
    raise AssertionError("no product with stock")


# ------------------------------------------------------------- verify auth

def test_verify_requires_bearer():
    with client() as c:
        sid = mint_and_bind(c)
        assert c.get(f"/api/verify/{sid}").status_code == 401
        assert c.get(f"/api/verify/{sid}", headers={"Authorization": "Bearer x"}).status_code == 401


def test_verify_404_on_unknown_sid():
    # D6: rubric treats this as an infra fault -> raise, never score 0
    with client() as c:
        assert verify(c, str(uuid.uuid4())).status_code == 404


def test_verify_empty_cart_shape():
    with client() as c:
        sid = mint_and_bind(c)
        r = verify(c, sid)
        assert r.status_code == 200
        body = r.json()
        assert body == {"cart": [], "orders": [], "coupons_applied": []}


# ------------------------------------------------------------- cart verify

def test_verify_reflects_cart_state():
    p, (color, size) = pick(need=2)
    with client() as c:
        sid = mint_and_bind(c)
        add(c, p["sku"], color, size, 2)
        body = verify(c, sid).json()
        assert body["cart"] == [
            {
                "sku": p["sku"],
                "color": color,
                "size": size,
                "qty": 2,
                "unit_price": p["price"],
            }
        ]


# ----------------------------------------------------------------- coupons

def test_valid_coupon_applies_and_shows_in_verify():
    # SAVE10 = 10% off, no minimum
    p, (color, size) = pick()
    with client() as c:
        sid = mint_and_bind(c)
        add(c, p["sku"], color, size, 1)
        r = c.post("/api/cart/coupon", data={"code": "SAVE10"})
        assert "notice" in r.headers["location"]
        assert verify(c, sid).json()["coupons_applied"] == ["SAVE10"]


def test_invalid_coupon_rejected():
    with client() as c:
        sid = mint_and_bind(c)
        r = c.post("/api/cart/coupon", data={"code": "NOPE99"})
        assert "error" in r.headers["location"]
        assert verify(c, sid).json()["coupons_applied"] == []


def test_coupon_below_minimum_not_counted():
    # FLAT15 requires min_subtotal 50; a cheap cart applies but discount stays 0
    cheap = min(
        (p for p in catalog() if in_stock_variant(p)),
        key=lambda p: p["price"],
    )
    color, size = in_stock_variant(cheap)
    with client() as c:
        sid = mint_and_bind(c)
        add(c, cheap["sku"], color, size, 1)
        c.post("/api/cart/coupon", data={"code": "FLAT15"})
        # applied but under minimum -> discount 0 -> not reported as effective
        assert verify(c, sid).json()["coupons_applied"] == []


def test_coupon_rate_limited():
    with client() as c:
        mint_and_bind(c)
        results = []
        for _ in range(7):
            r = c.post("/api/cart/coupon", data={"code": "NOPE"})
            results.append(r.headers["location"])
        assert any("Too+many" in loc or "Too%20many" in loc for loc in results[-2:])


# ---------------------------------------------------------------- checkout

def test_checkout_creates_order_and_clears_cart():
    p, (color, size) = pick(need=2)
    with client() as c:
        sid = mint_and_bind(c)
        add(c, p["sku"], color, size, 2)
        r = c.post("/api/checkout", data=VALID_SHIPPING)
        assert r.status_code == 303
        assert "/orders/ord_" in r.headers["location"]

        body = verify(c, sid).json()
        assert body["cart"] == []  # cart cleared
        assert len(body["orders"]) == 1
        order = body["orders"][0]
        assert order["items"] == [
            {"sku": p["sku"], "color": color, "size": size, "qty": 2, "unit_price": p["price"]}
        ]
        assert order["shipping"]["name"] == "Ada Lovelace"
        assert order["shipping"]["state"] == "NY"
        assert order["shipping"]["zip"] == "10001"


def test_checkout_with_coupon_records_discount():
    # use a cart over $100 to satisfy BODEGA20 (20% off, min 100)
    expensive = max(
        (p for p in catalog() if in_stock_variant(p, 2)),
        key=lambda p: p["price"],
    )
    color, size = in_stock_variant(expensive, 2)
    with client() as c:
        sid = mint_and_bind(c)
        add(c, expensive["sku"], color, size, 2)
        c.post("/api/cart/coupon", data={"code": "BODEGA20"})
        c.post("/api/checkout", data=VALID_SHIPPING)
        order = verify(c, sid).json()["orders"][0]
        assert order["coupon"] == "BODEGA20"
        expected_sub = round(expensive["price"] * 2, 2)
        assert order["subtotal"] == expected_sub
        assert abs(order["discount"] - round(expensive["price"] * 2 * 0.20, 2)) < 0.01
        assert abs(order["total"] - (expected_sub - order["discount"])) < 0.01


def test_checkout_rejects_bad_shipping():
    p, (color, size) = pick()
    with client() as c:
        mint_and_bind(c)
        add(c, p["sku"], color, size, 1)
        bad = dict(VALID_SHIPPING, zip="abc")
        r = c.post("/api/checkout", data=bad)
        assert "error" in r.headers["location"]


def test_checkout_rejects_bad_card():
    p, (color, size) = pick()
    with client() as c:
        mint_and_bind(c)
        add(c, p["sku"], color, size, 1)
        bad = dict(VALID_SHIPPING, card="123")
        r = c.post("/api/checkout", data=bad)
        assert "error" in r.headers["location"]


def test_checkout_empty_cart_rejected():
    with client() as c:
        mint_and_bind(c)
        r = c.post("/api/checkout", data=VALID_SHIPPING)
        assert "error" in r.headers["location"]


def test_orders_isolated_between_sids():
    p, (color, size) = pick(need=2)
    with client() as a, client() as b:
        sid_a = mint_and_bind(a)
        sid_b = mint_and_bind(b)
        add(a, p["sku"], color, size, 1)
        a.post("/api/checkout", data=VALID_SHIPPING)
        # A has one order; B (never ordered) still sees none
        assert len(verify(a, sid_a).json()["orders"]) == 1
        assert verify(b, sid_b).json()["orders"] == []
