import { fmtPrice, productBySlug } from "@/lib/catalog";
import { Thumb } from "../../components";

export const dynamic = "force-dynamic";

const NUMERIC_LABELS: [key: string, label: string, unit: string][] = [
  ["battery_hours", "Battery life", "hours"],
  ["capacity_liters", "Capacity", "liters"],
  ["wattage", "Power", "watts"],
  ["weight_grams", "Weight", "grams"],
  ["screen_inches", "Screen size", "inches"],
];

export default function ProductPage({ params }: { params: { slug: string } }) {
  const p = productBySlug(params.slug);
  if (!p) return <h1>Product not found</h1>;

  return (
    <div className="detail">
      <Thumb p={p} />
      <div className="detail-info">
        <h1 id="product-name">{p.name}</h1>
        <div className="price" id="product-price">
          {fmtPrice(p.price)}
        </div>
        <div className="rating" id="product-rating">
          {p.rating.toFixed(1)}★ ({p.review_count} reviews)
        </div>
        <p id="product-description">{p.description}</p>
        <h2>Details</h2>
        <ul id="product-attributes">
          {p.attributes.map((a) => (
            <li key={a}>{a}</li>
          ))}
          {NUMERIC_LABELS.filter(([k]) => (p as any)[k] !== null).map(
            ([k, label, unit]) => (
              <li key={k} id={`spec-${k}`}>
                {label}: {(p as any)[k]} {unit}
              </li>
            )
          )}
        </ul>
        <h2>Availability</h2>
        <table className="stock-table" id="stock-table">
          <thead>
            <tr>
              <th>Color</th>
              <th>Size</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {p.variants.color.flatMap((c) =>
              p.variants.size.map((s) => (
                <tr key={`${c}|${s}`}>
                  <td>{c}</td>
                  <td>{s}</td>
                  <td>
                    {(p.stock[`${c}|${s}`] ?? 0) > 0 ? "In stock" : "Out of stock"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <h2>Add to cart</h2>
        <form action="/api/cart/add" method="POST">
          <input type="hidden" name="sku" value={p.sku} />
          <div className="variant-row">
            <div>
              <label htmlFor="color">Color</label>
              <select name="color" id="color">
                {p.variants.color.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="size">Size</label>
              <select name="size" id="size">
                {p.variants.size.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="qty">Quantity</label>
              <input
                type="number"
                name="qty"
                id="qty"
                min="1"
                max="25"
                defaultValue="1"
                className="qty-input"
              />
            </div>
          </div>
          <button type="submit" id="add-to-cart" className="btn btn-primary">
            Add to cart
          </button>
        </form>
      </div>
    </div>
  );
}
