import { prisma } from "./db";
import { productBySku, stockFor } from "./catalog";

export async function getCartLines(sid: string) {
  // A5: deterministic ordering — never DB order
  return prisma.cartLine.findMany({
    where: { sid },
    orderBy: [{ sku: "asc" }, { color: "asc" }, { size: "asc" }],
  });
}

export function cartSubtotal(lines: { qty: number; unitPrice: number }[]) {
  return Math.round(lines.reduce((s, l) => s + l.qty * l.unitPrice, 0) * 100) / 100;
}

export interface Totals {
  subtotal: number;
  couponCode: string | null;
  discount: number;
  total: number;
}

// Single source of truth for money math (cart page, checkout, verify all use it).
// A coupon below its min_subtotal contributes 0 discount but stays "applied".
export function computeTotals(
  lines: { qty: number; unitPrice: number }[],
  coupon: { code: string; type: string; value: number; minSubtotal: number } | null
): Totals {
  const subtotal = cartSubtotal(lines);
  let discount = 0;
  let couponCode: string | null = null;
  if (coupon) {
    couponCode = coupon.code;
    if (subtotal >= coupon.minSubtotal) {
      discount =
        coupon.type === "percent"
          ? Math.round(subtotal * (coupon.value / 100) * 100) / 100
          : Math.min(coupon.value, subtotal);
    }
  }
  const total = Math.round((subtotal - discount) * 100) / 100;
  return { subtotal, couponCode, discount, total };
}

export type AddResult =
  | { ok: true }
  | { ok: false; error: string };

export async function addToCart(
  sid: string,
  sku: string,
  color: string,
  size: string,
  qty: number
): Promise<AddResult> {
  const p = productBySku(sku);
  if (!p) return { ok: false, error: "Unknown product" };
  if (!p.variants.color.includes(color) || !p.variants.size.includes(size))
    return { ok: false, error: "Unknown variant" };
  if (!Number.isInteger(qty) || qty < 1 || qty > 25)
    return { ok: false, error: "Invalid quantity" };
  const available = stockFor(p, color, size);
  const existing = await prisma.cartLine.findFirst({
    where: { sid, sku, color, size },
  });
  const already = existing?.qty ?? 0;
  if (already + qty > available)
    return { ok: false, error: "Not enough stock for that variant" };
  if (existing) {
    await prisma.cartLine.update({
      where: { id: existing.id },
      data: { qty: already + qty },
    });
  } else {
    await prisma.cartLine.create({
      data: { sid, sku, color, size, qty, unitPrice: p.price },
    });
  }
  return { ok: true };
}

export async function updateCartLine(
  sid: string,
  lineId: string,
  qty: number
): Promise<AddResult> {
  const line = await prisma.cartLine.findUnique({ where: { id: lineId } });
  if (!line || line.sid !== sid) return { ok: false, error: "Unknown cart line" };
  if (!Number.isInteger(qty) || qty < 0 || qty > 25)
    return { ok: false, error: "Invalid quantity" };
  if (qty === 0) {
    await prisma.cartLine.delete({ where: { id: lineId } });
    return { ok: true };
  }
  const p = productBySku(line.sku);
  if (p && qty > stockFor(p, line.color, line.size))
    return { ok: false, error: "Not enough stock for that variant" };
  await prisma.cartLine.update({ where: { id: lineId }, data: { qty } });
  return { ok: true };
}

export async function removeCartLine(sid: string, lineId: string): Promise<AddResult> {
  const line = await prisma.cartLine.findUnique({ where: { id: lineId } });
  if (!line || line.sid !== sid) return { ok: false, error: "Unknown cart line" };
  await prisma.cartLine.delete({ where: { id: lineId } });
  return { ok: true };
}
