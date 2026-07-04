"""Phrasing registers (WebShop-inspired instruction diversity).

Each question kind has several REGISTERS: 0=direct, 1=question, 2=casual,
3=contextual-with-noise. Register 3 is HELD OUT of train-pool and appears only
in eval splits — a language-generalization probe (did the model learn to shop,
or learn our sentence shape?).

Rules every phrasing must obey (unit-tested):
- every spec slot appears verbatim in the final string
- no extra constraint implied (flavor text must be checkably irrelevant)
"""

HELD_OUT_REGISTER = 3
ALL_REGISTERS = [0, 1, 2, 3]
TRAIN_REGISTERS = [0, 1, 2]

# ---- T1 -------------------------------------------------------------------
T1_PRICE = [
    "What is the price of the {name}?",
    "How much does the {name} cost?",
    "I'm looking at the {name} — what's its price?",
    "A friend recommended the {name} and I'm budgeting for it. Look it up and tell me its price.",
]
T1_RATING = [
    "What is the star rating of the {name}?",
    "How is the {name} rated?",
    "Quick check: what rating does the {name} have?",
    "Reviews matter to me. Find the {name} and tell me its star rating.",
]
T1_NUMERIC = [
    "What is the {label} of the {name}?",
    "Can you find the {label} of the {name}?",
    "Spec check on the {name}: what's its {label}?",
    "I'm comparing specs for a purchase later. Find the {name} and report its {label}.",
]
T1_STOCK = [
    "Is the {name} currently in stock in color {color}, size {size}?",
    "Can I buy the {name} in color {color}, size {size} right now?",
    "Stock check: {name}, color {color}, size {size} — available?",
    "Before I plan a gift, check the {name} in color {color}, size {size} and tell me whether it is in stock.",
]

# ---- T2 -------------------------------------------------------------------
T2_CHEAPEST = [
    "Find the cheapest {desc}{cons}.",
    "What is the least expensive {desc}{cons}?",
    "I'm bargain hunting: cheapest {desc}{cons} — which is it?",
    "My budget is tight this month. Search the store for the cheapest {desc}{cons} and report it.",
]
T2_HIGHEST_RATED = [
    "Find the highest-rated {desc}{cons}.",
    "Which {desc}{cons} has the best rating?",
    "Best reviews win: find the top-rated {desc}{cons}.",
    "Quality over price for this one — find me the highest-rated {desc}{cons} in the store.",
]

# ---- T3 -------------------------------------------------------------------
T3_COMPARE = [
    "Of these products: {listing} — which one has the {mode} {label}?",
    "Compare {listing}. Which has the {mode} {label}?",
    "Between {listing}: {mode} {label} — which is it?",
    "I've narrowed my shortlist to {listing}. Check their product pages and tell me which one has the {mode} {label}.",
]

# ---- T4 -------------------------------------------------------------------
T4_CART = [
    "Add the following to your cart and leave it there (do not check out): {listing}. Add nothing else to the cart.",
    "Please put exactly these items in the cart, and nothing more: {listing}. Do not check out.",
    "Cart prep: {listing}. Leave everything in the cart, buy nothing, add nothing extra.",
    "I'll review the cart myself before paying, so just stage it for me: add {listing}. Nothing else goes in, and do not check out.",
]

# ---- T5 -------------------------------------------------------------------
T5_CONSTRAINED = [
    "Build a shopping cart containing exactly {cons}, one unit of each, with a cart subtotal of at most ${budget}. Cheaper carts score higher. Leave the items in the cart; do not check out.",
    "Can you fill a cart with exactly {cons} (one of each) while keeping the subtotal at or under ${budget}? The cheaper the better. Don't check out.",
    "Challenge: exactly {cons}, one each, subtotal ≤ ${budget} — minimize the cost. Leave it all in the cart, no checkout.",
    "I'm putting together a bundle and comparing stores. In this one, build a cart of exactly {cons}, one unit each, subtotal no more than ${budget} — as cheap as you can manage. Leave the cart as-is; do not check out.",
]

# ---- T6 -------------------------------------------------------------------
T6_CHECKOUT = [
    "Purchase the following: {listing}.{coupon} Check out and ship the order to: {address}. Use any 16-digit number for payment. Order exactly these items and nothing else.",
    "Please buy {listing} for me.{coupon} At checkout, ship to {address} and pay with any 16-digit card number. The order must contain exactly these items and nothing else.",
    "Order time: {listing}.{coupon} Shipping goes to {address}; any 16-digit number works for payment. Exactly these items — nothing more, nothing less.",
    "This is a gift order, so get it exactly right: purchase {listing}.{coupon} Ship it to {address}, use any 16-digit number at the payment step, and make sure the order contains exactly these items and nothing else.",
]

BANKS = {
    "t1_price": T1_PRICE,
    "t1_rating": T1_RATING,
    "t1_numeric": T1_NUMERIC,
    "t1_stock": T1_STOCK,
    "t2_cheapest": T2_CHEAPEST,
    "t2_highest_rated": T2_HIGHEST_RATED,
    "t3_compare": T3_COMPARE,
    "t4_cart": T4_CART,
    "t5_constrained": T5_CONSTRAINED,
    "t6_checkout": T6_CHECKOUT,
}


def pick_phrasing(rng, bank_key, registers):
    """Deterministically choose a register index and return (index, template)."""
    reg = rng.choice(sorted(registers))
    return reg, BANKS[bank_key][reg]
