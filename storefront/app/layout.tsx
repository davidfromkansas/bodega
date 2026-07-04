import type { ReactNode } from "react";
import "./globals.css";

export const metadata = { title: "Bodega" };
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <a href="/" id="site-logo" className="logo">
            Bodega
          </a>
          <form action="/search" method="GET" className="search-form">
            <input
              type="text"
              name="q"
              id="search-input"
              placeholder="Search products…"
              aria-label="Search products"
            />
            <button type="submit" id="search-submit" className="btn btn-primary">
              Search
            </button>
          </form>
          <a href="/cart" id="cart-link" className="btn btn-secondary">
            Cart
          </a>
          <a href="/orders" id="orders-link" className="btn btn-secondary">
            Orders
          </a>
        </header>
        <main className="main">{children}</main>
      </body>
    </html>
  );
}
