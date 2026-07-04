import { fmtPrice, productBySku } from "@/lib/catalog";
import { currentSid } from "@/lib/session";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

interface Item {
  sku: string;
  color: string;
  size: string;
  qty: number;
  unit_price: number;
}

export default async function OrderDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const sid = await currentSid();
  const order = sid
    ? await prisma.order.findFirst({ where: { id: params.id, sid } })
    : null;

  if (!order) {
    return <h1>Order not found</h1>;
  }

  const items: Item[] = JSON.parse(order.itemsJson);

  return (
    <div>
      <div className="notice" id="order-confirmation">
        Order {order.id} placed successfully.
      </div>
      <h1>Order {order.id}</h1>

      <table className="cart-table" id="order-items">
        <thead>
          <tr>
            <th>Product</th>
            <th>Color</th>
            <th>Size</th>
            <th>Qty</th>
            <th>Unit price</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => {
            const p = productBySku(it.sku);
            return (
              <tr key={i}>
                <td>{p?.name ?? it.sku}</td>
                <td>{it.color}</td>
                <td>{it.size}</td>
                <td>{it.qty}</td>
                <td>{fmtPrice(it.unit_price)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="summary-box" id="order-summary">
        <div>
          <span>Subtotal</span>
          <span>{fmtPrice(order.subtotal)}</span>
        </div>
        {order.coupon && (
          <div>
            <span>Coupon ({order.coupon})</span>
            <span>−{fmtPrice(order.discount)}</span>
          </div>
        )}
        <div className="total">
          <span>Total</span>
          <span>{fmtPrice(order.total)}</span>
        </div>
      </div>

      <h2>Shipping to</h2>
      <address id="order-shipping">
        {order.shipName}
        <br />
        {order.shipAddress1}
        <br />
        {order.shipCity}, {order.shipState} {order.shipZip}
      </address>
    </div>
  );
}
