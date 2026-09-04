"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";

interface UserInfo {
  id: string;
  name: string;
  email: string;
  role: string;
  gender?: string;
  phone?: string;
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const token = localStorage.getItem("token");
    const userData = localStorage.getItem("user");
    if (!token || !userData) {
      router.push("/login");
      return;
    }
    try {
      setUser(JSON.parse(userData));
    } catch {
      router.push("/login");
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  if (!mounted || !user) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span className="spinner spinner-lg" />
      </div>
    );
  }

  // Ornab: added nav links for Rides (surge + cost splitter) and Eco Tracker
  const navLinks = [
    { href: "/dashboard", label: "🗺️  Map & Tracking", section: "ride" },
    { href: "/dashboard/rides", label: "🚗  Rides & Surge", section: "ride" },
    { href: "/dashboard/wallet", label: "💳  Wallet & bKash", section: "ride" },
    { href: "/dashboard/earnings", label: "💰  Driver Earnings", section: "ride" },
    { href: "/dashboard/history", label: "🧾  Ride History", section: "ride" },
    { href: "/dashboard/driver", label: "🚗  Driver Verification", section: "ride" },
    { href: "/dashboard/eco", label: "🌱  Eco Tracker", section: "ride" },
    { href: "/dashboard/complaints", label: "📋  Complaints", section: "safety" },
    { href: "/dashboard/contacts", label: "👥  Trusted Contacts", section: "safety" },
  ];

  return (
    <div className="dashboard-layout">
      <aside className="sidebar">
        <Link href="/" className="sidebar-logo">Arooohi</Link>

        <nav className="sidebar-nav">
          <div className="sidebar-section">Navigation</div>
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`sidebar-link ${pathname === link.href ? "active" : ""}`}
            >
              {link.label}
            </Link>
          ))}

          {user.role === "admin" && (
            <>
              <div className="sidebar-section" style={{ marginTop: 16 }}>Admin</div>
              <Link href="/admin" className={`sidebar-link ${pathname === "/admin" ? "active" : ""}`}>
                📊  Dashboard
              </Link>
              <Link href="/admin/complaints" className={`sidebar-link ${pathname === "/admin/complaints" ? "active" : ""}`}>
                🛡️  Complaint Panel
              </Link>
              <Link href="/admin/drivers" className={`sidebar-link ${pathname === "/admin/drivers" ? "active" : ""}`}>
                📄  Driver Verification
              </Link>
            </>
          )}
        </nav>

        <div className="sidebar-bottom">
          <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)", marginBottom: 4 }}>{user.name}</div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)", marginBottom: 12 }}>{user.email}</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className={`badge ${user.role === "admin" ? "badge-accent" : user.role === "driver" ? "badge-primary" : "badge-info"}`}>
              {user.role}
            </span>
          </div>
          <button onClick={handleLogout} className="btn btn-ghost btn-sm" style={{ width: "100%", marginTop: 12 }}>
            Logout
          </button>
        </div>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
