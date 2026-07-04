import { fmtPrice } from "@/lib/catalog";
import { currentSid } from "@/lib/session";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function OrdersPage() {
  const sid = await currentSid();
  const orders = sid
    ? await prisma.order.findMany({
        where: { sid },
        orderBy: { seq: "asc" }, // A5: deterministic, no timestamps
      })
    : [];

  return (
    <div>
      <h1>Your orders</h1>
      {orders.length === 0 ? (
        <p id="orders-empty">You have no orders yet.</p>
      ) : (
        <ul id="orders-list">
          {orders.map((o) => (
            <li key={o.id}>
              <a href={`/orders/${o.id}`} id={`order-${o.id}`}>
                {o.id}
              </a>{" "}
              — {fmtPrice(o.total)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
