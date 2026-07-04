import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { redirectWith, resolveSid } from "@/lib/mutation";

export const dynamic = "force-dynamic";

const MAX_TRIES = 5; // rate-limit: 5 attempts/sid (spec §2)

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const code = String(form.get("code") ?? "").trim().toUpperCase();

  const sidInfo = await resolveSid(req);
  const session = await prisma.session.findUnique({ where: { sid: sidInfo.sid } });
  if (!session) {
    return redirectWith(req, "/cart", { error: "Session expired" }, sidInfo);
  }
  if (session.couponTries >= MAX_TRIES) {
    return redirectWith(
      req,
      "/cart",
      { error: "Too many coupon attempts" },
      sidInfo
    );
  }
  await prisma.session.update({
    where: { sid: sidInfo.sid },
    data: { couponTries: { increment: 1 } },
  });

  const coupon = await prisma.coupon.findUnique({ where: { code } });
  if (!coupon) {
    return redirectWith(req, "/cart", { error: "Invalid coupon code" }, sidInfo);
  }
  await prisma.session.update({
    where: { sid: sidInfo.sid },
    data: { coupon: code },
  });
  return redirectWith(req, "/cart", { notice: `Coupon ${code} applied` }, sidInfo);
}
