import { prisma } from "./db";
import { computeTotals, getCartLines } from "./cart";

export interface ShippingFields {
  name: string;
  address1: string;
  city: string;
  state: string;
  zip: string;
}

export type CheckoutResult =
  | { ok: true; orderId: string }
  | { ok: false; error: string };

function validShipping(s: ShippingFields): string | null {
  if (!s.name.trim()) return "Name is required";
  if (!s.address1.trim()) return "Address is required";
  if (!s.city.trim()) return "City is required";
  if (!/^[A-Za-z]{2}$/.test(s.state.trim())) return "State must be 2 letters";
  if (!/^\d{5}$/.test(s.zip.trim())) return "ZIP must be 5 digits";
  return null;
}

export async function placeOrder(
  sid: string,
  shipping: ShippingFields,
  cardDigits: string
): Promise<CheckoutResult> {
  const err = validShipping(shipping);
  if (err) return { ok: false, error: err };
  if (!/^\d{16}$/.test(cardDigits.replace(/\s/g, "")))
    return { ok: false, error: "Card number must be 16 digits" };

  const lines = await getCartLines(sid);
  if (lines.length === 0) return { ok: false, error: "Cart is empty" };

  const session = await prisma.session.findUnique({ where: { sid } });
  const coupon = session?.coupon
    ? await prisma.coupon.findUnique({ where: { code: session.coupon } })
    : null;
  const totals = computeTotals(lines, coupon);

  const items = lines.map((l) => ({
    sku: l.sku,
    color: l.color,
    size: l.size,
    qty: l.qty,
    unit_price: l.unitPrice,
  }));

  // per-sid sequential order id (A5: deterministic, no timestamps rendered)
  const priorCount = await prisma.order.count({ where: { sid } });
  const seq = priorCount + 1;
  const orderId = `ord_${sid.slice(0, 8)}_${seq}`;

  await prisma.$transaction([
    prisma.order.create({
      data: {
        id: orderId,
        sid,
        itemsJson: JSON.stringify(items),
        subtotal: totals.subtotal,
        coupon: totals.discount > 0 ? totals.couponCode : null,
        discount: totals.discount,
        total: totals.total,
        shipName: shipping.name.trim(),
        shipAddress1: shipping.address1.trim(),
        shipCity: shipping.city.trim(),
        shipState: shipping.state.trim().toUpperCase(),
        shipZip: shipping.zip.trim(),
        seq,
      },
    }),
    prisma.cartLine.deleteMany({ where: { sid } }),
    prisma.session.update({ where: { sid }, data: { coupon: null } }),
  ]);

  return { ok: true, orderId };
}
