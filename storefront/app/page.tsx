import { categories, featuredProducts } from "@/lib/catalog";
import { ProductCard } from "./components";

export const dynamic = "force-dynamic";

export default function HomePage() {
  return (
    <div>
      <h1>Welcome to Bodega</h1>
      <h2>Shop by category</h2>
      <nav className="category-tiles" id="category-tiles">
        {categories().map((c) => (
          <a key={c} href={`/c/${c}`} id={`cat-${c}`}>
            {c}
          </a>
        ))}
      </nav>
      <h2>Featured products</h2>
      <div className="product-grid" id="featured-grid">
        {featuredProducts().map((p) => (
          <ProductCard key={p.sku} p={p} />
        ))}
      </div>
    </div>
  );
}
