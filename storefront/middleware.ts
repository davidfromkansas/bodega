// First request carrying ?sid=<uuid>: bind the sid to an httpOnly cookie and
// 302-redirect to the same URL without the param. Format is validated here;
// existence/expiry are validated at every use in lib/session.ts (an unminted
// sid yields no cart and a verify-404, which the env treats as an infra fault).
import { NextRequest, NextResponse } from "next/server";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SID_COOKIE = "bodega_sid";

export function middleware(req: NextRequest) {
  const sid = req.nextUrl.searchParams.get("sid");
  if (sid && UUID_RE.test(sid)) {
    // Middleware requires an ABSOLUTE redirect URL. Build it from the incoming
    // Host header (what the browser/proxy/Railway actually used) rather than
    // req.nextUrl.origin, which leaks the container hostname behind Docker.
    const host = req.headers.get("host") ?? req.nextUrl.host;
    const proto = req.headers.get("x-forwarded-proto") ?? req.nextUrl.protocol.replace(":", "");
    const url = new URL(req.nextUrl.pathname, `${proto}://${host}`);
    for (const [k, v] of req.nextUrl.searchParams) {
      if (k !== "sid") url.searchParams.set(k, v);
    }
    const res = NextResponse.redirect(url, 302);
    res.cookies.set(SID_COOKIE, sid, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      maxAge: 4 * 60 * 60,
    });
    return res;
  }
  return NextResponse.next();
}

export const config = {
  // pages only; API routes manage cookies themselves
  matcher: ["/((?!api|_next|favicon.ico).*)"],
};
