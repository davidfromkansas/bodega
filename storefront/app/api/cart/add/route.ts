import { NextRequest } from "next/server";
import { addToCart } from "@/lib/cart";
import { redirectWith, resolveSid } from "@/lib/mutation";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const sku = String(form.get("sku") ?? "");
  const color = String(form.get("color") ?? "");
  const size = String(form.get("size") ?? "");
  const qty = Number(form.get("qty") ?? "1");

  const sidInfo = await resolveSid(req);
  const result = await addToCart(sidInfo.sid, sku, color, size, qty);
  if (!result.ok) {
    return redirectWith(req, "/cart", { error: result.error }, sidInfo);
  }
  return redirectWith(req, "/cart", { notice: "Added to cart" }, sidInfo);
}
