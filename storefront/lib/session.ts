// sid <-> cookie binding and session lifecycle.
// - POST /api/sessions (bearer) mints a sid row (env rollouts).
// - middleware.ts binds ?sid=<uuid> to an httpOnly cookie and strips the param.
// - Anonymous visitors get a lazily-minted sid on first mutation.
// TTL is 4 hours (amendment A4: survives training-queue latency).
import { randomUUID } from "crypto";
import { cookies } from "next/headers";
import { prisma } from "./db";

export const SID_COOKIE = "bodega_sid";
export const SESSION_TTL_MS = 4 * 60 * 60 * 1000;

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(s: string): boolean {
  return UUID_RE.test(s);
}

export async function mintSession(): Promise<string> {
  const sid = randomUUID();
  await prisma.session.create({
    data: { sid, expiresAt: new Date(Date.now() + SESSION_TTL_MS) },
  });
  return sid;
}

/** Valid, unexpired session or null. */
export async function getSession(sid: string) {
  if (!isUuid(sid)) return null;
  const s = await prisma.session.findUnique({ where: { sid } });
  if (!s || s.expiresAt.getTime() < Date.now()) return null;
  return s;
}

/** sid from the request cookie, validated against the DB. Null if absent/expired. */
export async function currentSid(): Promise<string | null> {
  const c = cookies().get(SID_COOKIE)?.value;
  if (!c) return null;
  const s = await getSession(c);
  return s ? s.sid : null;
}

export function verifyKeyOk(authHeader: string | null): boolean {
  const key = process.env.BODEGA_VERIFY_KEY;
  if (!key) return false;
  return authHeader === `Bearer ${key}`;
}
