// Catalog access layer. Products are frozen data (seed JSON), loaded once in
// memory — never stored in the DB, never exposed via any public JSON endpoint
// (ground-truth hygiene: all product data reaches agents as rendered HTML only).
import catalogA from "../seed/catalog-seed-A.json";
import catalogB from "../seed/catalog-seed-B.json";

// BODEGA_CATALOG=B serves the second store (eval-ood). Default: A.
const ACTIVE = process.env.BODEGA_CATALOG === "B" ? catalogB : catalogA;

export interface Product {
  sku: string;
  slug: string;
  name: string;
  category: string;
  price: number;
  rating: number;
  review_count: number;
  variants: { color: string[]; size: string[] };
  stock: Record<string, number>;
  attributes: string[];
  description: string;
  featured: boolean;
  battery_hours: number | null;
  capacity_liters: number | null;
  wattage: number | null;
  weight_grams: number | null;
  screen_inches: number | null;
}

// A5: deterministic ordering everywhere — canonical order is by sku.
const PRODUCTS: Product[] = (ACTIVE.products as unknown as Product[])
  .slice()
  .sort((a, b) => (a.sku < b.sku ? -1 : 1));

const BY_SLUG = new Map(PRODUCTS.map((p) => [p.slug, p]));
const BY_SKU = new Map(PRODUCTS.map((p) => [p.sku, p]));

export function allProducts(): Product[] {
  return PRODUCTS;
}

export function productBySlug(slug: string): Product | undefined {
  return BY_SLUG.get(slug);
}

export function productBySku(sku: string): Product | undefined {
  return BY_SKU.get(sku);
}

export function categories(): string[] {
  return Array.from(new Set(PRODUCTS.map((p) => p.category))).sort();
}

export function featuredProducts(): Product[] {
  return PRODUCTS.filter((p) => p.featured);
}

export function searchProducts(q: string): Product[] {
  const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];
  return PRODUCTS.filter((p) => {
    const hay = `${p.name} ${p.description} ${p.attributes.join(" ")} ${p.category}`.toLowerCase();
    return terms.every((t) => hay.includes(t));
  });
}

export interface CategoryFilters {
  priceMin?: number;
  priceMax?: number;
  ratingMin?: number;
  attrs?: string[];
  sort?: "price_asc" | "price_desc" | "rating";
}

export function filterCategory(category: string, f: CategoryFilters): Product[] {
  let out = PRODUCTS.filter((p) => p.category === category);
  if (f.priceMin !== undefined) out = out.filter((p) => p.price >= f.priceMin!);
  if (f.priceMax !== undefined) out = out.filter((p) => p.price <= f.priceMax!);
  if (f.ratingMin !== undefined) out = out.filter((p) => p.rating >= f.ratingMin!);
  if (f.attrs && f.attrs.length > 0)
    out = out.filter((p) => f.attrs!.every((a) => p.attributes.includes(a)));
  // ties broken by sku for determinism (A5)
  if (f.sort === "price_asc") out.sort((a, b) => a.price - b.price || (a.sku < b.sku ? -1 : 1));
  else if (f.sort === "price_desc") out.sort((a, b) => b.price - a.price || (a.sku < b.sku ? -1 : 1));
  else if (f.sort === "rating") out.sort((a, b) => b.rating - a.rating || (a.sku < b.sku ? -1 : 1));
  return out;
}

export function categoryAttributes(category: string): string[] {
  const s = new Set<string>();
  PRODUCTS.filter((p) => p.category === category).forEach((p) =>
    p.attributes.forEach((a) => s.add(a))
  );
  return Array.from(s).sort();
}

export function stockFor(p: Product, color: string, size: string): number {
  return p.stock[`${color}|${size}`] ?? 0;
}

export function fmtPrice(n: number): string {
  return `$${n.toFixed(2)}`;
}
