// Private verification endpoint (bearer BODEGA_VERIFY_KEY). The rubric reads
// TRUE backend state here — cart, orders, applied coupons — to score rollouts.
// 404 on unknown/expired sid (rubric treats that as an infra fault -> raise, D6).
// Unreachable without the key from the browser's network position.
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { computeTotals } from "@/lib/cart";
import { getSession, verifyKeyOk } from "@/lib/session";

export const dynamic = "force-dynamic";

interface Item {
  sku: string;
  color: string;
  size: string;
  qty: number;
  unit_price: number;
}

export async function GET(
  req: NextRequest,
  { params }: { params: { sid: string } }
) {
  if (!verifyKeyOk(req.headers.get("authorization"))) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const session = await getSession(params.sid);
  if (!session) {
    return NextResponse.json({ error: "unknown or expired sid" }, { status: 404 });
  }
  const sid = session.sid;

  const [lines, orders] = await Promise.all([
    prisma.cartLine.findMany({
      where: { sid },
      orderBy: [{ sku: "asc" }, { color: "asc" }, { size: "asc" }],
    }),
    prisma.order.findMany({ where: { sid }, orderBy: { seq: "asc" } }),
  ]);

  const cart: Item[] = lines.map((l) => ({
    sku: l.sku,
    color: l.color,
    size: l.size,
    qty: l.qty,
    unit_price: l.unitPrice,
  }));

  const couponsApplied = new Set<string>();
  const cartCoupon = session.coupon
    ? await prisma.coupon.findUnique({ where: { code: session.coupon } })
    : null;
  const cartTotals = computeTotals(lines, cartCoupon);
  if (cartTotals.couponCode && cartTotals.discount > 0)
    couponsApplied.add(cartTotals.couponCode);

  const orderPayload = orders.map((o) => {
    if (o.coupon) couponsApplied.add(o.coupon);
    return {
      order_id: o.id,
      items: JSON.parse(o.itemsJson) as Item[],
      subtotal: o.subtotal,
      coupon: o.coupon,
      discount: o.discount,
      total: o.total,
      shipping: {
        name: o.shipName,
        address1: o.shipAddress1,
        city: o.shipCity,
        state: o.shipState,
        zip: o.shipZip,
      },
    };
  });

  return NextResponse.json({
    cart,
    orders: orderPayload,
    coupons_applied: Array.from(couponsApplied).sort(),
  });
}
