import { searchProducts } from "@/lib/catalog";
import { ProductCard } from "../components";

export const dynamic = "force-dynamic";

export default function SearchPage({
  searchParams,
}: {
  searchParams: { q?: string; page?: string };
}) {
  const q = (searchParams.q ?? "").trim();
  const results = q ? searchProducts(q) : [];

  const PER_PAGE = 24;
  const pageRaw = Number(searchParams.page ?? "1");
  const totalPages = Math.max(1, Math.ceil(results.length / PER_PAGE));
  const page =
    Number.isInteger(pageRaw) && pageRaw >= 1 ? Math.min(pageRaw, totalPages) : 1;
  const pageResults = results.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  return (
    <div>
      <h1>Search results for “{q}”</h1>
      <p id="result-count">
        {`${results.length} result${results.length === 1 ? "" : "s"} — page ${page} of ${totalPages}`}
      </p>
      <div className="product-grid" id="search-results">
        {pageResults.map((p) => (
          <ProductCard key={p.sku} p={p} />
        ))}
      </div>
      {totalPages > 1 && (
        <nav className="pagination" id="pagination">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) =>
            p === page ? (
              <span key={p} className="page-current" aria-current="page">
                {p}
              </span>
            ) : (
              <a
                key={p}
                href={`/search?q=${encodeURIComponent(q)}&page=${p}`}
                id={`page-${p}`}
              >
                {p}
              </a>
            )
          )}
        </nav>
      )}
    </div>
  );
}
