import type { Product } from "@/lib/catalog";
import { fmtPrice } from "@/lib/catalog";

// Deterministic placeholder "image": colored block + product name (spec §2).
const PALETTE = [
  "#4a6fa5", "#6b4aa5", "#a54a6f", "#4aa58a",
  "#a5804a", "#5d8a4a", "#7a7a7a", "#8a4a4a",
];

export function thumbColor(sku: string): string {
  let h = 0;
  for (const ch of sku) h = (h * 31 + ch.charCodeAt(0)) % 997;
  return PALETTE[h % PALETTE.length];
}

export function Thumb({ p }: { p: Product }) {
  return (
    <div className="thumb" style={{ background: thumbColor(p.sku) }}>
      {p.name}
    </div>
  );
}

export function ProductCard({ p }: { p: Product }) {
  return (
    <div className="product-card" id={`card-${p.sku}`}>
      <Thumb p={p} />
      <a className="name" href={`/p/${p.slug}`}>
        {p.name}
      </a>
      <div className="price">{fmtPrice(p.price)}</div>
      <div className="rating">
        {p.rating.toFixed(1)}★ ({p.review_count} reviews)
      </div>
    </div>
  );
}
