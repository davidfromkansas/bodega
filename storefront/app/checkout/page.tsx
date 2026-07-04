import { fmtPrice, productBySku } from "@/lib/catalog";
import { computeTotals, getCartLines } from "@/lib/cart";
import { currentSid } from "@/lib/session";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function CheckoutPage({
  searchParams,
}: {
  searchParams: { error?: string };
}) {
  const sid = await currentSid();
  const lines = sid ? await getCartLines(sid) : [];
  const session = sid
    ? await prisma.session.findUnique({ where: { sid } })
    : null;
  const coupon = session?.coupon
    ? await prisma.coupon.findUnique({ where: { code: session.coupon } })
    : null;
  const { subtotal, couponCode, discount, total } = computeTotals(lines, coupon);

  if (lines.length === 0) {
    return (
      <div>
        <h1>Checkout</h1>
        <p id="checkout-empty">Your cart is empty. Add items before checking out.</p>
      </div>
    );
  }

  return (
    <div>
      <h1>Checkout</h1>
      {searchParams.error && (
        <div className="notice error" id="checkout-error">
          {searchParams.error}
        </div>
      )}

      <div className="summary-box" id="checkout-summary">
        {lines.map((l) => {
          const p = productBySku(l.sku);
          return (
            <div key={l.id}>
              <span>
                {p?.name ?? l.sku} ({l.color}/{l.size}) ×{l.qty}
              </span>
              <span>{fmtPrice(l.qty * l.unitPrice)}</span>
            </div>
          );
        })}
        <div>
          <span>Subtotal</span>
          <span>{fmtPrice(subtotal)}</span>
        </div>
        {couponCode && discount > 0 && (
          <div>
            <span>Coupon ({couponCode})</span>
            <span>−{fmtPrice(discount)}</span>
          </div>
        )}
        <div className="total">
          <span>Total</span>
          <span id="checkout-total">{fmtPrice(total)}</span>
        </div>
      </div>

      <form action="/api/checkout" method="POST" className="checkout-form" id="checkout-form">
        <h2>Shipping</h2>
        <label htmlFor="name">Full name</label>
        <input type="text" name="name" id="name" required />
        <label htmlFor="address1">Address</label>
        <input type="text" name="address1" id="address1" required />
        <label htmlFor="city">City</label>
        <input type="text" name="city" id="city" required />
        <label htmlFor="state">State (2 letters)</label>
        <input type="text" name="state" id="state" maxLength={2} required />
        <label htmlFor="zip">ZIP (5 digits)</label>
        <input type="text" name="zip" id="zip" maxLength={5} required />

        <h2>Payment</h2>
        <fieldset>
          <label htmlFor="card">Card number (any 16 digits)</label>
          <input type="text" name="card" id="card" required />
        </fieldset>

        <br />
        <button type="submit" id="place-order" className="btn btn-primary">
          Place order
        </button>
      </form>
    </div>
  );
}
