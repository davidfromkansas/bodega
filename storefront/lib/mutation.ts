// Shared plumbing for form-POST mutation endpoints: resolve the caller's sid
// (minting an anonymous session for cookie-less human visitors), run the
// operation, then 303-redirect back to a page with a notice/error.
import { NextRequest, NextResponse } from "next/server";
import { SID_COOKIE, getSession, mintSession } from "./session";

export async function resolveSid(
  req: NextRequest
): Promise<{ sid: string; setCookie: boolean }> {
  const fromCookie = req.cookies.get(SID_COOKIE)?.value;
  if (fromCookie) {
    const s = await getSession(fromCookie);
    if (s) return { sid: s.sid, setCookie: false };
  }
  const sid = await mintSession();
  return { sid, setCookie: true };
}

export function redirectWith(
  req: NextRequest,
  path: string,
  params: Record<string, string>,
  sidInfo: { sid: string; setCookie: boolean }
): NextResponse {
  // Relative Location so the browser resolves it against its own host.
  // Building an absolute URL from req.nextUrl.origin leaks the container
  // hostname (e.g. http://<id>:3000) behind Docker/proxies/Railway.
  const qs = new URLSearchParams(params).toString();
  const location = qs ? `${path}?${qs}` : path;
  const res = new NextResponse(null, {
    status: 303,
    headers: { Location: location },
  });
  if (sidInfo.setCookie) {
    res.cookies.set(SID_COOKIE, sidInfo.sid, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      maxAge: 4 * 60 * 60,
    });
  }
  return res;
}
