import type { Metadata } from "next";
import Navbar from "@/components/Navbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "myData - Platform Data Mining Terdistribusi",
  description: "Dashboard Monitoring & Eksekusi Klaster Data Mining Terdistribusi UAS Komputasi Paralel",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <head>
        {/* Bootstrap 5 CSS */}
        <link
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
          rel="stylesheet"
          integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH"
          crossOrigin="anonymous"
        />
        {/* Remix Icon CDN */}
        <link
          href="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css"
          rel="stylesheet"
        />
      </head>
      <body className="min-vh-100 d-flex flex-column app-shell">
        <Navbar />
        <main className="container-fluid py-4 px-4 px-lg-5 flex-grow-1 app-main">
          {children}
        </main>
        <footer className="app-footer text-center py-3 mt-auto">
          <small>
            myData Platform © 2026 · UAS Komputasi Paralel dan Sistem Terdistribusi · Tema #5 Distributed Data Mining
          </small>
        </footer>
      </body>
    </html>
  );
}
