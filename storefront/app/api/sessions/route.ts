// Private endpoint (bearer BODEGA_VERIFY_KEY): mints a per-rollout sid.
import { NextRequest, NextResponse } from "next/server";
import { mintSession, verifyKeyOk } from "@/lib/session";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  if (!verifyKeyOk(req.headers.get("authorization"))) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const sid = await mintSession();
  return NextResponse.json({ sid });
}
