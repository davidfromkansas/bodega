"""M0 step 1 acceptance tests: catalog schema validation + invariant checks."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"

REQUIRED_FIELDS = {
    "sku": str, "slug": str, "name": str, "category": str,
    "price": float, "rating": float, "review_count": int,
    "variants": dict, "stock": dict, "attributes": list,
    "description": str, "featured": bool,
}
NUMERIC_FIELDS = ["battery_hours", "capacity_liters", "wattage", "weight_grams", "screen_inches"]
CATEGORIES = {"apparel", "electronics", "kitchen", "outdoors", "grocery", "home", "toys", "office", "sports"}


def load(label):
    with open(SEED_DIR / f"catalog-seed-{label}.json") as f:
        return json.load(f)


@pytest.fixture(scope="module", params=["A", "B"])
def catalog(request):
    return load(request.param)


def test_product_count(catalog):
    assert len(catalog["products"]) == 810


def test_schema(catalog):
    for p in catalog["products"]:
        for field, typ in REQUIRED_FIELDS.items():
            assert field in p, f"{p.get('sku')}: missing {field}"
            if typ is float:
                assert isinstance(p[field], (int, float))
            else:
                assert isinstance(p[field], typ), f"{p['sku']}: {field} wrong type"
        for f in NUMERIC_FIELDS:
            assert f in p
            assert p[f] is None or isinstance(p[f], (int, float))
        assert p["category"] in CATEGORIES


def test_unique_skus_slugs_names(catalog):
    products = catalog["products"]
    for key in ("sku", "slug", "name"):
        vals = [p[key] for p in products]
        assert len(vals) == len(set(vals)), f"duplicate {key}"


def test_no_pipe_in_names(catalog):
    # A5: '|' is the ANSWER parser delimiter
    for p in catalog["products"]:
        assert "|" not in p["name"], p["sku"]


def test_per_variant_stock_present(catalog):
    for p in catalog["products"]:
        expected = {
            f"{c}|{s}"
            for c in p["variants"]["color"]
            for s in p["variants"]["size"]
        }
        assert set(p["stock"].keys()) == expected, p["sku"]
        for v in p["stock"].values():
            assert isinstance(v, int) and v >= 0


def test_value_ranges(catalog):
    for p in catalog["products"]:
        assert 0 < p["price"] < 1000
        assert p["price"] == round(p["price"], 2)
        assert 3.0 <= p["rating"] <= 5.0
        assert 0 <= p["review_count"] <= 2000


def _filler_only(p):
    """Description minus the factual sentence (which may legitimately contain
    digits/attribute words via the product name, e.g. 'Sparkling Water 12-Pack',
    'Hooded Sweatshirt')."""
    import re
    desc = p["description"].lower()
    name = re.escape(p["name"].lower())
    return re.sub(rf"the {name} is a .*? collection\.", "", desc)


def test_filler_has_no_digits(catalog):
    # Numeric facts live ONLY in structured spec fields; prose digits could
    # contradict or counterfeit an answer key.
    for p in catalog["products"]:
        assert not any(ch.isdigit() for ch in _filler_only(p)), p["sku"]


def test_description_contains_true_attribute_sentence(catalog):
    for p in catalog["products"]:
        attr_phrase = " and ".join(p["attributes"][:2]).replace("-", " ")
        assert f"is a {attr_phrase}" in p["description"], p["sku"]


def test_filler_is_attribute_neutral(catalog):
    # Filler must never mention attribute vocabulary -> no false search hits.
    all_attrs = set()
    for p in catalog["products"]:
        all_attrs.update(a.replace("-", " ") for a in p["attributes"])
    for p in catalog["products"]:
        rest = _filler_only(p)
        for attr in all_attrs:
            assert attr not in rest, f"{p['sku']}: filler leaks attribute '{attr}'"


def test_featured_count_and_in_stock(catalog):
    featured = [p for p in catalog["products"] if p["featured"]]
    assert len(featured) == 12
    for p in featured:
        assert any(v > 0 for v in p["stock"].values()), p["sku"]


def test_seed_a_b_disjoint_products():
    names_a = {p["name"] for p in load("A")["products"]}
    names_b = {p["name"] for p in load("B")["products"]}
    assert not names_a & names_b, "seed A and B share product names"


@pytest.mark.parametrize("label", ["A", "B"])
def test_determinism_regenerate_byte_identical(label, tmp_path):
    out = tmp_path / "regen.json"
    subprocess.run(
        [sys.executable, str(SEED_DIR / "generate_catalog.py"),
         "--seed-label", label, "--out", str(out)],
        check=True, capture_output=True,
    )
    frozen = (SEED_DIR / f"catalog-seed-{label}.json").read_bytes()
    assert out.read_bytes() == frozen, f"seed {label} regeneration is not byte-identical"
