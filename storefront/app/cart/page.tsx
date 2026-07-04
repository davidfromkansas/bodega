import { fmtPrice, productBySku } from "@/lib/catalog";
import { computeTotals, getCartLines } from "@/lib/cart";
import { currentSid } from "@/lib/session";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function CartPage({
  searchParams,
}: {
  searchParams: { error?: string; notice?: string };
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

  return (
    <div>
      <h1>Your cart</h1>
      {searchParams.error && (
        <div className="notice error" id="cart-error">
          {searchParams.error}
        </div>
      )}
      {searchParams.notice && (
        <div className="notice" id="cart-notice">
          {searchParams.notice}
        </div>
      )}
      {lines.length === 0 ? (
        <p id="cart-empty">Your cart is empty.</p>
      ) : (
        <div>
          <table className="cart-table" id="cart-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Color</th>
                <th>Size</th>
                <th>Unit price</th>
                <th>Quantity</th>
                <th>Line total</th>
                <th>Remove</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((l) => {
                const p = productBySku(l.sku);
                return (
                  <tr key={l.id} id={`line-${l.sku}-${l.color}-${l.size}`}>
                    <td>
                      <a href={`/p/${p?.slug ?? ""}`}>{p?.name ?? l.sku}</a>
                    </td>
                    <td>{l.color}</td>
                    <td>{l.size}</td>
                    <td>{fmtPrice(l.unitPrice)}</td>
                    <td>
                      <form
                        action="/api/cart/update"
                        method="POST"
                        className="inline-form"
                      >
                        <input type="hidden" name="line_id" value={l.id} />
                        <input
                          type="number"
                          name="qty"
                          min="0"
                          max="25"
                          defaultValue={l.qty}
                          className="qty-input"
                          aria-label="Quantity"
                        />
                        <button type="submit" className="btn btn-secondary">
                          Update
                        </button>
                      </form>
                    </td>
                    <td>{fmtPrice(l.qty * l.unitPrice)}</td>
                    <td>
                      <form action="/api/cart/remove" method="POST">
                        <input type="hidden" name="line_id" value={l.id} />
                        <button type="submit" className="btn btn-danger">
                          Remove
                        </button>
                      </form>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <h2>Coupon</h2>
          <form
            action="/api/cart/coupon"
            method="POST"
            className="inline-form"
            id="coupon-form"
          >
            <input
              type="text"
              name="code"
              id="coupon-code"
              placeholder="Coupon code"
              className="qty-input"
              style={{ width: 180 }}
            />
            <button type="submit" id="apply-coupon" className="btn btn-secondary">
              Apply coupon
            </button>
          </form>

          <div className="summary-box" id="cart-summary">
            <div>
              <span>Subtotal</span>
              <span id="cart-subtotal">{fmtPrice(subtotal)}</span>
            </div>
            {couponCode && (
              <div>
                <span>Coupon ({couponCode})</span>
                <span id="cart-discount">−{fmtPrice(discount)}</span>
              </div>
            )}
            <div className="total">
              <span>Total</span>
              <span id="cart-total">{fmtPrice(total)}</span>
            </div>
          </div>

          <a href="/checkout" id="checkout-link" className="btn btn-primary">
            Checkout
          </a>
        </div>
      )}
    </div>
  );
}
