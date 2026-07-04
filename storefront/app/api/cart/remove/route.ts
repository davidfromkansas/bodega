import { NextRequest } from "next/server";
import { removeCartLine } from "@/lib/cart";
import { redirectWith, resolveSid } from "@/lib/mutation";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const lineId = String(form.get("line_id") ?? "");

  const sidInfo = await resolveSid(req);
  const result = await removeCartLine(sidInfo.sid, lineId);
  if (!result.ok) {
    return redirectWith(req, "/cart", { error: result.error }, sidInfo);
  }
  return redirectWith(req, "/cart", { notice: "Item removed" }, sidInfo);
}
