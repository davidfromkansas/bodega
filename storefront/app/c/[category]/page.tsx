import {
  categories,
  categoryAttributes,
  filterCategory,
  type CategoryFilters,
} from "@/lib/catalog";
import { ProductCard } from "../../components";

export const dynamic = "force-dynamic";

function num(v: string | undefined): number | undefined {
  if (v === undefined || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export default function CategoryPage({
  params,
  searchParams,
}: {
  params: { category: string };
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const category = params.category;
  if (!categories().includes(category)) {
    return <h1>Category not found</h1>;
  }

  const rawAttrs = searchParams.attr;
  const attrs = Array.isArray(rawAttrs) ? rawAttrs : rawAttrs ? [rawAttrs] : [];
  const sortRaw = typeof searchParams.sort === "string" ? searchParams.sort : "";
  const filters: CategoryFilters = {
    priceMin: num(searchParams.price_min as string | undefined),
    priceMax: num(searchParams.price_max as string | undefined),
    ratingMin: num(searchParams.rating_min as string | undefined),
    attrs,
    sort: ["price_asc", "price_desc", "rating"].includes(sortRaw)
      ? (sortRaw as CategoryFilters["sort"])
      : undefined,
  };
  const results = filterCategory(category, filters);

  const PER_PAGE = 24;
  const pageRaw = Number(searchParams.page ?? "1");
  const totalPages = Math.max(1, Math.ceil(results.length / PER_PAGE));
  const page = Number.isInteger(pageRaw) && pageRaw >= 1 ? Math.min(pageRaw, totalPages) : 1;
  const pageResults = results.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  const pageHref = (p: number) => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(searchParams)) {
      if (k === "page" || v === undefined) continue;
      if (Array.isArray(v)) v.forEach((x) => params.append(k, x));
      else params.set(k, v);
    }
    params.set("page", String(p));
    return `/c/${category}?${params.toString()}`;
  };

  return (
    <div>
      <h1>{category}</h1>
      {/* Filters are plain GET forms (spec §2) */}
      <form method="GET" className="filters" id="filter-form">
        <div>
          <label htmlFor="price_min">Min price</label>
          <input
            type="number"
            step="0.01"
            name="price_min"
            id="price_min"
            defaultValue={searchParams.price_min as string | undefined}
          />
        </div>
        <div>
          <label htmlFor="price_max">Max price</label>
          <input
            type="number"
            step="0.01"
            name="price_max"
            id="price_max"
            defaultValue={searchParams.price_max as string | undefined}
          />
        </div>
        <div>
          <label htmlFor="rating_min">Min rating</label>
          <input
            type="number"
            step="0.1"
            min="0"
            max="5"
            name="rating_min"
            id="rating_min"
            defaultValue={searchParams.rating_min as string | undefined}
          />
        </div>
        <div>
          <label htmlFor="sort">Sort by</label>
          <select name="sort" id="sort" defaultValue={sortRaw}>
            <option value="">Default</option>
            <option value="price_asc">Price: low to high</option>
            <option value="price_desc">Price: high to low</option>
            <option value="rating">Rating</option>
          </select>
        </div>
        <div className="attr-checks" id="attr-checks">
          {categoryAttributes(category).map((a) => (
            <label key={a}>
              <input
                type="checkbox"
                name="attr"
                value={a}
                id={`attr-${a}`}
                defaultChecked={attrs.includes(a)}
              />
              {a}
            </label>
          ))}
        </div>
        <button type="submit" id="apply-filters" className="btn btn-primary">
          Apply filters
        </button>
      </form>
      <p id="result-count">
        {`${results.length} product${results.length === 1 ? "" : "s"} — page ${page} of ${totalPages}`}
      </p>
      <div className="product-grid" id="category-results">
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
              <a key={p} href={pageHref(p)} id={`page-${p}`}>
                {p}
              </a>
            )
          )}
        </nav>
      )}
    </div>
  );
}
