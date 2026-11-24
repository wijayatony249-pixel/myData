"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "Dashboard Klaster", icon: "ri-dashboard-3-line" },
    { href: "/dataset", label: "Dataset", icon: "ri-database-2-line" },
    { href: "/buat-job", label: "Buat Job", icon: "ri-play-circle-line" },
    { href: "/benchmark", label: "Benchmark", icon: "ri-line-chart-line" },
    { href: "/uji-kegagalan", label: "Uji Kegagalan", icon: "ri-shield-flash-line" },
  ];

  return (
    <nav className="navbar navbar-expand-lg navbar-dark sticky-top px-3 app-navbar">
      <div className="container-fluid">
        <Link href="/" className="navbar-brand d-flex align-items-center fw-bold text-white fs-4">
          <i className="ri-cpu-line me-2 fs-3 brand-mark"></i>
          <span>myData</span>
          <span className="brand-tag ms-2">DISTRIBUTED MINING</span>
        </Link>
        <div className="collapse navbar-collapse show" id="navbarNav">
          <ul className="navbar-nav ms-auto mb-2 mb-lg-0">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <li className="nav-item" key={item.href}>
                  <Link
                    href={item.href}
                    className={`nav-link px-3 d-flex align-items-center ${
                      isActive ? "active text-white fw-bold rounded" : "text-light"
                    }`}
                  >
                    <i className={`${item.icon} me-2 fs-5`}></i>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </nav>
  );
}
