import { NextRequest } from "next/server";
import { placeOrder } from "@/lib/order";
import { redirectWith, resolveSid } from "@/lib/mutation";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const shipping = {
    name: String(form.get("name") ?? ""),
    address1: String(form.get("address1") ?? ""),
    city: String(form.get("city") ?? ""),
    state: String(form.get("state") ?? ""),
    zip: String(form.get("zip") ?? ""),
  };
  const card = String(form.get("card") ?? "");

  const sidInfo = await resolveSid(req);
  const result = await placeOrder(sidInfo.sid, shipping, card);
  if (!result.ok) {
    return redirectWith(req, "/checkout", { error: result.error }, sidInfo);
  }
  return redirectWith(req, `/orders/${result.orderId}`, {}, sidInfo);
}
