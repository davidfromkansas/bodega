#!/usr/bin/env python3
"""One-time catalog generator for Bodega.

Produces frozen catalog JSON files (catalog-seed-A.json, catalog-seed-B.json).
Product names/descriptions come from curated word banks (authored once, below);
every numeric/enumerable field is assigned by a seeded PRNG so the output is a
pure function of the seed label. Same invocation => byte-identical output.

Usage:
    python generate_catalog.py --seed-label A --out catalog-seed-A.json
    python generate_catalog.py --seed-label B --out catalog-seed-B.json
"""

import argparse
import json
import random

# ---------------------------------------------------------------------------
# Word banks. Bank A and bank B are disjoint so seed-B is a genuinely
# different store (per plan: eval-ood uses entirely different products).
# ---------------------------------------------------------------------------

BRANDS = {
    "A": [
        "Trailhead", "Northwind", "Cobalt", "Hearthstone", "Luma", "Verano",
        "Ironpeak", "Meadowlark", "Quill", "Solstice", "Bramble", "Atlaswork",
        "Fernway", "Coppertail", "Driftwood",
    ],
    "B": [
        "Sablecrest", "Windermere", "Ochre", "Tidepool", "Marlowe", "Kestrel",
        "Stonebriar", "Palisade", "Juniper", "Lanternfield", "Wrenhouse",
        "Calder", "Mossbeck", "Ferrostat", "Halcyon",
    ],
}

# numeric attribute fields (all products carry all keys; null when N/A)
NUMERIC_FIELDS = [
    "battery_hours", "capacity_liters", "wattage", "weight_grams",
    "screen_inches",
]

CLOTHING_SIZES = ["S", "M", "L", "XL"]
ONE_SIZE = ["One Size"]

COLORS = [
    "black", "white", "blue", "red", "green", "olive", "navy", "gray",
    "tan", "yellow", "orange", "purple", "teal", "maroon", "pink",
]

# Each product type: (type name, sizing mode, applicable numeric fields,
#                     price range (lo, hi))
# sizing: "clothing" -> S..XL, "one" -> One Size
CATEGORIES = {
    "apparel": {
        "types": [
            ("Crewneck Sweater", "clothing", [], (24, 90)),
            ("Denim Jacket", "clothing", [], (45, 140)),
            ("Flannel Shirt", "clothing", [], (25, 75)),
            ("Chino Pants", "clothing", [], (30, 85)),
            ("Hooded Sweatshirt", "clothing", [], (28, 80)),
            ("Puffer Vest", "clothing", [], (40, 130)),
            ("Graphic Tee", "clothing", [], (12, 35)),
            ("Wool Cardigan", "clothing", [], (45, 120)),
            ("Track Jacket", "clothing", [], (35, 95)),
            ("Linen Shirt", "clothing", [], (30, 85)),
            ("Corduroy Pants", "clothing", [], (35, 90)),
            ("Rain Parka", "clothing", [], (60, 180)),
        ],
        "attrs": [
            "organic-cotton", "machine-washable", "slim-fit", "relaxed-fit",
            "wrinkle-resistant", "breathable", "water-repellent", "recycled",
        ],
    },
    "electronics": {
        "types": [
            ("Wireless Earbuds", "one", ["battery_hours"], (25, 220)),
            ("Bluetooth Speaker", "one", ["battery_hours", "wattage"], (20, 260)),
            ("Portable Charger", "one", ["battery_hours", "weight_grams"], (18, 90)),
            ("Smart Display", "one", ["screen_inches", "wattage"], (60, 380)),
            ("Noise-Cancelling Headphones", "one", ["battery_hours"], (60, 420)),
            ("Action Camera", "one", ["battery_hours", "weight_grams"], (90, 480)),
            ("E-Reader", "one", ["battery_hours", "screen_inches"], (80, 300)),
            ("Mechanical Keyboard", "one", ["weight_grams"], (45, 210)),
            ("Wireless Mouse", "one", ["battery_hours", "weight_grams"], (15, 95)),
            ("Fitness Tracker", "one", ["battery_hours", "screen_inches"], (30, 240)),
            ("Desk Lamp", "one", ["wattage"], (18, 85)),
            ("Webcam", "one", [], (25, 160)),
        ],
        "attrs": [
            "wireless", "bluetooth", "rechargeable", "water-resistant",
            "fast-charging", "voice-control", "usb-c", "backlit",
        ],
    },
    "kitchen": {
        "types": [
            ("French Press", "one", ["capacity_liters"], (15, 60)),
            ("Chef's Knife", "one", ["weight_grams"], (20, 160)),
            ("Cast Iron Skillet", "one", ["weight_grams"], (25, 95)),
            ("Electric Kettle", "one", ["capacity_liters", "wattage"], (25, 110)),
            ("Blender", "one", ["capacity_liters", "wattage"], (35, 240)),
            ("Cutting Board", "one", [], (12, 55)),
            ("Dutch Oven", "one", ["capacity_liters", "weight_grams"], (45, 260)),
            ("Toaster Oven", "one", ["wattage"], (40, 220)),
            ("Mixing Bowl Set", "one", ["capacity_liters"], (18, 70)),
            ("Coffee Grinder", "one", ["wattage"], (20, 130)),
            ("Stockpot", "one", ["capacity_liters"], (25, 120)),
            ("Salad Spinner", "one", ["capacity_liters"], (14, 45)),
        ],
        "attrs": [
            "dishwasher-safe", "non-stick", "bpa-free", "stainless-steel",
            "oven-safe", "induction-ready", "cordless", "compact",
        ],
    },
    "outdoors": {
        "types": [
            ("Rain Jacket", "clothing", ["weight_grams"], (50, 190)),
            ("Daypack", "one", ["capacity_liters", "weight_grams"], (30, 150)),
            ("Sleeping Bag", "one", ["weight_grams"], (45, 280)),
            ("Trekking Poles", "one", ["weight_grams"], (25, 130)),
            ("Camp Stove", "one", ["weight_grams", "wattage"], (30, 160)),
            ("Insulated Water Bottle", "one", ["capacity_liters", "weight_grams"], (15, 55)),
            ("Headlamp", "one", ["battery_hours", "weight_grams"], (15, 85)),
            ("Camping Tent", "one", ["weight_grams"], (90, 450)),
            ("Fleece Pullover", "clothing", ["weight_grams"], (30, 110)),
            ("Hiking Gaiters", "one", ["weight_grams"], (18, 60)),
            ("Dry Bag", "one", ["capacity_liters", "weight_grams"], (12, 55)),
            ("Camp Chair", "one", ["weight_grams"], (25, 120)),
        ],
        "attrs": [
            "waterproof", "packable", "hooded", "insulated", "lightweight",
            "windproof", "quick-dry", "reflective",
        ],
    },
    "grocery": {
        "types": [
            ("Single-Origin Coffee Beans", "one", ["weight_grams"], (9, 32)),
            ("Extra Virgin Olive Oil", "one", ["capacity_liters"], (8, 45)),
            ("Wildflower Honey", "one", ["weight_grams"], (7, 28)),
            ("Loose Leaf Tea", "one", ["weight_grams"], (6, 30)),
            ("Dark Chocolate Bar", "one", ["weight_grams"], (3, 14)),
            ("Trail Mix", "one", ["weight_grams"], (5, 20)),
            ("Maple Syrup", "one", ["capacity_liters"], (9, 38)),
            ("Sea Salt Flakes", "one", ["weight_grams"], (4, 18)),
            ("Almond Butter", "one", ["weight_grams"], (7, 24)),
            ("Granola", "one", ["weight_grams"], (5, 19)),
            ("Hot Sauce", "one", ["capacity_liters"], (5, 22)),
            ("Sparkling Water 12-Pack", "one", ["capacity_liters"], (6, 18)),
        ],
        "attrs": [
            "organic", "fair-trade", "gluten-free", "vegan", "non-gmo",
            "small-batch", "sugar-free", "kosher",
        ],
    },
    "home": {
        "types": [
            ("Throw Blanket", "one", ["weight_grams"], (20, 95)),
            ("Scented Candle", "one", ["weight_grams"], (10, 45)),
            ("Ceramic Vase", "one", [], (15, 80)),
            ("Linen Duvet Cover", "one", [], (55, 220)),
            ("Wall Clock", "one", [], (18, 90)),
            ("Floor Lamp", "one", ["wattage"], (45, 210)),
            ("Storage Basket", "one", ["capacity_liters"], (14, 60)),
            ("Area Rug", "one", ["weight_grams"], (60, 380)),
            ("Picture Frame Set", "one", [], (15, 65)),
            ("Humidifier", "one", ["capacity_liters", "wattage"], (30, 140)),
            ("Bookend Pair", "one", ["weight_grams"], (14, 55)),
            ("Table Runner", "one", [], (12, 48)),
        ],
        "attrs": [
            "handmade", "machine-washable", "hypoallergenic", "eco-friendly",
            "stain-resistant", "fade-resistant", "unscented", "dimmable",
        ],
    },
    "toys": {
        "types": [
            ("Building Block Set", "one", ["weight_grams"], (15, 120)),
            ("Wooden Puzzle", "one", [], (10, 45)),
            ("Plush Bear", "one", ["weight_grams"], (10, 40)),
            ("RC Buggy", "one", ["battery_hours", "weight_grams"], (30, 180)),
            ("Board Game", "one", [], (15, 70)),
            ("Craft Kit", "one", [], (10, 40)),
            ("Kite", "one", ["weight_grams"], (8, 35)),
            ("Marble Run", "one", [], (20, 85)),
            ("Play Kitchen Set", "one", ["weight_grams"], (45, 190)),
            ("Card Game", "one", [], (6, 25)),
            ("Science Experiment Kit", "one", [], (18, 75)),
            ("Yo-Yo", "one", ["weight_grams"], (5, 30)),
        ],
        "attrs": [
            "ages-3-plus", "ages-8-plus", "educational", "battery-free",
            "washable", "travel-size", "award-winning", "cooperative",
        ],
    },
    "office": {
        "types": [
            ("Fountain Pen", "one", ["weight_grams"], (12, 90)),
            ("Hardcover Notebook", "one", [], (8, 35)),
            ("Desk Organizer", "one", [], (14, 60)),
            ("Ergonomic Office Chair", "one", ["weight_grams"], (120, 480)),
            ("Monitor Stand", "one", ["weight_grams"], (20, 95)),
            ("Paper Shredder", "one", ["wattage"], (35, 180)),
            ("Whiteboard", "one", [], (18, 85)),
            ("Label Maker", "one", ["battery_hours"], (20, 80)),
            ("Stapler", "one", ["weight_grams"], (6, 28)),
            ("File Cabinet", "one", ["weight_grams"], (60, 260)),
            ("Desk Pad", "one", [], (10, 45)),
            ("Highlighter Set", "one", [], (4, 18)),
        ],
        "attrs": [
            "refillable", "acid-free-paper", "adjustable", "lockable",
            "cable-management", "quiet-operation", "recycled", "magnetic",
        ],
    },
    "sports": {
        "types": [
            ("Yoga Mat", "one", ["weight_grams"], (15, 90)),
            ("Adjustable Dumbbell", "one", ["weight_grams"], (60, 320)),
            ("Foam Roller", "one", ["weight_grams"], (12, 55)),
            ("Jump Rope", "one", ["weight_grams"], (8, 35)),
            ("Resistance Band Set", "one", [], (10, 45)),
            ("Cycling Helmet", "one", ["weight_grams"], (30, 160)),
            ("Running Belt", "one", ["capacity_liters"], (10, 40)),
            ("Kettlebell", "one", ["weight_grams"], (20, 110)),
            ("Swim Goggles", "one", [], (8, 45)),
            ("Tennis Racket", "one", ["weight_grams"], (35, 220)),
            ("Basketball", "one", ["weight_grams"], (15, 70)),
            ("Compression Socks", "clothing", [], (8, 32)),
        ],
        "attrs": [
            "non-slip", "sweat-resistant", "adjustable", "anti-burst",
            "moisture-wicking", "indoor-outdoor", "beginner-friendly", "pro-grade",
        ],
    },
}

# Description language rules (tested in test_catalog.py):
# - NO DIGITS anywhere in a description: numeric facts live only in the
#   structured spec list on the product page, so prose can never contradict
#   or counterfeit an answer.
# - Filler avoids all attribute-vocabulary words, so search cannot get false
#   hits from marketing fluff.
DESCRIPTION_OPENERS = [
    "A dependable everyday pick.",
    "Built to hold up to regular use.",
    "A customer favorite in its category.",
    "Designed with simplicity in mind.",
    "A practical choice for most needs.",
    "Made to be easy to live with.",
    "Thoughtfully designed and easy to use.",
    "A solid staple worth keeping around.",
]

DESCRIPTION_CLOSERS = [
    "Backed by our generous return policy.",
    "Ships in plain recyclable packaging.",
    "Pairs well with other items in this category.",
    "A great gift option year-round.",
    "Loved for its balance of price and quality.",
    "An easy way to upgrade your routine.",
]

# Marketing sludge (WebShop-inspired noise). Digit-free and attribute-neutral.
DESCRIPTION_FILLER = [
    "Our design team obsessed over every detail so you don't have to.",
    "It arrives ready to use straight out of the box.",
    "Customers tell us it quickly becomes the piece they reach for first.",
    "The finish resists everyday wear and keeps looking fresh.",
    "We sweat the small stuff, from stitching to seams to surfaces.",
    "It slots neatly into busy mornings and slow weekends alike.",
    "Every unit is inspected before it leaves our warehouse.",
    "The silhouette is classic enough to outlast passing trends.",
    "You will wonder how you managed without it.",
    "It makes an impression without shouting about it.",
    "Care is simple, so it stays in rotation season after season.",
    "The materials were chosen for how they feel, not just how they look.",
    "It earns its keep in small spaces and big households alike.",
    "Little touches make the difference, and this one is full of them.",
    "Expect compliments; we hear about them all the time.",
    "From the first use, it just makes sense.",
]

# numeric field value generators: (range lo, hi, rounding)
NUMERIC_RANGES = {
    "battery_hours": (4, 60, 0),
    "capacity_liters": (0.3, 30, 1),
    "wattage": (5, 1800, 0),
    "weight_grams": (50, 12000, 0),
    "screen_inches": (5, 15, 1),
}

TARGET_PER_CATEGORY = 90  # 9 categories x 90 = 810 SKUs
FEATURED_PER_CATALOG = 12

CATEGORY_PREFIX = {
    "apparel": "APP", "electronics": "ELC", "kitchen": "KIT",
    "outdoors": "OUT", "grocery": "GRO", "home": "HOM",
    "toys": "TOY", "office": "OFF", "sports": "SPT",
}


def slugify(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-").replace("--", "-")


def gen_product(rng, category, cat_index, brand, type_spec, attrs_pool):
    type_name, sizing, numeric_fields, (price_lo, price_hi) = type_spec
    name = f"{brand} {type_name}"
    assert "|" not in name, f"pipe in product name: {name}"  # A5: parser delimiter

    price = round(rng.uniform(price_lo, price_hi) - 0.01, 2)
    # bias toward retail-looking endings deterministically
    if rng.random() < 0.6:
        price = float(int(price)) + rng.choice([0.99, 0.49, 0.95, 0.00])
    price = round(price, 2)

    rating = round(rng.uniform(3.0, 5.0), 1)
    review_count = rng.randint(0, 1800)

    n_colors = rng.randint(1, 4)
    colors = sorted(rng.sample(COLORS, n_colors))
    sizes = CLOTHING_SIZES if sizing == "clothing" else ONE_SIZE

    stock = {}
    for c in colors:
        for s in sizes:
            stock[f"{c}|{s}"] = 0 if rng.random() < 0.10 else rng.randint(1, 25)

    n_attrs = rng.randint(2, 4)
    attributes = sorted(rng.sample(attrs_pool, n_attrs))

    numerics = {f: None for f in NUMERIC_FIELDS}
    for f in numeric_fields:
        lo, hi, nd = NUMERIC_RANGES[f]
        v = round(rng.uniform(lo, hi), nd)
        numerics[f] = int(v) if nd == 0 else v

    attr_phrase = " and ".join(attributes[:2]).replace("-", " ")
    true_sentence = (
        f"The {name} is a {attr_phrase} {type_name.lower()} "
        f"from our {category} collection."
    )
    n_filler = rng.randint(2, 4)
    filler = rng.sample(DESCRIPTION_FILLER, n_filler)
    # bury the factual sentence at a seeded position inside the sludge
    insert_at = rng.randint(0, n_filler)
    body = filler[:insert_at] + [true_sentence] + filler[insert_at:]
    description = " ".join(
        [rng.choice(DESCRIPTION_OPENERS)] + body + [rng.choice(DESCRIPTION_CLOSERS)]
    )

    sku = f"{CATEGORY_PREFIX[category]}-{cat_index:04d}"
    product = {
        "sku": sku,
        "slug": slugify(name),
        "name": name,
        "category": category,
        "price": price,
        "rating": rating,
        "review_count": review_count,
        "variants": {"color": colors, "size": sizes},
        "stock": stock,
        "attributes": attributes,
        "description": description,
        "featured": False,
    }
    product.update(numerics)
    return product


def generate(seed_label: str):
    rng = random.Random(f"bodega-catalog-{seed_label}")
    brands = BRANDS[seed_label]
    products = []
    used_names = set()

    for category in sorted(CATEGORIES):
        spec = CATEGORIES[category]
        combos = [(b, t) for b in brands for t in spec["types"]]
        rng.shuffle(combos)
        cat_index = 0
        for brand, type_spec in combos:
            if cat_index >= TARGET_PER_CATEGORY:
                break
            name = f"{brand} {type_spec[0]}"
            if name in used_names:
                continue
            used_names.add(name)
            cat_index += 1
            products.append(
                gen_product(rng, category, cat_index, brand, type_spec, spec["attrs"])
            )

    # featured picks: deterministic sample across catalog, must be in stock
    in_stock = [p for p in products if any(v > 0 for v in p["stock"].values())]
    for p in rng.sample(in_stock, FEATURED_PER_CATALOG):
        p["featured"] = True

    products.sort(key=lambda p: p["sku"])
    return {"catalog_seed": seed_label, "products": products}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-label", required=True, choices=["A", "B"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    catalog = generate(args.seed_label)
    with open(args.out, "w") as f:
        json.dump(catalog, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {len(catalog['products'])} products to {args.out}")


if __name__ == "__main__":
    main()
