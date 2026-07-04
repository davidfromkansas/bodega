import { NextRequest } from "next/server";
import { updateCartLine } from "@/lib/cart";
import { redirectWith, resolveSid } from "@/lib/mutation";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const lineId = String(form.get("line_id") ?? "");
  const qty = Number(form.get("qty") ?? "");

  const sidInfo = await resolveSid(req);
  const result = await updateCartLine(sidInfo.sid, lineId, qty);
  if (!result.ok) {
    return redirectWith(req, "/cart", { error: result.error }, sidInfo);
  }
  return redirectWith(req, "/cart", { notice: "Cart updated" }, sidInfo);
}
