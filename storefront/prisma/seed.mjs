// Seeds the coupon table (idempotent). Coupon codes appear only in task
// prompts, never anywhere on the site (spec: not guessable from the site).
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

const COUPONS = [
  { code: "SAVE10", type: "percent", value: 10, minSubtotal: 0 },
  { code: "FLAT15", type: "flat", value: 15, minSubtotal: 50 },
  { code: "BODEGA20", type: "percent", value: 20, minSubtotal: 100 },
];

for (const c of COUPONS) {
  await prisma.coupon.upsert({
    where: { code: c.code },
    create: c,
    update: c,
  });
}

console.log(`seeded ${COUPONS.length} coupons`);
await prisma.$disconnect();
